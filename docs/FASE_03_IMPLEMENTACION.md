# Fase 03 — Implementación (desarrollo local con SQLite)

Resultados verificados: [PRUEBAS_FASE_03.md](PRUEBAS_FASE_03.md).

Esta fase completa los tres módulos funcionales (Académico, Finanzas, Tareas) de React a FastAPI
y a una base SQLite local, sin Supabase. Supabase queda para una fase posterior: el adaptador
PostgREST de la Fase 01 se conserva sin cambios de comportamiento.

---

## 1. Arquitectura de desarrollo local

```
React (Vite)  ──fetch /api/*──▶  FastAPI
                                   │
                  api/ (rutas, DTO)│  schemas/ (validación de forma)
                                   ▼
                       services/ (reglas de uso, 404/409/422)
                                   │  llama a motores puros
                                   ▼
                       core/ (motores: grades, budget, tasks)
                                   │
                       repositorio (interfaz por operación)
                       ├── infrastructure/sqlite/  ← desarrollo y demo
                       └── repositories/           ← PostgREST (Supabase, futuro)
```

- **Motores** (`backend/app/core/`): funciones puras sin FastAPI ni base de datos. Son la única
  fuente de reglas: promedios, aprobación, nota necesaria, importes COP, orden y vencimientos de
  tareas. La UI no vuelve a calcular ninguna de estas cosas.
- **Servicios**: traducen errores del motor a HTTP (422 de validación, 404 si el recurso no es
  accesible, 409 si hay duplicado).
- **Repositorios SQLite** (`infrastructure/sqlite/repositories.py`): solo SQL. Cada consulta filtra
  por `user_id`, que es el equivalente local de la política RLS `auth.uid() = user_id`.
- **Selección de backend**: `PERSISTENCE_BACKEND=sqlite|supabase` (por defecto `supabase`). Con
  `supabase`, las finanzas y tareas responden **501** porque aún no tienen adaptador PostgREST.

## 2. Base SQLite y migraciones

- Archivo: `backend/data/aurora_local.sqlite3` (ruta configurable con `SQLITE_PATH`). Ignorado por
  Git (`.gitignore`: `backend/data/`, `*.sqlite3*`).
- Migraciones SQL numeradas en `backend/app/infrastructure/sqlite/migrations/`:
  - `0001_academico.sql`: asignaturas y notas.
  - `0002_finanzas_tareas.sql`: presupuestos, gastos y tareas.
- Se aplican al arrancar, solo las pendientes, y quedan registradas en `schema_migrations`.
  Cada migración es un script y no es transaccional de forma automática: si falla a mitad, hay que
  revisarla antes de volver a arrancar (las sentencias usan `IF NOT EXISTS`).
- Las restricciones (CHECK, UNIQUE, claves foráneas compuestas `(user_id, id)`) las aplica la base,
  igual que en PostgreSQL.

## 3. Modo demo y registros ficticios

- `DEMO_MODE=true` desactiva el inicio de sesión y usa un único usuario local fijo. **No es
  autenticación**: el servidor lo declara en `GET /api/modo`, y la interfaz muestra el aviso
  «MODO DEMO LOCAL» en todo momento.
- **Protección**: `Settings.validate_runtime()` impide arrancar si `DEMO_MODE=true` y `APP_ENV`
  no es `development`, `local` o `test`. También exige `PERSISTENCE_BACKEND=sqlite`. Se comprobó
  que el arranque falla (exit 1) con `APP_ENV=production`, con `supabase` y en `uvicorn`.
- **Datos ficticios**: `python -m app.infrastructure.sqlite.seed [--reset]` inserta datos con
  `origen='demo'`. `--reset` borra **solo** las filas demo. Todas las entidades (asignaturas,
  notas, presupuestos, gastos y tareas) tienen la columna `origen` (`real`|`demo`), y la interfaz
  marca los registros demo con una etiqueta.

## 4. Módulo académico

- Asignaturas: crear, renombrar, consultar y eliminar (con confirmación en dos pasos). Nombres
  duplicados (sin distinguir mayúsculas) → 409.
- Notas 0–5 con hasta dos decimales. La interfaz acepta coma decimal.
- Promedio y aprobación (≥ 3,0) desde `core/grades.py`.
- **Nota necesaria** (`GET /api/subjects/{id}/objetivo?objetivo=`): calcula la nota mínima de la
  próxima evaluación para alcanzar un promedio objetivo. Informa si es imposible (incluso con 5).
  Supuesto documentado: todas las notas pesan igual, como en el promedio.
- **Resumen** (`GET /api/academico/resumen`): asignaturas, aprobadas, reprobadas y promedio general
  (cada asignatura pesa igual).
- Gráfica de barras de promedios por asignatura (SVG/CSS propio, sin librerías nuevas).

## 5. Módulo financiero

- Presupuesto por mes (`PUT /api/finanzas/presupuestos/{anio}/{mes}`): ingreso y meta de ahorro.
- Gastos con descripción, categoría, importe, tipo (fijo/variable) y **fecha obligatoria dentro
  del mes** (`POST .../gastos`, `PATCH|DELETE /api/finanzas/gastos/{id}`).
- Resumen del mes (`GET .../presupuestos/{anio}/{mes}`): gastos fijos y variables, gasto
  acumulado, saldo, disponible para gastar, ahorro logrado (saldo sin negativos), cumplimiento de
  la meta y distribución por categoría con porcentajes.
