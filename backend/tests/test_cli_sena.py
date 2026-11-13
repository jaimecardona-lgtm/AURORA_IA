"""Los programas CLI de la evidencia SENA deben seguir funcionando de forma independiente."""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _ejecutar(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BACKEND / "sena_cli" / script), *args],
        capture_output=True,
        text=True,
        cwd=BACKEND,
        timeout=60,
    )


def test_cli_calificaciones_aprobado():
    r = _ejecutar("calificaciones.py", "4.5", "3.0", "2.9")
    assert r.returncode == 0
    assert "Promedio: 3.47" in r.stdout
    assert "APROBADO" in r.stdout


def test_cli_calificaciones_error_de_rango():
    r = _ejecutar("calificaciones.py", "6")
    assert r.returncode == 2
    assert "entre 0 y 5" in r.stderr


def test_cli_presupuesto_resumen():
    r = _ejecutar(
        "presupuesto.py", "--ingreso", "2000000", "--ahorro", "300000",
        "--gasto", "Arriendo:600000:fijo", "--gasto", "Mercado:250000:variable",
    )
    assert r.returncode == 0
    assert "Saldo final: $ 1,150,000.00 COP" in r.stdout


def test_cli_tareas_ordena_por_prioridad():
    r = _ejecutar("tareas.py", "Leer:3:completada", "Entregar:1", "Correo:2")
    assert r.returncode == 0
    lineas = [l for l in r.stdout.splitlines() if l.strip()]
    assert "Entregar" in lineas[0]
    assert "Leer" in lineas[-1]
