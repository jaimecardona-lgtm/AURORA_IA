"""Fixtures compartidos.

- Par RSA generado en memoria: simula las claves del JWKS de Supabase (sin red).
- Fábrica de tokens con iss/aud/exp/iat/sub correctos (o rotos a propósito en las pruebas).
- Repositorio en memoria que aísla datos por token, para probar la API sin Supabase.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.api.deps import get_academic_service, get_verifier
from app.main import create_app
from app.security.jwt_verifier import SupabaseJwtVerifier

ISSUER = "https://proyecto-prueba.supabase.co/auth/v1"
AUDIENCE = "authenticated"
KID = "clave-prueba-1"


@pytest.fixture(scope="session")
def rsa_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def rsa_public_key(rsa_private_key):
    return rsa_private_key.public_key()


@pytest.fixture(scope="session")
def otra_clave_privada():
    """Clave distinta: firmar con ella debe producir tokens rechazados."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def make_token(rsa_private_key):
    import jwt

    def _make(
        *,
        sub: str | None = None,
        exp_offset: int = 3600,
        iss: str = ISSUER,
        aud: str = AUDIENCE,
        key: Any = None,
        algorithm: str = "RS256",
        kid: str | None = KID,
        extra: dict[str, Any] | None = None,
    ) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "sub": sub or str(uuid.uuid4()),
            "iss": iss,
            "aud": aud,
            "iat": now,
            "exp": now + exp_offset,
            "role": "authenticated",
            "email": "alumna@prueba.local",
        }
        if extra:
            payload.update(extra)
        headers = {"kid": kid} if kid else {}
        return jwt.encode(payload, key or rsa_private_key, algorithm=algorithm, headers=headers)

    return _make


class RepositorioEnMemoria:
    """Imita AcademicRepository: cada token es un 'usuario' y solo ve sus filas (como RLS)."""

    def __init__(self) -> None:
        self.asignaturas: list[dict[str, Any]] = []
        self.notas: list[dict[str, Any]] = []

    @staticmethod
    def _ahora() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    def _propias_asignaturas(self, token: str):
        return [s for s in self.asignaturas if s["_owner"] == token]

    def _propias_notas(self, token: str):
        return [n for n in self.notas if n["_owner"] == token]

    def list_subjects(self, token):
        return [dict(s) for s in self._propias_asignaturas(token)]

    def get_subject(self, token, subject_id):
        for s in self._propias_asignaturas(token):
            if str(s["id"]) == str(subject_id):
                return dict(s)
        return None

    def create_subject(self, token, nombre):
        if any(s["nombre"].lower() == nombre.lower() for s in self._propias_asignaturas(token)):
            from app.errors import SupabaseConstraintError

            raise SupabaseConstraintError("Ya existe un registro con esos datos.", 409)
        ahora = self._ahora()
        fila = {"id": str(uuid.uuid4()), "nombre": nombre, "created_at": ahora, "updated_at": ahora, "_owner": token}
        self.asignaturas.append(fila)
        return dict(fila)

    def update_subject(self, token, subject_id, changes):
        for s in self._propias_asignaturas(token):
            if str(s["id"]) == str(subject_id):
                s.update(changes)
                return dict(s)
        return None

    def delete_subject(self, token, subject_id):
        antes = len(self.asignaturas)
        self.asignaturas = [s for s in self.asignaturas if not (s["_owner"] == token and str(s["id"]) == str(subject_id))]
        self.notas = [n for n in self.notas if not (n["_owner"] == token and str(n["subject_id"]) == str(subject_id))]
        return len(self.asignaturas) < antes

    def list_grades(self, token, subject_id=None):
        filas = self._propias_notas(token)
        if subject_id is not None:
            filas = [n for n in filas if str(n["subject_id"]) == str(subject_id)]
        return [dict(n) for n in filas]

    def get_grade(self, token, grade_id):
        for n in self._propias_notas(token):
            if str(n["id"]) == str(grade_id):
                return dict(n)
        return None

    def create_grade(self, token, subject_id, descripcion, nota):
        ahora = self._ahora()
        fila = {
            "id": str(uuid.uuid4()),
            "subject_id": str(subject_id),
            "descripcion": descripcion,
            "nota": nota,
            "created_at": ahora,
            "updated_at": ahora,
            "_owner": token,
        }
        self.notas.append(fila)
        return dict(fila)

    def update_grade(self, token, grade_id, changes):
        for n in self._propias_notas(token):
            if str(n["id"]) == str(grade_id):
                n.update(changes)
                return dict(n)
        return None

    def delete_grade(self, token, grade_id):
        antes = len(self.notas)
        self.notas = [n for n in self.notas if not (n["_owner"] == token and str(n["id"]) == str(grade_id))]
        return len(self.notas) < antes


@pytest.fixture
def repo_en_memoria():
    return RepositorioEnMemoria()


@pytest.fixture
def verifier(rsa_public_key):
    return SupabaseJwtVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        resolve_key=lambda _token: rsa_public_key,
        leeway_seconds=0,
    )


@pytest.fixture
def client(verifier, repo_en_memoria):
    """TestClient con verificador de JWT local y repositorio en memoria."""
    from app.services.academic_service import AcademicService

    app = create_app()
    app.dependency_overrides[get_verifier] = lambda: verifier
    app.dependency_overrides[get_academic_service] = lambda: AcademicService(repo_en_memoria)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_header(make_token):
    """Devuelve un encabezado Authorization válido para un usuario nuevo."""
    def _header(sub: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(sub=sub)}"}

    return _header


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    """Las pruebas no deben depender de variables del shell (p. ej. DEMO_MODE exportado al probar el servidor)."""
    # Vacío explícito: la variable de entorno tiene prioridad sobre backend/.env (que sí tiene Supabase).
    for variable in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "OPENROUTER_API_KEY", "OPENROUTER_MODEL"):
        monkeypatch.setenv(variable, "")
    monkeypatch.setenv("APP_ENV", "development")
    for variable in ("DEMO_MODE", "PERSISTENCE_BACKEND", "SQLITE_PATH", "JWT_ISSUER", "JWT_JWKS_URL", "JWT_AUDIENCE"):
        monkeypatch.delenv(variable, raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
