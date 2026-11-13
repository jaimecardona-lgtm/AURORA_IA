"""Adaptadores PostgREST de Finanzas (presupuestos y gastos) y Tareas.

Misma interfaz que los repositorios SQLite (app/infrastructure/sqlite/repositories.py), para que
los servicios existentes funcionen sin cambios.

Seguridad:
- Cada petición lleva el JWT del usuario (access_token). RLS filtra por auth.uid().
- No se envía user_id: la base lo asigna con DEFAULT auth.uid() y la política WITH CHECK lo valida.
- No se usa service_role. No se filtra por user_id en el cliente: el aislamiento es de la base.
- Los importes se envían como cadenas decimales exactas, nunca como float.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.errors import SupabaseRejectedTokenError
from app.repositories.postgrest_client import PostgrestClient
from app.security.principal import Principal

MONTHLY_BUDGETS = "monthly_budgets"
BUDGET_EXPENSES = "budget_expenses"
TASKS = "tasks"


def _token(principal: Principal) -> str:
    if not principal.access_token:
        raise SupabaseRejectedTokenError("La sesión no es válida. Vuelve a iniciar sesión.")
    return principal.access_token


def _primera(filas: list[dict[str, Any]]) -> dict[str, Any] | None:
    return filas[0] if filas else None


class PostgrestBudgetRepository:
    def __init__(self, client: PostgrestClient) -> None:
        self._client = client

    # ----- presupuestos ---------------------------------------------------
    def list_budgets(self, principal: Principal) -> list[dict[str, Any]]:
        return self._client.request(
            "GET", MONTHLY_BUDGETS, access_token=_token(principal),
            params={"select": "*", "order": "anio.desc,mes.desc"},
        )

    def get_budget(self, principal: Principal, anio: int, mes: int) -> dict[str, Any] | None:
        return _primera(self._client.request(
            "GET", MONTHLY_BUDGETS, access_token=_token(principal),
            params={"select": "*", "anio": f"eq.{anio}", "mes": f"eq.{mes}", "limit": "1"},
        ))

    def get_budget_by_id(self, principal: Principal, budget_id: UUID) -> dict[str, Any] | None:
        return _primera(self._client.request(
            "GET", MONTHLY_BUDGETS, access_token=_token(principal),
            params={"select": "*", "id": f"eq.{budget_id}", "limit": "1"},
        ))

    def upsert_budget(
        self, principal: Principal, anio: int, mes: int, ingreso: str, meta_ahorro: str, origen: str = "real"
    ) -> dict[str, Any]:
        """Crea o actualiza el presupuesto del mes. `origen` no existe en PostgreSQL (solo demo local)."""
        existente = self.get_budget(principal, anio, mes)
        token = _token(principal)
        if existente is None:
            filas = self._client.request(
                "POST", MONTHLY_BUDGETS, access_token=token,
                json={"anio": anio, "mes": mes, "ingreso": ingreso, "meta_ahorro": meta_ahorro},
                return_representation=True,
            )
        else:
            filas = self._client.request(
                "PATCH", MONTHLY_BUDGETS, access_token=token,
                params={"id": f"eq.{existente['id']}"},
                json={"ingreso": ingreso, "meta_ahorro": meta_ahorro},
                return_representation=True,
            )
        return filas[0]

    # ----- gastos -----------------------------------------------------------
    def list_expenses(self, principal: Principal, budget_id: UUID) -> list[dict[str, Any]]:
        return self._client.request(
            "GET", BUDGET_EXPENSES, access_token=_token(principal),
            params={"select": "*", "budget_id": f"eq.{budget_id}", "order": "fecha.asc,created_at.asc"},
        )

    def get_expense(self, principal: Principal, expense_id: UUID) -> dict[str, Any] | None:
        return _primera(self._client.request(
            "GET", BUDGET_EXPENSES, access_token=_token(principal),
            params={"select": "*", "id": f"eq.{expense_id}", "limit": "1"},
        ))

    def create_expense(
        self, principal: Principal, budget_id: UUID, datos: dict[str, Any], origen: str = "real"
    ) -> dict[str, Any]:
        filas = self._client.request(
            "POST", BUDGET_EXPENSES, access_token=_token(principal),
            json={
                "budget_id": str(budget_id),
                "descripcion": datos["descripcion"],
                "categoria": datos["categoria"],
                "monto": str(datos["monto"]),
                "tipo": datos["tipo"],
                "fecha": datos["fecha"],
            },
            return_representation=True,
        )
        return filas[0]

    def update_expense(self, principal: Principal, expense_id: UUID, changes: dict[str, Any]) -> dict[str, Any] | None:
        cambios = {k: (str(v) if k == "monto" else v) for k, v in changes.items()}
        return _primera(self._client.request(
            "PATCH", BUDGET_EXPENSES, access_token=_token(principal),
            params={"id": f"eq.{expense_id}"}, json=cambios, return_representation=True,
        ))

    def delete_expense(self, principal: Principal, expense_id: UUID) -> bool:
        return bool(self._client.request(
            "DELETE", BUDGET_EXPENSES, access_token=_token(principal),
            params={"id": f"eq.{expense_id}"}, return_representation=True,
        ))


class PostgrestTaskRepository:
    def __init__(self, client: PostgrestClient) -> None:
        self._client = client

    def list_tasks(self, principal: Principal) -> list[dict[str, Any]]:
        return self._client.request(
            "GET", TASKS, access_token=_token(principal),
            params={"select": "*", "order": "created_at.asc"},
        )

    def get_task(self, principal: Principal, task_id: UUID) -> dict[str, Any] | None:
        return _primera(self._client.request(
            "GET", TASKS, access_token=_token(principal),
            params={"select": "*", "id": f"eq.{task_id}", "limit": "1"},
        ))

    def create_task(self, principal: Principal, datos: dict[str, Any], origen: str = "real") -> dict[str, Any]:
        filas = self._client.request(
            "POST", TASKS, access_token=_token(principal),
            json={
                "titulo": datos["titulo"],
                "prioridad": datos["prioridad"],
                "estado": datos["estado"],
                "fecha_limite": datos["fecha_limite"],
            },
            return_representation=True,
        )
        return filas[0]

    def update_task(self, principal: Principal, task_id: UUID, changes: dict[str, Any]) -> dict[str, Any] | None:
        return _primera(self._client.request(
            "PATCH", TASKS, access_token=_token(principal),
            params={"id": f"eq.{task_id}"}, json=changes, return_representation=True,
        ))

    def delete_task(self, principal: Principal, task_id: UUID) -> bool:
        return bool(self._client.request(
            "DELETE", TASKS, access_token=_token(principal),
            params={"id": f"eq.{task_id}"}, return_representation=True,
        ))
