-- Simulación local de Supabase Auth: solo para validar la migración en un clúster desechable.
create schema if not exists auth;
create table if not exists auth.users (id uuid primary key);
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(coalesce(current_setting('request.jwt.claim.sub', true), ''), '')::uuid
$$;
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
end $$;
grant usage on schema public to anon, authenticated;
grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
-- EMULACIÓN (supuesto a confirmar en el proyecto real): Supabase concede por defecto privilegios de tabla
-- sobre las tablas nuevas de public a anon y authenticated. Así se reproduce el escenario más exigente.
alter default privileges in schema public grant all on tables to anon, authenticated;
insert into auth.users values ('11111111-1111-4111-8111-111111111111'), ('22222222-2222-4222-8222-222222222222') on conflict do nothing;
