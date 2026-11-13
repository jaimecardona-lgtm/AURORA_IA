"""Repositorios SQLite (infraestructura). Solo SQL; ninguna regla de negocio.

Aislamiento: CADA consulta filtra por `principal.user_id`. Es el equivalente local de la
política RLS `auth.uid() = user_id` de PostgreSQL. Los nombres de columna que se
actualizan salen de listas blancas fijas, nunca de la entrada del cliente.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import UUID

from app.errors import ConflictError, ValidationFailedError
from app.security.principal import Principal

ORIGENES = ("real", "demo")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nuevo_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def _restricciones() -> Iterator[None]:
    """Traduce violaciones de la base a errores de dominio (409 único, 422 resto)."""
    try:
        yield
    except sqlite3.IntegrityError as exc:
        if "UNIQUE" in str(exc).upper():
            raise ConflictError("Ya existe un registro con esos datos.") from None
        raise ValidationFailedError("Los datos no cumplen las restricciones de la base de datos.") from None


def _fila(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _set_clause(changes: dict[str, Any], permitidas: frozenset[str]) -> tuple[str, list[Any]]:
    columnas = [c for c in changes if c in permitidas]
    if not columnas:
        raise ValidationFailedError("No hay campos actualizables.")
    partes = ", ".join(f"{c} = ?" for c in columnas)
    return partes, [changes[c] for c in columnas]


def _origen(origen: str) -> str:
    if origen not in ORIGENES:
        raise ValueError("origen inválido")
    return origen


# --------------------------------------------------------------------------- académico
class SqliteAcademicRepository:
    _ACTUALIZABLES_ASIGNATURA = frozenset({"nombre"})
    _ACTUALIZABLES_NOTA = frozenset({"descripcion", "nota"})

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # asignaturas
    def list_subjects(self, principal: Principal) -> list[dict[str, Any]]:
        filas = self._conn.execute(
            "SELECT * FROM academic_subjects WHERE user_id = ? ORDER BY lower(nombre) ASC",
            (principal.user_id,),
        ).fetchall()
        return [dict(f) for f in filas]

    def get_subject(self, principal: Principal, subject_id: UUID) -> dict[str, Any] | None:
        return _fila(
            self._conn.execute(
                "SELECT * FROM academic_subjects WHERE user_id = ? AND id = ?",
                (principal.user_id, str(subject_id)),
            ).fetchone()
        )

    def create_subject(self, principal: Principal, nombre: str, origen: str = "real") -> dict[str, Any]:
        ahora = _ahora()
        nueva = _nuevo_id()
        with _restricciones():
            self._conn.execute(
                "INSERT INTO academic_subjects (id, user_id, nombre, origen, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (nueva, principal.user_id, nombre, _origen(origen), ahora, ahora),
            )
        return self.get_subject(principal, UUID(nueva))  # type: ignore[return-value]

    def update_subject(self, principal: Principal, subject_id: UUID, changes: dict[str, Any]) -> dict[str, Any] | None:
        if self.get_subject(principal, subject_id) is None:
            return None
        partes, valores = _set_clause(changes, self._ACTUALIZABLES_ASIGNATURA)
        with _restricciones():
            self._conn.execute(
                f"UPDATE academic_subjects SET {partes}, updated_at = ? WHERE user_id = ? AND id = ?",
                (*valores, _ahora(), principal.user_id, str(subject_id)),
            )
        return self.get_subject(principal, subject_id)

    def delete_subject(self, principal: Principal, subject_id: UUID) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM academic_subjects WHERE user_id = ? AND id = ?",
            (principal.user_id, str(subject_id)),
        )
        return cursor.rowcount > 0

    # notas
    def list_grades(self, principal: Principal, subject_id: UUID | None = None) -> list[dict[str, Any]]:
        if subject_id is None:
            filas = self._conn.execute(
                "SELECT * FROM grade_entries WHERE user_id = ? ORDER BY created_at ASC",
                (principal.user_id,),
            ).fetchall()
        else:
            filas = self._conn.execute(
                "SELECT * FROM grade_entries WHERE user_id = ? AND subject_id = ? ORDER BY created_at ASC",
                (principal.user_id, str(subject_id)),
            ).fetchall()
        return [dict(f) for f in filas]

    def get_grade(self, principal: Principal, grade_id: UUID) -> dict[str, Any] | None:
        return _fila(
            self._conn.execute(
                "SELECT * FROM grade_entries WHERE user_id = ? AND id = ?",
                (principal.user_id, str(grade_id)),
            ).fetchone()
        )

    def create_grade(
        self,
        principal: Principal,
        subject_id: UUID,
        descripcion: str,
        nota: float,
        origen: str = "real",
    ) -> dict[str, Any]:
        ahora = _ahora()
        nueva = _nuevo_id()
        with _restricciones():
            self._conn.execute(
                "INSERT INTO grade_entries (id, user_id, subject_id, descripcion, nota, origen, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (nueva, principal.user_id, str(subject_id), descripcion, nota, _origen(origen), ahora, ahora),
            )
        return self.get_grade(principal, UUID(nueva))  # type: ignore[return-value]

    def update_grade(self, principal: Principal, grade_id: UUID, changes: dict[str, Any]) -> dict[str, Any] | None:
        if self.get_grade(principal, grade_id) is None:
            return None
        partes, valores = _set_clause(changes, self._ACTUALIZABLES_NOTA)
        with _restricciones():
            self._conn.execute(
                f"UPDATE grade_entries SET {partes}, updated_at = ? WHERE user_id = ? AND id = ?",
                (*valores, _ahora(), principal.user_id, str(grade_id)),
            )
        return self.get_grade(principal, grade_id)

    def delete_grade(self, principal: Principal, grade_id: UUID) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM grade_entries WHERE user_id = ? AND id = ?",
            (principal.user_id, str(grade_id)),
        )
        return cursor.rowcount > 0


# --------------------------------------------------------------------------- finanzas
class SqliteBudgetRepository:
    _ACTUALIZABLES_GASTO = frozenset({"descripcion", "categoria", "monto", "tipo", "fecha"})

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_budgets(self, principal: Principal) -> list[dict[str, Any]]:
        filas = self._conn.execute(
            "SELECT * FROM monthly_budgets WHERE user_id = ? ORDER BY anio DESC, mes DESC",
            (principal.user_id,),
        ).fetchall()
        return [dict(f) for f in filas]

    def get_budget(self, principal: Principal, anio: int, mes: int) -> dict[str, Any] | None:
        return _fila(
            self._conn.execute(
                "SELECT * FROM monthly_budgets WHERE user_id = ? AND anio = ? AND mes = ?",
                (principal.user_id, anio, mes),
            ).fetchone()
        )

    def get_budget_by_id(self, principal: Principal, budget_id: UUID) -> dict[str, Any] | None:
        return _fila(
            self._conn.execute(
                "SELECT * FROM monthly_budgets WHERE user_id = ? AND id = ?",
                (principal.user_id, str(budget_id)),
            ).fetchone()
        )

    def upsert_budget(
        self,
        principal: Principal,
        anio: int,
        mes: int,
        ingreso: float,
        meta_ahorro: float,
        origen: str = "real",
    ) -> dict[str, Any]:
        ahora = _ahora()
        with _restricciones():
            self._conn.execute(
                "INSERT INTO monthly_budgets (id, user_id, anio, mes, ingreso, meta_ahorro, origen, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (user_id, anio, mes) DO UPDATE SET "
                "ingreso = excluded.ingreso, meta_ahorro = excluded.meta_ahorro, updated_at = excluded.updated_at",
                (_nuevo_id(), principal.user_id, anio, mes, float(ingreso), float(meta_ahorro), _origen(origen), ahora, ahora),
            )
        return self.get_budget(principal, anio, mes)  # type: ignore[return-value]

    def list_expenses(self, principal: Principal, budget_id: UUID) -> list[dict[str, Any]]:
        filas = self._conn.execute(
            "SELECT * FROM budget_expenses WHERE user_id = ? AND budget_id = ? ORDER BY fecha ASC, created_at ASC",
            (principal.user_id, str(budget_id)),
        ).fetchall()
        return [dict(f) for f in filas]

    def get_expense(self, principal: Principal, expense_id: UUID) -> dict[str, Any] | None:
        return _fila(
            self._conn.execute(
                "SELECT * FROM budget_expenses WHERE user_id = ? AND id = ?",
                (principal.user_id, str(expense_id)),
            ).fetchone()
        )

    def create_expense(
        self,
        principal: Principal,
        budget_id: UUID,
        datos: dict[str, Any],
        origen: str = "real",
    ) -> dict[str, Any]:
        ahora = _ahora()
        nueva = _nuevo_id()
        with _restricciones():
            self._conn.execute(
                "INSERT INTO budget_expenses (id, user_id, budget_id, descripcion, categoria, monto, tipo, fecha, "
                "origen, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    nueva,
                    principal.user_id,
                    str(budget_id),
                    datos["descripcion"],
                    datos["categoria"],
                    float(datos["monto"]),
                    datos["tipo"],
                    datos["fecha"],
                    _origen(origen),
                    ahora,
                    ahora,
                ),
            )
        return self.get_expense(principal, UUID(nueva))  # type: ignore[return-value]

    def update_expense(self, principal: Principal, expense_id: UUID, changes: dict[str, Any]) -> dict[str, Any] | None:
        if self.get_expense(principal, expense_id) is None:
            return None
        if "monto" in changes:
            changes = {**changes, "monto": float(changes["monto"])}
        partes, valores = _set_clause(changes, self._ACTUALIZABLES_GASTO)
        with _restricciones():
            self._conn.execute(
                f"UPDATE budget_expenses SET {partes}, updated_at = ? WHERE user_id = ? AND id = ?",
                (*valores, _ahora(), principal.user_id, str(expense_id)),
            )
        return self.get_expense(principal, expense_id)

    def delete_expense(self, principal: Principal, expense_id: UUID) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM budget_expenses WHERE user_id = ? AND id = ?",
            (principal.user_id, str(expense_id)),
        )
        return cursor.rowcount > 0


# --------------------------------------------------------------------------- tareas
class SqliteTaskRepository:
    _ACTUALIZABLES = frozenset({"titulo", "prioridad", "estado", "fecha_limite"})

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_tasks(self, principal: Principal) -> list[dict[str, Any]]:
        filas = self._conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at ASC",
            (principal.user_id,),
        ).fetchall()
        return [dict(f) for f in filas]

    def get_task(self, principal: Principal, task_id: UUID) -> dict[str, Any] | None:
        return _fila(
            self._conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND id = ?",
                (principal.user_id, str(task_id)),
            ).fetchone()
        )

    def create_task(self, principal: Principal, datos: dict[str, Any], origen: str = "real") -> dict[str, Any]:
        ahora = _ahora()
        nueva = _nuevo_id()
        with _restricciones():
            self._conn.execute(
                "INSERT INTO tasks (id, user_id, titulo, prioridad, estado, fecha_limite, origen, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    nueva,
                    principal.user_id,
                    datos["titulo"],
                    datos["prioridad"],
                    datos["estado"],
                    datos["fecha_limite"],
                    _origen(origen),
                    ahora,
                    ahora,
                ),
            )
        return self.get_task(principal, UUID(nueva))  # type: ignore[return-value]

    def update_task(self, principal: Principal, task_id: UUID, changes: dict[str, Any]) -> dict[str, Any] | None:
        if self.get_task(principal, task_id) is None:
            return None
        partes, valores = _set_clause(changes, self._ACTUALIZABLES)
        with _restricciones():
            self._conn.execute(
                f"UPDATE tasks SET {partes}, updated_at = ? WHERE user_id = ? AND id = ?",
                (*valores, _ahora(), principal.user_id, str(task_id)),
            )
        return self.get_task(principal, task_id)

    def delete_task(self, principal: Principal, task_id: UUID) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM tasks WHERE user_id = ? AND id = ?",
            (principal.user_id, str(task_id)),
        )
        return cursor.rowcount > 0
