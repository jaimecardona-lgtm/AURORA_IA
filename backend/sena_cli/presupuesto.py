"""CLI del motor de presupuesto mensual en COP (evidencia SENA).

Uso desde la carpeta backend/:
    python sena_cli/presupuesto.py --ingreso 2000000 --ahorro 300000 \
        --gasto "Arriendo:600000:fijo" --gasto "Mercado:250000:variable"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.budget import BudgetError, Expense, summarize  # noqa: E402


def _parse_gasto(texto: str) -> Expense:
    partes = texto.rsplit(":", 2)
    if len(partes) != 3:
        raise BudgetError("Formato de gasto: 'descripcion:monto:fijo|variable'")
    descripcion, monto, tipo = partes
    return Expense.build(descripcion, monto, tipo.strip().lower())


def _cop(valor) -> str:
    return f"$ {valor:,.2f} COP"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resumen de presupuesto mensual en COP")
    parser.add_argument("--ingreso", required=True, help="Ingreso mensual")
    parser.add_argument("--ahorro", default="0", help="Meta de ahorro mensual")
    parser.add_argument(
        "--gasto",
        action="append",
        default=[],
        help="Gasto 'descripcion:monto:fijo|variable'. Se puede repetir.",
    )
    args = parser.parse_args(argv)

    try:
        gastos = [_parse_gasto(g) for g in args.gasto]
        resumen = summarize(args.ingreso, args.ahorro, gastos)
    except BudgetError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Ingreso: {_cop(resumen.income)}")
    print(f"Meta de ahorro: {_cop(resumen.savings_goal)}")
    print(f"Gastos fijos: {_cop(resumen.fixed_total)}")
    print(f"Gastos variables: {_cop(resumen.variable_total)}")
    print(f"Disponible para gastar: {_cop(resumen.available_to_spend)}")
    print(f"Saldo final: {_cop(resumen.balance)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
