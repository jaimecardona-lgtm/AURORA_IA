-- =============================================================================
-- AURORA AI · Fase 08A · Persistencia de conversaciones del copiloto (NO destructivo)
--
-- ESTADO: PENDIENTE DE REVISIÓN Y DE APLICACIÓN MANUAL. No se ha ejecutado en ningún proyecto.
--
-- Requiere: el esquema auth estándar de Supabase (auth.users y auth.uid()).
-- No depende de las tablas de dominio ni de las migraciones 20261111120000 y 20261112120000.
-- Se aplica desde Supabase SQL Editor, en el proyecto AURORA_IA, y nunca con Supabase CLI.
--
-- Qué añade:
--   * ai_conversations : conversaciones del copiloto de cada usuario.
--   * ai_messages      : mensajes de cada conversación, con metadatos limitados.
--
-- Qué NO hace:
--   * No modifica las cinco tablas actuales (academic_*, grade_entries, monthly_budgets,
--     budget_expenses, tasks), ni sus políticas ni sus permisos.
--   * No guarda contexto académico, financiero ni de tareas, ni claves, ni tokens JWT.
--   * No guarda los mensajes de error: un error es estado de la interfaz, no conversación.
--
-- Garantías de integridad y seguridad:
--   * user_id tiene DEFAULT auth.uid() y las políticas exigen auth.uid() = user_id.
--     El valor que envíe el navegador nunca se usa para decidir la propiedad.
--   * Clave foránea COMPUESTA (user_id, conversation_id) -> ai_conversations (user_id, id):
--     un mensaje solo puede referenciar una conversación del MISMO usuario. Incluso si se
--     intenta insertar un identificador ajeno, la base rechaza la fila (23503).
--   * Clave única (user_id, conversation_id, cliente_id): idempotencia. Reenviar el mismo
--     mensaje no lo duplica.
--   * Los mensajes son inmutables para el cliente: no hay políticas de UPDATE ni DELETE.
--     Se eliminan solo en cascada al borrar su conversación.
--   * anon no tiene permisos ni políticas.
--
-- Idempotente: puede ejecutarse de nuevo sin efectos adicionales.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Tabla de conversaciones
-- ---------------------------------------------------------------------------
create table if not exists public.ai_conversations (
  id          uuid        primary key default gen_random_uuid(),
  user_id     uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  title       text        not null default 'Nueva conversación'
                          check (char_length(btrim(title)) between 1 and 120),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint ai_conversations_user_id_id_key unique (user_id, id)
);

comment on table public.ai_conversations is 'Conversaciones del copiloto. Cada fila pertenece a un único usuario (auth.uid()).';
comment on column public.ai_conversations.title is 'Título visible (1–120 caracteres). Se deriva de la primera pregunta.';

create index if not exists ai_conversations_user_updated_idx
  on public.ai_conversations (user_id, updated_at desc, id);

-- ---------------------------------------------------------------------------
-- 2. Tabla de mensajes
-- ---------------------------------------------------------------------------
create table if not exists public.ai_messages (
  id              uuid        primary key default gen_random_uuid(),
  orden           bigint      generated always as identity unique,
  user_id         uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  conversation_id uuid        not null,
  cliente_id      uuid        not null,
  role            text        not null check (role in ('user', 'assistant')),
  content         text        not null check (char_length(btrim(content)) between 1 and 8000),
  estado          text        not null default 'completado' check (estado in ('completado', 'incompleto')),
  proveedor       text        null check (proveedor is null or char_length(proveedor) <= 30),
  modelo          text        null check (modelo is null or char_length(modelo) <= 120),
  simulado        boolean     null,
  contexto_usado  text[]      not null default '{}'
                              check (contexto_usado <@ array['academic', 'finance', 'tasks']::text[]),
  total_tokens    integer     null check (total_tokens is null or total_tokens >= 0),
  created_at      timestamptz not null default now(),

  -- Pertenencia: el mensaje solo puede apuntar a una conversación del mismo usuario.
  constraint ai_messages_conversacion_fk
    foreign key (user_id, conversation_id)
    references public.ai_conversations (user_id, id) on delete cascade,
  -- Idempotencia: un mismo envío del cliente no genera dos filas.
  constraint ai_messages_cliente_key unique (user_id, conversation_id, cliente_id),
  constraint ai_messages_user_id_id_key unique (user_id, id)
);

