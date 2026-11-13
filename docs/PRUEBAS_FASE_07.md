# Pruebas — Fase 07

Fecha: 2026-11-12 · Windows 11 · Python 3.12.10 · Node v22.22.0 · Chrome instalado.

**Estado: IMPLEMENTACIÓN VERIFICADA SIN SUPABASE REAL.** La carga del dataset, el aislamiento RLS con datos
completos, la persistencia tras reinicio y el cierre de sesión con Supabase no se han ejecutado. No hay
simulación presentada como evidencia remota.

## 1. Regresión (ejecutada)

| Prueba | Resultado |
|---|---|
| Pytest completo | ✅ **236 aprobadas** (228 previas + 8 del sembrador) |
| TypeScript estricto (`tsc --noEmit`) | ✅ sin errores |
| Build de Vite | ✅ compila |
| CLI calificaciones (SENA) | ✅ exit 0 |
| CLI presupuesto (SENA) | ✅ exit 0 |
| CLI tareas (SENA) | ✅ exit 0 |

## 2. Sembrador (simulado, sin Supabase)

Ejecutadas con un servidor FastAPI simulado en memoria (`backend/tests/test_seed_supabase.py`):

| Prueba | Resultado |
|---|---|
| Dataset de A cumple los requisitos (6 asignaturas, 2–4 notas, 0–5, 8 gastos, 6 categorías, 10 tareas) | ✅ |
| Gastos con fechas válidas de noviembre y saldo esperado (2.270.000 COP gastados; 530.000 de saldo) | ✅ |
| Primera ejecución crea todo; segunda ejecución no duplica (asignaturas, notas, gastos, tareas) | ✅ |
| Prefijo `DEMO-AURORA-` y sin tocar otras cuentas | ✅ |
| La verificación lee solo los registros de la cuenta | ✅ |
| Solo endpoints `/api/` (ninguno de administración) | ✅ |
| `--plan` no envía nada | ✅ |
| Sin confirmación `SI`, no se inserta nada | ✅ |

**Ninguna de estas pruebas contacta Supabase.** La carga real está pendiente.

## 3. Interfaz del copiloto (Chrome, demo con proveedor SIMULADO)

Ejecutadas con `frontend/e2e/fase07_ui.py` contra el backend de demostración, con
`COPILOT_PROVIDER=simulado` y `OPENROUTER_API_KEY` vacía. **No es IA ni hay llamadas a OpenRouter.**

Resultado: **26 de 26 aprobadas**, 0 fallos. Peticiones al copiloto registradas: 4, que corresponden a una
pregunta desde el widget, una desde la página completa, una fallida (503) y su reintento. No hay duplicados.

| Área | Comprobaciones | Resultado |
|---|---|---|
| Widget: botón flotante | visible, esquina inferior derecha | ✅ 2/2 |
| Widget: apertura y cierre | se abre sin cambiar de página; el foco entra en el campo; ancho de unos 400 px; Escape cierra; el foco vuelve al botón | ✅ 5/5 |
| Widget: respuesta | etiquetada como simulada | ✅ |
| Expandir | el widget se oculta; la pregunta y la respuesta enviadas desde el widget aparecen en la página completa | ✅ 3/3 |
| Página completa | un envío = una petición | ✅ |
| Navegación | al volver al copiloto se conserva la conversación; el widget no aparece en el copiloto y sí en otras secciones | ✅ 2/2 |
| Conversaciones | nueva conversación; la anterior sigue en el panel; el panel se puede ocultar | ✅ 3/3 |
| Errores | 503 con mensaje en español; reintento que no duplica la pregunta ni deja el error | ✅ 3/3 |
| Limpiar | la conversación activa queda vacía | ✅ |
| Responsive página completa | 390, 768, 1440 y 1920 px, sin desplazamiento horizontal | ✅ 4/4 |
| Responsive widget móvil | panel casi a pantalla completa, sin ocultar la cabecera | ✅ |

**Defectos encontrados y corregidos durante la verificación:**

1. El foco no volvía al botón al cerrar, porque se intentaba enfocar antes de que el botón existiera en el DOM.
2. La lista de conversaciones no tenía nombre accesible.
3. Expandir el widget lo dejaba abierto al volver a otra sección.
4. El panel del widget se animaba desde opacidad 0; la captura podía salir translúcida o vacía según el momento.
   Se quitó la animación de entrada.
5. El botón «Limpiar conversación» se había perdido al reescribir la página, y se restauró.
6. Un id de campo duplicado si el widget y la página estaban visibles a la vez: ahora cada campo tiene su propio id.

