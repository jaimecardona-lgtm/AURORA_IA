"""Fase 08A · Interfaz de conversaciones persistidas con BACKEND SIMULADO EN EL NAVEGADOR (route mock).

LO QUE PRUEBA: el comportamiento de React (CopilotProvider, página y widget) cuando el servidor informa
persistencia = true: carga del historial, guardado de pregunta y respuesta, reintentos, idempotencia de
envíos, borrado con confirmación y ausencia de credenciales en las peticiones.

LO QUE NO PRUEBA: la base de datos ni la política RLS. El almacén es un diccionario en memoria del propio
script; la migración 20261113120000 y las pruebas contra Supabase siguen pendientes (docs/PRUEBAS_FASE_08A.md).

Requisitos: frontend en http://127.0.0.1:5173 (o el indicado). El resto de rutas /api se reenvían al servidor real.
Uso (desde la raíz del repositorio):
  backend\\.venv\\Scripts\\python.exe frontend\\e2e\\fase08a_persistencia_simulada.py http://127.0.0.1:5175 visual-evidence\\fase-08a\\persistencia-simulada
"""

import json
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Route, expect, sync_playwright

ESTADO_BASE = {
    "configurado": True, "proveedor": "simulado", "modelo": "simulado-determinista", "simulado": True,
    "modo": "demo", "max_mensaje": 1000, "max_turnos_historial": 6,
    "mensaje": "Respuestas SIMULADAS para desarrollo. No son inteligencia artificial.", "persistencia": True,
}
resultados: list[dict] = []


def registrar(nombre: str, ok: bool, detalle: str = "") -> None:
    resultados.append({"prueba": nombre, "resultado": "PASS" if ok else "FAIL", "detalle": detalle})
    print(("PASS " if ok else "FAIL ") + nombre + (f" | {detalle}" if detalle else ""), flush=True)


class AlmacenSimulado:
    """Almacén en memoria con las reglas que aplicará la base: idempotencia por cliente_id y orden estable."""

    def __init__(self) -> None:
        self.conversaciones: dict[str, dict] = {}
        self.reloj = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)
        self.contadores = {"chat": 0, "post_usuario": 0, "post_asistente": 0}
        self.fallar_chat = 0
        self.fallar_guardado_asistente = 0
        self.cuerpos_enviados: list[str] = []
        self.sembrar_previa()

    def ahora(self) -> str:
        self.reloj += timedelta(seconds=1)
        return self.reloj.isoformat()

    def sembrar_previa(self) -> None:
        cid = self.crear("Conversación previa")
        self.anadir(cid, "user", "¿Cuál es mi promedio?", cliente=str(uuid.uuid4()))
        self.anadir(cid, "assistant", "Tu promedio es 3,47.", cliente=str(uuid.uuid4()))

    def crear(self, titulo: str) -> str:
        cid = str(uuid.uuid4())
        ahora = self.ahora()
        self.conversaciones[cid] = {"id": cid, "title": titulo, "created_at": ahora, "updated_at": ahora, "mensajes": []}
        return cid

    def anadir(self, cid: str, role: str, content: str, cliente: str, **meta) -> dict:
        mensaje = {"id": str(uuid.uuid4()), "cliente_id": cliente, "role": role, "content": content,
                   "estado": meta.get("estado", "completado"), "proveedor": meta.get("proveedor"),
                   "modelo": meta.get("modelo"), "simulado": meta.get("simulado"),
                   "contexto_usado": meta.get("contexto_usado", []), "total_tokens": meta.get("total_tokens"),
                   "created_at": self.ahora()}
        self.conversaciones[cid]["mensajes"].append(mensaje)
        self.conversaciones[cid]["updated_at"] = mensaje["created_at"]
        return mensaje

    def mensajes_de(self, texto_parcial: str, role: str | None = None) -> int:
        return sum(1 for c in self.conversaciones.values() for m in c["mensajes"]
                   if texto_parcial in m["content"] and (role is None or m["role"] == role))

    def total_mensajes(self) -> int:
        return sum(len(c["mensajes"]) for c in self.conversaciones.values())


def json_resp(route: Route, status: int, cuerpo) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(cuerpo) if cuerpo is not None else "")


