"""Prueba de humo de la UI de acceso. No usa credenciales reales.

Requiere dos instancias del backend que sirvan dos builds del frontend:
  - 8766: build SIN VITE_SUPABASE_* (muestra "Configuración pendiente").
  - 8765: build CON URL/clave FICTICIAS (Auth inalcanzable -> error controlado).
Uso (desde frontend/, con Playwright y Chrome instalados):
  python e2e/smoke_ui_sin_supabase.py <carpeta_para_capturas>
"""
import sys
from playwright.sync_api import sync_playwright

BASE_SIN = "http://127.0.0.1:8766"   # build sin configuración de Supabase
BASE_CON = "http://127.0.0.1:8765"   # build con URL ficticia (proveedor inalcanzable)

resultados = []


def check(nombre, ok, extra=""):
    resultados.append((nombre, ok))
    print(("PASS " if ok else "FAIL ") + nombre + (f" | {extra}" if extra else ""))


with sync_playwright() as p:
    navegador = p.chromium.launch(channel="chrome", headless=True)

    # 1) Sin configuración: debe mostrar el aviso, no romper.
    pagina = navegador.new_page(viewport={"width": 390, "height": 844})
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    pagina.goto(BASE_SIN, wait_until="networkidle")
    check("sin config: muestra 'Configuración pendiente'",
          pagina.get_by_role("heading", name="Configuración pendiente").is_visible())
    check("sin config: sin errores de JS", len(errores) == 0, "; ".join(errores))
    sin_scroll = pagina.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    check("sin config (390px): sin scroll horizontal", sin_scroll)
    pagina.screenshot(path=sys.argv[1] + "/sin_config_movil.png", full_page=True)
    pagina.close()

    # 2) Con configuración ficticia: formulario de acceso y error controlado si Supabase no responde.
    pagina = navegador.new_page(viewport={"width": 1280, "height": 800})
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    pagina.goto(BASE_CON, wait_until="networkidle")
    check("con config: formulario 'Inicia sesión' visible",
          pagina.get_by_role("heading", name="Inicia sesión").is_visible())

    pagina.get_by_label("Correo electrónico").fill("prueba@ejemplo.com")
    pagina.get_by_label("Contraseña").fill("clave-de-prueba")
    pagina.get_by_role("button", name="Entrar").click()
    alerta = pagina.get_by_role("alert")
    alerta.wait_for(timeout=30000)
    texto = alerta.inner_text()
    check("con config: error controlado al no poder contactar Auth",
          "conexión" in texto.lower() or "no se pudo" in texto.lower(), texto)
    check("con config: sin excepciones no capturadas", len(errores) == 0, "; ".join(errores))
    pagina.screenshot(path=sys.argv[1] + "/login_error_escritorio.png", full_page=True)

    # Validación en cliente: correo inválido
    pagina.get_by_label("Correo electrónico").fill("no-es-correo")
    pagina.get_by_role("button", name="Entrar").click()
    check("validación cliente: correo inválido",
          "correo válido" in pagina.get_by_role("alert").inner_text())

    # Modo recuperar y volver
    pagina.get_by_role("button", name="Olvidé mi contraseña").click()
    check("modo recuperar muestra título",
          pagina.get_by_role("heading", name="Recupera tu contraseña").is_visible())

    # Móvil
    pagina.set_viewport_size({"width": 360, "height": 740})
    pagina.wait_for_timeout(300)
    check("login (360px): sin scroll horizontal",
          pagina.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
    pagina.screenshot(path=sys.argv[1] + "/login_movil.png", full_page=True)
    navegador.close()

fallidos = [n for n, ok in resultados if not ok]
print(f"\nTOTAL {len(resultados)} | OK {len(resultados) - len(fallidos)} | FALLIDOS {len(fallidos)}")
sys.exit(1 if fallidos else 0)
