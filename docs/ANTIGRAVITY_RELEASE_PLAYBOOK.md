# AURORA AI | Playbook de cierre con Google Antigravity

Este repositorio tiene AGENTS.md con reglas permanentes. Estado: MVP y CI existentes; despliegue publico, OpenRouter real e historial remoto aun sin validar. No afirmar finalizacion sin pruebas.

## 1. Iniciar Antigravity
Abrir carpeta local AURORA_IA. Revisar estado en PowerShell antes de tocar nada:

`git status --short`
`git branch --show-current`
`git log -5 --oneline`
`git fetch origin`

Conservar los archivos backend/.env y frontend/.env: contienen configuracion privada y NO deben sobrescribirse. No hacer reset --hard, clean -fd ni force push. El agente debe trabajar en una rama de feature separada y mostrar plan, diff, tests y evidencia.

### PROMPT MAESTRO PARA PEGAR AL AGENTE
Eres un ingeniero senior Full Stack + DevOps + QA. Lee AGENTS.md y docs/ANTIGRAVITY_RELEASE_PLAYBOOK.md, el dossier de fase 08A, Dockerfile, render.yaml, CI, codigo React y FastAPI. Objetivo: cerrar AURORA AI para una demostracion de CI/CD. Orden: audita, plantea pasos, implementa cambios pequenos, ejecuta backend pytest, frontend typecheck/build, Docker build/run y QA de navegador en 390, 768, 1366, 1440 y 1920 px. Verifica login, CRUD, dashboard, pagina del copiloto y widget; muestra capturas y resultados sin datos privados. No modifiques Supabase remoto, claves, Render o main sin mi autorizacion especifica. No uses Supabase CLI. No afirmes IA real por un mock ni un despliegue real por un healthcheck.

## 2. Gate A - integridad y pruebas locales
- Inspeccionar estado actual de Git y ramas. El PR #1 contiene MVP y el PR #2 contiene CI/CD. main aun estaba en commit inicial al revisar.
- Backend: entrar en backend, ejecutar `.\\.venv\\Scripts\\python.exe -m pytest -q` si existe entorno; si no, configurar Python 3.12. Ejecutar los tres CLI del SENA.
- Frontend: entrar en frontend; `npm ci`, `npm run typecheck`, `npm run build`.
- Docker: ejecutar build del Dockerfile desde la raiz con build args VITE_SUPABASE_URL y VITE_SUPABASE_PUBLISHABLE_KEY publicos. Ejecutar contenedor con APP_ENV=production, PERSISTENCE_BACKEND=supabase, DEMO_MODE=false y SUPABASE_URL/KEY publicos.
- Smoke: `GET /api/health` estado 200, `GET /api/modo` produccion+supabase, `GET /` contiene assets JS, `GET /api/subjects` sin JWT 401. Este smoke NO verifica Supabase real ni IA.
- Nuevas guardas rechazan producción con SQLite, demo, Supabase HTTP o faltante. CI ejecuta build y smoke Docker sin secretos.
- Los VITE_* se compilan en bundle PUBLICO: solamente URL y publishable key. OPENROUTER_API_KEY solo en runtime backend.

## 3. Gate B - Supabase fase 08A (manual, autorizado)
1. Confirmar Dashboard proyecto AURORA_IA, ref dsldzrtgzrthifsxmtwu. Hay otras cuentas de Supabase: no inferir proyecto por sesion CLI.
2. Inspeccionar si ya se aplico `supabase/migrations/20261113120000_fase08a_conversaciones_ia.sql`. La captura Success. No rows returned no confirma privilegios.
3. Aplicar SQL revisado en SQL Editor SOLO si procede. Nunca ejecutar tests de stub/auth local en Supabase remoto.
4. Ejecutar `supabase/sql_editor/08a_verificar_conversaciones.sql`. Exigir 20 filas, todas ok=true. Guardar evidencia de solo lectura.
5. Con usuarios ficticios A/B: crear, listar, recargar, renombrar, borrar conversaciones propias; asegurar que B no puede leer ni modificar objetos de A. No tocar los 48 registros de demo.
6. Solo tras aprobacion activar AI_CONVERSACIONES_PERSISTENTES=true y repetir pruebas de pagina/widget, idempotencia y cambio de usuario. Cuotas y retencion para uso abierto siguen siendo consideraciones de producto.

