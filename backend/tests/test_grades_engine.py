"""Pruebas unitarias del motor de calificaciones (escala 0–5, aprobación >= 3.0)."""

from decimal import Decimal

import pytest

from app.core.grades import GradeError, average, is_passing, parse_grade


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (0, "0.00"),
        (5, "5.00"),
        ("4.5", "4.50"),
        (3.25, "3.25"),
        ("  2.9  ", "2.90"),
        (Decimal("4.257"), "4.26"),  # redondeo half-up a dos decimales
    ],
)
def test_notas_validas_se_normalizan(entrada, esperado):
    assert str(parse_grade(entrada)) == esperado


@pytest.mark.parametrize(
    "entrada",
    [-0.01, 5.01, "6", "-1", "abc", "", None, True, False, float("nan"), float("inf"), "NaN"],
)
def test_notas_invalidas_se_rechazan(entrada):
    with pytest.raises(GradeError):
        parse_grade(entrada)


def test_promedio_redondeado_a_dos_decimales():
    assert str(average(["4.5", "3.0", "2.9"])) == "3.47"


def test_promedio_sin_notas_no_es_cero():
    with pytest.raises(GradeError):
        average([])


def test_promedio_con_nota_invalida_falla():
    with pytest.raises(GradeError):
        average(["4.0", "7"])


@pytest.mark.parametrize(
    ("nota", "aprueba"),
    [("2.99", False), ("3.00", True), ("3", True), ("3.01", True), ("0", False)],
)
def test_umbral_de_aprobacion_es_3_0(nota, aprueba):
    assert is_passing(nota) is aprueba
