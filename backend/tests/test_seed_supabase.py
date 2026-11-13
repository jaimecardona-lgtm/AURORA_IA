"""Pruebas del sembrador DEMO-AURORA- con un servidor FastAPI SIMULADO en memoria (sin red ni Supabase).

Verifican: forma del dataset, idempotencia (segunda ejecución sin duplicados), prefijo, y que el
sembrador solo usa endpoints normales de la API (ninguno de administración).
"""

import importlib.util
import json
import re
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

RUTA = Path(__file__).resolve().parents[1] / "tools" / "seed_supabase.py"
spec = importlib.util.spec_from_file_location("seed_supabase", RUTA)
seed = importlib.util.module_from_spec(spec)
import sys
sys.modules["seed_supabase"] = seed
spec.loader.exec_module(seed)


class ApiSimulada:
    """Imita las rutas que usa el sembrador: asignaturas, notas, presupuesto, gastos y tareas."""

    def __init__(self):
        self.subjects, self.grades, self.budgets, self.expenses, self.tasks = [], [], {}, [], []
        self.llamadas = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.llamadas.append((request.method, request.url.path))
        ruta, metodo = request.url.path, request.method
        cuerpo = json.loads(request.content) if request.content else {}
        if ruta == "/api/subjects" and metodo == "GET":
            return httpx.Response(200, json=[dict(s) for s in self.subjects])
        if ruta == "/api/subjects" and metodo == "POST":
            fila = {"id": str(uuid.uuid4()), "nombre": cuerpo["nombre"], "total_notas": 0}
            self.subjects.append(fila)
            return httpx.Response(201, json=fila)
        m = re.fullmatch(r"/api/subjects/([^/]+)", ruta)
        if m and metodo == "GET":
            subj = next(s for s in self.subjects if s["id"] == m.group(1))
            notas = [dict(n) for n in self.grades if n["subject_id"] == subj["id"]]
            return httpx.Response(200, json={**subj, "notas": notas})
        m = re.fullmatch(r"/api/subjects/([^/]+)/grades", ruta)
        if m and metodo == "POST":
            fila = {"id": str(uuid.uuid4()), "subject_id": m.group(1), "descripcion": cuerpo["descripcion"], "nota": cuerpo["nota"]}
            self.grades.append(fila)
            return httpx.Response(201, json=fila)
        m = re.fullmatch(r"/api/finanzas/presupuestos/(\d+)/(\d+)", ruta)
        if m and metodo == "PUT":
            clave = (m.group(1), m.group(2))
            self.budgets[clave] = {"ingreso": cuerpo["ingreso"], "meta_ahorro": cuerpo["meta_ahorro"]}
            return httpx.Response(200, json={})
        if m and metodo == "GET":
            clave = (m.group(1), m.group(2))
            if clave not in self.budgets:
                return httpx.Response(404, json={"detail": "No hay presupuesto registrado para ese mes."})
            pres = self.budgets[clave]
            gastos = [g for g in self.expenses]
            total = sum(Decimal(g["monto"]) for g in gastos)
            saldo = Decimal(pres["ingreso"]) - total
            return httpx.Response(200, json={"ingreso": pres["ingreso"], "meta_ahorro": pres["meta_ahorro"], "gastos": gastos,
                                             "saldo": str(saldo), "meta_cumplida": saldo >= Decimal(pres["meta_ahorro"])})
        m = re.fullmatch(r"/api/finanzas/presupuestos/(\d+)/(\d+)/gastos", ruta)
        if m and metodo == "POST":
            fila = {"id": str(uuid.uuid4()), **cuerpo}
            self.expenses.append(fila)
            return httpx.Response(201, json=fila)
        if ruta == "/api/tareas" and metodo == "GET":
            return httpx.Response(200, json=[dict(t) for t in self.tasks])
        if ruta == "/api/tareas" and metodo == "POST":
            fila = {"id": str(uuid.uuid4()), **cuerpo}
            self.tasks.append(fila)
            return httpx.Response(201, json=fila)
        return httpx.Response(404, json={"detail": "no simulado"})


_CLIENTE_REAL = httpx.Client


def _cliente_simulado(api: ApiSimulada):
    """Fábrica que sustituye httpx.Client por el cliente con transporte simulado (sin recursión)."""
    def fabrica(**kw):
        return _CLIENTE_REAL(base_url="http://simulado", transport=httpx.MockTransport(api.handler), headers=kw.get("headers"))
    return fabrica


