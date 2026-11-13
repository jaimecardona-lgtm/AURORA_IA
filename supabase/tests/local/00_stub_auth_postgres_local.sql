-- =============================================================================
-- SOLO PARA POSTGRESQL LOCAL DE PRUEBA. NO EJECUTAR EN SUPABASE.
--
-- Supabase ya provee el esquema auth, la tabla auth.users, los roles anon/authenticated
-- y la función auth.uid(). Este stub reproduce esas piezas mínimas para poder
-- ejecutar las migraciones y las pruebas RLS en un PostgreSQL sin Supabase.
-- La definición de auth.uid() imita la de Supabase: lee el claim 'sub' del JWT
-- que PostgREST expone en request.jwt.claims.
-- =============================================================================

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
end
$$;

create schema if not exists auth;

create table if not exists auth.users (
  id    uuid primary key,
  email text
);

create or replace function auth.uid()
returns uuid
language sql
stable
as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;

grant usage on schema auth to anon, authenticated;
grant usage on schema public to anon, authenticated;
