# Pruebas — Fase 05 (cierre 05B)

Fecha: 2026-11-12 · Windows 11 · Python 3.12.10 (`backend/.venv`) · Node v22.22.0 · Chrome instalado
(Playwright 1.65.1, fuera del proyecto).

Estado general: **copiloto verificado con proveedor de prueba y con el proveedor SIMULADO. La
llamada real a OpenRouter está BLOQUEADA POR CONFIGURACIÓN** (sin `OPENROUTER_API_KEY` ni
`OPENROUTER_MODEL`). No se ha realizado ninguna llamada a OpenRouter ni se ha generado coste.

Sin commits, sin Supabase, sin despliegue en Render.

## 1. Resumen

| Ámbito | Resultado |
|---|---|
| Pytest completo | ✅ **218 aprobadas** (178 previas + 40 del copiloto) |
| Compilación TypeScript estricta | ✅ sin errores |
| Build de Vite | ✅ compila |
| Navegador Chrome (copiloto) | ✅ **33 / 33 aprobadas**, 0 fallidas |
| Evidencia JSON | ✅ `visual-evidence/fase-05/resultados_fase05.json` (válido, 33 entradas) |
| Llamada real a OpenRouter | ⛔ **BLOQUEADA POR CONFIGURACIÓN** |
| CLI del SENA | ✅ ver §7 |

## 2. Pruebas de navegador (33/33)

Ejecución: `python -u e2e/fase05_copiloto.py <simulado> <pendiente> <capturas> <json>` con dos servidores
temporales sobre base SQLite aislada (`scratchpad/e2e_fase05.sqlite3`): uno con `COPILOT_PROVIDER=simulado`
y otro con `COPILOT_PROVIDER=openrouter` **sin clave**. La base de desarrollo del puerto 8765 no se usó ni se modificó.

| Escenario | Comprobaciones | Resultado |
|---|---|---|
| Acceso y etiquetado | Copiloto en la navegación; etiqueta «SIMULADO · no es IA»; solo lectura (sin botones de borrar o modificar) | ✅ 3/3 |
| Sugerencias | Rellenan la pregunta sin enviarla | ✅ |
| Envío y respuesta | Burbuja del usuario; respuesta con procedencia; «Datos usados»; promedio del motor (3.64) | ✅ 4/4 |
| Enter | Enter envía la pregunta | ✅ |
| Selección de contexto | Desmarcar Finanzas y Tareas reduce los datos usados | ✅ |
| Renderizado seguro | HTML inyectado en la respuesta se muestra como texto; sin imagen ni ejecución de script | ✅ 3/3 |
| **HTTP 429** | Mensaje claro en alerta | ✅ |
| **Reintento** | «Reintentar» reenvía la misma pregunta; al terminar no queda error ni pregunta duplicada | ✅ 3/3 |
| **HTTP 503** | Motivo en español desde el código del servidor | ✅ |
| **Historial** | La consulta envía turnos previos completos, no repite la pregunta actual, máximo 6 turnos | ✅ 2/2 |
| Indicador | Estado de espera visible mientras se genera | ✅ |
| Límite de entrada | `maxlength` = 1000 | ✅ |
| Limpiar | Vacía la conversación | ✅ |
| Estado pendiente (sin clave) | Aviso de configuración; campo y botón deshabilitados; sin respuestas; sin valores de clave en la página; áreas accesibles | ✅ 6/6 |
| Responsive | 390, 820 y 1366 px: desborde horizontal 0 px en los tres | ✅ 3/3 |
| Consola | Sin errores de JavaScript | ✅ |

### Defectos encontrados en esta fase y corregidos

