# Pruebas — Fase 06C (verificación real de Supabase)

Fecha: 2026-11-12 · Proyecto: AURORA_IA (`<ref-del-proyecto>`).

**Estado: PARCIAL.** La conectividad y la configuración están verificadas contra el proyecto real. Faltan las
pruebas que requieren usuarios autenticados (registro, login, CRUD con sesión, aislamiento A/B, persistencia
tras reinicio), porque necesitan dos cuentas de prueba que aún no existen. No se han usado simulaciones para dar
por buenas estas comprobaciones remotas.

Reglas cumplidas: sin Supabase CLI, sin migraciones, sin `service_role`, sin impresión de claves ni JWT,
sin consumo de OpenRouter, sin commits, push ni despliegues.

## 1. Configuración (sin imprimir valores de claves)

| Comprobación | Resultado |
|---|---|
| `backend/.env` · `SUPABASE_URL` apunta exactamente a `<ref-del-proyecto>` | ✅ |
| `frontend/.env` · `VITE_SUPABASE_URL` apunta exactamente a `<ref-del-proyecto>` | ✅ |
| Clave publishable presente en ambos y **idéntica** entre backend y frontend | ✅ |
| Formato `sb_publishable_…` y ninguna clave secreta (`sb_secret_` o `service_role`) | ✅ |
| `backend/.env` y `frontend/.env` ignorados por Git y sin rastrear | ✅ |
| Configuración de OpenRouter sin cambios (clave presente, modelo `google/gemma-4-26b-a4b-it:free`, proveedor `openrouter`) | ✅ |
| `PERSISTENCE_BACKEND` no definida (por defecto `supabase`) · `DEMO_MODE` no definida · `APP_ENV=development` | ✅ |
| `VITE_API_BASE_URL` | ⚠️ **Corregido**: estaba en `https://…supabase.co/rest/v1/` (PostgREST directo, saltándose FastAPI). Ahora vacía: mismo origen, con el proxy `/api` de Vite. Reversible. |
| Nombre del archivo del frontend | ⚠️ Está en `frontend/.env`, no en `frontend/.env.local` como indicaba la instrucción. Vite lo lee igual; Git lo ignora. Si prefieres `.env.local`, renómbralo. |

**Alerta de proyecto:** la auditoría detectó primero una `SUPABASE_URL` de otro proyecto en `backend/.env`. Ya corregida,
y todas las comprobaciones posteriores son contra `<ref-del-proyecto>`.

## 2. Conectividad y clave (contra el proyecto real)

| Prueba | Resultado |
|---|---|
| `GET /auth/v1/settings` con la clave publishable (solo lectura) | ✅ HTTP 200 → la clave es aceptada por **este** proyecto (una clave de otro proyecto recibiría 401) |
| Proveedor de correo habilitado; `mailer_autoconfirm = false` | ℹ️ Registro requiere confirmar el correo; no hay auto-confirmación |
| JWKS público (`.well-known/jwks.json`) | ✅ una clave EC P-256, `alg=ES256` (ver Fase 06B) |
| `GET /rest/v1/{academic_subjects,monthly_budgets,budget_expenses,tasks}` **sin usuario** (solo clave publishable) | ✅ HTTP 401 con código `42501` en las cuatro: el anónimo no tiene acceso al dominio |

Estos cuatro resultados son de Supabase real. No se ha usado ningún usuario ni ninguna clave secreta.

## 3. Backend en modo Supabase (sin DEMO_MODE)

Arranque: `uvicorn app.main:app` sobre la configuración de `backend/.env`, puerto 8770 (ya detenido).

| Endpoint | Sin token | Resultado |
|---|---|---|
| `GET /api/modo` | — | ✅ `{"modo":"produccion","persistencia":"supabase"}` |
| `GET /api/health` | — | ✅ `supabase_configurado: true` |
| `/api/subjects`, `/api/tareas`, `/api/finanzas/presupuestos`, `/api/dashboard`, `/api/copilot/estado` | ✅ 401 cada una |
| Token falso (no firmado por el proyecto) | ✅ 401, sin trazas en el registro |

## 4. Regresión

| Ámbito | Resultado |
|---|---|
| Pytest completo | ✅ **228 aprobadas** |
| Build de Vite (con la configuración corregida) | ✅ compila |
| CLI calificaciones / presupuesto / tareas (SENA) | ✅ exit 0 / 0 / 0 |
| Servidor de desarrollo SQLite del puerto 8765 | ✅ intacto, responde |

## 5. Pendiente: requiere dos cuentas de prueba (no ejecutado)

| Prueba | Bloqueo |
|---|---|
| Registro de A y B mediante `signup` | Necesita dos correos controlables y confirmarlos (auto-confirmación desactivada) |
| Inicio de sesión y recuperación de sesión | Depende de las cuentas |
| CRUD académico, financiero y de tareas con PostgreSQL real, con JWT de A | Depende de las cuentas |
| Dashboard y contexto del copiloto leyendo los datos de A | Depende de las cuentas |
| **Aislamiento RLS real A/B**: leer, modificar y eliminar datos de B desde A | Depende de las cuentas |
| Persistencia tras reiniciar la aplicación | Depende de las cuentas |

**Qué necesito para continuar:**

1. Dos correos ficticios que controles (o alias de tu correo). Ejemplo: `tu.correo+aurora-a@…`.
2. Decidir la confirmación: confirmas tú los correos desde el enlace, o creas los dos usuarios en
   Authentication → Users del dashboard con la opción de confirmación automática.
3. Las contraseñas **no me las envíes por el chat**: introdúcelas tú en el formulario de la aplicación, o déjalas
   en variables de entorno locales que yo lea sin imprimir.

## 6. Limitaciones

- Ninguna prueba de esta fase usa simulación para el resultado remoto; las simulaciones de Fase 06B siguen siendo
  las únicas pruebas de los adaptadores y no sustituyen a estas.
- Solo Chrome, y no se ha probado la aplicación en navegador en modo Supabase todavía.
- Sin commits, push ni despliegue en Render.
