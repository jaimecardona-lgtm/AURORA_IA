"""Adaptador PostgREST de las conversaciones del copiloto (Fase 08A).

Seguridad:
- Cada petición lleva el JWT del usuario. RLS aplica auth.uid() = user_id en la base.
- Nunca se envía user_id: lo asigna DEFAULT auth.uid() y la política WITH CHECK lo valida.
- Nunca se usa service_role. Una conversación ajena se ve como inexistente (la lista llega vacía).
- Los mensajes no tienen UPDATE ni DELETE directos: solo lectura y creación.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.errors import SupabaseRejectedTokenError
from app.repositories.postgrest_client import PostgrestClient
from app.security.principal import Principal

CONVERSATIONS = "ai_conversations"
MESSAGES = "ai_messages"


def _token(principal: Principal) -> str:
    if not principal.access_token:
        raise SupabaseRejectedTokenError("La sesión no es válida. Vuelve a iniciar sesión.")
    return principal.access_token


def _primera(filas: list[dict[str, Any]]) -> dict[str, Any] | None:
    return filas[0] if filas else None


class PostgrestConversationRepository:
    def __init__(self, client: PostgrestClient) -> None:
        self._client = client

    # ----- conversaciones -------------------------------------------------
    def list_conversations(self, principal: Principal, limit: int, offset: int) -> list[dict[str, Any]]:
        """Pide limit+1 filas para saber si hay página siguiente sin contar toda la tabla."""
        return self._client.request(
            "GET", CONVERSATIONS, access_token=_token(principal),
            params={
                "select": "id,title,created_at,updated_at",
                "order": "updated_at.desc,id.desc",
                "limit": str(limit + 1),
                "offset": str(offset),
            },
        )

    def get_conversation(self, principal: Principal, conversation_id: UUID) -> dict[str, Any] | None:
        return _primera(self._client.request(
            "GET", CONVERSATIONS, access_token=_token(principal),
            params={"select": "id,title,created_at,updated_at", "id": f"eq.{conversation_id}", "limit": "1"},
        ))

    def create_conversation(self, principal: Principal, title: str) -> dict[str, Any]:
        filas = self._client.request(
            "POST", CONVERSATIONS, access_token=_token(principal),
            json={"title": title},
            return_representation=True,
        )
        return filas[0]

    def update_title(self, principal: Principal, conversation_id: UUID, title: str) -> dict[str, Any] | None:
        return _primera(self._client.request(
            "PATCH", CONVERSATIONS, access_token=_token(principal),
            params={"id": f"eq.{conversation_id}"}, json={"title": title}, return_representation=True,
        ))

    def delete_conversation(self, principal: Principal, conversation_id: UUID) -> bool:
        """Borra la conversación; sus mensajes se eliminan en cascada en la base."""
        return bool(self._client.request(
            "DELETE", CONVERSATIONS, access_token=_token(principal),
            params={"id": f"eq.{conversation_id}"}, return_representation=True,
        ))

    # ----- mensajes -------------------------------------------------------
    def list_messages(self, principal: Principal, conversation_id: UUID, limit: int, offset: int) -> list[dict[str, Any]]:
        return self._client.request(
            "GET", MESSAGES, access_token=_token(principal),
            params={
                "select": "id,cliente_id,role,content,estado,proveedor,modelo,simulado,contexto_usado,total_tokens,created_at",
                "conversation_id": f"eq.{conversation_id}",
                "order": "orden.asc",
                "limit": str(limit + 1),
                "offset": str(offset),
            },
        )

    def find_message_by_client(self, principal: Principal, conversation_id: UUID, cliente_id: UUID) -> dict[str, Any] | None:
        return _primera(self._client.request(
            "GET", MESSAGES, access_token=_token(principal),
            params={
                "select": "id,cliente_id,role,content,estado,proveedor,modelo,simulado,contexto_usado,total_tokens,created_at",
                "conversation_id": f"eq.{conversation_id}",
                "cliente_id": f"eq.{cliente_id}",
                "limit": "1",
            },
        ))

    def insert_message(self, principal: Principal, conversation_id: UUID, datos: dict[str, Any]) -> dict[str, Any]:
        filas = self._client.request(
            "POST", MESSAGES, access_token=_token(principal),
            json={"conversation_id": str(conversation_id), **datos},
            return_representation=True,
        )
        return filas[0]
