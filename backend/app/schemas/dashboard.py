"""DTO del panel general (Overview). Todos los valores proceden de los servicios y motores."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.finance import CategoryShareOut
from app.schemas.tasks import TaskOut


class AsignaturaResumen(BaseModel):
    id: UUID
    nombre: str
    promedio: Decimal | None
    aprobado: bool | None
    total_notas: int


class AcademicoDashboard(BaseModel):
    total_asignaturas: int
    con_notas: int
    aprobadas: int
    reprobadas: int
    promedio_general: Decimal | None
    por_asignatura: list[AsignaturaResumen]
    bajo_rendimiento: list[AsignaturaResumen]
    criterio_bajo_rendimiento: str = Field(description="Regla aplicada; viene del motor de calificaciones.")


class FinanzasDashboard(BaseModel):
    disponible: bool
    anio: int
    mes: int
    tiene_presupuesto: bool = False
    ingreso: Decimal | None = None
    meta_ahorro: Decimal | None = None
    gastos_total: Decimal | None = None
    gastos_fijos: Decimal | None = None
    gastos_variables: Decimal | None = None
    saldo: Decimal | None = None
    ahorro_logrado: Decimal | None = None
    disponible_para_gastar: Decimal | None = None
    porcentaje_meta_ahorro: Decimal | None = None
    meta_cumplida: bool | None = None
    categorias: list[CategoryShareOut] = Field(default_factory=list)


class PrioridadesConteo(BaseModel):
    alta: int
    media: int
    baja: int


class TareasDashboard(BaseModel):
    disponible: bool
    total: int = 0
    completadas: int = 0
    pendientes: int = 0
    porcentaje: Decimal | None = None
    vencidas: list[TaskOut] = Field(default_factory=list)
    proximas: list[TaskOut] = Field(default_factory=list)
    proximas_total: int = 0
    pendientes_por_prioridad: PrioridadesConteo | None = None


class DashboardOut(BaseModel):
    persistencia: Literal["sqlite", "supabase"]
    generado_el: date
    academico: AcademicoDashboard
    finanzas: FinanzasDashboard
    tareas: TareasDashboard
