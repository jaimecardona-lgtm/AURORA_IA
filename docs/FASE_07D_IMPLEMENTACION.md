# Fase 07D — Auditoría visual, responsive y corrección E2E

Pruebas y resultados: [PRUEBAS_FASE_07D.md](PRUEBAS_FASE_07D.md). Evidencias: `visual-evidence/fase-07d/`.

Esta fase no carga datos, no modifica registros remotos, no usa `service_role` ni migraciones, no llama a OpenRouter
y no hace commits. Los datos de Supabase no se tocaron.

## 1. Diagnóstico de los dos errores E2E

### 1.1 Finanzas: «no se encuentra 530.000»

Causa comprobada: **selector de prueba defectuoso**, no un fallo del componente.

- `get_by_label("Mes")` (coincidencia parcial) devuelve dos elementos: el `input#periodo` y el `form` del presupuesto,
  cuyo `aria-labelledby` apunta a «Presupuesto del mes». Un selector ambiguo no se puede usar para escribir el mes.
- Reproducción con el componente real (backend de demostración con una base SQLite temporal con los importes de la
  cuenta A en octubre: ingreso 2.800.000, meta 500.000, gastos 2.270.000): al escribir `2026-10` en `#periodo`, la app
  pide `/api/finanzas/presupuestos/2026/10` y el KPI «Saldo» muestra `$ 530.000` visible.
- El texto usa un espacio no separable (U+00A0) entre `$` y la cifra. `Intl` con `es-CO` produce `$ 530.000`; la
  subcadena `530.000` aparece, así que la comprobación de texto es válida si se acota.
- **Limitación:** en la ejecución real de 07C (`visual-evidence/fase-07c/20261112-233849`) el fallo no aparece como
  «elemento ambiguo» sino como «no encontrado». No he podido reproducir esa ejecución contra Supabase (requiere tu
  inicio de sesión). La causa más probable es el selector ambiguo, pero queda **por confirmar** en la próxima ejecución real.

Corrección en `frontend/e2e/fase07c_verificacion.py`:
- El mes se escribe en `#periodo` y se comprueba que el valor queda en `2026-10`.
- El saldo se busca dentro del KPI «Saldo», no en todo el documento.

### 1.2 Copiloto: `get_by_placeholder("Escribe tu pregunta…")` agota el tiempo

Causa comprobada: **selector incorrecto**. El campo sí existe, está habilitado, es visible y queda dentro del viewport.

| Elemento | Placeholder real | Id |
|---|---|---|
| Página completa | `Escribe tu pregunta. Enter envía; Shift+Enter, nueva línea.` | `pregunta-copiloto` |
| Widget | `Escribe tu pregunta…` | `pregunta-widget` |

El selector de la prueba buscaba el texto del widget con el carácter de puntos suspensivos, pero en la página
completa el texto es distinto. Ahora la prueba usa los identificadores estables.

## 2. Layout del copiloto

Problema medido (antes): la página necesitaba 1.186 px de scroll en móvil y 231 px en escritorio 1440. El campo de
escritura quedaba fuera del viewport a 390 px y a 1366 px. Causa: `.copiloto__cuerpo` usaba `align-items: stretch`
y la columna de datos empujaba el chat hacia abajo.

Cambios (`frontend/src/styles.css`, bloque «Fase 07D», y `CopilotPage.tsx`):

- **Altura de pantalla** sin números mágicos: `:has(.copiloto--completo)` convierte la cadena de flex de la cáscara
  (`.app` → `.layout` → `.content` → `.module`) en una altura de `100dvh`, solo en la página del copiloto.
- **Chat con scroll interno**: la lista de mensajes ocupa `flex: 1` con `min-height: 0` y el campo queda en la parte
  inferior con `flex: 0 0 auto`.
