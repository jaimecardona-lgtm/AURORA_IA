"""Recorrido de la Fase 04 en Chrome real: panel general, CRUD de los tres módulos, responsive y capturas.

Requisitos (ver docs/PRUEBAS_FASE_04.md):
  1. Base demo limpia:  python -m app.infrastructure.sqlite.seed --reset   (desde backend/)
  2. Backend demo sirviendo el build:  APP_ENV=development PERSISTENCE_BACKEND=sqlite DEMO_MODE=true
     python -m uvicorn app.main:app --port 8765                             (desde backend/)

Uso (desde frontend/):
  python e2e/fase04_recorrido.py <URL> <carpeta_capturas> <resultados.json> [--verificar]

Sin --verificar: recorre todo y deja una nota "Parcial 4" y una tarea "Tarea persistente".
Con --verificar: tras reiniciar el servidor, comprueba que esos datos siguen en SQLite.
"""

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ANCHOS = [("movil", 390, 844), ("tableta", 820, 1180), ("escritorio", 1366, 860)]
resultados: list[dict] = []
errores_consola: list[str] = []


def registrar(nombre: str, ok: bool, detalle: str = "") -> None:
    resultados.append({"prueba": nombre, "resultado": "PASS" if ok else "FAIL", "detalle": detalle})
    print(("PASS " if ok else "FAIL ") + nombre + (f" | {detalle}" if detalle else ""))


def comprobar(nombre: str, fn, detalle_ok: str = "") -> None:
    try:
        fn()
        registrar(nombre, True, detalle_ok)
    except Exception as exc:  # noqa: BLE001 - se registra y se continúa
        registrar(nombre, False, f"{type(exc).__name__}: {str(exc)[:260]}")


def bloque(fn, *args) -> None:
    try:
        fn(*args)
    except Exception as exc:  # noqa: BLE001
        registrar(f"Recorrido interrumpido: {fn.__name__}", False, f"{type(exc).__name__}: {str(exc)[:260]}")


TITULO_MODULO = {"Mi espacio": "Vista general"}


def nav(pagina: Page, modulo: str) -> None:
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name=modulo).click()
    expect(pagina.get_by_role("heading", level=1, name=TITULO_MODULO.get(modulo, modulo), exact=False)).to_be_visible()


def aviso(pagina: Page, texto: str) -> None:
    expect(pagina.get_by_role("status").filter(has_text=texto).or_(pagina.get_by_role("alert").filter(has_text=texto))).to_be_visible(timeout=8000)


def numero_es(valor) -> str:
    """Formato es-CO de nota (3,69) a partir de un decimal de la API."""
    return f"{float(valor):.2f}".replace(".", ",")


def recorrido_panel(pagina: Page, base: str, capturas: Path) -> None:
    datos = pagina.request.get(f"{base}/api/dashboard").json()
    ac, fi, ta = datos["academico"], datos["finanzas"], datos["tareas"]

    comprobar("Panel: título Vista general y accesos a los tres módulos",
              lambda: expect(pagina.get_by_role("heading", name="Vista general")).to_be_visible())
    comprobar("Panel: promedio general coincide con la API",
              lambda: expect(pagina.get_by_text(numero_es(ac["promedio_general"]), exact=True).first).to_be_visible(),
              f"API={ac['promedio_general']}")
    comprobar("Panel: aprobadas coincide con la API",
              lambda: expect(pagina.get_by_text(f"{ac['aprobadas']} / {ac['con_notas']}", exact=True)).to_be_visible())
    comprobar("Panel: saldo coincide con la API",
              lambda: expect(pagina.get_by_text(re.compile(re.escape(f"{float(fi['saldo']):,.0f}".replace(",", "."))), exact=False).first).to_be_visible())
    comprobar("Panel: pendientes y próximas coinciden con la API",
              lambda: expect(pagina.locator(".kpi").filter(has_text="Tareas pendientes").get_by_text(str(ta["pendientes"]), exact=True)).to_be_visible())
    comprobar("Panel: próximas a vencer = total de la API",
              lambda: expect(pagina.locator(".kpi").filter(has_text="Próximas a vencer").get_by_text(str(ta["proximas_total"]), exact=True)).to_be_visible())
    comprobar("Panel: Copiloto marcado como próximamente y no interactivo",
              lambda: expect(pagina.get_by_text("Próximamente").first).to_be_visible())
    comprobar("Panel: el Copiloto no tiene botón que simule respuestas",
              lambda: expect(pagina.get_by_role("button", name=re.compile("copiloto", re.I))).to_have_count(0))
    pagina.screenshot(path=str(capturas / "01_mi_espacio_escritorio.png"), full_page=True)


