"""Aplicación FastAPI de AURORA AI.

- API bajo /api (salud, documentación y recursos académicos).
- En producción sirve también el frontend compilado (STATIC_DIR) en el MISMO origen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app import __version__
from app.ai.provider import AIProviderError
from app.api.routes_academic import router as academic_router
from app.api.routes_copilot import router as copilot_router
from app.api.routes_conversaciones import router as conversaciones_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_finance import router as finance_router
from app.api.routes_tasks import router as tasks_router
from app.config import get_settings
from app.infrastructure.sqlite.database import open_migrated
from app.errors import DomainError, SupabaseError
from app.schemas.academic import HealthOut
from app.security.jwt_verifier import InvalidTokenError, JwksUnavailableError

health_router = APIRouter(prefix="/api", tags=["sistema"])


class ModoOut(BaseModel):
    modo: Literal["demo", "produccion"]
    persistencia: Literal["sqlite", "supabase"]
    aviso: str | None


@health_router.get("/modo", response_model=ModoOut)
def modo() -> ModoOut:
    """Indica a la UI si el servidor está en modo demo (sin inicio de sesión)."""
    settings = get_settings()
    demo = settings.demo_mode
    return ModoOut(
        modo="demo" if demo else "produccion",
        persistencia=settings.persistence_backend,  # type: ignore[arg-type]
        aviso=(
            "MODO DEMO LOCAL: sin inicio de sesión y con datos de demostración. No usar con datos reales."
            if demo
            else None
        ),
    )


@health_router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    return HealthOut(
        status="ok",
        supabase_configurado=bool(settings.supabase_url and settings.supabase_publishable_key),
        version=__version__,
    )


def _error_json(status_code: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


_CAMPOS = {
    "nombre": "El nombre", "descripcion": "La descripción", "nota": "La nota", "objetivo": "El objetivo",
    "ingreso": "El ingreso", "meta_ahorro": "La meta de ahorro", "monto": "El monto", "tipo": "El tipo",
    "categoria": "La categoría", "fecha": "La fecha", "titulo": "El título", "prioridad": "La prioridad",
    "estado": "El estado", "fecha_limite": "La fecha límite", "anio": "El año", "mes": "El mes",
    "dias": "Los días", "subject_id": "La asignatura", "grade_id": "La nota", "expense_id": "El gasto",
    "task_id": "La tarea", "body": "Los datos",
}


def _mensaje_validacion(error: dict[str, Any]) -> str:
    """Traduce un error de validación de Pydantic a un mensaje en español para la UI."""
    tipo = error.get("type", "")
    ctx = error.get("ctx", {}) or {}
    if tipo == "missing":
        return "es obligatorio."
    if tipo == "extra_forbidden":
        return "no está permitido."
    if tipo == "greater_than_equal":
        return f"debe ser mayor o igual a {ctx.get('ge')}."
    if tipo == "less_than_equal":
        return f"debe ser menor o igual a {ctx.get('le')}."
    if tipo == "string_too_short":
        return "no puede estar vacío."
    if tipo == "string_too_long":
        return f"no puede superar {ctx.get('max_length')} caracteres."
    if tipo == "literal_error":
        return "no es una opción válida."
    if tipo in {"int_parsing", "float_parsing", "decimal_parsing", "decimal_type", "int_type", "float_type"}:
        return "debe ser un número."
    if tipo in {"date_from_datetime_parsing", "date_parsing", "date_type"}:
        return "debe tener formato AAAA-MM-DD."
    if tipo in {"uuid_parsing", "uuid_type"}:
        return "no es un identificador válido."
    if tipo == "value_error":
        return str(ctx.get("error", "valor no válido")).removeprefix("Value error, ")
    return "tiene un valor no válido."


def _detalle_validacion(errores: list[dict[str, Any]]) -> str:
    if not errores:
        return "Revisa los datos ingresados."
    primero = errores[0]
    ubicacion = [str(parte) for parte in primero.get("loc", []) if parte not in ("body", "query", "path")]
    campo = ubicacion[-1] if ubicacion else ""
    etiqueta = _CAMPOS.get(campo, campo.replace("_", " ").capitalize() if campo else "Un dato")
    tipo = primero.get("type", "")
    if tipo == "missing":
        return f"Falta indicar {etiqueta[0].lower() + etiqueta[1:] if etiqueta else 'un dato'}."
    if tipo == "extra_forbidden":
        return f"El campo '{campo}' no está permitido."
    return f"{etiqueta} {_mensaje_validacion(primero)}".strip()


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_json(422, _detalle_validacion(exc.errors()))

    @app.exception_handler(InvalidTokenError)
    async def _token_invalido(_: Request, exc: InvalidTokenError) -> JSONResponse:
        return _error_json(401, str(exc), {"WWW-Authenticate": "Bearer"})

    @app.exception_handler(JwksUnavailableError)
    async def _jwks_no_disponible(_: Request, exc: JwksUnavailableError) -> JSONResponse:
        return _error_json(503, str(exc))

    @app.exception_handler(SupabaseError)
    async def _supabase(_: Request, exc: SupabaseError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return _error_json(exc.status_code, exc.detail, headers)

    @app.exception_handler(AIProviderError)
    async def _proveedor_ia(_: Request, exc: AIProviderError) -> JSONResponse:
        # Mensaje genérico y código; nunca el cuerpo del proveedor ni la clave.
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "codigo": exc.code})

    @app.exception_handler(DomainError)
    async def _dominio(_: Request, exc: DomainError) -> JSONResponse:
        return _error_json(exc.status_code, exc.detail)


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Sirve el SPA compilado. Las rutas /api/* nunca caen en el fallback."""
    index_file = static_dir / "index.html"
    if not index_file.is_file():
        return
    root = static_dir.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Recurso no encontrado.")
        candidate = (root / full_path).resolve()
        if candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index_file)


def create_app() -> FastAPI:
    settings = get_settings()
    # Falla al arrancar si la configuración es insegura (p. ej. DEMO_MODE en producción).
    settings.validate_runtime()
    if settings.persistence_backend == "sqlite":
        # Migraciones locales reproducibles: se aplican al arrancar, solo las pendientes.
        open_migrated(settings.sqlite_path).close()
    app = FastAPI(
        title="AURORA AI API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    _register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(academic_router)
    app.include_router(finance_router)
    app.include_router(tasks_router)
    app.include_router(dashboard_router)
    app.include_router(copilot_router)
    app.include_router(conversaciones_router)
    _mount_frontend(app, settings.static_dir)
    return app


app = create_app()
