# Pruebas — Fase 07D

Fecha: 2026-11-12 · Windows 11 · Chrome instalado · Python 3.12 · Node 22.

**Estado: parcial.** Las pruebas de regresión, responsive, widget y copiloto simulado están ejecutadas y en verde.
La integración real A/B con Supabase **no** se ha ejecutado: requiere tu inicio de sesión manual (ver §6).

## 1. Regresión (ejecutada)

| Prueba | Resultado |
|---|---|
| Pytest completo | ✅ **239 aprobadas** |
| TypeScript estricto (`npx tsc --noEmit`) | ✅ sin errores |
| Build de Vite (`npx vite build`) | ✅ compila (aviso de tamaño de chunk, ya existía) |
| CLI calificaciones (SENA) | ✅ exit 0 |
| CLI presupuesto (SENA) | ✅ exit 0 |
| CLI tareas (SENA) | ✅ exit 0 |
| Suite de la fase 07 (widget y copiloto, `fase07_ui.py`) | ✅ **26 de 26**, 4 peticiones al copiloto, sin duplicados |

La suite de la fase 07 se ejecutó contra la copia de la interfaz en `:5175`, que reenvía `/api` a un backend de
demostración con SQLite temporal y proveedor **SIMULADO**. No se llamó a OpenRouter.

## 2. Diagnóstico E2E

| Caso | Hallazgo | Resultado |
|---|---|---|
| Finanzas: «530.000 no encontrado» | Selector `get_by_label("Mes")` ambiguo (input + formulario). El componente muestra `$ 530.000` al cambiar a `2026-10`. | Selector corregido. Causa **probable** del fallo real; **por confirmar** en la próxima ejecución con Supabase. |
| Copiloto: placeholder «Escribe tu pregunta…» | El selector no coincide con el texto real de la página completa. El campo existe, está habilitado y visible. | Selectores por id (`#pregunta-copiloto`, `#pregunta-widget`). |

Validación de los selectores de 07C contra la interfaz real (sin login, backend de demostración):

| Comprobación | Resultado |
|---|---|
| Selector de mes queda en `2026-10` | ✅ PASS |
| KPI «Saldo» muestra `530.000` | ✅ PASS |
| Copiloto de la página: responde con SIMULADO, 1 petición | ✅ PASS |
| Copiloto del widget: responde con SIMULADO, 1 petición | ✅ PASS |
| Nombres `DEMO-AURORA-A-…` | ❌ esperado: la base de demostración no tiene esos registros |

## 3. Auditoría responsive (antes y después)

Herramienta: `frontend/e2e/fase07d_auditoria.py`. Evidencias: `visual-evidence/fase-07d/antes/` y `…/despues/`
(métricas en `metricas.json` de cada carpeta).

### 3.1 Copiloto completo

| Ancho | Antes: scroll vertical | Antes: campo entero en viewport | Después: scroll vertical | Después: campo entero |
|---|---|---|---|---|
| 390 px | 1.186 px | ❌ no | 0 | ✅ |
| 768 px | 715 px | ✅ | 0 | ✅ |
| 1366 px | 363 px | ❌ no | 0 | ✅ |
| 1440 px | 231 px | ✅ | 0 | ✅ |
| 1920 px | 51 px | ✅ | 0 | ✅ |

Después, ningún tamaño tiene desbordamiento horizontal ni controles solapados en el copiloto.

### 3.2 Resto de pantallas (Mi espacio, Académico, Finanzas, Tareas, widget)

- **Desbordamiento horizontal**: 0 px en los 30 casos (6 pantallas incluido el widget × 5 tamaños), antes y después.
- **Controles tapados al final de la página**: esta medición se añadió después de la línea base, así que «antes» no
  está medido con ese criterio. Lo que sí se midió antes: el lanzador tapaba «Agregar» y «Guardar presupuesto» en
  móvil (listado de pares). **Después, 0 casos.** Corrección: margen inferior de 96 px en `.content`.
- **Solapamientos al abrir la página** (en el inicio, sin desplazar): **9 casos, residuales**. Ninguno aparece al final
  de la página (ver arriba).
  - Lanzador flotante sobre un control de la parte inferior, en la posición de inicio: Académico 390 (2 casos
    verificados por listado de pares: campo «nueva asignatura» y botón «Agregar»), Finanzas 390 (botón
    «Guardar presupuesto», verificado), Mi espacio 1366 (enlace «Ver todas», verificado), Mi espacio 1920 y Finanzas
    1440 (no verificados individualmente tras el último cambio).
  - Widget abierto sobre el contenido de fondo: Widget 768, 1366, 1440 y 1920. Es el comportamiento esperado de un
    panel flotante; el contenido de fondo queda tapado mientras está abierto.
  - Acción pendiente: si quieres cero solapamientos en la posición de inicio, habría que ocultar el lanzador al
    llegar a la zona de controles, decisión de diseño que no he tomado sin tu visto bueno.
