"""Pruebas del panel general (/api/dashboard): valores esperados calculados a mano.

Cada cifra esperada se deriva de los motores (ver comentarios); no se duplica la lógica aquí.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_verifier
from app.config import get_settings
from app.main import create_app


@pytest.fixture
def cliente_sqlite(tmp_path, monkeypatch, verifier):
    from app.api import deps

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "panel.sqlite3"))
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("SUPABASE_URL", "")
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()
    app = create_app()
    app.dependency_overrides[get_verifier] = lambda: verifier
    yield TestClient(app)
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()


def _h(make_token):
    return {"Authorization": f"Bearer {make_token()}"}


def _datos(c, h):
    hoy = date.today()
    anio, mes = hoy.year, hoy.month

    calc = c.post("/api/subjects", headers=h, json={"nombre": "Cálculo"}).json()["id"]
    for nota in ["4.5", "3.0", "2.9"]:
        c.post(f"/api/subjects/{calc}/grades", headers=h, json={"descripcion": "N", "nota": nota})
    fis = c.post("/api/subjects", headers=h, json={"nombre": "Física"}).json()["id"]
    for nota in ["2.0", "2.5"]:
        c.post(f"/api/subjects/{fis}/grades", headers=h, json={"descripcion": "N", "nota": nota})
    c.post("/api/subjects", headers=h, json={"nombre": "Historia"})

    c.put(f"/api/finanzas/presupuestos/{anio}/{mes}", headers=h, json={"ingreso": 2000000, "meta_ahorro": 300000})
    c.post(f"/api/finanzas/presupuestos/{anio}/{mes}/gastos", headers=h, json={
        "descripcion": "Arriendo", "categoria": "Vivienda", "monto": 600000, "tipo": "fijo",
        "fecha": f"{anio}-{mes:02d}-01"})
    c.post(f"/api/finanzas/presupuestos/{anio}/{mes}/gastos", headers=h, json={
        "descripcion": "Mercado", "categoria": "Alimentación", "monto": 250000, "tipo": "variable",
        "fecha": f"{anio}-{mes:02d}-02"})

    c.post("/api/tareas", headers=h, json={"titulo": "Vencida", "prioridad": "alta",
                                           "fecha_limite": (hoy - timedelta(days=2)).isoformat()})
    c.post("/api/tareas", headers=h, json={"titulo": "Próxima", "prioridad": "media",
                                           "fecha_limite": (hoy + timedelta(days=3)).isoformat()})
    c.post("/api/tareas", headers=h, json={"titulo": "Sin fecha", "prioridad": "baja"})
    c.post("/api/tareas", headers=h, json={"titulo": "Hecha", "prioridad": "alta", "estado": "completada"})
    return anio, mes


def test_panel_academico_usa_promedios_y_criterio_del_motor(cliente_sqlite, make_token):
    h = _h(make_token)
    anio, mes = _datos(cliente_sqlite, h)
    panel = cliente_sqlite.get("/api/dashboard", headers=h).json()["academico"]

    # Cálculo: (4,5+3,0+2,9)/3 = 3,47 · Física: (2,0+2,5)/2 = 2,25 · Historia sin notas.
    assert panel["total_asignaturas"] == 3
    assert panel["con_notas"] == 2
    assert panel["aprobadas"] == 1 and panel["reprobadas"] == 1
    # Promedio general = media de los promedios de asignatura: (3,47+2,25)/2 = 2,86.
    assert panel["promedio_general"] == "2.86"
    # Bajo rendimiento = promedio < 3,0 (motor), solo Física.
    assert [a["nombre"] for a in panel["bajo_rendimiento"]] == ["Física"]
    assert panel["bajo_rendimiento"][0]["promedio"] == "2.25"
    assert "3.00" in panel["criterio_bajo_rendimiento"]


def test_panel_financiero_coincide_con_el_motor(cliente_sqlite, make_token):
    h = _h(make_token)
    anio, mes = _datos(cliente_sqlite, h)
    fin = cliente_sqlite.get("/api/dashboard", headers=h).json()["finanzas"]

    assert fin["disponible"] is True and fin["tiene_presupuesto"] is True
    assert fin["gastos_total"] == "850000.00"              # 600000 + 250000
    assert fin["saldo"] == "1150000.00"                    # 2000000 - 850000
    assert fin["ahorro_logrado"] == "1150000.00"
    assert fin["porcentaje_meta_ahorro"] == "383.33"       # 1150000 / 300000 · 100
    assert fin["meta_cumplida"] is True
    assert fin["categorias"][0]["categoria"] == "Vivienda"
    assert fin["categorias"][0]["porcentaje"] == "70.59"   # 600000 / 850000 · 100


def test_panel_tareas_vencimientos_y_prioridades(cliente_sqlite, make_token):
    h = _h(make_token)
    _datos(cliente_sqlite, h)
    tareas = cliente_sqlite.get("/api/dashboard", headers=h).json()["tareas"]

    assert tareas["disponible"] is True
    assert (tareas["total"], tareas["completadas"], tareas["pendientes"]) == (4, 1, 3)
    assert tareas["porcentaje"] == "25.00"
    assert [t["titulo"] for t in tareas["vencidas"]] == ["Vencida"]
    assert [t["titulo"] for t in tareas["proximas"]] == ["Próxima"]
    assert tareas["proximas_total"] == 1
    assert tareas["pendientes_por_prioridad"] == {"alta": 1, "media": 1, "baja": 1}


def test_mes_sin_presupuesto_no_inventa_cifras(cliente_sqlite, make_token):
    h = _h(make_token)
    _datos(cliente_sqlite, h)
    fin = cliente_sqlite.get("/api/dashboard", params={"anio": 2001, "mes": 1}, headers=h).json()["finanzas"]
    assert fin == {**fin, "disponible": True, "tiene_presupuesto": False, "saldo": None, "categorias": []}


def test_panel_vacio_responde_con_ceros_y_nulos(cliente_sqlite, make_token):
    panel = cliente_sqlite.get("/api/dashboard", headers=_h(make_token)).json()
    assert panel["academico"]["promedio_general"] is None
    assert panel["academico"]["bajo_rendimiento"] == []
    assert panel["tareas"]["total"] == 0 and panel["tareas"]["porcentaje"] == "0.00"
    assert panel["finanzas"]["tiene_presupuesto"] is False


def test_panel_sin_token_responde_401(cliente_sqlite):
    assert cliente_sqlite.get("/api/dashboard").status_code == 401


def test_panel_no_muestra_datos_de_otro_usuario(cliente_sqlite, make_token):
    _datos(cliente_sqlite, _h(make_token))
    otro = cliente_sqlite.get("/api/dashboard", headers=_h(make_token)).json()
    assert otro["academico"]["total_asignaturas"] == 0
    assert otro["tareas"]["total"] == 0
    assert otro["finanzas"]["tiene_presupuesto"] is False


def test_panel_con_supabase_marca_finanzas_y_tareas_no_disponibles(client, make_token):
    """Con PostgREST activo, solo el módulo académico tiene adaptador: el resto se declara no disponible."""
    panel = client.get("/api/dashboard", headers=_h(make_token)).json()
    assert panel["persistencia"] == "supabase"
    assert panel["finanzas"]["disponible"] is False
    assert panel["tareas"]["disponible"] is False
    assert panel["academico"]["total_asignaturas"] == 0


@pytest.mark.parametrize("consulta", ["anio=1999", "mes=13", "mes=0"])
def test_parametros_fuera_de_rango_responden_422(cliente_sqlite, make_token, consulta):
    assert cliente_sqlite.get(f"/api/dashboard?{consulta}", headers=_h(make_token)).status_code == 422
