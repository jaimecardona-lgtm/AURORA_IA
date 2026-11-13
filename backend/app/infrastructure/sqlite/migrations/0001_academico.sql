-- AURORA AI · SQLite local · 0001 · Módulo académico.
-- Reflejo local de la migración PostgreSQL 20261111120000 (sin RLS: el aislamiento lo
-- aplica el repositorio filtrando por user_id; ver docs/FASE_03_IMPLEMENTACION.md).
-- origen: 'real' (registro del usuario) | 'demo' (datos ficticios de demostración).

CREATE TABLE IF NOT EXISTS academic_subjects (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL,
  nombre      TEXT NOT NULL CHECK (length(trim(nombre)) BETWEEN 1 AND 120),
  origen      TEXT NOT NULL DEFAULT 'real' CHECK (origen IN ('real', 'demo')),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  UNIQUE (user_id, id)
);

CREATE UNIQUE INDEX IF NOT EXISTS academic_subjects_user_nombre_key
  ON academic_subjects (user_id, lower(trim(nombre)));

CREATE TABLE IF NOT EXISTS grade_entries (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL,
  subject_id  TEXT NOT NULL,
  descripcion TEXT NOT NULL CHECK (length(trim(descripcion)) BETWEEN 1 AND 200),
  nota        REAL NOT NULL CHECK (nota >= 0 AND nota <= 5),
  origen      TEXT NOT NULL DEFAULT 'real' CHECK (origen IN ('real', 'demo')),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  -- La asignatura debe pertenecer al MISMO usuario que la nota.
  FOREIGN KEY (user_id, subject_id) REFERENCES academic_subjects (user_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS grade_entries_user_subject_idx
  ON grade_entries (user_id, subject_id);
