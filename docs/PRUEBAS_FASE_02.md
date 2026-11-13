# Pruebas — Fase 02

Fecha: 2026-11-11 · Entorno: Windows 11 local · Node 22.22.0 · npm 10.6.0 · Python 3.12 (venv) · Docker Desktop 27.2.0 · Supabase CLI 2.48.3

**Estado de la fase: NO COMPLETADA.** La integración con Supabase real está bloqueada porque no hay
proyecto Supabase exclusivo de AURORA AI accesible desde esta sesión (ver §5). Lo que sigue solo
cubre verificación LOCAL.

## 1. Resumen por ámbito

| Ámbito | Resultado |
|---|---|
| Unit/API (pytest) | ✅ 90 superadas |
| Build frontend (`npm ci` + `npm run build`) | ✅ Compila |
| CLI SENA (3 programas) | ✅ Funcionan |
| Docker `build` de la imagen única | ✅ Construye (exit 0) |
| Contenedor: health, SPA, 401 sin token | ✅ Comprobado (sin Supabase configurado) |
| PostgreSQL local + RLS (stub de `auth`) | ✅ 23 comprobaciones (de Fase 01; no repetidas en esta fase) |
| Supabase remoto: JWT real, migración, RLS, registro/login | ⛔ BLOQUEADO (sin proyecto y sin autorización) |
| Navegador con Auth y API reales (A/B) | ⛔ BLOQUEADO (depende de lo anterior) |
| Playwright con sesión y API **simuladas** | Fase 01, no repetido aquí; no cuenta como integración |

## 2. Auditoría (Paso 0)

Comandos y salidas reales:

```
git branch --show-current            → main
git log --oneline -n 3               → 9ae034f Initial commit
git status --short                   → M README.md; ?? .dockerignore .gitignore Dockerfile backend/ docs/ frontend/ render.yaml supabase/
```
Ningún `.env` real existe (solo `backend/.env.example` y `frontend/.env.example`). `git check-ignore`
confirmó en Fase 01 que `.env`, `.env.local`, `.venv`, `node_modules` y `dist` están ignorados.

```
cd backend && python -m pytest -q        → 90 passed, 1 warning
cd frontend && npm ci                    → added 32 packages
cd frontend && npm run build             → tsc --noEmit && vite build → ✓ built
python sena_cli/calificaciones.py 4.5 3.0 2.9   → Promedio: 3.47 · APROBADO · exit 0
python sena_cli/presupuesto.py --ingreso 2000000 --ahorro 300000 --gasto "Arriendo:600000:fijo"
                                         → Saldo final: $ 1,400,000.00 COP · exit 0
python sena_cli/tareas.py "Entregar:1" "Leer:3:completada"  → exit 0
```

## 3. Cambio durante esta fase (con prueba de regresión)

**Hallazgo:** una petición **sin token** a `/api/subjects` respondía **503** cuando el servidor no
tenía Supabase configurado, en vez de **401**. Causa: la dependencia de configuración se evaluaba
antes de mirar el token.

**Corrección:** `get_verifier()` ya no lanza al iniciar; si falta configuración devuelve un verificador
que responde 503 solo al intentar validar un token.

**Regresión:** nueva prueba `test_sin_token_y_sin_configuracion_responde_401_no_503`.
Resultado: `90 passed` (antes 89 + la nueva). Verificado también en la imagen Docker:
`subjects sin token: 401`.

## 4. Docker (real)

```
docker build -t aurora-ai:fase02-local .   → exit 0
docker run -d -p 18000:8000 aurora-ai:fase02-local
GET /api/health → {"status":"ok","supabase_configurado":false,"version":"0.1.0"}
GET /api/subjects (sin token) → 401
```
Advertencias de BuildKit: `SecretsUsedInArgOrEnv` sobre `VITE_SUPABASE_PUBLISHABLE_KEY`. La clave
publishable **es pública** (se incrusta en el JavaScript), así que la advertencia no implica una fuga;
se mantiene por diseño y queda documentada.

## 5. Bloqueadores (no ejecutado)

| Prueba | Motivo |
|---|---|
| Ver algoritmo JWT activo del proyecto | Requiere acceso al dashboard del proyecto. |
| Aplicar migración `20261111120000_fase01_dominio_rls.sql` | Requiere proyecto autorizado y aprobación expresa (`supabase db push --remote`). |
| Ejecutar `rls_dominio_test.sql` en Supabase | Mismo motivo; además requiere dos usuarios de prueba. |
| Registro/confirmación/login de usuarios A y B | Requiere proyecto con Auth configurado. |
| Persistencia tras recarga, aislamiento A/B en navegador | Depende de lo anterior. |
| Recuperación de contraseña | Requiere URLs de redirección configuradas en el proyecto. |

Instrucciones exactas para desbloquear: ver `docs/FASE_02_IMPLEMENTACION.md` §6.

## 6. Limitaciones

- Ninguna prueba de esta fase toca Supabase real; no se afirma conectividad ni RLS remoto.
- El stub de `auth` en PostgreSQL local no reproduce todo el esquema de Supabase.
- Sin límite de tasa en la API.

## 7. Sesión 2026-11-12 — verificación previa a la autorización

Alcance: solo lectura y pruebas locales. **No se aplicó ninguna migración, no se hizo ningún commit y no se desplegó en Render.** No se imprimió ningún valor de credencial.

### 7.1 Variables de entorno (paso 1)