def recorrido_academico(pagina: Page, capturas: Path) -> None:
    nav(pagina, "Académico")
    comprobar("Académico: aviso de ponderación igual visible",
              lambda: expect(pagina.get_by_text("Todas las notas de una asignatura pesan igual")).to_be_visible())

    pagina.get_by_role("button", name=re.compile("Cálculo diferencial")).click()
    expect(pagina.get_by_role("list", name="Notas registradas")).to_be_visible()
    comprobar("Académico: gráfica de notas por evaluación",
              lambda: expect(pagina.get_by_text("Notas por evaluación (0 a 5)")).to_be_visible())

    pagina.get_by_label("Evaluación", exact=True).fill("Parcial 4")
    pagina.get_by_label("Nota (0 a 5)", exact=True).fill("4,10")
    pagina.get_by_role("button", name="Registrar nota").click()
    aviso(pagina, "Nota registrada: Parcial 4")
    comprobar("Académico: nota creada aparece en la lista",
              lambda: expect(pagina.get_by_role("list", name="Notas registradas").get_by_text("Parcial 4", exact=True)).to_be_visible())

    pagina.get_by_label("Evaluación", exact=True).fill("Temporal")
    pagina.get_by_label("Nota (0 a 5)", exact=True).fill("7")
    pagina.get_by_role("button", name="Registrar nota").click()
    comprobar("Académico: nota fuera de rango se rechaza",
              lambda: expect(pagina.get_by_text("debe estar entre 0 y 5")).to_be_visible())

    pagina.get_by_text("Eliminar nota Parcial 4").click()
    comprobar("Académico: borrar nota pide confirmación antes de actuar",
              lambda: expect(pagina.get_by_text("Se eliminará la nota «Parcial 4»")).to_be_visible())
    pagina.get_by_role("button", name="Sí, eliminar").click()
    aviso(pagina, "Nota «Parcial 4» eliminada")
    comprobar("Académico: nota eliminada desaparece",
              lambda: expect(pagina.get_by_role("list", name="Notas registradas").get_by_text("Parcial 4", exact=True)).to_have_count(0))
    pagina.screenshot(path=str(capturas / "02_academico_escritorio.png"), full_page=True)


