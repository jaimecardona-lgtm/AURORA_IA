"""Panel general: compone los servicios de cada módulo. No contiene reglas nuevas.

- Promedios, aprobación y "bajo rendimiento": motor app.core.grades (is_passing).
- Saldo, ahorro y categorías: motor app.core.budget, vía BudgetService.
- Vencidas, próximas y progreso: motor app.core.tasks, vía TaskService.

Si un módulo no está disponible con la persistencia activa (p. ej. Supabase en esta fase),
se devuelve marcado como `disponible: false` en vez de inventar cifras.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.core.grades import PASSING_GRADE, is_passing
from app.errors import NotFoundError
from app.schemas.dashboard import (
    AcademicoDashboard,
    AsignaturaResumen,
    DashboardOut,
    FinanzasDashboard,
    PrioridadesConteo,
    TareasDashboard,
)
from app.security.principal import Principal
from app.services.academic_service import AcademicService
from app.services.budget_service import BudgetService
from app.services.task_service import TaskService

LIMITE_PROXIMAS = 5
DIAS_PROXIMAS = 7


class DashboardService:
    def __init__(
        self,
        academic: AcademicService,
        budget: BudgetService | None,
        tasks: TaskService | None,
        persistencia: str,
    ) -> None:
        self._academic = academic
        self._budget = budget
        self._tasks = tasks
        self._persistencia = persistencia

    def _academico(self, principal: Principal) -> AcademicoDashboard:
        resumen = self._academic.academic_summary(principal)
        asignaturas = [
            AsignaturaResumen(
                id=s.id, nombre=s.nombre, promedio=s.promedio, aprobado=s.aprobado, total_notas=s.total_notas
            )
            for s in self._academic.list_subjects(principal)
        ]
        bajo = sorted(
            (a for a in asignaturas if a.promedio is not None and not is_passing(a.promedio)),
            key=lambda a: a.promedio,
        )
        return AcademicoDashboard(
            total_asignaturas=resumen.total_asignaturas,
            con_notas=resumen.con_notas,
            aprobadas=resumen.aprobadas,
            reprobadas=resumen.reprobadas,
            promedio_general=resumen.promedio_general,
            por_asignatura=sorted(asignaturas, key=lambda a: a.nombre.lower()),
            bajo_rendimiento=bajo,
            criterio_bajo_rendimiento=f"Promedio menor a {PASSING_GRADE.quantize(Decimal('0.00'))}.",
        )

    def _finanzas(self, principal: Principal, anio: int, mes: int) -> FinanzasDashboard:
        if self._budget is None:
            return FinanzasDashboard(disponible=False, anio=anio, mes=mes)
        try:
            detalle = self._budget.get_budget(principal, anio, mes)
        except NotFoundError:
            return FinanzasDashboard(disponible=True, anio=anio, mes=mes, tiene_presupuesto=False)

        meta = detalle.meta_ahorro
        porcentaje = (
            (detalle.ahorro_logrado * 100 / meta).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if meta > 0
            else None
        )
        return FinanzasDashboard(
            disponible=True,
            anio=anio,
            mes=mes,
            tiene_presupuesto=True,
            ingreso=detalle.ingreso,
            meta_ahorro=meta,
            gastos_total=detalle.gastos_total,
            gastos_fijos=detalle.gastos_fijos,
            gastos_variables=detalle.gastos_variables,
            saldo=detalle.saldo,
            ahorro_logrado=detalle.ahorro_logrado,
            disponible_para_gastar=detalle.disponible_para_gastar,
            porcentaje_meta_ahorro=porcentaje,
            meta_cumplida=detalle.meta_cumplida,
            categorias=detalle.categorias,
        )

    def _tareas(self, principal: Principal, hoy: date) -> TareasDashboard:
        if self._tasks is None:
            return TareasDashboard(disponible=False)
        resumen = self._tasks.summary(principal, hoy, DIAS_PROXIMAS)
        pendientes = self._tasks.list_tasks(principal, hoy, estado="pendiente")
        conteo = Counter(t.prioridad for t in pendientes)
        return TareasDashboard(
            disponible=True,
            total=resumen.total,
            completadas=resumen.completadas,
            pendientes=resumen.pendientes,
            porcentaje=resumen.porcentaje,
            vencidas=resumen.vencidas,
            proximas=resumen.proximas[:LIMITE_PROXIMAS],
            proximas_total=len(resumen.proximas),
            pendientes_por_prioridad=PrioridadesConteo(
                alta=conteo.get("alta", 0), media=conteo.get("media", 0), baja=conteo.get("baja", 0)
            ),
        )

    def build(self, principal: Principal, anio: int, mes: int, hoy: date) -> DashboardOut:
        return DashboardOut(
            persistencia=self._persistencia,  # type: ignore[arg-type]
            generado_el=hoy,
            academico=self._academico(principal),
            finanzas=self._finanzas(principal, anio, mes),
            tareas=self._tareas(principal, hoy),
        )