| Archivo | Estado | Comprobación |
|---|---|---|
| `backend/.env` | ⛔ **No existe** en `AURORA_IA` | `find` sobre el proyecto y `.env*` no devuelve nada |
| `frontend/.env.local` | ⛔ **No existe** en `AURORA_IA` | Igual que arriba |
| `backend/.env.example`, `frontend/.env.example` | ✅ Presentes | Solo plantillas |

Los `.env` encontrados en otras carpetas de `GitHub\` pertenecen a otros proyectos y **no se han leído ni usado**.
Consecuencia: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY` no están disponibles para esta sesión. Si el archivo se creó en otra ruta, hay que moverlo a las rutas indicadas arriba.

### 7.2 Conectividad y JWT (paso 2)

- **Conectividad con Supabase: NO comprobada.** Sin `SUPABASE_URL` no hay endpoint al que llamar.
- **Configuración JWT en código** (verificada por lectura de `backend/app/config.py`, `backend/app/security/jwt_verifier.py`):
  - Algoritmos aceptados: solo `RS256` y `ES256` (vía JWKS). Un proyecto que solo use el secreto HS256 heredado rechazará todos los tokens.
  - Issuer por defecto: `{SUPABASE_URL}/auth/v1`. Audience por defecto: `authenticated`. JWKS: `{issuer}/.well-known/jwks.json`.
  - Claims obligatorios: `exp`, `iat`, `sub`, `iss`, `aud`.
- **Algoritmo activo en el proyecto remoto: NO verificado** (requiere ver *Settings → JWT signing keys* en el dashboard).

### 7.3 Esquema y RLS (paso 3, revisión estática)

Revisado `supabase/migrations/20261111120000_fase01_dominio_rls.sql` (225 líneas):

- 5 tablas (`academic_subjects`, `grade_entries`, `monthly_budgets`, `budget_expenses`, `tasks`), todas con `enable` y `force row level security`.
- `revoke all` a `anon`, `authenticated` y `public`; después, `select/insert/update/delete` solo para `authenticated`. `anon` no tiene grants ni políticas.
- Políticas `select/insert/update/delete` por tabla con `auth.uid() = user_id` (`using` y `with check` en update).
- Claves foráneas compuestas `(user_id, id)` para impedir referencias cruzadas entre usuarios.
- `set_updated_at` es `security invoker` con `search_path = ''`.

Observaciones (no bloqueantes):
- `user_id` tiene `default auth.uid()`. Si una inserción se hace sin sesión, `user_id` queda `NULL` y falla por `not null`, lo cual es el comportamiento deseado.
- Las tablas `budget_expenses` y `tasks` no tienen todavía endpoints; sus políticas se verifican igual.
- `supabase/tests/rls_dominio_test.sql` (231 líneas) no se ha ejecutado contra Supabase remoto. Requiere dos usuarios.

### 7.4 Pruebas locales ejecutadas hoy

| Prueba | Comando | Resultado |
|---|---|---|
| Suite backend | `backend\.venv\Scripts\python.exe -m pytest -q` | ✅ **90 passed, 1 warning** |
| Herramientas | `supabase --version`, `node --version`, `python --version` | ✅ Supabase CLI 2.48.3, Node v22.22.0, Python 3.12.10 |

### 7.5 Plan de migración (pendiente de autorización)

1. Confirmar que existe un proyecto Supabase **exclusivo de AURORA AI** (no reutilizar otro de la cuenta).
2. Crear `backend/.env` y `frontend/.env.local` con las URL y claves **publishable** (nunca `service_role`).
3. Comprobar en *Settings → JWT signing keys* el algoritmo activo. Si solo existe el secreto legado, decidir la migración a clave asimétrica antes de cualquier prueba de login.
4. Comprobar conectividad: `GET {SUPABASE_URL}/auth/v1/.well-known/jwks.json` debe devolver claves públicas.
5. **Pedir autorización expresa** para aplicar `20261111120000_fase01_dominio_rls.sql` (vía `supabase db push --remote` o SQL Editor, nunca ambos).
6. Tras aplicar: ejecutar las comprobaciones RLS dentro de transacciones revertibles, con dos usuarios de prueba A y B.
7. Pruebas de integración: registro/login real, persistencia tras recarga, aislamiento A/B (lectura, escritura y borrado cruzados deben fallar o devolver vacío).

### 7.6 Riesgos abiertos

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | Proyecto solo con secreto HS256 heredado: todos los tokens rechazados | Migrar a clave asimétrica antes de probar login; revisar `getClaims()` |
| R2 | Migración aplicada sin revisión de datos previos | Proyecto vacío y dedicado; migración idempotente en tablas (`if not exists`) pero las políticas **no** son idempotentes (`create policy` falla si ya existe) |
| R3 | Clave `service_role` expuesta por error | Solo claves publishable en `.env`; comprobar con `git check-ignore` |
| R4 | Sin límite de tasa en la API | Fuera del alcance de esta fase |
| R5 | Audience `authenticated` no confirmada en el proyecto real | Confirmar con un token real (claim `aud`) tras el primer login |

### 7.7 Estado

**Fase 02: NO COMPLETADA.** Bloqueada por: variables de entorno ausentes en el proyecto y autorización expresa para aplicar la migración en Supabase remoto.

Lo que el usuario debe hacer para desbloquear:
1. Colocar `backend/.env` y `frontend/.env.local` en `AURORA_IA` (copiando desde los `.env.example`).
2. Confirmar el algoritmo JWT activo.
3. Autorizar explícitamente la migración remota (indicando el método).
4. Proporcionar (o crear) dos usuarios de prueba A y B.
