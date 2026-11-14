# AURORA AI: cierre seguro de Supabase, OpenRouter y Render

Este documento describe comprobaciones pendientes. **No certifica un despliegue público** ni una llamada de IA real.

## Error observado en la captura del 14-11-2026: PROYECTO EQUIVOCADO
La URL de la captura corresponde a **LOGIXTIC** (`wjccxmpxhhavfmhgnqit`), no a AURORA.
La respuesta `ai_conversations=NULL`, `ai_messages=ai_messages` **es de Logixtic**. No significa que las migraciones de AURORA hayan fallado. NO ejecutar la migración de AURORA en Logixtic.

AURORA: `https://supabase.com/dashboard/project/dsldzrtgzrthifsxmtwu/sql/new`.
No existe herramienta conectada de Supabase con permisos SQL en este flujo; los cambios deben ejecutarse con el dashboard del proyecto correcto después de revisar la consulta.

### Gate B: dos comprobaciones SQL, ninguna destructiva
1. Abrir el dashboard de la URL anterior y comprobar que arriba dice `AURORA_IA` y en la URL `dsldzrtgzrthifsxmtwu`.
2. Abrir `supabase/sql_editor/08a_preflight_solo_lectura.sql` (7 filas: las 5 tablas del dominio y las 2 tablas del historial).
3. Si las 5 tablas del dominio no aparecen, PARAR: puede ser proyecto equivocado o esquema incompleto.
4. Si falta una o ambas tablas del historial, revisar primero `supabase/migrations/20261113120000_fase08a_conversaciones_ia.sql`, comprobar idempotencia y aprobar manualmente su aplicación en el SQL Editor de **AURORA** (NO Supabase CLI).
5. Ejecutar `supabase/sql_editor/08a_verificar_conversaciones.sql`: deben salir **20 filas ok=true**. Las capturas «Success. No rows returned» NO sustituyen esta verificación.
6. Comprobar sesión A y sesión B con datos de QA; después activar `AI_CONVERSACIONES_PERSISTENTES=true` en backend local y Render. Verificar historial tras recarga y prohibición de acceso cruzado.

### Gate C: OpenRouter (cuotas gratuitas y modelo alternativo)
- La ejecución local con Antigravity encontró un **429/límite** del modelo gratuito; el log no demuestra una respuesta IA exitosa.
- Revocar la clave antigua expuesta, generar una **clave nueva** y guardarla solo en backend/.env (local) y entorno protegido de Render. No pegarla en Git, README, pantallas ni frontend.
- AURORA permite configurar `OPENROUTER_MODEL` y opcionalmente `OPENROUTER_FALLBACK_MODELS` con hasta 3 identificadores adicionales separados por coma, **todos terminados en `:free`**. Si se definen fallbacks, el modelo principal también debe ser `:free`.
- OpenRouter acepta `models: [modelo_principal, ...alternativos]` para intentar modelos por prioridad **en una sola petición**. El sistema no cambia a modelos de pago automáticamente.
- Confirmar que los identificadores existen en el catálogo actual y que la cuota permite solicitudes. Los modelos gratuitos pueden rechazar peticiones por capacidad/cuota. Un 429 es esperado cuando se agotan; no inventar un PASS.
- Ejemplo esquemático **NO es configuración real**:

```dotenv
COPILOT_PROVIDER=openrouter
OPENROUTER_MODEL=proveedor/modelo-primario:free
OPENROUTER_FALLBACK_MODELS=proveedor/modelo-alternativo:free
```

- Antes de uso abierto, valorar un presupuesto de tokens/costo, cuotas persistentes y aviso al usuario de envío de su contexto autorizado a un proveedor externo. Los límites actuales en memoria no son distribuidos.

### Gate D: UI responsive
Antigravity reportó PASS en 390, 768, 1366, 1440 y 1920 px, con cero overflow y botones tapados. Preservar las capturas y la rama local `feat/aurora-production-readiness`; al revisarse el 14-11 dicha rama **no existía en GitHub**, así que los cambios locales no están presentes en esta rama remota.

La corrección local de `VITE_API_BASE_URL=""` hecha por Antigravity **no queda necesariamente en Git**, porque .env.local está ignorado. En Render también debe quedar vacío en variables para que el frontend use su mismo origen `/api`.

### Gate E: Render, un Web Service Docker
El Dockerfile compila frontend en Node 22 y copia artefactos al runtime Python 3.12; FastAPI sirve web + API. Supabase y OpenRouter son servicios externos.
El archivo `render.yaml` usa `autoDeploy: false`; para el primer despliegue se recomienda aprobación manual.
Configurar URL y clave **publishable** en backend y `VITE_*`, clave OpenRouter solo en backend, `APP_ENV=production`, `DEMO_MODE=false`, `PERSISTENCE_BACKEND=supabase`. Confirmar `OPENROUTER_MODEL` existe y ha superado consulta real.
Los `VITE_*` se compilan dentro del bundle; si cambian, solicitar **rebuild**, no solo restart.

**Smoke público sin cuentas ni secretos:**
```powershell
python backend/tools/smoke_public_release.py https://NOMBRE-SERVICIO.onrender.com
```
No añade datos ni envía solicitudes a OpenRouter. Solo verifica salud, modo, SPA y 401 de ruta privada. Una vez aprobado, completar login real, CRUD, RLS con A/B, persistencia, agente real y responsive desde URL pública.

### Gate F: CI/CD y ramas
- PR #1: MVP -> main; PR #2: CI/CD -> rama MVP; PR #3: reglas y guardas -> rama CI/CD; este PR: ajustes adicionales -> rama PR #3.
- Integrar en orden después de revisión, preservando cambios locales de Antigravity. NO hacer merges, deploy ni escrituras SQL remotas sin autorización.
- El workflow CD exige hook privado `RENDER_DEPLOY_HOOK_URL` y CI verde. Activar el hook **solo después** de comprobar deploy manual + rollback.
- La CI automatizada con datos ficticios no puede asegurar conexión real a Supabase/OpenRouter.

## Evidencia de aceptación de producción
URL pública; commit SHA; CI PASS; smoke HTTP PASS; JWT real; CRUD por usuario; 20/20 SQL; RLS A/B; persistencia real; una respuesta de OpenRouter no simulada; capturas responsive de producción; logs sin secretos; plan de rollback.

Si falta una evidencia, comunicar **PENDIENTE**, nunca «todo funcional».
