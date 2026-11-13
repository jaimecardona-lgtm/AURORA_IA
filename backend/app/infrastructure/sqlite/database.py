"""Conexión y migraciones de la base SQLite local (desarrollo y demostración).

- Las migraciones son archivos SQL numerados en `migrations/`, aplicados en orden y
  registrados en `schema_migrations`. Se aplican una sola vez por base de datos.
- Cada conexión activa las claves foráneas (SQLite las desactiva por defecto).
- Autocommit: cada sentencia es una transacción. Las restricciones (CHECK, UNIQUE, FK)
  las hace cumplir la base de datos, igual que en PostgreSQL.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version     TEXT PRIMARY KEY,
  applied_at  TEXT NOT NULL
)
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI crea la dependencia y ejecuta el endpoint en hilos
    # distintos. Cada petición tiene SU conexión y nunca se comparte, así que no hay acceso
    # concurrente a la misma conexión.
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def available_migrations() -> list[tuple[str, Path]]:
    """Lista (versión, ruta) ordenada por nombre de archivo."""
    return [(archivo.stem, archivo) for archivo in sorted(MIGRATIONS_DIR.glob("*.sql"))]


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Aplica las migraciones pendientes. Devuelve las versiones aplicadas en esta llamada."""
    conn.execute(_CREATE_MIGRATIONS_TABLE)
    aplicadas = {fila["version"] for fila in conn.execute("SELECT version FROM schema_migrations")}
    nuevas: list[str] = []
    for version, ruta in available_migrations():
        if version in aplicadas:
            continue
        sql = ruta.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            (version,),
        )
        nuevas.append(version)
    return nuevas


def open_migrated(path: Path) -> sqlite3.Connection:
    """Abre la base (creándola si no existe) y la deja al día con las migraciones."""
    conn = connect(path)
    migrate(conn)
    return conn