- Validaciones: importes negativos, no numéricos o con más de dos decimales; categoría y
  descripción obligatorias; fecha con formato AAAA-MM-DD y dentro del mes; campos extra → 422.
- Formato colombiano en la entrada: `2.000.000` y `1.500,50`. El punto solo se trata como
  separador de miles si agrupa de tres en tres.

## 6. Módulo de tareas

- Crear, editar, completar, eliminar. Prioridad alta/media/baja (la API) ↔ 1/2/3 (el motor).
- Fecha límite opcional. `dias_para_vencer` y `vencida` los calcula el servidor.
- Filtros por estado y prioridad (`GET /api/tareas?estado=&prioridad=`).
- Orden: el motor (`priority_key`), pendientes primero, luego prioridad y título.
- Resumen (`GET /api/tareas/resumen`): progreso en porcentaje, vencidas y próximas a vencer en 7 días
  (solo pendientes).

## 7. Interfaz

- Paleta del documento C4 (azul oscuro, violeta, cian, menta), tarjetas KPI, gráficas, estados
  vacíos, carga y mensajes de error y confirmación en español.
- Navegación lateral; en móvil y tableta, barra superior desplazable. Copiloto aparece como
  «Próximamente» deshabilitado, sin botón que aparente funcionar.
- Accesibilidad: etiquetas asociadas a cada campo, `aria-invalid`/`aria-describedby` en errores,
  barras de progreso con `role="progressbar"`, enlace «Saltar al contenido», `aria-current` en la
  navegación y foco visible.
- Los mensajes de validación de la API se traducen a español en un único manejador
  (`app/main.py`), así que la UI no depende de los mensajes de Pydantic.

## 8. Compatibilidad con las evidencias SENA

Los tres CLI (`backend/sena_cli/calificaciones.py`, `presupuesto.py`, `tareas.py`) no cambiaron.
Se ejecutan de forma independiente, sin base de datos, sin frontend y sin Internet. Las pruebas
`tests/test_cli_sena.py` siguen pasando. Los informes de evidencia no se han redactado.

## 9. Errores encontrados y corregidos durante la verificación

Estos defectos aparecieron al probar en navegador real; las pruebas de la API no los detectaban.

| Defecto | Causa | Corrección | Prueba de regresión |
|---|---|---|---|
| `sqlite3.ProgrammingError` en el servidor real | FastAPI crea la dependencia y ejecuta el endpoint en hilos distintos | `check_same_thread=False` (una conexión por petición, nunca compartida) | `test_conexion_sqlite_puede_usarse_desde_otro_hilo` (falla sin la corrección) |
| Tras crear una asignatura, la pantalla mostraba la anterior, y «Eliminar» podía borrar la equivocada | Recarga con un valor de `seleccionada` capturado antes de crear | El id abierto se guarda en una referencia (`useRef`) | Recorrido de navegador (crear + eliminar) |
| Mensajes de validación en inglés (`Input should be…`) | Errores de Pydantic sin traducir | Manejador `RequestValidationError` en español | Verificado a mano con la API |
| Leyenda de la dona solapada en móvil | Columna de texto demasiado estrecha | Apilado en pantallas ≤ 600 px | Captura móvil revisada |

## 10. Decisiones

| # | Decisión | Motivo |
|---|---|---|
| D1 | Repositorios por operación, no un ORM | Igual que la Fase 01; el SQL queda visible y auditable. |
| D2 | Sin dependencias nuevas en Python ni en npm | `sqlite3` es de la biblioteca estándar; gráficas propias. |
| D3 | `Principal` (usuario + token opcional) en lugar del token | Permite el modo demo sin token y que SQLite filtre por `user_id`. |
| D4 | Modo demo con usuario fijo y sin contraseñas | El prompt prohíbe credenciales ficticias que aparenten autenticar. |
| D5 | Finanzas y tareas solo en SQLite (501 con Supabase) | Evita implementar PostgREST ahora; la respuesta es honesta. |
| D6 | Mes del presupuesto como `AAAA-MM` en la URL | Clave natural única por usuario y mes. |

## 11. Pendientes técnicos

1. **Supabase**: implementar los adaptadores PostgREST de presupuesto y tareas (las tablas ya existen
   en la migración `20261111120000`, pero `budget_expenses` y `tasks` no tienen `categoria`, `origen`
   ni `fecha_limite` en esa migración). Requiere una migración nueva, aplicada solo con autorización.
2. **Aislamiento en SQLite**: es un filtro de aplicación por `user_id`, sin RLS. Aceptable para
   desarrollo local; no sustituye a RLS en producción.
3. **Modo demo**: no hay límite de acceso más allá de `DEMO_MODE`. Usar solo en `127.0.0.1`.
4. **Edición de gastos** en la interfaz: la API existe (`PATCH`), la pantalla solo permite crear y
   eliminar.
5. **Documentación C4**: `docs/arquitectura-c4.html` no se ha actualizado; la arquitectura local
   está descrita aquí.
6. **Pruebas Playwright antiguas** (`frontend/e2e/smoke_*.py`, Fase 01): no se han ejecutado en esta
   fase y pueden esperar textos anteriores. La prueba nueva es `fase03_recorrido_demo.py`.
7. Sin límite de tasa en la API ni protección CSRF (la API usa Bearer y no cookies).
8. Sin commits ni despliegue en Render, según lo solicitado.
