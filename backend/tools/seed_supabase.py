"""Sembrador reproducible de datos de demostración para AURORA AI (Supabase real).

Qué hace:
  - Carga datos FICTICIOS con prefijo DEMO-AURORA- para dos cuentas de prueba (A principal, B de aislamiento).
  - Usa SOLO los endpoints normales de FastAPI con el JWT del usuario (flujo de Supabase Auth).
  - Es idempotente: antes de crear, busca el registro por nombre o descripción; si existe, no lo duplica.
  - NUNCA sobrescribe un presupuesto existente. Si el mes está ocupado por datos distintos, se detiene
    antes de escribir nada y propone otro mes (--mes AAAA-MM).
  - No usa service_role, no borra nada, no modifica registros existentes de otro prefijo.
  - --plan se conecta solo para LEER: muestra qué existe y qué se crearía. No escribe nada.
  - La inserción pide confirmación explícita (escribir SI) antes de la primera escritura.

Seguridad:
  - La contraseña se pide con getpass (no se muestra ni se guarda). El JWT vive solo en memoria.
  - Nunca imprime tokens ni contraseñas. Imprime solo cantidades y estado.
  - La URL y la clave publicable se leen de backend/.env; deben pertenecer al proyecto AURORA_IA.

Uso (desde backend/, con el venv):
  python tools/seed_supabase.py --cuenta A --plan
  python tools/seed_supabase.py --cuenta A                 (pide confirmación antes de insertar)
  python tools/seed_supabase.py --cuenta B --mes 2026-10
"""

from __future__ import annotations

import argparse
import getpass
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

PREFIJO = "DEMO-AURORA-"
MES_POR_DEFECTO = (2026, 11)  # noviembre de 2026

# ----------------------------------------------------------------- datos de demostración (cuenta A)
ASIGNATURAS_A = {
    "Cálculo diferencial": [("Parcial 1", "4.5"), ("Parcial 2", "4.0"), ("Taller 3", "3.8")],
    "Programación I": [("Quiz 1", "3.4"), ("Proyecto", "3.0"), ("Examen", "3.1")],
    "Álgebra lineal": [("Parcial 1", "2.5"), ("Parcial 2", "3.0")],
    "Física II": [("Laboratorio 1", "2.0"), ("Parcial 1", "2.8"), ("Parcial 2", "2.6")],
    "Inglés B1": [("Speaking", "4.2"), ("Writing", "4.6")],
    "Estadística": [("Parcial 1", "3.9"), ("Taller 2", "2.9"), ("Parcial 2", "3.6"), ("Quiz", "3.3")],
}

PRESUPUESTO_A = {"ingreso": "2800000.00", "meta_ahorro": "500000.00"}

# (descripción, monto, tipo, categoría, día del mes)
GASTOS_A = [
    ("Arriendo", "900000.00", "fijo", "Vivienda", 1),
    ("Internet", "90000.00", "fijo", "Servicios", 2),
    ("Energía", "120000.00", "fijo", "Servicios", 3),
    ("Mercado semanal", "420000.00", "variable", "Alimentación", 5),
    ("Transporte público", "180000.00", "variable", "Transporte", 7),
    ("Matrícula de curso", "300000.00", "variable", "Educación", 10),
    ("Libros y material", "110000.00", "variable", "Educación", 12),
    ("Salida con amigos", "150000.00", "variable", "Entretenimiento", 20),
]

# (título, prioridad, estado, desplazamiento en días respecto a hoy o None)
TAREAS_A = [
    ("Entregar taller de cálculo", "alta", "pendiente", -3),
    ("Corregir informe de física", "alta", "pendiente", -1),
    ("Repasar examen de estadística", "media", "pendiente", -2),
    ("Preparar exposición de programación", "alta", "pendiente", 2),
    ("Estudiar para parcial de álgebra", "media", "pendiente", 4),
    ("Práctica de speaking en inglés", "baja", "pendiente", 6),
    ("Leer capítulo 5 de física", "media", "pendiente", 14),
    ("Inscribir proyecto de grado", "baja", "pendiente", 30),
    ("Entregar laboratorio de química", "media", "completada", -5),
    ("Resumen de la clase de inglés", "baja", "completada", None),
]

