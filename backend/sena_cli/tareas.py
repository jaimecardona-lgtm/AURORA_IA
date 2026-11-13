"""CLI del motor de priorización de tareas (evidencia SENA).

Uso desde la carpeta backend/:
    python sena_cli/tareas.py "Entregar AA2:1" "Leer guía:3:completada" "Revisar correo:2"
Formato de cada tarea: 'titulo:prioridad[:estado]'  (prioridad 1–3, estado pendiente|completada)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.tasks import Task, TaskError, prioritize  # noqa: E402


def _parse_tarea(texto: str) -> Task:
    partes = texto.split(":")
    if len(partes) == 2:
        titulo, prioridad = partes
        estado = "pendiente"
    elif len(partes) == 3:
        titulo, prioridad, estado = partes
    else:
        raise TaskError("Formato de tarea: 'titulo:prioridad[:estado]'")
    return Task.build(titulo, prioridad, estado.strip().lower())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ordena tareas por estado y prioridad (1 alta, 3 baja)")
    parser.add_argument("tareas", nargs="+", help="Tareas 'titulo:prioridad[:estado]'")
    args = parser.parse_args(argv)

    try:
        tareas = [_parse_tarea(t) for t in args.tareas]
    except TaskError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    for indice, tarea in enumerate(prioritize(tareas), start=1):
        print(f"{indice}. [P{tarea.priority}] {tarea.title} ({tarea.status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
