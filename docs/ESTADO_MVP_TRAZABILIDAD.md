# Estado real del MVP de AURORA AI — trazabilidad

Fecha de corte: 2026-11-13. Este documento separa lo **verificado** de lo **pendiente**. Ningún elemento pendiente
se presenta aquí como terminado.

## 1. Verificado

| Área | Evidencia | Resultado |
|---|---|---|
| Integración real con Supabase (dos cuentas, una pestaña) | `visual-evidence/fase-07c/20261113-095536/resultados.json` | **59 de 59** pruebas, estado COMPLETA, 0 fallos |
| Dataset de demostración en Supabase | Carga verificada en la Fase 07 (48 registros con prefijo `DEMO-AURORA-`) | Cargado. No se vuelve a sembrar |
| Dashboard y responsive | `visual-evidence/fase-07d/` | Sin desbordamiento horizontal en 390–1920 px; campo del copiloto visible |
| Copiloto en modo simulado | Suite de la Fase 07 y `visual-evidence/fase-07d/regresion/` | 26 de 26; respuestas etiquetadas como SIMULADO |
| Pytest del backend | Última ejecución en esta fase | **262 aprobadas** |
| TypeScript estricto y build de Vite | Última ejecución en esta fase | Sin errores |
| CLI del SENA (calificaciones, presupuesto, tareas) | Última ejecución en esta fase | exit 0 |
| Persistencia de conversaciones (Fase 08A), pruebas locales | `docs/PRUEBAS_FASE_08A.md` | Migración en clúster local: **25 de 25** pruebas SQL; interfaz con backend simulado: **26 de 26**; pytest de conversaciones: **23** |

## 2. Pendiente (no hecho)

| Elemento | Motivo |
|---|---|
| Aplicar la migración `20261113120000_fase08a_conversaciones_ia.sql` en Supabase | Requiere revisión y ejecución manual en SQL Editor |
| Verificar en Supabase las **20** comprobaciones de `08a_verificar_conversaciones.sql` | Depende de la aplicación anterior |
| Activar `AI_CONVERSACIONES_PERSISTENTES=true` | Solo después de la verificación remota |
| Pruebas de RLS con dos sesiones reales sobre las conversaciones | Depende de la migración aplicada |
| Llamada real a OpenRouter | Sin autorización explícita; el copiloto actual es simulado |
| Despliegue en Render | No autorizado. `render.yaml` existe, pero **no se ha desplegado** |
| Cuotas de uso para conversaciones y mensajes | Riesgo abierto identificado en la auditoría de la Fase 08A |

## 3. Limitaciones conocidas

- El copiloto **no es inteligencia artificial** mientras use el proveedor simulado.
- Las pruebas de la Fase 08A con la base de datos son **locales**: un clúster PostgreSQL desechable con un
  esquema `auth` simulado. No reproducen GoTrue ni PostgREST de Supabase.
- Las pruebas de la interfaz de persistencia usan un **backend simulado en el navegador**: validan la interfaz,
  no la base de datos.
- Los privilegios por defecto de Supabase sobre tablas nuevas se **suponen** en las pruebas locales; la migración los
  revoca explícitamente, así que el resultado no depende de esa suposición.
- Las evidencias de ejecuciones con sesión real (capturas con datos de cuenta, identificadores de registros) **no se
  publican** en el repositorio. Solo se publica el resultado agregado de la ejecución 07C.

## 4. Evidencias y documentación

- Documentación por fase: `docs/FASE_*_IMPLEMENTACION.md` y `docs/PRUEBAS_FASE_*.md`.
- Arquitectura del copiloto: `docs/ARQUITECTURA_COPILOTO.md`.
- Persistencia de conversaciones: `docs/FASE_08A_IMPLEMENTACION.md`.
- Evidencias publicadas: `visual-evidence/` (las de sesión real están excluidas en `.gitignore`).
