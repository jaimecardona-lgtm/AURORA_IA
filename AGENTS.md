# AURORA AI — Reglas de trabajo para Google Antigravity

Este archivo es una regla permanente del repositorio. Leelo antes de editar y consulta `docs/ANTIGRAVITY_RELEASE_PLAYBOOK.md`.

## Proposito del producto y arquitectura
- Aplicacion de estudiantes: React 19 + TypeScript + Vite; FastAPI + Python 3.12; Supabase Auth + PostgreSQL / PostgREST + RLS; AURORA Copilot conectado a OpenRouter (solo lectura).
- `Dockerfile` multietapa: Vite se compila en Node 22, FastAPI sirve la SPA estatica y `/api/*` desde una unica imagen. Render aloja **un** Web Service. No dividir el despliegue en varios servicios sin una justificacion.
- La aplicacion conserva tres motores de dominio (academico, finanzas, tareas), dashboard, widget de chat y pagina completa con estado compartido. Los calculos numericos los hace el backend, no el LLM.
- SQL de dominio 01 y 06 ya fue aplicado; 08A debe verificarse en Supabase remoto mediante 20/20 comprobaciones antes de activar historial persistente.

## Seguridad y datos (obligatorio)
1. No ejecutar `supabase login`, `supabase link`, `supabase db push`, `supabase db reset` ni scripts de test SQL con stub sobre la base remota. Usar exclusivamente SQL Editor del proyecto AURORA_IA (`dsldzrtgzrthifsxmtwu`) para operaciones revisadas manualmente.
2. Nunca borrar o reseedear los 48 registros DEMO-AURORA existentes. Prohibido usar `service_role` en CRUD o en frontend. Trabajar con JWT por usuario y politicas RLS.
3. Nunca imprimir, mostrar en terminal, pantallas, logs, chat, PR ni commits las claves, contrasenas, JWT o contenidos financieros personales. `backend/.env` y `frontend/.env` contienen configuracion local: NO sobrescribirlos, compartirlos ni agregarlos a Git.
4. Una clave OpenRouter antigua fue expuesta: requerir revocacion y NUEVA clave antes de llamar IA real. `COPILOT_PROVIDER=simulado` no se admite en produccion; el estado del proveedor se debe comprobar, no suponer.
5. Ninguna publicacion, merge a `main`, ejecucion SQL remota, cambio de permisos, activacion de CD ni rotacion de credenciales sin autorizacion humana puntual. Primero generar plan y diff.
6. No cambiar `AI_CONVERSACIONES_PERSISTENTES=false` hasta comprobar 20/20 `ok=true`, pruebas CRUD y RLS A/B de historial remoto.
7. No poner claves secretas en `VITE_*`; las variables `VITE_*` acaban en el JavaScript publico. La clave publishable de Supabase es publica y si puede estar alli.

## Metodologia y criterios de cierre
- Comprender -> acotar -> disenar -> implementar -> probar -> verificar visualmente -> documentar -> versionar.
- Antes de empezar: `git status --short`, `git branch --show-current`, `git log -5 --oneline`. No hacer `git reset --hard`, `git clean -fd`, rebase ni force push por conveniencia.
- Los PR #1 y #2 son trabajo previo; mantener ramas y trazabilidad. Trabajar en rama nueva; no atribuir pruebas simuladas a ejecuciones reales.
- Backend: `python -m pytest -q` en `backend/`; frontend: `npm ci`, `npm run typecheck`, `npm run build` en `frontend/`; CLI SENA: tres programas. Docker: build y smoke en `/api/health`, `/api/modo`, `/`, autorizacion.
- Visual: usar navegador real o `/browser`; revisar 390x844, 768x1024, 1366x768, 1440x900 y 1920x1080, sin overflow, botones tapados ni errores JS. Probar login, logout, widget, pagina de chat, scroll, editor y reintentos.
- Produccion: acreditar URL real de Render, commit SHA, pruebas HTTP, login de cuenta ficticia, CRUD, RLS A/B, historial y respuesta de OpenRouter con consumo medido. No afirmar listo por `HTTP 200 /api/health` solamente.
- Usar Conventional Commits. Informar archivos modificados, pruebas ejecutadas, evidencia y pendientes; nunca presentar mocks como integracion real.

## Referencias
- `docs/ESTADO_MVP_TRAZABILIDAD.md`
- `docs/FASE_08A_IMPLEMENTACION.md`
- `docs/PRUEBAS_FASE_08A.md`
- `docs/ANTIGRAVITY_RELEASE_PLAYBOOK.md`
- `supabase/sql_editor/08a_verificar_conversaciones.sql`
- `.github/workflows/ci.yml`, `render.yaml`, `Dockerfile`
