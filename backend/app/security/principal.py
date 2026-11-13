"""Identidad de quien hace la petición, independiente del backend de persistencia.

- Modo normal: `user_id` = claim `sub` verificado del JWT; `access_token` = JWT del usuario
  (lo usa PostgREST, donde RLS aplica `auth.uid()`).
- Modo demo (solo desarrollo, SQLite): usuario local fijo, sin token. No es autenticación:
  la UI lo muestra como MODO DEMO y el arranque se rechaza fuera de desarrollo.
"""

from __future__ import annotations

from dataclasses import dataclass

# UUID fijo y sin privilegios: solo existe en la base SQLite local.
DEMO_USER_ID = "00000000-0000-4000-8000-00000000da0e"


@dataclass(frozen=True)
class Principal:
    user_id: str
    access_token: str | None = None
    is_demo: bool = False


DEMO_PRINCIPAL = Principal(user_id=DEMO_USER_ID, access_token=None, is_demo=True)
