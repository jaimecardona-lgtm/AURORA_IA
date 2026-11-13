# Fase 05 — AURORA Copilot: copiloto contextual de solo lectura

Resultados verificados: [PRUEBAS_FASE_05.md](PRUEBAS_FASE_05.md).
Arquitectura: [ARQUITECTURA_COPILOTO.md](ARQUITECTURA_COPILOTO.md). Prompts: [PROMPTS_COPILOTO.md](PROMPTS_COPILOTO.md).

## Estado en una frase

El copiloto está **implementado y probado** con un proveedor de prueba y con el proveedor simulado de
desarrollo. **La llamada real a OpenRouter no se ha ejecutado**: `backend/.env` (local, ignorado por Git) ya contiene
`OPENROUTER_API_KEY` y `OPENROUTER_MODEL` (`google/gemma-4-26b-a4b-it:free`, sin verificar en el catálogo), pero no hay autorización
explícita de consumo. Hasta que se
configure, el copiloto muestra «pendiente de configuración» y no inventa respuestas.

## 1. Auditoría previa

- Git: el repositorio sigue sin commits nuevos; las carpetas de fases anteriores siguen sin seguir.
- Línea base: 178 pruebas pytest en verde y build correcto.
- Servicios reutilizables: `AcademicService`, `BudgetService`, `TaskService` y `DashboardService`
  ya devolvían cifras de los motores. No fue necesario reconstruir nada.
- Dependencias de identidad: `get_principal` ya exige token fuera del modo demo.

## 2. Lo que se construyó

**Backend (`backend/app/ai/`)**

- `provider.py`: interfaz `AIProvider` y jerarquía de errores con código HTTP y código estable.
- `openrouter_client.py`: cliente HTTP de la API oficial (`https://openrouter.ai/api/v1/chat/completions`,
  cabecera `Authorization: Bearer`). Sin streaming. Traduce 401, 402, 429, 5xx, timeouts y respuestas
  malformadas. Registra solo estado, latencia y tokens.
- `simulated_provider.py`: resumen determinista **etiquetado como SIMULADO**. Prohibido fuera de desarrollo.
- `prompts.py`: `SYSTEM_PROMPT` versionado (`copiloto-v1.0`) y envoltorio delimitado de los datos.
- `context_builder.py`: construye el contexto solo desde los servicios, sin identificadores ni marcas de tiempo.
- `copilot_service.py`: orquestación, límites (por minuto, por día en tokens, concurrencia) y métricas técnicas.
- `schemas/copilot.py`: contratos con `extra="forbid"` y límites de tamaño.
- `api/routes_copilot.py`: `POST /api/copilot/chat` y `GET /api/copilot/estado`.

**Configuración**: `OPENROUTER_API_KEY` (tipo `SecretStr`, nunca se imprime), `OPENROUTER_MODEL`,
`OPENROUTER_TIMEOUT_SECONDS`, `COPILOT_PROVIDER`, `COPILOT_MAX_TOKENS`, `COPILOT_REQUESTS_PER_MINUTE`,
`COPILOT_DAILY_TOKENS` y `COPILOT_CONCURRENCY`. Todas están en `backend/.env.example` con valores vacíos o
no secretos. Los errores de proveedor se traducen en `main.py` sin exponer el cuerpo de la respuesta.

**Frontend**: `pages/CopilotPage.tsx` con chat, sugerencias por área, selector de áreas incluidas,
indicador de generación, error con reintento explícito, limpiar conversación, contador de caracteres
y render seguro del texto (sin HTML). Se muestra la procedencia de cada respuesta: «Generado por
OpenRouter · modelo» o «Simulado · no es IA». El Copiloto deja de estar «Próximamente» y pasa a ser
un módulo de la navegación.

## 3. Decisiones