# ----------------------------------------------------------------- datos de aislamiento (cuenta B)
ASIGNATURAS_B = {"Historia de Colombia": [("Parcial 1", "3.6"), ("Ensayo", "4.1")]}
PRESUPUESTO_B = {"ingreso": "1200000.00", "meta_ahorro": "150000.00"}
GASTOS_B = [("Mercado", "300000.00", "variable", "Alimentación", 4)]
TAREAS_B = [("Leer lectura de historia", "media", "pendiente", 3)]

CUENTAS = {
    "A": (ASIGNATURAS_A, PRESUPUESTO_A, GASTOS_A, TAREAS_A),
    "B": (ASIGNATURAS_B, PRESUPUESTO_B, GASTOS_B, TAREAS_B),
}


class MesOcupado(Exception):
    """El mes ya tiene datos que no coinciden con el dataset. No se escribe nada."""


@dataclass
class Resumen:
    creados: dict[str, int] = field(default_factory=dict)
    existentes: dict[str, int] = field(default_factory=dict)

    def sumar(self, clave: str, creado: bool) -> None:
        bolsa = self.creados if creado else self.existentes
        bolsa[clave] = bolsa.get(clave, 0) + 1


class Sembrador:
    """Crea los datos con endpoints normales de FastAPI. `cliente` debe llevar el JWT del usuario."""

    def __init__(self, cliente: httpx.Client, hoy: date | None = None, mes: tuple[int, int] = MES_POR_DEFECTO) -> None:
        self.c = cliente
        self.hoy = hoy or date.today()
        self.anio, self.mes = mes
        self.resumen = Resumen()

    # ---- utilidades
    def _get(self, ruta: str):
        r = self.c.get(ruta)
        r.raise_for_status()
        return r.json()

    def _fecha_mes(self, dia: int) -> str:
        return date(self.anio, self.mes, dia).isoformat()

    def _presupuesto_previo(self):
        """GET del mes: 200 (existe, con datos) o 404 (no existe). Solo lectura."""
        return self.c.get(f"/api/finanzas/presupuestos/{self.anio}/{self.mes}")

    # ---- diagnóstico (solo lectura)
    def diagnosticar(self, asignaturas, presupuesto, gastos, tareas, prefijo: str) -> dict:
        subjects = {s["nombre"] for s in self._get("/api/subjects")}
        nombres = [f"{PREFIJO}{prefijo}-{n}" for n in asignaturas]
        previo = self._presupuesto_previo()
        titulos = {t["titulo"] for t in self._get("/api/tareas")}
        plan = {
            "mes": f"{self.anio:04d}-{self.mes:02d}",
            "asignaturas_existentes": sum(1 for n in nombres if n in subjects),
            "asignaturas_por_crear": sum(1 for n in nombres if n not in subjects),
            "notas_por_crear": sum(len(v) for v in asignaturas.values()),
            "tareas_existentes": sum(1 for t in tareas if f"{PREFIJO}{prefijo}-{t[0]}" in titulos),
            "tareas_por_crear": sum(1 for t in tareas if f"{PREFIJO}{prefijo}-{t[0]}" not in titulos),
            "presupuesto": "no existe" if previo.status_code == 404 else "existe",
            "gastos_por_crear": len(gastos),
            "gastos_existentes": 0,
            "gastos_no_demo_en_el_mes": 0,
            "conflicto": None,
        }
        if previo.status_code == 200:
            datos = previo.json()
            igual = (Decimal(str(datos["ingreso"])) == Decimal(presupuesto["ingreso"])
                     and Decimal(str(datos["meta_ahorro"])) == Decimal(presupuesto["meta_ahorro"]))
            descripciones = [g["descripcion"] for g in datos["gastos"]]
            etiquetas = {f"{PREFIJO}{prefijo}-{g[0]}" for g in gastos}
            plan["gastos_existentes"] = sum(1 for d in descripciones if d in etiquetas)
            plan["gastos_no_demo_en_el_mes"] = sum(1 for d in descripciones if not d.startswith(PREFIJO))
            plan["gastos_por_crear"] = len(gastos) - plan["gastos_existentes"]
            if not igual:
                plan["conflicto"] = "el presupuesto del mes tiene ingreso o meta distintos"
            elif plan["gastos_no_demo_en_el_mes"]:
                plan["conflicto"] = "el mes contiene gastos que no son DEMO-AURORA-"
        return plan

    # ---- académico
    def academico(self, asignaturas, prefijo: str) -> None:
        existentes = {s["nombre"]: s for s in self._get("/api/subjects")}
        for nombre, notas in asignaturas.items():
            nombre_completo = f"{PREFIJO}{prefijo}-{nombre}"
            if nombre_completo in existentes:
                subj = existentes[nombre_completo]
                self.resumen.sumar("asignaturas", False)
            else:
                r = self.c.post("/api/subjects", json={"nombre": nombre_completo})
                r.raise_for_status()
                subj = r.json()
                self.resumen.sumar("asignaturas", True)
            detalle = self._get(f"/api/subjects/{subj['id']}")
            descripciones = {n["descripcion"] for n in detalle["notas"]}
            for descripcion, nota in notas:
                if descripcion in descripciones:
                    self.resumen.sumar("notas", False)
                    continue
                r = self.c.post(f"/api/subjects/{subj['id']}/grades", json={"descripcion": descripcion, "nota": nota})
                r.raise_for_status()
                self.resumen.sumar("notas", True)

    # ---- finanzas
    def finanzas(self, presupuesto, gastos, prefijo: str) -> None:
        previo = self._presupuesto_previo()
        if previo.status_code == 200:
            datos = previo.json()
            igual = (Decimal(str(datos["ingreso"])) == Decimal(presupuesto["ingreso"])
                     and Decimal(str(datos["meta_ahorro"])) == Decimal(presupuesto["meta_ahorro"]))
            if not igual:
                raise MesOcupado("el presupuesto del mes ya existe con otros valores: no se modifica")
            self.resumen.sumar("presupuestos", False)  # ya existía con los mismos valores: no se reescribe
        else:
            r = self.c.put(f"/api/finanzas/presupuestos/{self.anio}/{self.mes}",
                           json={"ingreso": presupuesto["ingreso"], "meta_ahorro": presupuesto["meta_ahorro"]})
            r.raise_for_status()
            self.resumen.sumar("presupuestos", True)

        detalle = self._get(f"/api/finanzas/presupuestos/{self.anio}/{self.mes}")
        if any(not g["descripcion"].startswith(PREFIJO) for g in detalle["gastos"]):
            raise MesOcupado("el mes contiene gastos que no son DEMO-AURORA-: no se añaden gastos de demostración")
        descripciones = {g["descripcion"] for g in detalle["gastos"]}
        for descripcion, monto, tipo, categoria, dia in gastos:
            etiqueta = f"{PREFIJO}{prefijo}-{descripcion}"
            if etiqueta in descripciones:
                self.resumen.sumar("gastos", False)
                continue
            r = self.c.post(f"/api/finanzas/presupuestos/{self.anio}/{self.mes}/gastos", json={
                "descripcion": etiqueta, "categoria": categoria, "monto": monto,
                "tipo": tipo, "fecha": self._fecha_mes(dia)})
            r.raise_for_status()
            self.resumen.sumar("gastos", True)

    # ---- tareas
    def tareas(self, tareas, prefijo: str) -> None:
        existentes = {t["titulo"] for t in self._get("/api/tareas")}
        for titulo, prioridad, estado, desplazamiento in tareas:
            etiqueta = f"{PREFIJO}{prefijo}-{titulo}"
            if etiqueta in existentes:
                self.resumen.sumar("tareas", False)
                continue
            cuerpo = {"titulo": etiqueta, "prioridad": prioridad, "estado": estado}
            if desplazamiento is not None:
                cuerpo["fecha_limite"] = (self.hoy + timedelta(days=desplazamiento)).isoformat()
            r = self.c.post("/api/tareas", json=cuerpo)
            r.raise_for_status()
            self.resumen.sumar("tareas", True)

    # ---- verificación (solo lectura, mediante la API autenticada)
    def verificar(self, prefijo: str) -> dict[str, object]:
        asig = [s for s in self._get("/api/subjects") if s["nombre"].startswith(f"{PREFIJO}{prefijo}-")]
        presupuesto = self._get(f"/api/finanzas/presupuestos/{self.anio}/{self.mes}")
        tareas = [t for t in self._get("/api/tareas") if t["titulo"].startswith(f"{PREFIJO}{prefijo}-")]
        return {"asignaturas": len(asig), "gastos_del_mes": len(presupuesto["gastos"]), "tareas": len(tareas),
                "saldo": presupuesto["saldo"], "meta_cumplida": presupuesto["meta_cumplida"]}


