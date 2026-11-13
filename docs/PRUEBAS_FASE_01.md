# Pruebas — Fase 01

Fecha de verificación: 2026-11-11 (Windows 11). Todas las salidas son reales y se copiaron de la
ejecución; ninguna se redactó de memoria.

**Resumen**

| Ámbito | Resultado |
|---|---|
| Pruebas pytest (motores, JWT, API, PostgREST, CLI) | ✅ 89 superadas |
| Build del frontend (`tsc` estricto + Vite) | ✅ Compila |
| CLI SENA (calificaciones, presupuesto, tareas) | ✅ Funcionan |
| RLS sobre PostgreSQL 18 local | ✅ 23 comprobaciones superadas |
| UI de acceso (Chrome, Auth inalcanzable) | ✅ 9/9 |
| UI académica (sesión simulada, API interceptada) | ✅ 12/12 (no es integración real) |
| Login/registro contra **Supabase real** | ⛔ **No ejecutado: no hay proyecto ni credenciales** |
| Imagen Docker | ⛔ **No construida: daemon Docker inactivo** |
| Despliegue en Render | ⛔ **No realizado (intencional)** |

---

## 1. Pruebas automáticas del backend

Comando (desde la raíz):
```bash
backend\.venv\Scripts\python.exe -m pytest -q backend
```
Salida:
```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
89 passed, 1 warning in 2.75s
```

Cobertura por archivo:

| Archivo | Qué prueba |
|---|---|
| `test_grades_engine.py` | Notas válidas e inválidas (rango, booleanos, NaN, ∞), redondeo, promedio, umbral 3.0 exacto. |
| `test_budget_tasks_engines.py` | Resumen COP, gastos inválidos, prioridades 1..3, orden de tareas. |
| `test_jwt_verifier.py` | Token válido; expirado; firma de otra clave; `iss` y `aud` incorrectos; `sub` no UUID; claim ausente; **HS256 y `alg=none` rechazados**; token malformado; **JWKS inaccesible → 503**. |
| `test_api.py` | Sin token, esquema incorrecto, token expirado → 401; campo `user_id` en el cuerpo → 422; nota fuera de rango → 422; UUID inválido → 422; duplicado → 409; inexistente → 404; **otro usuario no ve ni modifica datos**; CRUD completo con promedio; sin configuración → 503. |
| `test_postgrest_client.py` | Envía el JWT del usuario y la clave pública (no `service_role`); traduce 401/403/404/409/422/5xx; caída de red → 503. |
| `test_cli_sena.py` | Los tres CLI ejecutan y devuelven los códigos de salida correctos. |

> El único aviso es una advertencia de dependencia (`starlette` / `TestClient`), sin efecto en el resultado.

## 2. Build del frontend

```bash
cd frontend
npm install
npm run build
```
Salida (últimas líneas):
```
> aurora-ai-frontend@0.1.0 build
> tsc --noEmit && vite build
✓ 66 modules transformed.
dist/index.html                   0.52 kB │ gzip:  0.32 kB
dist/assets/index-…css            8.18 kB │ gzip:  2.62 kB
dist/assets/index-….js          229.88 kB │ gzip: 72.46 kB
✓ built in 289ms
```
`package-lock.json` está generado y versionable. Las versiones están fijadas con `--save-exact`.

## 3. Programas CLI de la evidencia SENA

```bash
cd backend
python sena_cli/calificaciones.py 4.5 3.0 2.9
python sena_cli/presupuesto.py --ingreso 2000000 --ahorro 300000 --gasto "Arriendo:600000:fijo" --gasto "Mercado:250000:variable"
python sena_cli/tareas.py "Entregar AA2:1" "Leer guia:3:completada" "Revisar correo:2"
```
Salida real:
```
Notas: 4.50, 3.00, 2.90
Promedio: 3.47
Estado: APROBADO
exit=0

Ingreso: $ 2,000,000.00 COP
Meta de ahorro: $ 300,000.00 COP
Gastos fijos: $ 600,000.00 COP
Gastos variables: $ 250,000.00 COP
Disponible para gastar: $ 1,700,000.00 COP
Saldo final: $ 1,150,000.00 COP
exit=0

1. [P1] Entregar AA2 (pendiente)
2. [P2] Revisar correo (pendiente)
3. [P3] Leer guia (completada)
exit=0
```
Nota inválida (`6`): mensaje `Error: La nota debe estar entre 0 y 5.` y código de salida **2**.

