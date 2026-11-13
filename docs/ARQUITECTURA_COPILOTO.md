# Arquitectura del copiloto AURORA

Estado: **implementado y probado con proveedor de prueba y simulado**. La llamada real a OpenRouter
**no se ha realizado** porque no hay clave configurada (ver [PRUEBAS_FASE_05.md](PRUEBAS_FASE_05.md)).

## 1. Flujo

```
React (CopilotPage)
   │  POST /api/copilot/chat  { message, history, include_context }   ← sin user_id ni datos académicos
   ▼
FastAPI · routes_copilot.py
   │  1. Validación de esquema (Pydantic, extra="forbid", límites de tamaño)
   │  2. Identidad: get_principal → JWT verificado (o usuario demo local en desarrollo)
   ▼
CopilotService (copilot_service.py)
   │  3. Límites: peticiones/minuto, presupuesto diario de tokens, concurrencia
   │  4. ContextBuilder (context_builder.py) ── lee SOLO vía servicios internos
   │        ├─ DashboardService  → cifras de los motores (promedio, saldo, vencimientos)
   │        ├─ AcademicService   → notas por asignatura
   │        └─ BudgetService     → gastos del mes (sin identificadores)
   │  5. Mensajes: [system: prompt versionado] [system: DATOS delimitados] [historial] [user]
   ▼
AIProvider (interfaz)
   ├─ OpenRouterProvider  → POST https://openrouter.ai/api/v1/chat/completions (Bearer)
   └─ SimulatedProvider   → solo desarrollo; etiquetado SIMULADO
   ▼
ChatOut { answer, provider, model, simulado, context_used, usage, incomplete, latency_ms, prompt_version }
   ▼
React: burbuja del asistente con procedencia (OpenRouter o SIMULADO) y datos usados
```

## 2. Componentes

| Componente | Archivo | Responsabilidad |
|---|---|---|
| Interfaz de proveedor y errores | `backend/app/ai/provider.py` | `AIProvider`; `ProviderResponse`; errores con código HTTP y código estable |
| Cliente OpenRouter | `backend/app/ai/openrouter_client.py` | HTTP con `httpx`; mapea 401, 402, 429, 5xx, timeouts y respuestas malformadas |
| Proveedor simulado | `backend/app/ai/simulated_provider.py` | Resumen determinista; **no es IA**; prohibido fuera de desarrollo |
| Prompts versionados | `backend/app/ai/prompts.py` | `SYSTEM_PROMPT`, `PROMPT_VERSION`, bloque de datos delimitado |
| Contexto | `backend/app/ai/context_builder.py` | Construye el contexto desde los servicios, sin identificadores |
| Orquestación y límites | `backend/app/ai/copilot_service.py` | Flujo completo, `Limitador`, métricas técnicas |
| Contratos | `backend/app/schemas/copilot.py` | Entrada, salida y estado; `extra="forbid"` |
| Endpoints | `backend/app/api/routes_copilot.py` | `POST /api/copilot/chat`, `GET /api/copilot/estado` |
| Dependencias | `backend/app/api/deps.py` | `get_ai_provider` (None si no hay clave), `get_copilot_service` |
| Interfaz | `frontend/src/pages/CopilotPage.tsx` | Chat, sugerencias, errores, reintento, render seguro |

## 3. Separación entre reglas deterministas y generación

- **Cifras y reglas**: promedios, aprobación, nota necesaria, saldos, porcentajes, vencimientos y
  prioridades los calculan los motores (`core/grades.py`, `core/budget.py`, `core/tasks.py`) y los
  servicios. El contexto se envía tal cual; el modelo no las recalcula.
- **Generación**: el modelo solo redacta la explicación a partir de ese contexto.
- **Respuesta visible**: la interfaz indica la procedencia (OpenRouter con modelo, o SIMULADO) y
  los bloques de datos usados.

## 4. Contexto autorizado

- Solo se lee a través de los servicios con el `Principal` de la petición. Un usuario nunca recibe
  datos de otro (prueba `test_aislamiento_por_identidad_en_el_contexto`).
- **Sin identificadores**: ningún UUID, `user_id` ni marca de tiempo entra en el contexto (prueba
  `test_contexto_no_contiene_identificadores_ni_marcas_de_tiempo`).
- **Límites de volumen**: 30 asignaturas, 40 notas por asignatura, 60 gastos, 10 tareas por lista.
- **Bloques indicados por el usuario**: `include_context` activa o desactiva académico, finanzas y tareas.
  El servidor vuelve a validar cada bloque; el navegador no envía datos.
- **Sin registros**: si no hay datos, el contexto lo declara (`sin_datos: true`) y el modelo debe
  decir que no hay información suficiente (prueba `test_sin_registros_no_se_inventan_datos`).

## 5. Seguridad