def manejar(almacen: AlmacenSimulado):
    def _manejar(route: Route) -> None:
        peticion = route.request
        ruta = urlparse(peticion.url)
        if not ruta.path.startswith("/api/copilot"):
            return route.continue_()
        metodo = peticion.method
        cuerpo_texto = peticion.post_data or ""
        if cuerpo_texto:
            almacen.cuerpos_enviados.append(cuerpo_texto)
        cuerpo = json.loads(cuerpo_texto) if cuerpo_texto else None
        partes = [p for p in ruta.path.split("/") if p]  # api, copilot, ...
        if ruta.path == "/api/copilot/estado":
            return json_resp(route, 200, ESTADO_BASE)
        if ruta.path == "/api/copilot/chat" and metodo == "POST":
            almacen.contadores["chat"] += 1
            if almacen.fallar_chat > 0:
                almacen.fallar_chat -= 1
                return json_resp(route, 503, {"detail": "El proveedor no responde. Intenta de nuevo."})
            return json_resp(route, 200, {
                "answer": f"Respuesta simulada a: {cuerpo['message']}", "provider": "simulado",
                "model": "simulado-determinista", "simulado": True, "context_used": ["academic"],
                "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": 0},
                "incomplete": False, "latency_ms": 1, "prompt_version": "copiloto-v1.1",
            })
        if partes[:3] == ["api", "copilot", "conversaciones"]:
            if len(partes) == 3:
                if metodo == "GET":
                    orden = sorted(almacen.conversaciones.values(), key=lambda c: c["updated_at"], reverse=True)
                    limite = int(parse_qs(ruta.query).get("limit", ["20"])[0])
                    desde = int(parse_qs(ruta.query).get("offset", ["0"])[0])
                    items = [{k: v for k, v in c.items() if k != "mensajes"} for c in orden[desde:desde + limite]]
                    siguiente = desde + limite if len(orden) > desde + limite else None
                    return json_resp(route, 200, {"items": items, "siguiente": siguiente})
                if metodo == "POST":
                    titulo = (cuerpo or {}).get("title") or "Nueva conversación"
                    cid = almacen.crear(titulo)
                    return json_resp(route, 201, {k: v for k, v in almacen.conversaciones[cid].items() if k != "mensajes"})
            cid = partes[3]
            if cid not in almacen.conversaciones:
                return json_resp(route, 404, {"detail": "La conversación no existe o no es accesible."})
            if len(partes) == 4 and metodo == "PATCH":
                almacen.conversaciones[cid]["title"] = cuerpo["title"]
                return json_resp(route, 200, {k: v for k, v in almacen.conversaciones[cid].items() if k != "mensajes"})
            if len(partes) == 4 and metodo == "DELETE":
                if "confirmar=true" not in ruta.query:
                    return json_resp(route, 422, {"detail": "Confirma el borrado."})
                del almacen.conversaciones[cid]
                return json_resp(route, 204, None)
            if len(partes) == 5 and partes[4] == "mensajes" and metodo == "GET":
                limite = int(parse_qs(ruta.query).get("limit", ["100"])[0])
                desde = int(parse_qs(ruta.query).get("offset", ["0"])[0])
                todos = almacen.conversaciones[cid]["mensajes"]
                return json_resp(route, 200, {"items": todos[desde:desde + limite],
                                              "siguiente": desde + limite if len(todos) > desde + limite else None})
            if len(partes) == 5 and partes[4] == "mensajes" and metodo == "POST":
                existente = next((m for m in almacen.conversaciones[cid]["mensajes"] if m["cliente_id"] == cuerpo["cliente_id"]), None)
                if existente:
                    return json_resp(route, 201, {"mensaje": existente, "repetido": True})
                if cuerpo["role"] == "user":
                    almacen.contadores["post_usuario"] += 1
                else:
                    almacen.contadores["post_asistente"] += 1
                    if almacen.fallar_guardado_asistente > 0:
                        almacen.fallar_guardado_asistente -= 1
                        return json_resp(route, 503, {"detail": "El servicio de datos no está disponible en este momento."})
                nuevo = almacen.anadir(cid, cuerpo["role"], cuerpo["content"], cuerpo["cliente_id"],
                                       proveedor=cuerpo.get("proveedor"), modelo=cuerpo.get("modelo"),
                                       simulado=cuerpo.get("simulado"), contexto_usado=cuerpo.get("contexto_usado", []),
                                       total_tokens=cuerpo.get("total_tokens"), estado=cuerpo.get("estado", "completado"))
                return json_resp(route, 201, {"mensaje": nuevo, "repetido": False})
        return json_resp(route, 404, {"detail": "ruta no simulada"})
    return _manejar


def esperar_respuesta(pagina: Page, texto: str, timeout: int = 15000) -> None:
    expect(pagina.get_by_label("Respuesta del copiloto").filter(has_text=texto).first).to_be_visible(timeout=timeout)


