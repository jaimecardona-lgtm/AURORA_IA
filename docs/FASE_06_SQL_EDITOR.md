# Fase 06 — Preparación del esquema PostgreSQL mediante SQL Editor

Proyecto Supabase: **AURORA_IA** (ref `<ref-del-proyecto>`).

Esta fase **no ejecuta nada contra Supabase**. Genera los scripts y deja el procedimiento
para que los ejecutes tú en el **SQL Editor del Dashboard** del proyecto AURORA_IA.

**Decisión:** no se usa Supabase CLI para conectarse a ninguna base remota (`supabase login`,
`link`, `db push`, `db reset` no se han ejecutado ni se deben ejecutar aquí). Hay otros proyectos
vinculados en tus terminales; el CLI podría apuntar al proyecto equivocado.

---

## 1. Qué hay y qué falta

| Tabla | Migración Fase 01 | Lo que usa la aplicación | Estado |
|---|---|---|---|
| `academic_subjects` | ✅ | `nombre`, `user_id`, marcas de tiempo | Completa |
| `grade_entries` | ✅ | `descripcion`, `nota NUMERIC(4,2)`, FK compuesta | Completa |
| `monthly_budgets` | ✅ | `anio`, `mes`, `ingreso`, `meta_ahorro` `NUMERIC(14,2)` | Completa |
| `budget_expenses` | ⚠️ sin `categoria` ni `fecha` | `categoria`, `fecha` (exigidos por la API) | **Falta** → complemento |
| `tasks` | ⚠️ sin `fecha_limite` | `fecha_limite` (vencimientos y próximas) | **Falta** → complemento |

Comparación con SQLite (migraciones `0001`/`0002`):

- Coinciden en nombres y restricciones de los campos de dominio.
- SQLite tiene además `origen` (`real`|`demo`) en todas las tablas. **No se añade a PostgreSQL**: los
  datos demo nunca deben llegar a la base remota. La aplicación trata una fila sin `origen` como `real`.
- Los importes: SQLite los guarda como `REAL` (riesgo de precisión documentado en la Fase 04). En PostgreSQL
  son `NUMERIC(14,2)`, exactos.

Comparación con modelos y servicios:

- Pydantic (`schemas/finance.py`, `schemas/tasks.py`) exige `categoria` (1–60), `fecha` (AAAA-MM-DD),
  `fecha_limite` opcional y `prioridad`/`estado` con sus valores permitidos. Las columnas nuevas recogen esos límites.
- Los repositorios PostgREST existen **solo para Académico**. Finanzas y tareas con Supabase responden 501
  (ver Fase 03). El esquema queda listo para cuando se escriba ese adaptador; hoy la aplicación no lo usa.

## 2. Riesgos detectados

1. **Migración original y reejecución:** la Fase 01 usa `create policy` sin `drop policy if exists`.
   Ejecutarla dos veces falla. Por eso el paso 0 comprueba antes qué existe.
2. **Coma flotante al escribir importes:** el backend envía los importes como números JSON
   (`float(Decimal)`). PostgREST los convierte a `NUMERIC`, normalmente sin pérdida para importes de dos
   decimales, pero es más seguro enviarlos como cadena decimal (`"1234.56"`). **Recomendado para la fase de
   adaptador PostgREST**; no se cambia ahora.
3. **Filas existentes:** el complemento añade `categoria` y `fecha` como `NOT NULL`. Si `budget_expenses`
   tiene filas sin esas columnas, la migración se **detiene con error** y no inventa valores.
4. **Migraciones fuera del historial del CLI:** ver §6.

## 3. Archivos y orden de ejecución

Ejecuta **en este orden**, en el SQL Editor de AURORA_IA, cada archivo en una consulta separada.

| Orden | Archivo | Tipo | Cuándo |
|---|---|---|---|
| **0** | `supabase/sql_editor/00_comprobar_estado_actual.sql` | Solo lectura | Siempre, primero |
| **1** | `supabase/migrations/20261111120000_fase01_dominio_rls.sql` | Crea tablas, RLS, permisos y políticas | **Solo si el paso 0 indica que las 5 tablas NO existen** |
| **2** | `supabase/migrations/20261112120000_fase06_complemento_dominio.sql` | Añade columnas e índices | Siempre que las columnas del paso 0 no aparezcan |
| **3** | `supabase/sql_editor/03_verificar_resultado.sql` | Solo lectura | Después del último script ejecutado |

**Interpretación del paso 0:**

