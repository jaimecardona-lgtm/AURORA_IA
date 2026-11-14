#!/usr/bin/env python3
"""Smoke HTTP sin autenticación ni secretos para una URL pública de AURORA AI.

No realiza escrituras, no entra a cuentas, no llama al copiloto.
Ejemplo: python backend/tools/smoke_public_release.py https://aurora-ai.onrender.com
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def consultar(base: str, ruta: str):
    url = base.rstrip("/") + ruta
    request = urllib.request.Request(url, headers={"Accept": "application/json, text/html"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read(512_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read(2048).decode("utf-8", errors="replace")


def verificar(base: str) -> list[tuple[str, bool, str]]:
    registros = []
    try:
        status, body = consultar(base, "/api/health")
        data = json.loads(body) if status == 200 else {}
        ok = status == 200 and data.get("status") == "ok" and data.get("supabase_configurado") is True
        registros.append(("salud (NO verifica conexión real a Supabase)", ok, f"HTTP {status}"))
    except (ValueError, urllib.error.URLError, OSError) as error:
        registros.append(("salud", False, type(error).__name__))

    try:
        status, body = consultar(base, "/api/modo")
        data = json.loads(body) if status == 200 else {}
        ok = status == 200 and data.get("modo") == "produccion" and data.get("persistencia") == "supabase"
        registros.append(("configuración segura", ok, f"HTTP {status}"))
    except (ValueError, urllib.error.URLError, OSError) as error:
        registros.append(("configuración segura", False, type(error).__name__))

    try:
        status, body = consultar(base, "/")
        registros.append(("SPA compilada", status == 200 and "<html" in body.lower() and "assets/" in body, f"HTTP {status}"))
    except (urllib.error.URLError, OSError) as error:
        registros.append(("SPA compilada", False, type(error).__name__))

    try:
        status, _ = consultar(base, "/api/subjects")
        registros.append(("rutas privadas protegidas (sin JWT)", status == 401, f"HTTP {status}"))
    except (urllib.error.URLError, OSError) as error:
        registros.append(("rutas privadas protegidas", False, type(error).__name__))
    return registros


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL HTTPS pública del Web Service Render")
    args = parser.parse_args()
    parts = urllib.parse.urlsplit(args.url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("", "/"):
        parser.error("Solo se admite URL base HTTPS sin credenciales, rutas, parámetros ni fragmento")
    if parts.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
        parser.error("Usa la URL pública HTTPS, no localhost")
    resultados = verificar(args.url.rstrip("/"))
    for etiqueta, ok, detalle in resultados:
        print(f"{'PASS' if ok else 'FAIL'} | {etiqueta} | {detalle}")
    print("NOTA: estas pruebas no certifican login, RLS, datos, historial ni IA real.")
    return 0 if all(ok for _, ok, _ in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
