"""Contratos de las conversaciones persistidas del copiloto (Fase 08A).

- extra="forbid": el navegador no puede enviar user_id, created_at ni otros campos de identidad o tiempo.
- La identidad real siempre viene del JWT validado (Principal); la base la asigna con auth.uid().
- Los mensajes llevan cliente_id (UUID generado por la interfaz) para evitar duplicados al reintentar.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TITULO_MAX = 120
CONTENIDO_MAX = 8000
TITULO_POR_DEFECTO = "Nueva conversación"
LIMITE_PAGINA_MAX = 100
AREAS = ("academic", "finance", "tasks")

Titulo = Annotated[str, Field(min_length=1, max_length=TITULO_MAX)]


class ConversacionCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Titulo | None = None


class ConversacionTitulo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Titulo


class ConversacionOut(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversacionesPagina(BaseModel):
    items: list[ConversacionOut]
    # Desplazamiento de la siguiente página, o null si no hay más.
    siguiente: int | None = None


class MensajeCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cliente_id: UUID
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=CONTENIDO_MAX)]
    estado: Literal["completado", "incompleto"] = "completado"
    proveedor: Annotated[str | None, Field(max_length=30)] = None
    modelo: Annotated[str | None, Field(max_length=120)] = None
    simulado: bool | None = None
    contexto_usado: Annotated[list[Literal["academic", "finance", "tasks"]], Field(max_length=3)] = Field(default_factory=list)
    total_tokens: Annotated[int | None, Field(ge=0)] = None


class MensajeOut(BaseModel):
    id: UUID
    cliente_id: UUID
    role: Literal["user", "assistant"]
    content: str
    estado: Literal["completado", "incompleto"]
    proveedor: str | None
    modelo: str | None
    simulado: bool | None
    contexto_usado: list[str]
    total_tokens: int | None
    created_at: datetime


class MensajeGuardadoOut(BaseModel):
    mensaje: MensajeOut
    # true si el mismo cliente_id ya existía: no se creó nada nuevo (reintento seguro).
    repetido: bool


class MensajesPagina(BaseModel):
    items: list[MensajeOut]
    siguiente: int | None = None