## 4. Pruebas RLS (PostgreSQL 18 local)

**Limitación importante:** se ejecutaron en un PostgreSQL 18 local con un *stub* del esquema `auth`
(`supabase/tests/local/00_stub_auth_postgres_local.sql`). Eso reproduce `auth.uid()` y los roles
`anon`/`authenticated`. **No sustituye** la ejecución en el proyecto Supabase real, que debe hacerse
(ver §7).

Procedimiento:
```powershell
psql -h 127.0.0.1 -p 5433 -U postgres -d postgres -c "create database aurora_test;"
psql -h 127.0.0.1 -p 5433 -U postgres -d aurora_test -f supabase/tests/local/00_stub_auth_postgres_local.sql
psql -h 127.0.0.1 -p 5433 -U postgres -d aurora_test -f supabase/migrations/20261111120000_fase01_dominio_rls.sql
psql -h 127.0.0.1 -p 5433 -U postgres -d aurora_test -f supabase/tests/rls_dominio_test.sql
```
Resultado (recreando la base desde cero):
```
stub=0
migracion=0
rls_exit=0
OK lines: 23
FALLO lines: 0
```
Comprobaciones superadas (mensajes `OK:` reales):
- A ve sus 2 asignaturas; `user_id` se asigna automáticamente a A.
- A ve su nota creada.
- Nota 5.01 y -0.1 rechazadas por CHECK (0–5).
- A no puede reasignar su asignatura a B (WITH CHECK).
- A no puede duplicar asignatura (índice único por usuario).
- **B NO ve asignaturas ni notas de A.**
- **B no puede modificar ni borrar asignaturas de A** (UPDATE/DELETE afectan 0 filas).
- **B no puede insertar filas con `user_id` de A.**
- **B no puede crear nota apuntando a la asignatura de A** (FK compuesta).
- B ve solo su propia nota.
- **anon** no puede leer ni insertar en asignaturas, notas ni tareas (sin grant).
- Sesión `authenticated` sin `sub` no ve filas y no puede insertar.
- B no ve ni puede crear tareas de A.
- Prioridad 4 rechazada por CHECK (1..3).

## 5. Pruebas de interfaz (Chrome real, Playwright)

Se levantaron dos instancias de FastAPI que sirven dos builds del frontend fuera del repositorio:
una **sin** configuración de Supabase y otra con URL **ficticia**, para la que el proveedor no responde.

### 5.1 Acceso (`frontend/e2e/smoke_ui_sin_supabase.py`)
```
PASS sin config: muestra 'Configuración pendiente'
PASS sin config: sin errores de JS
PASS sin config (390px): sin scroll horizontal
PASS con config: formulario 'Inicia sesión' visible
PASS con config: error controlado al no poder contactar Auth | No hay conexión con el servicio de autenticación.
PASS con config: sin excepciones no capturadas
PASS validación cliente: correo inválido
PASS modo recuperar muestra título
PASS login (360px): sin scroll horizontal
TOTAL 9 | OK 9 | FALLIDOS 0
```

