-- =============================================================================
-- PASO 0 · Comprobación previa (SOLO LECTURA)
-- Ejecutar primero en el SQL Editor del proyecto AURORA_IA.
-- No modifica nada. Muestra qué tablas y columnas ya existen.
-- =============================================================================

select
  t.tabla,
  to_regclass('public.' || t.tabla) is not null as existe
from (values
  ('academic_subjects'),
  ('grade_entries'),
  ('monthly_budgets'),
  ('budget_expenses'),
  ('tasks')
) as t(tabla)
order by t.tabla;

select
  table_name,
  column_name,
  data_type
from information_schema.columns
where table_schema = 'public'
  and (
    (table_name = 'budget_expenses' and column_name in ('categoria', 'fecha'))
    or (table_name = 'tasks' and column_name = 'fecha_limite')
  )
order by table_name, column_name;

-- Filas existentes (solo conteo). Las columnas nuevas solo se añaden sin pérdida si esto es 0.
select
  case when to_regclass('public.budget_expenses') is not null
       then (select count(*) from public.budget_expenses) end as filas_budget_expenses,
  case when to_regclass('public.tasks') is not null
       then (select count(*) from public.tasks) end as filas_tasks;

-- INTERPRETACIÓN:
--   * Si las 5 tablas NO existen  -> ejecutar después 20261111120000_fase01_dominio_rls.sql
--   * Si las 5 existen y las columnas categoria/fecha/fecha_limite NO aparecen
--                                 -> saltar la Fase 01 y ejecutar 20261112120000_fase06_complemento_dominio.sql
--   * Si todo aparece ya            -> no ejecutar nada; ir al script 03 de verificación
