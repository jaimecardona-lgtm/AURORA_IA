# Pruebas — Fase 08A (persistencia de conversaciones)

Fecha: 2026-11-13 · Windows 11 · PostgreSQL 18 (clúster desechable local) · Chrome · Python 3.12 · Node 22.

**Estado: pruebas locales aprobadas. Pruebas contra Supabase real: PENDIENTES** (la migración no se ha aplicado).
Ninguna prueba de este documento contacta con Supabase ni con OpenRouter.

## 1. Resumen

| Bloque | Qué comprueba | Resultado | Tipo |
|---|---|---|---|
| Pytest completo (backend) | Regresión y nuevas pruebas | ✅ **262 aprobadas** (239 previas + 23 nuevas) | Local, PostgREST simulado |
| TypeScript estricto | Tipos de la interfaz nueva | ✅ sin errores | Local |
| Build de Vite | Compilación | ✅ correcto | Local |
| Migración SQL en clúster limpio | Aplica, idempotente | ✅ aplica y se repite sin errores | **Clúster desechable local, no Supabase** |
| Pruebas SQL de comportamiento | RLS, propiedad, FK compuesta, idempotencia, permisos de columna, TRUNCATE, cascada | ✅ **25 de 25** | **Clúster desechable local con `auth` simulado** |
| Verificación de solo lectura | Catálogo: RLS, políticas, permisos, TRUNCATE, FK, disparadores | ✅ 19 de 20 en `true`; la comprobación de las 5 tablas de dominio es `false` porque el clúster no las contiene (esperado) | Clúster desechable local |
| Suite de la fase 07 (copiloto en memoria) | Sin persistencia, comportamiento anterior | ✅ **26 de 26** | Backend demo + Vite |
| Interfaz con persistencia | Carga, envío, reintentos, widget, borrado | ✅ **26 de 26** | **Backend simulado en el navegador** |

## 2. Pytest: pruebas nuevas (`backend/tests/test_conversaciones.py`, 23)

El PostgREST de estas pruebas es una **simulación en memoria** (`httpx.MockTransport`). Reproduce propiedad por
usuario, clave foránea compuesta, unicidad de `cliente_id`, restricciones de contenido y denegación de escrituras
no permitidas. **No prueba la política RLS real de Supabase.**

- CRUD de conversaciones; paginación (25 conversaciones en páginas de 10, sin repetidos, `siguiente` correcto).
- Límites de paginación (0, 101, desplazamiento negativo) rechazados.
- Título normalizado, vacío → valor por defecto, recorte a 120.
- Lecturas y escrituras cruzadas: B no obtiene, lista, renombra ni borra conversaciones de A (404).
- No se puede escribir en una conversación ajena, ni siquiera con el identificador.
- El navegador no puede imponer `user_id` (422).
- Idempotencia: reenvío con el mismo `cliente_id` → `repetido: true`, una sola fila.
- Mismo `cliente_id` con otro contenido → 409.
- **Carrera:** otro envío llega entre la comprobación y la inserción → se devuelve el existente, sin duplicar.
- Mensajes paginados en orden de inserción.
- Metadatos del asistente guardados con sus límites.
- Borrado sin confirmar → 422; confirmado → 204 y mensajes eliminados en cascada.
- Token ausente → 401; token rechazado por la base → 401, nunca datos.
- Sin persistencia activa → **501** en los endpoints; estado del copiloto con `persistencia: false`.

## 3. Pruebas SQL en clúster desechable (`supabase/tests/08a_probar_rls_LOCAL_desechable.sql`, 25)

Clúster PostgreSQL 18 local, puerto 55433, base `aurora_08a_final`, con `auth.users`, `auth.uid()` y roles
`anon` / `authenticated` **simulados**, con los privilegios por defecto de tabla de Supabase emulados
(`08a_stub_auth_LOCAL_no_supabase.sql`, supuesto a confirmar en el proyecto real). Ejecutado desde cero: **25 de 25**.

