"""Cliente HTTP para Supabase PostgREST que propaga el JWT REAL del usuario.

Puntos clave de seguridad:
- Authorization lleva el access_token del usuario, así que PostgreSQL aplica RLS
  con auth.uid() = ese usuario. No se usa service_role ni se hace bypass de RLS.
- apikey es la clave PÚBLICA (publishable). Nunca una clave secreta.
- Sin token de usuario, la petición va como 'anon' y RLS/grants la rechazan.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from app.errors import (
    SupabaseConstraintError,
    SupabaseError,
    SupabasePermissionError,
    SupabaseRejectedTokenError,
    SupabaseUnavailableError,
)

# Códigos SQLSTATE de PostgreSQL que traduce PostgREST en el campo "code".
_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"
_CHECK_VIOLATION = "23514"
_NOT_NULL_VIOLATION = "23502"
_INVALID_TEXT_REPRESENTATION = "22P02"
_NUMERIC_OUT_OF_RANGE = "22003"


class PostgrestClient:
    def __init__(
        self,
        base_url: str,
        publishable_key: str,
        timeout_seconds: float = 8.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/rest/v1",
            timeout=timeout_seconds,
            transport=transport,
        )
        self._publishable_key = publishable_key

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        table: str,
        *,
        access_token: str,
        params: dict[str, str] | None = None,
        json: Any | None = None,
        return_representation: bool = False,
    ) -> list[dict[str, Any]]:
        headers = {
            "apikey": self._publishable_key,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        if return_representation:
            headers["Prefer"] = "return=representation"

        try:
            response = self._client.request(
                method,
                f"/{table}",
                params=params,
                json=json,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise SupabaseUnavailableError("No se pudo contactar Supabase. Intenta de nuevo.") from exc

        return self._interpret(response)

    @staticmethod
    def _interpret(response: httpx.Response) -> list[dict[str, Any]]:
        if response.status_code in (200, 201):
            # parse_float=Decimal: los NUMERIC de PostgreSQL llegan como Decimal exacto, no como float.
            data = response.json(parse_float=Decimal)
            return data if isinstance(data, list) else [data]
        if response.status_code == 204:
            return []

        payload = _safe_json(response)
        code = str(payload.get("code", "")) if isinstance(payload, dict) else ""
        message = str(payload.get("message", "")) if isinstance(payload, dict) else ""

        if response.status_code == 401:
            raise SupabaseRejectedTokenError("La sesión no es válida. Vuelve a iniciar sesión.")
        if response.status_code == 403:
            raise SupabasePermissionError("No tienes permiso para realizar esta operación.")
        # El código SQLSTATE manda sobre el estatus HTTP (PostgREST responde 409 a varias
        # violaciones distintas, así que no basta con mirar el 409).
        if code == _UNIQUE_VIOLATION:
            raise SupabaseConstraintError("Ya existe un registro con esos datos.", 409)
        if code == _FOREIGN_KEY_VIOLATION:
            raise SupabaseConstraintError("La referencia no existe o no es accesible.", 422)
        if code in (_CHECK_VIOLATION, _NOT_NULL_VIOLATION, _NUMERIC_OUT_OF_RANGE, _INVALID_TEXT_REPRESENTATION):
            raise SupabaseConstraintError("Los datos no cumplen las reglas de la base de datos.", 422)
        if response.status_code == 409:
            raise SupabaseConstraintError("Conflicto con el estado actual del registro.", 409)
        if response.status_code in (400, 422):
            raise SupabaseConstraintError(message or "Solicitud no válida.", 422)
        if response.status_code >= 500 or response.status_code == 404:
            # 404 de PostgREST significa tabla o endpoint inexistente: error de configuración.
            raise SupabaseUnavailableError("El servicio de datos no está disponible en este momento.")
        raise SupabaseError("Error inesperado al consultar los datos.")


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json(parse_float=Decimal)
    except ValueError:
        return {}
