"""Pruebas de integración de la API con SQLite real (archivo temporal por prueba).

Cubren: arranque y migraciones, modo demo y su rechazo en producción, CRUD académico,
presupuesto y tareas, validaciones de entrada, aislamiento entre usuarios y persistencia
después de reiniciar la aplicación.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_verifier
from app.config import ConfigurationError, get_settings
from app.infrastructure.sqlite.database import connect, migrate, open_migrated
from app.infrastructure.sqlite.seed import seed_demo
from app.main import create_app
from app.security.principal import DEMO_USER_ID


@pytest.fixture
def entorno_sqlite(tmp_path, monkeypatch):
    """Configura SQLite local en un archivo temporal, sin Supabase y sin modo demo."""
    from app.api import deps

    ruta = tmp_path / "aurora_prueba.sqlite3"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(ruta))
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "")
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()
    yield ruta
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()


@pytest.fixture
def cliente(entorno_sqlite, verifier):
    app = create_app()
    app.dependency_overrides[get_verifier] = lambda: verifier
    return TestClient(app)


def _cabecera(make_token, sub=None):
    import uuid

    sub = sub or str(uuid.uuid4())
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


# ----------------------------------------------------------- arranque y modo demo
def test_arranque_aplica_migraciones_una_sola_vez(entorno_sqlite, verifier):
    create_app()
    create_app()  # segunda vez: no debe fallar ni duplicar
    conn = connect(entorno_sqlite)
    versiones = [f["version"] for f in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert versiones == ["0001_academico", "0002_finanzas_tareas"]
    assert migrate(conn) == []  # nada pendiente
    conn.close()


def test_modo_demo_rechazado_en_produccion(entorno_sqlite, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError, match="no arranca"):
        create_app()


def test_modo_demo_requiere_sqlite(entorno_sqlite, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "supabase")
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError, match="sqlite"):
        create_app()


def test_persistencia_desconocida_se_rechaza(entorno_sqlite, monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "mysql")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        get_settings()


def test_modo_demo_permite_sin_token_y_lo_declara(entorno_sqlite, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    c = TestClient(create_app())
    modo = c.get("/api/modo").json()
    assert modo["modo"] == "demo"
    assert "MODO DEMO" in modo["aviso"]
    assert c.get("/api/subjects").status_code == 200  # sin Authorization, solo en demo


def test_produccion_sin_demo_exige_token_aunque_sea_sqlite(cliente):
    assert cliente.get("/api/modo").json()["modo"] == "produccion"
    assert cliente.get("/api/subjects").status_code == 401
    assert cliente.get("/api/finanzas/presupuestos").status_code == 401


def test_modo_demo_no_aparece_en_produccion_con_supabase(monkeypatch, entorno_sqlite):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "supabase")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    modo = TestClient(create_app()).get("/api/modo").json()
    assert modo == {"modo": "produccion", "persistencia": "supabase", "aviso": None}


# ----------------------------------------------------------- académico
def test_crud_academico_con_promedio_objetivo_y_resumen(cliente, make_token):
    h = _cabecera(make_token)
    asig = cliente.post("/api/subjects", headers=h, json={"nombre": "Cálculo"}).json()
    assert asig["origen"] == "real"
    sid = asig["id"]
    for descripcion, nota in [("Parcial 1", 4.5), ("Parcial 2", 3.0), ("Taller", 2.9)]:
        assert cliente.post(f"/api/subjects/{sid}/grades", headers=h,
                            json={"descripcion": descripcion, "nota": nota}).status_code == 201

    detalle = cliente.get(f"/api/subjects/{sid}", headers=h).json()
    assert detalle["promedio"] == "3.47" and detalle["aprobado"] is True and detalle["total_notas"] == 3

    objetivo = cliente.get(f"/api/subjects/{sid}/objetivo", params={"objetivo": "3.5"}, headers=h).json()
    assert objetivo["posible"] is True and objetivo["nota_minima"] == "3.60"
    imposible = cliente.get(f"/api/subjects/{sid}/objetivo", params={"objetivo": "4.9"}, headers=h).json()
    assert imposible["posible"] is False and imposible["nota_minima"] is None
    assert cliente.get(f"/api/subjects/{sid}/objetivo", params={"objetivo": "6"}, headers=h).status_code == 422

    resumen = cliente.get("/api/academico/resumen", headers=h).json()
    assert resumen["total_asignaturas"] == 1 and resumen["aprobadas"] == 1 and resumen["promedio_general"] == "3.47"

    renombrada = cliente.patch(f"/api/subjects/{sid}", headers=h, json={"nombre": "Cálculo II"}).json()
    assert renombrada["nombre"] == "Cálculo II"

    assert cliente.delete(f"/api/subjects/{sid}", headers=h).status_code == 204
    assert cliente.get("/api/subjects", headers=h).json() == []
    assert cliente.get("/api/academico/resumen", headers=h).json()["total_asignaturas"] == 0


def test_asignatura_duplicada_responde_409(cliente, make_token):
    h = _cabecera(make_token)
    assert cliente.post("/api/subjects", headers=h, json={"nombre": "Física"}).status_code == 201
    assert cliente.post("/api/subjects", headers=h, json={"nombre": "física"}).status_code == 409


def test_nota_fuera_de_rango_no_se_guarda(cliente, make_token):
    h = _cabecera(make_token)
    sid = cliente.post("/api/subjects", headers=h, json={"nombre": "Química"}).json()["id"]
    assert cliente.post(f"/api/subjects/{sid}/grades", headers=h,
                        json={"descripcion": "X", "nota": 5.01}).status_code == 422
    assert cliente.get(f"/api/subjects/{sid}", headers=h).json()["total_notas"] == 0


# ----------------------------------------------------------- aislamiento entre usuarios
def test_usuarios_distintos_no_se_ven_ni_modifican(cliente, make_token):
    ana = _cabecera(make_token)
    luis = _cabecera(make_token)
    sid = cliente.post("/api/subjects", headers=ana, json={"nombre": "Historia"}).json()["id"]
    gid = cliente.post(f"/api/subjects/{sid}/grades", headers=ana,
                       json={"descripcion": "Parcial", "nota": 4.0}).json()["id"]

    assert cliente.get("/api/subjects", headers=luis).json() == []
    assert cliente.get(f"/api/subjects/{sid}", headers=luis).status_code == 404
    assert cliente.patch(f"/api/subjects/{sid}", headers=luis, json={"nombre": "Robado"}).status_code == 404
    assert cliente.delete(f"/api/subjects/{sid}", headers=luis).status_code == 404
    assert cliente.post(f"/api/subjects/{sid}/grades", headers=luis,
                        json={"descripcion": "Intruso", "nota": 1}).status_code == 404
    assert cliente.get(f"/api/grades/{gid}", headers=luis).status_code == 404
    assert cliente.delete(f"/api/grades/{gid}", headers=luis).status_code == 404
    assert cliente.get(f"/api/subjects/{sid}", headers=ana).json()["nombre"] == "Historia"


def test_presupuesto_y_tareas_aislados_entre_usuarios(cliente, make_token):
    ana = _cabecera(make_token)
    luis = _cabecera(make_token)
    hoy = date.today()
    cliente.put(f"/api/finanzas/presupuestos/{hoy.year}/{hoy.month}", headers=ana,
                json={"ingreso": 1000000, "meta_ahorro": 0})
    tarea_id = cliente.post("/api/tareas", headers=ana,
                            json={"titulo": "Privada", "prioridad": "alta"}).json()["id"]

    assert cliente.get(f"/api/finanzas/presupuestos/{hoy.year}/{hoy.month}", headers=luis).status_code == 404
    assert cliente.get("/api/tareas", headers=luis).json() == []
    assert cliente.patch(f"/api/tareas/{tarea_id}", headers=luis, json={"estado": "completada"}).status_code == 404
    assert cliente.delete(f"/api/tareas/{tarea_id}", headers=luis).status_code == 404


# ----------------------------------------------------------- finanzas
def _mes(hoy=None):
    hoy = hoy or date.today()
    return hoy.year, hoy.month


def test_presupuesto_completo_con_categorias_y_metas(cliente, make_token):
    h = _cabecera(make_token)
    anio, mes = _mes()
    r = cliente.put(f"/api/finanzas/presupuestos/{anio}/{mes}", headers=h,
                    json={"ingreso": 2000000, "meta_ahorro": 300000})
    assert r.status_code == 200 and r.json()["saldo"] == "2000000.00"

    gastos = [
        {"descripcion": "Arriendo", "categoria": "Vivienda", "monto": 600000, "tipo": "fijo", "fecha": f"{anio}-{mes:02d}-01"},
        {"descripcion": "Mercado", "categoria": "Alimentación", "monto": 250000, "tipo": "variable", "fecha": f"{anio}-{mes:02d}-02"},
        {"descripcion": "Arriendo 2", "categoria": "Vivienda", "monto": 150000, "tipo": "fijo", "fecha": f"{anio}-{mes:02d}-03"},
    ]
    for g in gastos:
        assert cliente.post(f"/api/finanzas/presupuestos/{anio}/{mes}/gastos", headers=h, json=g).status_code == 201

    detalle = cliente.get(f"/api/finanzas/presupuestos/{anio}/{mes}", headers=h).json()
    assert detalle["gastos_total"] == "1000000.00"
    assert detalle["gastos_fijos"] == "750000.00" and detalle["gastos_variables"] == "250000.00"
    assert detalle["saldo"] == "1000000.00"
    assert detalle["disponible_para_gastar"] == "1700000.00"
    assert detalle["meta_cumplida"] is True and detalle["ahorro_logrado"] == "1000000.00"
    assert [c["categoria"] for c in detalle["categorias"]] == ["Vivienda", "Alimentación"]
    assert detalle["categorias"][0]["porcentaje"] == "75.00"
    assert len(detalle["gastos"]) == 3


def test_editar_y_eliminar_gasto(cliente, make_token):
    h = _cabecera(make_token)
    anio, mes = _mes()
    cliente.put(f"/api/finanzas/presupuestos/{anio}/{mes}", headers=h, json={"ingreso": 500000})
    gid = cliente.post(f"/api/finanzas/presupuestos/{anio}/{mes}/gastos", headers=h,
                       json={"descripcion": "Taxi", "categoria": "Transporte", "monto": 20000,
                             "tipo": "variable", "fecha": f"{anio}-{mes:02d}-10"}).json()["id"]

    editado = cliente.patch(f"/api/finanzas/gastos/{gid}", headers=h, json={"monto": 35000, "categoria": "Movilidad"})
    assert editado.status_code == 200 and editado.json()["monto"] == "35000.00"
    assert editado.json()["categoria"] == "Movilidad"

    assert cliente.delete(f"/api/finanzas/gastos/{gid}", headers=h).status_code == 204
    assert cliente.get(f"/api/finanzas/presupuestos/{anio}/{mes}", headers=h).json()["gastos"] == []


@pytest.mark.parametrize(
    ("cuerpo", "codigo"),
    [
        ({"descripcion": "X", "categoria": "Ocio", "monto": -1, "tipo": "fijo", "fecha": "HOY"}, 422),
        ({"descripcion": "X", "categoria": "Ocio", "monto": "abc", "tipo": "fijo", "fecha": "HOY"}, 422),
        ({"descripcion": "X", "categoria": "Ocio", "monto": 10, "tipo": "ocasional", "fecha": "HOY"}, 422),
        ({"descripcion": "", "categoria": "Ocio", "monto": 10, "tipo": "fijo", "fecha": "HOY"}, 422),
        ({"descripcion": "X", "categoria": "", "monto": 10, "tipo": "fijo", "fecha": "HOY"}, 422),
        ({"descripcion": "X", "monto": 10, "tipo": "fijo", "fecha": "HOY"}, 422),  # sin categoría
        ({"descripcion": "X", "categoria": "Ocio", "monto": 10, "tipo": "fijo"}, 422),  # sin fecha
        ({"descripcion": "X", "categoria": "Ocio", "monto": 10, "tipo": "fijo", "fecha": "2026-02-31"}, 422),
        ({"descripcion": "X", "categoria": "Ocio", "monto": 10, "tipo": "fijo", "fecha": "HOY", "user_id": "x"}, 422),
    ],
)
def test_gasto_invalido_responde_422(cliente, make_token, cuerpo, codigo):
    h = _cabecera(make_token)
    anio, mes = _mes()
    cliente.put(f"/api/finanzas/presupuestos/{anio}/{mes}", headers=h, json={"ingreso": 500000})
    if cuerpo.get("fecha") == "HOY":
        cuerpo["fecha"] = date.today().isoformat()
    r = cliente.post(f"/api/finanzas/presupuestos/{anio}/{mes}/gastos", headers=h, json=cuerpo)
    assert r.status_code == codigo


def test_gasto_fuera_del_mes_se_rechaza(cliente, make_token):
    h = _cabecera(make_token)
    anio, mes = _mes()
    cliente.put(f"/api/finanzas/presupuestos/{anio}/{mes}", headers=h, json={"ingreso": 500000})
    r = cliente.post(f"/api/finanzas/presupuestos/{anio}/{mes}/gastos", headers=h,
                     json={"descripcion": "X", "categoria": "Ocio", "monto": 10, "tipo": "fijo", "fecha": "2001-01-15"})
    assert r.status_code == 422


def test_gasto_sin_presupuesto_del_mes_responde_404(cliente, make_token):
    h = _cabecera(make_token)
    r = cliente.post("/api/finanzas/presupuestos/2001/1/gastos", headers=h,
                     json={"descripcion": "X", "categoria": "Ocio", "monto": 10, "tipo": "fijo", "fecha": "2001-01-02"})
    assert r.status_code == 404


@pytest.mark.parametrize("cuerpo", [{"ingreso": -1}, {"ingreso": 100, "meta_ahorro": -5}, {"ingreso": "x"}, {}])
def test_presupuesto_con_importes_invalidos_responde_422(cliente, make_token, cuerpo):
    h = _cabecera(make_token)
    assert cliente.put("/api/finanzas/presupuestos/2026/3", headers=h, json=cuerpo).status_code == 422


def test_mes_fuera_de_rango_responde_422(cliente, make_token):
    h = _cabecera(make_token)
    assert cliente.put("/api/finanzas/presupuestos/2026/13", headers=h, json={"ingreso": 1}).status_code == 422


# ----------------------------------------------------------- tareas
def test_tareas_crud_orden_filtros_y_resumen(cliente, make_token):
    h = _cabecera(make_token)
    hoy = date.today()
    vencida = cliente.post("/api/tareas", headers=h, json={
        "titulo": "Entregar taller", "prioridad": "media", "fecha_limite": (hoy - timedelta(days=2)).isoformat()}).json()
    proxima = cliente.post("/api/tareas", headers=h, json={
        "titulo": "Preparar exposición", "prioridad": "alta", "fecha_limite": (hoy + timedelta(days=3)).isoformat()}).json()
    lejana = cliente.post("/api/tareas", headers=h, json={
        "titulo": "Leer artículo", "prioridad": "baja", "fecha_limite": (hoy + timedelta(days=40)).isoformat()}).json()
    hecha = cliente.post("/api/tareas", headers=h, json={"titulo": "Correo", "prioridad": "alta", "estado": "completada"}).json()

    assert vencida["vencida"] is True and vencida["dias_para_vencer"] == -2
    assert proxima["prioridad"] == "alta" and proxima["prioridad_valor"] == 1
    assert hecha["vencida"] is False and hecha["fecha_limite"] is None

    orden = [t["titulo"] for t in cliente.get("/api/tareas", headers=h).json()]
    assert orden == ["Preparar exposición", "Entregar taller", "Leer artículo", "Correo"]

    assert [t["titulo"] for t in cliente.get("/api/tareas", params={"estado": "completada"}, headers=h).json()] == ["Correo"]
    assert [t["titulo"] for t in cliente.get("/api/tareas", params={"prioridad": "baja"}, headers=h).json()] == ["Leer artículo"]

    resumen = cliente.get("/api/tareas/resumen", headers=h).json()
    assert resumen["total"] == 4 and resumen["completadas"] == 1 and resumen["porcentaje"] == "25.00"
    assert [t["titulo"] for t in resumen["vencidas"]] == ["Entregar taller"]
    assert [t["titulo"] for t in resumen["proximas"]] == ["Preparar exposición"]

    completada = cliente.patch(f"/api/tareas/{vencida['id']}", headers=h, json={"estado": "completada"}).json()
    assert completada["estado"] == "completada" and completada["vencida"] is False

    sin_fecha = cliente.patch(f"/api/tareas/{proxima['id']}", headers=h, json={"fecha_limite": None}).json()
    assert sin_fecha["fecha_limite"] is None and sin_fecha["dias_para_vencer"] is None

    assert cliente.delete(f"/api/tareas/{lejana['id']}", headers=h).status_code == 204
    assert len(cliente.get("/api/tareas", headers=h).json()) == 3


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"titulo": "", "prioridad": "alta"},
        {"titulo": "X", "prioridad": "urgente"},
        {"titulo": "X", "prioridad": 1},
        {"titulo": "X", "prioridad": "alta", "estado": "en curso"},
        {"titulo": "X", "prioridad": "alta", "fecha_limite": "10/05/2026"},
        {"titulo": "X"},
        {"prioridad": "alta"},
        {"titulo": "X", "prioridad": "alta", "user_id": "x"},
    ],
)
def test_tarea_invalida_responde_422(cliente, make_token, cuerpo):
    assert cliente.post("/api/tareas", headers=_cabecera(make_token), json=cuerpo).status_code == 422


def test_patch_de_tarea_sin_campos_responde_422(cliente, make_token):
    h = _cabecera(make_token)
    tid = cliente.post("/api/tareas", headers=h, json={"titulo": "A", "prioridad": "alta"}).json()["id"]
    assert cliente.patch(f"/api/tareas/{tid}", headers=h, json={}).status_code == 422
    assert cliente.patch(f"/api/tareas/{tid}", headers=h, json={"titulo": None}).status_code == 422


def test_filtro_de_prioridad_invalido_responde_422(cliente, make_token):
    assert cliente.get("/api/tareas", params={"prioridad": "x"}, headers=_cabecera(make_token)).status_code == 422


# ----------------------------------------------------------- persistencia tras reiniciar
def test_datos_persisten_tras_reiniciar_la_aplicacion(entorno_sqlite, verifier, make_token):
    h = _cabecera(make_token)
    hoy = date.today()

    app1 = create_app()
    app1.dependency_overrides[get_verifier] = lambda: verifier
    c1 = TestClient(app1)
    c1.post("/api/subjects", headers=h, json={"nombre": "Persistente"})
    sid = c1.get("/api/subjects", headers=h).json()[0]["id"]
    c1.post(f"/api/subjects/{sid}/grades", headers=h, json={"descripcion": "Parcial", "nota": 4.1})
    c1.put(f"/api/finanzas/presupuestos/{hoy.year}/{hoy.month}", headers=h, json={"ingreso": 700000})
    c1.post("/api/tareas", headers=h, json={"titulo": "Sigue ahí", "prioridad": "alta"})
    del c1, app1
    get_settings.cache_clear()

    app2 = create_app()  # nuevo proceso lógico: solo el archivo SQLite
    app2.dependency_overrides[get_verifier] = lambda: verifier
    c2 = TestClient(app2)
    asignaturas = c2.get("/api/subjects", headers=h).json()
    assert [a["nombre"] for a in asignaturas] == ["Persistente"]
    assert asignaturas[0]["promedio"] == "4.10"
    assert c2.get(f"/api/finanzas/presupuestos/{hoy.year}/{hoy.month}", headers=h).json()["ingreso"] == "700000.00"
    assert [t["titulo"] for t in c2.get("/api/tareas", headers=h).json()] == ["Sigue ahí"]


# ----------------------------------------------------------- demo: datos ficticios y origen
def test_datos_demo_se_distinguen_y_reset_no_toca_reales(entorno_sqlite, verifier, make_token):
    h = _cabecera(make_token)
    c = TestClient(_app_con(verifier))
    c.post("/api/subjects", headers=h, json={"nombre": "Mi asignatura real"})  # usuario real

    conn = connect(entorno_sqlite)  # ya migrada por create_app
    assert seed_demo(conn).startswith("Datos demo cargados")
    assert seed_demo(conn).startswith("Los datos demo ya existen")
    assert seed_demo(conn, reset=True).startswith("Datos demo regenerados")
    filas = conn.execute("SELECT origen, COUNT(*) n FROM academic_subjects GROUP BY origen").fetchall()
    assert {f["origen"]: f["n"] for f in filas} == {"demo": 3, "real": 1}
    assert conn.execute("SELECT COUNT(*) FROM academic_subjects WHERE user_id = ?", (DEMO_USER_ID,)).fetchone()[0] == 3
    conn.close()


def _app_con(verifier):
    app = create_app()
    app.dependency_overrides[get_verifier] = lambda: verifier
    return app


# ----------------------------------------------------------- sin SQLite: 501 y 503 honestos
def test_finanzas_y_tareas_con_supabase_sin_configurar_responden_503(monkeypatch, verifier, make_token):
    """Con PERSISTENCE_BACKEND=supabase y sin URL/clave, el adaptador PostgREST no existe: 503 claro."""
    from app.api import deps

    monkeypatch.setenv("PERSISTENCE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "")
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()
    deps.get_postgrest_client.cache_clear()
    app = create_app()
    app.dependency_overrides[get_verifier] = lambda: verifier
    c = TestClient(app)
    h = {"Authorization": f"Bearer {make_token()}"}
    assert c.get("/api/tareas", headers=h).status_code == 503
    assert c.get("/api/finanzas/presupuestos", headers=h).status_code == 503
    get_settings.cache_clear()
    deps.get_postgrest_client.cache_clear()


def test_conexion_sqlite_puede_usarse_desde_otro_hilo(entorno_sqlite):
    """Regresión: FastAPI crea la dependencia y ejecuta el endpoint en hilos distintos.

    Con check_same_thread=True esto lanza sqlite3.ProgrammingError en el servidor real
    (no lo detecta TestClient, que ejecuta todo en el mismo hilo).
    """
    import threading

    conexion = {}
    crear = threading.Thread(target=lambda: conexion.update(c=open_migrated(entorno_sqlite)))
    crear.start()
    crear.join()

    resultado = {}

    def usar():
        resultado["filas"] = conexion["c"].execute("SELECT COUNT(*) FROM academic_subjects").fetchone()[0]

    usar_hilo = threading.Thread(target=usar)
    usar_hilo.start()
    usar_hilo.join()
    assert resultado["filas"] == 0
    conexion["c"].close()
