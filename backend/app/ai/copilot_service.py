"""Orquestación del copiloto (solo lectura).

Flujo: validación → límites de uso → contexto autorizado (servicios internos) → proveedor → respuesta.
- Nunca ejecuta acciones: el proveedor solo recibe texto y devuelve texto.
- Los límites viven en memoria del proceso (documentado: no son distribuidos).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date

from app.ai.context_builder import ContextBuilder
from app.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT, bloque_datos
from app.ai.provider import AIConfigurationError, AIProvider
from app.errors import DomainError
from app.schemas.copilot import ChatIn, ChatOut, EstadoCopilotoOut, Uso
from app.security.principal import Principal

log = logging.getLogger("aurora.copilot")


class CopilotLimitError(DomainError):
    status_code = 429


@dataclass
class LimitesCopiloto:
    peticiones_por_minuto: int = 10
    tokens_diarios: int = 100_000
    concurrencia: int = 2
    max_tokens_respuesta: int = 700


@dataclass
class Limitador:
    """Control de consumo por usuario. En memoria y por proceso."""

    limites: LimitesCopiloto
    _peticiones: dict[str, deque] = field(default_factory=lambda: defaultdict(deque))
    _tokens: dict[str, tuple[date, int]] = field(default_factory=dict)
    _cerrojo: threading.Lock = field(default_factory=threading.Lock)
    _concurrencia: threading.BoundedSemaphore = field(init=False)

    def __post_init__(self) -> None:
        self._concurrencia = threading.BoundedSemaphore(self.limites.concurrencia)

    def comprobar_peticion(self, usuario: str, ahora: float | None = None) -> None:
        ahora = time.monotonic() if ahora is None else ahora
        with self._cerrojo:
            ventana = self._peticiones[usuario]
            while ventana and ahora - ventana[0] > 60:
                ventana.popleft()
            if len(ventana) >= self.limites.peticiones_por_minuto:
                raise CopilotLimitError("Has enviado demasiadas preguntas seguidas. Espera un minuto.")
            ventana.append(ahora)

    def comprobar_presupuesto(self, usuario: str, hoy: date) -> None:
        with self._cerrojo:
            dia, usados = self._tokens.get(usuario, (hoy, 0))
            if dia != hoy:
                usados = 0
            if usados >= self.limites.tokens_diarios:
                raise CopilotLimitError("Has alcanzado el límite diario de uso del copiloto. Vuelve mañana.")

    def registrar_tokens(self, usuario: str, hoy: date, tokens: int) -> None:
        with self._cerrojo:
            dia, usados = self._tokens.get(usuario, (hoy, 0))
            if dia != hoy:
                usados = 0
            self._tokens[usuario] = (hoy, usados + max(0, tokens))

    def adquirir(self) -> None:
        if not self._concurrencia.acquire(blocking=False):
            raise CopilotLimitError("El copiloto está atendiendo otras consultas. Intenta de nuevo en unos segundos.")

    def liberar(self) -> None:
        self._concurrencia.release()


class CopilotService:
    def __init__(
        self,
        proveedor: AIProvider | None,
        constructor: ContextBuilder,
        limitador: Limitador,
        modo: str,
        persistencia: bool = False,
    ) -> None:
        self._proveedor = proveedor
        self._contexto = constructor
        self._limites = limitador
        self._modo = modo
        self._persistencia = persistencia

    def estado(self) -> EstadoCopilotoOut:
        if self._proveedor is None:
            return EstadoCopilotoOut(
                configurado=False, proveedor="openrouter", modelo=None, simulado=False, modo=self._modo,  # type: ignore[arg-type]
                mensaje="Copiloto pendiente de configuración: falta OPENROUTER_API_KEY u OPENROUTER_MODEL en el servidor.",
                persistencia=self._persistencia,
            )
        simulado = self._proveedor.name == "simulado"
        return EstadoCopilotoOut(
            configurado=True,
            proveedor=self._proveedor.name,  # type: ignore[arg-type]
            modelo=self._proveedor.model,
            simulado=simulado,
            modo=self._modo,  # type: ignore[arg-type]
            persistencia=self._persistencia,
            mensaje=(
                "Respuestas SIMULADAS para desarrollo. No son inteligencia artificial."
                if simulado
                else "Respuestas generadas por OpenRouter a partir de tus datos registrados."
            ),
        )

    def chat(self, principal: Principal, data: ChatIn, hoy: date) -> ChatOut:
        if self._proveedor is None:
            raise AIConfigurationError()
        usuario = principal.user_id
        self._limites.comprobar_peticion(usuario)
        self._limites.comprobar_presupuesto(usuario, hoy)

        incluir = data.include_context.model_dump()
        construido = self._contexto.build(principal, hoy, incluir) if any(incluir.values()) else None
        mensajes: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if construido is not None:
            mensajes.append({"role": "system", "content": bloque_datos(construido.datos)})
        mensajes.extend({"role": m.role, "content": m.content} for m in data.history)
        mensajes.append({"role": "user", "content": data.message})

        self._limites.adquirir()
        try:
            respuesta = self._proveedor.complete(mensajes, self._limites.limites.max_tokens_respuesta)
        finally:
            self._limites.liberar()

        tokens = respuesta.usage.total_tokens or 0
        self._limites.registrar_tokens(usuario, hoy, tokens)
        # Solo métricas técnicas: sin mensajes, sin contexto y sin identificadores.
        log.info("copilot proveedor=%s modelo=%s latencia_ms=%s tokens=%s incompleta=%s",
                 self._proveedor.name, respuesta.model, respuesta.latency_ms, tokens, respuesta.incomplete)
        return ChatOut(
            answer=respuesta.text,
            provider=self._proveedor.name,
            model=respuesta.model,
            simulado=self._proveedor.name == "simulado",
            context_used=construido.usados if construido else [],
            usage=Uso(
                prompt_tokens=respuesta.usage.prompt_tokens,
                completion_tokens=respuesta.usage.completion_tokens,
                total_tokens=respuesta.usage.total_tokens,
            ),
            incomplete=respuesta.incomplete,
            latency_ms=respuesta.latency_ms,
            prompt_version=PROMPT_VERSION,
        )
