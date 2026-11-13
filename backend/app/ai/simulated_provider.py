"""Proveedor SIMULADO: solo desarrollo y pruebas. NO es inteligencia artificial.

Devuelve un resumen determinista de los datos recibidos, marcado como SIMULADO en la respuesta
(`provider="simulado"`, `simulado=true`). Está prohibido en producción (ver Settings.validate_runtime).
"""

from __future__ import annotations

import json

from app.ai.prompts import DELIMITADOR_DATOS_FIN, DELIMITADOR_DATOS_INICIO
from app.ai.provider import ProviderResponse, Usage


class SimulatedProvider:
    name = "simulado"
    model = "simulado-determinista"

    def complete(self, messages: list[dict[str, str]], max_tokens: int) -> ProviderResponse:
        contexto = _extraer_contexto(messages)
        lineas = ["[SIMULADO · no es una respuesta de IA] Resumen de los datos disponibles:"]
        if contexto is None:
            lineas.append("No se incluyó contexto en esta consulta.")
        else:
            acad = contexto.get("academico")
            if acad is not None:
                lineas.append(
                    f"- Académico: {acad.get('total_asignaturas', 0)} asignaturas; "
                    f"promedio general {acad.get('promedio_general') or 'sin notas'}."
                )
            fin = contexto.get("finanzas")
            if fin is not None:
                lineas.append(f"- Finanzas: saldo {_cop(fin['saldo']) if fin.get('saldo') is not None else 'sin presupuesto'}.")
            tar = contexto.get("tareas")
            if tar is not None:
                lineas.append(f"- Tareas: {tar.get('pendientes', 0)} pendientes; {tar.get('vencidas_total', 0)} vencidas.")
        texto = "\n".join(lineas)
        palabras = len(texto.split())
        return ProviderResponse(
            text=texto,
            model=self.model,
            usage=Usage(prompt_tokens=None, completion_tokens=palabras, total_tokens=palabras),
            latency_ms=0,
            incomplete=False,
        )


def _cop(valor) -> str:
    """Formato COP para mostrar: $ 870.000 (sin decimales)."""
    try:
        numero = round(float(valor))
    except (TypeError, ValueError):
        return str(valor)
    return "$ " + f"{numero:,}".replace(",", ".")


def _extraer_contexto(messages: list[dict[str, str]]) -> dict | None:
    for mensaje in messages:
        contenido = mensaje.get("content", "")
        if DELIMITADOR_DATOS_INICIO in contenido:
            bloque = contenido.split(DELIMITADOR_DATOS_INICIO, 1)[1].split(DELIMITADOR_DATOS_FIN, 1)[0]
            return json.loads(bloque)
    return None
