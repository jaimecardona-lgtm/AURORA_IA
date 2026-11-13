-- AURORA AI · SQLite local · 0002 · Presupuesto mensual y tareas.
-- Montos en COP guardados como REAL y convertidos a Decimal en el motor (dos decimales).
-- Fechas en ISO 8601 (AAAA-MM-DD); la coherencia con el mes se valida en el servicio.

CREATE TABLE IF NOT EXISTS monthly_budgets (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL,
  anio         INTEGER NOT NULL CHECK (anio BETWEEN 2000 AND 2100),
  mes          INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
  ingreso      REAL NOT NULL CHECK (ingreso >= 0),
  meta_ahorro  REAL NOT NULL DEFAULT 0 CHECK (meta_ahorro >= 0),
  origen       TEXT NOT NULL DEFAULT 'real' CHECK (origen IN ('real', 'demo')),
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  UNIQUE (user_id, anio, mes),
  UNIQUE (user_id, id)
);

CREATE TABLE IF NOT EXISTS budget_expenses (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL,
  budget_id    TEXT NOT NULL,
  descripcion  TEXT NOT NULL CHECK (length(trim(descripcion)) BETWEEN 1 AND 200),
  categoria    TEXT NOT NULL CHECK (length(trim(categoria)) BETWEEN 1 AND 60),
  monto        REAL NOT NULL CHECK (monto >= 0),
  tipo         TEXT NOT NULL CHECK (tipo IN ('fijo', 'variable')),
  fecha        TEXT NOT NULL,
  origen       TEXT NOT NULL DEFAULT 'real' CHECK (origen IN ('real', 'demo')),
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  FOREIGN KEY (user_id, budget_id) REFERENCES monthly_budgets (user_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS budget_expenses_user_budget_idx
  ON budget_expenses (user_id, budget_id);

CREATE TABLE IF NOT EXISTS tasks (
  id            TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL,
  titulo        TEXT NOT NULL CHECK (length(trim(titulo)) BETWEEN 1 AND 200),
  prioridad     INTEGER NOT NULL CHECK (prioridad IN (1, 2, 3)),
  estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'completada')),
  fecha_limite  TEXT NULL,
  origen        TEXT NOT NULL DEFAULT 'real' CHECK (origen IN ('real', 'demo')),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  UNIQUE (user_id, id)
);

CREATE INDEX IF NOT EXISTS tasks_user_estado_prioridad_idx
  ON tasks (user_id, estado, prioridad);