- Las 5 tablas no existen → ejecutar el paso 1 y después el paso 2.
- Las 5 existen, pero `categoria`, `fecha` o `fecha_limite` no aparecen → saltar el paso 1 y ejecutar solo el paso 2.
- Todo aparece → no ejecutar nada; ir al paso 3.

**Resultado esperado del paso 3:** nueve filas con `ok = true`:
tablas existen; columnas requeridas presentes; importes exactos; índices requeridos; claves foráneas compuestas;
RLS habilitado y forzado; 4 políticas por tabla (20); anon sin permisos; authenticated con 20 permisos.

Si alguna fila sale `false`, **no sigas usando la base**: revisa esa comprobación antes de avanzar.

### Cómo ejecutar cada archivo

1. Abre el proyecto AURORA_IA en el Dashboard de Supabase → **SQL Editor** → **New query**.
2. Abre el archivo indicado en tu editor local, copia **todo** su contenido y pégalo.
3. Pulsa **Run**. Los paso 0 y 3 devuelven tablas de resultados; los paso 1 y 2 terminan sin filas.
4. Anota la hora y el resultado. Si hay un error, **no** lo reejecutes a ciegas: copia el mensaje y vuelve a ejecutar el paso 0.

## 4. Garantías de seguridad de los scripts

- **Ningún script contiene** `DROP`, `TRUNCATE`, `DELETE` ni `UPDATE` sobre datos.
- **No se modifican** las políticas RLS: el complemento no toca `create policy`, `drop policy` ni `revoke`.
  Las políticas son por fila (`auth.uid() = user_id`) y cubren las columnas nuevas.
- **No se modifican** los permisos de tabla: los `grant` de la Fase 01 ya aplican a las columnas añadidas.
- **No se tocan otros esquemas** (`auth`, `storage`, etc.) ni otros proyectos de Supabase.
- El complemento es **idempotente** (`add column if not exists`, `create index if not exists`) y **se detiene**
  si encuentra datos que no puede completar.

Verificado localmente con un PostgreSQL 18 temporal
de prueba, nunca con Supabase: aplicación completa, reejecución del complemento, verificación con nueve
comprobaciones `true`, prueba de la guarda con datos y la batería RLS existente (23 comprobaciones `OK`, 0 fallos).

## 5. Qué hacer si algo sale mal

- **No hay rollback automático.** No se incluyen scripts de reversión porque cualquier reversión sería
  destructiva. Si hace falta deshacer, se preparará un script específico, revisado y aprobado antes de ejecutarlo.
- Si el paso 1 falla a mitad, el propio SQL de la Fase 01 no es transaccional por completo: revisa el estado
  con el paso 0 antes de reintentar. No reejecutes el paso 1 si las tablas ya existen.
- Si el paso 2 se detiene con el error de «tiene filas», **no** borres filas. Revisa esos registros y decide con
  el equipo cómo completarlos (`categoria` y `fecha`).

## 6. Historial de migraciones y Supabase CLI (advertencia)

Las migraciones ejecutadas desde el **SQL Editor no quedan registradas** en el historial que mantiene Supabase
CLI (`supabase_migrations.schema_migrations`). Consecuencias si en el futuro usas el CLI sobre este proyecto:

- `supabase db push` intentaría aplicar `20261111120000` y `20261112120000` de nuevo. La primera fallaría al
  recrear las políticas, y la segunda sería inocua pero no está registrada.
- Por eso, **antes de usar el CLI contra este proyecto**, hay que reconciliar el historial.

Procedimiento de reconciliación **documentado, no ejecutado** (hacerlo solo cuando decidas usar el CLI, y solo
con el proyecto correcto seleccionado):

1. Vincular el CLI **únicamente** al proyecto `<ref-del-proyecto>` (comprobando el ref antes de confirmar).
2. Revisar `supabase migration list` para ver qué versiones figuran como pendientes.
3. Marcar como aplicadas, sin ejecutar SQL:
   - `supabase migration repair --status applied 20261111120000`
   - `supabase migration repair --status applied 20261112120000`
4. Confirmar con `supabase migration list` que no quedan pendientes.

No ejecutar `db reset`, que borra datos.

## 7. Limitaciones

- No se ha probado contra el proyecto remoto; la validación es local en PostgreSQL 18 con el stub de `auth`.
- El stub de `auth` simula `auth.uid()` y los roles `anon`/`authenticated`; en Supabase real vienen de la plataforma.
- Las pruebas RLS de `supabase/tests/rls_dominio_test.sql` están pensadas para PostgreSQL local con el stub.
  Pueden ejecutarse en el SQL Editor solo si creas datos de prueba de forma controlada; no se han ejecutado allí.
- Sin datos de demo en la base remota por diseño.
