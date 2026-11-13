"""Fase 06D · Auditoría responsive del dashboard y los módulos (Chrome, headless).

Usa viewports EXPLÍCITOS e independientes, uno por tamaño. Para cada módulo registra:
  innerWidth, outerWidth, clientWidth (documento) y scrollWidth (documento).
Un desbordamiento (scrollWidth > clientWidth) indica un defecto de CSS, no de la ventana.

Uso (desde frontend/), con la aplicación de auditoría en http://127.0.0.1:8766 (modo demo):
  python e2e/fase06d_responsive.py http://127.0.0.1:8766 <carpeta_capturas> <resultados.json>
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

TAMANOS = [
    ("movil", 390, 844),
    ("tableta", 768, 1024),
    ("portatil", 1366, 768),
    ("escritorio", 1440, 900),
    ("full_hd", 1920, 1080),
]
MODULOS = ["Mi espacio", "Académico", "Finanzas", "Tareas"]


def medidas(pagina) -> dict:
    return pagina.evaluate("""() => ({
        innerWidth: window.innerWidth,
        outerWidth: window.outerWidth,
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        ancho_contenido: (document.querySelector('.content') || {}).offsetWidth || null,
        ancho_maximo_modulo: (document.querySelector('.module') || {}).offsetWidth || null,
        columnas_kpi: getComputedStyle(document.querySelector('.kpis') || document.body)
            .gridTemplateColumns.split(' ').filter(Boolean).length,
    })""")


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    base, carpeta, salida = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
    carpeta.mkdir(parents=True, exist_ok=True)
    resultados = []
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome", headless=True)
        for nombre, ancho, alto in TAMANOS:
            contexto = navegador.new_context(viewport={"width": ancho, "height": alto})
            pagina = contexto.new_page()
            pagina.goto(base)
            expect(pagina.locator(".demo-banner")).to_be_visible(timeout=15000)
            for modulo in MODULOS:
                pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name=modulo).click()
                pagina.wait_for_timeout(500)
                m = medidas(pagina)
                desborde = m["scrollWidth"] - m["clientWidth"]
                resultados.append({
                    "tamano": nombre, "viewport": f"{ancho}x{alto}", "modulo": modulo,
                    "medidas": m, "desborde_px": desborde, "ok_sin_desborde": desborde <= 1,
                })
                slug = modulo.lower().replace(" ", "_")
                pagina.screenshot(path=str(carpeta / f"{nombre}_{slug}.png"), full_page=True)
                print(f"{nombre:10} {ancho}x{alto} {modulo:12} desborde={desborde}px "
                      f"contenido={m['ancho_contenido']}px kpi_cols={m['columnas_kpi']}", flush=True)
            contexto.close()
        navegador.close()

    fallos = [r for r in resultados if not r["ok_sin_desborde"]]
    salida.write_text(json.dumps({"total": len(resultados), "con_desborde": len(fallos), "resultados": resultados},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(resultados)} · Con desborde horizontal: {len(fallos)}", flush=True)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
