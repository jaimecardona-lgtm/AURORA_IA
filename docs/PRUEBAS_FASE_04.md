# Pruebas — Fase 04

Fecha: 2026-11-12 · Entorno: Windows 11 · Python 3.12.10 (`backend/.venv`) · Node v22.22.0 ·
Chrome instalado (Playwright 1.65.1, fuera del proyecto).

Todos los resultados son de ejecuciones reales de esta sesión. Ninguno se ha simulado. Sin commits,
sin Supabase, sin OpenRouter y sin despliegue en Render.

## 1. Auditoría y línea base

| Comprobación | Resultado |
|---|---|
| Suite pytest al inicio de la fase | 167 passed |
| Build de Vite al inicio | compila |
| Estado de Git | sin commits nuevos; sin cambios de esta fase antes de empezar |
| Documento C4 | el repositorio contiene `AURORA_AI_Arquitectura_C4.html`; se creó `docs/arquitectura-c4.html` |

## 2. Resultados finales

| Ámbito | Comando | Resultado |
|---|---|---|
| Suite completa backend | `cd backend && python -m pytest -q` | ✅ **178 passed** (167 previas + 11 del panel) |
| Pruebas del panel | `tests/test_dashboard.py` | ✅ 11/11 (cifras calculadas a mano en el test) |
| Compilación TypeScript estricta | `cd frontend && npx tsc --noEmit` | ✅ sin errores |
| Build de Vite | `npm run build` | ✅ compila |
| CLI calificaciones | `python sena_cli/calificaciones.py 4.5 3.0 2.9` | ✅ exit 0 |
| CLI presupuesto | `python sena_cli/presupuesto.py --ingreso 2000000 --ahorro 300000 --gasto ...` | ✅ exit 0 |
| CLI tareas | `python sena_cli/tareas.py "Entregar:1" "Leer:3:completada"` | ✅ exit 0 |
| Navegador, recorrido completo | `python e2e/fase04_recorrido.py <URL> <capturas> <json>` | ✅ **40 / 40 PASS** |
| Persistencia tras reiniciar | `… --verificar` tras reiniciar `uvicorn` | ✅ **4 / 4 PASS** |
| Arranque con demo en producción | `APP_ENV=production DEMO_MODE=true` | ✅ no arranca (exit 1) — comprobado en la fase 03 y sin cambios |

Entorno de la prueba en navegador: base SQLite **temporal aislada** (`scratchpad/e2e_fase04.sqlite3`),
creada con `seed`, servidor en `127.0.0.1:8766`. La base de desarrollo (`backend/data/`) no se usó
para las pruebas destructivas.

## 3. Panel general (Mi espacio)

- ✅ Título «Vista general» y accesos a los tres módulos.
- ✅ Promedio general igual al de la API (3,64).
- ✅ Aprobadas igual a la API (2 / 3).
- ✅ Saldo igual a la API (870.000).
- ✅ Tareas pendientes igual a la API.
- ✅ Próximas a vencer igual a `proximas_total` de la API.
- ✅ Copiloto marcado como **Próximamente**, sin botón que simule respuestas.

## 4. Académico (CRUD y mejoras)

- ✅ Aviso visible: las notas pesan igual; las ponderaciones no están implementadas.
- ✅ Gráfica «Notas por evaluación (0 a 5)».
- ✅ Crear nota (`4,10`) y verla en la lista.
- ✅ Nota `7` rechazada en la interfaz.
- ✅ Eliminar nota: pide confirmación antes de actuar, y después desaparece.

## 5. Finanzas (CRUD, edición y tabla)

- ✅ Gráfica de gastos fijos frente a variables.
- ✅ Tabla de transacciones con encabezados.
- ✅ Crear gasto.
- ✅ Editar: el formulario carga los datos actuales.
- ✅ Edición con importe `-1` rechazada («no puede ser negativo»).
- ✅ Edición válida (`20.000`) guardada y reflejada en la tabla.
- ✅ Eliminar gasto: la fila desaparece.

## 6. Tareas

- ✅ Prioridad alta aplicada como clase visual (`prioridad--alta`).
- ✅ Completar: la tarea queda tachada.
- ✅ Crear y eliminar tareas con confirmación.

