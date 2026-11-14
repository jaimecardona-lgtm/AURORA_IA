"""Configuración del backend leída desde variables de entorno.

Ningún secreto va en el código. Ver backend/.env.example (valores ficticios).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEMO_ALLOWED_ENVIRONMENTS = frozenset({"development", "local", "test"})


class ConfigurationError(RuntimeError):
    """Configuración incompatible: el servidor no debe arrancar."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")

    # Proyecto Supabase (clave PÚBLICA; nunca service_role).
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_publishable_key: str = Field(default="", alias="SUPABASE_PUBLISHABLE_KEY")

    # Validación del JWT de Supabase Auth.
    # Por defecto: issuer = {SUPABASE_URL}/auth/v1, audience = "authenticated",
    # JWKS = {issuer}/.well-known/jwks.json. Se pueden sobrescribir explícitamente.
    jwt_issuer: str = Field(default="", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="authenticated", alias="JWT_AUDIENCE")
    jwt_jwks_url: str = Field(default="", alias="JWT_JWKS_URL")
    jwt_leeway_seconds: int = Field(default=10, alias="JWT_LEEWAY_SECONDS", ge=0, le=60)

    # Tiempo máximo para llamar a Supabase (PostgREST y JWKS), en segundos.
    supabase_timeout_seconds: float = Field(default=8.0, alias="SUPABASE_TIMEOUT_SECONDS", gt=0, le=30)

    # Orígenes CORS permitidos (separados por coma). En producción el frontend
    # va bajo el mismo origen, así que normalmente no hace falta.
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    # Carpeta con el frontend compilado (vite build). Si no existe, solo se sirve la API.
    static_dir: Path = Field(default=BACKEND_DIR.parent / "frontend" / "dist", alias="STATIC_DIR")

    # Persistencia: "supabase" (PostgREST con JWT del usuario, integración futura) o
    # "sqlite" (desarrollo y demostración local, fuera del control de versiones).
    persistence_backend: str = Field(default="supabase", alias="PERSISTENCE_BACKEND")
    sqlite_path: Path = Field(default=BACKEND_DIR / "data" / "aurora_local.sqlite3", alias="SQLITE_PATH")

    # Modo demo: sin inicio de sesión, con un único usuario local. SOLO en desarrollo y con SQLite.
    # La aplicación se niega a arrancar si se combina con producción (ver validate_runtime).
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")

    # Copiloto (OpenRouter). La clave SOLO se lee del entorno del servidor y nunca se imprime.
    openrouter_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="", alias="OPENROUTER_MODEL")
    openrouter_timeout_seconds: float = Field(default=20.0, alias="OPENROUTER_TIMEOUT_SECONDS", gt=0, le=60)
    copilot_provider: str = Field(default="openrouter", alias="COPILOT_PROVIDER")
    copilot_max_tokens: int = Field(default=700, alias="COPILOT_MAX_TOKENS", ge=50, le=2000)
    copilot_requests_per_minute: int = Field(default=10, alias="COPILOT_REQUESTS_PER_MINUTE", ge=1, le=120)
    copilot_daily_tokens: int = Field(default=100000, alias="COPILOT_DAILY_TOKENS", ge=1000)
    copilot_concurrency: int = Field(default=2, alias="COPILOT_CONCURRENCY", ge=1, le=10)

    # Persistencia de conversaciones (Fase 08A). Desactivada por defecto: solo debe activarse
    # cuando la migración 20261113120000_fase08a_conversaciones_ia.sql esté aplicada en Supabase.
    # Con el valor en false, el copiloto funciona solo en memoria y no lo presenta como guardado.
    ai_conversaciones_persistentes: bool = Field(default=False, alias="AI_CONVERSACIONES_PERSISTENTES")

    @field_validator("copilot_provider")
    @classmethod
    def _proveedor_conocido(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ("openrouter", "simulado"):
            raise ValueError("COPILOT_PROVIDER debe ser 'openrouter' o 'simulado'.")
        return value

    @field_validator("persistence_backend")
    @classmethod
    def _backend_conocido(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ("supabase", "sqlite"):
            raise ValueError("PERSISTENCE_BACKEND debe ser 'supabase' o 'sqlite'.")
        return value

    def validate_runtime(self) -> None:
        """Falla al arrancar si la combinación de configuración es insegura."""
        if self.copilot_provider == "simulado" and self.app_env.strip().lower() not in DEMO_ALLOWED_ENVIRONMENTS:
            raise ConfigurationError("COPILOT_PROVIDER=simulado solo se permite en desarrollo. No es IA real.")
        if self.demo_mode:
            if self.app_env.strip().lower() not in DEMO_ALLOWED_ENVIRONMENTS:
                raise ConfigurationError(
                    "DEMO_MODE=true no puede usarse fuera de desarrollo. "
                    "La aplicación no arranca con el modo demo en producción."
                )
            if self.persistence_backend != "sqlite":
                raise ConfigurationError("DEMO_MODE=true requiere PERSISTENCE_BACKEND=sqlite.")
        if self.app_env.strip().lower() == "production":
            if self.persistence_backend != "supabase":
                raise ConfigurationError("Produccion requiere PERSISTENCE_BACKEND=supabase.")
            if not (self.supabase_url.startswith("https://") and self.supabase_publishable_key.strip()):
                raise ConfigurationError("Produccion requiere SUPABASE_URL HTTPS y SUPABASE_PUBLISHABLE_KEY.")

    @field_validator("supabase_url")
    @classmethod
    def _sin_barra_final(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def effective_issuer(self) -> str:
        return self.jwt_issuer.rstrip("/") or f"{self.supabase_url}/auth/v1"

    @property
    def effective_jwks_url(self) -> str:
        return self.jwt_jwks_url or f"{self.effective_issuer}/.well-known/jwks.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
