"""Fase 07C · Verificación de SOLO LECTURA en UNA ventana de Chrome.

Recorrido (una ventana, un contexto, una pestaña durante toda la ejecución):
  1. Inicias sesión TÚ con la cuenta A en la ventana que abre el script.
  2. Verificaciones de A: API con su JWT (en memoria) e interfaz.
  3. «Cerrar sesión» con el botón normal de la app; vuelve el formulario en la MISMA pestaña.
  4. Inicias sesión TÚ con la cuenta B en esa misma pestaña. Verificaciones de B.
  5. Aislamiento RLS con dos clientes HTTP independientes (JWT de A y de B en memoria). Sin ventanas nuevas.
  6. Escribe visual-evidence\\fase-07c\\<marca>\\resultados.json (también si hay fallos o interrupciones).

Garantías:
  - Ningún JWT, contraseña ni storageState se guarda, se imprime o se exporta.
  - Solo peticiones GET a la API. El copiloto se verifica en modo SIMULADO (el backend debe estar en simulado).
  - No crea, modifica ni borra registros remotos.

Uso (PowerShell, desde la raíz del repositorio):
  backend\\.venv\\Scripts\\python.exe frontend\\e2e\\fase07c_verificacion.py visual-evidence\\fase-07c
"""

import importlib.util
import json
import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("seed_supabase", RAIZ / "backend" / "tools" / "seed_supabase.py")
seed = importlib.util.module_from_spec(spec)
sys.modules["seed_supabase"] = seed
spec.loader.exec_module(seed)

FRONT = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000"
PREFIJO = seed.PREFIJO
MES_A = (2026, 10)  # octubre: presupuesto del dataset de A
MES_B = (2026, 11)  # noviembre: presupuesto del dataset de B
SIMULADO = re.compile("simulad", re.IGNORECASE)
TIMEOUT_LOGIN_MS = 900_000
SIN_SESION_JS = "() => !Object.keys(localStorage).some(k => k.startsWith('sb-') && k.endsWith('-auth-token'))"
IDS: dict[str, str] = {}  # solo identificadores de asignatura y nota, para lecturas por UUID