def ir_a_copiloto(pagina: Page) -> None:
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Copiloto").click()
    pagina.wait_for_timeout(500)


def comprobar(nombre: str, fn) -> bool:
    try:
        fn()
        registrar(nombre, True)
        return True
    except AssertionError as exc:
        registrar(nombre, False, str(exc)[:200])
    except Exception as exc:  # noqa: BLE001 - se registra y se sigue con las demás
        registrar(nombre, False, f"{type(exc).__name__}: {str(exc)[:200]}")
    return False


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    base, carpeta = sys.argv[1].rstrip("/"), Path(sys.argv[2])
    carpeta.mkdir(parents=True, exist_ok=True)
    almacen = AlmacenSimulado()
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome", headless=True)
        contexto = navegador.new_context(viewport={"width": 1440, "height": 900})
        contexto.route("**/api/**", manejar(almacen))
        pagina = contexto.new_page()
        pagina.goto(base)
        pagina.get_by_role("navigation", name="Módulos").wait_for(timeout=20000)

        # 1. Carga inicial: el historial del servidor aparece y la interfaz lo presenta como guardado.
        ir_a_copiloto(pagina)
        comprobar("Carga · el historial del servidor se muestra al abrir el copiloto",
                  lambda: esperar_respuesta(pagina, "Tu promedio es 3,47."))
        comprobar("Carga · la nota indica guardado en la cuenta",
                  lambda: expect(pagina.get_by_text("Guardadas en tu cuenta")).to_be_visible())
        comprobar("Carga · la conversación previa aparece en la lista",
                  lambda: expect(pagina.get_by_role("button", name="Conversación previa")).to_be_visible())

        # 2. Envío: se guarda la pregunta y la respuesta, una vez cada una.
        pregunta = "¿Cuántas tareas están vencidas?"
        antes_chat, antes_u, antes_a = almacen.contadores["chat"], almacen.contadores["post_usuario"], almacen.contadores["post_asistente"]
        pagina.locator("#pregunta-copiloto").fill(pregunta)
        pagina.get_by_role("button", name="Enviar").first.click()
        comprobar("Envío · la respuesta aparece", lambda: esperar_respuesta(pagina, f"Respuesta simulada a: {pregunta}"))
        pagina.wait_for_timeout(800)
        comprobar("Envío · una sola consulta al copiloto", lambda: _igual(almacen.contadores["chat"] - antes_chat, 1))
        comprobar("Envío · la pregunta se guarda una vez", lambda: _igual(almacen.contadores["post_usuario"] - antes_u, 1))
        comprobar("Envío · la respuesta se guarda una vez", lambda: _igual(almacen.contadores["post_asistente"] - antes_a, 1))
        comprobar("Envío · el servidor tiene pregunta y respuesta (sin duplicados)",
                  lambda: _igual(almacen.mensajes_de(pregunta), 2))

        # 3. Recarga: el historial sigue ahí, recuperado del servidor.
        pagina.reload()
        pagina.get_by_role("navigation", name="Módulos").wait_for(timeout=20000)
        ir_a_copiloto(pagina)
        comprobar("Recarga · el historial se recupera tras recargar la página",
                  lambda: esperar_respuesta(pagina, f"Respuesta simulada a: {pregunta}"))

        # 4. Fallo al guardar la respuesta: reintentar guarda sin volver a consultar al modelo.
        almacen.fallar_guardado_asistente = 1
        chat_antes = almacen.contadores["chat"]
        pregunta_b = "¿Qué gastos debería revisar primero?"
        pagina.locator("#pregunta-copiloto").fill(pregunta_b)
        pagina.get_by_role("button", name="Enviar").first.click()
        comprobar("Guardado fallido · se muestra el error con reintento",
                  lambda: expect(pagina.locator(".chat__burbuja--error").filter(has_text="no está disponible")).to_be_visible(timeout=15000))
        comprobar("Guardado fallido · el modelo se consultó una sola vez", lambda: _igual(almacen.contadores["chat"] - chat_antes, 1))
        pagina.locator(".chat__burbuja--error").get_by_role("button", name="Reintentar").click()
        comprobar("Guardado fallido · el reintento guarda la respuesta",
                  lambda: esperar_respuesta(pagina, f"Respuesta simulada a: {pregunta_b}"))
        pagina.wait_for_timeout(800)
        comprobar("Guardado fallido · el reintento no vuelve a consultar al modelo", lambda: _igual(almacen.contadores["chat"] - chat_antes, 1))
        comprobar("Guardado fallido · pregunta y respuesta guardadas una sola vez",
                  lambda: _igual(almacen.mensajes_de(pregunta_b), 2))

        # 5. Fallo del modelo: reintentar no duplica la pregunta ya guardada.
        almacen.fallar_chat = 1
        pregunta_c = "¿Cómo organizo mi semana?"
        pagina.locator("#pregunta-copiloto").fill(pregunta_c)
        pagina.get_by_role("button", name="Enviar").first.click()
        comprobar("Fallo del modelo · se muestra el error con reintento",
                  lambda: expect(pagina.locator(".chat__burbuja--error").filter(has_text="no responde")).to_be_visible(timeout=15000))
        pagina.locator(".chat__burbuja--error").get_by_role("button", name="Reintentar").click()
        comprobar("Fallo del modelo · el reintento responde", lambda: esperar_respuesta(pagina, f"Respuesta simulada a: {pregunta_c}"))
        pagina.wait_for_timeout(800)
        comprobar("Fallo del modelo · la pregunta queda guardada una sola vez", lambda: _igual(almacen.mensajes_de(pregunta_c, "user"), 1))

        # 6. Nueva conversación con título derivado de la primera pregunta.
        pagina.get_by_role("button", name="Nueva conversación", exact=True).first.click()
        pregunta_d = "Mi primera pregunta de prueba para el título"
        pagina.locator("#pregunta-copiloto").fill(pregunta_d)
        pagina.get_by_role("button", name="Enviar").first.click()
        comprobar("Nueva · la conversación nueva recibe la respuesta", lambda: esperar_respuesta(pagina, f"Respuesta simulada a: {pregunta_d}"))
        comprobar("Nueva · el título se deriva de la primera pregunta",
                  lambda: expect(pagina.get_by_role("button", name=re.compile("Mi primera pregunta de prueba"))).to_be_visible(timeout=10000))
        comprobar("Nueva · la conversación anterior sigue en la lista",
                  lambda: expect(pagina.get_by_role("button", name="Conversación previa")).to_be_visible())

        # 7. Widget y página comparten la misma conversación.
        pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Mi espacio").click()
        pagina.get_by_role("button", name=re.compile("Habla con AURORA")).click()
        pregunta_e = "Pregunta desde el widget"
        pagina.locator("#pregunta-widget").fill(pregunta_e)
        pagina.get_by_role("button", name="Enviar").last.click()
        comprobar("Widget · responde en la conversación activa", lambda: esperar_respuesta(pagina, f"Respuesta simulada a: {pregunta_e}"))
        pagina.keyboard.press("Escape")
        ir_a_copiloto(pagina)
        comprobar("Widget · la pregunta aparece en la página completa",
                  lambda: esperar_respuesta(pagina, f"Respuesta simulada a: {pregunta_e}"))

        # 8. Privacidad: ninguna petición lleva credenciales ni tokens.
        comprobar("Privacidad · ninguna petición al copiloto incluye credenciales",
                  lambda: _igual(sum(1 for c in almacen.cuerpos_enviados if "eyJ" in c or "Bearer" in c or "password" in c.lower()), 0))

        # 9. Borrado con confirmación explícita.
        activa = next(k for k, v in almacen.conversaciones.items() if v["title"].startswith("Mi primera pregunta"))
        pagina.once("dialog", lambda d: d.accept())
        pagina.get_by_role("button", name="Limpiar conversación").click()
        comprobar("Borrado · la conversación activa desaparece del servidor", lambda: _igual(activa in almacen.conversaciones, False))
        comprobar("Borrado · sus mensajes se eliminan en cascada",
                  lambda: _igual(almacen.mensajes_de("Mi primera pregunta de prueba"), 0))
        comprobar("Borrado · la conversación previa no se toca",
                  lambda: _igual(any(v["title"] == "Conversación previa" for v in almacen.conversaciones.values()), True))
        pagina.screenshot(path=str(carpeta / "copiloto_persistencia_simulada.png"), full_page=True)

        navegador.close()

    total = len(resultados)
    fallos = sum(1 for r in resultados if r["resultado"] == "FAIL")
    salida = {
        "tipo": "backend simulado en el navegador (route mock): valida la interfaz, no la base de datos",
        "total": total, "fallos": fallos, "resultados": resultados,
    }
    (carpeta / "resultados.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {total} · Fallos: {fallos}", flush=True)
    return 0 if fallos == 0 else 1


def _igual(obtenido, esperado) -> None:
    assert obtenido == esperado, f"obtenido={obtenido} esperado={esperado}"


if __name__ == "__main__":
    raise SystemExit(main())
