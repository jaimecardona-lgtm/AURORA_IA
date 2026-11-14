# AURORA AI · Taller CI/CD y despliegue seguro con Render

Fecha de preparación: 13-11-2026. Esta guía NO certifica que Render esté desplegado, que OpenRouter funcione, ni que SQL 08A esté validado.

## 1. Arquitectura de bajo costo
React/TypeScript/Vite se compila en una etapa `node:22-alpine` de Docker. El resultado `dist/` se copia a una segunda etapa `python:3.12-slim`; FastAPI sirve tanto los archivos estáticos como `/api/*` en el mismo origen HTTP. **Una imagen de contenedor, un Web Service de Render y un dominio.** No se ejecutan dos contenedores en producción; Supabase (Auth, PostgreSQL y PostgREST) y OpenRouter son servicios administrados externos.

Esto economiza instancias, no reduce a cero los costos de Supabase, tokens de IA, ancho de banda o los límites de Render. También acopla el escalado de frontend y backend: adecuado para un MVP docente, no universal para cualquier carga.

## 2. Diferenciar CI de CD
**CI**: `.github/workflows/ci.yml` corre Pytest, tres CLI del SENA, TypeScript, Vite y una construcción Docker sin credenciales, en cada push/PR. No contacta a Supabase ni OpenRouter.

**CD**: `.github/workflows/cd-render.yml` se activa tras CI EXITOSA de la rama `main`, exclusivamente si se configura el secreto `RENDER_DEPLOY_HOOK_URL` en GitHub. Si no hay secreto, omite el despliegue. Render reconstruye la imagen; un CI verde NO prueba automáticamente la integración real de SQL/RLS/IA. Para seguridad, introducir primero el deploy manual en el panel; habilitar CD solo después de probar el servicio.

## 3. Punto de partida comprobado
- PR #1 `feat/aurora-mvp-trazabilidad` estaba abierto al comenzar este taller; `main` conserva commit inicial. **No seleccionar `main` para el primer despliegue hasta fusionar el PR revisado**.
- 262 pruebas de backend y 59 verificaciones de integración 07C reportadas; el CI de GitHub para el PR #1 aprobó.
- El copiloto 07C usó proveedor simulado, prohibido intencionalmente bajo `APP_ENV=production`.
- Persistencia 08A: **exigir** 20/20 validaciones del SQL editor remoto; no asumir lista por mensaje «Success».
- Clave anterior OpenRouter estuvo expuesta: revocar y rotar antes de probar.
- No duplicar semilla de 48 registros. No ejecutar `supabase link`, `db push`, `db reset` en este proyecto.

## 4. Preflight local (PowerShell)
```powershell
git status --short
git branch --show-current
docker version
docker build -t aurora-ai:local --build-arg VITE_SUPABASE_URL=https://dsldzrtgzrthifsxmtwu.supabase.co --build-arg VITE_SUPABASE_PUBLISHABLE_KEY=TU_CLAVE_PUBLICA .
docker run --rm -p 8000:8000 -e APP_ENV=production -e PERSISTENCE_BACKEND=supabase -e SUPABASE_URL=https://dsldzrtgzrthifsxmtwu.supabase.co -e SUPABASE_PUBLISHABLE_KEY=TU_CLAVE_PUBLICA -e COPILOT_PROVIDER=openrouter aurora-ai:local
```
En otra terminal: `Invoke-RestMethod http://127.0.0.1:8000/api/health` y comprobar `http://127.0.0.1:8000/`. El estado de salud indica configuración, **no** garantiza conexión real a la base ni una respuesta de IA. No copiar claves en grabaciones ni capturas. Las claves publishable son públicas; **no** usar `service_role`.

## 5. Verificar Supabase antes de habilitar historial
1. Abrir Supabase Dashboard y confirmar exactamente proyecto `AURORA_IA`, referencia `dsldzrtgzrthifsxmtwu`.
2. Leer migración `supabase/migrations/20261113120000_fase08a_conversaciones_ia.sql`. Verificar si ya se aplicó; ejecutar **solo si procede** en SQL Editor.
3. Ejecutar `supabase/sql_editor/08a_verificar_conversaciones.sql` (solo lectura). Guardar evidencia de **20 filas `ok=true`**.
4. En dos cuentas de prueba controladas, probar historial tras recargar, cambiar cuenta, borrar y confirmar bloqueo de accesos cruzados.
5. Solo entonces configurar `AI_CONVERSACIONES_PERSISTENTES=true`. Mientras tanto `false`.

