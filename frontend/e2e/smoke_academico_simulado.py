"""Prueba de UI del módulo Académico con SESIÓN SIMULADA y API INTERCEPTADA en el navegador.
NO es integración real con Supabase ni con FastAPI: valida la lógica de la interfaz únicamente.

Requiere el backend sirviendo un build con VITE_SUPABASE_URL ficticia en http://127.0.0.1:8765.
Uso (desde frontend/): python e2e/smoke_academico_simulado.py <carpeta_para_capturas>
"""
import json
import sys
import time
import uuid
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
REF = "proyecto-ficticio"  # clave de sesión de supabase-js = sb-<ref>-auth-token
USER_ID = "11111111-1111-1111-1111-111111111111"

asignaturas = []
notas = []
resultados = []


def check(nombre, ok, extra=""):
    resultados.append((nombre, ok))
    print(("PASS " if ok else "FAIL ") + nombre + (f" | {extra}" if extra else ""))


def promedio_de(subject_id):
    valores = [float(n["nota"]) for n in notas if n["subject_id"] == subject_id]
    if not valores:
        return None, None
    prom = round(sum(valores) / len(valores) + 1e-9, 2)
    return f"{prom:.2f}", prom >= 3.0


def manejar_api(ruta, metodo, cuerpo):
    path = ruta.replace(BASE, "")
    if path == "/api/subjects" and metodo == "GET":
        return 200, [
            {**a, "total_notas": sum(1 for n in notas if n["subject_id"] == a["id"]),
             "promedio": promedio_de(a["id"])[0], "aprobado": promedio_de(a["id"])[1]}
            for a in asignaturas
        ]
    if path == "/api/subjects" and metodo == "POST":
        nombre = cuerpo["nombre"]
        if any(a["nombre"].lower() == nombre.lower() for a in asignaturas):
            return 409, {"detail": "Ya existe un registro con esos datos."}
        ahora = "2026-11-11T12:00:00Z"
        nueva = {"id": str(uuid.uuid4()), "nombre": nombre, "created_at": ahora, "updated_at": ahora}
        asignaturas.append(nueva)
        return 201, {**nueva, "total_notas": 0, "promedio": None, "aprobado": None}
    if path.startswith("/api/subjects/") and path.endswith("/grades") and metodo == "POST":
        sid = path.split("/")[3]
        valor = cuerpo["nota"]
        if not (0 <= float(valor) <= 5):
            return 422, {"detail": [{"loc": ["body", "nota"], "msg": "La nota debe estar entre 0 y 5."}]}
        nueva = {"id": str(uuid.uuid4()), "subject_id": sid, "descripcion": cuerpo["descripcion"],
                 "nota": f"{float(valor):.2f}", "aprobado": float(valor) >= 3.0,
                 "created_at": "2026-11-11T12:00:00Z", "updated_at": "2026-11-11T12:00:00Z"}
        notas.append(nueva)
        return 201, nueva
    if path.startswith("/api/subjects/") and metodo == "GET":
        sid = path.split("/")[3]
        asig = next((a for a in asignaturas if a["id"] == sid), None)
        if not asig:
            return 404, {"detail": "La asignatura no existe o no es accesible."}
        prom, aprob = promedio_de(sid)
        mis = [n for n in notas if n["subject_id"] == sid]
        return 200, {**asig, "total_notas": len(mis), "promedio": prom, "aprobado": aprob, "notas": mis}
    if path.startswith("/api/grades/") and metodo == "DELETE":
        gid = path.split("/")[3]
        notas[:] = [n for n in notas if n["id"] != gid]
        return 204, None
    if path.startswith("/api/subjects/") and metodo == "DELETE":
        sid = path.split("/")[3]
        asignaturas[:] = [a for a in asignaturas if a["id"] != sid]
        notas[:] = [n for n in notas if n["subject_id"] != sid]
        return 204, None
    return 404, {"detail": "Recurso no encontrado."}


def sesion_simulada():
    ahora = int(time.time())
    return json.dumps({
        "access_token": "token.simulado.no.real",
        "token_type": "bearer",
        "expires_in": 3600,
        "expires_at": ahora + 3600,
        "refresh_token": "refresh-simulado",
        "user": {"id": USER_ID, "aud": "authenticated", "role": "authenticated",
                 "email": "alumna.prueba@ejemplo.com", "app_metadata": {}, "user_metadata": {},
                 "created_at": "2026-11-01T00:00:00Z"},
    })


