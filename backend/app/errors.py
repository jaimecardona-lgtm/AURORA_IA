"""Excepciones de dominio e infraestructura, y su traducción a HTTP.

Mapa de respuestas:
- 401: token ausente/inválido/expirado (Bearer rechazado).
- 403: Supabase deniega el permiso (grants/RLS a nivel de tabla).
- 404: el recurso no existe o no es accesible para este usuario (RLS lo oculta).
- 409: conflicto de unicidad (p. ej. asignatura duplicada).
- 422: datos inválidos (validación de negocio o restricción de base de datos).
- 501: funcionalidad no disponible con el backend de persistencia activo.
- 503: Supabase o el proveedor de identidad no disponibles.
"""

from __future__ import annotations


class DomainError(Exception):
    status_code = 422

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class ValidationFailedError(DomainError):
    status_code = 422


class FeatureNotAvailableError(DomainError):
    """Funcionalidad no implementada para el backend de persistencia activo (501)."""

    status_code = 501


class SupabaseError(Exception):
    status_code = 503

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class SupabaseUnavailableError(SupabaseError):
    status_code = 503


class SupabaseRejectedTokenError(SupabaseError):
    status_code = 401


class SupabasePermissionError(SupabaseError):
    status_code = 403


class SupabaseConstraintError(SupabaseError):
    """Violación de restricción (FK, CHECK, UNIQUE): se mapea a 409 o 422."""

    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.status_code = status_code
