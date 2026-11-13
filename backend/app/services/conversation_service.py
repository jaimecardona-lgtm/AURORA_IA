"""Servicio de conversaciones persistidas del copiloto (Fase 08A).

Reglas:
- Antes de leer o escribir mensajes se comprueba que la conversación existe para este usuario
  (RLS la oculta si es ajena, y entonces se responde 404).
- Guardar un mensaje es idempotente por cliente_id: un reintento no crea otra fila.
  Si el mismo cliente_id llega con otro contenido, se rechaza (409), nunca se sobrescribe.
- Borrar exige confirmación explícita (confirmar=true).
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.errors import ConflictError, NotFoundError, SupabaseConstraintError, ValidationFailedError
from app.schemas.conversaciones import (
    LIMITE_PAGINA_MAX,
    TITULO_MAX,
    TITULO_POR_DEFECTO,
    ConversacionesPagina,
    ConversacionOut,
    MensajeCrear,
    MensajeGuardadoOut,
    MensajeOut,
    MensajesPagina,
)
from app.security.principal import Principal


class ConversationRepositoryPort(Protocol):
    def list_conversations(self, principal: Principal, limit: int, offset: int) -> list[dict[str, Any]]: ...
    def get_conversation(self, principal: Principal, conversation_id: UUID) -> dict[str, Any] | None: ...
    def create_conversation(self, principal: Principal, title: str) -> dict[str, Any]: ...
    def update_title(self, principal: Principal, conversation_id: UUID, title: str) -> dict[str, Any] | None: ...
    def delete_conversation(self, principal: Principal, conversation_id: UUID) -> bool: ...
    def list_messages(self, principal: Principal, conversation_id: UUID, limit: int, offset: int) -> list[dict[str, Any]]: ...
    def find_message_by_client(self, principal: Principal, conversation_id: UUID, cliente_id: UUID) -> dict[str, Any] | None: ...
    def insert_message(self, principal: Principal, conversation_id: UUID, datos: dict[str, Any]) -> dict[str, Any]: ...


def normalizar_titulo(texto: str | None) -> str:
    """Quita espacios sobrantes y recorta. Sin texto útil, devuelve el título por defecto."""
    limpio = " ".join((texto or "").split())
    if not limpio:
        return TITULO_POR_DEFECTO
    return limpio[:TITULO_MAX]


def _paginar(limit: int, offset: int) -> tuple[int, int]:
    if not 1 <= limit <= LIMITE_PAGINA_MAX:
        raise ValidationFailedError(f"El tamaño de página debe estar entre 1 y {LIMITE_PAGINA_MAX}.")
    if offset < 0:
        raise ValidationFailedError("El desplazamiento no puede ser negativo.")
    return limit, offset


def _mensaje_out(fila: dict[str, Any]) -> MensajeOut:
    return MensajeOut.model_validate(fila)


class ConversationService:
    def __init__(self, repo: ConversationRepositoryPort) -> None:
        self._repo = repo

    # ----- conversaciones ----------------------------------------------------
    def listar(self, principal: Principal, limit: int, offset: int) -> ConversacionesPagina:
        limit, offset = _paginar(limit, offset)
        filas = self._repo.list_conversations(principal, limit, offset)
        hay_mas = len(filas) > limit
        items = [ConversacionOut.model_validate(f) for f in filas[:limit]]
        return ConversacionesPagina(items=items, siguiente=offset + limit if hay_mas else None)

    def crear(self, principal: Principal, title: str | None) -> ConversacionOut:
        fila = self._repo.create_conversation(principal, normalizar_titulo(title))
        return ConversacionOut.model_validate(fila)

    def obtener(self, principal: Principal, conversation_id: UUID) -> ConversacionOut:
        return ConversacionOut.model_validate(self._exigir(principal, conversation_id))

    def renombrar(self, principal: Principal, conversation_id: UUID, title: str) -> ConversacionOut:
        self._exigir(principal, conversation_id)
        fila = self._repo.update_title(principal, conversation_id, normalizar_titulo(title))
        if fila is None:
            raise NotFoundError("La conversación no existe o no es accesible.")
        return ConversacionOut.model_validate(fila)

    def eliminar(self, principal: Principal, conversation_id: UUID, confirmar: bool) -> None:
        if not confirmar:
            raise ValidationFailedError("Para eliminar la conversación confirma la acción con confirmar=true.")
        if not self._repo.delete_conversation(principal, conversation_id):
            raise NotFoundError("La conversación no existe o no es accesible.")

    # ----- mensajes ----------------------------------------------------------
    def mensajes(self, principal: Principal, conversation_id: UUID, limit: int, offset: int) -> MensajesPagina:
        self._exigir(principal, conversation_id)
        limit, offset = _paginar(limit, offset)
        filas = self._repo.list_messages(principal, conversation_id, limit, offset)
        hay_mas = len(filas) > limit
        items = [_mensaje_out(f) for f in filas[:limit]]
        return MensajesPagina(items=items, siguiente=offset + limit if hay_mas else None)

    def guardar_mensaje(self, principal: Principal, conversation_id: UUID, datos: MensajeCrear) -> MensajeGuardadoOut:
        self._exigir(principal, conversation_id)
        existente = self._repo.find_message_by_client(principal, conversation_id, datos.cliente_id)
        if existente is not None:
            return self._repetido(existente, datos)

        cuerpo = datos.model_dump(mode="json", exclude={"cliente_id"})
        cuerpo["cliente_id"] = str(datos.cliente_id)
        try:
            fila = self._repo.insert_message(principal, conversation_id, cuerpo)
        except SupabaseConstraintError as exc:
            if exc.status_code != 409:
                raise
            # Carrera: otro envío con el mismo cliente_id llegó antes. Se devuelve el guardado, sin duplicar.
            existente = self._repo.find_message_by_client(principal, conversation_id, datos.cliente_id)
            if existente is None:
                raise
            return self._repetido(existente, datos)
        return MensajeGuardadoOut(mensaje=_mensaje_out(fila), repetido=False)

    # ----- internos ----------------------------------------------------------
    def _exigir(self, principal: Principal, conversation_id: UUID) -> dict[str, Any]:
        fila = self._repo.get_conversation(principal, conversation_id)
        if fila is None:
            raise NotFoundError("La conversación no existe o no es accesible.")
        return fila

    @staticmethod
    def _repetido(existente: dict[str, Any], datos: MensajeCrear) -> MensajeGuardadoOut:
        if existente.get("role") != datos.role or existente.get("content") != datos.content:
            raise ConflictError("Ese identificador de mensaje ya se usó con otro contenido.")
        return MensajeGuardadoOut(mensaje=_mensaje_out(existente), repetido=True)
