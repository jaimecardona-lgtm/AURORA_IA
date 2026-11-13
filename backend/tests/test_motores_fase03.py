"""Pruebas unitarias de las reglas añadidas en la Fase 03 (sin FastAPI ni base de datos)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.budget import BudgetError, Expense, by_category, ensure_in_period, summarize
from app.core.grades import GradeError, required_grade, summarize_subjects
from app.core.tasks import Task, TaskError, due_summary, filter_tasks, prioritize, progress


# ----------------------------------------------------------- nota necesaria
def test_nota_necesaria_calcula_el_minimo_exacto():
    # (4.5 + 3.0 + 2.9 + x) / 4 >= 3.5  ->  x >= 3.6
    r = required_grade(["4.5", "3.0", "2.9"], "3.5")
    assert r.possible is True
    assert r.minimum == Decimal("3.60")


def test_nota_necesaria_es_suficiente_para_alcanzar_el_objetivo():
    notas = [Decimal("4.2"), Decimal("3.1")]
    r = required_grade(notas, "3.8")
    assert r.possible
    promedio = (sum(notas) + r.minimum) / (len(notas) + 1)
    assert promedio >= Decimal("3.8")


def test_nota_necesaria_imposible_cuando_ni_5_alcanza():
    r = required_grade(["2.0", "1.0"], "4.5")
    assert r.possible is False
    assert r.minimum is None
    assert "No es posible" in r.message


def test_nota_necesaria_cero_cuando_el_promedio_ya_alcanza_el_objetivo():
    r = required_grade(["5.0", "5.0"], "3.0")
    assert r.possible and r.minimum == Decimal("0.00")


def test_nota_necesaria_sin_notas_es_el_propio_objetivo():
    assert required_grade([], "3.0").minimum == Decimal("3.00")


def test_nota_necesaria_redondea_hacia_arriba():
    # x >= 3*(n+1) - S con decimales: nunca debe quedar por debajo del objetivo.
    r = required_grade(["3.33", "3.33"], "3.34")
    assert r.minimum is not None
    assert (Decimal("3.33") * 2 + r.minimum) / 3 >= Decimal("3.34")


@pytest.mark.parametrize("objetivo", ["-1", "5.1", "abc", True])
def test_objetivo_fuera_de_rango_se_rechaza(objetivo):
    with pytest.raises(GradeError):
        required_grade(["3.0"], objetivo)


def test_resumen_academico_cuenta_aprobadas_y_promedio_general():
    r = summarize_subjects([Decimal("3.47"), None, Decimal("2.00"), Decimal("4.00")])
    assert r.total_asignaturas == 4
    assert r.con_notas == 3
    assert r.aprobadas == 2
    assert r.reprobadas == 1
    assert r.promedio_general == Decimal("3.16")


def test_resumen_academico_sin_notas_no_inventa_promedio():
    r = summarize_subjects([None, None])
    assert r.promedio_general is None and r.con_notas == 0


# ----------------------------------------------------------- presupuesto
def test_gasto_con_categoria_y_fecha():
    gasto = Expense.build("Mercado", "250000", "variable", "Alimentación", "2026-03-05")
    assert gasto.category == "Alimentación"
    assert gasto.date == date(2026, 3, 5)


@pytest.mark.parametrize(
    ("categoria", "fecha", "mensaje"),
    [
        ("", "2026-03-05", "categoría"),
        ("   ", "2026-03-05", "categoría"),
        ("x" * 61, "2026-03-05", "superar"),
        ("Ocio", "05/03/2026", "AAAA-MM-DD"),
        ("Ocio", "2026-02-30", "AAAA-MM-DD"),
    ],
)
def test_gasto_con_categoria_o_fecha_invalidas(categoria, fecha, mensaje):
    with pytest.raises(BudgetError, match=mensaje):
        Expense.build("Algo", "10", "fijo", categoria, fecha)


def test_gasto_debe_pertenecer_al_mes_del_presupuesto():
    gasto = Expense.build("Algo", "10", "fijo", "Ocio", "2026-03-31")
    ensure_in_period(gasto, 2026, 3)
    with pytest.raises(BudgetError, match="mes del presupuesto"):
        ensure_in_period(gasto, 2026, 4)


def test_gasto_sin_fecha_no_es_valido_para_un_mes():
    gasto = Expense.build("Algo", "10", "fijo", "Ocio")
    with pytest.raises(BudgetError, match="obligatoria"):
        ensure_in_period(gasto, 2026, 3)


def test_totales_por_categoria_ordenados_de_mayor_a_menor():
    gastos = [
        Expense.build("A", "100", "fijo", "Vivienda"),
        Expense.build("B", "300", "variable", "Ocio"),
        Expense.build("C", "50", "variable", "Vivienda"),
    ]
    totales = by_category(gastos)
    assert totales == {"Vivienda": Decimal("150"), "Ocio": Decimal("300")}
    assert list(totales) == ["Ocio", "Vivienda"]  # de mayor a menor gasto


def test_meta_de_ahorro_y_ahorro_logrado():
    resumen = summarize("2000000", "300000", [Expense.build("A", "1500000", "fijo", "Vivienda")])
    assert resumen.balance == Decimal("500000.00")
    assert resumen.savings_goal_met is True
    assert resumen.savings_achieved == Decimal("500000.00")


def test_saldo_negativo_no_cuenta_como_ahorro():
    resumen = summarize("1000000", "200000", [Expense.build("A", "1500000", "fijo", "Vivienda")])
    assert resumen.balance == Decimal("-500000.00")
    assert resumen.savings_achieved == Decimal("0")
    assert resumen.savings_goal_met is False


def test_meta_de_ahorro_negativa_se_rechaza():
    with pytest.raises(BudgetError):
        summarize("1000000", "-1", [])


# ----------------------------------------------------------- tareas
def _tarea(titulo, prioridad, estado="pendiente", dias=None, ref=""):
    limite = date.today() + timedelta(days=dias) if dias is not None else None
    return Task(title=titulo, priority=prioridad, status=estado, due_date=limite, ref=ref)


def test_fecha_limite_se_acepta_como_texto_iso():
    tarea = Task.build("Entregar", 1, "pendiente", "2026-04-10")
    assert tarea.due_date == date(2026, 4, 10)


def test_fecha_limite_invalida_se_rechaza():
    with pytest.raises(TaskError, match="AAAA-MM-DD"):
        Task.build("Entregar", 1, "pendiente", "10/04/2026")


def test_vencidas_y_proximas_solo_entre_pendientes():
    hoy = date(2026, 5, 10)
    tareas = [
        Task("Vencida", 1, "pendiente", date(2026, 5, 8)),
        Task("Hoy", 2, "pendiente", date(2026, 5, 10)),
        Task("En 3 días", 2, "pendiente", date(2026, 5, 13)),
        Task("Lejana", 3, "pendiente", date(2026, 6, 30)),
        Task("Completada vencida", 1, "completada", date(2026, 5, 1)),
        Task("Sin fecha", 1, "pendiente", None),
    ]
    aviso = due_summary(tareas, hoy, days=7)
    assert [t.title for t in aviso.vencidas] == ["Vencida"]
    assert [t.title for t in aviso.proximas] == ["Hoy", "En 3 días"]


def test_ventana_de_proximas_no_puede_ser_negativa():
    with pytest.raises(TaskError):
        due_summary([], date(2026, 1, 1), days=-1)


def test_progreso_porcentaje_con_dos_decimales():
    tareas = [_tarea("a", 1, "completada"), _tarea("b", 2), _tarea("c", 3)]
    p = progress(tareas)
    assert (p.total, p.completadas, p.pendientes) == (3, 1, 2)
    assert p.porcentaje == Decimal("33.33")


def test_progreso_sin_tareas_es_cero():
    assert progress([]).porcentaje == Decimal("0.00")


def test_filtros_por_estado_y_prioridad():
    tareas = [_tarea("a", 1), _tarea("b", 2, "completada"), _tarea("c", 1, "completada")]
    assert [t.title for t in filter_tasks(tareas, status="completada")] == ["b", "c"]
    assert [t.title for t in filter_tasks(tareas, priority=1)] == ["a", "c"]
    assert [t.title for t in filter_tasks(tareas, status="pendiente", priority=1)] == ["a"]
    with pytest.raises(TaskError):
        filter_tasks(tareas, priority=9)


def test_orden_del_motor_se_mantiene_con_el_nuevo_campo():
    tareas = [Task("Leer", 3, "completada"), Task("Entregar", 1), Task("Correo", 2)]
    assert [t.title for t in prioritize(tareas)] == ["Entregar", "Correo", "Leer"]
