# Fase 08A — Persistencia de conversaciones del copiloto

Pruebas y resultados: [PRUEBAS_FASE_08A.md](PRUEBAS_FASE_08A.md).

**Estado: preparada y revisable. NO aplicada.** La migración no se ha ejecutado en ningún proyecto de Supabase.
Hasta que la apliques y verifiques tú, la aplicación sigue funcionando **en memoria**, y la interfaz no lo presenta
como guardado. No se ha usado Supabase CLI, `service_role` ni se ha llamado a OpenRouter.

## 1. Diseño

### 1.1 Tablas

**`public.ai_conversations`**

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()` |
| `user_id` | `uuid` NOT NULL | `DEFAULT auth.uid()`, FK a `auth.users` con cascada |
| `title` | `text` NOT NULL | Por defecto «Nueva conversación». 1–120 caracteres tras `btrim` |
| `created_at`, `updated_at` | `timestamptz` | `updated_at` lo fija el servidor en cada cambio |

Restricciones: `unique (user_id, id)`. Índice `(user_id, updated_at desc, id)` para listar.

**`public.ai_messages`**

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `orden` | `bigint` identidad, único | Orden estable de inserción (`created_at` puede empatar) |
| `user_id` | `uuid` NOT NULL | `DEFAULT auth.uid()` |
| `conversation_id` | `uuid` NOT NULL | |
| `cliente_id` | `uuid` NOT NULL | Clave de idempotencia generada por la interfaz |
| `role` | `text` | Solo `user` o `assistant` |
| `content` | `text` | 1–8000 caracteres tras `btrim` |
| `estado` | `text` | `completado` o `incompleto` |
| `proveedor`, `modelo` | `text` NULL | Máximos 30 y 120 caracteres |
| `simulado` | `boolean` NULL | |
| `contexto_usado` | `text[]` | Solo `academic`, `finance`, `tasks`. Hasta 3 |
| `total_tokens` | `integer` NULL | ≥ 0 |
| `created_at` | `timestamptz` | |

Restricciones: **clave foránea compuesta** `(user_id, conversation_id)` → `ai_conversations (user_id, id)` con
cascada; `unique (user_id, conversation_id, cliente_id)` (idempotencia); `unique (user_id, id)`.

### 1.2 Garantías

- **Pertenencia.** La clave foránea compuesta exige que la conversación sea del mismo `user_id` que el mensaje.
  Un intento de escribir en una conversación ajena falla con `23503`, aunque se conozca el identificador.
- **Identidad.** `user_id` lo asigna `auth.uid()`. Las políticas exigen `auth.uid() = user_id`. Si el navegador
  envía otro `user_id`, la base rechaza la fila (`42501`). El backend además no acepta ese campo (`extra="forbid"`).
- **Idempotencia.** Reenviar el mismo `cliente_id` no crea otra fila. Si llega con otro contenido, se rechaza (409).
- **Inmutabilidad.** Los mensajes no tienen políticas de `UPDATE` ni `DELETE`. Solo se eliminan en cascada al borrar
  su conversación. El cliente solo puede cambiar el **título** de una conversación.
- **anon.** Sin permisos ni políticas.
- **Las cinco tablas existentes no se modifican.**

### 1.3 Políticas RLS

| Tabla | Operación | Condición |
|---|---|---|
| `ai_conversations` | select / update / delete | `auth.uid() = user_id` |
| `ai_conversations` | insert | `with check (auth.uid() = user_id)` |
| `ai_messages` | select | `auth.uid() = user_id` |
| `ai_messages` | insert | `with check (auth.uid() = user_id)` |
| `ai_messages` | update / delete | sin política (denegado) |

Privilegios de tabla y de columna (tras una revocación **explícita** de `anon`, `authenticated` y `public`):

| Rol | `ai_conversations` | `ai_messages` |
|---|---|---|
| `anon` | ninguno | ninguno |
| `authenticated` | `select`, `delete`; `insert` solo de `title`; `update` solo de `title` y `updated_at` | `select`; `insert` solo de `conversation_id`, `cliente_id`, `role`, `content`, `estado`, `proveedor`, `modelo`, `simulado`, `contexto_usado`, `total_tokens` |

Sin `truncate`, `references` ni `trigger` para nadie fuera del propietario. `user_id`, `id`, `orden` y `created_at`
nunca son insertables desde el cliente: su valor lo fija la base.

**Por qué la revocación explícita es imprescindible:** Supabase concede por defecto privilegios de tabla a
`authenticated` sobre las tablas nuevas de `public`. RLS **no filtra `TRUNCATE`**. En una prueba local que emula
ese valor por defecto, la versión inicial de esta migración permitía a un usuario vaciar `ai_messages` para todos
los usuarios. Esta versión lo impide. Ver [PRUEBAS_FASE_08A.md](PRUEBAS_FASE_08A.md) §9.

### 1.4 Endpoints (FastAPI, JWT validado, PostgREST con el token del usuario)

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/copilot/conversaciones?limit&offset` | Lista propia, más reciente primero. `limit` 1–100 (por defecto 20). Devuelve `siguiente` |
| POST | `/api/copilot/conversaciones` | Crea una conversación (título opcional) |
| GET | `/api/copilot/conversaciones/{id}` | Consulta una conversación propia |
| PATCH | `/api/copilot/conversaciones/{id}` | Cambia el título |
| DELETE | `/api/copilot/conversaciones/{id}?confirmar=true` | Borra. Sin `confirmar=true` responde 422 |
| GET | `/api/copilot/conversaciones/{id}/mensajes?limit&offset` | Mensajes en orden de inserción. Por defecto 100 |
| POST | `/api/copilot/conversaciones/{id}/mensajes` | Guarda un mensaje. Idempotente: devuelve `repetido: true` si ya existía |

