"""Panel general (Overview): indicadores reales de los tres módulos."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import CurrentPrincipal, DashboardServiceDep
from app.schemas.dashboard import DashboardOut

router = APIRouter(prefix="/api", tags=["panel"])


@router.get("/dashboard", response_model=DashboardOut)
def panel(
    principal: CurrentPrincipal,
    service: DashboardServiceDep,
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
) -> DashboardOut:
    hoy = date.today()
    return service.build(principal, anio or hoy.year, mes or hoy.month, hoy)
