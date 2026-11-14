# AURORA AI — Intelligent Student Workspace

Plataforma académica del proyecto SENA: asignaturas y notas, finanzas personales, tareas, dashboard y
copiloto de IA (React → Supabase Auth → FastAPI → Supabase PostgreSQL con RLS → React).

> **Estado de preparación para despliegue (14-11-2026):** La integración del dominio con Supabase
> fue comprobada en Fase 07C (59/59 pruebas). El usuario ejecutó en el proyecto correcto `AURORA_IA`
> (`dsldzrtgzrthifsxmtwu`) el verificador SQL de Fase 08A con **20/20 filas `ok=true`**.
> Esto verifica la estructura, políticas, grants y disparadores; **todavía no prueba el
> aislamiento real de conversaciones con usuarios A/B**. El agente OpenRouter real y el
> despliegue público a Render también siguen sin verificarse. `AI_CONVERSACIONES_PERSISTENTES`
> permanece `false` por seguridad hasta realizar QA multiusuario. La última CI del PR #4
> aprobó backend, frontend y smoke Docker. No confundir estas pruebas con producción validada.
> Ver [guía de cierre](docs/RELEASE_GATES_SUPABASE_OPENROUTER_RENDER.md).

## Estructura

```
frontend/              React + TypeScript + Vite (Auth con supabase-js; datos vía FastAPI)
  e2e/                 Pruebas de humo de la interfaz (Playwright, opcionales)
backend/               FastAPI: validación JWT, DTO, repositorios PostgREST, servicios, REST
  app/core/            Motores Python puros: calificaciones, presupuesto (COP), tareas
  sena_cli/            Programas CLI de los motores (evidencia SENA; ejecutables en VS Code)
  app/                 API (api/), seguridad (security/), acceso a datos (repositories/)
  tests/               Pytest: motores, JWT, API, cliente PostgREST, CLI
supabase/
  migrations/          Migraciones SQL versionadas (tablas + RLS + grants)
  tests/               Pruebas SQL de RLS y stub para PostgreSQL local
docs/                  Arquitectura C4, estado inicial, implementación y pruebas de la fase
Dockerfile             Imagen única: compila el frontend y sirve API + SPA en el mismo origen
render.yaml            Blueprint de Render (Web Service Docker). No desplegado.
```

## Requisitos

- Node.js 22+ y npm.
- Python 3.12 (la imagen Docker usa 3.12).
- Un proyecto de Supabase (gratuito) para la conexión real.
- Opcional: Docker, PostgreSQL 16+ local para ejecutar las pruebas RLS sin Supabase.

## 1. Crear el proyecto de Supabase y las claves (de forma segura)

1. En https://supabase.com crea un proyecto. Guarda la contraseña de la base de datos en un gestor de contraseñas; **no** la pegues en el repositorio ni en el chat.
2. En **Project Settings → API** copia:
   - **Project URL** → `SUPABASE_URL` y `VITE_SUPABASE_URL`.
   - **Publishable key** (clave pública) → `SUPABASE_PUBLISHABLE_KEY` y `VITE_SUPABASE_PUBLISHABLE_KEY`.
   - **No copies** la clave `service_role` ni la clave secreta. Esta aplicación no debe usarlas nunca.
3. En **Authentication → Sign In / Providers** deja habilitado *Email*. Para pruebas puedes desactivar la confirmación de correo; si la mantienes, la app lo indica al registrarse.
4. En **Authentication → JWT Signing Keys** (o la sección equivalente del panel) usa **claves de firma asimétricas** (RS256 o ES256). El backend valida firmas con el JWKS público (`/auth/v1/.well-known/jwks.json`) y **rechaza HS256** a propósito. Si tu proyecto usa solo el secreto HS256 heredado, hay que migrar a claves asimétricas antes de que el backend acepte los tokens.
5. Crea los archivos locales a partir de los ejemplos (nunca los subas a Git; `.gitignore` ya los excluye):
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env.local
   ```
   Edita ambos con los valores de tu proyecto.

## 2. Aplicar la migración y verificar RLS

En el **SQL Editor** de Supabase:

1. Pega y ejecuta `supabase/migrations/20261111120000_fase01_dominio_rls.sql`.
2. Pega y ejecuta `supabase/tests/rls_dominio_test.sql`. Debe terminar sin errores y mostrar los mensajes `OK:`. Todo corre dentro de una transacción con `ROLLBACK`, así que no deja datos.

Para este proyecto, con múltiples cuentas Supabase, **no usar `supabase link`, `db push` ni `db reset`**. Se requiere SQL Editor del proyecto verificado y revisión explícita de cualquier migración pendiente.

## 3. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   |   source .venv/bin/activate  (Linux/macOS)
pip install -r requirements-dev.txt
python -m pytest -q               # pruebas unitarias y de API (sin red)
uvicorn app.main:app --reload --port 8000
```

- Salud: `GET http://127.0.0.1:8000/api/health`
- Documentación interactiva: `http://127.0.0.1:8000/api/docs`

## 4. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (las llamadas /api se reenvían a :8000)
npm run build      # typecheck + build de producción en frontend/dist
```

## 5. Motores y programas CLI (evidencia SENA)

Desde `backend/`:

```bash
python sena_cli/calificaciones.py 4.5 3.0 2.9          # promedio y aprobación (escala 0–5, aprueba >= 3.0)
python sena_cli/presupuesto.py --ingreso 2000000 --ahorro 300000 \
  --gasto "Arriendo:600000:fijo" --gasto "Mercado:250000:variable"
python sena_cli/tareas.py "Entregar AA2:1" "Leer guía:3:completada"
```

Se ejecutan sin base de datos ni servidor.

## 6. Docker (imagen única)

```bash
docker build -t aurora-ai \
  --build-arg VITE_SUPABASE_URL=https://TU-PROYECTO.supabase.co \
  --build-arg VITE_SUPABASE_PUBLISHABLE_KEY=TU_CLAVE_PUBLICA \
  .
docker run --rm -p 8000:8000 -e SUPABASE_URL=https://TU-PROYECTO.supabase.co \
  -e SUPABASE_PUBLISHABLE_KEY=TU_CLAVE_PUBLICA aurora-ai
```

Las variables `VITE_*` quedan dentro del JavaScript público. Solo pasa claves **públicas**.

## 7. Render (pendiente de despliegue)

`render.yaml` define un Web Service Docker. Para crearlo:
1. En Render: **New → Blueprint** y selecciona este repositorio.
2. Completa los valores marcados `sync: false` en el panel (URL y clave pública). **No** los escribas en el archivo.
3. Tras el despliegue, comprueba `https://<tu-servicio>.onrender.com/api/health`.

Esta fase **no** despliega nada. El despliegue se hará cuando las pruebas locales pasen y lo indiques.

## Seguridad

- El navegador solo usa la clave pública y el token de usuario. Los datos van por FastAPI.
- FastAPI valida el JWT (firma, emisor, audiencia, expiración) y propaga el token del usuario a PostgREST. Así RLS aplica `auth.uid() = user_id`. No hay bypass ni `service_role`.
- Las filas referencian asignaturas con claves foráneas compuestas `(user_id, id)`, por lo que no se puede asociar una nota a la asignatura de otro usuario.
- OpenRouter **no** está activo en esta fase.
