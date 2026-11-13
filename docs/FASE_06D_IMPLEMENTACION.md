# Fase 06D — Estabilización del procedimiento Playwright y rediseño responsive

Pruebas: [PRUEBAS_FASE_06D.md](PRUEBAS_FASE_06D.md). Evidencias: `visual-evidence/fase-06d/`.

Esta fase corrige el procedimiento de autenticación real, auditó la distribución responsive del dashboard y
dejó lista la ejecución manual con las cuentas A y B. **La ejecución real con ambas cuentas no se ha completado
en esta sesión**: requiere que inicies sesión tú en las ventanas de Chrome.

## 1. Origen del `TargetClosedError`

- El script abría las dos ventanas y esperaba el inicio de sesión con `page.wait_for`.
- Si cerrabas una ventana antes de terminar, Playwright lanzaba `TargetClosedError`.
- **El error no estaba controlado**: no había ningún `try/except` alrededor de la espera, así que la excepción
  llegaba a `main()` y terminaba el proceso, cerrando también la otra ventana.
- Además, cada contexto usaba un viewport fijo de 1280×860, independiente del tamaño real de la ventana.

## 2. Cambios en `frontend/e2e/fase06c_supabase_real.py`

- **Autenticación secuencial:** primero A; B se abre solo después de autenticar A.
- **Aislamiento:** cada cuenta usa su propio contexto (`Sesion`), con cookies y almacenamiento independientes.
- **Cierre controlado:** si una ventana se cierra, el script detecta `TargetClosedError` y pregunta en la
  terminal si reabrir esa cuenta. Si dices que no, la prueba se marca como INTERRUMPIDA.
- **Sin falsos aprobados:** una prueba interrumpida nunca se registra como PASS.
- **Sin ventana fija:** los contextos usan `no_viewport=True`; el tamaño lo marca la ventana.
- **Errores no controlados:** se registran en el JSON en lugar de perder la evidencia parcial.
- **Un JSON por ejecución:** `visual-evidence/fase-06d/<marca-de-tiempo>/resultados.json`, junto con
  `ids_prueba.json`, que solo contiene identificadores de registros, sin tokens ni contraseñas.
- **Sin credenciales:** el script no pide, no guarda y no exporta contraseñas ni estados de sesión.
  Los tokens viven en memoria del proceso y nunca se imprimen.
- **Datos de las tres áreas:** crea asignatura, nota, presupuesto, gasto y tarea para A y para B, todos con el
  prefijo `06C-`.

## 3. Auditoría responsive

Se midió con `frontend/e2e/fase06d_responsive.py`, con viewports explícitos independientes en cinco tamaños:
390×844, 768×1024, 1366×768, 1440×900 y 1920×1080. Para cada módulo se registran `innerWidth`, `outerWidth`,
`clientWidth` y `scrollWidth`, además del ancho del contenido y el número de columnas de los indicadores.

Antes de los cambios se encontraron dos defectos de distribución, confirmados en la captura de 1920 px:

1. **Franja vacía a la derecha:** `.module` tenía `max-width: 1200px`, y en pantallas grandes el contenido
   quedaba en una columna estrecha con hueco lateral.
2. **Indicadores desequilibrados:** la rejilla de seis indicadores usaba `auto-fit`, y a 1920 px calculaba
   siete columnas para seis elementos, con una columna vacía.

Ninguno de los dos era un desbordamiento horizontal: en las 20 mediciones iniciales el `scrollWidth` coincidía con
el `clientWidth`. Por eso no se confundió con un defecto del viewport.

**Correcciones** (en `frontend/src/styles.css`, bloque «Fase 06D»):

- `.module`: `max-width: 1480px; width: 100%`. El contenido ocupa el ancho disponible.
- `.kpis--seis`: seis columnas por defecto; tres por debajo de 1280 px; dos por debajo de 760 px.
- El dashboard conserva dos columnas de tarjetas por encima de 1100 px y una por debajo, como antes.

Después de los cambios, en las 20 mediciones: sin desbordamiento horizontal, seis indicadores equilibrados en
escritorio, tres por fila en tableta y dos en móvil.

Los estados vacíos del dashboard ya muestran un mensaje y una acción, sin cifras ficticias. **Mejorar su
presentación visual queda pendiente**: no se ha rediseñado en esta fase.

## 4. Copiloto

- El módulo aparece en la navegación y en el panel general.
- El procedimiento incluye comprobaciones del copiloto del puerto 8001 con el JWT de cada cuenta. Las respuestas
  se declaran SIMULADAS. **Aún no se han ejecutado con éxito contra Supabase**: la última ejecución se interrumpió
  al inicio. No se llama a OpenRouter.
- No se ha añadido ninguna ruta del modo simulado a producción: `validate_runtime` lo impide.

## 5. Lo que no se ha cambiado

- Migraciones: no se han vuelto a ejecutar.
- Políticas RLS y permisos: no se han modificado.
- SQLite: no se ha borrado ni tocado la base del puerto 8765.
- OpenRouter: sin llamadas, sin cambios de configuración.

## 6. Pendiente (requiere tu ejecución manual)

Ejecuta el procedimiento en PowerShell, desde la raíz del repositorio:

```powershell
python frontend\e2e\fase06c_supabase_real.py visual-evidence\fase-06d
```

- Se abrirá la ventana de la cuenta A. Introduce sus credenciales. Cuando veas «Cerrar sesión», el script continúa.
- Después se abrirá la ventana de la cuenta B. Haz lo mismo.
- Las pruebas RLS cruzadas y la lectura de datos se ejecutan automáticamente.
- No cierres las ventanas durante la ejecución. Si lo haces, el script preguntará si quieres reabrirlas, y la
  prueba no contará como aprobada.

Después de la ejecución, la persistencia tras reiniciar se comprueba reiniciando el backend y repitiendo las lecturas.