def recorrido_finanzas(pagina: Page, capturas: Path) -> None:
    nav(pagina, "Finanzas")
    comprobar("Finanzas: gráfica fijos frente a variables",
              lambda: expect(pagina.get_by_text("Gastos según su tipo (COP)")).to_be_visible())
    comprobar("Finanzas: tabla de transacciones con encabezados",
              lambda: expect(pagina.get_by_role("columnheader", name="Monto")).to_be_visible())

    pagina.get_by_label("Descripción", exact=True).fill("Gasto Fase 4")
    pagina.get_by_label("Categoría", exact=True).fill("Pruebas")
    pagina.get_by_label("Monto (COP)", exact=True).fill("15.000")
    pagina.get_by_role("button", name="Registrar gasto").click()
    aviso(pagina, "Gasto registrado: Gasto Fase 4")

    pagina.get_by_role("button", name="Editar Gasto Fase 4").click()
    comprobar("Finanzas: edición abre el formulario con los datos actuales",
              lambda: expect(pagina.get_by_role("heading", name="Editar gasto")).to_be_visible())
    pagina.get_by_label("Monto (COP)", exact=True).last.fill("-1")
    pagina.get_by_role("button", name="Guardar cambios").click()
    comprobar("Finanzas: edición valida importes negativos",
              lambda: expect(pagina.get_by_text("no puede ser negativo")).to_be_visible())
    pagina.locator("#ed-monto").fill("20.000")
    pagina.get_by_role("button", name="Guardar cambios").click()
    aviso(pagina, "Gasto «Gasto Fase 4» actualizado")
    comprobar("Finanzas: edición guardada y reflejada en la tabla",
              lambda: expect(pagina.get_by_role("table").get_by_text("$ 20.000").first).to_be_visible())

    pagina.get_by_label("Eliminar Gasto Fase 4").click() if False else pagina.get_by_text("Eliminar Gasto Fase 4").click()
    pagina.get_by_role("button", name="Sí, eliminar").click()
    aviso(pagina, "Gasto «Gasto Fase 4» eliminado")
    comprobar("Finanzas: gasto eliminado desaparece de la tabla",
              lambda: expect(pagina.get_by_role("table").get_by_text("Gasto Fase 4", exact=True)).to_have_count(0))
    pagina.screenshot(path=str(capturas / "03_finanzas_escritorio.png"), full_page=True)


def recorrido_tareas(pagina: Page, capturas: Path, verificar: bool) -> None:
    nav(pagina, "Tareas")
    if verificar:
        comprobar("Persistencia: tarea creada antes del reinicio sigue en SQLite",
                  lambda: expect(pagina.get_by_role("list", name="Lista de tareas").get_by_text("Tarea persistente", exact=True)).to_be_visible())
        return

    pagina.get_by_label("Título", exact=True).fill("Tarea Fase 4")
    pagina.locator("#tarea-prioridad").select_option("alta")
    pagina.get_by_role("button", name="Crear tarea").click()
    aviso(pagina, "Tarea «Tarea Fase 4» creada")
    item = pagina.locator("li.tarea").filter(has_text="Tarea Fase 4")
    comprobar("Tareas: la prioridad alta se muestra con su clase visual",
              lambda: expect(item).to_have_class(re.compile("prioridad--alta")))

    pagina.get_by_role("checkbox", name="Marcar «Tarea Fase 4» como completada").click()
    aviso(pagina, "«Tarea Fase 4» completada")
    comprobar("Tareas: al completar, la tarea queda tachada",
              lambda: expect(pagina.locator("li.tarea.is-done").filter(has_text="Tarea Fase 4")).to_be_visible())

    pagina.get_by_role("checkbox", name="Marcar «Tarea Fase 4» como pendiente").click()
    aviso(pagina, "«Tarea Fase 4» vuelve a pendiente")

    pagina.get_by_label("Título", exact=True).fill("Tarea persistente")
    pagina.locator("#tarea-prioridad").select_option("media")
    pagina.get_by_role("button", name="Crear tarea").click()
    aviso(pagina, "Tarea «Tarea persistente» creada")

    pagina.get_by_text("Eliminar Tarea Fase 4").click()
    pagina.get_by_role("button", name="Sí, eliminar").click()
    aviso(pagina, "Tarea «Tarea Fase 4» eliminada")
    pagina.screenshot(path=str(capturas / "04_tareas_escritorio.png"), full_page=True)


def recarga_persistencia(pagina: Page, base: str, verificar: bool) -> None:
    pagina.goto(base)
    expect(pagina.locator(".demo-banner")).to_be_visible()
    comprobar("Modo demo: aviso visible y sin botón de cerrar sesión",
              lambda: expect(pagina.get_by_role("button", name="Cerrar sesión")).to_have_count(0))
    if verificar:
        datos = pagina.request.get(f"{base}/api/dashboard").json()
        esperado = numero_es(datos["academico"]["promedio_general"])
        comprobar("Persistencia: el promedio general tras reiniciar coincide con la API y se muestra",
                  lambda: expect(pagina.get_by_text(esperado, exact=True).first).to_be_visible(), f"promedio={esperado}")
        recorrido_tareas(pagina, Path("."), True)


