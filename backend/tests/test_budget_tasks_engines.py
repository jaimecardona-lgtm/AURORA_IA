"""Pruebas de los motores de presupuesto (COP) y tareas."""

from decimal import Decimal

import pytest

from app.core.budget import BudgetError, Expense, summarize
from app.core.tasks import Task, TaskError, prioritize


def test_resumen_de_presupuesto_en_cop():
    gastos = [
        Expense.build("Arriendo", "600000", "fijo"),
        Expense.build("Mercado", 250000, "variable"),
    ]
    resumen = summarize("2000000", 300000, gastos)
    assert resumen.fixed_total == Decimal("600000.00")
    assert resumen.variable_total == Decimal("250000.00")
    assert resumen.available_to_spend == Decimal("1700000.00")
    assert resumen.balance == Decimal("1150000.00")


@pytest.mark.parametrize(
    ("descripcion", "monto", "tipo", "mensaje"),
    [
        ("", "10", "fijo", "obligatoria"),
        ("Algo", "-1", "fijo", "negativo"),
        ("Algo", "abc", "fijo", "número"),
        ("Algo", True, "fijo", "booleano"),
        ("Algo", "10", "ocasional", "fijo"),
    ],
)
def test_gasto_invalido(descripcion, monto, tipo, mensaje):
    with pytest.raises(BudgetError, match=mensaje):
        Expense.build(descripcion, monto, tipo)


def test_ingreso_negativo_se_rechaza():
    with pytest.raises(BudgetError):
        summarize("-100", 0, [])


def test_prioridad_pendientes_primero_y_luego_prioridad_ascendente():
    tareas = [
        Task.build("Leer", 3, "completada"),
        Task.build("Entregar", 1),
        Task.build("Correo", 2),
        Task.build("Estudiar", 1),
    ]
    orden = [t.title for t in prioritize(tareas)]
    assert orden == ["Entregar", "Estudiar", "Correo", "Leer"]


@pytest.mark.parametrize("prioridad", [0, 4, "x", True])
def test_prioridad_fuera_de_rango_se_rechaza(prioridad):
    with pytest.raises(TaskError):
        Task.build("Tarea", prioridad)


def test_estado_invalido_se_rechaza():
    with pytest.raises(TaskError):
        Task.build("Tarea", 1, "en curso")
