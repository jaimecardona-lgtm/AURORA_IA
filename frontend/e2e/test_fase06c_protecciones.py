"""Protecciones de fase06c_supabase_real.py: solo lectura por defecto, confirmación SI, copiloto simulado.

Sin navegador, sin red y sin Supabase. Ejecutar a mano (no forma parte de la CI de backend):
  backend/.venv/Scripts/python.exe -m pytest frontend/e2e/test_fase06c_protecciones.py -q
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parent / "fase06c_supabase_real.py"
spec = importlib.util.spec_from_file_location("f06c", RUTA)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Resp:
    def __init__(self, status=404, data=None):
        self.status_code = status
        self._data = data if data is not None else []

    def json(self):
        return self._data


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    m.resultados.clear()
    m.ids.clear()
    m.ids.update({"asignatura_B": "x1", "nota_B": "x2", "gasto_B": "x3", "tarea_B": "x4"})
    m.ESCRIBIR = False
    yield


def test_solo_lectura_no_envia_escrituras(monkeypatch):
    llamadas = []

    def api_falsa(metodo, ruta, token, cuerpo=None, base=None):
        llamadas.append(metodo)
        return Resp(404, [])

    monkeypatch.setattr(m, "api", api_falsa)
    m.pruebas_cruzadas("A", "tok-A", "B", "tok-B")
    assert set(llamadas) == {"GET"}, f"métodos enviados: {llamadas}"
    omitidas = [r for r in m.resultados if r["resultado"] == "OMITIDA"]
    assert len(omitidas) >= 8  # PATCH y DELETE por recurso (4) + POST de notas


def test_escritura_autorizada_si_envia_patch_y_delete(monkeypatch):
    llamadas = []

    def api_falsa(metodo, ruta, token, cuerpo=None, base=None):
        llamadas.append(metodo)
        return Resp(404, [])

    monkeypatch.setattr(m, "api", api_falsa)
    m.ESCRIBIR = True
    m.pruebas_cruzadas("A", "tok-A", "B", "tok-B")
    assert "PATCH" in llamadas and "DELETE" in llamadas and "POST" in llamadas


def test_copiloto_no_simulado_no_recibe_chat(monkeypatch):
    posts = []
    monkeypatch.setattr(m.httpx, "get", lambda url, **kw: Resp(200, {"proveedor": "openrouter", "simulado": False}))
    monkeypatch.setattr(m.httpx, "post", lambda url, **kw: posts.append(url) or Resp(200, {}))
    panel = {"academico": {"por_asignatura": [{"nombre": "06C-Cálculo A"}]},
             "finanzas": {"tiene_presupuesto": True}, "tareas": {"pendientes": 1}}
    monkeypatch.setattr(m, "api", lambda metodo, ruta, token, cuerpo=None, base=None: Resp(200, panel))
    m.dashboard_y_copiloto("tok", "A", "A")
    assert posts == [], "se envió una pregunta a un copiloto no simulado"
    assert any(r["resultado"] == "OMITIDA" and "OpenRouter" in r["detalle"] for r in m.resultados)


def test_verificacion_aborta_si_no_es_produccion(monkeypatch):
    monkeypatch.setattr(m.httpx, "get", lambda url, **kw: Resp(200, {"modo": "demo", "persistencia": "sqlite"}))
    with pytest.raises(SystemExit) as info:
        m.verificar_entorno_seguro()
    assert "ABORTADO" in str(info.value)


def test_confirmacion_distinta_de_SI_cancela_sin_escribir(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["x", "carpeta", m.FLAG_ESCRITURA])
    monkeypatch.setattr("builtins.input", lambda _: "si")  # minúscula: no es SI
    assert m.main() == 3
    assert m.ESCRIBIR is False


def test_sin_flag_no_crea_datos(monkeypatch):
    creados = []
    monkeypatch.setattr(sys, "argv", ["x", "carpeta"])
    monkeypatch.setattr(m, "verificar_entorno_seguro", lambda: None)
    monkeypatch.setattr(m, "crear_datos_ui", lambda *a, **k: creados.append(a))

    class Pw:
        def __enter__(self):
            raise RuntimeError("corte antes del navegador (prueba)")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(m, "sync_playwright", lambda: Pw())
    with pytest.raises(RuntimeError):
        m.main()
    assert creados == []
    assert m.ESCRIBIR is False
