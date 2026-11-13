"""Interfaz desacoplada de proveedores de IA y su jerarquía de errores.

El copiloto depende solo de `AIProvider`. Implementaciones: OpenRouterProvider (real) y
SimulatedProvider (solo desarrollo, etiquetado como SIMULADO en la respuesta).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    model: str
    usage: Usage
    latency_ms: int
    incomplete: bool  # True si el modelo se cortó por límite de tokens


class AIProvider(Protocol):
    name: str
    model: str

    def complete(self, messages: list[dict[str, str]], max_tokens: int) -> ProviderResponse: ...


class AIProviderError(Exception):
    """Error al hablar con el proveedor. `status_code` es el que devuelve el copiloto."""

    status_code = 502
    code = "proveedor_error"
    message = "El proveedor de IA devolvió un error."

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.message)
        self.detail = detail or self.message


class AIConfigurationError(AIProviderError):
    status_code = 503
    code = "no_configurado"
    message = "El copiloto no está configurado en el servidor."


class ProviderAuthError(AIProviderError):
    status_code = 503  # la clave del servidor no es válida: no es culpa del usuario
    code = "clave_invalida"
    message = "La clave de OpenRouter no es válida. Revisa OPENROUTER_API_KEY en el servidor."


class ProviderPaymentError(AIProviderError):
    status_code = 503
    code = "sin_credito"
    message = "OpenRouter rechazó la petición por falta de crédito o de presupuesto."


class ProviderRateLimitError(AIProviderError):
    status_code = 429
    code = "limite_proveedor"
    message = "El proveedor de IA está limitando las peticiones. Intenta de nuevo en unos segundos."


class ProviderUnavailableError(AIProviderError):
    status_code = 503
    code = "proveedor_no_disponible"
    message = "El proveedor de IA no responde en este momento. Intenta de nuevo más tarde."


class ProviderTimeoutError(AIProviderError):
    status_code = 504
    code = "tiempo_agotado"
    message = "El proveedor de IA tardó demasiado en responder. Reintenta."


class ProviderMalformedError(AIProviderError):
    status_code = 502
    code = "respuesta_invalida"
    message = "El proveedor devolvió una respuesta que no se pudo interpretar."
