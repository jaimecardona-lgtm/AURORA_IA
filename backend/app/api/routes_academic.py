"""Endpoints REST de asignaturas, notas y cálculos académicos."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AcademicServiceDep, CurrentPrincipal
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

router = APIRouter(prefix="/api", tags=["académico"])


@router.get("/subjects", response_model=list[SubjectOut])
def listar_asignaturas(principal: CurrentPrincipal, service: AcademicServiceDep) -> list[SubjectOut]:
    return service.list_subjects(principal)


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def crear_asignatura(data: SubjectCreate, principal: CurrentPrincipal, service: AcademicServiceDep) -> SubjectOut:
    return service.create_subject(principal, data)


@router.get("/subjects/{subject_id}", response_model=SubjectDetail)
def obtener_asignatura(subject_id: UUID, principal: CurrentPrincipal, service: AcademicServiceDep) -> SubjectDetail:
    return service.get_subject(principal, subject_id)


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
def actualizar_asignatura(
    subject_id: UUID, data: SubjectUpdate, principal: CurrentPrincipal, service: AcademicServiceDep
) -> SubjectOut:
    return service.update_subject(principal, subject_id, data)


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def eliminar_asignatura(subject_id: UUID, principal: CurrentPrincipal, service: AcademicServiceDep) -> Response:
    service.delete_subject(principal, subject_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/subjects/{subject_id}/grades", response_model=list[GradeOut])
def listar_notas(subject_id: UUID, principal: CurrentPrincipal, service: AcademicServiceDep) -> list[GradeOut]:
    return service.list_grades(principal, subject_id)


@router.post("/subjects/{subject_id}/grades", response_model=GradeOut, status_code=status.HTTP_201_CREATED)
def agregar_nota(
    subject_id: UUID, data: GradeCreate, principal: CurrentPrincipal, service: AcademicServiceDep
) -> GradeOut:
    return service.add_grade(principal, subject_id, data)


@router.get("/grades/{grade_id}", response_model=GradeOut)
def obtener_nota(grade_id: UUID, principal: CurrentPrincipal, service: AcademicServiceDep) -> GradeOut:
    return service.get_grade(principal, grade_id)


@router.patch("/grades/{grade_id}", response_model=GradeOut)
def actualizar_nota(grade_id: UUID, data: GradeUpdate, principal: CurrentPrincipal, service: AcademicServiceDep) -> GradeOut:
    return service.update_grade(principal, grade_id, data)


@router.delete("/grades/{grade_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def eliminar_nota(grade_id: UUID, principal: CurrentPrincipal, service: AcademicServiceDep) -> Response:
    service.delete_grade(principal, grade_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/subjects/{subject_id}/objetivo", response_model=RequiredGradeOut)
def nota_necesaria(
    subject_id: UUID,
    principal: CurrentPrincipal,
    service: AcademicServiceDep,
    objetivo: Decimal = Query(ge=0, le=5, description="Promedio que quieres alcanzar (0 a 5)."),
) -> RequiredGradeOut:
    return service.required_for_target(principal, subject_id, objetivo)


@router.get("/academico/resumen", response_model=AcademicSummaryOut)
def resumen_academico(principal: CurrentPrincipal, service: AcademicServiceDep) -> AcademicSummaryOut:
    return service.academic_summary(principal)
