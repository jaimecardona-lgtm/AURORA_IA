-- =============================================================================
-- AURORA AI · Fase 06 · Complemento incremental del dominio (NO destructivo)
--
-- Requiere haber aplicado antes: 20261111120000_fase01_dominio_rls.sql
--
-- Qué añade (lo que usa la aplicación y falta en la Fase 01):
--   * budget_expenses.categoria  text NOT NULL  (1–60 caracteres)
--   * budget_expenses.fecha      date NOT NULL  (fecha del gasto)
--   * tasks.fecha_limite         date NULL      (fecha límite opcional)
--   * índices para consultas por fecha
--
-- Qué NO hace:
--   * No borra tablas, columnas, filas, políticas ni permisos.
--   * No modifica las políticas RLS: son por fila (auth.uid() = user_id) y ya cubren
--     las columnas nuevas. Los permisos de tabla también cubren las columnas nuevas.
--   * No añade la columna SQLite "origen": los datos demo no deben llegar a Supabase.
--
-- Seguridad frente a datos existentes:
--   Si budget_expenses ya tiene filas y aún no existe categoria o fecha, la migración
--   se detiene con un error en lugar de inventar valores.
--
-- Idempotente: puede ejecutarse de nuevo sin efectos adicionales.
-- =============================================================================

do $$
begin
  if not exists (
       select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'budget_expenses' and column_name = 'categoria')
     and exists (select 1 from public.budget_expenses) then
    raise exception 'budget_expenses tiene filas y no tiene categoria: revisa los datos antes de continuar.';
  end if;

  if not exists (
       select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'budget_expenses' and column_name = 'fecha')
     and exists (select 1 from public.budget_expenses) then
    raise exception 'budget_expenses tiene filas y no tiene fecha: revisa los datos antes de continuar.';
  end if;
end
$$;

-- ---------------------------------------------------------------------------
-- 1. budget_expenses: categoría y fecha del gasto
-- ---------------------------------------------------------------------------
alter table public.budget_expenses
  add column if not exists categoria text not null
    check (char_length(btrim(categoria)) between 1 and 60);

alter table public.budget_expenses
  add column if not exists fecha date not null;

comment on column public.budget_expenses.categoria is 'Categoría del gasto (texto libre, 1–60 caracteres).';
comment on column public.budget_expenses.fecha is 'Fecha del gasto. La aplicación exige que pertenezca al mes del presupuesto.';

create index if not exists budget_expenses_user_fecha_idx
  on public.budget_expenses (user_id, fecha);

-- ---------------------------------------------------------------------------
-- 2. tasks: fecha límite opcional
-- ---------------------------------------------------------------------------
alter table public.tasks
  add column if not exists fecha_limite date null;

comment on column public.tasks.fecha_limite is 'Fecha límite opcional. Vencimientos y próximas tareas se calculan en el backend.';

create index if not exists tasks_user_fecha_limite_pendiente_idx
  on public.tasks (user_id, fecha_limite)
  where estado = 'pendiente';
