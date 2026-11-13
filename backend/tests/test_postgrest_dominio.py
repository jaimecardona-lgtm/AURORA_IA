"""Adaptadores PostgREST de Finanzas y Tareas + servicios reales.

IMPORTANTE: el servidor PostgREST de estas pruebas es una SIMULACIÓN en memoria (httpx.MockTransport).
Imita PostgREST en lo que usan los adaptadores (filtros eq., order, return=representation) y el
DEFAULT auth.uid() de la base. NO prueba la política RLS real de Supabase: eso exige la integración
remota, documentada como pendiente en docs/PRUEBAS_FASE_06B.md.
"""

import json
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest

from app.errors import SupabasePermissionError, SupabaseRejectedTokenError
from app.repositories.postgrest_client import PostgrestClient
from app.repositories.postgrest_dominio import PostgrestBudgetRepository, PostgrestTaskRepository
from app.security.principal import Principal
from app.services.budget_service import BudgetService
from app.services.task_service import TaskService
from app.schemas.finance import BudgetIn, ExpenseIn
from app.schemas.tasks import TaskIn

ANON = "clave-publica-de-prueba"
USUARIO_A = str(uuid.uuid4())
USUARIO_B = str(uuid.uuid4())
TOKEN = {"tok-A": USUARIO_A, "tok-B": USUARIO_B}


NUMERIC_COLS = {"ingreso", "meta_ahorro", "monto"}


def _json_postgrest(filas):
    """Serializa como PostgREST: las columnas numeric salen como número JSON (sin comillas)."""
    def valor(k, v):
        if k in NUMERIC_COLS and isinstance(v, str):
            return v  # número JSON textual exacto
        return json.dumps(v, default=str)
    partes = []
    for fila in filas:
        campos = ",".join(f'"{k}":{valor(k, v)}' for k, v in fila.items())
        partes.append("{" + campos + "}")
    return "[" + ",".join(partes) + "]"


class PostgrestSimulado:
    """Tablas en memoria con aislamiento por token, como lo haría RLS con auth.uid()."""

    def __init__(self):
        self.tablas = {"monthly_budgets": [], "budget_expenses": [], "tasks": []}
        self.peticiones = []

    def _usuario(self, request):
        auth = request.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        return TOKEN.get(token)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.peticiones.append(request)
        tabla = request.url.path.rsplit("/", 1)[-1]
        usuario = self._usuario(request)
        if request.headers.get("apikey") != ANON:
            return httpx.Response(401, json={"message": "apikey"})
        if usuario is None or tabla not in self.tablas:
            return httpx.Response(403, json={"code": "42501", "message": "permission denied"})

        filas = self.tablas[tabla]
        filtros = {k: v for k, v in request.url.params.items() if k not in ("select", "order", "limit")}
        visibles = [f for f in filas if f["user_id"] == usuario]
        for columna, valor in filtros.items():
            op, _, dato = valor.partition(".")
            if op == "eq":
                visibles = [f for f in visibles if str(f.get(columna)) == dato]

        metodo = request.method
        if metodo == "GET":
            return httpx.Response(200, content=_json_postgrest([dict(f) for f in visibles]).encode(), headers={"content-type": "application/json"})

        if metodo == "POST":
            cuerpo = json.loads(request.content)
            fila = {"id": str(uuid.uuid4()), "user_id": usuario,  # DEFAULT auth.uid()
                    "created_at": "2026-11-12T10:00:00+00:00", "updated_at": "2026-11-12T10:00:00+00:00", **cuerpo}
            filas.append(fila)
            return httpx.Response(201, content=_json_postgrest([fila]).encode(), headers={"content-type": "application/json"})

        if metodo == "PATCH":
            cambios = json.loads(request.content)
            tocadas = []
            for f in visibles:
                f.update(cambios)
                tocadas.append(dict(f))
            return httpx.Response(200, content=_json_postgrest(tocadas).encode(), headers={"content-type": "application/json"})

        if metodo == "DELETE":
            borradas = [dict(f) for f in visibles]
            ids = {f["id"] for f in borradas}
            self.tablas[tabla] = [f for f in filas if f["id"] not in ids]
            return httpx.Response(200, content=_json_postgrest(borradas).encode(), headers={"content-type": "application/json"})

        return httpx.Response(405, json={})


@pytest.fixture
def sim():
    return PostgrestSimulado()


@pytest.fixture
def cliente(sim):
    return PostgrestClient("https://proyecto.example", ANON, transport=httpx.MockTransport(sim.handler))


def _p(usuario="A"):
    token = "tok-A" if usuario == "A" else "tok-B"
    return Principal(user_id=USUARIO_A if usuario == "A" else USUARIO_B, access_token=token)


# ----------------------------------------------------------- contrato de red
def test_cabeceras_usan_clave_publica_y_jwt_del_usuario(cliente, sim):
    PostgrestBudgetRepository(cliente).list_budgets(_p("A"))
    peticion = sim.peticiones[-1]
    assert peticion.headers["apikey"] == ANON
    assert peticion.headers["authorization"] == "Bearer tok-A"
    assert "service_role" not in str(peticion.headers).lower()


def test_sin_jwt_no_se_consulta_la_base(cliente, sim):
    with pytest.raises(SupabaseRejectedTokenError):
        PostgrestBudgetRepository(cliente).list_budgets(Principal(user_id=USUARIO_A, access_token=None))
    assert sim.peticiones == []


