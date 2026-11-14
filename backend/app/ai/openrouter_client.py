"""Cliente HTTP de OpenRouter (API oficial, chat completions, sin streaming).

Endpoint: https://openrouter.ai/api/v1/chat/completions · Auth: `Authorization: Bearer <clave>`.

Seguridad y privacidad:
- La clave se lee solo del servidor (SecretStr) y no aparece en logs, errores ni respuestas.
- No se registra el contenido de los mensajes ni el cuerpo de las respuestas.
- Solo se registran métricas técnicas: estado HTTP, latencia y tokens.
"""

from __future__ import annotations

import logging
import time

import httpx

from app.ai.provider import (
    ProviderMalformedError,
    ProviderAuthError,
    ProviderPaymentError,
    ProviderRateLimitError,
    ProviderResponse,
    ProviderTimeoutError,
    ProviderUnavailableError,
    Usage,
)

log = logging.getLogger("aurora.copilot")

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
TITULO_APP = "AURORA AI"


class OpenRouterProvider:
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
        endpoint: str = ENDPOINT,
        fallback_models: list[str] | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        # No automatizar cambios a modelos de pago: sólo fallbacks configurados explícitamente.
        self._fallback_models = list(fallback_models or [])
        self._endpoint = endpoint
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    def complete(self, messages: list[dict[str, str]], max_tokens: int) -> ProviderResponse:
        cuerpo = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        if self._fallback_models:
            # OpenRouter intenta los modelos en orden en una sola petición HTTP.
            cuerpo["models"] = [self.model, *self._fallback_models]
        cabeceras = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": TITULO_APP,
        }
        inicio = time.perf_counter()
        try:
            respuesta = self._client.post(self._endpoint, json=cuerpo, headers=cabeceras)
        except httpx.TimeoutException:
            self._registrar(None, inicio)
            raise ProviderTimeoutError() from None
        except httpx.HTTPError:
            self._registrar(None, inicio)
            raise ProviderUnavailableError() from None

        latencia = self._registrar(respuesta.status_code, inicio)
        estado = respuesta.status_code
        if estado == 401:
            raise ProviderAuthError()
        if estado == 402:
            raise ProviderPaymentError()
        if estado == 429:
            raise ProviderRateLimitError()
        if estado >= 500:
            raise ProviderUnavailableError()
        if estado >= 400:
            raise ProviderMalformedError("OpenRouter rechazó la petición.")

        return self._interpretar(respuesta, latencia)

    def _interpretar(self, respuesta: httpx.Response, latencia: int) -> ProviderResponse:
        try:
            datos = respuesta.json()
            eleccion = datos["choices"][0]
            texto = eleccion["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderMalformedError() from None
        if not isinstance(texto, str) or not texto.strip():
            raise ProviderMalformedError()

        uso = datos.get("usage") or {}
        usage = Usage(
            prompt_tokens=_entero(uso.get("prompt_tokens")),
            completion_tokens=_entero(uso.get("completion_tokens")),
            total_tokens=_entero(uso.get("total_tokens")),
        )
        self._registrar_tokens(usage, datos.get("model"))
        return ProviderResponse(
            text=texto.strip(),
            model=str(datos.get("model") or self.model),
            usage=usage,
            latency_ms=latencia,
            incomplete=eleccion.get("finish_reason") == "length",
        )

    def _registrar(self, estado: int | None, inicio: float) -> int:
        latencia = int((time.perf_counter() - inicio) * 1000)
        log.info("openrouter estado=%s latencia_ms=%s", estado, latencia)
        return latencia

    def _registrar_tokens(self, usage: Usage, modelo: object) -> None:
        log.info("openrouter tokens total=%s modelo=%s", usage.total_tokens, modelo)

    def close(self) -> None:
        self._client.close()


def _entero(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None
