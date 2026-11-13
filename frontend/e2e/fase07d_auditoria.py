"""Fase 07D · Auditoría responsive y visual de AURORA (solo lectura, Chrome real, headless).

Uso (PowerShell, desde la raíz del repositorio):
  backend\\.venv\\Scripts\\python.exe frontend\\e2e\\fase07d_auditoria.py http://127.0.0.1:5175 visual-evidence\\fase-07d\\antes antes
  backend\\.venv\\Scripts\\python.exe frontend\\e2e\\fase07d_auditoria.py http://127.0.0.1:5175 visual-evidence\\fase-07d\\despues despues

Requiere un backend de demostración (DEMO_MODE, SQLite temporal) detrás del frontend indicado.
No inicia sesión, no escribe datos y no llama a ningún proveedor de IA.

Por cada pantalla y tamaño guarda captura completa y métricas:
  - desbordamiento horizontal del documento y elementos visibles fuera del viewport;
  - pares de controles (botón, enlace, campo, chip) que se solapan;
  - texto visible de menos de 12 px;
  - en el copiloto: si el campo de escritura queda entero dentro del viewport y si la página necesita scroll vertical.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

TAMANOS = [("movil", 390, 844), ("tableta", 768, 1024), ("portatil", 1366, 768), ("escritorio", 1440, 900), ("full_hd", 1920, 1080)]
PANTALLAS = ["Mi espacio", "Académico", "Finanzas", "Tareas", "Copiloto"]

JS_METRICAS = """() => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const visible = (e) => { const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  // Un elemento dentro de un carril con desplazamiento propio (p. ej. la navegación móvil) no es un desbordamiento.
  const recortado = (e) => { for (let a = e.parentElement; a; a = a.parentElement) {
    const o = getComputedStyle(a).overflowX; if (o !== 'visible' && a.scrollWidth > a.clientWidth + 1) return true; } return false; };
  const fuera = [];
  document.querySelectorAll('body *').forEach((e) => {
    if (!visible(e) || recortado(e)) return;
    const r = e.getBoundingClientRect();
    if (r.right > vw + 1 || r.left < -1) {
      if (fuera.length < 6) fuera.push(`${e.tagName.toLowerCase()}.${(e.className && e.className.baseVal === undefined ? e.className : '').toString().split(' ')[0]}`);
    }
  });
  const controles = [...document.querySelectorAll('button, a[href], input, textarea, select')].filter((e) => visible(e) && !recortado(e))
    .map((e) => ({ e, r: e.getBoundingClientRect() }));
  let solapados = 0;
  for (let i = 0; i < controles.length; i++) for (let j = i + 1; j < controles.length; j++) {
    const a = controles[i].r, b = controles[j].r;
    const w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (w > 4 && h > 4 && !controles[i].e.contains(controles[j].e) && !controles[j].e.contains(controles[i].e)) solapados++;
  }
  let textoPequeno = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = walker.nextNode())) {
    if (!n.textContent.trim() || !n.parentElement || !visible(n.parentElement)) continue;
    if (parseFloat(getComputedStyle(n.parentElement).fontSize) < 12) textoPequeno++;
  }
  const campo = document.querySelector('#pregunta-copiloto');
  let campoVisible = null, campoCompleto = null;
  if (campo && visible(campo)) {
    const r = campo.getBoundingClientRect();
    campoCompleto = r.top >= 0 && r.bottom <= vh + 1;
    campoVisible = campoCompleto;
  }
  return {
    ancho_documento: document.documentElement.scrollWidth, ancho_ventana: vw,
    desborde_horizontal_px: document.documentElement.scrollWidth - vw,
    fuera_de_viewport: fuera, solapamientos: solapados, texto_menor_12px: textoPequeno,
    scroll_vertical_documento_px: Math.max(0, document.documentElement.scrollHeight - vh),
    campo_copiloto_presente: !!campo, campo_copiloto_entero_en_viewport: campoCompleto,
  };
}"""


def ir_a(pagina: Page, nombre: str) -> None:
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name=nombre).click()
    pagina.wait_for_timeout(600)


def auditar(base: str, carpeta: Path, etapa: str) -> dict:
    carpeta.mkdir(parents=True, exist_ok=True)
    resultados = []
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context()
        pagina = ctx.new_page()
        pagina.goto(base)
        pagina.get_by_role("navigation", name="Módulos").wait_for(timeout=20000)
        for etiqueta, ancho, alto in TAMANOS:
            pagina.set_viewport_size({"width": ancho, "height": alto})
            for pantalla in PANTALLAS:
                ir_a(pagina, pantalla)
                pagina.wait_for_timeout(400)
                slug = f"{pantalla.lower().replace(' ', '_').replace('é', 'e').replace('í', 'i')}_{etiqueta}_{ancho}"
                met = pagina.evaluate(JS_METRICAS)
                pagina.screenshot(path=str(carpeta / f"{slug}.png"), full_page=pantalla != "Copiloto")
                # Al final de la página, los controles deben quedar libres del lanzador flotante.
                pagina.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
                pagina.wait_for_timeout(300)
                al_final = pagina.evaluate(JS_METRICAS)
                pagina.evaluate("() => window.scrollTo(0, 0)")
                resultados.append({"pantalla": pantalla, "tamano": etiqueta, "ancho": ancho, "alto": alto, **met,
                                   "solapamientos_al_final": al_final["solapamientos"]})
            # Widget flotante sobre Mi espacio.
            ir_a(pagina, "Mi espacio")
            pagina.get_by_role("button", name="Habla con AURORA").click()
            pagina.wait_for_timeout(500)
            met_w = pagina.evaluate(JS_METRICAS)
            caja = pagina.locator(".widget-aurora").bounding_box()
            pagina.screenshot(path=str(carpeta / f"widget_{etiqueta}_{ancho}.png"))
            resultados.append({"pantalla": "Widget", "tamano": etiqueta, "ancho": ancho, "alto": alto,
                               **met_w, "widget_caja": caja})
            pagina.keyboard.press("Escape")
        nav.close()
    informe = {"etapa": etapa, "base": base, "resultados": resultados}
    (carpeta / "metricas.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return informe


def auditar_login(base: str, carpeta: Path) -> dict:
    """Pantalla de inicio de sesión (sin credenciales): formulario utilizable en todos los tamaños."""
    carpeta.mkdir(parents=True, exist_ok=True)
    resultados = []
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="chrome", headless=True)
        pagina = nav.new_context().new_page()
        pagina.goto(base)
        pagina.get_by_label("Correo electrónico").wait_for(timeout=20000)
        for etiqueta, ancho, alto in TAMANOS:
            pagina.set_viewport_size({"width": ancho, "height": alto})
            pagina.wait_for_timeout(300)
            met = pagina.evaluate(JS_METRICAS)
            campos = pagina.evaluate("""() => [...document.querySelectorAll('input')].map(e => {
                const r = e.getBoundingClientRect(); return {h: Math.round(r.height), ancho: Math.round(r.width)}; })""")
            boton = pagina.get_by_role("button", name="Entrar").bounding_box()
            pagina.screenshot(path=str(carpeta / f"login_{etiqueta}_{ancho}.png"), full_page=True)
            resultados.append({"pantalla": "Inicio de sesión", "tamano": etiqueta, "ancho": ancho, "alto": alto, **met,
                               "campos_alto_px": [c["h"] for c in campos], "boton_entrar_alto_px": round(boton["height"]) if boton else None})
        nav.close()
    informe = {"etapa": "login", "base": base, "resultados": resultados}
    (carpeta / "metricas.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return informe


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[3] == "login":
        raise SystemExit(0 if all(r["desborde_horizontal_px"] <= 1 for r in auditar_login(sys.argv[1], Path(sys.argv[2]))["resultados"]) else 1)
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(2)
    inf = auditar(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
    # Criterio: desbordamiento horizontal o controles tapados al final de la página (lo que el usuario alcanza).
    malos = [r for r in inf["resultados"] if r["desborde_horizontal_px"] > 1 or r.get("solapamientos_al_final", 0) > 0]
    tapados_al_inicio = [r for r in inf["resultados"] if r["solapamientos"] > 0]
    print(f"Mediciones: {len(inf['resultados'])} · con desborde o control tapado al final: {len(malos)}")
    for r in malos:
        print(f"  {r['pantalla']} {r['ancho']}px: desborde={r['desborde_horizontal_px']} tapados_al_final={r.get('solapamientos_al_final')}")
    print(f"Solapamientos visibles al abrir la página (en el inicio): {len(tapados_al_inicio)}")
