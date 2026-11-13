"""Reglas de la capa académica: promedios con el motor Python y CRUD con 404 coherente.

El servicio no conoce HTTP ni SQL: recibe el token del usuario y delega en el repositorio.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.grades import average, is_passing, parse_grade, required_grade, summarize_subjects
from app.errors import NotFoundError
from app.security.principal import Principal
from app.repositories.academic_repository import AcademicRepository
from app.schemas.academic import (
    AcademicSummaryOut,
    GradeCreate,
    GradeOut,
    GradeUpdate,
    RequiredGradeOut,
    SubjectCreate,
    SubjectDetail,
    SubjectOut,
    SubjectUpdate,
)


def _to_float(value: Decimal) -> float:
    # PostgREST recibe el número en JSON; numeric(4,2) redondea a dos decimales.
    return float(value)


class AcademicService:
    def __init__(self, repository: AcademicRepository) -> None:
        self._repo = repository

    # ----- helpers ---------------------------------------------------------
    @staticmethod
    def _resumen(subject: dict[str, Any], notas: list[Decimal]) -> SubjectOut:
        promedio = average(notas) if notas else None
        return SubjectOut(
            id=subject["id"],
            nombre=subject["nombre"],
            origen=subject.get("origen", "real"),
            created_at=subject["created_at"],
            updated_at=subject["updated_at"],
            total_notas=len(notas),
            promedio=promedio,
            aprobado=is_passing(promedio) if promedio is not None else None,
        )

    def _asignatura_o_404(self, principal: Principal, subject_id: UUID) -> dict[str, Any]:
        subject = self._repo.get_subject(principal, subject_id)
        if subject is None:
            raise NotFoundError("La asignatura no existe o no es accesible.")
        return subject

    # ----- asignaturas -----------------------------------------------------
    def list_subjects(self, principal: Principal) -> list[SubjectOut]:
        subjects = self._repo.list_subjects(principal)
        grades = self._repo.list_grades(principal)
        notas_por_asignatura: dict[str, list[Decimal]] = {}
        for grade in grades:
            notas_por_asignatura.setdefault(str(grade["subject_id"]), []).append(parse_grade(grade["nota"]))
        return [self._resumen(s, notas_por_asignatura.get(str(s["id"]), [])) for s in subjects]

    def create_subject(self, principal: Principal, data: SubjectCreate) -> SubjectOut:
        subject = self._repo.create_subject(principal, data.nombre)
        return self._resumen(subject, [])

    def get_subject(self, principal: Principal, subject_id: UUID) -> SubjectDetail:
        subject = self._asignatura_o_404(principal, subject_id)
        notas_rows = self._repo.list_grades(principal, subject_id)
        notas = [GradeOut.from_row(row) for row in notas_rows]
        resumen = self._resumen(subject, [g.nota for g in notas])
        return SubjectDetail(**resumen.model_dump(), notas=notas)

    def update_subject(self, principal: Principal, subject_id: UUID, data: SubjectUpdate) -> SubjectOut:
        self._asignatura_o_404(principal, subject_id)
        changes = data.model_dump(exclude_unset=True)
        updated = self._repo.update_subject(principal, subject_id, changes)
        if updated is None:
            raise NotFoundError("La asignatura no existe o no es accesible.")
        notas = [parse_grade(g["nota"]) for g in self._repo.list_grades(principal, subject_id)]
        return self._resumen(updated, notas)

    def delete_subject(self, principal: Principal, subject_id: UUID) -> None:
        if not self._repo.delete_subject(principal, subject_id):
            raise NotFoundError("La asignatura no existe o no es accesible.")

    # ----- notas -----------------------------------------------------------
    def list_grades(self, principal: Principal, subject_id: UUID) -> list[GradeOut]:
        self._asignatura_o_404(principal, subject_id)
        return [GradeOut.from_row(row) for row in self._repo.list_grades(principal, subject_id)]

    def add_grade(self, principal: Principal, subject_id: UUID, data: GradeCreate) -> GradeOut:
        self._asignatura_o_404(principal, subject_id)
        row = self._repo.create_grade(principal, subject_id, data.descripcion, _to_float(data.nota))
        return GradeOut.from_row(row)

    def get_grade(self, principal: Principal, grade_id: UUID) -> GradeOut:
        row = self._repo.get_grade(principal, grade_id)
        if row is None:
            raise NotFoundError("La nota no existe o no es accesible.")
        return GradeOut.from_row(row)

    def update_grade(self, principal: Principal, grade_id: UUID, data: GradeUpdate) -> GradeOut:
        self.get_grade(principal, grade_id)
        changes = data.model_dump(exclude_unset=True)
        if "nota" in changes and changes["nota"] is not None:
            changes["nota"] = _to_float(changes["nota"])
        row = self._repo.update_grade(principal, grade_id, changes)
        if row is None:
            raise NotFoundError("La nota no existe o no es accesible.")
        return GradeOut.from_row(row)

    def delete_grade(self, principal: Principal, grade_id: UUID) -> None:
        if not self._repo.delete_grade(principal, grade_id):
            raise NotFoundError("La nota no existe o no es accesible.")

    # ----- cálculos (motor Python: la UI no repite estas reglas) -------------
    def required_for_target(self, principal: Principal, subject_id: UUID, objetivo: object) -> RequiredGradeOut:
        self._asignatura_o_404(principal, subject_id)
        notas = [parse_grade(g["nota"]) for g in self._repo.list_grades(principal, subject_id)]
        resultado = required_grade(notas, objetivo)
        return RequiredGradeOut(
            objetivo=resultado.target,
            posible=resultado.possible,
            nota_minima=resultado.minimum,
            mensaje=resultado.message,
        )

    def academic_summary(self, principal: Principal) -> AcademicSummaryOut:
        subjects = self.list_subjects(principal)
        resumen = summarize_subjects(s.promedio for s in subjects)
        return AcademicSummaryOut(
            total_asignaturas=resumen.total_asignaturas,
            con_notas=resumen.con_notas,
            aprobadas=resumen.aprobadas,
            reprobadas=resumen.reprobadas,
            promedio_general=resumen.promedio_general,
        )
