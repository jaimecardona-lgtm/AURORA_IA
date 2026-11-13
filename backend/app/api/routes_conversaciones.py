"""Conversaciones persistidas del copiloto (Fase 08A). Identidad siempre desde el JWT validado."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import ConversacionesServiceDep, CurrentPrincipal
from app.schemas.conversaciones import (
    LIMITE_PAGINA_MAX,
    ConversacionCrear,
    ConversacionesPagina,
    ConversacionOut,
    ConversacionTitulo,
    MensajeCrear,
    MensajeGuardadoOut,
    MensajesPagina,
)

router = APIRouter(prefix="/api/copilot/conversaciones", tags=["copiloto"])


@router.get("", response_model=ConversacionesPagina)
def listar(
    principal: CurrentPrincipal,
    service: ConversacionesServiceDep,
    limit: int = Query(20, ge=1, le=LIMITE_PAGINA_MAX),
    offset: int = Query(0, ge=0),
) -> ConversacionesPagina:
    return service.listar(principal, limit, offset)


@router.post("", response_model=ConversacionOut, status_code=status.HTTP_201_CREATED)
def crear(data: ConversacionCrear | None, principal: CurrentPrincipal, service: ConversacionesServiceDep) -> ConversacionOut:
    return service.crear(principal, data.title if data else None)


@router.get("/{conversation_id}", response_model=ConversacionOut)
def obtener(conversation_id: UUID, principal: CurrentPrincipal, service: ConversacionesServiceDep) -> ConversacionOut:
    return service.obtener(principal, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversacionOut)
def renombrar(
    conversation_id: UUID, data: ConversacionTitulo, principal: CurrentPrincipal, service: ConversacionesServiceDep
) -> ConversacionOut:
    return service.renombrar(principal, conversation_id, data.title)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def eliminar(
    conversation_id: UUID,
    principal: CurrentPrincipal,
    service: ConversacionesServiceDep,
    confirmar: bool = Query(False, description="Debe ser true: confirmación explícita del borrado."),
) -> Response:
    service.eliminar(principal, conversation_id, confirmar)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{conversation_id}/mensajes", response_model=MensajesPagina)
def mensajes(
    conversation_id: UUID,
    principal: CurrentPrincipal,
    service: ConversacionesServiceDep,
    limit: int = Query(100, ge=1, le=LIMITE_PAGINA_MAX),
    offset: int = Query(0, ge=0),
) -> MensajesPagina:
    return service.mensajes(principal, conversation_id, limit, offset)


@router.post("/{conversation_id}/mensajes", response_model=MensajeGuardadoOut, status_code=status.HTTP_201_CREATED)
def guardar_mensaje(
    conversation_id: UUID, data: MensajeCrear, principal: CurrentPrincipal, service: ConversacionesServiceDep
) -> MensajeGuardadoOut:
    """Idempotente por cliente_id: un reintento devuelve el mensaje existente con repetido=true."""
    return service.guardar_mensaje(principal, conversation_id, data)