with sync_playwright() as p:
    navegador = p.chromium.launch(channel="chrome", headless=True)
    contexto = navegador.new_context(viewport={"width": 1280, "height": 860})
    contexto.add_init_script(
        f"localStorage.setItem('sb-{REF}-auth-token', {json.dumps(sesion_simulada())});"
    )
    pagina = contexto.new_page()
    errores_js = []
    pagina.on("pageerror", lambda e: errores_js.append(str(e)))
    peticiones_sin_bearer = []

    def ruta_api(route, request):
        if "Bearer " not in (request.headers.get("authorization") or ""):
            peticiones_sin_bearer.append(request.url)
        cuerpo = json.loads(request.post_data) if request.post_data else None
        status, payload = manejar_api(request.url, request.method, cuerpo)
        if payload is None:
            route.fulfill(status=status, body="")
        else:
            route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))

    pagina.route("**/api/**", ruta_api)
    pagina.goto(BASE, wait_until="networkidle")
    try:
        pagina.get_by_role("heading", name="Asignaturas y notas").wait_for(timeout=15000)
    except Exception:
        pagina.screenshot(path=sys.argv[1] + "/fallo_entrada.png", full_page=True)
        print("DIAG texto pagina:", pagina.inner_text("body")[:400])
        print("DIAG errores_js:", errores_js)
        raise
    check("sesión simulada: entra al módulo Académico", True)

    # Crear asignatura
    pagina.get_by_placeholder("Ej.: Programación I").fill("Programación")
    pagina.get_by_role("button", name="Crear").click()
    pagina.locator(".subject-item", has_text="Programación").first.wait_for(timeout=10000)
    check("crear asignatura: aparece en la lista", pagina.locator(".subject-item", has_text="Programación").count() == 1)
    check("crear asignatura: estado vacío de notas visible",
          pagina.get_by_text("Esta asignatura aún no tiene notas.").is_visible())

    # Validación de nota fuera de rango (cliente)
    pagina.get_by_placeholder("Ej.: Parcial 1").fill("Parcial 1")
    pagina.get_by_placeholder("4.2").fill("6")
    pagina.get_by_role("button", name="Agregar nota").click()
    check("validación cliente: nota 6 rechazada",
          "entre 0 y 5" in pagina.get_by_role("alert").inner_text())

    # Agregar notas válidas
    for desc, nota in [("Parcial 1", "4.5"), ("Parcial 2", "2,0")]:
        pagina.get_by_placeholder("Ej.: Parcial 1").fill(desc)
        pagina.get_by_placeholder("4.2").fill(nota)
        pagina.get_by_role("button", name="Agregar nota").click()
        pagina.get_by_role("cell", name=desc, exact=True).wait_for(timeout=10000)

    promedio_txt = pagina.locator(".average-card__value").inner_text().strip()
    check("promedio calculado: 3.25 para notas 4.5 y 2.0", promedio_txt == "3.25", promedio_txt)
    check("estado del promedio: Aprobado",
          pagina.locator(".average-card .badge").inner_text().strip() == "Aprobado")
    check("tabla: 2 notas listadas", pagina.locator("tbody tr").count() == 2)
    pagina.screenshot(path=sys.argv[1] + "/academico_simulado_escritorio.png", full_page=True)

    # Recargar: los datos vuelven desde el 'backend' (simulado) y la sesión persiste
    pagina.reload(wait_until="networkidle")
    pagina.locator(".subject-item", has_text="Programación").first.click()
    pagina.get_by_role("cell", name="Parcial 1", exact=True).wait_for(timeout=10000)
    check("recarga: notas se recuperan del servidor", pagina.locator("tbody tr").count() == 2)

    # Móvil sin scroll horizontal
    pagina.set_viewport_size({"width": 360, "height": 740})
    pagina.wait_for_timeout(300)
    desbordados = pagina.evaluate("""() => {
      const w = document.documentElement.clientWidth;
      return [...document.querySelectorAll('body *')]
        .filter(el => el.getBoundingClientRect().right > w + 1)
        .slice(0, 8)
        .map(el => el.tagName.toLowerCase() + '.' + (el.className?.toString() || '') + ' right=' + Math.round(el.getBoundingClientRect().right));
    }""")
    print("DIAG desbordados:", desbordados)
    check("académico (360px): sin scroll horizontal",
          pagina.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
    pagina.screenshot(path=sys.argv[1] + "/academico_simulado_movil.png", full_page=True)
    pagina.set_viewport_size({"width": 1280, "height": 860})

    # Cerrar sesión
    pagina.get_by_role("button", name="Cerrar sesión").click()
    pagina.get_by_role("heading", name="Inicia sesión").wait_for(timeout=10000)
    check("cerrar sesión: vuelve a la pantalla de acceso", True)

    check("todas las peticiones llevaron Bearer", len(peticiones_sin_bearer) == 0,
          "; ".join(peticiones_sin_bearer[:3]))
    check("sin excepciones no capturadas", len(errores_js) == 0, "; ".join(errores_js))
    navegador.close()

fallidos = [n for n, ok in resultados if not ok]
print(f"\nTOTAL {len(resultados)} | OK {len(resultados) - len(fallidos)} | FALLIDOS {len(fallidos)}")
sys.exit(1 if fallidos else 0)