def _sembrador(api: ApiSimulada, hoy=date(2026, 11, 12)):
    cliente = httpx.Client(base_url="http://simulado", transport=httpx.MockTransport(api.handler))
    return seed.Sembrador(cliente, hoy=hoy)


def test_dataset_cuenta_a_cumple_los_requisitos_de_la_fase():
    asig = seed.ASIGNATURAS_A
    assert len(asig) == 6
    assert all(2 <= len(notas) <= 4 for notas in asig.values())
    notas = [Decimal(n) for ns in asig.values() for _, n in ns]
    assert all(Decimal("0") <= n <= Decimal("5") for n in notas)
    promedios = {k: sum(Decimal(n) for _, n in v) / len(v) for k, v in asig.items()}
    assert any(p >= Decimal("3") for p in promedios.values()) and any(p < Decimal("3") for p in promedios.values())
    assert seed.PRESUPUESTO_A == {"ingreso": "2800000.00", "meta_ahorro": "500000.00"}
    assert len(seed.GASTOS_A) == 8
    assert {c for _, _, _, c, _ in seed.GASTOS_A} >= {"Alimentación", "Transporte", "Vivienda", "Servicios", "Educación", "Entretenimiento"}
    assert {t for _, _, t, _, _ in seed.GASTOS_A} == {"fijo", "variable"}
    assert len(seed.TAREAS_A) == 10
    assert {p for _, p, _, _ in seed.TAREAS_A} == {"alta", "media", "baja"}
    assert {e for _, _, e, _ in seed.TAREAS_A} == {"pendiente", "completada"}
    desplaz = [d for *_, d in seed.TAREAS_A if d is not None]
    assert any(d < 0 for d in desplaz) and any(0 < d <= 7 for d in desplaz) and any(d > 7 for d in desplaz)


def test_gastos_son_fechas_validas_dentro_de_noviembre_y_suman_el_saldo_esperado():
    for _, monto, _, _, dia in seed.GASTOS_A:
        date(2026, 11, dia)  # lanza si la fecha no existe
        assert Decimal(monto) > 0
    total = sum(Decimal(m) for _, m, *_ in seed.GASTOS_A)
    saldo = Decimal(seed.PRESUPUESTO_A["ingreso"]) - total
    assert total == Decimal("2270000.00")
    assert saldo == Decimal("530000.00") and saldo >= Decimal(seed.PRESUPUESTO_A["meta_ahorro"])


def test_primera_ejecucion_crea_todo_y_la_segunda_no_duplica():
    api = ApiSimulada()
    s1 = _sembrador(api)
    s1.academico(seed.ASIGNATURAS_A, "A")
    s1.finanzas(seed.PRESUPUESTO_A, seed.GASTOS_A, "A")
    s1.tareas(seed.TAREAS_A, "A")
    assert s1.resumen.creados == {"asignaturas": 6, "notas": sum(len(v) for v in seed.ASIGNATURAS_A.values()),
                                  "presupuestos": 1, "gastos": 8, "tareas": 10}

    antes = (len(api.subjects), len(api.grades), len(api.expenses), len(api.tasks))
    s2 = _sembrador(api)
    s2.academico(seed.ASIGNATURAS_A, "A")
    s2.finanzas(seed.PRESUPUESTO_A, seed.GASTOS_A, "A")
    s2.tareas(seed.TAREAS_A, "A")
    despues = (len(api.subjects), len(api.grades), len(api.expenses), len(api.tasks))
    assert antes == despues, "la segunda ejecución duplicó registros"
    assert s2.resumen.creados == {}


def test_prefijo_identifica_los_registros_y_no_toca_otras_cuentas():
    api = ApiSimulada()
    _sembrador(api).academico(seed.ASIGNATURAS_B, "B")
    _sembrador(api).tareas(seed.TAREAS_A, "A")
    assert all(s["nombre"].startswith("DEMO-AURORA-B-") for s in api.subjects)
    assert all(t["titulo"].startswith("DEMO-AURORA-A-") for t in api.tasks)
    assert all(t["titulo"].startswith("DEMO-AURORA-") for t in api.tasks)


def test_verificacion_lee_solo_registros_de_la_cuenta():
    api = ApiSimulada()
    s = _sembrador(api)
    s.academico(seed.ASIGNATURAS_A, "A")
    s.academico(seed.ASIGNATURAS_B, "B")
    s.finanzas(seed.PRESUPUESTO_A, seed.GASTOS_A, "A")
    s.tareas(seed.TAREAS_A, "A")
    resultado = s.verificar("A")
    assert resultado["asignaturas"] == 6
    assert resultado["tareas"] == 10
    assert resultado["gastos_del_mes"] == 8
    assert resultado["meta_cumplida"] is True