def test_inserciones_no_envian_user_id(cliente, sim):
    repo = PostgrestTaskRepository(cliente)
    repo.create_task(_p("A"), {"titulo": "x", "prioridad": 1, "estado": "pendiente", "fecha_limite": None})
    assert "user_id" not in json.loads(sim.peticiones[-1].content)


def test_importes_se_envian_como_cadena_decimal_exacta(cliente, sim):
    repo = PostgrestBudgetRepository(cliente)
    repo.upsert_budget(_p("A"), 2026, 11, "2000000.10", "300000.00")
    cuerpo = json.loads(sim.peticiones[-1].content)
    assert cuerpo["ingreso"] == "2000000.10" and isinstance(cuerpo["ingreso"], str)


def test_numeric_llega_como_decimal_exacto(cliente, sim):
    repo = PostgrestBudgetRepository(cliente)
    repo.upsert_budget(_p("A"), 2026, 11, "12345678901234.56", "0.00")
    fila = repo.get_budget(_p("A"), 2026, 11)
    assert isinstance(fila["ingreso"], Decimal)
    assert fila["ingreso"] == Decimal("12345678901234.56")


# ----------------------------------------------------------- servicios de finanzas
def test_presupuesto_gastos_y_resumen_con_el_motor(cliente):
    hoy = date.today()
    servicio = BudgetService(PostgrestBudgetRepository(cliente))
    p = _p("A")
    servicio.define_budget(p, hoy.year, hoy.month, BudgetIn(ingreso=Decimal("2000000"), meta_ahorro=Decimal("300000")))
    servicio.add_expense(p, hoy.year, hoy.month, ExpenseIn(
        descripcion="Arriendo", categoria="Vivienda", monto=Decimal("600000.50"), tipo="fijo", fecha=date(hoy.year, hoy.month, 1)))
    detalle = servicio.get_budget(p, hoy.year, hoy.month)
    assert detalle.gastos_total == Decimal("600000.50")
    assert detalle.saldo == Decimal("1399999.50")
    assert detalle.categorias[0].categoria == "Vivienda"


def test_editar_y_eliminar_gasto_via_postgrest(cliente):
    hoy = date.today()
    servicio = BudgetService(PostgrestBudgetRepository(cliente))
    p = _p("A")
    servicio.define_budget(p, hoy.year, hoy.month, BudgetIn(ingreso=Decimal("100000")))
    creado = servicio.add_expense(p, hoy.year, hoy.month, ExpenseIn(
        descripcion="Taxi", categoria="Transporte", monto=Decimal("20000"), tipo="variable", fecha=date(hoy.year, hoy.month, 2)))
    from app.schemas.finance import ExpenseUpdate
    editado = servicio.update_expense(p, creado.id, ExpenseUpdate(monto=Decimal("35000.25")))
    assert editado.monto == Decimal("35000.25")
    servicio.delete_expense(p, creado.id)
    assert servicio.get_budget(p, hoy.year, hoy.month).gastos == []


# ----------------------------------------------------------- servicios de tareas
def test_tareas_crud_y_orden_con_el_motor(cliente):
    servicio = TaskService(PostgrestTaskRepository(cliente))
    p = _p("A")
    hoy = date.today()
    servicio.create_task(p, TaskIn(titulo="Baja", prioridad="baja"))
    servicio.create_task(p, TaskIn(titulo="Alta vencida", prioridad="alta", fecha_limite=hoy - timedelta(days=1)))
    orden = [t.titulo for t in servicio.list_tasks(p, hoy)]
    assert orden == ["Alta vencida", "Baja"]
    resumen = servicio.summary(p, hoy)
    assert [t.titulo for t in resumen.vencidas] == ["Alta vencida"]


# ----------------------------------------------------------- aislamiento entre usuarios (simulado)
def test_usuario_b_no_ve_ni_modifica_datos_de_a(cliente):
    hoy = date.today()
    budget = BudgetService(PostgrestBudgetRepository(cliente))
    tasks = TaskService(PostgrestTaskRepository(cliente))
    a, b = _p("A"), _p("B")
    budget.define_budget(a, hoy.year, hoy.month, BudgetIn(ingreso=Decimal("1000")))
    tarea = tasks.create_task(a, TaskIn(titulo="Privada de A", prioridad="alta"))

    assert budget.list_budgets(b) == []
    assert tasks.list_tasks(b, hoy) == []
    from app.errors import NotFoundError
    with pytest.raises(NotFoundError):
        tasks.update_task(b, tarea.id, __import__("app.schemas.tasks", fromlist=["TaskUpdate"]).TaskUpdate(estado="completada"))
    with pytest.raises(NotFoundError):
        tasks.delete_task(b, tarea.id)
    assert [t.titulo for t in tasks.list_tasks(a, hoy)] == ["Privada de A"]


def test_error_de_permiso_de_la_base_se_traduce_a_403(sim):
    cliente = PostgrestClient("https://proyecto.example", ANON, transport=httpx.MockTransport(sim.handler))
    with pytest.raises(SupabasePermissionError):
        PostgrestBudgetRepository(cliente).list_budgets(Principal(user_id=USUARIO_A, access_token="token-desconocido"))
