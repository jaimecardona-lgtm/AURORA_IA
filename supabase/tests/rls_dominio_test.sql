-- =============================================================================
-- Pruebas RLS del dominio AURORA (Fase 01).
--
-- Cubre:
--   * acceso propio permitido (CRUD de academic_subjects y grade_entries),
--   * acceso cruzado denegado (SELECT, UPDATE, DELETE, INSERT con user_id ajeno),
--   * referencias cruzadas denegadas (FK compuesta),
--   * validaciones CHECK (nota fuera de 0–5),
--   * usuario anónimo (anon) y sesión sin usuario denegados.
--
-- Ejecución:
--   * En Supabase: SQL Editor (o `supabase db query`) con la migración aplicada.
--     Debe ejecutarse como rol postgres (el de SQL Editor), que sí puede crear usuarios de prueba.
--   * En PostgreSQL local: ver docs/PRUEBAS_FASE_01.md (requiere el stub de supabase/tests/local/).
-- Todo corre dentro de una transacción que termina en ROLLBACK: no deja datos.
-- Si alguna comprobación falla, aborta con 'FALLO RLS: ...'.
-- =============================================================================

begin;

-- ---------------------------------------------------------------------------
-- Helpers temporales (pg_temp: solo viven en esta sesión)
-- ---------------------------------------------------------------------------
create or replace function pg_temp.check_true(cond boolean, msg text)
returns void language plpgsql as $$
begin
  if cond is distinct from true then
    raise exception 'FALLO RLS: %', msg;
  end if;
  raise notice 'OK: %', msg;
end $$;

-- Verifica que la sentencia FALLE (violación de RLS, FK, CHECK o permisos).
create or replace function pg_temp.check_fails(stmt text, msg text)
returns void language plpgsql as $$
begin
  execute stmt;
  raise exception 'FALLO RLS (se esperaba bloqueo): %', msg;
exception
  when others then
    if sqlerrm like 'FALLO RLS%' then
      raise;
    end if;
    raise notice 'OK: % (bloqueado: %)', msg, sqlerrm;
end $$;

create or replace function pg_temp.as_user(uid uuid)
returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claims', json_build_object('sub', uid, 'role', 'authenticated')::text, false);
  perform set_config('request.jwt.claim.sub', uid::text, false);
  execute 'set role authenticated';
end $$;

create or replace function pg_temp.as_anon()
returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claims', '', false);
  perform set_config('request.jwt.claim.sub', '', false);
  execute 'set role anon';
end $$;

create or replace function pg_temp.as_admin()
returns void language plpgsql as $$
begin
  execute 'reset role';
  perform set_config('request.jwt.claims', '', false);
  perform set_config('request.jwt.claim.sub', '', false);
end $$;

-- ---------------------------------------------------------------------------
-- Preparación (como administrador de la prueba)
-- ---------------------------------------------------------------------------
select pg_temp.as_admin();

insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'alumna.a@prueba.local'),
  ('22222222-2222-2222-2222-222222222222', 'alumno.b@prueba.local');

-- ---------------------------------------------------------------------------
-- A. Acceso propio (usuario A)
-- ---------------------------------------------------------------------------
select pg_temp.as_user('11111111-1111-1111-1111-111111111111');

-- ID fijo para poder referenciarla desde B sin depender de SELECT (que B no puede hacer).
insert into public.academic_subjects (id, nombre)
  values ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Matemáticas');
insert into public.academic_subjects (nombre) values ('Programación');

select pg_temp.check_true(
  (select count(*) from public.academic_subjects) = 2,
  'A ve sus 2 asignaturas');

select pg_temp.check_true(
  (select count(*) from public.academic_subjects where user_id = '11111111-1111-1111-1111-111111111111') = 2,
  'user_id se asigna automáticamente a A (auth.uid())');

insert into public.grade_entries (subject_id, descripcion, nota)
  select id, 'Parcial 1', 4.25 from public.academic_subjects where nombre = 'Matemáticas';

select pg_temp.check_true(
  (select count(*) from public.grade_entries) = 1,
  'A ve su nota creada');

select pg_temp.check_fails(
  $$insert into public.grade_entries (subject_id, descripcion, nota)
      select id, 'Nota fuera de rango', 5.01 from public.academic_subjects where nombre = 'Matemáticas'$$,
  'nota 5.01 rechazada por CHECK (0–5)');

select pg_temp.check_fails(
  $$insert into public.grade_entries (subject_id, descripcion, nota)
      select id, 'Nota negativa', -0.1 from public.academic_subjects where nombre = 'Matemáticas'$$,
  'nota -0.1 rechazada por CHECK (0–5)');

-- Un usuario no puede cambiar la propiedad de una fila propia a otro usuario.
select pg_temp.check_fails(
  $$update public.academic_subjects set user_id = '22222222-2222-2222-2222-222222222222'
      where nombre = 'Programación'$$,
  'A no puede reasignar su asignatura a B (WITH CHECK)');