- **Texto menor de 12 px**: 0 en todas las mediciones.
- **Login** (sin credenciales): sin desbordamiento, scroll vertical 0, campos de 44 px y botón de 46 px en los cinco tamaños.

Nota: la línea base «antes» se midió con la definición anterior de la auditoría (que contaba los elementos del
carril móvil de navegación como «fuera del viewport»). Esos falsos positivos se excluyeron después; la comparación de
desbordamiento y del copiloto no depende de ese cambio.

## 4. Chat y widget (interacción)

Cubierto por la suite de la fase 07 (§1) y por la auditoría (§3):

| Comprobación | Resultado |
|---|---|
| Botón «Habla con AURORA» visible en páginas normales, esquina inferior derecha | ✅ |
| No aparece sobre el copiloto completo | ✅ |
| Se abre sin cambiar de página; el foco entra en el campo | ✅ |
| Escape cierra y devuelve el foco al botón | ✅ |
| Expandir: la conversación aparece en la página completa, sin pestañas nuevas | ✅ |
| Conversación compartida entre widget y página; sin duplicados (4 peticiones, 4 envíos) | ✅ |
| Historial conservado al navegar entre módulos | ✅ |
| Widget en móvil: panel casi a pantalla completa, campo visible | ✅ (captura `despues/widget_movil_390.png`) |
| Lanzador compacto en móvil con nombre accesible «Habla con AURORA» | ✅ (aria-label) |

## 5. Pruebas pendientes

| Prueba | Estado | Motivo |
|---|---|---|
| Ejecución real 07C con Supabase (A y B, una sola ventana) | ⏸ pendiente | Requiere tu inicio de sesión manual. Comando en §6. |
| Confirmación del fallo real de Finanzas | ⏸ pendiente | Se confirmará en la próxima ejecución real. |
| Persistencia tras reiniciar FastAPI | ⏸ pendiente | Fuera del alcance de 07D; se hará después de la ejecución real. |
| Pruebas de escritura cruzada A/B | ⏸ no solicitadas | Solo sobre registros descartables y con autorización. |
| OpenRouter real | ⏸ bloqueado | Sin autorización. |

## 6. Cómo ejecutar la integración real (cuando puedas)

Requiere el backend de Supabase en `:8000` y la interfaz en `:5173` (ya activos). Desde la raíz del repositorio:

```powershell
backend\.venv\Scripts\python.exe frontend\e2e\fase07c_verificacion.py visual-evidence\fase-07c
```

Recorrido: se abre una ventana; inicias sesión tú con la cuenta A; el script verifica A; pulsas «Cerrar sesión»;
inicias sesión tú con la cuenta B en la misma pestaña; el script verifica B, comprueba que ambos JWT siguen vigentes y
ejecuta el aislamiento RLS con dos clientes HTTP independientes. Solo hace peticiones `GET`. El resultado queda en
`visual-evidence/fase-07c/<marca>/resultados.json`, con estados `PASS`, `FAIL` o `NO_CONCLUYENTE`.

Si un JWT ya no es válido tras el cierre de sesión global, sus pruebas aparecerán como `NO_CONCLUYENTE`, no como
denegación RLS.

## 7. Evidencias

- `visual-evidence/fase-07d/antes/`: capturas y `metricas.json` de la línea base.
- `visual-evidence/fase-07d/despues/`: capturas y `metricas.json` tras los cambios.
- `visual-evidence/fase-07d/login/`: capturas y métricas de la pantalla de inicio de sesión.
- `visual-evidence/fase-07d/regresion/`: resultados de `fase07_ui.py` (`fase07_ui.json` y capturas).

## 8. Limitaciones

- Chrome en modo headless para la auditoría; la integración real usa Chrome visible.
- La auditoría usa la copia de demostración (datos ficticios de SQLite temporal), no Supabase.
- La conversación del copiloto sigue viviendo solo en la sesión del navegador (sin tablas `ai_*`).
- Los servidores temporales de diagnóstico (`:5175` y `:8766`) se detuvieron al terminar. No se tocaron otros
  procesos, incluidos los de otros proyectos.
