"""Validación criptográfica de JWT emitidos por Supabase Auth.

Garantías:
- Firma verificada con la clave pública publicada en el JWKS del proyecto.
- Algoritmos asimétricos únicamente (RS256, ES256). Se rechaza HS256 y "none"
  para evitar confusión de algoritmos (usar la clave pública como secreto HMAC).
- Se exigen y comparan: iss, aud, exp, iat, sub.
- Nunca se confía en un user_id enviado en el cuerpo de la petición.

Errores:
- InvalidTokenError (401): token ausente, malformado, firma, expiración, iss/aud, kid desconocido...
- JwksUnavailableError (503): el proveedor no responde o no se puede obtener el JWKS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

ALLOWED_ALGORITHMS = ("RS256", "ES256")
REQUIRED_CLAIMS = ("exp", "iat", "sub", "iss", "aud")

# Devuelve la clave de verificación para un token concreto (se resuelve por 'kid').
KeyResolver = Callable[[str], object]


class InvalidTokenError(Exception):
    """El token no es válido para esta API (se responde 401)."""


class JwksUnavailableError(Exception):
    """No se pudo obtener la clave pública del proveedor de identidad (se responde 503)."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str | None
    role: str | None


def jwks_key_resolver(jwks_url: str, timeout_seconds: float) -> KeyResolver:
    """Crea un resolutor de claves que consulta el JWKS (con caché interna de PyJWT)."""
    client = PyJWKClient(jwks_url, cache_keys=True, lifespan=600, timeout=timeout_seconds)

    def resolve(token: str) -> object:
        try:
            return client.get_signing_key_from_jwt(token).key
        except PyJWKClientConnectionError as exc:
            raise JwksUnavailableError("No se pudo contactar el proveedor de identidad.") from exc
        except PyJWKClientError as exc:
            # kid desconocido, JWKS sin claves utilizables o token sin 'kid'.
            raise InvalidTokenError("No se encontró una clave de firma válida para el token.") from exc
        except jwt.DecodeError as exc:
            raise InvalidTokenError("Token malformado.") from exc

    return resolve


class SupabaseJwtVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        resolve_key: KeyResolver,
        leeway_seconds: int = 10,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._resolve_key = resolve_key
        self._leeway = leeway_seconds

    def verify(self, token: str) -> AuthenticatedUser:
        if not token or not token.strip():
            raise InvalidTokenError("Token vacío.")

        key = self._resolve_key(token)

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": list(REQUIRED_CLAIMS)},
            )
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("El token ha expirado.") from exc
        except jwt.InvalidAudienceError as exc:
            raise InvalidTokenError("Audiencia del token no válida.") from exc
        except jwt.InvalidIssuerError as exc:
            raise InvalidTokenError("Emisor del token no válido.") from exc
        except jwt.MissingRequiredClaimError as exc:
            raise InvalidTokenError(f"Falta el claim obligatorio: {exc.claim}.") from exc
        except jwt.PyJWTError as exc:
            # Firma inválida, algoritmo no permitido, token malformado, etc.
            raise InvalidTokenError("Token no válido.") from exc

        try:
            user_id = UUID(str(claims["sub"]))
        except ValueError as exc:
            raise InvalidTokenError("El claim 'sub' no es un UUID válido.") from exc

        email = claims.get("email")
        role = claims.get("role")
        return AuthenticatedUser(
            id=user_id,
            email=email if isinstance(email, str) else None,
            role=role if isinstance(role, str) else None,
        )
