# Fase 06B — Conexión con Supabase: implementación

Pruebas: [PRUEBAS_FASE_06B.md](PRUEBAS_FASE_06B.md). Esquema remoto: [FASE_06_SQL_EDITOR.md](FASE_06_SQL_EDITOR.md).

**Estado honesto:** el código de conexión está implementado y probado con simulación. La
**integración remota no está verificada**: la configuración local apunta a otro proyecto de Supabase y
falta la clave publicable de AURORA_IA. Hasta que lo corrijas, no hay login ni persistencia remota probados.

## 1. Auditoría

| Elemento | Estado |
|---|---|
| Git | Sin commits. Cambios de todas las fases sin seguir. |
| Pytest | 218 pruebas en verde al empezar. |
| `backend/.env` | Existe (ignorado por Git, no rastreado). Tiene `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` **definidas**, pero la URL **no corresponde** al proyecto AURORA_IA (`<ref-del-proyecto>`). No se ha impreso ni usado. |
| `frontend/.env.local` | No existe. |
| JWT signing keys | Verificado en lectura pública del JWKS del proyecto AURORA_IA (ver §4). |
| Migraciones | Ejecutadas por ti en el SQL Editor (Fase 01 y Fase 06). No se han vuelto a ejecutar. |

## 2. Código implementado

**Adaptadores PostgREST nuevos** (`backend/app/repositories/postgrest_dominio.py`):

- `PostgrestBudgetRepository`: presupuestos mensuales (crear, actualizar, consultar) y gastos
  (listar, crear, editar, eliminar).
- `PostgrestTaskRepository`: tareas (listar, crear, editar, eliminar).

Ambos tienen la misma interfaz que los repositorios SQLite, de modo que los servicios existentes
(`BudgetService`, `TaskService`), los motores (`core/budget.py`, `core/tasks.py`) y el panel general
funcionan sin cambios de reglas.

**Seguridad de las peticiones:**

- Cada petición lleva el JWT del usuario (`Authorization: Bearer <access_token>`) y la clave publicable
  en `apikey`. Nunca `service_role`.
- Las inserciones no envían `user_id`. La base lo asigna con `DEFAULT auth.uid()` y la política RLS lo valida.
- Sin JWT, el adaptador no envía la petición (`SupabaseRejectedTokenError`).
- Los errores de la base se traducen a códigos HTTP (403 por permiso, 409 por duplicado, 422 por restricción).

**Importes exactos:**

- El cliente PostgREST lee los `numeric` como `Decimal` (`response.json(parse_float=Decimal)`), no como `float`.
- Los servicios pasan los importes como cadena decimal (`str(Decimal)`) hacia el repositorio.
- SQLite sigue guardando `REAL` (esquema sin cambios); la conversión a `float` ocurre solo en su escritura.
  El riesgo de precisión de SQLite se mantiene documentado (Fase 04).

**Dependencias (`backend/app/api/deps.py`):**

- `PERSISTENCE_BACKEND=sqlite` (por defecto para demostraciones): finanzas y tareas usan SQLite.
- `PERSISTENCE_BACKEND=supabase`: finanzas, tareas, panel y copiloto usan PostgREST.
- Si Supabase no está configurado, finanzas y tareas responden 503 claro, y el panel las marca como no disponibles.
  No se inventan cifras.

**Pruebas de la suite:** el entorno de pruebas fija `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` vacías,
porque las variables de entorno tienen prioridad sobre `backend/.env`. Así las pruebas no dependen de
la configuración real.

## 3. Módulo académico con PostgREST

Ya existía el adaptador (`academic_repository.py`), con la misma estrategia de JWT y RLS. No se ha modificado
su lógica. Su integración remota **no está verificada** (ver PRUEBAS_FASE_06B.md).

## 4. JWT signing keys, issuer, audiencia y JWKS

Verificado en **lectura pública** del JWKS del proyecto AURORA_IA (`GET .../auth/v1/.well-known/jwks.json`,
sin autenticación, sin SQL):

- HTTP 200.
- Una clave pública: `kty=EC`, `crv=P-256`, `alg=ES256`, `use=sig`.
- El backend acepta `RS256` y `ES256`; por tanto **no hace falta el secreto HS256 heredado**.

Valores esperados del proyecto (derivados de la referencia `<ref-del-proyecto>`):

| Parámetro | Valor |
|---|---|
| Issuer | `https://<ref-del-proyecto>.supabase.co/auth/v1` |
| Audiencia | `authenticated` (valor por defecto de `JWT_AUDIENCE`) |
| JWKS | `https://<ref-del-proyecto>.supabase.co/auth/v1/.well-known/jwks.json` |

**Riesgo:** si `SUPABASE_URL` de `backend/.env` no es la de AURORA_IA, el issuer derivado tampoco lo será, y
todos los tokens válidos de AURORA_IA se rechazarían con 401.

## 5. Lo que hay que corregir en la configuración local (lo haces tú)

No he modificado `backend/.env` ni he impreso sus valores.

1. En `backend/.env`, cambiar `SUPABASE_URL` a `https://<ref-del-proyecto>.supabase.co`.
2. Asegurarse de que `SUPABASE_PUBLISHABLE_KEY` es la **clave publicable de AURORA_IA** (Project Settings → API).
   Si la actual pertenece a otro proyecto, sustitúyela. No uses nunca la clave `service_role`.
3. Crear `frontend/.env.local` con dos líneas: `VITE_SUPABASE_URL=https://<ref-del-proyecto>.supabase.co` y
   `VITE_SUPABASE_PUBLISHABLE_KEY=<la misma clave publicable>`. Es el único archivo del frontend que
   necesita valores; no está versionado.
4. Confirmar que `PERSISTENCE_BACKEND=supabase` en `backend/.env` cuando quieras usar la base remota.
   Para demostraciones locales, déjalo en `sqlite` o usa un archivo de entorno aparte.

## 6. Pendiente (requiere tu acción)

- **Verificación remota del esquema:** ejecuta `supabase/sql_editor/03_verificar_resultado.sql` en el SQL Editor de
  AURORA_IA y pega aquí el resultado (nueve filas, todas `true` esperadas). No lo ejecuté yo.
- **Usuarios de prueba A y B:** créalos tú en Authentication → Users del proyecto AURORA_IA (con correos ficticios).
  No me envíes sus contraseñas. Las pruebas de integración leerán sus credenciales de variables de entorno locales.
- **Confirmar la URL y la clave** (§5), tras lo cual podré ejecutar la verificación remota de login y RLS.

## 7. Límites y riesgos

- **RLS**: no verificada remotamente. Las pruebas de aislamiento son simuladas (servidor PostgREST en memoria).
- **Sin commits ni push; sin despliegue en Render.**
- **Supabase CLI**: no se ha usado.
- **Migraciones**: no se ha ejecutado ninguna. Las tablas remotas son las que ejecutaste manualmente.
- **Copiloto con Supabase**: depende de finanzas y tareas por PostgREST; el contexto se construye igual, pero solo
  con datos reales cuando la configuración remota esté verificada.
- **Rate limiting del copiloto**: en memoria, como antes.
- **OpenRouter**: sin cambios ni llamadas pagas. La configuración de `backend/.env` no se ha modificado.

## 8. Lo que no se ha hecho (por instrucción)

- `supabase login`, `link`, `db push`, `db reset`.
- Scripts SQL remotos, ni siquiera de lectura.
- Borrado o migración de datos de SQLite.
- Uso de `service_role`.
- Despliegue en Render, commits y push.