| Comprobación | Esperado | Resultado |
|---|---|---|
| A crea su conversación | OK | ✅ |
| A no puede crear una conversación a nombre de B | 42501 | ✅ |
| A escribe en su conversación | OK | ✅ |
| Mismo `cliente_id` en la misma conversación | 23505 | ✅ |
| A no puede escribir en una conversación de B (FK compuesta) | 23503 | ✅ |
| A no puede escribir como B aunque conozca el identificador | 42501 | ✅ |
| B no lee conversaciones ni mensajes de A | 0 filas | ✅ ✅ |
| B no renombra ni borra la conversación de A | 0 filas | ✅ ✅ |
| A renombra su conversación | OK | ✅ |
| A no puede cambiar `user_id` de su conversación | 42501 | ✅ |
| A no puede modificar el contenido de un mensaje | 42501 | ✅ |
| A no puede borrar mensajes directamente | 42501 | ✅ |
| `anon` no lee conversaciones ni escribe mensajes | 42501 | ✅ ✅ |
| Título vacío y de 121 caracteres rechazados | 23514 | ✅ ✅ |
| Contexto fuera de la lista y rol `system` rechazados | 23514 | ✅ ✅ |
| Estado `error` no admitido en un mensaje | 23514 | ✅ |
| Respuesta del asistente con metadatos limitados | OK | ✅ |
| A borra su conversación; mensajes eliminados en cascada | OK y 0 mensajes | ✅ |

Aplicar la migración **dos veces** en el mismo clúster no produce errores (idempotencia).

**Defecto encontrado y corregido durante la verificación:** en la primera ejecución, 14 pruebas daban 42501 en
casos legítimos. La causa era la tabla auxiliar de prueba (`public.ids`), que el rol de usuario no podía leer. Se
corrigió en el propio script de pruebas, sin cambiar ningún permiso de la migración. Tras la corrección, las 23
pasan desde un clúster limpio.

## 4. Verificación de solo lectura (`supabase/sql_editor/08a_verificar_conversaciones.sql`)

Ejecutada sobre el clúster desechable: 19 comprobaciones en `true`. La de **«tablas de dominio existentes con RLS
activa (5 de 5)» es `false` ahí, porque ese clúster no contiene esas tablas**. En Supabase real deben dar `true`
las 20 comprobaciones; si no, no se debe activar la persistencia.

## 5. Interfaz con persistencia (backend simulado en el navegador)

`frontend/e2e/fase08a_persistencia_simulada.py`. Playwright intercepta `/api/copilot/*` y responde con un almacén en
memoria que aplica las mismas reglas de idempotencia. El estado que devuelve el script informa `persistencia: true`.
El resto de rutas `/api` se reenvía al backend de demostración. Resultado: **26 de 26**.

| Área | Comprobaciones | Resultado |
|---|---|---|
| Carga | historial del servidor visible; nota «Guardadas en tu cuenta»; conversación previa en la lista | ✅ 3/3 |
| Envío | una consulta; la pregunta se guarda una vez; la respuesta se guarda una vez; sin duplicados | ✅ 4/4 |
| Recarga | el historial se recupera tras recargar | ✅ |
| Guardado fallido | error con reintento; el modelo se consulta una vez; el reintento guarda sin volver a consultar; sin duplicados | ✅ 4/4 |
| Fallo del modelo | error con reintento; el reintento responde; la pregunta se guarda una vez | ✅ 3/3 |
| Nueva conversación | recibe la respuesta; título derivado de la primera pregunta; la anterior sigue | ✅ 3/3 |
| Widget y página | el widget responde en la conversación activa; la pregunta aparece en la página | ✅ 2/2 |
| Privacidad | ninguna petición lleva `eyJ`, `Bearer` ni `password` | ✅ |
| Borrado | la conversación activa desaparece; sus mensajes también; la previa no se toca | ✅ 3/3 |

**Limitación explícita:** esta prueba valida la interfaz, no la base de datos. El almacén es un diccionario en
memoria del propio script.

## 6. Regresión sin persistencia (suite de la fase 07, memoria)

Con el backend de demostración (`persistencia: false`), la suite existente pasa **26 de 26**. Confirma que el modo en
memoria sigue igual: sin aparentar guardado, con las mismas peticiones (4) y sin duplicados.

## 7. Pendiente (no ejecutado todavía)

| Prueba | Estado | Motivo |
|---|---|---|
| Aplicar la migración en el proyecto AURORA_IA y ejecutar `08a_verificar_conversaciones.sql` | ⏸ | Requiere tu revisión y aplicación manual |
| RLS real con dos JWT (A y B) contra Supabase | ⏸ | Requiere la migración aplicada y tu sesión |
| Persistencia real tras recargar y tras reiniciar FastAPI | ⏸ | Requiere la migración aplicada y el flag activado |
| Cambio de cuenta en el navegador con datos reales | ⏸ | Requiere sesiones A y B |
| OpenRouter con conversaciones persistidas | ⏸ bloqueado | Sin autorización; no se ha consumido |