### 5.2 Módulo Académico (`frontend/e2e/smoke_academico_simulado.py`)
> **Sesión simulada y API interceptada en el navegador.** Valida la lógica de la interfaz; **no**
> prueba Supabase ni FastAPI reales.
```
PASS sesión simulada: entra al módulo Académico
PASS crear asignatura: aparece en la lista
PASS crear asignatura: estado vacío de notas visible
PASS validación cliente: nota 6 rechazada
PASS promedio calculado: 3.25 para notas 4.5 y 2.0 | 3.25
PASS estado del promedio: Aprobado
PASS tabla: 2 notas listadas
PASS recarga: notas se recuperan del servidor
PASS académico (360px): sin scroll horizontal
PASS cerrar sesión: vuelve a la pantalla de acceso
PASS todas las peticiones llevaron Bearer
PASS sin excepciones no capturadas
TOTAL 12 | OK 12 | FALLIDOS 0
```

**Errores encontrados y corregidos por estas pruebas:**
- *Cerrar sesión sin red no salía de la cuenta.* `signOut` global conserva la sesión local si no hay
  conexión. Corregido con respaldo a `scope: 'local'`.
- *Desbordamiento horizontal en 360px.* El `nav` del shell tomaba el ancho del contenido. Corregido con `minmax(0, 1fr)`.

### 5.3 Capturas
Las capturas se generaron en el scratchpad de la sesión (no se versionan). Se revisaron visualmente:
pantalla de acceso con error controlado, módulo académico en móvil con promedio y tabla.

## 6. Pruebas de sistema que faltaron o no se ejecutaron

| Prueba | Estado | Motivo |
|---|---|---|
| Login, registro y recarga con **cuenta real de Supabase** | ⛔ Pendiente | No hay proyecto ni credenciales de prueba. No se pidieron contraseñas en el chat. |
| Consultas de notas con **JWT real** de Supabase | ⛔ Pendiente | Depende del punto anterior. |
| Validación de firma contra el **JWKS real** | ⛔ Pendiente | Solo se probó con JWKS simulado (par RSA local) y con un host inalcanzable. |
| RLS en el Postgres de **Supabase** | ⛔ Pendiente | Se probó en PostgreSQL 18 local con stub de `auth`. |
| `docker build` y `docker run` | ⛔ Pendiente | El daemon de Docker Desktop no estaba activo. Se verificó sintaxis del Dockerfile por lectura, no por construcción. |
| Despliegue en Render y `/api/health` público | ⛔ Intencionalmente no realizado | El prompt indica desplegar solo cuando las pruebas locales pasen y se indique. |
| Pruebas unitarias del frontend | ⛔ No incluidas | Se cubrió con compilación estricta y pruebas de humo. |
| Verificación de que el backend arranca | ✅ | `uvicorn app.main:app` respondió a health, SPA, 401 sin token, 401 con token malformado y 404 en rutas `/api` desconocidas. |

Smoke test del servidor (salida real):
```
HEALTH 200 {"status":"ok","supabase_configurado":true,"version":"0.1.0"}
ROOT 200 ctype=text/html; charset=utf-8 hasRoot=True
SPA_DEEP 200
NOAUTH 401
BADTOKEN 401
API_UNKNOWN 404
DOCS 200
```
La prueba de recorrido de ruta (`/..%2F..%2FREADME.md`) devolvió el `index.html` del fallback
(526 bytes), no el README (11 bytes): no hay fuga de archivos fuera de `frontend/dist`.

## 7. Cómo completar la verificación contra Supabase real

Con un proyecto creado (ver README §1 y §2):
1. Ejecutar la migración y `supabase/tests/rls_dominio_test.sql` en el **SQL Editor** de Supabase. Debe mostrar 23 mensajes `OK:` y ningún `FALLO`.
2. Crear dos cuentas de prueba con correo (A y B), iniciar `uvicorn` con `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` reales, e `npm run dev`.
3. Con A: crear asignatura, agregar nota, recargar, confirmar datos, cerrar sesión.
4. Con B: confirmar que no aparecen las asignaturas ni notas de A.
5. Registrar los resultados en este archivo, con fecha y salida real.

## 8. Riesgos residuales

- La validación contra JWKS real podría fallar si el proyecto usa HS256 heredado (ver README §1.4).
- El stub de `auth` no replica todos los detalles del esquema real de Supabase.
- Sin límite de tasa en la API.
