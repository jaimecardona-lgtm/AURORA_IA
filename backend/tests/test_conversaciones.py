"""Conversaciones persistidas del copiloto (Fase 08A).

IMPORTANTE: el PostgREST de estas pruebas es una SIMULACIÓN en memoria (httpx.MockTransport). Reproduce lo que
la migración 20261113120000 garantiza: propiedad por usuario (auth.uid()), clave foránea compuesta,
unicidad de cliente_id, restricciones de contenido y denegación de escrituras no permitidas. NO prueba la
política RLS real de Supabase: eso exige aplicar la migración y ejecutar supabase/sql_editor/08a_*.sql
y las pruebas de integración contra el proyecto (pendientes, ver docs/PRUEBAS_FASE_08A.md).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api.deps import get_conversation_service, get_principal
from app.errors import ConflictError, NotFoundError, SupabaseRejectedTokenError, ValidationFailedError
from app.main import create_app
from app.repositories.postgrest_client import PostgrestClient
from app.repositories.postgrest_conversaciones import PostgrestConversationRepository
from app.schemas.conversaciones import MensajeCrear
from app.security.principal import Principal
from app.services.conversation_service import ConversationService, normalizar_titulo

USUARIO_A = str(uuid.uuid4())
USUARIO_B = str(uuid.uuid4())
TOKENS = {"tok-A": USUARIO_A, "tok-B": USUARIO_B}
ROL_CONTENIDO = ("user", "assistant")
CONTEXTOS = {"academic", "finance", "tasks"}


def _error(status: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(status, json={"code": code, "message": message})


class PostgrestConversacionesSimulado:
    """Tablas en memoria con las mismas garantías de la migración 08A (simulación, no RLS real)."""

    def __init__(self) -> None:
        self.conversaciones: list[dict] = []
        self.mensajes: list[dict] = []
        self._reloj = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
        self.peticiones: list[tuple[str, str]] = []

    def _ahora(self) -> str:
        self._reloj += timedelta(seconds=1)
        return self._reloj.isoformat()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        usuario = TOKENS.get(token)
        tabla = request.url.path.rsplit("/", 1)[-1]
        self.peticiones.append((request.method, tabla))
        if usuario is None:
            return _error(401, "PGRST301", "JWT inválido")
        params = dict(request.url.params)
        cuerpo = json.loads(request.content) if request.content else None
        if tabla == "ai_conversations":
            return self._conversaciones(request.method, usuario, params, cuerpo)
        if tabla == "ai_messages":
            return self._mensajes(request.method, usuario, params, cuerpo)
        return _error(404, "PGRST205", "tabla no encontrada")

    # ----- conversaciones (RLS: solo filas del usuario) ----------------------
    def _conversaciones(self, metodo: str, usuario: str, params: dict, cuerpo: dict | None) -> httpx.Response:
        if metodo == "GET":
            filas = [c for c in self.conversaciones if c["user_id"] == usuario]
            if "id" in params:
                filas = [c for c in filas if c["id"] == params["id"].removeprefix("eq.")]
            filas.sort(key=lambda c: (c["updated_at"], c["id"]), reverse=True)
            return httpx.Response(200, json=[_publica(c) for c in _pagina(filas, params)])
        if metodo == "POST":
            if cuerpo and "user_id" in cuerpo and cuerpo["user_id"] != usuario:
                return _error(403, "42501", "new row violates row-level security policy")
            titulo = (cuerpo or {}).get("title", "Nueva conversación")
            if not titulo.strip() or len(titulo.strip()) > 120:
                return _error(400, "23514", "check constraint ai_conversations_title_check")
            ahora = self._ahora()
            fila = {"id": str(uuid.uuid4()), "user_id": usuario, "title": titulo,
                    "created_at": ahora, "updated_at": ahora}
            self.conversaciones.append(fila)
            return httpx.Response(201, json=[_publica(fila)])
        if metodo == "PATCH":
            filas = self._propias_por_id(usuario, params)
            for c in filas:
                c["title"] = cuerpo["title"]
                c["updated_at"] = self._ahora()
            return httpx.Response(200, json=[_publica(c) for c in filas])
        if metodo == "DELETE":
            filas = self._propias_por_id(usuario, params)
            ids = {c["id"] for c in filas}
            self.conversaciones = [c for c in self.conversaciones if c["id"] not in ids]
            self.mensajes = [m for m in self.mensajes if m["conversation_id"] not in ids]  # cascada
            return httpx.Response(200, json=[_publica(c) for c in filas])
        return _error(405, "PGRST000", "método no permitido")

    def _propias_por_id(self, usuario: str, params: dict) -> list[dict]:
        return [c for c in self.conversaciones
                if c["user_id"] == usuario and c["id"] == params.get("id", "").removeprefix("eq.")]

    # ----- mensajes (sin UPDATE ni DELETE directos; FK compuesta) ------------
    def _mensajes(self, metodo: str, usuario: str, params: dict, cuerpo: dict | None) -> httpx.Response:
        if metodo == "GET":
            filas = [m for m in self.mensajes if m["user_id"] == usuario]
            if "conversation_id" in params:
                filas = [m for m in filas if m["conversation_id"] == params["conversation_id"].removeprefix("eq.")]
            if "cliente_id" in params:
                filas = [m for m in filas if m["cliente_id"] == params["cliente_id"].removeprefix("eq.")]
            filas.sort(key=lambda m: m["orden"])
            return httpx.Response(200, json=[_publica_mensaje(m) for m in _pagina(filas, params)])
        if metodo == "POST":
            if cuerpo.get("user_id", usuario) != usuario:
                return _error(403, "42501", "new row violates row-level security policy")
            conv = cuerpo["conversation_id"]
            # Equivalente a la FK compuesta (user_id, conversation_id): la pareja debe existir.
            if not any(c["user_id"] == usuario and c["id"] == conv for c in self.conversaciones):
                return _error(409, "23503", "insert violates foreign key constraint ai_messages_conversacion_fk")
            if any(m["user_id"] == usuario and m["conversation_id"] == conv and m["cliente_id"] == cuerpo["cliente_id"]
                   for m in self.mensajes):
                return _error(409, "23505", "duplicate key value violates unique constraint ai_messages_cliente_key")
            if cuerpo["role"] not in ROL_CONTENIDO:
                return _error(400, "23514", "check constraint ai_messages_role_check")
            if not 1 <= len(cuerpo["content"].strip()) <= 8000:
                return _error(400, "23514", "check constraint ai_messages_content_check")
            if not set(cuerpo.get("contexto_usado", [])) <= CONTEXTOS:
                return _error(400, "23514", "check constraint ai_messages_contexto_usado_check")
            fila = {"id": str(uuid.uuid4()), "orden": len(self.mensajes) + 1, "user_id": usuario,
                    "conversation_id": conv, "cliente_id": cuerpo["cliente_id"], "role": cuerpo["role"],
                    "content": cuerpo["content"], "estado": cuerpo.get("estado", "completado"),
                    "proveedor": cuerpo.get("proveedor"), "modelo": cuerpo.get("modelo"),
                    "simulado": cuerpo.get("simulado"), "contexto_usado": cuerpo.get("contexto_usado", []),
                    "total_tokens": cuerpo.get("total_tokens"), "created_at": self._ahora()}
            self.mensajes.append(fila)
            for c in self.conversaciones:  # disparador: la conversación pasa a ser la más reciente
                if c["id"] == conv:
                    c["updated_at"] = self._ahora()
            return httpx.Response(201, json=[_publica_mensaje(fila)])
        # Sin políticas de UPDATE ni DELETE, PostgREST responde 403 (permiso denegado).
        return _error(403, "42501", "permission denied for table ai_messages")


def _publica(c: dict) -> dict:
    return {k: v for k, v in c.items() if k != "user_id"}


def _publica_mensaje(m: dict) -> dict:
    return {k: v for k, v in m.items() if k not in ("user_id", "orden")}


def _pagina(filas: list[dict], params: dict) -> list[dict]:
    desde = int(params.get("offset", 0))
    hasta = desde + int(params["limit"]) if "limit" in params else None
    return filas[desde:hasta]


@pytest.fixture
def simulado() -> PostgrestConversacionesSimulado:
    return PostgrestConversacionesSimulado()


@pytest.fixture
def servicio(simulado) -> ConversationService:
    cliente = PostgrestClient("https://proyecto-prueba.supabase.co", "clave-publica-de-prueba",
                              transport=httpx.MockTransport(simulado))
    return ConversationService(PostgrestConversationRepository(cliente))


def _principal(usuario: str) -> Principal:
    token = next(t for t, u in TOKENS.items() if u == usuario)
    return Principal(user_id=usuario, access_token=token)


A = _principal(USUARIO_A)
B = _principal(USUARIO_B)


def _mensaje(texto: str = "¿Cuál es mi promedio?", role: str = "user", cliente: uuid.UUID | None = None) -> MensajeCrear:
    return MensajeCrear(cliente_id=cliente or uuid.uuid4(), role=role, content=texto)


# ----- CRUD y paginación ------------------------------------------------------
def test_crear_y_listar_conversaciones_propias(servicio):
    servicio.crear(A, "Primera")
    servicio.crear(A, "Segunda")
    pagina = servicio.listar(A, limit=20, offset=0)
    assert [c.title for c in pagina.items] == ["Segunda", "Primera"]  # la más reciente primero
    assert pagina.siguiente is None


def test_paginacion_devuelve_siguiente_desplazamiento(servicio):
    for i in range(25):
        servicio.crear(A, f"Conversación {i}")
    primera = servicio.listar(A, limit=10, offset=0)
    segunda = servicio.listar(A, limit=10, offset=10)
    ultima = servicio.listar(A, limit=10, offset=20)
    assert len(primera.items) == 10 and primera.siguiente == 10
    assert len(segunda.items) == 10 and segunda.siguiente == 20
    assert len(ultima.items) == 5 and ultima.siguiente is None
    ids = [c.id for c in primera.items + segunda.items + ultima.items]
    assert len(set(ids)) == 25  # sin repetidos entre páginas


def test_paginacion_fuera_de_rango_se_rechaza(servicio):
    with pytest.raises(ValidationFailedError):
        servicio.listar(A, limit=0, offset=0)
    with pytest.raises(ValidationFailedError):
        servicio.listar(A, limit=101, offset=0)
    with pytest.raises(ValidationFailedError):
        servicio.listar(A, limit=10, offset=-1)


def test_titulo_normalizado_y_renombrado(servicio):
    creada = servicio.crear(A, "   ¿Cómo   va   mi   promedio?  ")
    assert creada.title == "¿Cómo va mi promedio?"
    renombrada = servicio.renombrar(A, creada.id, "Promedio académico")
    assert renombrada.title == "Promedio académico"


def test_titulo_vacio_usa_el_valor_por_defecto():
    assert normalizar_titulo("   ") == "Nueva conversación"
    assert normalizar_titulo(None) == "Nueva conversación"
    assert len(normalizar_titulo("x" * 500)) == 120


# ----- lecturas y escrituras cruzadas --------------------------------------------
def test_usuario_b_no_ve_ni_modifica_conversaciones_de_a(servicio):
    conv = servicio.crear(A, "Privada de A")
    servicio.guardar_mensaje(A, conv.id, _mensaje())
    with pytest.raises(NotFoundError):
        servicio.obtener(B, conv.id)
    with pytest.raises(NotFoundError):
        servicio.mensajes(B, conv.id, limit=50, offset=0)
    with pytest.raises(NotFoundError):
        servicio.renombrar(B, conv.id, "hackeada")
    with pytest.raises(NotFoundError):
        servicio.eliminar(B, conv.id, confirmar=True)
    assert servicio.listar(B, limit=20, offset=0).items == []
    # La conversación de A sigue intacta.
    assert servicio.obtener(A, conv.id).title == "Privada de A"
    assert len(servicio.mensajes(A, conv.id, limit=50, offset=0).items) == 1


def test_no_se_puede_escribir_en_conversacion_ajena(servicio):
    conv_b = servicio.crear(B, "De B")
    with pytest.raises(NotFoundError):
        servicio.guardar_mensaje(A, conv_b.id, _mensaje("intruso"))
    assert servicio.mensajes(B, conv_b.id, limit=50, offset=0).items == []


def test_el_navegador_no_puede_imponer_user_id(client_api):
    cliente, _ = client_api
    respuesta = cliente.post("/api/copilot/conversaciones", headers={"X-Usuario": "A"},
                             json={"title": "x", "user_id": USUARIO_B})
    assert respuesta.status_code == 422


# ----- mensajes: idempotencia e integridad --------------------------------------
def test_reenvio_con_el_mismo_cliente_id_no_duplica(servicio):
    conv = servicio.crear(A, "Chat")
    msg = _mensaje("Pregunta única")
    primera = servicio.guardar_mensaje(A, conv.id, msg)
    segunda = servicio.guardar_mensaje(A, conv.id, msg)
    assert primera.repetido is False
    assert segunda.repetido is True
    assert segunda.mensaje.id == primera.mensaje.id
    assert len(servicio.mensajes(A, conv.id, limit=50, offset=0).items) == 1


def test_mismo_cliente_id_con_otro_contenido_se_rechaza(servicio):
    conv = servicio.crear(A, "Chat")
    cliente = uuid.uuid4()
    servicio.guardar_mensaje(A, conv.id, _mensaje("uno", cliente=cliente))
    with pytest.raises(ConflictError):
        servicio.guardar_mensaje(A, conv.id, _mensaje("otro", cliente=cliente))


def test_carrera_en_el_guardado_no_duplica(simulado):
    """Otro envío llega entre la comprobación y el INSERT: debe devolverse el existente, sin duplicar."""
    cliente = PostgrestClient("https://proyecto-prueba.supabase.co", "clave", transport=httpx.MockTransport(simulado))
    repo = PostgrestConversationRepository(cliente)
    servicio = ConversationService(repo)
    conv = servicio.crear(A, "Chat")
    msg = _mensaje("carrera")
    servicio.guardar_mensaje(A, conv.id, msg)  # el "otro" envío ya guardó el mensaje

    original = repo.find_message_by_client
    llamadas = {"n": 0}

    def ocultar_la_primera_vez(principal, conversation_id, cliente_id):
        llamadas["n"] += 1
        return None if llamadas["n"] == 1 else original(principal, conversation_id, cliente_id)

    repo.find_message_by_client = ocultar_la_primera_vez  # type: ignore[method-assign]
    resultado = servicio.guardar_mensaje(A, conv.id, msg)
    assert resultado.repetido is True
    assert len(servicio.mensajes(A, conv.id, limit=50, offset=0).items) == 1


def test_mensajes_paginados_en_orden_de_insercion(servicio):
    conv = servicio.crear(A, "Chat")
    for i in range(7):
        servicio.guardar_mensaje(A, conv.id, _mensaje(f"mensaje {i}", role="user" if i % 2 == 0 else "assistant"))
    primera = servicio.mensajes(A, conv.id, limit=5, offset=0)
    segunda = servicio.mensajes(A, conv.id, limit=5, offset=5)
    assert [m.content for m in primera.items] == [f"mensaje {i}" for i in range(5)]
    assert primera.siguiente == 5
    assert [m.content for m in segunda.items] == ["mensaje 5", "mensaje 6"]
    assert segunda.siguiente is None


def test_metadatos_del_asistente_se_guardan_con_limites(servicio):
    conv = servicio.crear(A, "Chat")
    datos = MensajeCrear(cliente_id=uuid.uuid4(), role="assistant", content="Tu promedio es 3,47.",
                         proveedor="simulado", modelo="simulado-v1", simulado=True,
                         contexto_usado=["academic"], total_tokens=0, estado="completado")
    guardado = servicio.guardar_mensaje(A, conv.id, datos).mensaje
    assert guardado.proveedor == "simulado" and guardado.contexto_usado == ["academic"]


# ----- borrado con confirmación ----------------------------------------------
def test_borrado_exige_confirmacion_explicita(servicio):
    conv = servicio.crear(A, "Borrar")
    with pytest.raises(ValidationFailedError):
        servicio.eliminar(A, conv.id, confirmar=False)
    assert servicio.obtener(A, conv.id).id == conv.id


def test_borrado_confirmado_elimina_la_conversacion_y_sus_mensajes(servicio):
    conv = servicio.crear(A, "Borrar")
    servicio.guardar_mensaje(A, conv.id, _mensaje())
    servicio.eliminar(A, conv.id, confirmar=True)
    with pytest.raises(NotFoundError):
        servicio.obtener(A, conv.id)


# ----- errores de sesión y de servidor ----------------------------------------
def test_sin_token_la_operacion_se_rechaza(servicio):
    sin_token = Principal(user_id=USUARIO_A, access_token=None)
    with pytest.raises(SupabaseRejectedTokenError):
        servicio.listar(sin_token, limit=10, offset=0)


def test_token_rechazado_por_la_base_no_se_convierte_en_datos(simulado):
    cliente = PostgrestClient("https://proyecto-prueba.supabase.co", "clave", transport=httpx.MockTransport(simulado))
    servicio = ConversationService(PostgrestConversationRepository(cliente))
    caducado = Principal(user_id=USUARIO_A, access_token="token-caducado")
    with pytest.raises(Exception) as info:
        servicio.listar(caducado, limit=10, offset=0)
    assert getattr(info.value, "status_code", None) == 401


# ----- contratos HTTP ---------------------------------------------------------
@pytest.fixture
def client_api(simulado, servicio):
    app = create_app()

    def principal_de_prueba(request: Request) -> Principal:
        usuario = request.headers.get("X-Usuario", "")
        return {"A": A, "B": B}[usuario]

    app.dependency_overrides[get_principal] = principal_de_prueba
    app.dependency_overrides[get_conversation_service] = lambda: servicio
    with TestClient(app) as cliente:
        yield cliente, servicio
    app.dependency_overrides.clear()


def test_api_crud_y_aislamiento(client_api):
    cliente, _ = client_api
    creada = cliente.post("/api/copilot/conversaciones", headers={"X-Usuario": "A"}, json={"title": "Mi chat"})
    assert creada.status_code == 201
    conv_id = creada.json()["id"]
    assert cliente.get(f"/api/copilot/conversaciones/{conv_id}", headers={"X-Usuario": "B"}).status_code == 404
    assert cliente.get("/api/copilot/conversaciones", headers={"X-Usuario": "B"}).json()["items"] == []
    listada = cliente.get("/api/copilot/conversaciones?limit=5&offset=0", headers={"X-Usuario": "A"}).json()
    assert listada["items"][0]["id"] == conv_id


def test_api_guardar_mensaje_repetido_devuelve_repetido_true(client_api):
    cliente, _ = client_api
    conv_id = cliente.post("/api/copilot/conversaciones", headers={"X-Usuario": "A"}, json={}).json()["id"]
    cuerpo = {"cliente_id": str(uuid.uuid4()), "role": "user", "content": "hola"}
    primera = cliente.post(f"/api/copilot/conversaciones/{conv_id}/mensajes", headers={"X-Usuario": "A"}, json=cuerpo)
    segunda = cliente.post(f"/api/copilot/conversaciones/{conv_id}/mensajes", headers={"X-Usuario": "A"}, json=cuerpo)
    assert primera.status_code == 201 and primera.json()["repetido"] is False
    assert segunda.status_code == 201 and segunda.json()["repetido"] is True


def test_api_borrado_sin_confirmar_responde_422(client_api):
    cliente, _ = client_api
    conv_id = cliente.post("/api/copilot/conversaciones", headers={"X-Usuario": "A"}, json={}).json()["id"]
    assert cliente.delete(f"/api/copilot/conversaciones/{conv_id}", headers={"X-Usuario": "A"}).status_code == 422
    assert cliente.delete(f"/api/copilot/conversaciones/{conv_id}?confirmar=true", headers={"X-Usuario": "A"}).status_code == 204


def test_api_rechaza_contenido_fuera_de_limites(client_api):
    cliente, _ = client_api
    conv_id = cliente.post("/api/copilot/conversaciones", headers={"X-Usuario": "A"}, json={}).json()["id"]
    url = f"/api/copilot/conversaciones/{conv_id}/mensajes"
    base = {"cliente_id": str(uuid.uuid4()), "role": "user"}
    assert cliente.post(url, headers={"X-Usuario": "A"}, json={**base, "content": ""}).status_code == 422
    assert cliente.post(url, headers={"X-Usuario": "A"}, json={**base, "content": "x" * 8001}).status_code == 422
    assert cliente.post(url, headers={"X-Usuario": "A"}, json={**base, "content": "ok", "role": "system"}).status_code == 422
    assert cliente.post(url, headers={"X-Usuario": "A"},
                        json={**base, "content": "ok", "contexto_usado": ["contraseña"]}).status_code == 422
    assert cliente.post(url, headers={"X-Usuario": "A"},
                        json={**base, "content": "ok", "estado": "error"}).status_code == 422


def test_api_sin_persistencia_activa_responde_501(monkeypatch):
    """Con la flag en false (valor por defecto), el backend no finge guardar nada."""
    monkeypatch.delenv("AI_CONVERSACIONES_PERSISTENTES", raising=False)
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: A
    with TestClient(app) as cliente:
        respuesta = cliente.get("/api/copilot/conversaciones")
    app.dependency_overrides.clear()
    assert respuesta.status_code == 501
    assert "no está activa" in respuesta.json()["detail"]


def test_estado_del_copiloto_informa_persistencia():
    from app.ai.copilot_service import CopilotService, Limitador, LimitesCopiloto

    limitador = Limitador(LimitesCopiloto())
    apagado = CopilotService(None, None, limitador, "produccion")  # type: ignore[arg-type]
    encendido = CopilotService(None, None, limitador, "produccion", persistencia=True)  # type: ignore[arg-type]
    assert apagado.estado().persistencia is False
    assert encendido.estado().persistencia is True