comment on table public.ai_messages is 'Mensajes de las conversaciones del copiloto. Inmutables para el cliente.';
comment on column public.ai_messages.cliente_id is 'Clave de idempotencia generada por la interfaz (UUID). Evita duplicados al reintentar.';
comment on column public.ai_messages.orden is 'Orden estable de inserción (identidad). created_at puede empatar.';

create index if not exists ai_messages_conversacion_orden_idx
  on public.ai_messages (user_id, conversation_id, orden);

-- ---------------------------------------------------------------------------
-- 3. Funciones y disparadores
-- ---------------------------------------------------------------------------
-- Antes de cualquier UPDATE: fija updated_at en el servidor e impide cambiar propietario o identidad.
create or replace function public.ai_conversations_before_update()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.id := old.id;
  new.user_id := old.user_id;
  new.created_at := old.created_at;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists ai_conversations_before_update on public.ai_conversations;
create trigger ai_conversations_before_update
  before update on public.ai_conversations
  for each row execute function public.ai_conversations_before_update();

-- Tras insertar un mensaje, la conversación pasa a ser la más reciente.
create or replace function public.ai_messages_after_insert()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  update public.ai_conversations
     set updated_at = now()
   where id = new.conversation_id
     and user_id = new.user_id;
  return new;
end;
$$;

drop trigger if exists ai_messages_after_insert on public.ai_messages;
create trigger ai_messages_after_insert
  after insert on public.ai_messages
  for each row execute function public.ai_messages_after_insert();

-- ---------------------------------------------------------------------------
-- 4. RLS: activar y bloquear el acceso anónimo
-- ---------------------------------------------------------------------------
alter table public.ai_conversations enable row level security;
alter table public.ai_messages      enable row level security;

-- Revocación EXPLÍCITA también para authenticated. Supabase concede por defecto privilegios de tabla
-- (incluido TRUNCATE, que RLS no filtra) sobre las tablas nuevas de public. Sin esta línea, un usuario
-- podría vaciar ai_messages para todos los usuarios.
revoke all on public.ai_conversations from anon, authenticated, public;
revoke all on public.ai_messages      from anon, authenticated, public;

-- Conversaciones: leer, borrar, crear (solo título; id, user_id y fechas los fija el servidor) y
-- renombrar (solo título; updated_at lo fija un disparador).
grant select, delete on public.ai_conversations to authenticated;
grant insert (title) on public.ai_conversations to authenticated;
grant update (title, updated_at) on public.ai_conversations to authenticated;

-- Mensajes: leer y crear. Las columnas de propiedad (user_id), identidad (id, orden) y tiempo (created_at)
-- no se pueden enviar desde el cliente: un INSERT que las incluya falla con 42501.
grant select on public.ai_messages to authenticated;
grant insert (conversation_id, cliente_id, role, content, estado, proveedor, modelo, simulado,
              contexto_usado, total_tokens) on public.ai_messages to authenticated;

-- ---------------------------------------------------------------------------
-- 5. Políticas por fila (auth.uid())
-- ---------------------------------------------------------------------------
drop policy if exists ai_conversations_select_own on public.ai_conversations;
create policy ai_conversations_select_own on public.ai_conversations
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists ai_conversations_insert_own on public.ai_conversations;
create policy ai_conversations_insert_own on public.ai_conversations
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists ai_conversations_update_own on public.ai_conversations;
create policy ai_conversations_update_own on public.ai_conversations
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists ai_conversations_delete_own on public.ai_conversations;
create policy ai_conversations_delete_own on public.ai_conversations
  for delete to authenticated using (auth.uid() = user_id);

drop policy if exists ai_messages_select_own on public.ai_messages;
create policy ai_messages_select_own on public.ai_messages
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists ai_messages_insert_own on public.ai_messages;
create policy ai_messages_insert_own on public.ai_messages
  for insert to authenticated with check (auth.uid() = user_id);

-- Nota: no hay políticas de UPDATE ni DELETE sobre ai_messages. Con RLS activa, eso deniega ambas.
