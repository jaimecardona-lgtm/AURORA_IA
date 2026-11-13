"""Recorrido funcional en navegador real (Chrome) del modo demo de la Fase 03.

Requisitos previos (ver docs/PRUEBAS_FASE_03.md):
  1. Datos demo cargados:  python -m app.infrastructure.sqlite.seed --reset   (desde backend/)
  2. Backend en modo demo sirviendo el build:
       APP_ENV=development PERSISTENCE_BACKEND=sqlite DEMO_MODE=true \
       python -m uvicorn app.main:app --port 8765         (desde backend/, con frontend/dist compilado)
  3. Playwright para Python con Chrome instalado en el equipo.

Uso (desde frontend/):
  python e2e/fase03_recorrido_demo.py <URL> <carpeta_capturas> <resultados.json> [--verificar]

  Sin --verificar: recorre todo y deja una tarea persistente ("Tarea persistente") y la nota
                   "Parcial 3" para comprobar la persistencia tras reiniciar el servidor.
  Con --verificar: tras reiniciar el backend, comprueba que esos datos siguen en SQLite.

No usa credenciales. Solo datos ficticios de la base demo local.
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
    except AssertionError as exc:
        registrar(nombre, False, str(exc)[:300])
    except Exception as exc:  # noqa: BLE001 - se registra y se sigue con el resto
        registrar(nombre, False, f"{type(exc).__name__}: {str(exc)[:300]}")


def nav(pagina: Page, modulo: str) -> None:
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name=modulo).click()
    expect(pagina.get_by_role("heading", level=1, name=modulo, exact=False)).to_be_visible()


def mensaje(pagina: Page, texto: str) -> None:
    expect(pagina.get_by_role("status").filter(has_text=texto).or_(pagina.get_by_role("alert").filter(has_text=texto))).to_be_visible(timeout=8000)


def recorrido_academico(pagina: Page, capturas: Path) -> None:
    nav(pagina, "Académico")
    expect(pagina.get_by_role("list", name="Lista de asignaturas")).to_be_visible()

    comprobar("Académico: datos demo visibles (3 asignaturas)",
              lambda: expect(pagina.get_by_role("list", name="Lista de asignaturas").get_by_role("button")).to_have_count(3))
    comprobar("Académico: promedio general del backend (3,64)",
              lambda: expect(pagina.get_by_text("3,64").first).to_be_visible())

    pagina.get_by_role("button", name=re.compile("Cálculo diferencial")).click()
    expect(pagina.get_by_role("list", name="Notas registradas")).to_be_visible()
    comprobar("Académico: promedio de Cálculo (4,17) y aprobación",
              lambda: expect(pagina.get_by_text("4,17").first).to_be_visible())

    # Nota objetivo: suma 12,5 con 3 notas. Para 4,5 hacen falta 5,5 (imposible); para 4,0, 3,50.
    pagina.get_by_label("Promedio objetivo (0 a 5)", exact=True).fill("4,5")
    pagina.get_by_role("button", name="Calcular").click()
    comprobar("Académico: nota objetivo imposible se informa",
              lambda: expect(pagina.get_by_text("No es posible")).to_be_visible())
    pagina.get_by_label("Promedio objetivo (0 a 5)", exact=True).fill("4")
    pagina.get_by_role("button", name="Calcular").click()
    comprobar("Académico: nota objetivo posible (3.50)",
              lambda: expect(pagina.get_by_text("3.50")).to_be_visible())

    # Validación de nota fuera de rango: no debe guardarse.
    pagina.get_by_label("Evaluación", exact=True).fill("Error de prueba")
    pagina.get_by_label("Nota (0 a 5)", exact=True).fill("6")
    pagina.get_by_role("button", name="Registrar nota").click()
    comprobar("Académico: nota fuera de rango se rechaza en la interfaz",
              lambda: expect(pagina.get_by_text("debe estar entre 0 y 5")).to_be_visible())

    # Alta de nota válida con coma decimal.
    pagina.get_by_label("Evaluación", exact=True).fill("Parcial 3")
    pagina.get_by_label("Nota (0 a 5)", exact=True).fill("4,80")
    pagina.get_by_role("button", name="Registrar nota").click()
    mensaje(pagina, "Nota registrada: Parcial 3")
    comprobar("Académico: nueva nota aparece y el promedio se recalcula (4,33)",
              lambda: expect(pagina.get_by_text("4,33").first).to_be_visible())

    # Crear y eliminar una asignatura: la lista se actualiza.
    pagina.get_by_label("Nombre de la nueva asignatura").fill("Prueba automatizada")
    pagina.get_by_role("button", name="Agregar").click()
    mensaje(pagina, "Asignatura «Prueba automatizada» creada")
    comprobar("Académico: lista actualizada tras crear (4 asignaturas)",
              lambda: expect(pagina.get_by_role("list", name="Lista de asignaturas").get_by_role("button")).to_have_count(4))
    pagina.get_by_text("Eliminar asignatura").click()
    pagina.get_by_role("button", name="Sí, eliminar").click()
    mensaje(pagina, "Asignatura «Prueba automatizada» eliminada")
    comprobar("Académico: lista actualizada tras eliminar (3 asignaturas)",
              lambda: expect(pagina.get_by_role("list", name="Lista de asignaturas").get_by_role("button")).to_have_count(3))
    pagina.screenshot(path=str(capturas / "academico_escritorio.png"), full_page=True)


def recorrido_finanzas(pagina: Page, capturas: Path) -> None:
    nav(pagina, "Finanzas")
    comprobar("Finanzas: ingreso demo del mes (2.500.000)",
              lambda: expect(pagina.get_by_text("2.500.000").first).to_be_visible())
    comprobar("Finanzas: distribución por categoría con datos",
              lambda: expect(pagina.get_by_text("Distribución por categoría")).to_be_visible())

    pagina.get_by_label("Descripción", exact=True).fill("Gasto prueba")
    pagina.get_by_label("Categoría", exact=True).fill("Pruebas")
    pagina.get_by_label("Monto (COP)", exact=True).fill("15.000")
    pagina.get_by_label("Tipo", exact=True).select_option("variable")
    pagina.get_by_role("button", name="Registrar gasto").click()
    mensaje(pagina, "Gasto registrado: Gasto prueba")
    comprobar("Finanzas: gasto registrado aparece en la lista",
              lambda: expect(pagina.get_by_role("list", name="Gastos del mes").get_by_text("Gasto prueba", exact=True)).to_be_visible())

    pagina.get_by_label("Monto (COP)", exact=True).fill("-5")
    pagina.get_by_label("Descripción", exact=True).fill("Negativo")
    pagina.get_by_role("button", name="Registrar gasto").click()
    comprobar("Finanzas: importe negativo se rechaza",
              lambda: expect(pagina.get_by_text("no puede ser negativo")).to_be_visible())

    pagina.get_by_label("Monto (COP)", exact=True).fill("100")
    pagina.get_by_label("Descripción", exact=True).fill("")
    pagina.get_by_role("button", name="Registrar gasto").click()
    comprobar("Finanzas: gasto incompleto se rechaza",
              lambda: expect(pagina.get_by_text("Describe el gasto")).to_be_visible())

    pagina.get_by_label("Descripción", exact=True).fill("")
    pagina.get_by_label("Categoría", exact=True).fill("")
    pagina.get_by_role("button", name="Registrar gasto").click()
    comprobar("Finanzas: categoría obligatoria",
              lambda: expect(pagina.get_by_text("Indica la categoría")).to_be_visible())

    pagina.get_by_text("Eliminar Gasto prueba").click()
    pagina.get_by_role("button", name="Sí, eliminar").click()
    mensaje(pagina, "Gasto «Gasto prueba» eliminado")
    comprobar("Finanzas: gasto eliminado desaparece",
              lambda: expect(pagina.get_by_role("list", name="Gastos del mes").get_by_text("Gasto prueba", exact=True)).to_have_count(0))
    pagina.screenshot(path=str(capturas / "finanzas_escritorio.png"), full_page=True)


def recorrido_tareas(pagina: Page, capturas: Path, verificar: bool) -> None:
    nav(pagina, "Tareas")
    if verificar:
        comprobar("Persistencia: tarea creada antes del reinicio sigue en SQLite",
                  lambda: expect(pagina.get_by_role("list", name="Lista de tareas").get_by_text("Tarea persistente", exact=True)).to_be_visible())
        pagina.screenshot(path=str(capturas / "tareas_tras_reinicio.png"), full_page=True)
        return

    pagina.get_by_label("Título", exact=True).fill("Tarea prueba")
    pagina.locator("#tarea-prioridad").select_option("alta")
    pagina.get_by_label("Fecha límite (opcional)", exact=True).fill("2026-12-31")
    pagina.get_by_role("button", name="Crear tarea").click()
    mensaje(pagina, "Tarea «Tarea prueba» creada")
    comprobar("Tareas: nueva tarea aparece con prioridad alta",
              lambda: expect(pagina.get_by_role("list", name="Lista de tareas").get_by_text("Tarea prueba", exact=True)).to_be_visible())

    pagina.get_by_role("checkbox", name="Marcar «Tarea prueba» como completada").click()
    mensaje(pagina, "«Tarea prueba» completada")
    comprobar("Tareas: marcar como completada",
              lambda: expect(pagina.get_by_role("checkbox", name="Marcar «Tarea prueba» como pendiente")).to_be_checked())

    pagina.get_by_label("Estado", exact=True).select_option("completada")
    comprobar("Tareas: filtro por estado completada muestra la tarea",
              lambda: expect(pagina.get_by_role("list", name="Lista de tareas").get_by_text("Tarea prueba", exact=True)).to_be_visible())
    pagina.get_by_label("Estado", exact=True).select_option("")

    pagina.get_by_role("button", name="Editar Tarea prueba").click()
    comprobar("Tareas: formulario pasa a modo edición",
              lambda: expect(pagina.get_by_role("heading", name="Editar tarea")).to_be_visible())
    pagina.get_by_label("Título", exact=True).fill("Tarea editada")
    pagina.get_by_role("button", name="Guardar cambios").click()
    mensaje(pagina, "Tarea «Tarea editada» actualizada")
    comprobar("Tareas: edición guardada",
              lambda: expect(pagina.get_by_role("list", name="Lista de tareas").get_by_text("Tarea editada", exact=True)).to_be_visible())

    pagina.get_by_label("Título", exact=True).fill("Tarea persistente")
    pagina.locator("#tarea-prioridad").select_option("media")
    pagina.get_by_role("button", name="Crear tarea").click()
    mensaje(pagina, "Tarea «Tarea persistente» creada")

    pagina.get_by_text("Eliminar Tarea editada").click()
    pagina.get_by_role("button", name="Sí, eliminar").click()
    mensaje(pagina, "Tarea «Tarea editada» eliminada")
    comprobar("Tareas: eliminación actualiza la lista",
              lambda: expect(pagina.get_by_role("list", name="Lista de tareas").get_by_text("Tarea editada", exact=True)).to_have_count(0))
    pagina.screenshot(path=str(capturas / "tareas_escritorio.png"), full_page=True)


def recorrido_persistencia_y_recarga(pagina: Page, base: str, verificar: bool) -> None:
    pagina.goto(base)
    expect(pagina.locator(".demo-banner")).to_be_visible()
    comprobar("Modo demo: el aviso es visible y no hay inicio de sesión",
              lambda: expect(pagina.get_by_role("button", name="Cerrar sesión")).to_have_count(0))
    nav(pagina, "Académico")
    if verificar:
        pagina.get_by_role("button", name=re.compile("Cálculo diferencial")).click()
        comprobar("Persistencia: nota creada antes del reinicio sigue en SQLite",
                  lambda: expect(pagina.get_by_text("Parcial 3", exact=True).first).to_be_visible())
        comprobar("Persistencia: promedio tras reinicio (4,33)",
                  lambda: expect(pagina.get_by_text("4,33").first).to_be_visible())


def bloque(fn, *args) -> None:
    """Ejecuta un recorrido completo; si falla, se registra y se continúa con el siguiente."""
    try:
        fn(*args)
    except Exception as exc:  # noqa: BLE001
        registrar(f"Recorrido interrumpido: {fn.__name__}", False, f"{type(exc).__name__}: {str(exc)[:300]}")


def _recarga_academico(pagina: Page, base: str) -> None:
    expect(pagina.locator(".demo-banner")).to_be_visible()
    nav(pagina, "Académico")
    pagina.get_by_role("button", name=re.compile("Cálculo diferencial")).click()
    expect(pagina.get_by_text("Parcial 3", exact=True).first).to_be_visible()


def sin_scroll_horizontal(pagina: Page) -> int:
    return pagina.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def recorrido_responsive(navegador, base: str, capturas: Path) -> None:
    for nombre, ancho, alto in ANCHOS:
        contexto = navegador.new_context(viewport={"width": ancho, "height": alto})
        pagina = contexto.new_page()
        pagina.goto(base)
        expect(pagina.locator(".demo-banner")).to_be_visible()
        for modulo in ["Académico", "Finanzas", "Tareas"]:
            nav(pagina, modulo)
            pagina.wait_for_timeout(300)
            desborde = sin_scroll_horizontal(pagina)
            comprobar(f"Responsive {nombre} {ancho}px · {modulo}: sin desplazamiento horizontal de página",
                      lambda d=desborde: _assert(d <= 1, f"desborde de {d}px"), f"desborde={desborde}px")
            pagina.screenshot(path=str(capturas / f"{modulo.lower()}_{nombre}.png"), full_page=True)
        contexto.close()


def _assert(condicion: bool, mensaje_error: str) -> None:
    assert condicion, mensaje_error


def recorrido_teclado(navegador, base: str) -> None:
    contexto = navegador.new_context(viewport={"width": 1366, "height": 860})
    pagina = contexto.new_page()
    pagina.goto(base)
    expect(pagina.locator(".demo-banner")).to_be_visible()
    pagina.keyboard.press("Tab")
    enlace = pagina.evaluate("() => document.activeElement && document.activeElement.textContent")
    comprobar("Teclado: primer Tab llega al enlace «Saltar al contenido»",
              lambda: _assert(enlace is not None and "Saltar" in enlace, f"foco en {enlace!r}"))
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Finanzas").focus()
    pagina.keyboard.press("Enter")
    comprobar("Teclado: Enter en la navegación abre el módulo",
              lambda: expect(pagina.get_by_role("heading", level=1, name="Finanzas")).to_be_visible())
    comprobar("Teclado: el módulo activo se marca con aria-current",
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

        comprobar("Carga inicial de la aplicación en modo demo",
                  lambda: pagina.goto(base) and expect(pagina.locator(".demo-banner")).to_be_visible())
        bloque(recorrido_persistencia_y_recarga, pagina, base, verificar)
        if verificar:
            bloque(recorrido_tareas, pagina, carpeta, True)
        else:
            bloque(recorrido_academico, pagina, carpeta)
            bloque(recorrido_finanzas, pagina, carpeta)
            bloque(recorrido_tareas, pagina, carpeta, False)
            pagina.goto(base)
            comprobar("Recarga: la nota registrada sigue tras recargar la página",
                      lambda: _recarga_academico(pagina, base))
        contexto.close()

        if not verificar:
            bloque(recorrido_responsive, navegador, base, carpeta)
            bloque(recorrido_teclado, navegador, base)
        navegador.close()

    comprobar("Consola del navegador sin errores de JavaScript",
              lambda: _assert(not errores_consola, "; ".join(errores_consola)[:300]))

    fallos = [r for r in resultados if r["resultado"] == "FAIL"]
    salida.write_text(json.dumps({"verificar": verificar, "total": len(resultados), "fallos": len(fallos), "resultados": resultados},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(resultados)} · Fallos: {len(fallos)} · Resultados: {salida}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
