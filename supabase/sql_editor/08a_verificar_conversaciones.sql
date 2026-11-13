-- =============================================================================
-- AURORA AI · Fase 08A · VERIFICACIÓN DE SOLO LECTURA (Supabase SQL Editor, proyecto AURORA_IA)
--
-- No crea, modifica ni borra nada. Ejecutar DESPUÉS de 20261113120000_fase08a_conversaciones_ia.sql.
-- Devuelve una fila por comprobación: ok = true significa que la comprobación se cumple.
-- Cualquier ok = false debe revisarse antes de activar PERSISTENCIA en el backend.
-- =============================================================================

with comprobaciones as (
  -- 1. Existencia de las dos tablas nuevas
  select 'tabla ai_conversations existe' as comprobacion,
         exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'ai_conversations') as ok
  union all
  select 'tabla ai_messages existe',
         exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'ai_messages')

  -- 2. RLS activa en ambas
  union all
  select 'RLS activa en ai_conversations',
         coalesce((select relrowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace
                   where n.nspname = 'public' and c.relname = 'ai_conversations'), false)
  union all
  select 'RLS activa en ai_messages',
         coalesce((select relrowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace
                   where n.nspname = 'public' and c.relname = 'ai_messages'), false)

  -- 3. Políticas esperadas (4 en conversaciones, 2 en mensajes; ninguna para anon ni public)
  union all
  select 'ai_conversations tiene 4 políticas (select, insert, update, delete)',
         (select count(*) from pg_policies where schemaname = 'public' and tablename = 'ai_conversations') = 4
  union all
  select 'ai_messages tiene 2 políticas (select, insert) y ninguna de update o delete',
         (select count(*) from pg_policies where schemaname = 'public' and tablename = 'ai_messages') = 2
     and not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'ai_messages' and cmd in ('UPDATE', 'DELETE'))
  union all
  select 'ninguna política de ai_* aplica a anon o public',
         not exists (select 1 from pg_policies where schemaname = 'public' and tablename in ('ai_conversations', 'ai_messages')
                      and (roles::text like '%anon%' or roles::text like '%public%'))
  union all
  select 'todas las políticas de ai_* usan auth.uid()',
         not exists (select 1 from pg_policies where schemaname = 'public' and tablename in ('ai_conversations', 'ai_messages')
                      and coalesce(qual, '') not like '%auth.uid()%' and cmd <> 'INSERT')
     and not exists (select 1 from pg_policies where schemaname = 'public' and tablename in ('ai_conversations', 'ai_messages')
                      and cmd = 'INSERT' and coalesce(with_check, '') not like '%auth.uid()%')

  -- 4. Permisos: anon sin acceso; authenticated solo lo necesario
  union all
  select 'anon no tiene ningún permiso sobre ai_conversations ni ai_messages',
         not has_table_privilege('anon', 'public.ai_conversations', 'select,insert,update,delete')
     and not has_table_privilege('anon', 'public.ai_messages', 'select,insert,update,delete')
  union all
  select 'authenticated no puede modificar ni borrar mensajes directamente',
         not has_table_privilege('authenticated', 'public.ai_messages', 'update,delete')
  union all
  select 'authenticated puede cambiar solo el título de una conversación',
         has_column_privilege('authenticated', 'public.ai_conversations', 'title', 'update')
     and not has_column_privilege('authenticated', 'public.ai_conversations', 'user_id', 'update')
     and not has_column_privilege('authenticated', 'public.ai_conversations', 'id', 'update')
  union all
  select 'authenticated no puede cambiar el contenido de los mensajes',
         not has_column_privilege('authenticated', 'public.ai_messages', 'content', 'update')
  union all
  select 'authenticated no tiene TRUNCATE, REFERENCES ni TRIGGER en ninguna tabla de ai_* (TRUNCATE no lo filtra RLS)',
         not has_table_privilege('authenticated', 'public.ai_conversations', 'truncate,references,trigger')
     and not has_table_privilege('authenticated', 'public.ai_messages', 'truncate,references,trigger')
  union all
  select 'authenticated puede leer y crear mensajes solo con las columnas previstas',
         has_table_privilege('authenticated', 'public.ai_messages', 'select')
     and has_column_privilege('authenticated', 'public.ai_messages', 'conversation_id', 'insert')
     and not has_column_privilege('authenticated', 'public.ai_messages', 'user_id', 'insert')
     and not has_column_privilege('authenticated', 'public.ai_messages', 'id', 'insert')
     and not has_column_privilege('authenticated', 'public.ai_messages', 'created_at', 'insert')
  union all
  select 'authenticated no puede fijar user_id, id ni created_at al crear conversaciones',
         has_column_privilege('authenticated', 'public.ai_conversations', 'title', 'insert')
     and not has_column_privilege('authenticated', 'public.ai_conversations', 'user_id', 'insert')
     and not has_column_privilege('authenticated', 'public.ai_conversations', 'id', 'insert')
     and not has_column_privilege('authenticated', 'public.ai_conversations', 'created_at', 'insert')

  -- 5. Integridad: claves y restricciones
  union all
  select 'clave foránea compuesta (user_id, conversation_id) -> ai_conversations',
         exists (select 1 from pg_constraint
                  where conname = 'ai_messages_conversacion_fk' and contype = 'f'
                    and conrelid = to_regclass('public.ai_messages')
                    and confrelid = to_regclass('public.ai_conversations'))
  union all
  select 'idempotencia: único (user_id, conversation_id, cliente_id)',
         exists (select 1 from pg_constraint where conname = 'ai_messages_cliente_key' and contype = 'u')
  union all
  select 'identidad propia: user_id referencia auth.users con DEFAULT auth.uid()',
         exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = 'ai_conversations' and column_name = 'user_id'
                    and column_default like '%auth.uid()%')
     and exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = 'ai_messages' and column_name = 'user_id'
                    and column_default like '%auth.uid()%')
  union all
  select 'disparadores de updated_at y de actualización de la conversación presentes',
         exists (select 1 from pg_trigger where tgname = 'ai_conversations_before_update' and not tgisinternal)
     and exists (select 1 from pg_trigger where tgname = 'ai_messages_after_insert' and not tgisinternal)

  -- 6. Las cinco tablas existentes siguen con RLS activa (la migración no las ha tocado)
  union all
  select 'tablas de dominio existentes con RLS activa (5 de 5)',
         (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
           where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity
             and c.relname in ('academic_subjects', 'grade_entries', 'monthly_budgets', 'budget_expenses', 'tasks')) = 5
)
select comprobacion, ok
  from comprobaciones
 order by comprobacion;
