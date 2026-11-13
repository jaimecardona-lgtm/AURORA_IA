"""Motor de priorización de tareas.

Prioridad: 1 = alta, 2 = media, 3 = baja (decisión documentada en docs/FASE_01_IMPLEMENTACION.md).
Estado: "pendiente" o "completada".

Orden de priorización: pendientes primero, luego prioridad ascendente (1 antes que 3),
y finalmente título para un orden estable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

PRIORITIES = (1, 2, 3)
STATUSES = ("pendiente", "completada")


class TaskError(ValueError):
    """Tarea no válida."""


@dataclass(frozen=True)
class Task:
    title: str
    priority: int
    status: str = "pendiente"
    due_date: date | None = None
    ref: str = ""  # identificador externo (p. ej. id de base de datos); no afecta al orden

    @classmethod
    def build(
        cls,
        title: str,
        priority: object,
        status: str = "pendiente",
        due_date: object = None,
    ) -> "Task":
        clean_title = str(title or "").strip()
        if not clean_title:
            raise TaskError("El título es obligatorio.")
        if isinstance(priority, bool) or not isinstance(priority, int):
            try:
                priority_int = int(str(priority).strip())
            except ValueError:
                raise TaskError("La prioridad debe ser 1, 2 o 3.") from None
        else:
            priority_int = priority
        if priority_int not in PRIORITIES:
            raise TaskError("La prioridad debe ser 1, 2 o 3.")
        if status not in STATUSES:
            raise TaskError("El estado debe ser 'pendiente' o 'completada'.")
        return cls(clean_title, priority_int, status, _fecha_limite(due_date))


def _fecha_limite(value: object) -> date | None:
    """Acepta None, un date o una cadena ISO 'AAAA-MM-DD'."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise TaskError("La fecha límite debe tener formato AAAA-MM-DD.") from None


def priority_key(task: Task) -> tuple[bool, int, str]:
    """Clave de orden única: pendientes primero, luego prioridad ascendente y título."""
    return (task.status != "pendiente", task.priority, task.title.lower())


def prioritize(tasks: Iterable[Task]) -> list[Task]:
    """Devuelve las tareas ordenadas: pendientes primero, por prioridad y título."""
    return sorted(tasks, key=priority_key)



def filter_tasks(
    tasks: Iterable[Task],
    status: str | None = None,
    priority: int | None = None,
) -> list[Task]:
    """Filtra por estado y/o prioridad. Un valor None no filtra."""
    if status is not None and status not in STATUSES:
        raise TaskError("El estado debe ser 'pendiente' o 'completada'.")
    if priority is not None and priority not in PRIORITIES:
        raise TaskError("La prioridad debe ser 1, 2 o 3.")
    return [
        t
        for t in tasks
        if (status is None or t.status == status)
        and (priority is None or t.priority == priority)
    ]


@dataclass(frozen=True)
class DueSummary:
    vencidas: list[Task]
    proximas: list[Task]


def due_summary(tasks: Iterable[Task], today: date, days: int = 7) -> DueSummary:
    """Tareas PENDIENTES con fecha límite vencida o dentro de los próximos `days` días.

    Las completadas nunca aparecen: ya no requieren atención.
    """
    if days < 0:
        raise TaskError("El rango de días no puede ser negativo.")
    limite = today + timedelta(days=days)
    vencidas: list[Task] = []
    proximas: list[Task] = []
    for t in prioritize(tasks):
        if t.status != "pendiente" or t.due_date is None:
            continue
        if t.due_date < today:
            vencidas.append(t)
        elif t.due_date <= limite:
            proximas.append(t)
    proximas.sort(key=lambda t: (t.due_date, t.priority, t.title.lower()))
    vencidas.sort(key=lambda t: (t.due_date, t.priority, t.title.lower()))
    return DueSummary(vencidas=vencidas, proximas=proximas)


@dataclass(frozen=True)
class Progress:
    total: int
    completadas: int
    pendientes: int
    porcentaje: Decimal  # 0.00 a 100.00


def progress(tasks: Iterable[Task]) -> Progress:
    lista = list(tasks)
    total = len(lista)
    completadas = sum(1 for t in lista if t.status == "completada")
    porcentaje = (
        (Decimal(completadas) * 100 / Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total
        else Decimal("0.00")
    )
    return Progress(total, completadas, total - completadas, porcentaje)