- **Paneles con scroll propio**: conversaciones y datos tienen `overflow-y: auto` y `min-height: 0`.
- **Escritorio**: tres columnas (conversaciones 232 px, chat, datos 272 px).
- **Tableta y móvil (≤ 1000 px)**: el chat ocupa todo el espacio. Conversaciones y «Datos y sugerencias» son hojas
  plegables que se abren con su botón (`aria-expanded`, `aria-controls`). Empiezan plegadas.
- `html { scroll-padding-top: 88px }`: el foco y las anclas no quedan bajo la barra superior fija.

Resultado medido: sin scroll vertical de página ni desbordamiento horizontal en 390, 768, 1366, 1440 y 1920 px; el campo
de escritura queda entero dentro del viewport en los cinco tamaños.

## 3. Auditoría responsive y widget

Herramienta: `frontend/e2e/fase07d_auditoria.py` (Chrome headless, sin login, sin escrituras). Mide por pantalla y
tamaño: desbordamiento horizontal, elementos fuera del viewport (excluyendo carriles con desplazamiento propio),
pares de controles solapados, texto menor de 12 px, campo del copiloto y scroll vertical. Además mide los solapamientos
**al final de la página**, que es lo que el usuario alcanza al desplazarse.

Hallazgos corregidos:

- **El lanzador «Habla con AURORA ✦» tapaba controles** (Agregar, Guardar presupuesto, Ver todas). Se corrigió con
  un margen inferior de 96 px en `.content` (en todas las páginas salvo el copiloto, que no muestra el lanzador) y con un
  lanzador compacto de 52 px en móvil. El nombre accesible sigue siendo «Habla con AURORA» (`aria-label`).
- **Título del widget partido en tres líneas**: ahora una línea con elipsis.
- **Barra superior fija que tapaba el encabezado del copiloto** en móvil: resuelto con la altura controlada del copiloto
  y `scroll-padding-top`.
- **Falsos positivos de la auditoría**: los elementos dentro de la barra de navegación móvil (carril con
  desplazamiento horizontal) se marcaban como «fuera del viewport». Ahora se excluyen los contenedores con
  desplazamiento propio.

Nota sobre la comparación: la línea base «antes» se tomó con la definición anterior de la auditoría y el CSS original.
Las cifras de solapamiento de la línea base se verificaron además con un listado de pares concretos antes de cambiar
nada.

Pantalla de inicio de sesión: sin desbordamiento en los cinco tamaños, campos de 44 px y botón de 46 px.

## 4. Chat flotante

- Se abre desde las páginas normales, no aparece sobre el copiloto completo (comprobado por la suite de la fase 07).
- Escape cierra y devuelve el foco al botón (comprobado).
- Expandir abre la página completa **en la misma pestaña** y conserva la conversación.
- Sin cambios en el backend del copiloto.

## 5. Ajuste de la prueba 07C

`frontend/e2e/fase07c_verificacion.py`:

- Selectores por identificador: `#periodo`, `#pregunta-copiloto`, `#pregunta-widget`. Sin `get_by_label("Mes")` ni
  `get_by_placeholder` ambiguos.
- Comprobación de que los dos JWT siguen vigentes **antes** del RLS (`GET /api/subjects`). El logout de la aplicación
  usa alcance global, así que un token rechazado (401/403) se registra como **NO_CONCLUYENTE**, nunca como
  denegación RLS correcta. Si un token no está vigente, sus pruebas RLS y de estado del copiloto se marcan como no
  concluyentes.
- El JSON incluye el recuento de `no_concluyentes` y el estado de la ejecución.
- Sigue en una sola ventana, con autenticación secuencial A/B y sin escrituras remotas.

## 6. Lo que no cambió

- Backend del copiloto y de finanzas: sin cambios.
- Migraciones, políticas RLS y permisos: sin cambios.
- Datos de Supabase y de SQLite: sin cambios. Los 48 registros DEMO-AURORA- no se tocaron.
- OpenRouter: no se ha llamado.
- Git: sin commits ni push.
