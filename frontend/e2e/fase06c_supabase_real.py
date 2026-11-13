"""Fase 06C/06D · Integración real con Supabase Auth + PostgreSQL + RLS, cuentas A y B.

EJECUCIÓN MANUAL, EN PRIMER PLANO (no en segundo plano):
  python frontend\\e2e\\fase06c_supabase_real.py visual-evidence\\fase-06d

Procedimiento de autenticación:
  - Las cuentas se autentican en secuencia: primero A, después B.
  - Cada cuenta usa su propio contexto de Chrome (cookies y almacenamiento independientes).
  - Introduces tú el correo y la contraseña en la ventana de Chrome. El script no las conoce,
    no las pide por consola, no las guarda y no exporta estados de sesión.
  - Si cierras una ventana, el script lo detecta, no marca como aprobada ninguna prueba interrumpida
    y pregunta en la terminal si quieres reabrir esa cuenta.
  - Los tokens (JWT) viven solo en memoria del proceso y nunca se imprimen.

Requisitos:
  - Frontend en http://127.0.0.1:5173, backend real en http://127.0.0.1:8000 (modo Supabase, sin DEMO_MODE).
  - Copiloto de pruebas en http://127.0.0.1:8001 con COPILOT_PROVIDER=simulado (sin OpenRouter).

Salidas (una carpeta y un JSON nuevos por ejecución):
  visual-evidence/fase-06d/<marca>/resultados.json  y  ids_prueba.json (solo identificadores de registros)

Todos los registros creados llevan el prefijo "06C-".
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright

FRONT = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000"
COPILOTO = "http://127.0.0.1:8001"
PREFIJO = "06C-"

resultados: list[dict] = []
ids: dict[str, str] = {}
interrupciones: list[str] = []


class VentanaCerrada(Exception):
    """La ventana de Chrome de una cuenta se cerró antes de completar un paso."""


def registrar(nombre: str, ok: bool, detalle: str = "") -> None:
    resultados.append({"prueba": nombre, "resultado": "PASS" if ok else "FAIL", "detalle": detalle})
    print(("PASS " if ok else "FAIL ") + nombre + (f" | {detalle}" if detalle else ""), flush=True)


def comprobar(nombre: str, fn, detalle: str = "") -> bool:
    """Una comprobación. Si la ventana se cerró, se marca INTERRUMPIDA (nunca PASS) y se propaga."""
    try:
        fn()
        registrar(nombre, True, detalle)
        return True
    except VentanaCerrada:
        interrupciones.append(nombre)
        registrar(nombre, False, "INTERRUMPIDA: la ventana de Chrome se cerró antes de completar la prueba")
        raise
    except PlaywrightError as exc:
        if "closed" in str(exc).lower():
            interrupciones.append(nombre)
            registrar(nombre, False, "INTERRUMPIDA: la ventana o el navegador se cerraron (TargetClosedError)")
            raise VentanaCerrada(nombre) from exc
        registrar(nombre, False, f"{type(exc).__name__}: {str(exc)[:220]}")
        return False
    except AssertionError as exc:
        registrar(nombre, False, f"AssertionError: {str(exc)[:220]}")
        return False


def _ok(condicion: bool, texto: str) -> None:
    assert condicion, texto


def pagina_viva(sesion: "Sesion") -> Page:
    if sesion.page is None or sesion.page.is_closed():
        raise VentanaCerrada(sesion.etiqueta)
    return sesion.page


class Sesion:
    """Una cuenta: su contexto de Chrome independiente y su token en memoria."""

    def __init__(self, navegador, etiqueta: str) -> None:
        self.navegador = navegador
        self.etiqueta = etiqueta
        self.ctx = navegador.new_context(no_viewport=True)  # el tamaño lo marca la ventana
        self.page: Page | None = self.ctx.new_page()
        self.token: str | None = None

    def abrir_login(self) -> None:
        if self.page is None or self.page.is_closed():
            self.page = self.ctx.new_page()
        self.page.goto(FRONT)

    def token_de_sesion(self) -> str | None:
        return pagina_viva(self).evaluate(
            """() => {
                for (const k of Object.keys(localStorage)) {
                  if (k.startsWith('sb-') && k.endsWith('-auth-token')) {
                    try { return JSON.parse(localStorage[k]).access_token || null; } catch (e) {}
                  }
                }
                return null;
            }"""
        )


def autenticar_manual(sesion: "Sesion") -> str:
    """Espera a que el usuario inicie sesión en la ventana de esta cuenta. Reabre si se cerró."""
    while True:
        try:
            sesion.abrir_login()
            print(f"\n[{sesion.etiqueta}] En la ventana de Chrome de esta cuenta, introduce correo y contraseña.", flush=True)
            print(f"[{sesion.etiqueta}] El script continúa solo cuando aparezca «Cerrar sesión».", flush=True)
            pagina_viva(sesion).get_by_role("button", name="Cerrar sesión").wait_for(timeout=900_000)
            token = sesion.token_de_sesion()
            if not token:
                raise AssertionError("no se encontró la sesión de Supabase en el navegador")
            sesion.token = token
            registrar(f"Inicio de sesión real · {sesion.etiqueta} (Supabase Auth)", True, "sesión iniciada en el navegador")
            return token
        except (PlaywrightError, VentanaCerrada) as exc:
            respuesta = input(f"\n[{sesion.etiqueta}] La ventana se cerró antes de terminar. ¿Reabrirla? (s/n): ").strip().lower()
            if respuesta != "s":
                registrar(f"Inicio de sesión real · {sesion.etiqueta}", False,
                           "INTERRUMPIDA: el usuario no reabrió la ventana")
                raise VentanaCerrada(sesion.etiqueta) from exc
            sesion.page = None


def cabeceras(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def api(metodo: str, ruta: str, token: str, cuerpo=None, base: str = API) -> httpx.Response:
    return httpx.request(metodo, f"{base}{ruta}", headers=cabeceras(token), json=cuerpo, timeout=20)


def ir(page: Page, modulo: str) -> None:
    page.get_by_role("navigation", name="Módulos").get_by_role("button", name=modulo).click()
    page.wait_for_timeout(400)


def medir_ventana(page: Page) -> dict:
    """Registra las medidas de viewport para diagnosticar layout (no confundir viewport con CSS)."""
    return page.evaluate("""() => ({
        innerWidth: window.innerWidth, outerWidth: window.outerWidth,
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth })""")


# ----------------------------------------------------------------- UI: datos de cada cuenta
def crear_datos_ui(sesion: "Sesion", token: str, capturas: Path, prefijo_cuenta: str) -> None:
    """Crea asignatura+nota, presupuesto+gasto y tarea desde la interfaz, con el JWT de la propia cuenta."""
    page = pagina_viva(sesion)
    ir(page, "Académico")
    page.get_by_label("Nombre de la nueva asignatura").fill(f"{PREFIJO}Cálculo {prefijo_cuenta}")
    page.get_by_role("button", name="Agregar").click()
    expect(page.get_by_role("status").filter(has_text="creada")).to_be_visible(timeout=10000)
    page.get_by_label("Evaluación", exact=True).fill(f"{PREFIJO}Parcial {prefijo_cuenta}")
    page.get_by_label("Nota (0 a 5)", exact=True).fill("4,20")
    page.get_by_role("button", name="Registrar nota").click()
    expect(page.get_by_role("status").filter(has_text="Nota registrada")).to_be_visible(timeout=10000)

    ir(page, "Finanzas")
    page.get_by_label("Ingreso mensual (COP)").fill("1.000.000")
    page.get_by_label("Meta de ahorro (COP)").fill("100.000")
    page.get_by_role("button", name="Guardar presupuesto").click()
    expect(page.get_by_role("status").filter(has_text="Presupuesto del mes guardado")).to_be_visible(timeout=10000)
    page.get_by_label("Descripción", exact=True).fill(f"{PREFIJO}Mercado {prefijo_cuenta}")
    page.get_by_label("Categoría", exact=True).fill("Alimentación")
    page.get_by_label("Monto (COP)", exact=True).fill("250.000")
    page.get_by_role("button", name="Registrar gasto").click()
    expect(page.get_by_role("status").filter(has_text="Gasto registrado")).to_be_visible(timeout=10000)

    ir(page, "Tareas")
    page.get_by_label("Título", exact=True).fill(f"{PREFIJO}Entregar taller {prefijo_cuenta}")
    page.locator("#tarea-prioridad").select_option("alta")
    page.get_by_role("button", name="Crear tarea").click()
    expect(page.get_by_role("status").filter(has_text="creada")).to_be_visible(timeout=10000)
    page.screenshot(path=str(capturas / f"02_{prefijo_cuenta.lower()}_tras_crear_datos.png"), full_page=True)
    registrar(f"{sesion.etiqueta} · datos creados desde la interfaz (asignatura, nota, presupuesto, gasto, tarea)", True, "UI")


def leer_y_guardar_ids(token: str, prefijo_cuenta: str) -> None:
    subjects = api("GET", "/api/subjects", token).json()
    subj = next((s for s in subjects if s["nombre"] == f"{PREFIJO}Cálculo {prefijo_cuenta}"), None)
    comprobar(f"{prefijo_cuenta} · asignatura persiste en PostgreSQL (lectura con su JWT)",
              lambda: _ok(subj is not None and subj["total_notas"] == 1, f"asignaturas={len(subjects)}"))
    if subj:
        ids[f"asignatura_{prefijo_cuenta}"] = subj["id"]
        ids[f"nota_{prefijo_cuenta}"] = api("GET", f"/api/subjects/{subj['id']}", token).json()["notas"][0]["id"]

    hoy = datetime.now()
    pres = api("GET", f"/api/finanzas/presupuestos/{hoy.year}/{hoy.month}", token)
    comprobar(f"{prefijo_cuenta} · presupuesto del mes persiste en PostgreSQL",
              lambda: _ok(pres.status_code == 200 and pres.json()["ingreso"].startswith("1000000"), f"HTTP {pres.status_code}"))
    if pres.status_code == 200:
        gasto = next((g for g in pres.json()["gastos"] if g["descripcion"] == f"{PREFIJO}Mercado {prefijo_cuenta}"), None)
        comprobar(f"{prefijo_cuenta} · gasto persiste con categoría e importe exacto",
                  lambda: _ok(gasto is not None and gasto["monto"] == "250000.00" and gasto["categoria"] == "Alimentación", ""))
        if gasto:
            ids[f"gasto_{prefijo_cuenta}"] = gasto["id"]

    tareas = api("GET", "/api/tareas", token).json()
    tarea = next((t for t in tareas if t["titulo"] == f"{PREFIJO}Entregar taller {prefijo_cuenta}"), None)
    comprobar(f"{prefijo_cuenta} · tarea persiste en PostgreSQL", lambda: _ok(tarea is not None, f"tareas={len(tareas)}"))
    if tarea:
        ids[f"tarea_{prefijo_cuenta}"] = tarea["id"]


# ----------------------------------------------------------------- aislamiento RLS cruzado
def pruebas_cruzadas(atacante: str, token_atacante: str, dueno: str, token_dueno: str) -> None:
    """La cuenta 'atacante' intenta leer, modificar y eliminar los registros de 'dueno'."""
    objetivos = [
        ("asignatura", f"/api/subjects/{ids.get(f'asignatura_{dueno}')}", {"nombre": "HACKEADO"}, f"asignatura_{dueno}"),
        ("nota", f"/api/grades/{ids.get(f'nota_{dueno}')}", {"descripcion": "HACKEADO", "nota": 1}, f"nota_{dueno}"),
        ("gasto", f"/api/finanzas/gastos/{ids.get(f'gasto_{dueno}')}", {"descripcion": "HACKEADO"}, f"gasto_{dueno}"),
        ("tarea", f"/api/tareas/{ids.get(f'tarea_{dueno}')}", {"titulo": "HACKEADO"}, f"tarea_{dueno}"),
    ]
    for recurso, ruta, cambio, clave in objetivos:
        if clave not in ids:
            registrar(f"{atacante} sobre {recurso} de {dueno}", False, "no hay registro de prueba del dueño")
            continue
        lectura = api("GET", ruta, token_atacante)
        comprobar(f"{atacante} lee {recurso} de {dueno}: denegado",
                  lambda r=lectura: _ok(r.status_code == 404, f"HTTP {r.status_code}"), f"HTTP {lectura.status_code}")
        mod = api("PATCH", ruta, token_atacante, cambio)
        comprobar(f"{atacante} modifica {recurso} de {dueno}: denegado",
                  lambda r=mod: _ok(r.status_code in (403, 404), f"HTTP {r.status_code}"), f"HTTP {mod.status_code}")
        dele = api("DELETE", ruta, token_atacante)
        comprobar(f"{atacante} elimina {recurso} de {dueno}: denegado",
                  lambda r=dele: _ok(r.status_code in (403, 404), f"HTTP {r.status_code}"), f"HTTP {dele.status_code}")

    asig = ids.get(f"asignatura_{dueno}")
    if asig:
        crear = api("POST", f"/api/subjects/{asig}/grades", token_atacante, {"descripcion": "intrusa", "nota": 1})
        comprobar(f"{atacante} no puede crear notas en una asignatura de {dueno}",
                  lambda: _ok(crear.status_code == 404, f"HTTP {crear.status_code}"), f"HTTP {crear.status_code}")
        propia = api("GET", f"/api/subjects/{asig}", token_dueno)
        comprobar(f"{dueno}: sus registros siguen intactos tras los intentos de {atacante}",
                  lambda: _ok(propia.status_code == 200 and propia.json()["nombre"] == f"{PREFIJO}Cálculo {dueno}", f"HTTP {propia.status_code}"))
        ids_visibles = [s["id"] for s in api("GET", "/api/subjects", token_atacante).json()]
        comprobar(f"{atacante} no ve la asignatura de {dueno} en su listado",
                  lambda: _ok(asig not in ids_visibles, ""))


# ----------------------------------------------------------------- dashboard y copiloto
def dashboard_y_copiloto(token: str, etiqueta: str, prefijo: str) -> None:
    panel = api("GET", "/api/dashboard", token).json()
    nombres = [a["nombre"] for a in panel["academico"]["por_asignatura"]]
    comprobar(f"{etiqueta} · dashboard muestra solo sus asignaturas",
              lambda: _ok(all(n.startswith(PREFIJO) and n.endswith(prefijo) for n in nombres) and nombres != [],
                          str(nombres)), f"asignaturas={len(nombres)}")
    comprobar(f"{etiqueta} · dashboard incluye su presupuesto y tareas reales",
              lambda: _ok(panel["finanzas"]["tiene_presupuesto"] and panel["tareas"]["pendientes"] >= 1,
                          f"pendientes={panel['tareas']['pendientes']}"))

    r = httpx.post(f"{COPILOTO}/api/copilot/chat", headers=cabeceras(token), timeout=30,
                   json={"message": "Resumen de mis datos",
                         "include_context": {"academic": True, "finance": True, "tasks": True}})
    comprobar(f"{etiqueta} · copiloto (SIMULADO) responde", lambda: _ok(r.status_code == 200, f"HTTP {r.status_code}"))
    if r.status_code == 200:
        cuerpo = r.json()
        comprobar(f"{etiqueta} · copiloto declara la respuesta como SIMULADA",
                  lambda: _ok(cuerpo["simulado"] is True and cuerpo["provider"] == "simulado", ""))
        comprobar(f"{etiqueta} · contexto del copiloto con datos reales de su cuenta",
                  lambda: _ok("Académico: 1 asignaturas" in cuerpo["answer"] and "Tareas:" in cuerpo["answer"], cuerpo["answer"][:120]),
                  cuerpo["answer"][:120].replace("\n", " | "))


# ----------------------------------------------------------------- orquestación
def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    carpeta = Path(sys.argv[1]) / marca
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = carpeta / "resultados.json"

    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome", headless=False)
        try:
            cuenta_a = Sesion(navegador, "CUENTA A")
            token_a = autenticar_manual(cuenta_a)

            # Cuenta B: se abre solo después de autenticar A (secuencial).
            cuenta_b = Sesion(navegador, "CUENTA B")
            token_b = autenticar_manual(cuenta_b)
            comprobar("Cuentas A y B son usuarios distintos", lambda: _ok(token_a != token_b, ""))

            crear_datos_ui(cuenta_a, token_a, carpeta, "A")
            leer_y_guardar_ids(token_a, "A")
            crear_datos_ui(cuenta_b, token_b, carpeta, "B")
            leer_y_guardar_ids(token_b, "B")

            pruebas_cruzadas("A", token_a, "B", token_b)
            pruebas_cruzadas("B", token_b, "A", token_a)

            dashboard_y_copiloto(token_a, "A", "A")
            dashboard_y_copiloto(token_b, "B", "B")

            comprobar("Medidas de ventana registradas (cuenta A)",
                      lambda: _ok(medir_ventana(pagina_viva(cuenta_a))["innerWidth"] > 0, ""),
                      str(medir_ventana(pagina_viva(cuenta_a))))
        except VentanaCerrada as exc:
            print(f"\nEjecución interrumpida: {exc}. Las pruebas no completadas NO se cuentan como aprobadas.", flush=True)
        except Exception as exc:  # noqa: BLE001 - registrar la evidencia parcial
            registrar("Ejecución · error no controlado", False, f"{type(exc).__name__}: {str(exc)[:220]}")
            interrupciones.append("error no controlado")
        finally:
            navegador.close()

    (carpeta / "ids_prueba.json").write_text(json.dumps(ids, indent=2), encoding="utf-8")
    fallos = [r for r in resultados if r["resultado"] == "FAIL"]
    salida.write_text(json.dumps({"marca": marca, "total": len(resultados), "fallos": len(fallos),
                                  "interrumpidas": interrupciones, "resultados": resultados},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(resultados)} · Fallos: {len(fallos)} · Interrumpidas: {len(interrupciones)}", flush=True)
    print(f"Resultados: {salida}", flush=True)
    return 1 if fallos or interrupciones else 0


if __name__ == "__main__":
    raise SystemExit(main())
