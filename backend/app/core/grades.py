"""Motor de calificaciones: escala 0–5, aprobación desde 3.0.

Usa Decimal para evitar errores de coma flotante en promedios y comparaciones
con el umbral de aprobación.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable

GRADE_MIN = Decimal("0")
GRADE_MAX = Decimal("5")
PASSING_GRADE = Decimal("3.0")
_TWO_PLACES = Decimal("0.01")


class GradeError(ValueError):
    """Nota o entrada de calificaciones no válida."""


def parse_grade(value: object) -> Decimal:
    """Convierte una nota a Decimal con dos decimales, validando el rango 0–5.

    Rechaza booleanos (bool es subclase de int en Python), NaN, infinitos y
    valores fuera de rango.
    """
    if isinstance(value, bool):
        raise GradeError("La nota no puede ser un booleano.")
    if isinstance(value, float):
        # Convertir mediante str evita arrastrar el error binario del float.
        value = str(value)
    try:
        grade = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise GradeError("La nota debe ser un número.") from None
    if not grade.is_finite():
        raise GradeError("La nota debe ser un número finito.")
    if grade < GRADE_MIN or grade > GRADE_MAX:
        raise GradeError("La nota debe estar entre 0 y 5.")
    return grade.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def average(grades: Iterable[object]) -> Decimal:
    """Promedio aritmético redondeado a dos decimales.

    Lanza GradeError si no hay notas, porque un promedio sin datos no es 0.
    """
    parsed = [parse_grade(g) for g in grades]
    if not parsed:
        raise GradeError("No hay notas para calcular el promedio.")
    total = sum(parsed, Decimal("0"))
    return (total / len(parsed)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def is_passing(grade: object) -> bool:
    """True si la nota (o promedio) alcanza la aprobación (>= 3.0)."""
    return parse_grade(grade) >= PASSING_GRADE


# ---------------------------------------------------------------------------
# Nota necesaria para alcanzar un promedio objetivo.
# Supuesto (documentado): todas las notas de una asignatura pesan igual, como
# en `average`. Con n notas y suma S, la nota x que deja el promedio en T es
#     (S + x) / (n + 1) >= T   ->   x >= T * (n + 1) - S
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RequiredGrade:
    target: Decimal
    possible: bool
    minimum: Decimal | None  # None cuando no es posible
    message: str


def required_grade(grades: Iterable[object], target: object) -> RequiredGrade:
    """Calcula la nota mínima que la próxima evaluación necesita para alcanzar `target`.

    - Si ni con 5.00 se alcanza, `possible` es False y `minimum` es None.
    - Si el promedio ya alcanza `target` aunque la nueva nota sea 0, `minimum` es 0.00.
    - En otro caso, `minimum` es el valor redondeado HACIA ARRIBA a dos decimales,
      para que el promedio resultante no quede por debajo del objetivo.
    """
    goal = parse_grade(target)
    notas = [parse_grade(g) for g in grades]
    needed = goal * (len(notas) + 1) - sum(notas, Decimal("0"))

    if needed > GRADE_MAX:
        return RequiredGrade(
            target=goal,
            possible=False,
            minimum=None,
            message=f"No es posible: ni con {GRADE_MAX} se alcanza un promedio de {goal}.",
        )
    if needed <= GRADE_MIN:
        return RequiredGrade(
            target=goal,
            possible=True,
            minimum=Decimal("0.00"),
            message=f"Ya alcanzas {goal} aunque la próxima nota sea 0.",
        )
    minimum = needed.quantize(_TWO_PLACES, rounding=ROUND_CEILING)
    return RequiredGrade(
        target=goal,
        possible=True,
        minimum=minimum,
        message=f"Necesitas al menos {minimum} en la próxima nota.",
    )


# ---------------------------------------------------------------------------
# Resumen académico global. Cada asignatura pesa igual (promedio de promedios).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AcademicSummary:
    total_asignaturas: int
    con_notas: int
    aprobadas: int
    reprobadas: int
    promedio_general: Decimal | None


def summarize_subjects(averages: Iterable[Decimal | None]) -> AcademicSummary:
    valores = list(averages)
    con_notas = [v for v in valores if v is not None]
    aprobadas = sum(1 for v in con_notas if is_passing(v))
    promedio = (
        (sum(con_notas, Decimal("0")) / len(con_notas)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        if con_notas
        else None
    )
    return AcademicSummary(
        total_asignaturas=len(valores),
        con_notas=len(con_notas),
        aprobadas=aprobadas,
        reprobadas=len(con_notas) - aprobadas,
        promedio_general=promedio,
    )
