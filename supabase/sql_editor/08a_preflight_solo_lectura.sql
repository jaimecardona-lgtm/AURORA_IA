-- AURORA AI - diagnóstico 100% solo lectura (NO crea, actualiza ni elimina datos)
-- Antes de ejecutar: confirmar en el encabezado del Dashboard el proyecto AURORA_IA,
-- referencia dsldzrtgzrthifsxmtwu. NO ejecutar sobre LOGIXTIC.
-- Si no se encuentran las 5 tablas de dominio esperadas, DETENERSE:
-- posiblemente se abrió el proyecto equivocado o faltan migraciones anteriores.

WITH esperadas(nombre) AS (
  VALUES ('academic_subjects'), ('grade_entries'), ('monthly_budgets'),
         ('budget_expenses'), ('tasks')
), dominio AS (
  SELECT nombre, to_regclass('public.' || nombre) IS NOT NULL AS existe
  FROM esperadas
), ia AS (
  SELECT 'ai_conversations' AS nombre, to_regclass('public.ai_conversations') IS NOT NULL AS existe
  UNION ALL
  SELECT 'ai_messages', to_regclass('public.ai_messages') IS NOT NULL
)
SELECT 'dominio' AS grupo, nombre, existe FROM dominio
UNION ALL
SELECT 'conversaciones' AS grupo, nombre, existe FROM ia
ORDER BY grupo, nombre;

-- Esperado antes de habilitar el historial: 7 filas con existe = true.
-- Después ejecutar supabase/sql_editor/08a_verificar_conversaciones.sql:
-- 20 verificaciones, todas ok=true, y pruebas reales RLS usuarios A/B.
