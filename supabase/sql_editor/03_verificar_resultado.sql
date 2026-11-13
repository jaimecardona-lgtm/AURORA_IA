-- =============================================================================
-- PASO 3 · Verificación posterior (SOLO LECTURA)
-- Ejecutar después de las migraciones. Cada fila devuelve ok = true o false.
-- No modifica nada. Todas las comprobaciones deben dar true.
-- =============================================================================

with
-- Tablas esperadas
tablas_esperadas(tabla) as (values
  ('academic_subjects'), ('grade_entries'), ('monthly_budgets'), ('budget_expenses'), ('tasks')
),
-- Columnas que necesita la aplicación (nombre y tipo)
columnas_esperadas(tabla, columna, tipo_esperado) as (values
  ('academic_subjects', 'id', 'uuid'),
  ('academic_subjects', 'user_id', 'uuid'),
  ('academic_subjects', 'nombre', 'text'),
  ('academic_subjects', 'created_at', 'timestamp with time zone'),
  ('academic_subjects', 'updated_at', 'timestamp with time zone'),
  ('grade_entries', 'id', 'uuid'),
  ('grade_entries', 'user_id', 'uuid'),
  ('grade_entries', 'subject_id', 'uuid'),
  ('grade_entries', 'descripcion', 'text'),
  ('grade_entries', 'nota', 'numeric'),
  ('monthly_budgets', 'id', 'uuid'),
  ('monthly_budgets', 'user_id', 'uuid'),
  ('monthly_budgets', 'anio', 'smallint'),
  ('monthly_budgets', 'mes', 'smallint'),
  ('monthly_budgets', 'ingreso', 'numeric'),
  ('monthly_budgets', 'meta_ahorro', 'numeric'),
  ('budget_expenses', 'id', 'uuid'),
  ('budget_expenses', 'user_id', 'uuid'),
  ('budget_expenses', 'budget_id', 'uuid'),
  ('budget_expenses', 'descripcion', 'text'),
  ('budget_expenses', 'categoria', 'text'),
  ('budget_expenses', 'monto', 'numeric'),
  ('budget_expenses', 'tipo', 'text'),
  ('budget_expenses', 'fecha', 'date'),
  ('tasks', 'id', 'uuid'),
  ('tasks', 'user_id', 'uuid'),
  ('tasks', 'titulo', 'text'),
  ('tasks', 'prioridad', 'smallint'),
  ('tasks', 'estado', 'text'),
  ('tasks', 'fecha_limite', 'date')
),
-- Índices que la aplicación necesita para sus consultas
indices_esperados(nombre) as (values
  ('academic_subjects_user_nombre_key'),
  ('grade_entries_user_subject_idx'),
  ('budget_expenses_user_budget_idx'),
  ('budget_expenses_user_fecha_idx'),
  ('tasks_user_estado_prioridad_idx'),
  ('tasks_user_fecha_limite_pendiente_idx')
),
-- Restricciones de clave foránea compuesta (aislamiento entre usuarios)
fk_esperadas(nombre) as (values
  ('grade_entries_subject_same_user_fk'),
  ('budget_expenses_budget_same_user_fk')
),
tablas_rls as (
  select c.relname, c.relrowsecurity, c.relforcerowsecurity
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relname in (select tabla from tablas_esperadas)
),
politicas as (
  select tablename, count(*) as n
  from pg_policies
  where schemaname = 'public' and tablename in (select tabla from tablas_esperadas)
  group by tablename
),
permisos_anon as (
  select count(*) as n
  from information_schema.role_table_grants
  where grantee = 'anon' and table_schema = 'public'
    and table_name in (select tabla from tablas_esperadas)
),
permisos_auth as (
  select count(*) as n
  from information_schema.role_table_grants
  where grantee = 'authenticated' and table_schema = 'public'
    and table_name in (select tabla from tablas_esperadas)
    and privilege_type in ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
),
numeric_ok as (
  select
    (select numeric_precision || ',' || numeric_scale from information_schema.columns
      where table_schema='public' and table_name='grade_entries' and column_name='nota') = '4,2'
    and (select numeric_precision || ',' || numeric_scale from information_schema.columns
      where table_schema='public' and table_name='monthly_budgets' and column_name='ingreso') = '14,2'
    and (select numeric_precision || ',' || numeric_scale from information_schema.columns
      where table_schema='public' and table_name='budget_expenses' and column_name='monto') = '14,2'
    as ok
)
select 'tablas existen' as comprobacion,
       (select count(*) from tablas_esperadas t
          where to_regclass('public.' || t.tabla) is not null) = 5 as ok
union all
select 'columnas requeridas presentes',
       (select count(*) from columnas_esperadas e
          where exists (select 1 from information_schema.columns c
                         where c.table_schema = 'public' and c.table_name = e.tabla and c.column_name = e.columna
                           and c.data_type = e.tipo_esperado)) = (select count(*) from columnas_esperadas)
union all
select 'importes exactos NUMERIC (nota 4,2; dinero 14,2)', (select ok from numeric_ok)
union all
select 'índices requeridos presentes',
       (select count(*) from indices_esperados i
          where exists (select 1 from pg_indexes x where x.schemaname = 'public' and x.indexname = i.nombre)) = (select count(*) from indices_esperados)
union all
select 'claves foráneas compuestas presentes',
       (select count(*) from fk_esperadas f
          where exists (select 1 from pg_constraint k where k.conname = f.nombre and k.contype = 'f')) = (select count(*) from fk_esperadas)
union all
select 'RLS habilitado y forzado en las 5 tablas',
       (select count(*) from tablas_rls where relrowsecurity and relforcerowsecurity) = 5
union all
select 'políticas RLS: 4 por tabla (20 en total)',
       (select coalesce(sum(n), 0) from politicas) = 20 and (select count(*) from politicas where n = 4) = 5
union all
select 'anon sin permisos sobre el dominio', (select n from permisos_anon) = 0
union all
select 'authenticated con SELECT/INSERT/UPDATE/DELETE (20 permisos)', (select n from permisos_auth) = 20
order by comprobacion;

-- Resumen para leer de un vistazo: el total de comprobaciones fallidas debe ser 0.
-- (Si alguna fila sale false, no continuar: revisar antes de usar la aplicación.)
