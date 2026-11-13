"""Acceso a datos de asignaturas y notas vía PostgREST con el JWT del usuario.

Este módulo solo habla HTTP/PostgREST. No contiene reglas de negocio ni SQL libre:
las restricciones viven en la base de datos (migración 20261111120000).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.repositories.postgrest_client import PostgrestClient
from app.security.principal import Principal

SUBJECTS = "academic_subjects"
GRADES = "grade_entries"


class AcademicRepository:
    def __init__(self, client: PostgrestClient) -> None:
        self._client = client

    # ----- asignaturas -----------------------------------------------------
    def list_subjects(self, principal: Principal) -> list[dict[str, Any]]:
        return self._client.request(
            "GET", SUBJECTS, access_token=principal.access_token or "",
            params={"select": "*", "order": "nombre.asc"},
        )

    def get_subject(self, principal: Principal, subject_id: UUID) -> dict[str, Any] | None:
        rows = self._client.request(
            "GET", SUBJECTS, access_token=principal.access_token or "",
            params={"select": "*", "id": f"eq.{subject_id}", "limit": "1"},
        )
        return rows[0] if rows else None

    def create_subject(self, principal: Principal, nombre: str) -> dict[str, Any]:
        rows = self._client.request(
            "POST", SUBJECTS, access_token=principal.access_token or "",
            json={"nombre": nombre}, return_representation=True,
        )
        return rows[0]

    def update_subject(self, principal: Principal, subject_id: UUID, changes: dict[str, Any]) -> dict[str, Any] | None:
        rows = self._client.request(
            "PATCH", SUBJECTS, access_token=principal.access_token or "",
            params={"id": f"eq.{subject_id}"}, json=changes, return_representation=True,
        )
        return rows[0] if rows else None

    def delete_subject(self, principal: Principal, subject_id: UUID) -> bool:
        rows = self._client.request(
            "DELETE", SUBJECTS, access_token=principal.access_token or "",
            params={"id": f"eq.{subject_id}"}, return_representation=True,
        )
        return bool(rows)

    # ----- notas -----------------------------------------------------------
    def list_grades(self, principal: Principal, subject_id: UUID | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if subject_id is not None:
            params["subject_id"] = f"eq.{subject_id}"
        return self._client.request("GET", GRADES, access_token=principal.access_token or "", params=params)

    def get_grade(self, principal: Principal, grade_id: UUID) -> dict[str, Any] | None:
        rows = self._client.request(
            "GET", GRADES, access_token=principal.access_token or "",
            params={"select": "*", "id": f"eq.{grade_id}", "limit": "1"},
        )
        return rows[0] if rows else None

    def create_grade(self, principal: Principal, subject_id: UUID, descripcion: str, nota: float) -> dict[str, Any]:
        rows = self._client.request(
            "POST", GRADES, access_token=principal.access_token or "",
            json={"subject_id": str(subject_id), "descripcion": descripcion, "nota": nota},
            return_representation=True,
        )
        return rows[0]

    def update_grade(self, principal: Principal, grade_id: UUID, changes: dict[str, Any]) -> dict[str, Any] | None:
        rows = self._client.request(
            "PATCH", GRADES, access_token=principal.access_token or "",
            params={"id": f"eq.{grade_id}"}, json=changes, return_representation=True,
        )
        return rows[0] if rows else None

    def delete_grade(self, principal: Principal, grade_id: UUID) -> bool:
        rows = self._client.request(
            "DELETE", GRADES, access_token=principal.access_token or "",
            params={"id": f"eq.{grade_id}"}, return_representation=True,
        )
        return bool(rows)