| # | Defecto | Cómo se detectó | Corrección |
|---|---|---|---|
| 1 | La prueba se quedaba bloqueada: los manejadores de ruta eran `async` dentro de la API síncrona de Playwright, que nunca los ejecuta | 7 minutos sin avance en el registro | Manejadores convertidos a síncronos |
| 2 | Selectores ambiguos: el texto de la pregunta coincidía con la burbuja y con la sugerencia del panel | `strict mode violation` en la primera ejecución | Búsqueda limitada al registro de la conversación (`role=log`) |
| 3 | **El historial enviado incluía una pregunta sin respuesta** (la que falló con 503), creando un turno de usuario huérfano | Comprobación de historial: `history[-1]` era `user` | `CopilotPage` envía solo intercambios completos (pregunta seguida de respuesta) |
| 4 | Dos ejecuciones de prueba escribían en el mismo registro al mismo tiempo | Procesos duplicados en la auditoría | Procesos detenidos; una sola ejecución por registro |
| 5 | Servidores de pruebas de fases anteriores seguían activos | Auditoría de procesos | Detenidos; el servidor de desarrollo 8765 se dejó intacto |

### Pendientes de precisión visual

- El texto de las respuestas del asistente tiene contraste bajo en la captura de escritorio. Pendiente de ajuste.
- El proveedor simulado escribe el saldo sin formato (`870000.00`). Es texto del proveedor simulado, no de la interfaz.

## 3. Pruebas automatizadas (Pytest)

| Archivo | Cobertura | Resultado |
|---|---|---|
| `tests/test_copilot.py` (40) | Contexto académico, financiero y de tareas; sin identificadores; sin registros; aislamiento; validación de solicitudes; inyección de instrucciones; configuración; simulado prohibido en producción; límites (minuto, día, concurrencia); errores del proveedor (401, 402, 429, 5xx, timeout, red, respuesta malformada, respuesta cortada); clave ausente de logs y de errores | ✅ 40/40 |
| Resto de la suite | Motores, API, SQLite, dashboard, JWT | ✅ 178/178 |

**Importante — naturaleza de estas pruebas**: todas usan un **proveedor de prueba** o un **transporte
HTTP simulado** (`httpx.MockTransport`). Verifican la estructura y el manejo de errores, no el
comportamiento real del modelo ni la respuesta de OpenRouter.

Ejecución final: `env -u DEMO_MODE -u PERSISTENCE_BACKEND -u SQLITE_PATH -u APP_ENV -u OPENROUTER_API_KEY pytest -q` → **218 passed, 1 warning**.

## 4. Build y TypeScript

- `npx tsc --noEmit` → sin errores.
- `npm run build` → compila (aviso de tamaño de fragmento de Vite, no es error).

## 5. Seguridad y calidad (verificación)

| Requisito | Evidencia | Estado |
|---|---|---|
| Simulado prohibido en producción | `test_simulado_queda_prohibido_en_produccion` | ✅ (verificado por prueba) |
| Modo demo sin acceso anónimo en producción | Validación de arranque ya probada en fase 03; `/api/copilot/*` exige token fuera de demo | ✅ (por código y pruebas previas) |
| OpenRouter no modifica registros | El proveedor solo recibe texto y devuelve texto; ninguna herramienta de escritura | ✅ (por diseño y revisión) |
| Cliente sin `user_id` arbitrario | `test_el_navegador_no_puede_imponer_identidad_ni_datos` (422) | ✅ |
| Límites funcionan | Pruebas de minuto, día y concurrencia | ✅ |
| Sin claves en archivos versionados | `backend/.env.example` con valores vacíos; búsqueda de la clave en el repositorio sin resultados | ✅ |
| Errores sin credenciales | `test_la_clave_no_aparece_en_los_logs` y comprobación de errores HTTP | ✅ |
| Recomendaciones orientativas | Prompt `copiloto-v1.0` (texto en `docs/PROMPTS_COPILOTO.md`) | ✅ (revisión del texto) |
| Datos de usuario no sobrescriben el sistema | Pruebas de inyección (estructura); comportamiento del modelo **no verificado** | ⚠️ parcial |

