-- =============================================================================
-- AURORA AI · Fase 01 · Modelo de datos del dominio + RLS
--
-- Tablas: academic_subjects, grade_entries, monthly_budgets, budget_expenses, tasks.
-- Principios:
--   * Toda fila pertenece a un usuario (user_id = auth.uid()).
--   * RLS habilitado y forzado en todas las tablas del dominio.
--   * anon no tiene grants ni políticas: acceso denegado.
--   * authenticated solo accede a sus filas (políticas por operación).
--   * Claves foráneas COMPUESTAS (user_id, id): una fila no puede referenciar
--     un objeto de otro usuario aunque alguien intente insertar user_id ajeno.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Función de auditoría de fechas (SECURITY INVOKER: no eleva privilegios)
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- 1. academic_subjects
-- ---------------------------------------------------------------------------
create table if not exists public.academic_subjects (
  id          uuid        primary key default gen_random_uuid(),
  user_id     uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  nombre      text        not null check (char_length(btrim(nombre)) between 1 and 120),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  -- Necesaria como destino de la FK compuesta desde grade_entries.
  constraint academic_subjects_user_id_id_key unique (user_id, id)
);

-- Un usuario no puede repetir la misma asignatura (sin distinguir mayúsculas).
create unique index if not exists academic_subjects_user_nombre_key
  on public.academic_subjects (user_id, lower(btrim(nombre)));

create trigger academic_subjects_set_updated_at
  before update on public.academic_subjects
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 2. grade_entries
-- ---------------------------------------------------------------------------
create table if not exists public.grade_entries (
  id          uuid          primary key default gen_random_uuid(),
  user_id     uuid          not null default auth.uid() references auth.users (id) on delete cascade,
  subject_id  uuid          not null,
  descripcion text          not null check (char_length(btrim(descripcion)) between 1 and 200),
  nota        numeric(4, 2) not null check (nota >= 0 and nota <= 5),
  created_at  timestamptz   not null default now(),
  updated_at  timestamptz   not null default now(),
  -- FK compuesta: la asignatura debe pertenecer al MISMO usuario que la nota.
  constraint grade_entries_subject_same_user_fk
    foreign key (user_id, subject_id)
    references public.academic_subjects (user_id, id)
    on delete cascade
);

create index if not exists grade_entries_user_subject_idx
  on public.grade_entries (user_id, subject_id);

create trigger grade_entries_set_updated_at
  before update on public.grade_entries
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 3. monthly_budgets (esquema listo; CRUD en fases siguientes)
-- ---------------------------------------------------------------------------
create table if not exists public.monthly_budgets (
  id            uuid           primary key default gen_random_uuid(),
  user_id       uuid           not null default auth.uid() references auth.users (id) on delete cascade,
  anio          smallint       not null check (anio between 2000 and 2100),
  mes           smallint       not null check (mes between 1 and 12),
  ingreso       numeric(14, 2) not null check (ingreso >= 0),
  meta_ahorro   numeric(14, 2) not null default 0 check (meta_ahorro >= 0),
  created_at    timestamptz    not null default now(),
  updated_at    timestamptz    not null default now(),
  -- Un presupuesto por usuario y mes.
  constraint monthly_budgets_user_period_key unique (user_id, anio, mes),
  constraint monthly_budgets_user_id_id_key unique (user_id, id)
);

create trigger monthly_budgets_set_updated_at
  before update on public.monthly_budgets
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 4. budget_expenses (esquema listo; CRUD en fases siguientes)
-- ---------------------------------------------------------------------------
create table if not exists public.budget_expenses (
  id           uuid           primary key default gen_random_uuid(),
  user_id      uuid           not null default auth.uid() references auth.users (id) on delete cascade,
  budget_id    uuid           not null,
  descripcion  text           not null check (char_length(btrim(descripcion)) between 1 and 200),
  monto        numeric(14, 2) not null check (monto >= 0),
  tipo         text           not null check (tipo in ('fijo', 'variable')),
  created_at   timestamptz    not null default now(),
  updated_at   timestamptz    not null default now(),
  constraint budget_expenses_budget_same_user_fk
    foreign key (user_id, budget_id)
    references public.monthly_budgets (user_id, id)
    on delete cascade
);

create index if not exists budget_expenses_user_budget_idx
  on public.budget_expenses (user_id, budget_id);