Errores: 404 si la conversación no es propia o no existe (la base la oculta); 409 por identificador reutilizado con
otro contenido; 422 por datos inválidos o borrado sin confirmar; 401 si el token no es válido; **501 si la
persistencia no está activa** (no finge guardar).

### 1.5 Activación y estado

- Variable `AI_CONVERSACIONES_PERSISTENTES` (por defecto `false`). Solo tiene efecto con
  `PERSISTENCE_BACKEND=supabase` y Supabase configurado. Con SQLite (demostración) nunca se activa.
- `GET /api/copilot/estado` incluye `persistencia: true|false`. La interfaz solo habla de «guardado» cuando es `true`.

### 1.6 Flujo de un envío con persistencia

1. **Guardar la pregunta** (`POST …/mensajes`, rol `user`, con su `cliente_id`).
2. **Consultar al copiloto** (`POST /api/copilot/chat`, igual que antes, con el historial de la conversación activa).
3. **Guardar la respuesta** (`POST …/mensajes`, rol `assistant`, con metadatos limitados y un `cliente_id` propio).

Cada paso tiene su propio reintento. Si falla el guardado de la respuesta, **no se vuelve a consultar al modelo**:
se reintenta solo el guardado. Si falla la pregunta, se reintenta solo ese paso, con el mismo `cliente_id`.

El título se deriva de la primera pregunta (máximo 42 caracteres en pantalla, 120 en la base).

### 1.7 Privacidad

- No se guardan: JWT, claves, contexto académico, financiero o de tareas (solo los nombres de las áreas usadas),
  ni los mensajes de error de la interfaz.
- Las peticiones del navegador no llevan credenciales dentro del cuerpo; la autenticación va en la cabecera
  `Authorization` del cliente HTTP existente.

## 2. Archivos

| Archivo | Qué es |
|---|---|
| `supabase/migrations/20261113120000_fase08a_conversaciones_ia.sql` | **Migración incremental. Pendiente de revisión y aplicación.** |
| `supabase/sql_editor/08a_verificar_conversaciones.sql` | Verificación **de solo lectura** para el SQL Editor |
| `supabase/tests/08a_stub_auth_LOCAL_no_supabase.sql` | Simulación local de `auth` (solo para clústeres desechables) |
| `supabase/tests/08a_probar_rls_LOCAL_desechable.sql` | 25 pruebas de comportamiento en un clúster desechable |
| `backend/app/schemas/conversaciones.py` | Contratos (extra="forbid", límites) |
| `backend/app/repositories/postgrest_conversaciones.py` | Adaptador PostgREST con el JWT del usuario |
| `backend/app/services/conversation_service.py` | Reglas: propiedad, idempotencia, confirmación de borrado |
| `backend/app/api/routes_conversaciones.py` | Endpoints |
| `backend/app/api/deps.py` | Dependencia; 501 si la persistencia no está activa |
| `backend/tests/test_conversaciones.py` | 23 pruebas con PostgREST simulado |
| `frontend/src/api/conversaciones.ts` | Cliente de la API |
| `frontend/src/copilot/CopilotProvider.tsx` | Estado compartido con dos modos (memoria / persistente) |
| `frontend/src/pages/CopilotPage.tsx` | Aviso, carga, «Cargar más conversaciones» y nota de guardado |
| `frontend/e2e/fase08a_persistencia_simulada.py` | 26 comprobaciones de interfaz con backend simulado en el navegador |

## 3. Cómo aplicar la migración (SQL Editor) — SOLO CUANDO LA HAYAS REVISADO

1. Abre el dashboard de Supabase y selecciona el proyecto **AURORA_IA** (ref `<ref-del-proyecto>`). Comprueba el
   nombre antes de continuar.
2. Ve a **SQL Editor → New query**.
3. Abre `supabase/migrations/20261113120000_fase08a_conversaciones_ia.sql`, copia **todo** el contenido, pégalo y
   pulsa **Run**. Es idempotente: puedes repetirlo sin efectos adicionales.
4. En una consulta nueva, copia `supabase/sql_editor/08a_verificar_conversaciones.sql` y pulsa **Run**.
   Devuelve **20 filas**; **todas** deben tener `ok = true`, incluida «tablas de dominio existentes con RLS activa
   (5 de 5)». Si alguna es `false`, no actives la persistencia y pásame el resultado.
5. No ejecutes nada más. No uses la CLI de Supabase ni la clave `service_role`.

Después de la verificación, y solo con tu autorización, se activa con `AI_CONVERSACIONES_PERSISTENTES=true` en
`backend/.env` y se reinicia el backend. Mientras tanto, el valor por defecto `false` mantiene el modo en memoria.

## 4. Lo que no cambió

- Las cinco tablas de dominio, sus políticas y sus permisos.
- Los 48 registros DEMO-AURORA- del dataset.
- El backend del copiloto de OpenRouter y sus límites.
- Ningún commit, push ni despliegue.
