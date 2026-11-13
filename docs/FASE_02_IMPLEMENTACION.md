# Fase 02 — Implementación (estado real)

## 1. Qué se hizo

- **Auditoría reproducible** (ver `PRUEBAS_FASE_02.md` §2): git limpio en `main` sin commits nuevos;
  suites locales en verde; dependencias del frontend instaladas con `npm ci`.
- **Corrección de seguridad menor**: sin token, la API responde 401 también sin configuración de
  Supabase (antes 503). Con prueba de regresión.
- **Docker**: imagen construida localmente y verificada en contenedor (health, 401 sin token).
- **Documentación**: esta fase y `PRUEBAS_FASE_02.md`.

No cambió ningún endpoint, ninguna migración ni la arquitectura. Por eso **no se modificó**
`docs/arquitectura-c4.html`: no hay un contenedor o una comunicación nueva que documentar.

## 2. Endpoints (sin cambios respecto a Fase 01)

| Método | Ruta | Autenticación |
|---|---|---|
| GET | `/api/health` | No |
| GET/POST | `/api/subjects` | Bearer |
| GET/PATCH/DELETE | `/api/subjects/{id}` | Bearer |
| GET/POST | `/api/subjects/{id}/grades` | Bearer |
| GET/PATCH/DELETE | `/api/grades/{id}` | Bearer |

## 3. Flujo de datos previsto (aún no verificado contra Supabase real)

```
React (supabase-js, solo Auth) → access_token
  → fetch /api/... con "Authorization: Bearer <JWT del usuario>"
  → FastAPI: valida firma JWKS, iss, aud, exp → AuthContext
  → PostgREST con el mismo JWT → RLS: auth.uid() = user_id
  → JSON solo con filas propias → React
```

Las partes "React → FastAPI → PostgREST → RLS" están probadas **sin red** (tests con JWKS local
y PostgREST simulado con `httpx.MockTransport`) y en PostgreSQL local. La parte remota no.

## 4. Decisiones

- **Sin mocks como prueba de integración**: los tests existentes siguen siendo unitarios; la
  integración real queda pendiente y no se declara.
- **Clave publishable en el build**: se pasa como `ARG` a la imagen porque Vite la incrusta. Es
  pública por diseño; nunca se pasa `service_role` ni secretos.
- **Algoritmo JWT**: el backend solo acepta RS256/ES256 por JWKS. La documentación oficial de
  Supabase indica que la configuración está en *Settings > JWT signing keys*, que el JWKS es
  `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` y que el issuer es
  `https://<ref>.supabase.co/auth/v1`. La audiencia por defecto `authenticated` **debe confirmarse** en el
  proyecto real (no aparece en la documentación leída).

## 5. Riesgos abiertos

1. Si el proyecto usa solo el secreto HS256 heredado, el backend rechazará todos los tokens. La
   migración oficial es *Migrate JWT secret* → crear clave asimétrica → rotar. Antes de rotar, el código
   que verifica con el secreto legado debe usar `supabase.auth.getClaims()`; la documentación indica
   también desactivar anon y service_role antes de revocar el secreto legado. **No se realiza sin autorización.**
2. La migración no se ha aplicado a ningún proyecto remoto.
3. Sin límite de tasa en la API.

## 6. Qué necesito del usuario para desbloquear la fase

1. **Crear o elegir un proyecto Supabase exclusivo para AURORA AI** en https://supabase.com/dashboard
   (no reutilizar otro proyecto de la cuenta).
2. **Copiar la Project URL y la clave publishable** desde *Project Settings → API*. Pegarlas en:
   - `backend/.env` → `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` (copiar de `backend/.env.example`).
   - `frontend/.env.local` → `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`.
   No enviar contraseñas, `service_role` ni claves secretas por el chat.
3. **Revisar el algoritmo de firma** en *Settings → JWT signing keys*. Si aparece solo el secreto
   legado, decidir si autorizas la migración a clave asimétrica.
4. **Autorizar explícitamente** la aplicación de la migración `20261111120000_fase01_dominio_rls.sql`
   (y el comando `supabase db push --remote` o el SQL Editor, pero no ambos).
5. **Crear dos usuarios ficticios** (A y B) con correos de prueba que controles, y confirmar si el
   proyecto exige confirmación por correo.
6. Confirmar en *Authentication → URL Configuration* la URL de desarrollo (`http://localhost:5173`).

Con eso, la siguiente sesión puede: confirmar la audiencia JWT real, aplicar la migración autorizada,
ejecutar las pruebas RLS en transacciones revertibles, y hacer el recorrido completo A/B en el navegador.

## 7. Siguiente paso

Fase 02 queda **pendiente de la conexión Supabase**. No se propone todavía la Fase 03 hasta que el
flujo real esté confirmado.
