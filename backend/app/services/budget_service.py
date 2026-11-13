"""Reglas del módulo financiero: presupuesto mensual, gastos y categorías.

Las cuentas y validaciones de importes las hace el motor app.core.budget.
Este servicio solo traduce errores del motor a 422 y decide 404/409 según el caso.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from app.core.budget import (
    BudgetError,
    Expense,
    by_category,
    ensure_in_period,
    summarize,
)
from app.errors import NotFoundError, ValidationFailedError
from app.infrastructure.sqlite.repositories import SqliteBudgetRepository
from app.schemas.finance import (
    BudgetDetailOut,
    BudgetIn,
    BudgetOut,
    CategoryShareOut,
    ExpenseIn,
    ExpenseOut,
    ExpenseUpdate,
)
from app.security.principal import Principal

_DOS = Decimal("0.01")


def _traducir(fn, *args, **kwargs):
    """Convierte BudgetError del motor en 422 de dominio."""
    try:
        return fn(*args, **kwargs)
    except BudgetError as exc:
        raise ValidationFailedError(str(exc)) from None


def _dec(valor: Any) -> Decimal:
    return Decimal(str(valor)).quantize(_DOS, rounding=ROUND_HALF_UP)


class BudgetService:
    def __init__(self, repository: SqliteBudgetRepository) -> None:
        self._repo = repository

    # ----- helpers ---------------------------------------------------------
    def _motor_gastos(self, filas: list[dict[str, Any]]) -> list[Expense]:
        return [
            Expense(
                description=f["descripcion"],
                amount=_dec(f["monto"]),
                kind=f["tipo"],
                category=f["categoria"],
                date=date.fromisoformat(f["fecha"]),
            )
            for f in filas
        ]

    def _presupuesto_o_404(self, principal: Principal, anio: int, mes: int) -> dict[str, Any]:
        presupuesto = self._repo.get_budget(principal, anio, mes)
        if presupuesto is None:
            raise NotFoundError("No hay presupuesto registrado para ese mes.")
        return presupuesto

    def _resumen(self, presupuesto: dict[str, Any], filas_gastos: list[dict[str, Any]]) -> dict[str, Any]:
        gastos = self._motor_gastos(filas_gastos)
        resumen = summarize(presupuesto["ingreso"], presupuesto["meta_ahorro"], gastos)
        return {
            "anio": presupuesto["anio"],
            "mes": presupuesto["mes"],
            "ingreso": _dec(presupuesto["ingreso"]),
            "meta_ahorro": _dec(presupuesto["meta_ahorro"]),
            "origen": presupuesto.get("origen", "real"),
            "gastos_total": resumen.expenses_total,
            "saldo": resumen.balance,
            "meta_cumplida": resumen.savings_goal_met,
            "gastos_fijos": resumen.fixed_total,
            "gastos_variables": resumen.variable_total,
            "disponible_para_gastar": resumen.available_to_spend,
            "ahorro_logrado": resumen.savings_achieved,
            "_gastos": gastos,
        }

    # ----- presupuesto -----------------------------------------------------
    def list_budgets(self, principal: Principal) -> list[BudgetOut]:
        salida = []
        for presupuesto in self._repo.list_budgets(principal):
            filas = self._repo.list_expenses(principal, UUID(presupuesto["id"]))
            datos = self._resumen(presupuesto, filas)
            datos.pop("gastos_fijos")
            datos.pop("gastos_variables")
            datos.pop("disponible_para_gastar")
            datos.pop("ahorro_logrado")
            datos.pop("_gastos")
            salida.append(BudgetOut(**datos))
        return salida

    def define_budget(self, principal: Principal, anio: int, mes: int, data: BudgetIn) -> BudgetOut:
        # summarize valida importes (no negativos, numéricos) con las mismas reglas del motor.
        _traducir(summarize, data.ingreso, data.meta_ahorro, [])
        presupuesto = self._repo.upsert_budget(
            principal, anio, mes, str(data.ingreso), str(data.meta_ahorro)
        )
        filas = self._repo.list_expenses(principal, UUID(presupuesto["id"]))
        datos = self._resumen(presupuesto, filas)
        for clave in ("gastos_fijos", "gastos_variables", "disponible_para_gastar", "ahorro_logrado", "_gastos"):
            datos.pop(clave)
        return BudgetOut(**datos)

    def get_budget(self, principal: Principal, anio: int, mes: int) -> BudgetDetailOut:
        presupuesto = self._presupuesto_o_404(principal, anio, mes)
        filas = self._repo.list_expenses(principal, UUID(presupuesto["id"]))
        datos = self._resumen(presupuesto, filas)
        gastos: list[Expense] = datos.pop("_gastos")
        total = datos["gastos_total"]
        categorias = [
            CategoryShareOut(
                categoria=nombre,
                total=_dec(monto),
                porcentaje=(
                    (monto * 100 / total).quantize(_DOS, rounding=ROUND_HALF_UP) if total else Decimal("0.00")
                ),
            )
            for nombre, monto in by_category(gastos).items()
        ]
        return BudgetDetailOut(
            **datos,
            categorias=categorias,
            gastos=[ExpenseOut.from_row(f) for f in filas],
        )

    # ----- gastos ----------------------------------------------------------
    def add_expense(self, principal: Principal, anio: int, mes: int, data: ExpenseIn) -> ExpenseOut:
        presupuesto = self._presupuesto_o_404(principal, anio, mes)
        gasto = _traducir(
            Expense.build,
            data.descripcion, data.monto, data.tipo, data.categoria, data.fecha,
        )
        _traducir(ensure_in_period, gasto, anio, mes)
        fila = self._repo.create_expense(
            principal,
            UUID(presupuesto["id"]),
            {
                "descripcion": gasto.description,
                "categoria": gasto.category,
                "monto": str(gasto.amount),
                "tipo": gasto.kind,
                "fecha": gasto.date.isoformat(),  # type: ignore[union-attr]
            },
        )
        return ExpenseOut.from_row(fila)

    def update_expense(self, principal: Principal, expense_id: UUID, data: ExpenseUpdate) -> ExpenseOut:
        actual = self._repo.get_expense(principal, expense_id)
        if actual is None:
            raise NotFoundError("El gasto no existe o no es accesible.")
        presupuesto = self._repo.get_budget_by_id(principal, UUID(actual["budget_id"]))
        if presupuesto is None:  # no debería ocurrir: FK compuesta
            raise NotFoundError("El gasto no existe o no es accesible.")

        cambios = data.model_dump(exclude_unset=True)
        if any(valor is None for valor in cambios.values()):
            raise ValidationFailedError("Los campos del gasto no pueden quedar vacíos.")

        fusion = {
            "descripcion": actual["descripcion"],
            "monto": actual["monto"],
            "tipo": actual["tipo"],
            "categoria": actual["categoria"],
            "fecha": date.fromisoformat(actual["fecha"]),
            **cambios,
        }
        gasto = _traducir(
            Expense.build,
            fusion["descripcion"], fusion["monto"], fusion["tipo"], fusion["categoria"], fusion["fecha"],
        )
        _traducir(ensure_in_period, gasto, presupuesto["anio"], presupuesto["mes"])

        normalizado = {
            "descripcion": gasto.description,
            "categoria": gasto.category,
            "monto": str(gasto.amount),
            "tipo": gasto.kind,
            "fecha": gasto.date.isoformat(),  # type: ignore[union-attr]
        }
        cambios_bd = {k: normalizado[k] for k in cambios}
        fila = self._repo.update_expense(principal, expense_id, cambios_bd)
        if fila is None:
            raise NotFoundError("El gasto no existe o no es accesible.")
        return ExpenseOut.from_row(fila)

    def delete_expense(self, principal: Principal, expense_id: UUID) -> None:
        if not self._repo.delete_expense(principal, expense_id):
            raise NotFoundError("El gasto no existe o no es accesible.")
