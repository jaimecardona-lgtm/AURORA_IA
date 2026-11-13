# Pruebas — Fase 06D

Fecha: 2026-11-12 · Windows 11 · Python 3.12.10 · Node v22.22.0 · Chrome instalado.

**Estado: PARCIAL.** Lo verificado es la regresión, la auditoría responsive y el procedimiento de Playwright
corregido. **La prueba real con las cuentas A y B (autenticación, RLS cruzada, persistencia tras reinicio y
copiloto contra Supabase) no se ha completado**: requiere que inicies sesión tú en las ventanas de Chrome. No
hay resultados de esa prueba en este documento.

## 1. Regresión (ejecutada)

| Prueba | Resultado |
|---|---|
| Pytest completo | ✅ **228 aprobadas** |
| TypeScript estricto (`tsc --noEmit`) | ✅ sin errores |
| Build de Vite | ✅ compila |
| CLI calificaciones (SENA) | ✅ exit 0 |
| CLI presupuesto (SENA) | ✅ exit 0 |
| CLI tareas (SENA) | ✅ exit 0 |
| Backend real en Supabase (8000): `/api/modo`, `/api/health` | ✅ `produccion`, `supabase_configurado: true` |
| Copiloto de pruebas en Supabase (8001): `/api/modo` | ✅ responde |

## 2. Auditoría responsive (ejecutada)

Herramienta: `frontend/e2e/fase06d_responsive.py`, con viewports explícitos de 390×844, 768×1024, 1366×768,
1440×900 y 1920×1080. Aplicación de auditoría: build actual del frontend, con backend temporal en modo demo
y base SQLite nueva, aislada de la base de desarrollo.

Mediciones registradas por módulo: `innerWidth`, `outerWidth`, `clientWidth` y `scrollWidth` del documento,
ancho del contenido y número de columnas de los indicadores.

### Antes de los cambios

Las 20 mediciones no tenían desbordamiento horizontal (`scrollWidth = clientWidth`). Sin embargo, a 1920 px el
contenido estaba limitado a 1200 px, con una franja vacía, y los seis indicadores se repartían en siete columnas.

### Después de los cambios

| Tamaño | Columnas de indicadores | Desbordamiento | Ancho del contenido |
|---|---|---|---|
| 390×844 | 2 | 0 px | 390 px |
| 768×1024 | 3 | 0 px | 768 px |
| 1366×768 | 6 | 0 px | 1146 px |
| 1440×900 | 6 | 0 px | 1220 px |
| 1920×1080 | 6 | 0 px | 1700 px (máximo 1480 px de módulo) |

Resultado: 20 de 20 sin desbordamiento. Capturas en `visual-evidence/fase-06d/responsive-antes/` y
`responsive-despues/`. Revisada visualmente la captura de 1920 px del dashboard después del cambio.

## 3. Procedimiento de Playwright (corregido, sin ejecución completa)

| Comprobación | Estado |
|---|---|
| El script usa `no_viewport=True` en los contextos interactivos | ✅ revisado en el código |
| Autenticación secuencial A y luego B | ✅ revisado en el código |
| `TargetClosedError` controlado: detecta el cierre, pregunta en la terminal y no aprueba la prueba interrumpida | ✅ revisado en el código; **no ejecutado con cierre real de ventana** |
| JSON de resultados independiente por ejecución | ✅ revisado en el código |
| Sin contraseñas, sin tokens impresos, sin exportar estado de sesión | ✅ revisado en el código |
| Ejecución real con cuentas A y B | ⏸ **pendiente de tu ejecución manual** |

Causa original del `TargetClosedError`: un cierre de ventana durante la espera de inicio de sesión no estaba
controlado y terminaba el proceso. Documentado en `FASE_06D_IMPLEMENTACION.md` §1.

## 4. Resultados de la prueba real (pendientes)

Ninguno de los siguientes puntos se ha ejecutado todavía. No se marcan como aprobados.

| Prueba | Estado |
|---|---|
| Inicio de sesión real de A y de B | ⏸ pendiente |
| Creación de datos de A y de B en los tres módulos (con prefijo `06C-`) | ⏸ pendiente |
| Persistencia en PostgreSQL leída con el JWT de cada cuenta | ⏸ pendiente |
| Aislamiento RLS: lectura, modificación y eliminación cruzadas en ambos sentidos | ⏸ pendiente |
| Dashboard con datos reales de cada cuenta | ⏸ pendiente |
| Contexto del copiloto (simulado) con datos de cada cuenta | ⏸ pendiente |
| Persistencia tras reiniciar backend y frontend | ⏸ pendiente |

Para ejecutarla, desde la raíz del repositorio en PowerShell:

```powershell
python frontend\e2e\fase06c_supabase_real.py visual-evidence\fase-06d
```

## 5. Limitaciones

- Solo Chrome; sin pruebas en otros navegadores.
- Las mediciones responsive usan la aplicación de demostración; el diseño es el mismo, pero los datos no proceden de Supabase.
- Los estados vacíos siguen sin rediseñar: el mensaje existe, pero la presentación visual queda pendiente.
- Sin OpenRouter (no se ha consumido), sin commits, sin despliegue en Render, sin Supabase CLI.
