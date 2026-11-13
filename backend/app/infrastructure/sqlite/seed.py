"""Datos FICTICIOS de demostración para la base SQLite local.

Uso (desde backend/):
    python -m app.infrastructure.sqlite.seed            # añade los datos si no existen
    python -m app.infrastructure.sqlite.seed --reset    # borra SOLO los datos demo y los vuelve a cargar

Todos los registros llevan origen='demo'. Los registros reales (origen='real') nunca se
modifican ni se borran con esta herramienta.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date, timedelta

from app.config import get_settings
from app.errors import ConflictError
from app.infrastructure.sqlite.database import open_migrated
from app.infrastructure.sqlite.repositories import (
    SqliteAcademicRepository,
    SqliteBudgetRepository,
    SqliteTaskRepository,
)
from app.security.principal import DEMO_PRINCIPAL

_TABLAS = ("grade_entries", "academic_subjects", "budget_expenses", "monthly_budgets", "tasks")

ASIGNATURAS = {
    "Cálculo diferencial": [("Parcial 1", 4.2), ("Parcial 2", 3.8), ("Taller 3", 4.5)],
    "Programación I": [("Quiz 1", 3.0), ("Proyecto final", 2.5)],
    "Inglés B1": [("Speaking", 4.0)],
}

GASTOS = [
    # descripción, monto COP, tipo, categoría, día del mes (se acota a hoy)
    ("Arriendo", 800_000, "fijo", "Vivienda", 1),
    ("Internet", 90_000, "fijo", "Servicios", 1),
    ("Energía", 120_000, "fijo", "Servicios", 2),
    ("Mercado semanal", 350_000, "variable", "Alimentación", 3),
    ("Transporte", 120_000, "variable", "Transporte", 4),
    ("Salida con amigos", 150_000, "variable", "Ocio", 5),
]


def _borrar_demo(conn: sqlite3.Connection) -> None:
    for tabla in _TABLAS:
        conn.execute(f"DELETE FROM {tabla} WHERE user_id = ? AND origen = 'demo'", (DEMO_PRINCIPAL.user_id,))


def _hay_demo(conn: sqlite3.Connection) -> bool:
    fila = conn.execute(
        "SELECT COUNT(*) FROM academic_subjects WHERE user_id = ? AND origen = 'demo'",
        (DEMO_PRINCIPAL.user_id,),
    ).fetchone()
    return fila[0] > 0


def seed_demo(conn: sqlite3.Connection, reset: bool = False) -> str:
    """Carga los datos demo. Devuelve un mensaje con lo que hizo."""
    if reset:
        _borrar_demo(conn)
    elif _hay_demo(conn):
        return "Los datos demo ya existen. Usa --reset para regenerarlos."

    hoy = date.today()
    academico = SqliteAcademicRepository(conn)
    finanzas = SqliteBudgetRepository(conn)
    tareas = SqliteTaskRepository(conn)

    for nombre, notas in ASIGNATURAS.items():
        asignatura = academico.create_subject(DEMO_PRINCIPAL, nombre, origen="demo")
        for descripcion, nota in notas:
            academico.create_grade(DEMO_PRINCIPAL, asignatura["id"], descripcion, nota, origen="demo")

    presupuesto = finanzas.upsert_budget(DEMO_PRINCIPAL, hoy.year, hoy.month, 2_500_000.0, 400_000.0, origen="demo")
    for descripcion, monto, tipo, categoria, dia in GASTOS:
        fecha = date(hoy.year, hoy.month, min(dia, hoy.day))
        finanzas.create_expense(
            DEMO_PRINCIPAL,
            presupuesto["id"],
            {
                "descripcion": descripcion,
                "categoria": categoria,
                "monto": float(monto),
                "tipo": tipo,
                "fecha": fecha.isoformat(),
            },
            origen="demo",
        )

    tareas_demo = [
        ("Entregar taller de cálculo", 1, "pendiente", hoy - timedelta(days=2)),  # vencida
        ("Preparar presentación de programación", 1, "pendiente", hoy + timedelta(days=3)),  # próxima
        ("Estudiar para parcial de inglés", 2, "pendiente", hoy + timedelta(days=5)),
        ("Revisar correo institucional", 3, "pendiente", None),
        ("Leer capítulo 4 de cálculo", 3, "completada", None),
    ]
    for titulo, prioridad, estado, limite in tareas_demo:
        tareas.create_task(
            DEMO_PRINCIPAL,
            {
                "titulo": titulo,
                "prioridad": prioridad,
                "estado": estado,
                "fecha_limite": limite.isoformat() if limite else None,
            },
            origen="demo",
        )
    accion = "regenerados" if reset else "cargados"
    return f"Datos demo {accion}: {len(ASIGNATURAS)} asignaturas, {len(GASTOS)} gastos, {len(tareas_demo)} tareas."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carga datos FICTICIOS de demostración en SQLite.")
    parser.add_argument("--reset", action="store_true", help="Borra solo los datos demo y los vuelve a cargar.")
    args = parser.parse_args(argv)

    ajustes = get_settings()
    if ajustes.app_env.strip().lower() not in ("development", "local", "test"):
        print("Error: los datos demo solo se cargan en desarrollo.")
        return 2
    conn = open_migrated(ajustes.sqlite_path)
    try:
        print(f"Base: {ajustes.sqlite_path}")
        print(seed_demo(conn, reset=args.reset))
    except ConflictError:
        print("No se cargaron los datos demo: ya existe una asignatura real con el mismo nombre. "
              "Renómbrala o usa otra base (SQLITE_PATH).")
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
