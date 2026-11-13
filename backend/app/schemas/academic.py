"""DTO de entrada y salida para asignaturas y notas.

- extra="forbid": un cliente NO puede enviar user_id ni otros campos no previstos.
- La validación de notas delega en el motor app.core.grades (fuente única de reglas).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.grades import GradeError, is_passing, parse_grade

Origen = Literal["real", "demo"]

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)

NombreAsignatura = Annotated[str, Field(min_length=1, max_length=120)]
DescripcionNota = Annotated[str, Field(min_length=1, max_length=200)]


def _validar_nota(value: Any) -> Decimal:
    try:
        return parse_grade(value)
    except GradeError as exc:
        raise ValueError(str(exc)) from exc


class SubjectCreate(BaseModel):
    model_config = _STRICT
    nombre: NombreAsignatura


class SubjectUpdate(BaseModel):
    model_config = _STRICT
    nombre: NombreAsignatura | None = None

    @model_validator(mode="after")
    def _al_menos_un_campo(self) -> "SubjectUpdate":
        if self.model_dump(exclude_unset=True) == {}:
            raise ValueError("Indica al menos un campo para actualizar.")
        return self


class GradeCreate(BaseModel):
    model_config = _STRICT
    descripcion: DescripcionNota
    nota: Decimal

    @field_validator("nota", mode="before")
    @classmethod
    def _nota_valida(cls, value: Any) -> Decimal:
        return _validar_nota(value)


class GradeUpdate(BaseModel):
    model_config = _STRICT
    descripcion: DescripcionNota | None = None
    nota: Decimal | None = None

    @field_validator("nota", mode="before")
    @classmethod
    def _nota_valida(cls, value: Any) -> Decimal | None:
        return None if value is None else _validar_nota(value)

    @model_validator(mode="after")
    def _al_menos_un_campo(self) -> "GradeUpdate":
        if self.model_dump(exclude_unset=True) == {}:
            raise ValueError("Indica al menos un campo para actualizar.")
        return self


class GradeOut(BaseModel):
    id: UUID
    subject_id: UUID
    descripcion: str
    nota: Decimal
    aprobado: bool
    origen: Origen = "real"
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "GradeOut":
        nota = parse_grade(row["nota"])
        return cls(
            id=row["id"],
            subject_id=row["subject_id"],
            descripcion=row["descripcion"],
            nota=nota,
            aprobado=is_passing(nota),
            origen=row.get("origen", "real"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class SubjectOut(BaseModel):
    id: UUID
    nombre: str
    origen: Origen = "real"
    created_at: datetime
    updated_at: datetime
    total_notas: int = 0
    promedio: Decimal | None = None
    aprobado: bool | None = None


class SubjectDetail(SubjectOut):
    notas: list[GradeOut] = Field(default_factory=list)


class RequiredGradeOut(BaseModel):
    objetivo: Decimal
    posible: bool
    nota_minima: Decimal | None
    mensaje: str


class AcademicSummaryOut(BaseModel):
    total_asignaturas: int
    con_notas: int
    aprobadas: int
    reprobadas: int
    promedio_general: Decimal | None


class HealthOut(BaseModel):
    status: str
    supabase_configurado: bool
    version: str