## 7. Responsive (desbordamiento horizontal de la página)

Medido con `scrollWidth − innerWidth` en cada módulo:

| Ancho | Mi espacio | Académico | Finanzas | Tareas |
|---|---|---|---|---|
| 390 px (móvil) | 0 px | 0 px | 0 px | 0 px |
| 820 px (tableta) | 0 px | 0 px | 0 px | 0 px |
| 1366 px (escritorio) | 0 px | 0 px | 0 px | 0 px |

## 8. Accesibilidad y consola

- ✅ El primer Tab llega a «Saltar al contenido».
- ✅ Enter sobre la navegación abre el módulo.
- ✅ El módulo activo expone `aria-current="page"`.
- ✅ Consola del navegador sin errores de JavaScript durante todo el recorrido.

## 9. Persistencia tras reinicio

Tras reiniciar el servidor (proceso nuevo, mismo archivo SQLite):

- ✅ Promedio general mostrado igual al de la API (3,64).
- ✅ Tarea creada antes del reinicio sigue en la lista.
- ✅ Sin errores de consola.

## 10. Estados vacíos, errores y validaciones

Comprobados dentro del recorrido: nota fuera de rango, importe negativo, edición con fecha fuera del
mes, categoría vacía, descripción vacía, presupuesto sin datos (estado vacío con acción), panel sin
gastos (estado vacío con acceso a Finanzas) y Copiloto sin respuestas simuladas.

La validación de formato de la API (422) se comprobó en la fase anterior y el manejador de mensajes
en español sigue activo.

## 11. Pruebas del diagrama C4

Comprobación en Chrome del archivo `docs/arquitectura-c4.html` (sin errores de JavaScript):

- ✅ Vista actual: C1 con 5 nodos, C2 con 7, C3 con 10. Etiqueta «ACTUAL · VERIFICADO EN LOCAL».
- ✅ Vista objetivo: C2 con 10 nodos. Etiqueta «OBJETIVO · PROPUESTA, NO IMPLEMENTADA».
- ✅ Los botones de vista no cambian de nivel (defecto corregido, ver §12).

## 12. Defectos encontrados y corregidos

| # | Defecto | Detectado por | Estado |
|---|---|---|---|
| 1 | Meta de ahorro mostrada como 100 % en lugar de 217 % | Revisión visual de captura | ✅ corregido |
| 2 | Nota «4,10» rechazada por error binario (`4.1 × 100`) | Prueba de navegador (ninguna petición enviada) | ✅ corregido |
| 3 | Botones de vista del C4 disparaban `render(undefined)` | Prueba del diagrama | ✅ corregido |
| 4 | 9 pruebas de pytest fallaban con variables exportadas en el shell | Ejecución de pytest | ✅ corregido (fixture de aislamiento) |
| 5 | Importes del presupuesto sin formato | Captura móvil | ✅ corregido |

## 13. Capturas (`visual-evidence/fase-04/`)

Capturas reales del frontend generadas por el recorrido:

- Escritorio: `01_mi_espacio_escritorio.png`, `02_academico_escritorio.png`, `03_finanzas_escritorio.png`, `04_tareas_escritorio.png`.
- Responsive: `resp_<módulo>_<movil|tableta|escritorio>.png` (12 archivos).
- C4: `04_c4_objetivo.png`, `05_c4_actual_componentes.png`.

Revisión visual (honesta): inspeccioné la vista de escritorio de Mi espacio (que motivó la corrección 1),
la vista móvil de Finanzas (que motivó la corrección 5) y las vistas de C4. Las demás capturas se
generaron con la versión final, pero **no se han revisado una a una**.

## 14. Limitaciones

- Solo Chrome. No se ha probado en Firefox, Safari ni en dispositivos reales.
- La prueba del recorrido crea y elimina datos en una base temporal. No prueba dos usuarios reales en el navegador.
- Las pruebas Playwright de fases anteriores (`frontend/e2e/smoke_*.py` y `fase03_recorrido_demo.py`) no se han vuelto a ejecutar.
- La propuesta de migración de importes (§5.1 de la implementación) no está aplicada; solo se midió el riesgo.