**Limitación del rate limiting**: los contadores viven en memoria de cada proceso. Con varias
instancias o reinicios, los límites no se comparten. Hace falta un almacén común antes de desplegar con
más de un proceso.

## 6. Validación de OpenRouter

- Endpoint documentado: `https://openrouter.ai/api/v1/chat/completions`, cabecera `Authorization: Bearer`.
  Confirmado en la documentación de OpenRouter consultada.
- Configuración local: existe `backend/.env` (ignorado por Git, no rastreado). Contiene `OPENROUTER_API_KEY` y `OPENROUTER_MODEL`. **Los valores no se reproducen aquí.** El modelo configurado es `google/gemma-4-26b-a4b-it:free` (variante gratuita).
- Nota de seguridad: un comando de búsqueda de esta sesión imprimió por error el valor de la clave en la salida. Se recomienda **rotar la clave** en el panel de OpenRouter.
- Catálogo de modelos (`https://openrouter.ai/api/v1/models`, sin clave): la respuesta **no coincide con el
  esquema documentado** (no incluye precios, modalidades ni longitud de contexto, y todos los identificadores
  llevan el prefijo `anthropic/`). Por tanto **no se puede validar que ningún modelo exista, sea de texto ni esté
  disponible**. No se ha seleccionado modelo alguno.

## 7. CLI del SENA

| Programa | Resultado |
|---|---|
| `sena_cli/calificaciones.py 4.5 3.0 2.9` | exit 0 |
| `sena_cli/presupuesto.py --ingreso 2000000 --ahorro 300000 …` | exit 0 |
| `sena_cli/tareas.py "Entregar:1" "Leer:3:completada"` | exit 0 |

## 8. Capturas (`visual-evidence/fase-05/`)

- `01_copiloto_simulado_escritorio.png`, `02_copiloto_respuesta_escritorio.png`, `03_copiloto_pendiente_escritorio.png`.
- `resp_copiloto_movil.png`, `resp_copiloto_tableta.png`, `resp_copiloto_escritorio.png`.
- `c4_actual_contenedores.png`, `c4_actual_componentes.png`, `c4_objetivo_contenedores.png`.
- `resultados_fase05.json` (evidencia de la ejecución de navegador).

Inspeccionada visualmente: `02_copiloto_respuesta_escritorio.png` (interfaz y etiqueta SIMULADO correctas).
El resto se generó con la versión final y no se ha revisado una a una.

## 9. Bloqueado: llamada real a OpenRouter

| Prueba | Estado | Motivo |
|---|---|---|
| Solicitud mínima a OpenRouter | ⏸ PENDIENTE DE AUTORIZACIÓN | Credenciales presentes en `backend/.env`; modelo `:free` no verificado contra el catálogo; falta autorización explícita de consumo |
| Consulta contextual real con datos de demo | ⛔ BLOQUEADA | Depende de lo anterior |
| Verificación de que el modelo no obedece instrucciones maliciosas | ⛔ BLOQUEADA | Depende de lo anterior |
| Latencia y consumo reales | ⛔ BLOQUEADA | Depende de lo anterior |

No se ha simulado esta conexión ni se han hecho solicitudes que generen cargos.

## 10. Único paso pendiente para activar OpenRouter real

1. Confirmar que `google/gemma-4-26b-a4b-it:free` existe y está disponible en <https://openrouter.ai/models> (o indicar otro identificador de texto).
2. Autorizar explícitamente una prueba mínima de consumo (máximo 20 tokens de respuesta).
3. Rotar la clave expuesta por el comando de búsqueda.

Con eso se ejecuta la prueba real y se registran modelo, estado HTTP, latencia y tokens en este documento.

## 11. Limitaciones

- Solo Chrome. Sin pruebas en Firefox, Safari o dispositivos reales.
- Las pruebas de navegador usan un proveedor simulado; no demuestran la calidad de ninguna respuesta de IA.
- El copiloto no ha sido probado con el modelo real.
- Rate limiting en memoria, no compartido entre procesos.