| # | Decisión | Motivo |
|---|---|---|
| D1 | Sin streaming en esta fase | El prompt lo pide: primero la ruta convencional verificada. |
| D2 | El copiloto es de solo lectura | No hay herramientas de escritura para el modelo; el proveedor solo devuelve texto. |
| D3 | El contexto lo construye el servidor | El navegador no es fuente de datos. `include_context` solo decide qué áreas se incluyen. |
| D4 | Modelo sin valor por defecto | Los identificadores de modelo de las fuentes consultadas eran ejemplos; no se fija uno sin verificarlo. |
| D5 | Límites en memoria | Suficiente para desarrollo local; se documenta que no se comparten entre procesos. |
| D6 | `SimulatedProvider` marcado y prohibido en producción | Permite probar la interfaz sin fingir IA. |
| D7 | Sin clave, estado pendiente y ninguna respuesta | El prompt prohíbe fingir respuestas reales. |

## 4. Precisión monetaria (auditoría de SQLite)

La auditoría de la Fase 04 ya midió el riesgo: el tipo `REAL` no conserva el máximo de
`NUMERIC(14,2)` (`99999999999999.99` se guarda como `…98`). El copiloto no lo empeora:

- Los importes llegan al contexto como texto decimal producido por el motor (`Decimal`), nunca como `float`.
- Ningún cálculo monetario se delega al modelo; el prompt lo prohíbe y el contexto ya trae los totales.
- **Estrategia propuesta** (sin aplicar, sin migraciones destructivas): migración aditiva `0003` con
  columnas en centavos `INTEGER`, relleno verificado fila a fila con un informe de diferencias, lectura
  dual en la aplicación y retirada de las columnas `REAL` solo con copia de seguridad y autorización.
  Se detalla en `FASE_04_IMPLEMENTACION.md` §5.1.
- En PostgreSQL (Supabase) el tipo ya es `NUMERIC(14,2)`, exacto.

No se ha modificado ningún registro de la base local del usuario.

## 5. Defectos encontrados y corregidos durante la fase

| # | Defecto | Cómo se detectó | Corrección |
|---|---|---|---|
| 1 | El proveedor inyectado en las pruebas no tenía efecto: el servicio llamaba a `get_ai_provider()` directamente, en lugar de recibirlo como dependencia | Varias pruebas de copiloto fallaban con 503 | Dependencias inyectadas (`Depends`) para proveedor y limitador |
| 2 | El historial enviado al modelo incluía la pregunta actual, que además viajaba aparte | Revisión del flujo de `CopilotPage` | El historial excluye el último mensaje (la pregunta actual) |
| 3 | `React.KeyboardEvent` sin importar el espacio de nombres | TypeScript estricto | Importación explícita de tipos |
| 4 | La prueba de concurrencia dependía de estado implícito del semáforo | Revisión del código de la prueba | Se sustituye por un semáforo de capacidad 1 ocupado explícitamente |

Errores de fases anteriores que siguen corregidos: ver `FASE_04_IMPLEMENTACION.md` §7.

## 6. Qué falta para la llamada real a OpenRouter

1. Crear la clave en el panel de OpenRouter y definirla **solo** en el entorno del servidor o en
   `backend/.env` local (nunca en el repositorio ni en el frontend).
2. Elegir un modelo de texto disponible en <https://openrouter.ai/models> y definir `OPENROUTER_MODEL`
   con ese identificador exacto.
3. Autorizar un presupuesto de prueba y ejecutar una consulta mínima. La prueba real queda registrada
   en `PRUEBAS_FASE_05.md` como **pendiente**, no como realizada.

## 7. Riesgos abiertos

Ver `ARQUITECTURA_COPILOTO.md` §8. Los más relevantes: inyección indirecta no verificada con el modelo
real; límites en memoria; sin streaming; precisión monetaria pendiente de la migración propuesta.

## 8. Lo que no se ha hecho (por instrucción)

- Conexión a Supabase, despliegue en Render, commits y push.
- Informe AA2-EV01 y video AA2-EV02.
- Modificación de bases de datos ajenas o de registros de la base local del usuario.