## 6. Configuración de Render
Crear un único Web Service `Docker` desde el repositorio y la rama de publicación revisada (para demostración controlada puede usarse una rama aprobada); ruta `./Dockerfile`, contexto `.`. También existe `render.yaml`, que requiere revisar compatibilidad de build args con la configuración de Render.

Variables runtime:
- `APP_ENV=production`
- `PERSISTENCE_BACKEND=supabase`
- `DEMO_MODE=false`
- `SUPABASE_URL=https://dsldzrtgzrthifsxmtwu.supabase.co`
- `SUPABASE_PUBLISHABLE_KEY` = clave pública del proyecto
- `JWT_AUDIENCE=authenticated`
- `CORS_ORIGINS=` vacío (misma procedencia)
- `COPILOT_PROVIDER=openrouter`
- `OPENROUTER_API_KEY` = NUEVA clave secreta, solo entorno del servicio
- `OPENROUTER_MODEL` = identificador actual confirmado
- `AI_CONVERSACIONES_PERSISTENTES=false` hasta QA 08A

**En tiempo de build**: `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY` deben llegar efectivamente como Docker `ARG` a `npm run build`. Son variables públicas y se incorporan al bundle; no basta con definirlas únicamente en el entorno de ejecución si Render no las reenvía al build. Revisar los build logs y validar el login en navegador; utilizar la opción Build Arguments de la plataforma o configurar la entrega de estos ARG según documentación vigente. `VITE_API_BASE_URL` vacío para mismo origen.

Puerto: `PORT` de Render o 8000 local. Health Check: `/api/health`.

## 7. Pruebas obligatorias de la URL pública
- `GET /` entrega HTML y carga SPA; recargar ruta interna mantiene navegación.
- `GET /api/health` retorna HTTP 200 y `supabase_configurado=true`; esto NO sustituye prueba autenticada.
- `GET /api/modo` devuelve `produccion` + `supabase`, no demo.
- Registro/login de cuenta de prueba y sesión válida; dashboard, académicas, finanzas y tareas recuperan datos propios.
- Dos cuentas distintas no comparten registros ni conversaciones; negar acceso cruzado.
- Consulta de OpenRouter real, con clave nueva y modelo válido: verificar respuesta, gasto y ausencia de secretos en logs.
- Navegación móvil y revisión de consola del navegador; latencia y cold start de plan gratuito.
- Probar rollback: volver a commit anterior válido tras una regresión y repetir smoke test.

## 8. Guion demostración de 15 minutos
1. Dibujar flujo de Git → PR → CI → Docker → Render → Supabase/OpenRouter.
2. Mostrar `Dockerfile` y explicar etapas Node y Python; por qué el primer proceso desaparece del runtime.
3. Abrir Actions: pytest, typecheck, build y validación de Docker.
4. Mostrar PR, protección de rama recomendada y aprobación.
5. Render: ver commit, logs y URL; abrir `/api/health`, luego login.
6. Demostrar módulo académico/finanzas/tareas, preguntar al copiloto y enseñar el consumo.
7. Fallo controlado (solo teoría): variable `VITE_` faltante rompe login; cómo reconocerlo y recuperar el deploy.
8. Concluir con límites de la arquitectura, seguridad y métricas de operación.

## 9. Preguntas de comprensión
1. ¿Cuál es la diferencia entre una imagen Docker y un contenedor?
2. ¿Por qué compilamos React en la etapa Node y ejecutamos FastAPI en Python?
3. ¿Puede pasar CI si la base de datos remota está desconectada? Sí: estas suites no llaman a Supabase.
4. ¿Quién debe custodiar `OPENROUTER_API_KEY`? El backend/Render, nunca el bundle Vite.
5. ¿Qué valida RLS además del JWT? El acceso a filas por usuario en PostgreSQL.
6. ¿Por qué desplegar un solo Web Service no significa una sola base de datos ni cero gastos?
7. ¿Qué harías si Render publica una versión que falla?
8. ¿Qué diferencia hay entre desplegar manualmente y despliegue continuo automático?

## 10. Evidencia de cierre
Guardar: SHA desplegado, CI exitosa, logs de build sin secretos, URL pública y /api/health, capturas de sesión ficticia, prueba A/B, historial remoto y llamada IA real. Hasta entonces, llamar al resultado **preparado para despliegue**, no «publicado en producción».
