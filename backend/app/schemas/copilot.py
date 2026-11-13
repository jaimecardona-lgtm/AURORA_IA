"""Contratos del copiloto. extra="forbid": el navegador no puede enviar user_id ni datos académicos."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)

MAX_MENSAJE = 1000
MAX_TURNOS_HISTORIAL = 6
MAX_CARACTERES_HISTORIAL = 4000


class MensajeHistorial(BaseModel):
    model_config = _STRICT
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=MAX_MENSAJE)]


class IncluirContexto(BaseModel):
    model_config = _STRICT
    academic: bool = True
    finance: bool = True
    tasks: bool = True


class ChatIn(BaseModel):
    model_config = _STRICT
    message: Annotated[str, Field(min_length=1, max_length=MAX_MENSAJE)]
    history: list[MensajeHistorial] = Field(default_factory=list, max_length=MAX_TURNOS_HISTORIAL)
    include_context: IncluirContexto = Field(default_factory=IncluirContexto)

    @field_validator("history")
    @classmethod
    def _historial_acotado(cls, valor: list[MensajeHistorial]) -> list[MensajeHistorial]:
        total = sum(len(m.content) for m in valor)
        if total > MAX_CARACTERES_HISTORIAL:
            raise ValueError(f"El historial no puede superar {MAX_CARACTERES_HISTORIAL} caracteres.")
        return valor


class Uso(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatOut(BaseModel):
    answer: str
    provider: str
    model: str
    simulado: bool
    context_used: list[str]
    usage: Uso
    incomplete: bool
    latency_ms: int
    prompt_version: str


class EstadoCopilotoOut(BaseModel):
    configurado: bool
    proveedor: Literal["openrouter", "simulado"]
    modelo: str | None
    simulado: bool
    modo: Literal["demo", "produccion"]
    max_mensaje: int = MAX_MENSAJE
    max_turnos_historial: int = MAX_TURNOS_HISTORIAL
    mensaje: str
    # true solo si la migración está aplicada y el backend tiene PERSISTENCIA activada.
    persistencia: bool = False
