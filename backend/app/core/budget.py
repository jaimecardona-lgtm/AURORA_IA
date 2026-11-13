"""Motor de presupuesto mensual en COP.

Reglas:
- ingreso y meta de ahorro >= 0.
- cada gasto >= 0 y tipo "fijo" o "variable".
- disponible para gastar = ingreso - meta de ahorro.
- saldo = ingreso - suma de gastos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable, Mapping

EXPENSE_TYPES = ("fijo", "variable")
DEFAULT_CATEGORY = "General"
MAX_CATEGORY_LENGTH = 60
_TWO_PLACES = Decimal("0.01")


class BudgetError(ValueError):
    """Dato de presupuesto no válido."""


def _money(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise BudgetError(f"{field} no puede ser un booleano.")
    if isinstance(value, float):
        value = str(value)
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise BudgetError(f"{field} debe ser un número.") from None
    if not amount.is_finite():
        raise BudgetError(f"{field} debe ser un número finito.")
    if amount < 0:
        raise BudgetError(f"{field} no puede ser negativo.")
    return amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Expense:
    description: str
    amount: Decimal
    kind: str  # "fijo" | "variable"
    category: str = DEFAULT_CATEGORY
    date: date | None = None

    @classmethod
    def build(
        cls,
        description: str,
        amount: object,
        kind: str,
        category: str = DEFAULT_CATEGORY,
        date: object = None,
    ) -> "Expense":
        if not description or not str(description).strip():
            raise BudgetError("La descripción del gasto es obligatoria.")
        if kind not in EXPENSE_TYPES:
            raise BudgetError("El tipo de gasto debe ser 'fijo' o 'variable'.")
        clean_category = str(category or "").strip()
        if not clean_category:
            raise BudgetError("La categoría del gasto es obligatoria.")
        if len(clean_category) > MAX_CATEGORY_LENGTH:
            raise BudgetError(f"La categoría no puede superar {MAX_CATEGORY_LENGTH} caracteres.")
        return cls(
            str(description).strip(),
            _money(amount, "El monto"),
            kind,
            clean_category,
            _fecha(date),
        )


def _fecha(value: object) -> date | None:
    """Acepta None, un date o una cadena ISO 'AAAA-MM-DD'."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise BudgetError("La fecha debe tener formato AAAA-MM-DD.") from None


def ensure_in_period(expense: Expense, anio: int, mes: int) -> None:
    """Rechaza un gasto cuya fecha no pertenece al mes del presupuesto."""
    if expense.date is None:
        raise BudgetError("La fecha del gasto es obligatoria.")
    if (expense.date.year, expense.date.month) != (anio, mes):
        raise BudgetError("La fecha del gasto debe pertenecer al mes del presupuesto.")


def by_category(expenses: Iterable[Expense]) -> dict[str, Decimal]:
    """Total por categoría, ordenado de mayor a menor gasto."""
    totales: dict[str, Decimal] = {}
    for expense in expenses:
        totales[expense.category] = totales.get(expense.category, Decimal("0")) + expense.amount
    return dict(sorted(totales.items(), key=lambda par: (-par[1], par[0].lower())))


@dataclass(frozen=True)
class BudgetSummary:
    income: Decimal
    savings_goal: Decimal
    fixed_total: Decimal
    variable_total: Decimal

    @property
    def expenses_total(self) -> Decimal:
        return self.fixed_total + self.variable_total

    @property
    def balance(self) -> Decimal:
        return self.income - self.expenses_total

    @property
    def available_to_spend(self) -> Decimal:
        return self.income - self.savings_goal

    @property
    def savings_achieved(self) -> Decimal:
        """Ahorro real del mes: el saldo, sin valores negativos."""
        return max(self.balance, Decimal("0"))

    @property
    def savings_goal_met(self) -> bool:
        return self.balance >= self.savings_goal


def summarize(income: object, savings_goal: object, expenses: Iterable[Expense]) -> BudgetSummary:
    fixed = Decimal("0")
    variable = Decimal("0")
    for expense in expenses:
        if expense.kind == "fijo":
            fixed += expense.amount
        else:
            variable += expense.amount
    return BudgetSummary(
        income=_money(income, "El ingreso"),
        savings_goal=_money(savings_goal, "La meta de ahorro"),
        fixed_total=fixed,
        variable_total=variable,
    )


def expense_from_mapping(data: Mapping[str, object]) -> Expense:
    return Expense.build(
        description=str(data.get("description", "")),
        amount=data.get("amount"),
        kind=str(data.get("kind", "")),
    )
