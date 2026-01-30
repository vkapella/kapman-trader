\timing on
\echo '============================================================'
\echo ' KAPMAN SCHEMA INTEGRITY & DRIFT DIAGNOSTIC'
\echo '============================================================'

------------------------------------------------------------
-- 1. TABLE INVENTORY (public schema only)
------------------------------------------------------------
\echo ''
\echo '--- TABLE INVENTORY ---'
SELECT
  table_name,
  table_type
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_type, table_name;

------------------------------------------------------------
-- 2. DAILY_SNAPSHOTS COLUMN CONTRACT
------------------------------------------------------------
\echo ''
\echo '--- DAILY_SNAPSHOTS COLUMN CONTRACT ---'
SELECT
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'daily_snapshots'
ORDER BY ordinal_position;

------------------------------------------------------------
-- 3. JSONB COLUMN TYPE & NULLABILITY CHECK
------------------------------------------------------------
\echo ''
\echo '--- JSONB COLUMN TYPE CHECK ---'
SELECT
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'daily_snapshots'
  AND column_name IN (
    'events_json',
    'dealer_metrics_json',
    'volatility_metrics_json',
    'technical_indicators_json',
    'price_metrics_json'
  )
ORDER BY column_name;

------------------------------------------------------------
-- 4. MODEL VERSION DENSITY BY DATE (DRIFT DETECTOR)
------------------------------------------------------------
\echo ''
\echo '--- MODEL VERSION DENSITY (LAST 30 SNAPSHOTS) ---'
SELECT
  model_version,
  min(time) AS first_seen,
  max(time) AS last_seen,
  count(*)  AS rows
FROM daily_snapshots
WHERE time >= (
  SELECT max(time) - interval '30 days'
  FROM daily_snapshots
)
GROUP BY model_version
ORDER BY last_seen DESC;

------------------------------------------------------------
-- 5. UNEXPECTED / LEGACY MODEL VERSIONS
------------------------------------------------------------
\echo ''
\echo '--- LEGACY OR SINGLETON MODEL VERSIONS ---'
SELECT
  model_version,
  count(*) AS rows
FROM daily_snapshots
GROUP BY model_version
HAVING count(*) < 500
ORDER BY rows ASC;

\echo ''
\echo '============================================================'
\echo ' SCHEMA DIAGNOSTIC COMPLETE'
\echo '============================================================'