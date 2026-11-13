"""Endpoints del gestor de tareas (solo SQLite en esta fase)."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentPrincipal, TaskServiceDep
from app.schemas.tasks import TaskIn, TaskOut, TaskSummaryOut, TaskUpdate

router = APIRouter(prefix="/api/tareas", tags=["tareas"])


@router.get("", response_model=list[TaskOut])
def listar_tareas(
    principal: CurrentPrincipal,
    service: TaskServiceDep,
    estado: Literal["pendiente", "completada"] | None = Query(default=None),
    prioridad: Literal["alta", "media", "baja"] | None = Query(default=None),
) -> list[TaskOut]:
    """Ordenadas por el motor: pendientes primero, luego prioridad alta a baja."""
    return service.list_tasks(principal, date.today(), estado=estado, prioridad=prioridad)


@router.get("/resumen", response_model=TaskSummaryOut)
def resumen_tareas(
    principal: CurrentPrincipal,
    service: TaskServiceDep,
    dias: int = Query(default=7, ge=0, le=60, description="Ventana para 'próximas a vencer'."),
) -> TaskSummaryOut:
    return service.summary(principal, date.today(), dias)


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def crear_tarea(data: TaskIn, principal: CurrentPrincipal, service: TaskServiceDep) -> TaskOut:
    return service.create_task(principal, data)


@router.patch("/{task_id}", response_model=TaskOut)
def actualizar_tarea(task_id: UUID, data: TaskUpdate, principal: CurrentPrincipal, service: TaskServiceDep) -> TaskOut:
    return service.update_task(principal, task_id, data)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def eliminar_tarea(task_id: UUID, principal: CurrentPrincipal, service: TaskServiceDep) -> Response:
    service.delete_task(principal, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