Cuando apliques la migración, te propongo un script de integración con dos sesiones (como 07C) que haga las mismas
comprobaciones de RLS con los JWT reales, y lo ejecutes tú.

## 8. Limitaciones

- El clúster PostgreSQL es local y usa un `auth` simulado: no reproduce el comportamiento exacto de GoTrue ni de
  PostgREST de Supabase.
- El PostgREST de las pruebas de pytest es una simulación en memoria.
- El backend de demostración de este documento no usa Supabase.
- El código del servidor que está corriendo en `:8000` (tu backend de Supabase) es anterior a esta fase y debe
  reiniciarse para exponer los endpoints nuevos. Mientras la variable esté en `false`, responderán 501 y la
  interfaz usará el modo en memoria.

## 9. Auditoría final (2026-11-13): hallazgos y correcciones

Revisión de la migración, del script de verificación, del adaptador PostgREST y de las rutas, con pruebas en un
clúster desechable. No se ha ejecutado SQL en Supabase ni se ha usado la CLI.

| # | Hallazgo | Riesgo | Estado |
|---|---|---|---|
| 1 | Supabase concede privilegios de tabla por defecto a `authenticated`. La migración solo revocaba a `anon` y `public`. Con ese valor por defecto, **un usuario podía ejecutar `TRUNCATE` sobre `ai_messages` y borrar los mensajes de todos los usuarios**, porque RLS no filtra `TRUNCATE` (reproducido: 1 de 1 mensajes eliminados por A) | **Crítico** | **Corregido**: revocación explícita a `authenticated` y concesión mínima por columnas. Prueba y verificación añadidas |
| 2 | `authenticated` podía insertar `user_id`, `id` y `created_at` en las tablas | Medio | **Corregido** con `grant insert` por columnas. Un `INSERT` que las incluya falla con 42501 |
| 3 | El script de verificación usaba `::regclass`, que da error si la tabla no existe | Bajo | **Corregido** con `to_regclass` |
| 4 | El simulador local no emulaba los privilegios por defecto, así que la prueba no detectaba el #1 | Medio | **Corregido**: el simulador los emula (supuesto marcado para confirmar en el proyecto real) |
| 5 | Las pruebas de inserción usaban `id` explícito, que ya no está concedido | Bajo | **Corregido** en las pruebas |

Resultados tras las correcciones (clúster limpio, migración aplicada dos veces):
- Pruebas SQL: **25 de 25**. Incluyen «A no puede vaciar ai_messages con TRUNCATE» y «A no puede fijar created_at».
- Verificación: 19 de 20 en `true`; la de tablas de dominio es `false` solo porque el clúster no las tiene.
- Pytest de conversaciones: 23 aprobadas (sin cambios en el backend).

Comprobaciones sin hallazgos:
- La migración solo crea y modifica objetos `ai_*`. No hay sentencias sobre las cinco tablas actuales.
- Las únicas sentencias `drop` son `drop trigger if exists` y `drop policy if exists`, siempre sobre objetos `ai_*`.
- El script de verificación contiene únicamente `SELECT` y `WITH`.
- El backend no usa `service_role`. Ningún archivo del frontend envía `user_id`.
- La variable `AI_CONVERSACIONES_PERSISTENTES` no aparece en `backend/.env`, y su valor por defecto es `false`.
- El host de `SUPABASE_URL` en `backend/.env` es el proyecto `<ref-del-proyecto>`.
- Un mensaje dirigido a una conversación ajena devuelve 23503, el mismo error que si la conversación no existe.
  Por tanto no revela qué identificadores existen.

Riesgos abiertos (aceptados, no bloquean la aplicación):
- **Sin cuotas.** Cada usuario puede crear conversaciones y mensajes sin límite. Conviene una cuota antes de activar en producción.
- **`service_role` conserva acceso total** por la configuración por defecto de Supabase. La aplicación no la usa; la clave debe quedar solo en el servidor.
- **Los mensajes del asistente contienen datos del usuario** (promedios, saldos). Solo los ve su propietario, pero quedan almacenados.
- **El privilegio por defecto de Supabase es una suposición.** La revocación explícita hace que el resultado sea el mismo tanto si se concede como si no.
  La verificación del paso 4 lo confirma en el proyecto real.
- **Sin FORCE ROW LEVEL SECURITY.** El propietario de la tabla (`postgres`) la omite. Es el comportamiento estándar y no afecta a la aplicación.
