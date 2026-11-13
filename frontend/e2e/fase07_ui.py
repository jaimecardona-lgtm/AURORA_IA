"""Fase 07 · Verificación de la interfaz del copiloto (widget + página completa) en Chrome, headless.

Requiere la aplicación de demostración con el proveedor SIMULADO (no es IA) y la clave de OpenRouter vacía:
  APP_ENV=development PERSISTENCE_BACKEND=sqlite DEMO_MODE=true COPILOT_PROVIDER=simulado OPENROUTER_API_KEY= \
  python -m uvicorn app.main:app --port 8766        (desde backend/, con una base SQLite temporal)

Uso (desde frontend/):
  python e2e/fase07_ui.py http://127.0.0.1:8766 <carpeta_capturas> <resultados.json>

No usa cuentas reales ni Supabase. Cuenta las peticiones a /api/copilot/chat para verificar que no hay duplicados.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

resultados: list[dict] = []
peticiones_chat: list[str] = []


def registrar(nombre: str, ok: bool, detalle: str = "") -> None:
    resultados.append({"prueba": nombre, "resultado": "PASS" if ok else "FAIL", "detalle": detalle})
    print(("PASS " if ok else "FAIL ") + nombre + (f" | {detalle}" if detalle else ""), flush=True)


def comprobar(nombre: str, fn, detalle: str = "") -> bool:
    try:
        fn()
        registrar(nombre, True, detalle)
        return True
    except Exception as exc:  # noqa: BLE001
        registrar(nombre, False, f"{type(exc).__name__}: {str(exc)[:200]}")
        return False


def _ok(cond: bool, texto: str) -> None:
    assert cond, texto


def widget(pagina: Page):
    return pagina.get_by_role("dialog", name="Habla con AURORA ✦")


def enviar_en_widget(pagina: Page, texto: str) -> None:
    antes = len(peticiones_chat)
    pagina.get_by_label("Tu pregunta").last.fill(texto)
    pagina.get_by_role("dialog", name="Habla con AURORA ✦").get_by_role("button", name="Enviar").click()
    expect(widget(pagina).get_by_role("article", name="Respuesta del copiloto").last).to_be_visible(timeout=10000)
    assert len(peticiones_chat) == antes + 1, f"se enviaron {len(peticiones_chat) - antes} peticiones para un mensaje"


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    base, carpeta, salida = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
    carpeta.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome", headless=True)
        contexto = navegador.new_context(viewport={"width": 1366, "height": 860})
        pagina = contexto.new_page()
        pagina.on("request", lambda r: peticiones_chat.append(r.url) if r.method == "POST" and "/api/copilot/chat" in r.url else None)
        pagina.goto(base)
        expect(pagina.locator(".demo-banner")).to_be_visible(timeout=15000)

        boton = pagina.locator(".copiloto-flotante")
        comprobar("Widget: botón flotante «Habla con AURORA ✦» visible", lambda: expect(boton).to_be_visible(), "")
        caja = boton.bounding_box() or {}
        comprobar("Widget: botón en la esquina inferior derecha",
                  lambda: _ok(caja.get("x", 0) > 1366 * 0.7 and caja.get("y", 0) > 860 * 0.7, str(caja)))

        # Apertura y cierre sin cambiar de página.
        url_antes = pagina.url
        boton.click()
        comprobar("Widget: se abre sin cambiar de página", lambda: expect(widget(pagina)).to_be_visible(), f"url={pagina.url == url_antes}")
        comprobar("Widget: el foco entra en el campo al abrir",
                  lambda: _ok(pagina.evaluate("() => document.activeElement && document.activeElement.tagName") == "TEXTAREA", ""))
        comprobar("Widget: el ancho en escritorio es de unos 400 px",
                  lambda: _ok(340 <= (widget(pagina).bounding_box() or {}).get("width", 0) <= 420, str(widget(pagina).bounding_box())))
        pagina.screenshot(path=str(carpeta / "01_widget_abierto_escritorio.png"))
        pagina.keyboard.press("Escape")
        comprobar("Widget: Escape cierra el panel", lambda: expect(widget(pagina)).to_have_count(0))
        comprobar("Widget: al cerrar, el foco vuelve al botón", lambda: expect(boton).to_be_focused())

        # Enviar desde el widget (una sola petición).
        boton.click()
        enviar_en_widget(pagina, "¿Cuál es mi promedio académico?")
        comprobar("Widget: respuesta marcada como simulada (no es IA)",
                  lambda: expect(widget(pagina).get_by_text("Simulado · no es IA").first).to_be_visible())

        # Expandir a la página completa: la conversación debe continuar.
        widget(pagina).get_by_role("button", name="Abrir el chat completo").click()
        expect(pagina.get_by_role("heading", level=1, name="AURORA Copilot")).to_be_visible()
        comprobar("Expandir: el widget se oculta sobre la página completa",
                  lambda: expect(pagina.locator(".copiloto-flotante")).to_have_count(0))
        comprobar("Expandir: la pregunta enviada desde el widget aparece en la página completa",
                  lambda: expect(pagina.get_by_role("log").get_by_text("¿Cuál es mi promedio académico?", exact=True)).to_be_visible())
        comprobar("Expandir: la respuesta también aparece en la página completa",
                  lambda: expect(pagina.get_by_role("log").get_by_role("article", name="Respuesta del copiloto").first).to_be_visible())

        # Enviar desde la página completa: el widget (al volver) debe mostrar la misma conversación.
        antes = len(peticiones_chat)
        pagina.get_by_label("Tu pregunta", exact=True).fill("¿En qué categoría estoy gastando más?")
        pagina.get_by_role("button", name="Enviar", exact=True).click()
        expect(pagina.get_by_role("log").get_by_role("article", name="Respuesta del copiloto")).to_have_count(2, timeout=10000)
        comprobar("Página completa: un envío genera una sola petición", lambda: _ok(len(peticiones_chat) == antes + 1, f"{len(peticiones_chat) - antes}"))

        # Navegar a otra sección y volver: el historial de la sesión se conserva.
        pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Académico").click()
        pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Copiloto").click()
        comprobar("Navegación: al volver al copiloto se conserva la conversación",
                  lambda: expect(pagina.get_by_role("log").get_by_role("article", name="Respuesta del copiloto")).to_have_count(2))
        comprobar("Navegación: el widget vuelve a aparecer en otras secciones (no en el copiloto)",
                  lambda: expect(pagina.locator(".copiloto-flotante")).to_have_count(0))

        # Conversaciones: crear una nueva y comprobar que la anterior sigue en el listado.
        pagina.get_by_role("button", name="Nueva conversación").click()
        comprobar("Conversaciones: «Nueva conversación» muestra el estado inicial",
                  lambda: expect(pagina.get_by_text("Pregúntame sobre tus datos")).to_be_visible())
        comprobar("Conversaciones: la conversación anterior sigue en el panel lateral (dos entradas)",
                  lambda: expect(pagina.get_by_role("list", name="Lista de conversaciones").get_by_role("button")).to_have_count(2))
        pagina.get_by_role("button", name="Ocultar conversaciones").click()
        comprobar("Conversaciones: el panel lateral se puede ocultar",
                  lambda: expect(pagina.locator("#panel-conversaciones")).to_be_hidden())
        pagina.get_by_role("button", name="Mostrar conversaciones").click()
        pagina.screenshot(path=str(carpeta / "02_copiloto_completo_escritorio.png"), full_page=True)

        # Errores del backend: 503 con mensaje y reintento sin duplicar la pregunta.
        contador = {"n": 0}

        def fallar_una_vez(route):
            contador["n"] += 1
            if contador["n"] == 1:
                route.fulfill(status=503, content_type="application/json",
                              body=json.dumps({"detail": "El copiloto no está disponible en este momento.", "codigo": "proveedor_no_disponible"}))
            else:
                route.continue_()

        pagina.route("**/api/copilot/chat", fallar_una_vez)
        pagina.get_by_label("Tu pregunta", exact=True).fill("pregunta que falla")
        pagina.get_by_role("button", name="Enviar", exact=True).click()
        comprobar("Errores: un 503 se muestra con mensaje claro",
                  lambda: expect(pagina.get_by_role("alert").filter(has_text="no está disponible")).to_be_visible())
        pagina.get_by_role("button", name="Reintentar").click()
        comprobar("Reintentos: la respuesta llega tras reintentar",
                  lambda: expect(pagina.get_by_role("log").get_by_role("article", name="Respuesta del copiloto").last).to_be_visible(timeout=10000))
        comprobar("Reintentos: la pregunta no se duplica ni queda el error",
                  lambda: _ok(pagina.get_by_role("log").get_by_text("pregunta que falla", exact=True).count() == 1
                              and pagina.get_by_role("alert").count() == 0, ""))
        pagina.unroute("**/api/copilot/chat")

        # Limpiar la conversación activa.
        pagina.get_by_role("button", name="Limpiar conversación").click()
        comprobar("Limpiar: la conversación activa queda vacía",
                  lambda: expect(pagina.get_by_text("Pregúntame sobre tus datos")).to_be_visible())

        # Responsive: página completa y widget en los tamaños pedidos.
        for nombre, ancho, alto in [("movil", 390, 844), ("tableta", 768, 1024), ("escritorio", 1440, 900), ("full_hd", 1920, 1080)]:
            pagina.set_viewport_size({"width": ancho, "height": alto})
            pagina.wait_for_timeout(300)
            d = pagina.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            comprobar(f"Responsive copiloto completo {nombre} {ancho}px: sin desplazamiento horizontal",
                      lambda d=d: _ok(d <= 1, f"desborde {d}px"), f"desborde={d}px")
            pagina.screenshot(path=str(carpeta / f"resp_copiloto_{nombre}.png"), full_page=True)

        pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Académico").click()
        pagina.wait_for_timeout(300)
        pagina.set_viewport_size({"width": 390, "height": 844})
        pagina.locator(".copiloto-flotante").click()
        caja_w = widget(pagina).bounding_box() or {}
        comprobar("Responsive widget móvil: panel casi a pantalla completa y sin ocultar la cabecera",
                  lambda: _ok(caja_w.get("width", 0) >= 350 and caja_w.get("y", 0) >= 60, str(caja_w)))
        pagina.screenshot(path=str(carpeta / "03_widget_movil.png"))

        navegador.close()

    fallos = [r for r in resultados if r["resultado"] == "FAIL"]
    salida.write_text(json.dumps({"total": len(resultados), "fallos": len(fallos),
                                  "peticiones_chat_totales": len(peticiones_chat), "resultados": resultados},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(resultados)} · Fallos: {len(fallos)} · Peticiones al copiloto: {len(peticiones_chat)}", flush=True)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
