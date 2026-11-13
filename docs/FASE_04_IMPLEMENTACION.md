# Fase 04 — Dashboard premium, experiencia de usuario y analítica integrada

Resultados verificados: [PRUEBAS_FASE_04.md](PRUEBAS_FASE_04.md). Capturas: `visual-evidence/fase-04/`.

Esta fase mejora la experiencia sobre la base de la Fase 03 (React → FastAPI → SQLite local). No
conecta Supabase ni OpenRouter, no despliega en Render y no hace commits.

---

## 1. Auditoría previa

- Git: sin commits nuevos; cambios sin seguir de las fases anteriores (no tocados por esta fase).
- Línea base antes de los cambios: **167 pruebas pytest en verde** y build de Vite correcto.
- Pantallas revisadas en Chrome antes de rediseñar: navegación sin iconos, Mi espacio inexistente,
  eliminación de notas sin confirmación, edición de gastos ausente, transacciones en lista simple.
- Documento de arquitectura: el prompt se refiere a `docs/arquitectura-c4.html`, pero el original del
  repositorio es `docs/AURORA_AI_Arquitectura_C4.html`. Se mantiene intacto y la versión actualizada
  se creó como `docs/arquitectura-c4.html`.

## 2. Panel general (Mi espacio)

**Endpoint nuevo:** `GET /api/dashboard?anio=&mes=`, implementado en `services/dashboard_service.py`.
Solo **compone** los servicios existentes; no añade reglas:

| Bloque | Origen |
|---|---|
| Promedio general, aprobadas, reprobadas, bajo rendimiento | `AcademicService.academic_summary`, `list_subjects` y `core.grades.is_passing` |
| Saldo, gasto acumulado, ahorro logrado, % de meta, categorías | `BudgetService.get_budget` (motor `core.budget`) |
| Pendientes, completadas, vencidas, próximas (7 días), prioridades | `TaskService.summary` y `list_tasks` (motor `core.tasks`) |

- Si un módulo no tiene adaptador con la persistencia activa (finanzas y tareas con Supabase), el
  bloque llega con `disponible: false`. No se inventa ninguna cifra.
- Porcentaje de meta de ahorro = ahorro logrado / meta × 100, sin tope en el dato (la barra sí se
  recorta en la interfaz).
- Tareas próximas: el total (`proximas_total`) es independiente de la lista recortada a 5 elementos.

**Interfaz** (`pages/OverviewPage.tsx`): seis indicadores (promedio, aprobadas, saldo, meta de
ahorro, pendientes, próximas a vencer), gráfica de rendimiento por asignatura, dona de gastos por
categoría, progreso de tareas con pendientes por prioridad, lista de próximas tareas, estado
financiero del mes, accesos rápidos y tarjeta del Copiloto marcada como **Próximamente**, sin
respuestas simuladas y sin ninguna conexión.

## 3. Sistema visual

- Tokens de color en `:root` (paleta del C4): azul noche, violeta, cian, menta y naranja para avisos.
- Iconografía propia en SVG (`components/icons.tsx`), sin dependencias nuevas.
- Cabecera con estado del entorno: «Demo local · SQLite» o el entorno de producción, y aviso visible
  **MODO DEMO LOCAL** mientras el servidor esté en demo.
- Tarjetas con borde superior de color, tipografía jerárquica y prioridades con borde lateral de color
  y etiqueta de texto (no solo color).
- Animaciones suaves, desactivadas con `prefers-reduced-motion`.
- Responsive: rejilla de dos columnas en tabletas, un bloque en móvil. La tabla de transacciones se
  convierte en tarjetas por debajo de 640 px, sin desplazamiento horizontal de la página.

## 4. Módulo académico

- Se mantienen todas las funciones anteriores.
- Eliminar una nota pide confirmación en dos pasos.
- Gráfica «Notas por evaluación (0 a 5)» de la asignatura abierta.
- Aviso visible: «Todas las notas de una asignatura pesan igual: las ponderaciones aún no están
  implementadas».
- Defecto corregido en la validación: ver §7.

## 5. Módulo financiero

- Selector de mes (se mantiene) y tarjetas de ingreso, gasto, saldo y ahorro.
- Distribución por categoría (dona y barras) y **comparación fijos frente a variables**.
- **Visualización de la meta de ahorro**: barra del avance y cifras reales.
- **Tabla de transacciones** con edición desde React usando el endpoint PATCH existente. La edición
  valida importes, descripción, categoría y que la fecha pertenezca al mes.
- Entrada en formato colombiano (`2.000.000`, `1.500,50`) y valores del presupuesto formateados.

### 5.1 Precisión monetaria: riesgos y transición propuesta

**Medición realizada** (SQLite, columna `REAL`, mismo tipo que usa la migración 0002):

| Valor enviado | Valor almacenado | Exacto |
|---|---|---|
| 0.10 | 0.1 | sí |
| 1234567.89 | 1234567.89 | sí |
| 12345678901234.56 | 12345678901234.56 | sí |
| **99999999999999.99** (máximo de `NUMERIC(14,2)`) | **99999999999999.98** | **no** (−0,01) |

