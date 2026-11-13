-- Pruebas de comportamiento de la migración 08A en clúster desechable. Usuarios: A = 1111…, B = 2222….
create table if not exists public.resultados(prueba text, esperado text, obtenido text);
truncate public.resultados;
create table if not exists public.ids(nombre text primary key, id uuid);
truncate public.ids;
-- Solo para el escenario de prueba: la tabla auxiliar debe ser legible por los roles que simulan usuarios.
grant select on public.ids to anon, authenticated;

create or replace function public.probar(p_nombre text, p_uid uuid, p_rol text, p_sql text, p_esperado text)
returns void language plpgsql as $$
declare v_obt text := 'OK'; v_filas int := -1;
begin
  perform set_config('request.jwt.claim.sub', coalesce(p_uid::text, ''), true);
  execute format('set local role %s', p_rol);
  begin
    execute p_sql;
    get diagnostics v_filas = row_count;
    v_obt := 'OK:' || v_filas;
  exception when others then
    v_obt := sqlstate;
  end;
  execute 'reset role';
  insert into public.resultados values (p_nombre, p_esperado, v_obt);
end $$;

-- Preparación como superusuario (bypass RLS, solo para crear el escenario).
insert into public.ids values ('convB', gen_random_uuid());
insert into public.ai_conversations(id, user_id, title)
  select id, '22222222-2222-4222-8222-222222222222', 'Conversación de B' from public.ids where nombre = 'convB';
insert into public.ids values ('convA', gen_random_uuid());
insert into public.ids values ('cliA', gen_random_uuid());

-- A crea su conversación: el cliente solo puede enviar title (id, user_id y fechas los fija el servidor).
select public.probar('A crea su conversación', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_conversations(title) values ('Conversacion de A')$q$, 'OK:1');
-- Preparación (superusuario): se toma el id real creado por A para las pruebas siguientes.
update public.ids set id = (select c.id from public.ai_conversations c
                             where c.user_id = '11111111-1111-4111-8111-111111111111' and c.title = 'Conversacion de A')
 where nombre = 'convA';
select public.probar('A no puede fijar created_at al crear una conversación', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_conversations(title, created_at) values ('falsa', '2000-01-01T00:00:00Z')$q$, '42501');
select public.probar('A no puede vaciar ai_messages con TRUNCATE', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$truncate public.ai_messages$q$, '42501');
select public.probar('A no puede crear a nombre de B', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_conversations(user_id, title) values ('22222222-2222-4222-8222-222222222222', 'suplantación')$q$, '42501');
select public.probar('A escribe mensaje en su conversación', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_messages(conversation_id, cliente_id, role, content, contexto_usado)
     select id, (select id from public.ids where nombre='cliA'), 'user', '¿Cuál es mi promedio?', '{}' from public.ids where nombre='convA'$q$, 'OK:1');
select public.probar('mismo cliente_id no se duplica', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_messages(conversation_id, cliente_id, role, content)
     select id, (select id from public.ids where nombre='cliA'), 'user', 'duplicado' from public.ids where nombre='convA'$q$, '23505');
select public.probar('A no puede escribir en conversación de B (FK compuesta)', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_messages(conversation_id, cliente_id, role, content)
     select id, gen_random_uuid(), 'user', 'intruso' from public.ids where nombre='convB'$q$, '23503');
select public.probar('A no puede escribir como B aunque conozca el id', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_messages(user_id, conversation_id, cliente_id, role, content)
     select '22222222-2222-4222-8222-222222222222', id, gen_random_uuid(), 'user', 'intruso' from public.ids where nombre='convB'$q$, '42501');
select public.probar('B no lee conversaciones de A', '22222222-2222-4222-8222-222222222222', 'authenticated',
  $q$select 1 from public.ai_conversations where id = (select id from public.ids where nombre='convA')$q$, 'OK:0');
select public.probar('B no lee mensajes de A', '22222222-2222-4222-8222-222222222222', 'authenticated',
  $q$select 1 from public.ai_messages where conversation_id = (select id from public.ids where nombre='convA')$q$, 'OK:0');
select public.probar('B no renombra conversación de A (0 filas)', '22222222-2222-4222-8222-222222222222', 'authenticated',
  $q$update public.ai_conversations set title = 'hackeada' where id = (select id from public.ids where nombre='convA')$q$, 'OK:0');
select public.probar('A renombra su conversación', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$update public.ai_conversations set title = 'Promedio académico' where id = (select id from public.ids where nombre='convA')$q$, 'OK:1');
select public.probar('A no puede cambiar user_id de su conversación', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$update public.ai_conversations set user_id = '22222222-2222-4222-8222-222222222222' where id = (select id from public.ids where nombre='convA')$q$, '42501');
select public.probar('A no puede modificar contenido de un mensaje', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$update public.ai_messages set content = 'editado' where conversation_id = (select id from public.ids where nombre='convA')$q$, '42501');
select public.probar('A no puede borrar mensajes directamente', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$delete from public.ai_messages where conversation_id = (select id from public.ids where nombre='convA')$q$, '42501');
select public.probar('anon no lee conversaciones', null, 'anon', $q$select 1 from public.ai_conversations$q$, '42501');
select public.probar('anon no escribe mensajes', null, 'anon',
  $q$insert into public.ai_messages(conversation_id, cliente_id, role, content) values (gen_random_uuid(), gen_random_uuid(), 'user', 'x')$q$, '42501');
select public.probar('título vacío rechazado', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_conversations(title) values ('   ')$q$, '23514');
select public.probar('título de 121 caracteres rechazado', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_conversations(title) values (repeat('x', 121))$q$, '23514');
select public.probar('contexto fuera de la lista rechazado', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_messages(conversation_id, cliente_id, role, content, contexto_usado)
     select id, gen_random_uuid(), 'assistant', 'ok', array['contraseña'] from public.ids where nombre='convA'$q$, '23514');
select public.probar('rol inválido rechazado', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_messages(conversation_id, cliente_id, role, content)
     select id, gen_random_uuid(), 'system', 'x' from public.ids where nombre='convA'$q$, '23514');
select public.probar('estado de error no es válido en un mensaje', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_messages(conversation_id, cliente_id, role, content, estado)
     select id, gen_random_uuid(), 'assistant', 'x', 'error' from public.ids where nombre='convA'$q$, '23514');
select public.probar('respuesta del asistente con metadatos limitados', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$insert into public.ai_messages(conversation_id, cliente_id, role, content, proveedor, modelo, simulado, contexto_usado, total_tokens, estado)
     select id, gen_random_uuid(), 'assistant', 'Tu promedio es 3,47', 'simulado', 'simulado-v1', true, '{academic}', 0, 'completado' from public.ids where nombre='convA'$q$, 'OK:1');
select public.probar('B no borra conversación de A (0 filas)', '22222222-2222-4222-8222-222222222222', 'authenticated',
  $q$delete from public.ai_conversations where id = (select id from public.ids where nombre='convA')$q$, 'OK:0');
select public.probar('A borra su conversación', '11111111-1111-4111-8111-111111111111', 'authenticated',
  $q$delete from public.ai_conversations where id = (select id from public.ids where nombre='convA')$q$, 'OK:1');

select 'cascada: mensajes de A tras borrar = ' || count(*) as resultado from public.ai_messages where conversation_id = (select id from public.ids where nombre='convA');
select 'B conserva su conversación = ' || count(*) as resultado from public.ai_conversations where id = (select id from public.ids where nombre='convB');

select prueba, esperado, obtenido, case when obtenido = esperado then 'PASS' else 'FAIL' end as veredicto from public.resultados order by prueba;