-- Duplicado por usuario (sin distinguir mayúsculas ni espacios laterales)
select pg_temp.check_fails(
  $$insert into public.academic_subjects (nombre) values ('matemáticas ')$$,
  'A no puede duplicar asignatura (índice único por usuario)');

-- ---------------------------------------------------------------------------
-- B. Acceso cruzado denegado (usuario B intenta ver/tocar datos de A)
-- ---------------------------------------------------------------------------
select pg_temp.as_user('22222222-2222-2222-2222-222222222222');

select pg_temp.check_true(
  (select count(*) from public.academic_subjects) = 0,
  'B NO ve las asignaturas de A (SELECT cruzado denegado)');

select pg_temp.check_true(
  (select count(*) from public.grade_entries) = 0,
  'B NO ve las notas de A (SELECT cruzado denegado)');

-- UPDATE/DELETE cruzados: no afectan filas (RLS las filtra)
do $$
declare n integer;
begin
  update public.academic_subjects set nombre = 'Hackeada' where nombre = 'Matemáticas';
  get diagnostics n = row_count;
  perform pg_temp.check_true(n = 0, 'B no puede modificar asignaturas de A (UPDATE afecta 0 filas)');
end $$;

do $$
declare n integer;
begin
  delete from public.academic_subjects where nombre = 'Matemáticas';
  get diagnostics n = row_count;
  perform pg_temp.check_true(n = 0, 'B no puede borrar asignaturas de A (DELETE afecta 0 filas)');
end $$;

-- INSERT suplantando a A
select pg_temp.check_fails(
  $$insert into public.academic_subjects (user_id, nombre)
      values ('11111111-1111-1111-1111-111111111111', 'Suplantación')$$,
  'B no puede insertar filas con user_id de A (WITH CHECK)');

-- Referencia cruzada: B crea una nota (user_id = B) apuntando a la asignatura de A.
-- La FK compuesta (user_id, subject_id) debe rechazarlo aunque RLS no muestre la fila.
select pg_temp.check_fails(
  $$insert into public.grade_entries (subject_id, descripcion, nota)
      values ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Referencia cruzada', 3.0)$$,
  'B no puede crear nota apuntando a asignatura de A (FK compuesta)');

-- B sí puede operar sobre sus propios datos
insert into public.academic_subjects (nombre) values ('Física');
insert into public.grade_entries (subject_id, descripcion, nota)
  select id, 'Parcial B', 2.90 from public.academic_subjects where nombre = 'Física';

select pg_temp.check_true(
  (select count(*) from public.grade_entries) = 1,
  'B ve solo su propia nota');

-- ---------------------------------------------------------------------------
-- C. Sin sesión: anon y authenticated sin claim sub
-- ---------------------------------------------------------------------------
select pg_temp.as_anon();

select pg_temp.check_fails(
  $$select count(*) from public.academic_subjects$$,
  'anon no puede leer asignaturas (sin grant)');

select pg_temp.check_fails(
  $$insert into public.academic_subjects (nombre) values ('Anónima')$$,
  'anon no puede insertar asignaturas (sin grant)');

select pg_temp.check_fails(
  $$select count(*) from public.grade_entries$$,
  'anon no puede leer notas (sin grant)');

select pg_temp.check_fails(
  $$select count(*) from public.tasks$$,
  'anon no puede leer tareas (sin grant)');

-- authenticated sin claim sub: auth.uid() es NULL -> RLS devuelve 0 filas / bloquea
select pg_temp.as_admin();
set role authenticated;
select pg_temp.check_true(
  (select count(*) from public.academic_subjects) = 0,
  'authenticated sin uid (auth.uid() NULL) no ve filas');

select pg_temp.check_fails(
  $$insert into public.academic_subjects (nombre) values ('Sin sesión')$$,
  'authenticated sin uid no puede insertar (user_id NULL / WITH CHECK)');

-- ---------------------------------------------------------------------------
-- D. Tablas del dominio para fases siguientes: aislamiento básico
-- ---------------------------------------------------------------------------
select pg_temp.as_admin();
insert into public.tasks (user_id, titulo, prioridad) values
  ('11111111-1111-1111-1111-111111111111', 'Tarea de A', 1);

select pg_temp.as_user('22222222-2222-2222-2222-222222222222');
select pg_temp.check_true(
  (select count(*) from public.tasks) = 0,
  'B no ve tareas de A (aislamiento de tasks)');

select pg_temp.check_fails(
  $$insert into public.tasks (user_id, titulo, prioridad) values
      ('11111111-1111-1111-1111-111111111111', 'Suplantación', 2)$$,
  'B no puede crear tareas para A (tasks)');

select pg_temp.check_fails(
  $$insert into public.tasks (titulo, prioridad) values ('Prioridad inválida', 4)$$,
  'prioridad 4 rechazada por CHECK (1..3)');

rollback;
