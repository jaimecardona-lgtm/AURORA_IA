"""Endpoints del presupuesto mensual en COP (solo SQLite en esta fase)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path, Response, status

from app.api.deps import BudgetServiceDep, CurrentPrincipal
from app.schemas.finance import (
    BudgetDetailOut,
    BudgetIn,
    BudgetOut,
    ExpenseIn,
    ExpenseOut,
    ExpenseUpdate,
)

router = APIRouter(prefix="/api/finanzas", tags=["finanzas"])

AnioPath = Path(ge=2000, le=2100, description="Año del presupuesto.")
MesPath = Path(ge=1, le=12, description="Mes del presupuesto (1 a 12).")


@router.get("/presupuestos", response_model=list[BudgetOut])
def listar_presupuestos(principal: CurrentPrincipal, service: BudgetServiceDep) -> list[BudgetOut]:
    return service.list_budgets(principal)


@router.put("/presupuestos/{anio}/{mes}", response_model=BudgetOut)
def definir_presupuesto(
    data: BudgetIn,
    principal: CurrentPrincipal,
    service: BudgetServiceDep,
    anio: int = AnioPath,
    mes: int = MesPath,
) -> BudgetOut:
    """Crea o actualiza el ingreso y la meta de ahorro del mes."""
    return service.define_budget(principal, anio, mes, data)


@router.get("/presupuestos/{anio}/{mes}", response_model=BudgetDetailOut)
def obtener_presupuesto(
    principal: CurrentPrincipal,
    service: BudgetServiceDep,
    anio: int = AnioPath,
    mes: int = MesPath,
) -> BudgetDetailOut:
    return service.get_budget(principal, anio, mes)


@router.post("/presupuestos/{anio}/{mes}/gastos", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def registrar_gasto(
    data: ExpenseIn,
    principal: CurrentPrincipal,
    service: BudgetServiceDep,
    anio: int = AnioPath,
    mes: int = MesPath,
) -> ExpenseOut:
    return service.add_expense(principal, anio, mes, data)


@router.patch("/gastos/{expense_id}", response_model=ExpenseOut)
def actualizar_gasto(
    expense_id: UUID,
    data: ExpenseUpdate,
    principal: CurrentPrincipal,
    service: BudgetServiceDep,
) -> ExpenseOut:
    return service.update_expense(principal, expense_id, data)


@router.delete("/gastos/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def eliminar_gasto(expense_id: UUID, principal: CurrentPrincipal, service: BudgetServiceDep) -> Response:
    service.delete_expense(principal, expense_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
