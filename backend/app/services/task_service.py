"""Reglas del gestor de tareas. Orden, filtros, vencimientos y progreso salen del motor app.core.tasks.

La UI no vuelve a ordenar ni a calcular vencimientos: consume lo que devuelve esta API.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from app.core.tasks import Task, TaskError, due_summary, filter_tasks, priority_key, progress
from app.errors import NotFoundError, ValidationFailedError
from app.infrastructure.sqlite.repositories import SqliteTaskRepository
from app.schemas.tasks import (
    PRIORIDAD_A_VALOR,
    VALOR_A_PRIORIDAD,
    TaskIn,
    TaskOut,
    TaskSummaryOut,
    TaskUpdate,
)
from app.security.principal import Principal


def _motor(fila: dict[str, Any]) -> Task:
    """Fila de base de datos -> entidad del motor (con su id en `ref`). La base ya valida los datos."""
    return Task(
        title=fila["titulo"],
        priority=int(fila["prioridad"]),
        status=fila["estado"],
        due_date=date.fromisoformat(fila["fecha_limite"]) if fila["fecha_limite"] else None,
        ref=str(fila["id"]),
    )


def _salida(fila: dict[str, Any], hoy: date) -> TaskOut:
    limite = date.fromisoformat(fila["fecha_limite"]) if fila["fecha_limite"] else None
    dias = (limite - hoy).days if limite else None
    prioridad_valor = int(fila["prioridad"])
    return TaskOut(
        id=fila["id"],
        titulo=fila["titulo"],
        prioridad=VALOR_A_PRIORIDAD[prioridad_valor],
        prioridad_valor=prioridad_valor,
        estado=fila["estado"],
        fecha_limite=limite,
        dias_para_vencer=dias,
        vencida=bool(dias is not None and dias < 0 and fila["estado"] == "pendiente"),
        origen=fila.get("origen", "real"),
        created_at=fila["created_at"],
        updated_at=fila["updated_at"],
    )


def _datos_bd(titulo: str, prioridad: str, estado: str, fecha: date | None) -> dict[str, Any]:
    """Valores listos para la base, validados por el motor."""
    try:
        tarea = Task.build(titulo, PRIORIDAD_A_VALOR[prioridad], estado, fecha)
    except TaskError as exc:
        raise ValidationFailedError(str(exc)) from None
    return {
        "titulo": tarea.title,
        "prioridad": tarea.priority,
        "estado": tarea.status,
        "fecha_limite": tarea.due_date.isoformat() if tarea.due_date else None,
    }


class TaskService:
    def __init__(self, repository: SqliteTaskRepository) -> None:
        self._repo = repository

    def _fila_o_404(self, principal: Principal, task_id: UUID) -> dict[str, Any]:
        fila = self._repo.get_task(principal, task_id)
        if fila is None:
            raise NotFoundError("La tarea no existe o no es accesible.")
        return fila

    def list_tasks(
        self,
        principal: Principal,
        hoy: date,
        estado: str | None = None,
        prioridad: str | None = None,
    ) -> list[TaskOut]:
        filas = self._repo.list_tasks(principal)
        prioridad_valor = None
        if prioridad is not None:
            if prioridad not in PRIORIDAD_A_VALOR:
                raise ValidationFailedError("La prioridad debe ser alta, media o baja.")
            prioridad_valor = PRIORIDAD_A_VALOR[prioridad]

        pares = [(fila, _motor(fila)) for fila in filas]
        visibles = {t.ref for t in filter_tasks([t for _, t in pares], status=estado, priority=prioridad_valor)}
        pares = [(f, t) for f, t in pares if t.ref in visibles]
        pares.sort(key=lambda par: priority_key(par[1]))
        return [_salida(f, hoy) for f, _ in pares]

    def create_task(self, principal: Principal, data: TaskIn) -> TaskOut:
        datos = _datos_bd(data.titulo, data.prioridad, data.estado, data.fecha_limite)
        fila = self._repo.create_task(principal, datos)
        return _salida(fila, date.today())

    def update_task(self, principal: Principal, task_id: UUID, data: TaskUpdate) -> TaskOut:
        actual = self._fila_o_404(principal, task_id)
        cambios = data.model_dump(exclude_unset=True)
        if any(v is None for k, v in cambios.items() if k != "fecha_limite"):
            raise ValidationFailedError("Los campos de la tarea no pueden quedar vacíos.")

        titulo = cambios.get("titulo", actual["titulo"])
        prioridad_nombre = cambios.get("prioridad", VALOR_A_PRIORIDAD[int(actual["prioridad"])])
        estado = cambios.get("estado", actual["estado"])
        fecha = cambios["fecha_limite"] if "fecha_limite" in cambios else (
            date.fromisoformat(actual["fecha_limite"]) if actual["fecha_limite"] else None
        )
        normalizado = _datos_bd(titulo, prioridad_nombre, estado, fecha)
        columnas = [c for c in ("titulo", "prioridad", "estado", "fecha_limite") if c in cambios]
        fila = self._repo.update_task(principal, task_id, {c: normalizado[c] for c in columnas})
        if fila is None:
            raise NotFoundError("La tarea no existe o no es accesible.")
        return _salida(fila, date.today())

    def delete_task(self, principal: Principal, task_id: UUID) -> None:
        if not self._repo.delete_task(principal, task_id):
            raise NotFoundError("La tarea no existe o no es accesible.")

    def summary(self, principal: Principal, hoy: date, dias: int = 7) -> TaskSummaryOut:
        filas = self._repo.list_tasks(principal)
        tareas = [_motor(f) for f in filas]
        porcentaje = progress(tareas)
        aviso = due_summary(tareas, hoy, dias)
        por_id = {str(f["id"]): f for f in filas}
        return TaskSummaryOut(
            total=porcentaje.total,
            completadas=porcentaje.completadas,
            pendientes=porcentaje.pendientes,
            porcentaje=porcentaje.porcentaje,
            vencidas=[_salida(por_id[t.ref], hoy) for t in aviso.vencidas],
            proximas=[_salida(por_id[t.ref], hoy) for t in aviso.proximas],
        )
