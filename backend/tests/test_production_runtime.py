"""Guardas de seguridad del runtime de produccion, sin conexiones externas."""

from pydantic import SecretStr
import pytest

from app.config import ConfigurationError, Settings


def config_prod(**overrides):
    values = dict(
        APP_ENV="production",
        PERSISTENCE_BACKEND="supabase",
        DEMO_MODE=False,
        COPILOT_PROVIDER="openrouter",
        SUPABASE_URL="https://proyecto-ficticio.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="sb_publishable_prueba",
        OPENROUTER_API_KEY="",
        OPENROUTER_MODEL="",
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_prod_segura_admite_supabase_sin_conectar_red():
    config_prod().validate_runtime()


@pytest.mark.parametrize("cambios", [
    {"PERSISTENCE_BACKEND": "sqlite"},
    {"SUPABASE_URL": ""},
    {"SUPABASE_URL": "http://inseguro.test"},
    {"SUPABASE_PUBLISHABLE_KEY": ""},
    {"DEMO_MODE": True},
    {"COPILOT_PROVIDER": "simulado"},
])
def test_prod_rechaza_configuracion_insegura(cambios):
    with pytest.raises(ConfigurationError):
        config_prod(**cambios).validate_runtime()