Suma de diez `0.10` en SQL: `1.0` (en este caso exacto, pero la suma binaria no está garantizada en
general).

**Riesgos:**
1. Un `REAL` tiene unos 15–16 dígitos significativos; los importes del esquema llegan a 16. Un
   importe muy grande puede guardarse con un centavo de error.
2. Las agregaciones hechas en SQL (`SUM`) acumulan error binario. Hoy el backend suma en `Decimal`
   a partir de cadenas, así que el riesgo se limita a futuras consultas SQL directas.
3. En PostgreSQL (Supabase) los importes ya son `NUMERIC(14,2)`, exactos. El riesgo es solo de la
   capa SQLite de desarrollo.

**Transición propuesta (no ejecutada, sin migraciones destructivas):**
1. **Migración aditiva `0003`**: añadir `monto_centavos INTEGER` (y `ingreso_centavos`,
   `meta_ahorro_centavos`) sin borrar las columnas `REAL`.
2. **Relleno controlado** con un script de Python que calcule `ROUND(monto * 100)` con `Decimal` a
   partir del texto, verifique cada fila (diferencia cero) y deje un informe. Las filas que no
   cuadren se listan y no se modifican.
3. **Lectura dual en la aplicación**: el repositorio usa `*_centavos` cuando existe y el motor
   sigue recibiendo `Decimal`. Las pruebas comparan ambos caminos.
4. **Retirada de las columnas REAL** en una fase posterior, con copia de seguridad previa, solo con
   autorización explícita.

Estado: propuesta documentada; no se ha aplicado ninguna migración.

## 6. Módulo de tareas

- Prioridades visuales (color más etiqueta de texto) en la lista y en el panel general.
- Filtros por estado y prioridad (se mantienen), edición, finalización y eliminación con confirmación.
- Fechas límite y vencidas calculadas por el backend; la interfaz no las recalcula.
- Progreso con porcentaje y barra accesible.

## 7. Defectos encontrados y corregidos

| # | Defecto | Cómo se detectó | Corrección |
|---|---|---|---|
| 1 | La tarjeta «Meta de ahorro» mostraba 100 % aunque el avance era 217 % | Revisión visual de la captura de escritorio | Se muestra el valor real; la barra se recorta a 100 % |
| 2 | Una nota válida como «4,10» se rechazaba («Usa como máximo dos decimales») | Prueba de navegador: no llegaba ninguna petición al servidor | La comprobación se hace sobre el texto, no con `× 100` (que da `410.00000000000006` en binario) |
| 3 | Los botones de vista actual/objetivo del C4 usaban la clase de las pestañas y disparaban `render(undefined)` | Prueba del diagrama en Chrome | Clase propia y estilo propio |
| 4 | Las pruebas dependían de variables exportadas en el shell; con `DEMO_MODE=true` fallaban 9 | Ejecución de pytest tras las pruebas de servidor | Fixture `autouse` que aísla el entorno en `tests/conftest.py` |
| 5 | Los importes del presupuesto aparecían como `2500000.00` | Captura móvil de Finanzas | Formato es-CO en el campo; el backend sigue aceptando el valor |
| 6 | En móvil, la leyenda de la dona se solapaba | Captura móvil (fase anterior, corregida y comprobada) | Apilado en pantallas pequeñas |

Errores de fases anteriores (fase 03): el recorrido de Fase 03 encontró el fallo de hilos de SQLite y
el borrado de la asignatura equivocada; ambos siguen corregidos.

## 8. Arquitectura C4

`docs/arquitectura-c4.html` (nuevo, a partir del original) muestra dos vistas:

- **Actual · local verificada**: React → FastAPI → SQLite. Supabase y OpenRouter aparecen como
  **NO CONECTADO** con línea punteada.
- **Objetivo · propuesta**: React → FastAPI → Supabase PostgreSQL / Supabase Auth → OpenRouter, con la
  etiqueta «PROPUESTA, NO IMPLEMENTADA».

El original `docs/AURORA_AI_Arquitectura_C4.html` no se ha modificado.

## 9. Riesgos abiertos

1. Precisión de importes en SQLite (§5.1): pendiente de la migración aditiva propuesta.
2. Las finanzas y las tareas siguen sin adaptador PostgREST: con Supabase aparecen como no disponibles.
3. El aislamiento por `user_id` de SQLite es de aplicación, no RLS.
4. Un solo navegador probado (Chrome). No se ha probado en Firefox, Safari ni dispositivos reales.
5. Las pruebas Playwright de fases anteriores (`frontend/e2e/smoke_*.py`, `fase03_recorrido_demo.py`) no se han vuelto a ejecutar en esta fase; la prueba vigente es `fase04_recorrido.py`.
6. Sin commits ni despliegue, según lo pedido.

## 10. Lo que no se ha hecho (por instrucción)

- Conexión a Supabase, integración con OpenRouter, despliegue en Render, commits y push.
- Informe AA2-EV01 y video AA2-EV02.
- Migraciones destructivas o reinicio de bases con datos.
