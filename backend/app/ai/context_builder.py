"""Construcción del contexto autorizado para el copiloto.

Reglas:
- Solo lee a través de los servicios existentes, con el Principal de la petición (aislamiento por identidad).
- Los números vienen de los motores; este módulo no calcula nada nuevo.
- Se eliminan identificadores internos, marcas de tiempo y cualquier campo no necesario.
- Limita el volumen: máximo de asignaturas, gastos y tareas enviadas al modelo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.grades import PASSING_GRADE
from app.errors import NotFoundError
from app.security.principal import Principal
from app.services.academic_service import AcademicService
from app.services.budget_service import BudgetService
from app.services.dashboard_service import DashboardService

MAX_ASIGNATURAS = 30
MAX_NOTAS_POR_ASIGNATURA = 40
MAX_GASTOS = 60
MAX_TAREAS_LISTADAS = 10


def _txt(valor: Any) -> str | None:
    """Decimal/fecha/cadena a texto; None se mantiene."""
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return format(valor, "f")
    return str(valor)


@dataclass
class ContextoConstruido:
    datos: dict[str, Any] = field(default_factory=dict)
    usados: list[str] = field(default_factory=list)


class ContextBuilder:
    def __init__(
        self,
        dashboard: DashboardService,
        academic: AcademicService,
        budget: BudgetService | None,
    ) -> None:
        self._dashboard = dashboard
        self._academic = academic
        self._budget = budget

    def build(
        self,
        principal: Principal,
        hoy: date,
        incluir: dict[str, bool],
    ) -> ContextoConstruido:
        panel = self._dashboard.build(principal, hoy.year, hoy.month, hoy)
        salida = ContextoConstruido()

        if incluir.get("academic", False):
            bloque = self._academico(principal, panel.academico)
            salida.datos["academico"] = bloque
            if bloque["total_asignaturas"] > 0:
                salida.usados.append("academic")

        if incluir.get("finance", False):
            bloque = self._finanzas(principal, panel.finanzas)
            salida.datos["finanzas"] = bloque
            if bloque["disponible"] and bloque["tiene_presupuesto"]:
                salida.usados.append("finance")

        if incluir.get("tasks", False):
            bloque = self._tareas(panel.tareas)
            salida.datos["tareas"] = bloque
            if bloque["disponible"] and bloque["total"] > 0:
                salida.usados.append("tasks")

        salida.datos["fuentes"] = {
            "academico": "Servicio académico y motor de calificaciones (promedios, aprobación).",
            "finanzas": "Servicio financiero y motor de presupuesto (importes en COP).",
            "tareas": "Servicio de tareas y motor de prioridades y vencimientos.",
            "ponderacion": "Todas las notas de una asignatura pesan igual.",
        }
        return salida

    # ----- bloques -----------------------------------------------------------
    def _academico(self, principal: Principal, ac) -> dict[str, Any]:
        asignaturas = []
        for resumen in ac.por_asignatura[:MAX_ASIGNATURAS]:
            try:
                detalle = self._academic.get_subject(principal, resumen.id)
                notas = [
                    {"evaluacion": n.descripcion, "nota": _txt(n.nota)}
                    for n in detalle.notas[:MAX_NOTAS_POR_ASIGNATURA]
                ]
            except NotFoundError:
                notas = []
            asignaturas.append({
                "nombre": resumen.nombre,
                "promedio": _txt(resumen.promedio),
                "aprobada": resumen.aprobado,
                "total_notas": resumen.total_notas,
                "notas": notas,
            })
        return {
            "disponible": True,
            "total_asignaturas": ac.total_asignaturas,
            "con_notas": ac.con_notas,
            "aprobadas": ac.aprobadas,
            "reprobadas": ac.reprobadas,
            "promedio_general": _txt(ac.promedio_general),
            "umbral_aprobacion": _txt(PASSING_GRADE),
            "asignaturas": asignaturas,
            "bajo_rendimiento": [a.nombre for a in ac.bajo_rendimiento],
            "sin_datos": ac.total_asignaturas == 0 or ac.con_notas == 0,
        }

    def _finanzas(self, principal: Principal, fi) -> dict[str, Any]:
        bloque: dict[str, Any] = {
            "disponible": fi.disponible,
            "mes": f"{fi.anio:04d}-{fi.mes:02d}",
            "tiene_presupuesto": fi.tiene_presupuesto,
        }
        if not (fi.disponible and fi.tiene_presupuesto):
            return bloque
        gastos: list[dict[str, Any]] = []
        if self._budget is not None:
            try:
                detalle = self._budget.get_budget(principal, fi.anio, fi.mes)
                gastos = [
                    {
                        "descripcion": g.descripcion,
                        "categoria": g.categoria,
                        "monto": _txt(g.monto),
                        "tipo": g.tipo,
                        "fecha": g.fecha.isoformat(),
                    }
                    for g in detalle.gastos[:MAX_GASTOS]
                ]
            except NotFoundError:
                gastos = []
        bloque.update({
            "ingreso": _txt(fi.ingreso),
            "meta_ahorro": _txt(fi.meta_ahorro),
            "gastos_total": _txt(fi.gastos_total),
            "gastos_fijos": _txt(fi.gastos_fijos),
            "gastos_variables": _txt(fi.gastos_variables),
            "saldo": _txt(fi.saldo),
            "ahorro_logrado": _txt(fi.ahorro_logrado),
            "disponible_para_gastar": _txt(fi.disponible_para_gastar),
            "porcentaje_meta_ahorro": _txt(fi.porcentaje_meta_ahorro),
            "meta_cumplida": fi.meta_cumplida,
            "categorias": [
                {"categoria": c.categoria, "total": _txt(c.total), "porcentaje": _txt(c.porcentaje)}
                for c in fi.categorias
            ],
            "gastos": gastos,
            "sin_datos": not gastos,
        })
        return bloque

    def _tareas(self, ta) -> dict[str, Any]:
        bloque: dict[str, Any] = {"disponible": ta.disponible}
        if not ta.disponible:
            return bloque
        pp = ta.pendientes_por_prioridad
        bloque.update({
            "total": ta.total,
            "completadas": ta.completadas,
            "pendientes": ta.pendientes,
            "porcentaje_completadas": _txt(ta.porcentaje),
            "pendientes_por_prioridad": {"alta": pp.alta, "media": pp.media, "baja": pp.baja} if pp else None,
            "vencidas_total": len(ta.vencidas),
            "vencidas": [_tarea(t) for t in ta.vencidas[:MAX_TAREAS_LISTADAS]],
            "proximas_total": ta.proximas_total,
            "proximas": [_tarea(t) for t in ta.proximas[:MAX_TAREAS_LISTADAS]],
            "sin_datos": ta.total == 0,
        })
        return bloque


def _tarea(t) -> dict[str, Any]:
    return {
        "titulo": t.titulo,
        "prioridad": t.prioridad,
        "estado": t.estado,
        "fecha_limite": t.fecha_limite.isoformat() if t.fecha_limite else None,
        "dias_para_vencer": t.dias_para_vencer,
        "vencida": t.vencida,
    }