## 4. Pruebas pendientes (requieren Supabase real y tu autorización)

| Prueba | Estado |
|---|---|
| Carga del dataset DEMO-AURORA- en la cuenta A y en la cuenta B | ⏸ pendiente de confirmación y de las cuentas autenticadas |
| Dataset persistido en PostgreSQL y leído con el JWT de cada cuenta | ⏸ pendiente |
| Aislamiento RLS cruzado A/B con el dataset completo | ⏸ pendiente |
| Dashboard con gráficas calculadas sobre el dataset real de A | ⏸ pendiente |
| Contexto del copiloto con los datos reales de cada cuenta | ⏸ pendiente |
| Cierre de sesión y cambio de cuenta: el historial se limpia | ⏸ pendiente |
| Persistencia tras reiniciar | ⏸ pendiente |
| OpenRouter real | ⏸ bloqueado por la clave revocada, la nueva clave y tu autorización |

Lo que sí se ha comprobado en el código, sin navegador con cuentas reales: el reinicio del estado al cambiar
`userKey`, el descarte de respuestas de una cuenta anterior y la ausencia de tokens en el historial.

## 5. Limitaciones

- Solo Chrome, en modo headless para la verificación de la interfaz.
- La interfaz se ha verificado con el backend de demostración, no con Supabase.
- Las conversaciones no se guardan en la base de datos: viven en la sesión del navegador.
- No hay commits, no hay despliegue en Render, no se ha usado Supabase CLI y no se han ejecutado migraciones.

## 6. Evidencias (`visual-evidence/fase-07/`)

- `01_widget_abierto_escritorio.png`: widget abierto sobre el dashboard, en escritorio.
- `02_copiloto_completo_escritorio.png`: página completa con conversaciones, chat y datos.
- `03_widget_movil.png`: widget en móvil.
- `resp_copiloto_{movil,tableta,escritorio,full_hd}.png`: página completa en los cuatro tamaños.

## 7. Prompt 07B · auditoría previa del sembrador contra Supabase (estado)

**Sin escrituras remotas todavía.** La carga real espera tu confirmación.

### Hallazgos de la auditoría

| # | Hallazgo | Riesgo | Corrección |
|---|---|---|---|
| 1 | El sembrador hacía `PUT` sobre el presupuesto del mes sin comprobar si existía | Sobrescribir un presupuesto existente | Nunca sobrescribe. Si el mes existe con valores distintos, se detiene antes de escribir |
| 2 | Sin comprobación de gastos ajenos al prefijo en el mes | Mezclar datos de demostración con datos reales | Si el mes contiene gastos que no son `DEMO-AURORA-`, se detiene |
| 3 | El mes estaba fijado en el código (`2026-11`) | No se podía elegir otro mes | Nuevo argumento `--mes AAAA-MM` |
| 4 | `--plan` no se conectaba y no mostraba el estado real | No se podía ver el conflicto antes de escribir | `--plan` se conecta solo para leer y muestra existentes y por crear |
| 5 | La prueba 06C creó un presupuesto para noviembre de 2026 de la cuenta A (ingreso 1.000.000 COP, gasto `06C-Mercado A`) | Conflicto con el dataset de noviembre | El plan lo detecta; el dataset debe ir a otro mes |

### Estado de los registros de la cuenta A (06C, sin borrar)

- Asignatura `06C-Cálculo A` con una nota.
- Presupuesto de noviembre de 2026: ingreso 1.000.000 COP, con el gasto `06C-Mercado A`.
- Tarea `06C-Entregar taller A`.

Estos registros no se modifican ni se borran.

### Pendiente de tu ejecución

Desde `backend\` con el venv, en PowerShell:

```powershell
.\.venv\Scripts\python.exe tools\seed_supabase.py --cuenta A --plan --mes 2026-10
.\.venv\Scripts\python.exe tools\seed_supabase.py --cuenta B --plan
```

El plan pide correo y contraseña en la terminal (no se muestran ni se guardan), y no escribe nada.

### Pruebas del sembrador (simuladas, 11 pruebas)

Las 11 pruebas usan un servidor FastAPI simulado en memoria. Verifican el dataset, la idempotencia, que no se
sobrescribe ningún presupuesto, que `--plan` no escribe, que la confirmación es obligatoria y que el mes
alternativo se aplica a fechas y presupuesto. **No son pruebas de Supabase real.**

Regresión: Pytest completo, **239 aprobadas**; TypeScript estricto sin errores.
