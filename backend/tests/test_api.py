"""Pruebas de la API: autenticación (401), entradas inválidas (422), CRUD y aislamiento entre usuarios."""

import uuid

import pytest


# ---------------------------------------------------------------- salud y docs
def test_health_no_expone_secretos(client):
    respuesta = client.get("/api/health")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert set(cuerpo) == {"status", "supabase_configurado", "version"}


def test_documentacion_disponible_en_api_docs(client):
    assert client.get("/api/docs").status_code == 200


def test_sin_token_y_sin_configuracion_responde_401_no_503(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import deps
    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("SUPABASE_URL", "")
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()
    try:
        with TestClient(create_app()) as sin_config:
            assert sin_config.get("/api/subjects").status_code == 401
    finally:
        get_settings.cache_clear()
        deps.get_verifier.cache_clear()


def test_sin_configuracion_de_supabase_responde_503_con_bearer(monkeypatch):
    """Sin SUPABASE_URL el servidor debe responder 503 claro, no 500."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.api import deps
    from app.main import create_app

    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "")
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()
    try:
        with TestClient(create_app()) as sin_config:
            respuesta = sin_config.get("/api/subjects", headers={"Authorization": "Bearer a.b.c"})
            assert respuesta.status_code == 503
            assert sin_config.get("/api/health").json()["supabase_configurado"] is False
    finally:
        get_settings.cache_clear()
        deps.get_verifier.cache_clear()


# ---------------------------------------------------------- autenticación 401
@pytest.mark.parametrize(
    "encabezados",
    [
        {},  # sin Authorization
        {"Authorization": "Basic abc123"},  # esquema incorrecto
        {"Authorization": "Bearer "},  # token vacío
    ],
)
def test_sin_token_valido_responde_401(client, encabezados):
    respuesta = client.get("/api/subjects", headers=encabezados)
    assert respuesta.status_code == 401
    assert respuesta.headers.get("WWW-Authenticate") == "Bearer"


def test_token_invalido_responde_401(client):
    respuesta = client.get("/api/subjects", headers={"Authorization": "Bearer no.es.un.jwt"})
    assert respuesta.status_code == 401


def test_token_expirado_responde_401(client, make_token):
    token = make_token(exp_offset=-300)
    respuesta = client.get("/api/subjects", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 401


def test_user_id_en_el_cuerpo_no_sustituye_al_token(client, make_token):
    """El backend debe ignorar cualquier identidad enviada en el JSON."""
    token = make_token(sub=str(uuid.uuid4()))
    respuesta = client.post(
        "/api/subjects",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": "Cálculo", "user_id": str(uuid.uuid4())},
    )
    assert respuesta.status_code == 422  # campo extra rechazado (extra="forbid")


# ---------------------------------------------------------- entradas 422
def test_nota_fuera_de_rango_responde_422(client, auth_header):
    cabecera = auth_header()
    asignatura = client.post("/api/subjects", headers=cabecera, json={"nombre": "Física"}).json()
    respuesta = client.post(
        f"/api/subjects/{asignatura['id']}/grades",
        headers=cabecera,
        json={"descripcion": "Parcial", "nota": 5.5},
    )
    assert respuesta.status_code == 422


@pytest.mark.parametrize("nota", [-1, "abc", True, None])
def test_nota_no_valida_responde_422(client, auth_header, nota):
    cabecera = auth_header()
    asignatura = client.post("/api/subjects", headers=cabecera, json={"nombre": "Química"}).json()
    respuesta = client.post(
        f"/api/subjects/{asignatura['id']}/grades",
        headers=cabecera,
        json={"descripcion": "Parcial", "nota": nota},
    )
    assert respuesta.status_code == 422


def test_uuid_invalido_en_ruta_responde_422(client, auth_header):
    respuesta = client.get("/api/subjects/no-es-uuid", headers=auth_header())
    assert respuesta.status_code == 422


def test_nombre_vacio_responde_422(client, auth_header):
    respuesta = client.post("/api/subjects", headers=auth_header(), json={"nombre": "   "})
    assert respuesta.status_code == 422


def test_patch_sin_campos_responde_422(client, auth_header):
    cabecera = auth_header()
    asignatura = client.post("/api/subjects", headers=cabecera, json={"nombre": "Historia"}).json()
    respuesta = client.patch(f"/api/subjects/{asignatura['id']}", headers=cabecera, json={})
    assert respuesta.status_code == 422


# ---------------------------------------------------------- CRUD y promedio
def test_crud_de_asignaturas_y_notas_con_promedio(client, auth_header):
    cabecera = auth_header()

    creada = client.post("/api/subjects", headers=cabecera, json={"nombre": "Programación"})
    assert creada.status_code == 201
    asignatura_id = creada.json()["id"]
    assert creada.json()["promedio"] is None

    for descripcion, nota in [("Parcial 1", "4.5"), ("Parcial 2", 3.0), ("Taller", 2.9)]:
        r = client.post(
            f"/api/subjects/{asignatura_id}/grades",
            headers=cabecera,
            json={"descripcion": descripcion, "nota": nota},
        )
        assert r.status_code == 201

    detalle = client.get(f"/api/subjects/{asignatura_id}", headers=cabecera).json()
    assert detalle["total_notas"] == 3
    assert detalle["promedio"] == "3.47"
    assert detalle["aprobado"] is True
    assert len(detalle["notas"]) == 3

    listado = client.get("/api/subjects", headers=cabecera).json()
    assert [a["nombre"] for a in listado] == ["Programación"]

    nota_id = detalle["notas"][0]["id"]
    actualizada = client.patch(f"/api/grades/{nota_id}", headers=cabecera, json={"nota": 2.0})
    assert actualizada.status_code == 200
    assert actualizada.json()["aprobado"] is False

    assert client.delete(f"/api/grades/{nota_id}", headers=cabecera).status_code == 204
    assert client.get(f"/api/grades/{nota_id}", headers=cabecera).status_code == 404

    renombrada = client.patch(f"/api/subjects/{asignatura_id}", headers=cabecera, json={"nombre": "Prog. II"})
    assert renombrada.json()["nombre"] == "Prog. II"

    assert client.delete(f"/api/subjects/{asignatura_id}", headers=cabecera).status_code == 204
    assert client.get(f"/api/subjects/{asignatura_id}", headers=cabecera).status_code == 404


def test_asignatura_duplicada_responde_409(client, auth_header):
    cabecera = auth_header()
    client.post("/api/subjects", headers=cabecera, json={"nombre": "Álgebra"})
    respuesta = client.post("/api/subjects", headers=cabecera, json={"nombre": "álgebra"})
    assert respuesta.status_code == 409


def test_recurso_inexistente_responde_404(client, auth_header):
    respuesta = client.get(f"/api/subjects/{uuid.uuid4()}", headers=auth_header())
    assert respuesta.status_code == 404


# ---------------------------------------------------------- aislamiento
def test_otro_usuario_no_ve_ni_modifica_los_datos(client, make_token):
    token_a = make_token()
    token_b = make_token()
    cabecera_a = {"Authorization": f"Bearer {token_a}"}
    cabecera_b = {"Authorization": f"Bearer {token_b}"}

    asignatura = client.post("/api/subjects", headers=cabecera_a, json={"nombre": "Secreto de A"}).json()
    nota = client.post(
        f"/api/subjects/{asignatura['id']}/grades",
        headers=cabecera_a,
        json={"descripcion": "Privada", "nota": 4.0},
    ).json()

    assert client.get("/api/subjects", headers=cabecera_b).json() == []
    assert client.get(f"/api/subjects/{asignatura['id']}", headers=cabecera_b).status_code == 404
    assert client.get(f"/api/grades/{nota['id']}", headers=cabecera_b).status_code == 404
    assert client.patch(f"/api/grades/{nota['id']}", headers=cabecera_b, json={"nota": 0}).status_code == 404
    assert client.delete(f"/api/subjects/{asignatura['id']}", headers=cabecera_b).status_code == 404
    assert client.post(
        f"/api/subjects/{asignatura['id']}/grades",
        headers=cabecera_b,
        json={"descripcion": "Intrusa", "nota": 5.0},
    ).status_code == 404

    # Los datos de A siguen intactos
    assert client.get(f"/api/grades/{nota['id']}", headers=cabecera_a).json()["nota"] == "4.00"
