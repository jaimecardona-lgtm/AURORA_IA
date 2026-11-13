# Fase 07 — Dataset de demostración y copiloto de doble interfaz

Pruebas: [PRUEBAS_FASE_07.md](PRUEBAS_FASE_07.md). Evidencias: `visual-evidence/fase-07/`.

Esta fase deja listos el sembrador de datos de demostración y el copiloto en dos interfaces (página completa y
widget flotante) con una única conversación. **No se ha insertado ningún dato en Supabase** y **no se ha
llamado a OpenRouter**. Lo que sigue dependiendo de Supabase real está señalado en §6.

## 1. Fase A: estado de la prueba A/B

La ejecución manual de `fase06c_supabase_real.py` terminó con resultados parciales (ver `PRUEBAS_FASE_06D.md` y la
carpeta `visual-evidence/fase-06d/20261112-194002/`):

| Prueba | Resultado |
|---|---|
| Inicio de sesión real de A y de B | ✅ ambas sesiones iniciadas |
| Datos de A creados desde la interfaz (asignatura, nota, presupuesto, gasto, tarea) | ✅ |
| Persistencia de los datos de A en PostgreSQL, leída con el JWT de A | ✅ (4 registros) |
| Datos de B desde la interfaz | ⛔ interrumpido: la ventana se cerró durante la creación |
| Aislamiento RLS cruzado A/B | ⏸ no ejecutado: depende de los datos de B |
| Dashboard y copiloto con datos reales | ⏸ no ejecutado |
| Persistencia tras reinicio | ⏸ no ejecutado |

**Un defecto del procedimiento:** el error de ventana cerrada durante la creación de datos de B se clasificó como
«error no controlado», no como ventana cerrada. Quedó corregido en el script: cualquier `TargetClosedError` se marca
como interrumpida.

**Registros que quedan en Supabase** (no se borran sin autorización): asignatura `06C-Cálculo A`, su nota, el gasto
`06C-Mercado A` del mes de noviembre y la tarea `06C-Entregar taller A`.

## 2. Sembrador reproducible (`backend/tools/seed_supabase.py`)

Carga datos ficticios para las cuentas de prueba. Se ejecuta en local y usa **solo los endpoints normales de FastAPI**
con el JWT del usuario que inicia sesión.

- **Dataset de la cuenta A**: seis asignaturas con entre dos y cuatro evaluaciones (algunas aprobadas, otras que
  requieren refuerzo), presupuesto de noviembre de 2026 con ingreso de 2.800.000 COP y meta de 500.000 COP,
  ocho gastos fijos y variables en seis categorías (suman 2.270.000 COP, saldo de 530.000 COP, meta cumplida), y
  diez tareas con prioridades alta, media y baja, estados pendiente y completada, y fechas vencidas, próximas y
  futuras.
- **Dataset de la cuenta B**: una asignatura con dos notas, un presupuesto, un gasto y una tarea, sin reutilizar
  ningún registro de A.
- **Prefijo `DEMO-AURORA-`**, seguido de la letra de la cuenta (`DEMO-AURORA-A-…`).
- **Idempotente**: busca cada registro antes de crearlo. Una segunda ejecución no duplica nada. El presupuesto usa
  un upsert y solo se cuenta como creado si el mes no existía.
- **Confirmación obligatoria**: pide escribir `SI` antes de insertar. `--plan` muestra lo que haría sin conectarse.
- **Credenciales**: la contraseña se pide con `getpass` y no se muestra ni se guarda. El JWT vive solo en memoria.
  No se usa `service_role`, no se borra nada y no se exportan sesiones.
- **Verificación**: al terminar, relee los datos por la API autenticada y muestra solo cantidades.

Pruebas con un servidor FastAPI simulado en memoria: forma del dataset, idempotencia, prefijo, uso exclusivo de
endpoints `/api/` y no ejecución sin confirmación. **Ninguna de estas pruebas toca Supabase.**

## 3. Copiloto: página completa

`frontend/src/pages/CopilotPage.tsx`, con:

- Cabecera con el estado del proveedor («SIMULADO · no es IA», «OpenRouter · modelo» o «Pendiente de configuración»),
  botones «Nueva conversación» y «Limpiar conversación».
- Panel lateral de conversaciones, ocultable. Se indica que son solo de esta sesión del navegador.
- Área de conversación con mensajes diferenciados por autor, procedencia de cada respuesta, datos usados y tokens.
- Selector de áreas (académico, finanzas, tareas), sugerencias por módulo y contador de caracteres.
- Renderizado seguro del texto del modelo: sin HTML, con párrafos, listas y negritas.

## 4. Widget flotante «Habla con AURORA ✦»

`frontend/src/copilot/CopilotWidget.tsx`, dentro del layout autenticado:

- Botón flotante inferior derecho; el panel tiene unos 400 px en escritorio y casi pantalla completa en móvil.
- Se abre y cierra sin cambiar de página. Escape lo cierra, y el foco vuelve al botón.
- Botón «Chat completo», que cierra el panel y abre la página completa **con la misma conversación**.
- No aparece sobre la página completa del copiloto ni en la pantalla de inicio de sesión.
- Sin ventanas ni pestañas nuevas.

## 5. Estado compartido

`frontend/src/copilot/CopilotProvider.tsx` (`CopilotProvider` + `useCopilot`):

- Una sola conversación para la página completa y el widget. Expandir o navegar entre secciones no pierde mensajes.
- Un único envío a la vez. Una pregunta genera exactamente una petición al backend.
- Solo se envía el historial de la conversación activa, en intercambios completos.
- Se reinicia al cambiar de cuenta (`userKey`), y al cerrar sesión se desmonta junto con la vista autenticada.
- Las respuestas que llegan después de un cambio de cuenta se descartan.
- Ningún token se guarda en el historial: las peticiones pasan por el cliente HTTP existente.

El backend del copiloto no cambia: el widget y la página usan el mismo endpoint, el mismo cliente y los mismos servicios.

## 6. Pendiente (no se ha hecho en esta fase)

- **Persistencia de conversaciones en PostgreSQL** (`ai_conversations`, `ai_messages`): no se han preparado ni la
  migración ni su verificación. Hasta entonces, las conversaciones viven solo en la sesión del navegador.
- **Botón «Cargar datos de demostración»**: no se ha añadido. El sembrador se ejecuta desde la línea de comandos.
- **Carga real del dataset en Supabase**: pendiente de confirmación tuya y de las cuentas A y B autenticadas.
- **Prueba de cierre de sesión y cambio de cuenta en el navegador con Supabase real**: pendiente.
- **OpenRouter real**: pendiente de la clave revocada, una clave nueva y tu autorización.
- **Aislamiento RLS con el dataset completo**: pendiente de la carga real.

## 7. Lo que no se ha cambiado

- Migraciones: no se han ejecutado ni modificado.
- Políticas RLS y permisos: sin cambios.
- SQLite: sin cambios de datos.
- Configuración de OpenRouter en `backend/.env`: sin cambios.
- Arquitectura C4: no cambia la topología; el diagrama no se ha modificado.