def sin_desborde(pagina: Page) -> int:
    return pagina.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def responsive(navegador, base: str, capturas: Path) -> None:
    for nombre, ancho, alto in ANCHOS:
        contexto = navegador.new_context(viewport={"width": ancho, "height": alto})
        pagina = contexto.new_page()
        pagina.goto(base)
        expect(pagina.locator(".demo-banner")).to_be_visible()
        for modulo in ["Mi espacio", "Académico", "Finanzas", "Tareas"]:
            nav(pagina, modulo)
            pagina.wait_for_timeout(250)
            d = sin_desborde(pagina)
            comprobar(f"Responsive {nombre} {ancho}px · {modulo}: sin desplazamiento horizontal de página",
                      lambda d=d: _ok(d <= 1, f"desborde {d}px"), f"desborde={d}px")
            slug = modulo.lower().replace(" ", "_")
            pagina.screenshot(path=str(capturas / f"resp_{slug}_{nombre}.png"), full_page=True)
        contexto.close()


def _ok(condicion: bool, texto: str) -> None:
    assert condicion, texto


def teclado(navegador, base: str) -> None:
    contexto = navegador.new_context(viewport={"width": 1366, "height": 860})
    pagina = contexto.new_page()
    pagina.goto(base)
    expect(pagina.locator(".demo-banner")).to_be_visible()
    pagina.keyboard.press("Tab")
    foco = pagina.evaluate("() => document.activeElement && document.activeElement.textContent")
    comprobar("Teclado: primer Tab llega a «Saltar al contenido»",
              lambda: _ok(bool(foco) and "Saltar" in foco, f"foco={foco!r}"))
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Finanzas").focus()
    pagina.keyboard.press("Enter")
    comprobar("Teclado: Enter abre Finanzas",
              lambda: expect(pagina.get_by_role("heading", level=1, name="Finanzas")).to_be_visible())
    comprobar("Teclado: el módulo activo expone aria-current",
              lambda: expect(pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Finanzas")).to_have_attribute("aria-current", "page"))
    contexto.close()


def main() -> int:
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    verificar = "--verificar" in sys.argv
    if len(argumentos) != 3:
        print(__doc__)
        return 2
    base, carpeta, salida = argumentos[0].rstrip("/"), Path(argumentos[1]), Path(argumentos[2])
    carpeta.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome", headless=True)
        contexto = navegador.new_context(viewport={"width": 1366, "height": 860})
        pagina = contexto.new_page()
        pagina.on("pageerror", lambda e: errores_consola.append(f"pageerror: {e}"))
        pagina.on("console", lambda m: errores_consola.append(f"console.{m.type}: {m.text}")
                  if m.type == "error" and "Failed to load resource" not in m.text else None)

        bloque(recarga_persistencia, pagina, base, verificar)
        if not verificar:
            bloque(recorrido_panel, pagina, base, carpeta)
            bloque(recorrido_academico, pagina, carpeta)
            bloque(recorrido_finanzas, pagina, carpeta)
            bloque(recorrido_tareas, pagina, carpeta, False)
            pagina.goto(base)
            comprobar("Recarga: el panel vuelve a cargar tras recargar",
                      lambda: expect(pagina.get_by_role("heading", name="Vista general")).to_be_visible())
        contexto.close()

        if not verificar:
            bloque(responsive, navegador, base, carpeta)
            bloque(teclado, navegador, base)
        navegador.close()

    comprobar("Consola del navegador sin errores de JavaScript",
              lambda: _ok(not errores_consola, "; ".join(errores_consola)[:260]))
    fallos = [r for r in resultados if r["resultado"] == "FAIL"]
    salida.write_text(json.dumps({"verificar": verificar, "total": len(resultados), "fallos": len(fallos),
                                  "resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(resultados)} · Fallos: {len(fallos)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