def test_el_sembrador_solo_usa_endpoints_normales_de_la_api():
    api = ApiSimulada()
    s = _sembrador(api)
    s.academico(seed.ASIGNATURAS_A, "A")
    s.finanzas(seed.PRESUPUESTO_A, seed.GASTOS_A, "A")
    s.tareas(seed.TAREAS_A, "A")
    rutas = {ruta for _, ruta in api.llamadas}
    assert all(r.startswith("/api/") for r in rutas)
    assert not any("admin" in r or "service" in r or "rpc" in r for r in rutas)


def test_plan_solo_lee_y_no_escribe(monkeypatch, capsys):
    api = ApiSimulada()
    monkeypatch.setattr(seed, "cargar_publicable", lambda: ("https://x.supabase.co", "clave"))
    monkeypatch.setattr(seed, "iniciar_sesion", lambda *a: "token-de-prueba")
    respuestas = iter(["correo@example.test"])
    monkeypatch.setattr("builtins.input", lambda _: next(respuestas))
    monkeypatch.setattr(seed.getpass, "getpass", lambda _: "contrasena-de-prueba")
    monkeypatch.setattr(seed.httpx, "Client", _cliente_simulado(api))
    assert seed.main(["--cuenta", "A", "--plan"]) == 0
    salida = capsys.readouterr().out
    assert "Nada se ha escrito" in salida
    assert not any(m in ("POST", "PUT", "PATCH", "DELETE") for m, _ in api.llamadas)
    assert "eyJ" not in salida and "contrasena" not in salida.lower()


def test_sin_confirmacion_no_se_escribe(monkeypatch, capsys):
    api = ApiSimulada()
    monkeypatch.setattr(seed, "cargar_publicable", lambda: ("https://x.supabase.co", "clave"))
    monkeypatch.setattr(seed, "iniciar_sesion", lambda *a: "token-de-prueba")
    respuestas = iter(["correo@example.test", "no"])
    monkeypatch.setattr("builtins.input", lambda _: next(respuestas))
    monkeypatch.setattr(seed.getpass, "getpass", lambda _: "contrasena-de-prueba")
    monkeypatch.setattr(seed.httpx, "Client", _cliente_simulado(api))
    assert seed.main(["--cuenta", "A"]) == 1
    assert "No se ha escrito nada" in capsys.readouterr().out
    assert not any(m in ("POST", "PUT", "PATCH", "DELETE") for m, _ in api.llamadas)


def test_presupuesto_existente_con_otros_valores_no_se_sobrescribe():
    api = ApiSimulada()
    api.budgets[(str(seed.MES_POR_DEFECTO[0]), str(seed.MES_POR_DEFECTO[1]))] = {"ingreso": "1000000.00", "meta_ahorro": "0"}
    s = _sembrador(api)
    with pytest.raises(seed.MesOcupado):
        s.finanzas(seed.PRESUPUESTO_A, seed.GASTOS_A, "A")
    assert not any(m == "PUT" for m, _ in api.llamadas)
    assert api.budgets[(str(seed.MES_POR_DEFECTO[0]), str(seed.MES_POR_DEFECTO[1]))]["ingreso"] == "1000000.00"


def test_diagnostico_detecta_conflicto_sin_escribir():
    api = ApiSimulada()
    api.budgets[(str(seed.MES_POR_DEFECTO[0]), str(seed.MES_POR_DEFECTO[1]))] = {"ingreso": "1000000.00", "meta_ahorro": "0"}
    s = _sembrador(api)
    plan = s.diagnosticar(seed.ASIGNATURAS_A, seed.PRESUPUESTO_A, seed.GASTOS_A, seed.TAREAS_A, "A")
    assert plan["presupuesto"] == "existe" and plan["conflicto"]
    assert not any(m in ("POST", "PUT", "PATCH", "DELETE") for m, _ in api.llamadas)


def test_mes_alternativo_se_usa_en_presupuesto_y_fechas():
    api = ApiSimulada()
    s = seed.Sembrador(httpx.Client(base_url="http://simulado", transport=httpx.MockTransport(api.handler)), mes=(2026, 10))
    s.finanzas(seed.PRESUPUESTO_A, seed.GASTOS_A, "A")
    assert ("2026", "10") in api.budgets
    assert all(g["fecha"].startswith("2026-10-") for g in api.expenses)
