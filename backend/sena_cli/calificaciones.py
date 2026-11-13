"""CLI del motor de calificaciones (evidencia SENA).

Uso desde la carpeta backend/:
    python sena_cli/calificaciones.py 4.5 3.0 2.9
    python sena_cli/calificaciones.py --json 4 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Permite ejecutar el script directamente (python sena_cli/calificaciones.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.grades import GradeError, average, is_passing, parse_grade  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promedio y aprobación (escala 0–5, aprueba >= 3.0)")
    parser.add_argument("notas", nargs="+", help="Notas entre 0 y 5")
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    args = parser.parse_args(argv)

    try:
        grades = [parse_grade(n) for n in args.notas]
        avg = average(grades)
    except GradeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    result = {
        "notas": [str(g) for g in grades],
        "promedio": str(avg),
        "aprobado": is_passing(avg),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Notas: {', '.join(result['notas'])}")
        print(f"Promedio: {result['promedio']}")
        print(f"Estado: {'APROBADO' if result['aprobado'] else 'NO APROBADO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
