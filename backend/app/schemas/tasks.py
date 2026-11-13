"""DTO del gestor de tareas.

La API usa prioridad con nombres (alta, media, baja); el motor usa 1, 2 y 3.
La traducción vive aquí, en un único punto (PRIORIDAD_A_VALOR / VALOR_A_PRIORIDAD).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)

Origen = Literal["real", "demo"]
PrioridadNombre = Literal["alta", "media", "baja"]
Estado = Literal["pendiente", "completada"]

PRIORIDAD_A_VALOR: dict[str, int] = {"alta": 1, "media": 2, "baja": 3}
VALOR_A_PRIORIDAD: dict[int, str] = {v: k for k, v in PRIORIDAD_A_VALOR.items()}


class TaskIn(BaseModel):
    model_config = _STRICT
    titulo: Annotated[str, Field(min_length=1, max_length=200)]
    prioridad: PrioridadNombre
    estado: Estado = "pendiente"
    fecha_limite: date | None = None


class TaskUpdate(BaseModel):
    model_config = _STRICT
    titulo: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    prioridad: PrioridadNombre | None = None
    estado: Estado | None = None
    fecha_limite: date | None = None

    @model_validator(mode="after")
    def _al_menos_un_campo(self) -> "TaskUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("Indica al menos un campo para actualizar.")
        return self


class TaskOut(BaseModel):
    id: UUID
    titulo: str
    prioridad: PrioridadNombre
    prioridad_valor: int
    estado: Estado
    fecha_limite: date | None
    dias_para_vencer: int | None  # negativo = vencida; None = sin fecha límite
    vencida: bool
    origen: Origen = "real"
    created_at: datetime
    updated_at: datetime


class TaskSummaryOut(BaseModel):
    total: int
    completadas: int
    pendientes: int
    porcentaje: Decimal
    vencidas: list[TaskOut]
    proximas: list[TaskOut]
