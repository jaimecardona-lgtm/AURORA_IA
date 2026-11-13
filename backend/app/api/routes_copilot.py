"""Copiloto AURORA (solo lectura): estado de configuración y chat."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.api.deps import CopilotServiceDep, CurrentPrincipal
from app.schemas.copilot import ChatIn, ChatOut, EstadoCopilotoOut

router = APIRouter(prefix="/api/copilot", tags=["copiloto"])


@router.get("/estado", response_model=EstadoCopilotoOut)
def estado(principal: CurrentPrincipal, service: CopilotServiceDep) -> EstadoCopilotoOut:
    """Sin claves ni datos sensibles: solo si está configurado y con qué proveedor."""
    return service.estado()


@router.post("/chat", response_model=ChatOut)
def chat(data: ChatIn, principal: CurrentPrincipal, service: CopilotServiceDep) -> ChatOut:
    return service.chat(principal, data, date.today())
