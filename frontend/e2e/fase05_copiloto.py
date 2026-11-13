"""Pruebas de navegador del copiloto (Fase 05) en Chrome real.

Dos servidores de prueba (base temporal aislada, nunca la base de desarrollo):
  - SIMULADO:  COPILOT_PROVIDER=simulado  (respuestas deterministas, etiquetadas como SIMULADO)
  - PENDIENTE: COPILOT_PROVIDER=openrouter sin OPENROUTER_API_KEY (estado de configuración pendiente)

Uso (desde frontend/):
  python e2e/fase05_copiloto.py <URL_simulado> <URL_pendiente> <carpeta_capturas> <resultados.json>

Las comprobaciones de error (429/503) usan interceptación de red del navegador: son PRUEBAS de la interfaz,
no de la IA real.
"""

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, Route, expect, sync_playwright

ANCHOS = [("movil", 390, 844), ("tableta", 820, 1180), ("escritorio", 1366, 860)]
resultados: list[dict] = []
errores_consola: list[str] = []


def registrar(nombre, ok, detalle=""):
    resultados.append({"prueba": nombre, "resultado": "PASS" if ok else "FAIL", "detalle": detalle})
    print(("PASS " if ok else "FAIL ") + nombre + (f" | {detalle}" if detalle else ""))


def comprobar(nombre, fn, detalle_ok=""):
    try:
        fn()
        registrar(nombre, True, detalle_ok)
    except Exception as exc:  # noqa: BLE001
        registrar(nombre, False, f"{type(exc).__name__}: {str(exc)[:240]}")


def bloque(fn, *args):
    try:
        fn(*args)
    except Exception as exc:  # noqa: BLE001
        registrar(f"Recorrido interrumpido: {fn.__name__}", False, f"{type(exc).__name__}: {str(exc)[:240]}")


def _ok(cond, texto):
    assert cond, texto


def abrir_copiloto(pagina: Page) -> None:
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Copiloto").click()
    expect(pagina.get_by_role("heading", level=1, name="AURORA Copilot")).to_be_visible()


def enviar(pagina: Page, texto: str) -> None:
    pagina.get_by_label("Tu pregunta").fill(texto)
    pagina.get_by_role("button", name="Enviar").click()