## 4. Gate C - OpenRouter real
1. REVOCAR clave anterior expuesta. Configurar NUEVA OPENROUTER_API_KEY solo en backend/.env local y en Render Runtime sin incluirla en Git o capturas.
2. Confirmar slug OPENROUTER_MODEL en catalogo oficial. Poner COPILOT_PROVIDER=openrouter; prohibido simulado en produccion.
3. Con JWT de usuario ficticio validar GET /api/copilot/estado (configurado y no simulado). Luego una pregunta real de consumo minimo y comprobar POST /api/copilot/chat, modelo, contenido, tokens/costo y logs sin secretos.
4. Comprobar contexto Academico/Finanzas/Tareas con calculos del backend, acceso solamente a datos propios, una solicitud al modelo por mensaje y reintentos de persistencia sin duplicar la consulta.
5. Los limites del backend son por proceso y en memoria; no tratarlos como cuotas distribuidas robustas.

## 5. Gate D - QA responsive y accesibilidad
Inspeccionar en navegador real o Playwright: 390x844, 768x1024, 1366x768, 1440x900 y 1920x1080. Revisar login, dashboard, academia, finanzas, tareas, chat completo y widget; sin scroll horizontal, controles tapados, errores JS ni composer fuera del viewport. Probar teclado, Escape, loading, reconexion, logout/login A y B en una sola pestaña. Capturas sin credenciales/correos/identificadores.

## 6. Gate E - desplegar un UNICO Web Service Docker Render
- Crear Web Service Render Docker con Dockerfile en raiz y contexto ".". Usar rama aprobada; primero despliegue manual con autoDeploy deshabilitado.
- Variables publicas: APP_ENV=production, PERSISTENCE_BACKEND=supabase, DEMO_MODE=false, SUPABASE_URL=https://dsldzrtgzrthifsxmtwu.supabase.co, SUPABASE_PUBLISHABLE_KEY, JWT_AUDIENCE=authenticated, CORS_ORIGINS vacio, VITE_SUPABASE_URL igual a SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY, VITE_API_BASE_URL vacio.
- Variables privadas runtime: OPENROUTER_API_KEY nueva, OPENROUTER_MODEL slug confirmado; COPILOT_PROVIDER=openrouter. Mantener AI_CONVERSACIONES_PERSISTENTES=false hasta gate B.
- Render traduce environment variables a Docker build args, que Dockerfile recibe con ARG. Si cambias VITE_*, elegir Save, rebuild and deploy; no basta reiniciar runtime.
- Comprobar URL publica /, /api/health, /api/modo, 401 sin token, login real, CRUD, RLS A/B, historial y consulta OpenRouter. Guardar SHA, build logs saneados, salida navegador, costos y evidencia. No confundir health status=ok con integracion completada.

## 7. Gate F - CD y clase
- Revisar PR #1, PR #2 y este PR; integrar respetando dependencias y sin force push. Establecer revision/CI antes de merges.
- GitHub Actions hace Pytest, CLI SENA, TypeScript, Vite, Docker y smoke local. No contacta Supabase ni OpenRouter.
- `.github/workflows/cd-render.yml` invoca deploy hook solo despues de CI exitosa de push a main y al configurar secreto RENDER_DEPLOY_HOOK_URL. NO habilitar antes de probar deploy manual, rollback y permisos.
- CI verde no equivale a deploy aprobado: verificar resultado en Render, release SHA y smoke publico.
- Para clase mostrar Git -> PR -> CI -> Docker -> Render -> Supabase/OpenRouter, explicar multistage build, un solo servicio web, seguridad, costos, cold starts y rollback.

## Reporte obligatorio
Entregar tabla con estado PASS / FAIL / BLOQUEADO por gate A-F, comandos reales ejecutados, capturas saneadas, logs, archivos cambiados, pruebas y riesgos. Si no hay acceso a Render/OpenRouter/SQL Editor, declararlo BLOQUEADO, nunca inventar resultados.

Referencias: docs/ESTADO_MVP_TRAZABILIDAD.md; docs/FASE_08A_IMPLEMENTACION.md; docs/PRUEBAS_FASE_08A.md; supabase/sql_editor/08a_verificar_conversaciones.sql; AGENTS.md.