create trigger budget_expenses_set_updated_at
  before update on public.budget_expenses
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 5. tasks (esquema listo; CRUD en fases siguientes)
-- ---------------------------------------------------------------------------
create table if not exists public.tasks (
  id          uuid        primary key default gen_random_uuid(),
  user_id     uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  titulo      text        not null check (char_length(btrim(titulo)) between 1 and 200),
  prioridad   smallint    not null check (prioridad between 1 and 3),
  estado      text        not null default 'pendiente' check (estado in ('pendiente', 'completada')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint tasks_user_id_id_key unique (user_id, id)
);

create index if not exists tasks_user_estado_prioridad_idx
  on public.tasks (user_id, estado, prioridad);

create trigger tasks_set_updated_at
  before update on public.tasks
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS: habilitar y forzar en TODAS las tablas del dominio
-- ---------------------------------------------------------------------------
alter table public.academic_subjects enable row level security;
alter table public.grade_entries     enable row level security;
alter table public.monthly_budgets   enable row level security;
alter table public.budget_expenses   enable row level security;
alter table public.tasks             enable row level security;

alter table public.academic_subjects force row level security;
alter table public.grade_entries     force row level security;
alter table public.monthly_budgets   force row level security;
alter table public.budget_expenses   force row level security;
alter table public.tasks             force row level security;

-- ---------------------------------------------------------------------------
-- Grants: se parte de cero. anon no recibe nada; authenticated solo DML.
-- ---------------------------------------------------------------------------
revoke all on public.academic_subjects from anon, authenticated, public;
revoke all on public.grade_entries     from anon, authenticated, public;
revoke all on public.monthly_budgets   from anon, authenticated, public;
revoke all on public.budget_expenses   from anon, authenticated, public;
revoke all on public.tasks             from anon, authenticated, public;

grant select, insert, update, delete on public.academic_subjects to authenticated;
grant select, insert, update, delete on public.grade_entries     to authenticated;
grant select, insert, update, delete on public.monthly_budgets   to authenticated;
grant select, insert, update, delete on public.budget_expenses   to authenticated;
grant select, insert, update, delete on public.tasks             to authenticated;

-- ---------------------------------------------------------------------------
-- Políticas: propiedad estricta por usuario, para cada operación.
-- Las políticas se aplican solo al rol authenticated; anon no tiene ninguna.
-- ---------------------------------------------------------------------------

-- academic_subjects
create policy academic_subjects_select_own on public.academic_subjects
  for select to authenticated using (auth.uid() = user_id);
create policy academic_subjects_insert_own on public.academic_subjects
  for insert to authenticated with check (auth.uid() = user_id);
create policy academic_subjects_update_own on public.academic_subjects
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy academic_subjects_delete_own on public.academic_subjects
  for delete to authenticated using (auth.uid() = user_id);

-- grade_entries
create policy grade_entries_select_own on public.grade_entries
  for select to authenticated using (auth.uid() = user_id);
create policy grade_entries_insert_own on public.grade_entries
  for insert to authenticated with check (auth.uid() = user_id);
create policy grade_entries_update_own on public.grade_entries
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy grade_entries_delete_own on public.grade_entries
  for delete to authenticated using (auth.uid() = user_id);

-- monthly_budgets
create policy monthly_budgets_select_own on public.monthly_budgets
  for select to authenticated using (auth.uid() = user_id);
create policy monthly_budgets_insert_own on public.monthly_budgets
  for insert to authenticated with check (auth.uid() = user_id);
create policy monthly_budgets_update_own on public.monthly_budgets
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy monthly_budgets_delete_own on public.monthly_budgets
  for delete to authenticated using (auth.uid() = user_id);

-- budget_expenses
create policy budget_expenses_select_own on public.budget_expenses
  for select to authenticated using (auth.uid() = user_id);
create policy budget_expenses_insert_own on public.budget_expenses
  for insert to authenticated with check (auth.uid() = user_id);
create policy budget_expenses_update_own on public.budget_expenses
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy budget_expenses_delete_own on public.budget_expenses
  for delete to authenticated using (auth.uid() = user_id);

-- tasks
create policy tasks_select_own on public.tasks
  for select to authenticated using (auth.uid() = user_id);
create policy tasks_insert_own on public.tasks
  for insert to authenticated with check (auth.uid() = user_id);
create policy tasks_update_own on public.tasks
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy tasks_delete_own on public.tasks
  for delete to authenticated using (auth.uid() = user_id);