def cargar_publicable() -> tuple[str, str]:
    """Lee URL y clave publicable de backend/.env mediante la configuración de la aplicación."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.config import get_settings

    ajustes = get_settings()
    return ajustes.supabase_url, ajustes.supabase_publishable_key


def iniciar_sesion(url: str, clave: str, correo: str, contrasena: str) -> str:
    """Login normal de Supabase Auth. Devuelve el access_token SOLO en memoria."""
    r = httpx.post(f"{url}/auth/v1/token?grant_type=password",
                   headers={"apikey": clave, "Content-Type": "application/json"},
                   json={"email": correo, "password": contrasena}, timeout=20)
    if r.status_code != 200:
        raise SystemExit(f"Inicio de sesión rechazado (HTTP {r.status_code}). No se realizó ninguna escritura.")
    return r.json()["access_token"]


def analizar_mes(valor: str) -> tuple[int, int]:
    try:
        anio, mes = (int(p) for p in valor.split("-"))
        date(anio, mes, 1)
        return anio, mes
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("El mes debe tener formato AAAA-MM, p. ej. 2026-10.") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sembrador de datos DEMO-AURORA- en Supabase (endpoints FastAPI).")
    parser.add_argument("--cuenta", choices=["A", "B"], required=True, help="Cuenta de prueba a sembrar.")
    parser.add_argument("--plan", action="store_true", help="Solo lectura: muestra lo que existe y lo que se crearía.")
    parser.add_argument("--mes", type=analizar_mes, default=MES_POR_DEFECTO, help="Mes del presupuesto, AAAA-MM.")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="Base de la API FastAPI local.")
    args = parser.parse_args(argv)

    asig, pres, gastos, tareas = CUENTAS[args.cuenta]
    url, clave = cargar_publicable()
    print(f"Cuenta {args.cuenta}: introduce su correo y contraseña. Nada se muestra ni se guarda.")
    correo = input("Correo de la cuenta de prueba: ").strip()
    contrasena = getpass.getpass("Contraseña (no se muestra): ")
    token = iniciar_sesion(url, clave, correo, contrasena)
    del contrasena

    cliente = httpx.Client(base_url=args.api, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    try:
        s = Sembrador(cliente, mes=args.mes)
        plan = s.diagnosticar(asig, pres, gastos, tareas, args.cuenta)
        print("Plan (solo lectura):")
        for clave_plan, valor in plan.items():
            print(f"  {clave_plan}: {valor}")
        if plan["conflicto"]:
            print(f"\nNo se escribe nada: {plan['conflicto']}. Elige otro mes con --mes AAAA-MM "
                  "(p. ej. 2026-10 o 2026-09) y vuelve a planificar.")
            return 2
        if args.plan:
            print("\nNada se ha escrito. Quita --plan para insertar tras confirmar.")
            return 0

        confirmacion = input(f"\n¿Insertar los datos DEMO-AURORA- de la cuenta {args.cuenta} en el mes "
                             f"{plan['mes']} de Supabase? Escribe SI: ")
        if confirmacion.strip() != "SI":
            print("Cancelado. No se ha escrito nada.")
            return 1

        s.academico(asig, args.cuenta)
        s.finanzas(pres, gastos, args.cuenta)
        s.tareas(tareas, args.cuenta)
        print("Creados:", s.resumen.creados or "ninguno")
        print("Ya existentes (no duplicados):", s.resumen.existentes or "ninguno")
        print("Verificación por API:", s.verificar(args.cuenta))
        return 0
    except MesOcupado as exc:
        print(f"Detenido: {exc}. Revisa el mes con --plan y elige otro con --mes.")
        return 2
    finally:
        cliente.close()
        del token


if __name__ == "__main__":
    raise SystemExit(main())