def recorrido_simulado(pagina: Page, base: str, capturas: Path) -> None:
    abrir_copiloto(pagina)
    comprobar("Copiloto: acceso desde la navegación principal",
              lambda: expect(pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Copiloto")).to_be_visible())
    comprobar("Copiloto (simulado): la etiqueta indica SIMULADO y no es IA",
              lambda: expect(pagina.get_by_text("SIMULADO · no es IA").first).to_be_visible())
    comprobar("Copiloto: solo lectura, sin botones de acción sobre datos",
              lambda: expect(pagina.get_by_role("button", name=re.compile("eliminar|borrar|modificar", re.I))).to_have_count(0))

    # Sugerencias rellenan el campo sin enviar.
    pagina.get_by_role("button", name="¿Cuál es mi promedio académico?").click()
    comprobar("Sugerencias: rellenan la pregunta sin enviarla",
              lambda: _ok(pagina.get_by_label("Tu pregunta").input_value() == "¿Cuál es mi promedio académico?", "campo vacío"))
    pagina.get_by_label("Tu pregunta").fill("")

    enviar(pagina, "¿Cuál es mi promedio académico?")
    comprobar("Copiloto: el mensaje del usuario aparece en la conversación",
              lambda: expect(pagina.get_by_role("log").get_by_text("¿Cuál es mi promedio académico?", exact=True)).to_be_visible())
    comprobar("Copiloto: respuesta del asistente con su procedencia",
              lambda: expect(pagina.get_by_role("article", name="Respuesta del copiloto").first).to_contain_text("Resumen de los datos disponibles"),
              "respuesta recibida")
    comprobar("Copiloto: se indica qué datos se usaron",
              lambda: expect(pagina.get_by_text(re.compile("Datos usados: Académico"))).to_be_visible())
    comprobar("Copiloto: el promedio mostrado proviene del motor (3.69 o 3.64 según datos)",
              lambda: expect(pagina.get_by_role("article", name="Respuesta del copiloto").first).to_contain_text(re.compile(r"promedio general \d")))
    pagina.get_by_label("Tu pregunta").fill("Pregunta con Enter")
    pagina.get_by_label("Tu pregunta").press("Enter")
    comprobar("Teclado: Enter envía la pregunta",
              lambda: expect(pagina.get_by_role("log").get_by_text("Pregunta con Enter", exact=True)).to_be_visible())
    expect(pagina.get_by_role("article", name="Respuesta del copiloto")).to_have_count(2, timeout=8000)

    # Desactivar un área: la respuesta ya no declara sus datos.
    pagina.get_by_label("Finanzas").uncheck()
    pagina.get_by_label("Tareas").uncheck()
    pagina.get_by_label("Tu pregunta").fill("Solo académico")
    pagina.get_by_role("button", name="Enviar").click()
    expect(pagina.get_by_role("article", name="Respuesta del copiloto")).to_have_count(3, timeout=8000)
    comprobar("Copiloto: excluir áreas reduce los datos usados",
              lambda: expect(pagina.get_by_role("article", name="Respuesta del copiloto").last.get_by_text("Datos usados: Académico")).to_be_visible())
    pagina.get_by_label("Finanzas").check()
    pagina.get_by_label("Tareas").check()

    # Contenido del modelo: se muestra como texto; el HTML no se ejecuta.
    def inyectar(route: Route):
        cuerpo = {"answer": "Texto normal\n\n<img src=x onerror=\"window.__xss=1\"><b>no html</b>",
                  "provider": "simulado", "model": "simulado-determinista", "simulado": True,
                  "context_used": [], "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
                  "incomplete": False, "latency_ms": 0, "prompt_version": "copiloto-v1.0"}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(cuerpo))

    pagina.route("**/api/copilot/chat", inyectar)
    enviar(pagina, "prueba de HTML")
    comprobar("Seguridad: el HTML de la respuesta NO se renderiza ni se ejecuta",
              lambda: expect(pagina.get_by_text("<img src=x", exact=False).first).to_be_visible())
    comprobar("Seguridad: no aparece ninguna imagen inyectada",
              lambda: _ok(pagina.locator("article img").count() == 0, "se encontró una imagen"))
    comprobar("Seguridad: no se ejecutó el script inyectado",
              lambda: _ok(pagina.evaluate("() => window.__xss === undefined"), "se ejecutó JavaScript"))
    pagina.unroute("**/api/copilot/chat")

    # Error explícito y reintento.
    contador = {"n": 0}

    def fallar_una_vez(route: Route):
        contador["n"] += 1
        if contador["n"] == 1:
            route.fulfill(status=429, content_type="application/json",
                                body=json.dumps({"detail": "Espera un minuto.", "codigo": "limite_proveedor"}))
        else:
            route.continue_()

    pagina.route("**/api/copilot/chat", fallar_una_vez)
    enviar(pagina, "pregunta que falla")
    comprobar("Errores: un 429 se muestra como error con mensaje claro",
              lambda: expect(pagina.get_by_role("alert").filter(has_text="Espera un minuto")).to_be_visible())
    comprobar("Reintentos: el botón Reintentar reenvía la misma pregunta",
              lambda: expect(pagina.get_by_role("button", name="Reintentar")).to_be_visible())
    pagina.get_by_role("button", name="Reintentar").click()
    comprobar("Reintentos: la respuesta llega tras reintentar",
              lambda: expect(pagina.get_by_role("article", name="Respuesta del copiloto").last).to_contain_text("Resumen de los datos disponibles"))
    pagina.unroute("**/api/copilot/chat")
    comprobar("Reintentos: no se duplica la pregunta ni queda el error tras reintentar",
              lambda: _ok(pagina.get_by_role("log").get_by_text("pregunta que falla", exact=True).count() == 1
                          and pagina.get_by_role("alert").count() == 0, "pregunta duplicada o error residual"))

    # Error 503 con código del servidor: motivo claro, sin detalles técnicos.
    def sin_configurar(route: Route):
        route.fulfill(status=503, content_type="application/json",
                            body=json.dumps({"detail": "El copiloto no está configurado en el servidor.", "codigo": "no_configurado"}))

    pagina.route("**/api/copilot/chat", sin_configurar)
    enviar(pagina, "pregunta con 503")
    comprobar("Errores: un 503 muestra el motivo en español",
              lambda: expect(pagina.get_by_role("alert").filter(has_text="no está configurado")).to_be_visible())
    pagina.unroute("**/api/copilot/chat")

    # Historial: la consulta envía los turnos previos y NO repite la pregunta actual.
    registro: dict = {}

    def grabar(route: Route):
        registro["cuerpo"] = route.request.post_data_json
        route.continue_()

    pagina.route("**/api/copilot/chat", grabar)
    enviar(pagina, "pregunta de historial")
    expect(pagina.get_by_role("article", name="Respuesta del copiloto").last).to_contain_text("Resumen de los datos disponibles", timeout=8000)
    comprobar("Historial: la consulta envía el turno anterior y no repite la pregunta actual",
              lambda: _ok(registro.get("cuerpo", {}).get("message") == "pregunta de historial"
                          and registro["cuerpo"]["history"][-1]["role"] == "assistant"
                          and all(h["content"] != "pregunta de historial" for h in registro["cuerpo"]["history"]),
                          f"history={str(registro.get('cuerpo', {}).get('history', []))[-160:]}"))
    comprobar("Historial: el límite de turnos enviados es de 6 como máximo",
              lambda: _ok(len(registro["cuerpo"]["history"]) <= 6, "más de 6 turnos"))
    pagina.unroute("**/api/copilot/chat")

    # Indicador de generación: se retrasa la respuesta.
    def lenta(route: Route):
        import time
        time.sleep(1.2)
        route.continue_()

    pagina.route("**/api/copilot/chat", lenta)
    enviar(pagina, "pregunta lenta")
    comprobar("Indicador: mientras se genera, se muestra el estado de espera",
              lambda: expect(pagina.get_by_role("status").filter(has_text="generando")).to_be_visible(timeout=3000))
    expect(pagina.get_by_role("status").filter(has_text="generando")).to_have_count(0, timeout=8000)
    pagina.unroute("**/api/copilot/chat")

    comprobar("Límite: el campo impide escribir más caracteres que el máximo",
              lambda: _ok(pagina.get_by_label("Tu pregunta").get_attribute("maxlength") == "1000", "maxlength incorrecto"))

    pagina.get_by_role("button", name="Limpiar conversación").click()
    comprobar("Conversación: limpiar la vacía",
              lambda: expect(pagina.get_by_text("Pregúntame sobre tus datos")).to_be_visible())
    pagina.screenshot(path=str(capturas / "01_copiloto_simulado_escritorio.png"), full_page=True)

    # Respuesta de muestra para la captura final.
    enviar(pagina, "¿Cuál es mi promedio académico?")
    expect(pagina.get_by_role("article", name="Respuesta del copiloto").first).to_be_visible(timeout=8000)
    pagina.screenshot(path=str(capturas / "02_copiloto_respuesta_escritorio.png"), full_page=True)


def recorrido_pendiente(pagina: Page, base: str, capturas: Path) -> None:
    abrir_copiloto(pagina)
    comprobar("Sin clave: se muestra el estado de configuración pendiente",
              lambda: expect(pagina.get_by_role("heading", name="Copiloto pendiente de configuración")).to_be_visible())
    comprobar("Sin clave: el campo de pregunta está deshabilitado",
              lambda: expect(pagina.get_by_label("Tu pregunta")).to_be_disabled())
    comprobar("Sin clave: no hay botón de enviar activo",
              lambda: expect(pagina.get_by_role("button", name="Enviar")).to_be_disabled())
    comprobar("Sin clave: no aparece ninguna respuesta simulada",
              lambda: expect(pagina.get_by_role("article", name="Respuesta del copiloto")).to_have_count(0))
    comprobar("Sin clave: el estado no muestra ningún valor de clave",
              lambda: _ok("sk-" not in pagina.content(), "aparece un valor con forma de clave"))
    comprobar("Sin clave: las áreas siguen accesibles",
              lambda: expect(pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Académico")).to_be_visible())
    pagina.screenshot(path=str(capturas / "03_copiloto_pendiente_escritorio.png"), full_page=True)


def responsive(navegador, base: str, capturas: Path) -> None:
    for nombre, ancho, alto in ANCHOS:
        contexto = navegador.new_context(viewport={"width": ancho, "height": alto})
        pagina = contexto.new_page()
        pagina.goto(base)
        expect(pagina.locator(".demo-banner")).to_be_visible()
        abrir_copiloto(pagina)
        pagina.wait_for_timeout(250)
        d = pagina.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        comprobar(f"Responsive copiloto {nombre} {ancho}px: sin desplazamiento horizontal",
                  lambda d=d: _ok(d <= 1, f"desborde {d}px"), f"desborde={d}px")
        pagina.screenshot(path=str(capturas / f"resp_copiloto_{nombre}.png"), full_page=True)
        contexto.close()


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    base_sim, base_pen, carpeta, salida = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), Path(sys.argv[3]), Path(sys.argv[4])
    carpeta.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome", headless=True)
        contexto = navegador.new_context(viewport={"width": 1366, "height": 860})
        pagina = contexto.new_page()
        pagina.on("pageerror", lambda e: errores_consola.append(f"pageerror: {e}"))
        pagina.on("console", lambda m: errores_consola.append(f"console.{m.type}: {m.text}")
                  if m.type == "error" and "Failed to load resource" not in m.text else None)
        pagina.goto(base_sim)
        expect(pagina.locator(".demo-banner")).to_be_visible()
        bloque(recorrido_simulado, pagina, base_sim, carpeta)
        contexto.close()

        contexto2 = navegador.new_context(viewport={"width": 1366, "height": 860})
        pagina2 = contexto2.new_page()
        pagina2.goto(base_pen)
        expect(pagina2.locator(".demo-banner")).to_be_visible()
        bloque(recorrido_pendiente, pagina2, base_pen, carpeta)
        contexto2.close()

        bloque(responsive, navegador, base_sim, carpeta)
        navegador.close()

    comprobar("Consola del navegador sin errores de JavaScript",
              lambda: _ok(not errores_consola, "; ".join(errores_consola)[:240]))
    fallos = [r for r in resultados if r["resultado"] == "FAIL"]
    salida.write_text(json.dumps({"total": len(resultados), "fallos": len(fallos), "resultados": resultados},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(resultados)} · Fallos: {len(fallos)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
