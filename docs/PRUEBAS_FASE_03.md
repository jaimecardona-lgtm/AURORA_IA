# Pruebas — Fase 03

Fecha: 2026-11-12 · Entorno: Windows 11 · Python 3.12.10 (`backend/.venv`) · Node v22.22.0 ·
Chrome instalado (Playwright 1.65.1 en un entorno aparte, fuera del proyecto).

**Estado: COMPLETADA en lo local.** Supabase no se ha conectado (fuera de alcance por decisión
del prompt). Sin commits y sin despliegue en Render.

## 1. Auditoría previa (Paso 0)

| Comprobación | Resultado |
|---|---|
| `git status` | Sin cambios de Fase 03 antes de empezar (`M README.md`, resto sin seguimiento) |
| Suite inicial | **90 passed** |
| `npm run build` inicial | ✅ compila |
| Motores existentes | `grades.py`, `budget.py`, `tasks.py` (sin categoría, fecha ni fecha límite) |
| Dependencias de Supabase en la UI | `AuthProvider`, `AuthPage`, `lib/supabase.ts`: solo para el modo normal; el modo demo no las usa |

## 2. Resultados finales

| Ámbito | Comando | Resultado |
|---|---|---|
| Pruebas unitarias de motores | `pytest tests/test_motores_fase03.py` | ✅ incluidas en la suite |
| Integración API con SQLite | `pytest tests/test_api_sqlite.py` | ✅ incluidas en la suite |
| Suite completa backend | `cd backend && .venv\Scripts\python -m pytest -q` | ✅ **167 passed** (90 previas + 77 nuevas) |
| Compilación TypeScript + Vite | `cd frontend && npm run build` | ✅ `tsc --noEmit` y `vite build` sin errores |
| CLI calificaciones | `python sena_cli/calificaciones.py 4.5 3.0 2.9` | ✅ exit 0 |
| CLI presupuesto | `python sena_cli/presupuesto.py --ingreso 2000000 --ahorro 300000 --gasto ...` | ✅ exit 0 |
| CLI tareas | `python sena_cli/tareas.py "Entregar:1" "Leer:3:completada"` | ✅ exit 0 |
| Modo demo en producción | `APP_ENV=production DEMO_MODE=true` (`import app.main` y `uvicorn`) | ✅ **no arranca** (exit 1, mensaje claro) |
| Demo con Supabase | `APP_ENV=production DEMO_MODE=true PERSISTENCE_BACKEND=supabase` | ✅ no arranca (exit 1) |
| Recorrido en navegador (Chrome real) | `python e2e/fase03_recorrido_demo.py` (base limpia) | ✅ **38 / 38 PASS** |
| Persistencia tras reiniciar el servidor | `... --verificar` tras `uvicorn` reiniciado | ✅ **6 / 6 PASS** |

Los resultados completos de la ejecución en navegador están en los registros generados por el
script (`resultados_final.json`, `resultados_reinicio.json`, en la carpeta temporal de la sesión).

## 3. Pruebas de navegador — detalle

Protocolo: `python -m app.infrastructure.sqlite.seed --reset` → servidor demo en `127.0.0.1:8765` →
recorrido completo → reinicio del servidor → `--verificar`.

**Académico**
- ✅ Datos demo visibles (3 asignaturas), promedio general (3,64) y promedio de Cálculo (4,17).
- ✅ Nota objetivo imposible (4,5) informada como «No es posible»; posible (4) → 3.50.
- ✅ Nota 6 rechazada en la interfaz; nota 4,80 registrada y promedio recalculado (4,33).
- ✅ Crear y eliminar asignatura (lista actualizada en ambos casos).

**Finanzas**
- ✅ Ingreso demo (2.500.000) y distribución por categoría.
- ✅ Gasto registrado y visible; importe negativo, gasto sin categoría y sin descripción rechazados.
- ✅ Eliminación de gasto con confirmación en dos pasos.

**Tareas**
- ✅ Crear con prioridad alta y fecha límite; completar; filtrar por estado; editar; eliminar.

**Recarga**: ✅ la nota registrada sigue tras recargar la página.

**Consola del navegador**: ✅ sin errores de JavaScript durante todo el recorrido.

## 4. Pruebas de comportamiento responsive

Se midió el desbordamiento horizontal de la página (`scrollWidth − innerWidth`) en cada módulo:

| Ancho | Módulo Académico | Finanzas | Tareas |
|---|---|---|---|
| 390 px (móvil) | 0 px | 0 px | 0 px |
| 820 px (tableta) | 0 px | 0 px | 0 px |
| 1366 px (escritorio) | 0 px | 0 px | 0 px |

Revisión visual de capturas: escritorio de Académico y móvil de Finanzas. En la revisión se
encontró y corrigió un solapamiento de la leyenda de la distribución por categoría en móvil; la
captura corregida no se volvió a inspeccionar a mano, pero la comprobación de desbordamiento sí
se repitió.

## 5. Accesibilidad básica (verificada en navegador)

- ✅ El primer Tab llega al enlace «Saltar al contenido».
- ✅ Enter sobre un elemento de navegación abre el módulo.
- ✅ El módulo activo tiene `aria-current="page"`.
- ✅ Los campos tienen etiqueta asociada; los errores usan `aria-invalid` y `aria-describedby`.

## 6. Defectos encontrados durante la verificación

Todos corregidos y verificados de nuevo. Las pruebas de la API no los detectaban, por eso se
añadió una prueba de regresión y el recorrido de navegador.

| # | Defecto | Severidad | Estado |
|---|---|---|---|
| 1 | `sqlite3.ProgrammingError` (conexión usada en otro hilo) en todas las peticiones con base de datos | Alta: el servidor respondía 500 | ✅ corregido; `test_conexion_sqlite_puede_usarse_desde_otro_hilo` falla sin la corrección |
| 2 | Tras crear una asignatura se mostraba la anterior y «Eliminar» podía borrar la equivocada | **Alta: pérdida de datos** (se comprobó: se borró «Cálculo diferencial» en una ejecución) | ✅ corregido; verificado con el recorrido |
| 3 | Mensajes de validación en inglés | Media | ✅ traducidos (manejador único) |
| 4 | Leyenda de distribución solapada en móvil | Baja | ✅ corregido |

Durante la depuración también se purgaron registros de prueba de la base demo (solo filas con
`origen='real'`); las filas demo se conservaron y se regeneraron con `--reset`.

## 7. Limitaciones de esta verificación

- No hay pruebas contra Supabase: la fase no lo incluye, y finanzas y tareas responden 501 con ese backend.
- El aislamiento entre usuarios de SQLite se prueba por la API con dos identidades JWT
  (`test_usuarios_distintos_no_se_ven_ni_modifican`, `test_presupuesto_y_tareas_aislados_entre_usuarios`).
  No se prueba en el navegador con dos sesiones reales.
- Las pruebas Playwright de la Fase 01 (`frontend/e2e/smoke_*.py`) no se han ejecutado.
- No se ha verificado en Safari, Firefox ni en dispositivos físicos; solo Chrome.
- Los informes académicos AA2-EV01 y AA2-EV02 no se han redactado (fuera de alcance).