| Riesgo | Control |
|---|---|
| Clave expuesta en el navegador | La clave se lee del entorno del servidor (`SecretStr`). No hay ninguna referencia en React ni en los archivos versionados. |
| Clave en logs o errores | `_registrar` solo registra estado, latencia y tokens. Prueba `test_la_clave_no_aparece_en_los_logs`. Los errores no incluyen la clave. |
| Contenido del usuario en logs | No se registran mensajes, contexto ni respuestas. |
| Instrucciones maliciosas | El prompt declara los datos como información; los datos van delimitados y el usuario va como mensaje `user`. Pruebas `test_instrucciones_del_usuario_no_sustituyen_al_sistema` e `test_instruccion_maliciosa_en_titulo_de_tarea_queda_dentro_de_los_datos`. **Límite**: no garantiza que el modelo obedezca siempre; ver §8. |
| Acción sobre registros | Ninguna herramienta de escritura se entrega al modelo. El proveedor solo devuelve texto. |
| Identidad impuesta desde el navegador | `extra="forbid"`: un `user_id` en el cuerpo responde 422 (prueba `test_el_navegador_no_puede_imponer_identidad_ni_datos`). |
| Acceso anónimo en producción | El chat y el estado exigen token; en producción no existe el modo demo (validado al arrancar). |
| Simulado en producción | `validate_runtime` impide arrancar con `COPILOT_PROVIDER=simulado` fuera de desarrollo. |
| Costes excesivos | Límite de peticiones por minuto, presupuesto diario de tokens y concurrencia máxima. Los valores son configurables. |

## 6. Gestión de errores del proveedor

| Situación | Código HTTP del copiloto | Código | Mensaje al usuario |
|---|---|---|---|
| Sin clave o sin modelo | 503 | `no_configurado` | Copiloto pendiente de configuración |
| 401 del proveedor | 503 | `clave_invalida` | La clave no es válida (sin mostrar la clave) |
| 402 del proveedor | 503 | `sin_credito` | Falta crédito o presupuesto |
| 429 del proveedor | 429 | `limite_proveedor` | Intenta en unos segundos |
| 5xx o red caída | 503 | `proveedor_no_disponible` | No responde |
| Timeout | 504 | `tiempo_agotado` | Reintenta |
| Respuesta sin contenido | 502 | `respuesta_invalida` | No se pudo interpretar |
| Respuesta cortada por límite | 200 | `incomplete: true` | Se marca en la interfaz |
| Límite propio de peticiones o tokens | 429 | — | Espera o vuelve mañana |
| Concurrencia agotada | 429 | — | Intenta en unos segundos |

## 7. Configuración

Todas se leen de variables de entorno del backend. Ver `backend/.env.example`.

| Variable | Valor por defecto | Notas |
|---|---|---|
| `OPENROUTER_API_KEY` | vacío | Secreta. Nunca en el repositorio. |
| `OPENROUTER_MODEL` | vacío | Identificador verificado en openrouter.ai/models antes de usar. Sin valor, el copiloto queda pendiente. |
| `OPENROUTER_TIMEOUT_SECONDS` | 20 | Máximo 60. |
| `COPILOT_PROVIDER` | `openrouter` | `simulado` solo en desarrollo. |
| `COPILOT_MAX_TOKENS` | 700 | Límite de la respuesta. |
| `COPILOT_REQUESTS_PER_MINUTE` | 10 | Por usuario y por proceso. |
| `COPILOT_DAILY_TOKENS` | 100000 | Por usuario y día, según el uso que informa el proveedor. |
| `COPILOT_CONCURRENCY` | 2 | Consultas simultáneas al proveedor. |

## 8. Riesgos abiertos

1. **Inyección indirecta**: un modelo puede seguir instrucciones incrustadas en los datos. Las
   pruebas verifican la **estructura** (mensajes, delimitadores, ausencia de herramientas), no el
   comportamiento del modelo. Requiere pruebas con el modelo real, pendientes de clave.
2. **Límites en memoria**: no se comparten entre procesos ni reinicios. En despliegues con varias
   instancias harían falta un almacén común.
3. **Sin streaming**: la respuesta llega completa. El streaming se añadirá cuando la ruta
   convencional esté verificada con la clave real.
4. **Precisión monetaria**: los importes siguen en `REAL` en SQLite (ver
   [FASE_04_IMPLEMENTACION.md](FASE_04_IMPLEMENTACION.md) §5.1). El copiloto los recibe como texto
   decimal del motor; la migración propuesta aún no se ha aplicado.
5. **Precios y modelos**: no se ha verificado el coste ni la disponibilidad de ningún modelo concreto.

## 9. Lo que no está conectado

- Supabase (autenticación real y PostgreSQL) — fase futura.
- OpenRouter en tiempo real — requiere `OPENROUTER_API_KEY` y `OPENROUTER_MODEL`.
- Despliegue en Render — no realizado.

## 10. Interfaz (Fase 07): dos vistas, un estado

- **Estado compartido** (`frontend/src/copilot/CopilotProvider.tsx`): `CopilotProvider` + `useCopilot`. Una sola
  conversación para la página completa y el widget. Un único envío a la vez. Solo se envía al backend el historial
  de la conversación activa, en intercambios completos. Se reinicia al cambiar de cuenta.
- **Página completa** (`pages/CopilotPage.tsx`) y **widget flotante** (`copilot/CopilotWidget.tsx`): ambos usan los
  mismos componentes de presentación (`copilot/Mensajes.tsx`) y el mismo endpoint `POST /api/copilot/chat`.
- **Sin cambios de backend**: la interfaz no añade rutas ni duplica el cliente de OpenRouter.
- **Persistencia**: las conversaciones viven solo en la sesión del navegador. Las tablas `ai_conversations` y
  `ai_messages` no existen todavía.