class Registro:
    """Acumula resultados y los escribe en JSON al final, incluidos fallos e interrupciones."""

    def __init__(self, marca: str, carpeta: Path) -> None:
        self.marca = marca
        self.carpeta = carpeta
        self.inicio = datetime.now().isoformat(timespec="seconds")
        self.estado = "EN_CURSO"
        self.items: list[dict] = []

    def add(self, nombre: str, ok: bool, detalle: str = "") -> None:
        self.items.append({"prueba": nombre, "resultado": "PASS" if ok else "FAIL", "detalle": detalle})
        print(("PASS " if ok else "FAIL ") + nombre + (f" | {detalle}" if detalle else ""), flush=True)

    def no_concluyente(self, nombre: str, detalle: str) -> None:
        """Para pruebas que no pueden decidir (p. ej. JWT caducado): no es PASS ni FAIL."""
        self.items.append({"prueba": nombre, "resultado": "NO_CONCLUYENTE", "detalle": detalle})
        print("NO_CONCLUYENTE " + nombre + f" | {detalle}", flush=True)

    def comprobar(self, nombre: str, fn, detalle: str = "") -> bool:
        try:
            fn()
        except AssertionError as exc:
            self.add(nombre, False, f"AssertionError: {str(exc)[:200]}")
            return False
        except PlaywrightError as exc:
            if type(exc).__name__ == "TargetClosedError":
                raise  # lo gestiona main() como interrupción
            self.add(nombre, False, f"{type(exc).__name__}: {str(exc)[:200]}")
            return False
        self.add(nombre, True, detalle)
        return True

    def escribir(self) -> dict:
        resumen = {
            "marca": self.marca,
            "estado": self.estado,
            "inicio": self.inicio,
            "fin": datetime.now().isoformat(timespec="seconds"),
            "total": len(self.items),
            "fallos": sum(1 for i in self.items if i["resultado"] == "FAIL"),
            "no_concluyentes": sum(1 for i in self.items if i["resultado"] == "NO_CONCLUYENTE"),
            "resultados": self.items,
        }
        self.carpeta.mkdir(parents=True, exist_ok=True)
        (self.carpeta / "resultados.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        return resumen


def _ok(cond: bool, texto: str) -> None:
    assert cond, texto


def token_de(pagina: Page) -> str:
    """Lee el JWT del almacenamiento de la propia pestaña. Se queda en memoria; nunca se imprime."""
    token = pagina.evaluate("""() => { for (const k of Object.keys(localStorage)) {
        if (k.startsWith('sb-') && k.endsWith('-auth-token')) { try { return JSON.parse(localStorage[k]).access_token || null; } catch (e) {} } }
        return null; }""")
    _ok(bool(token), "no se encontró la sesión en la pestaña")
    return token


def cliente(token: str) -> httpx.Client:
    """Cliente HTTP independiente por cuenta. Solo se usa para GET."""
    return httpx.Client(base_url=API, headers={"Authorization": f"Bearer {token}"}, timeout=20)


def dinero(valor) -> Decimal:
    return Decimal(str(valor))


def esperar_login_manual(pagina: Page, etiqueta: str) -> None:
    print(f"\n[{etiqueta}] Inicia sesión TÚ en la ventana de Chrome. El script continúa al aparecer «Cerrar sesión».", flush=True)
    pagina.get_by_role("button", name="Cerrar sesión").wait_for(timeout=TIMEOUT_LOGIN_MS)


def cerrar_sesion(pagina: Page, reg: Registro, paginas: list) -> None:
    pagina.get_by_role("button", name="Cerrar sesión").click()
    reg.comprobar("Cierre de sesión A · vuelve el formulario en la misma pestaña",
                  lambda: expect(pagina.get_by_label("Correo electrónico")).to_be_visible(timeout=20000))
    reg.comprobar("Cierre de sesión A · no queda sesión en el navegador",
                  lambda: _ok(pagina.evaluate(SIN_SESION_JS), "queda un token en el almacenamiento"))
    reg.comprobar("Cierre de sesión A · sigue habiendo una sola pestaña", lambda: _ok(len(paginas) == 1, f"{len(paginas)}"))


def esperado_promedios(asignaturas: dict) -> dict[str, Decimal]:
    """Promedio por asignatura con la misma regla del motor (Decimal, dos decimales, mitad hacia arriba)."""
    salida = {}
    for nombre, notas in asignaturas.items():
        valores = [Decimal(n) for _, n in notas]
        salida[f"{PREFIJO}A-{nombre}"] = (sum(valores) / len(valores)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return salida


def verificar_cuenta_a(c: httpx.Client, reg: Registro) -> None:
    subs = [s for s in c.get("/api/subjects").json() if s["nombre"].startswith(f"{PREFIJO}A-")]
    esp = esperado_promedios(seed.ASIGNATURAS_A)
    reg.comprobar("A · 6 asignaturas DEMO con JWT de A", lambda: _ok(len(subs) == 6, f"{len(subs)}"))
    total_notas_esperadas = sum(len(v) for v in seed.ASIGNATURAS_A.values())
    reg.comprobar(f"A · {total_notas_esperadas} notas DEMO en total",
                  lambda: _ok(sum(s["total_notas"] for s in subs) == total_notas_esperadas, ""))
    for s in subs:
        prom = dinero(s["promedio"]) if s["promedio"] is not None else None
        reg.comprobar(f"A · promedio de «{s['nombre'].split('-', 2)[-1]}» coincide con el motor",
                      lambda s=s, p=prom: _ok(p == esp[s["nombre"]], f"API {p} vs esperado {esp[s['nombre']]}"),
                      f"{prom}")
    IDS["A_asignatura"] = subs[0]["id"]
    IDS["A_nota"] = c.get(f"/api/subjects/{subs[0]['id']}").json()["notas"][0]["id"]

    mes = c.get(f"/api/finanzas/presupuestos/{MES_A[0]}/{MES_A[1]:02d}")
    reg.comprobar("A · presupuesto de octubre existe", lambda: _ok(mes.status_code == 200, f"HTTP {mes.status_code}"))
    m = mes.json()
    gastos = [g for g in m["gastos"] if g["descripcion"].startswith(f"{PREFIJO}A-")]
    total = sum(dinero(g["monto"]) for g in gastos)
    reg.comprobar("A · ingreso 2.800.000 y meta 500.000",
                  lambda: _ok(dinero(m["ingreso"]) == Decimal("2800000.00") and dinero(m["meta_ahorro"]) == Decimal("500000.00"), ""))
    reg.comprobar("A · 8 gastos DEMO sumando 2.270.000",
                  lambda: _ok(len(gastos) == 8 and total == Decimal("2270000.00"), f"{len(gastos)} / {total}"))
    reg.comprobar("A · saldo 530.000 y meta cumplida",
                  lambda: _ok(dinero(m["saldo"]) == Decimal("530000.00") and m["meta_cumplida"] is True, str(m["saldo"])))

    tareas = [t for t in c.get("/api/tareas").json() if t["titulo"].startswith(f"{PREFIJO}A-")]
    reg.comprobar("A · 10 tareas DEMO", lambda: _ok(len(tareas) == 10, f"{len(tareas)}"))
    prio = {p: sum(1 for t in tareas if t["prioridad"] == p) for p in ("alta", "media", "baja")}
    reg.comprobar("A · prioridades alta 3 / media 4 / baja 3", lambda: _ok(prio == {"alta": 3, "media": 4, "baja": 3}, str(prio)))
    hoy = date.today()
    pendientes = [t for t in tareas if t["estado"] == "pendiente" and t["fecha_limite"]]
    venc = [t for t in pendientes if date.fromisoformat(t["fecha_limite"]) < hoy]
    prox = [t for t in pendientes if 0 <= (date.fromisoformat(t["fecha_limite"]) - hoy).days <= 7]
    reg.comprobar("A · 3 vencidas y 3 próximas según la fecha de hoy",
                  lambda: _ok(len(venc) == 3 and len(prox) == 3, f"vencidas={len(venc)} próximas={len(prox)}"))


def verificar_cuenta_b(c: httpx.Client, reg: Registro) -> None:
    subs = [s for s in c.get("/api/subjects").json() if s["nombre"].startswith(f"{PREFIJO}B-")]
    reg.comprobar("B · 1 asignatura DEMO", lambda: _ok(len(subs) == 1, f"{len(subs)}"))
    reg.comprobar("B · 2 notas DEMO", lambda: _ok(sum(s["total_notas"] for s in subs) == 2, ""))
    IDS["B_asignatura"] = subs[0]["id"]
    IDS["B_nota"] = c.get(f"/api/subjects/{subs[0]['id']}").json()["notas"][0]["id"]

    m = c.get(f"/api/finanzas/presupuestos/{MES_B[0]}/{MES_B[1]:02d}").json()
    gastos = [g for g in m["gastos"] if g["descripcion"].startswith(f"{PREFIJO}B-")]
    reg.comprobar("B · noviembre: ingreso 1.200.000 y saldo 900.000",
                  lambda: _ok(dinero(m["ingreso"]) == Decimal("1200000.00") and dinero(m["saldo"]) == Decimal("900000.00"), str(m["saldo"])))
    reg.comprobar("B · meta de 150.000 cumplida", lambda: _ok(m["meta_cumplida"] is True, ""))
    reg.comprobar("B · 1 gasto DEMO", lambda: _ok(len(gastos) == 1, f"{len(gastos)}"))

    tareas = [t for t in c.get("/api/tareas").json() if t["titulo"].startswith(f"{PREFIJO}B-")]
    reg.comprobar("B · 1 tarea DEMO", lambda: _ok(len(tareas) == 1, f"{len(tareas)}"))


def ui_cuenta_a(pagina: Page, reg: Registro, carpeta: Path) -> None:
    nav = pagina.get_by_role("navigation", name="Módulos")
    nav.get_by_role("button", name="Académico").click()
    reg.comprobar("UI · A ve su asignatura DEMO",
                  lambda: expect(pagina.get_by_text("DEMO-AURORA-A-Cálculo diferencial").first).to_be_visible())
    pagina.screenshot(path=str(carpeta / "01_a_academico.png"), full_page=True)

    nav.get_by_role("button", name="Finanzas").click()
    selector_mes = pagina.locator("#periodo")  # id real del selector; «Mes» por etiqueta coincide también con el formulario
    selector_mes.fill(f"{MES_A[0]}-{MES_A[1]:02d}")
    reg.comprobar("UI · selector de mes queda en 2026-10",
                  lambda: expect(selector_mes).to_have_value(f"{MES_A[0]}-{MES_A[1]:02d}", timeout=5000))
    saldo = pagina.locator(".kpi").filter(has_text="Saldo").locator(".kpi__valor")
    reg.comprobar("UI · A, octubre: KPI Saldo muestra 530.000",
                  lambda: expect(saldo).to_contain_text("530.000", timeout=10000))
    pagina.screenshot(path=str(carpeta / "02_a_finanzas_octubre.png"), full_page=True)

    nav.get_by_role("button", name="Tareas").click()
    reg.comprobar("UI · A ve su tarea DEMO",
                  lambda: expect(pagina.get_by_text("DEMO-AURORA-A-Entregar taller de cálculo").first).to_be_visible())
    pagina.screenshot(path=str(carpeta / "03_a_tareas.png"), full_page=True)

    pagina.reload()
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Tareas").click()
    reg.comprobar("Persistencia · A tras recargar la pestaña",
                  lambda: expect(pagina.get_by_text("DEMO-AURORA-A-Entregar taller de cálculo").first).to_be_visible(timeout=15000))

    for nombre, ancho, alto in [("movil", 390, 844), ("escritorio", 1440, 900)]:
        pagina.set_viewport_size({"width": ancho, "height": alto})
        nav.get_by_role("button", name="Mi espacio").click()
        pagina.wait_for_timeout(500)
        desborde = pagina.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        reg.comprobar(f"Responsive · dashboard de A {nombre} {ancho}px sin desplazamiento horizontal",
                      lambda d=desborde: _ok(d <= 1, f"desborde {d}px"), f"{desborde}px")
        pagina.screenshot(path=str(carpeta / f"05_a_dashboard_{nombre}.png"), full_page=True)


def ui_cuenta_b(pagina: Page, reg: Registro, carpeta: Path) -> None:
    pagina.get_by_role("navigation", name="Módulos").get_by_role("button", name="Académico").click()
    reg.comprobar("UI · B ve su asignatura DEMO",
                  lambda: expect(pagina.get_by_text("DEMO-AURORA-B-Historia de Colombia").first).to_be_visible())
    reg.comprobar("UI · B no ve asignaturas de A",
                  lambda: expect(pagina.get_by_text("DEMO-AURORA-A-", exact=False)).to_have_count(0))
    pagina.screenshot(path=str(carpeta / "04_b_academico.png"), full_page=True)


def copiloto_ui(pagina: Page, reg: Registro, etiqueta: str, peticiones: list[str], carpeta: Path) -> None:
    """Página completa y widget, con proveedor SIMULADO. Cada envío debe generar exactamente una petición."""
    nav = pagina.get_by_role("navigation", name="Módulos")
    nav.get_by_role("button", name="Copiloto").click()
    base = len(peticiones)
    pagina.locator("#pregunta-copiloto").fill("¿Cuál es mi promedio académico?")
    pagina.get_by_role("button", name="Enviar").first.click()
    reg.comprobar(f"Copiloto · {etiqueta} (página) responde con SIMULADO",
                  lambda: expect(pagina.get_by_label("Respuesta del copiloto").last).to_contain_text(SIMULADO, timeout=25000))
    reg.comprobar(f"Copiloto · {etiqueta} (página) exactamente 1 petición",
                  lambda: _ok(len(peticiones) - base == 1, f"{len(peticiones) - base}"))
    pagina.screenshot(path=str(carpeta / f"06_{etiqueta.lower()}_copiloto_pagina.png"), full_page=True)

    nav.get_by_role("button", name="Mi espacio").click()
    pagina.get_by_role("button", name="Habla con AURORA").click()
    base = len(peticiones)
    pagina.locator("#pregunta-widget").fill("¿Qué tareas están vencidas?")
    pagina.get_by_role("button", name="Enviar").last.click()
    reg.comprobar(f"Copiloto · {etiqueta} (widget) responde con SIMULADO",
                  lambda: expect(pagina.get_by_label("Respuesta del copiloto").last).to_contain_text(SIMULADO, timeout=25000))
    reg.comprobar(f"Copiloto · {etiqueta} (widget) exactamente 1 petición",
                  lambda: _ok(len(peticiones) - base == 1, f"{len(peticiones) - base}"))
    pagina.screenshot(path=str(carpeta / f"07_{etiqueta.lower()}_copiloto_widget.png"))
    # Cierra el widget para dejar la pestaña en un estado limpio antes de la siguiente fase de la prueba.
    pagina.keyboard.press("Escape")


def aislamiento(reg: Registro, dueno: str, c_otro: httpx.Client, nombre_otro: str) -> None:
    """Lectura por UUID de la cuenta «dueno» con el JWT de la otra cuenta: debe responder 404 y no mostrar datos."""
    for recurso, ruta in [("asignatura", f"/api/subjects/{IDS[f'{dueno}_asignatura']}"),
                          ("nota", f"/api/grades/{IDS[f'{dueno}_nota']}")]:
        r = c_otro.get(ruta)
        reg.comprobar(f"RLS · {nombre_otro} lee {recurso} de {dueno} por UUID: denegado",
                      lambda r=r: _ok(r.status_code == 404 and PREFIJO not in r.text, f"HTTP {r.status_code}"),
                      f"HTTP {r.status_code}")
    for nombre, ruta in [("asignaturas", "/api/subjects"), ("tareas", "/api/tareas")]:
        texto = c_otro.get(ruta).text
        reg.comprobar(f"RLS · lista de {nombre} de {nombre_otro} sin datos de {dueno}",
                      lambda t=texto: _ok(f"{PREFIJO}{dueno}-" not in t, ""))
    mes = MES_B if dueno == "B" else MES_A
    r = c_otro.get(f"/api/finanzas/presupuestos/{mes[0]}/{mes[1]:02d}")
    reg.comprobar(f"RLS · {nombre_otro} no ve gastos de {dueno} en su mes",
                  lambda: _ok(f"{PREFIJO}{dueno}-" not in r.text, f"HTTP {r.status_code}"))


def token_vigente(reg: Registro, nombre: str, c: httpx.Client) -> bool:
    """Antes del RLS: el JWT debe seguir aceptándose. Un 401/403 significa «no concluyente», no «denegado por RLS»."""
    r = c.get("/api/subjects")
    if r.status_code == 200:
        reg.add(f"Token de {nombre} vigente antes de RLS", True, "HTTP 200")
        return True
    if r.status_code in (401, 403):
        reg.no_concluyente(f"Token de {nombre} vigente antes de RLS",
                           f"HTTP {r.status_code}: el JWT ya no se acepta; no es una denegación RLS")
        return False
    reg.add(f"Token de {nombre} vigente antes de RLS", False, f"HTTP {r.status_code}")
    return False


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    carpeta = Path(sys.argv[1]) / marca
    reg = Registro(marca, carpeta)
    navegador = None
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(channel="chrome", headless=False)
            ctx = navegador.new_context(no_viewport=True)  # contexto nuevo: sin sesiones previas
            paginas: list = []
            ctx.on("page", lambda pg: paginas.append(pg))
            pagina = ctx.new_page()
            peticiones: list[str] = []
            pagina.on("request", lambda r: peticiones.append(r.url)
                      if r.method == "POST" and "/api/copilot/chat" in r.url else None)
            carpeta.mkdir(parents=True, exist_ok=True)

            pagina.goto(FRONT)
            esperar_login_manual(pagina, "CUENTA A")
            token_a = token_de(pagina)
            reg.add("Inicio de sesión manual · A en la pestaña única", True)
            c_a = cliente(token_a)
            verificar_cuenta_a(c_a, reg)
            ui_cuenta_a(pagina, reg, carpeta)
            copiloto_ui(pagina, reg, "A", peticiones, carpeta)
            cerrar_sesion(pagina, reg, paginas)

            esperar_login_manual(pagina, "CUENTA B")
            token_b = token_de(pagina)
            reg.add("Inicio de sesión manual · B en la misma pestaña", True)
            reg.comprobar("Una sola pestaña durante toda la ejecución", lambda: _ok(len(paginas) == 1, f"{len(paginas)}"))
            c_b = cliente(token_b)
            verificar_cuenta_b(c_b, reg)
            ui_cuenta_b(pagina, reg, carpeta)
            copiloto_ui(pagina, reg, "B", peticiones, carpeta)

            # Vigencia de ambos JWT (el logout es global): sin token vigente no se puede concluir el RLS.
            vigente_a = token_vigente(reg, "A", c_a)
            vigente_b = token_vigente(reg, "B", c_b)

            # Copiloto en modo simulado, con cada JWT vigente (solo lectura del estado).
            for nombre, c, vigente in (("A", c_a, vigente_a), ("B", c_b, vigente_b)):
                if not vigente:
                    reg.no_concluyente(f"Copiloto · estado {nombre}", "JWT no vigente")
                    continue
                estado = c.get("/api/copilot/estado").json()
                reg.comprobar(f"Copiloto · estado {nombre}: proveedor simulado, sin OpenRouter",
                              lambda e=estado: _ok(e.get("proveedor") == "simulado" and e.get("simulado") is True, str(e.get("proveedor"))))

            # Aislamiento RLS: cada JWT vigente intenta leer los datos del otro propietario.
            if vigente_a:
                aislamiento(reg, "B", c_a, "A")
            else:
                reg.no_concluyente("RLS · lectura de B con el JWT de A", "JWT de A no vigente")
            if vigente_b:
                aislamiento(reg, "A", c_b, "B")
            else:
                reg.no_concluyente("RLS · lectura de A con el JWT de B", "JWT de B no vigente")
            reg.comprobar("Ejecución sin ventanas adicionales", lambda: _ok(len(paginas) == 1, f"{len(paginas)}"))
            reg.estado = "COMPLETA"
    except KeyboardInterrupt:
        reg.estado = "INTERRUMPIDA_POR_USUARIO"
        reg.add("Ejecución interrumpida con Ctrl+C", False, "KeyboardInterrupt")
    except PlaywrightError as exc:
        if type(exc).__name__ == "TargetClosedError":
            reg.estado = "INTERRUMPIDA_VENTANA_CERRADA"
            reg.add("Ventana de Chrome cerrada durante la ejecución", False, "TargetClosedError controlado")
        else:
            reg.estado = "ERROR"
            reg.add("Error de Playwright no esperado", False, f"{type(exc).__name__}: {str(exc)[:200]}")
    except Exception as exc:  # noqa: BLE001 - se registra y se termina limpiamente
        reg.estado = "ERROR"
        reg.add("Error no esperado", False, f"{type(exc).__name__}: {str(exc)[:200]}")
    finally:
        if navegador is not None:
            try:
                navegador.close()
            except Exception:  # noqa: BLE001
                pass
        resumen = reg.escribir()
    print(f"\nEstado: {resumen['estado']} · Total: {resumen['total']} · Fallos: {resumen['fallos']}", flush=True)
    print(f"Resultados: {carpeta / 'resultados.json'}", flush=True)
    return 0 if resumen["estado"] == "COMPLETA" and resumen["fallos"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
