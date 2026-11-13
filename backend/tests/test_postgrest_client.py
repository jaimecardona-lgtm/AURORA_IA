"""Cliente PostgREST: cabeceras (JWT del usuario, nunca service_role) y traducción de errores."""

import httpx
import pytest

from app.errors import (
    SupabaseConstraintError,
    SupabasePermissionError,
    SupabaseRejectedTokenError,
    SupabaseUnavailableError,
)
from app.repositories.postgrest_client import PostgrestClient

BASE = "https://proyecto-prueba.supabase.co"
PUBLICA = "sb_publishable_CLAVE_FICTICIA_PRUEBA"
TOKEN_USUARIO = "token.de.usuario.prueba"


def _cliente(handler):
    return PostgrestClient(BASE, PUBLICA, transport=httpx.MockTransport(handler))


def test_propaga_jwt_del_usuario_y_usa_clave_publica():
    capturadas = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturadas["auth"] = request.headers["Authorization"]
        capturadas["apikey"] = request.headers["apikey"]
        capturadas["url"] = str(request.url)
        return httpx.Response(200, json=[{"id": "x"}])

    _cliente(handler).request("GET", "academic_subjects", access_token=TOKEN_USUARIO, params={"select": "*"})

    assert capturadas["auth"] == f"Bearer {TOKEN_USUARIO}"
    assert capturadas["apikey"] == PUBLICA
    assert capturadas["url"].startswith(f"{BASE}/rest/v1/academic_subjects")


@pytest.mark.parametrize(
    ("status", "payload", "excepcion"),
    [
        (401, {"message": "JWT expired"}, SupabaseRejectedTokenError),
        (403, {"message": "permission denied"}, SupabasePermissionError),
        (409, {"code": "23505"}, SupabaseConstraintError),
        (400, {"code": "23503"}, SupabaseConstraintError),
        (400, {"code": "23514"}, SupabaseConstraintError),
        (500, {"message": "boom"}, SupabaseUnavailableError),
        (404, {"message": "relation does not exist"}, SupabaseUnavailableError),
    ],
)
def test_errores_de_supabase_se_traducen(status, payload, excepcion):
    cliente = _cliente(lambda request: httpx.Response(status, json=payload))
    with pytest.raises(excepcion):
        cliente.request("GET", "academic_subjects", access_token=TOKEN_USUARIO)


def test_fk_y_check_devuelven_422_y_unicidad_409():
    fk = _cliente(lambda r: httpx.Response(409, json={"code": "23503"}))
    with pytest.raises(SupabaseConstraintError) as exc_fk:
        fk.request("POST", "grade_entries", access_token=TOKEN_USUARIO, json={})
    assert exc_fk.value.status_code == 422

    unico = _cliente(lambda r: httpx.Response(409, json={"code": "23505"}))
    with pytest.raises(SupabaseConstraintError) as exc_unico:
        unico.request("POST", "academic_subjects", access_token=TOKEN_USUARIO, json={})
    assert exc_unico.value.status_code == 409


def test_caida_de_red_se_convierte_en_503():
    def handler(request):
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(SupabaseUnavailableError):
        _cliente(handler).request("GET", "academic_subjects", access_token=TOKEN_USUARIO)


def test_respuesta_vacia_en_delete_devuelve_lista_vacia():
    cliente = _cliente(lambda r: httpx.Response(200, json=[]))
    assert cliente.request("DELETE", "tasks", access_token=TOKEN_USUARIO) == []
