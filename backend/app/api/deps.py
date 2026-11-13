"""Dependencias de FastAPI: identidad (JWT o modo demo) y elección del backend de persistencia.

Modo Supabase (por defecto, integración futura):
  Authorization: Bearer <JWT> -> verificación JWKS -> Principal(sub, token)
  -> PostgREST con ese token; RLS filtra los datos.

Modo SQLite (desarrollo y demostración local):
  -> Principal(usuario local) -> repositorios SQLite que filtran por user_id.
  Con DEMO_MODE=true no se exige token. Esto NO es autenticación: la UI lo muestra
  como MODO DEMO, y la aplicación se niega a arrancar fuera de desarrollo.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.errors import FeatureNotAvailableError, SupabaseUnavailableError
from app.infrastructure.sqlite.database import connect
from app.infrastructure.sqlite.repositories import (
    SqliteAcademicRepository,
    SqliteBudgetRepository,
    SqliteTaskRepository,
)
from app.repositories.academic_repository import AcademicRepository
from app.repositories.postgrest_client import PostgrestClient
from app.repositories.postgrest_conversaciones import PostgrestConversationRepository
from app.repositories.postgrest_dominio import PostgrestBudgetRepository, PostgrestTaskRepository
from app.services.conversation_service import ConversationService
from app.security.jwt_verifier import (
    AuthenticatedUser,
    JwksUnavailableError,
    SupabaseJwtVerifier,
    jwks_key_resolver,
)
from app.security.principal import DEMO_PRINCIPAL, Principal
from app.services.academic_service import AcademicService
from app.services.budget_service import BudgetService
from app.services.dashboard_service import DashboardService
from app.ai.context_builder import ContextBuilder
from app.ai.copilot_service import CopilotService, Limitador, LimitesCopiloto
from app.ai.openrouter_client import OpenRouterProvider
from app.ai.provider import AIProvider
from app.ai.simulated_provider import SimulatedProvider
from app.services.task_service import TaskService

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    user: AuthenticatedUser
    access_token: str


@lru_cache
def get_verifier() -> SupabaseJwtVerifier:
    settings = get_settings()
    if not settings.supabase_url:
        # Sin configuración NO se lanza aquí: así una petición sin token sigue recibiendo 401.
        # Al intentar validar un token se responde 503 (configuración incompleta).
        def sin_configuracion(_token: str) -> object:
            raise JwksUnavailableError("La autenticación no está configurada en el servidor.")

        return SupabaseJwtVerifier(
            issuer="", audience=settings.jwt_audience, resolve_key=sin_configuracion
        )
    return SupabaseJwtVerifier(
        issuer=settings.effective_issuer,
        audience=settings.jwt_audience,
        resolve_key=jwks_key_resolver(settings.effective_jwks_url, settings.supabase_timeout_seconds),
        leeway_seconds=settings.jwt_leeway_seconds,
    )


def _verificar_bearer(
    credentials: HTTPAuthorizationCredentials | None,
    verifier: SupabaseJwtVerifier,
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = verifier.verify(credentials.credentials)
    return AuthContext(user=user, access_token=credentials.credentials)


def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
    verifier: Annotated[SupabaseJwtVerifier, Depends(get_verifier)],
) -> Principal:
    """Identidad de la petición. En modo demo (solo desarrollo) no se exige token."""
    if get_settings().demo_mode:
        return DEMO_PRINCIPAL
    ctx = _verificar_bearer(credentials, verifier)
    return Principal(user_id=str(ctx.user.id), access_token=ctx.access_token)


def get_db() -> Iterator[sqlite3.Connection | None]:
    """Conexión SQLite por petición. None cuando la persistencia es Supabase."""
    settings = get_settings()
    if settings.persistence_backend != "sqlite":
        yield None
        return
    conn = connect(settings.sqlite_path)
    try:
        yield conn
    finally:
        conn.close()


@lru_cache
def get_postgrest_client() -> PostgrestClient:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_publishable_key):
        raise SupabaseUnavailableError("Los datos no están configurados en el servidor.")
    return PostgrestClient(
        base_url=settings.supabase_url,
        publishable_key=settings.supabase_publishable_key,
        timeout_seconds=settings.supabase_timeout_seconds,
    )


def _solo_sqlite(conn: sqlite3.Connection | None, modulo: str) -> sqlite3.Connection:
    if conn is None:
        # 501: funcionalidad no implementada para este backend, no un fallo del servidor.
        raise FeatureNotAvailableError(
            f"El módulo {modulo} solo está disponible con PERSISTENCE_BACKEND=sqlite en esta fase."
        )
    return conn


def get_academic_service(conn: Annotated[sqlite3.Connection | None, Depends(get_db)]) -> AcademicService:
    if conn is not None:
        return AcademicService(SqliteAcademicRepository(conn))
    return AcademicService(AcademicRepository(get_postgrest_client()))


def _supabase_configurado() -> bool:
    ajustes = get_settings()
    return bool(ajustes.supabase_url and ajustes.supabase_publishable_key)


def get_budget_service(conn: Annotated[sqlite3.Connection | None, Depends(get_db)]) -> BudgetService:
    if conn is not None:
        return BudgetService(SqliteBudgetRepository(conn))
    return BudgetService(PostgrestBudgetRepository(get_postgrest_client()))  # type: ignore[arg-type]


def get_task_service(conn: Annotated[sqlite3.Connection | None, Depends(get_db)]) -> TaskService:
    if conn is not None:
        return TaskService(SqliteTaskRepository(conn))
    return TaskService(PostgrestTaskRepository(get_postgrest_client()))  # type: ignore[arg-type]


def get_dashboard_service(
    conn: Annotated[sqlite3.Connection | None, Depends(get_db)],
    academic: AcademicServiceDep,
) -> DashboardService:
    """Finanzas y tareas solo existen con SQLite en esta fase; con Supabase se marcan no disponibles."""
    if conn is not None:
        return DashboardService(academic, BudgetService(SqliteBudgetRepository(conn)),
                                TaskService(SqliteTaskRepository(conn)), "sqlite")
    if not _supabase_configurado():
        # Sin Supabase configurado, finanzas y tareas se declaran no disponibles (sin cifras inventadas).
        return DashboardService(academic, None, None, "supabase")
    return DashboardService(academic, BudgetService(PostgrestBudgetRepository(get_postgrest_client())),  # type: ignore[arg-type]
                            TaskService(PostgrestTaskRepository(get_postgrest_client())), "supabase")  # type: ignore[arg-type]


@lru_cache
def get_ai_provider() -> AIProvider | None:
    """Proveedor del copiloto. None = no configurado (el copiloto responde 503 claro, sin inventar)."""
    ajustes = get_settings()
    if ajustes.copilot_provider == "simulado":
        return SimulatedProvider()
    clave = ajustes.openrouter_api_key.get_secret_value()
    if not clave or not ajustes.openrouter_model:
        return None
    return OpenRouterProvider(clave, ajustes.openrouter_model, ajustes.openrouter_timeout_seconds)


_LIMITADOR: Limitador | None = None


def get_limitador() -> Limitador:
    global _LIMITADOR
    if _LIMITADOR is None:
        ajustes = get_settings()
        _LIMITADOR = Limitador(LimitesCopiloto(
            peticiones_por_minuto=ajustes.copilot_requests_per_minute,
            tokens_diarios=ajustes.copilot_daily_tokens,
            concurrencia=ajustes.copilot_concurrency,
            max_tokens_respuesta=ajustes.copilot_max_tokens,
        ))
    return _LIMITADOR


def _persistencia_conversaciones_activa() -> bool:
    """Solo con Supabase, con la migración 08A aplicada (flag) y configuración completa. SQLite no la soporta."""
    ajustes = get_settings()
    return bool(ajustes.ai_conversaciones_persistentes and ajustes.persistence_backend == "supabase" and _supabase_configurado())


def get_conversation_service() -> ConversationService:
    if not _persistencia_conversaciones_activa():
        # 501: no es un fallo del servidor; la interfaz usa el modo en memoria.
        raise FeatureNotAvailableError(
            "La persistencia de conversaciones no está activa en este servidor."
        )
    return ConversationService(PostgrestConversationRepository(get_postgrest_client()))


def get_copilot_service(
    dashboard: DashboardServiceDep,
    academic: AcademicServiceDep,
    conn: Annotated[sqlite3.Connection | None, Depends(get_db)],
    proveedor: Annotated[AIProvider | None, Depends(get_ai_provider)],
    limitador: Annotated[Limitador, Depends(get_limitador)],
) -> CopilotService:
    if conn is not None:
        budget = BudgetService(SqliteBudgetRepository(conn))
    elif _supabase_configurado():
        budget = BudgetService(PostgrestBudgetRepository(get_postgrest_client()))  # type: ignore[arg-type]
    else:
        budget = None
    constructor = ContextBuilder(dashboard, academic, budget)
    modo = "demo" if get_settings().demo_mode else "produccion"
    return CopilotService(proveedor, constructor, limitador, modo, persistencia=_persistencia_conversaciones_activa())


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
    verifier: Annotated[SupabaseJwtVerifier, Depends(get_verifier)],
) -> AuthContext:
    return _verificar_bearer(credentials, verifier)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
AcademicServiceDep = Annotated[AcademicService, Depends(get_academic_service)]
BudgetServiceDep = Annotated[BudgetService, Depends(get_budget_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
CopilotServiceDep = Annotated[CopilotService, Depends(get_copilot_service)]
ConversacionesServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]
