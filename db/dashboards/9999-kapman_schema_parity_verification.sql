\echo '============================================================'
\echo 'KAPMAN SCHEMA PARITY VERIFICATION — HARD SAFE MODE'
\echo 'Baseline: 0001_schema_baseline_2026_01.sql'
\echo '============================================================'
\echo ''

\echo '------------------------------------------------------------'
\echo '1. TABLE INVENTORY'
\echo '------------------------------------------------------------'
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename;

\echo ''
\echo '------------------------------------------------------------'
\echo '2. COLUMN DEFINITIONS'
\echo '------------------------------------------------------------'
SELECT table_schema, table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name, ordinal_position;

\echo ''
\echo '------------------------------------------------------------'
\echo '3. CONSTRAINTS (PK / FK / UNIQUE)'
\echo '------------------------------------------------------------'
SELECT
    tc.table_schema,
    tc.table_name,
    tc.constraint_type,
    tc.constraint_name,
    kcu.column_name,
    ccu.table_schema AS foreign_table_schema,
    ccu.table_name   AS foreign_table_name,
    ccu.column_name  AS foreign_column_name
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
LEFT JOIN information_schema.constraint_column_usage ccu
    ON tc.constraint_name = ccu.constraint_name
WHERE tc.table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY tc.table_schema, tc.table_name, tc.constraint_type, tc.constraint_name;

\echo ''
\echo '------------------------------------------------------------'
\echo '4. INDEX DEFINITIONS'
\echo '------------------------------------------------------------'
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename, indexname;

\echo ''
\echo '------------------------------------------------------------'
\echo '5. ENUM TYPES'
\echo '------------------------------------------------------------'
SELECT
    n.nspname   AS schema_name,
    t.typname   AS enum_name,
    e.enumlabel AS enum_value,
    e.enumsortorder
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
JOIN pg_namespace n ON n.oid = t.typnamespace
ORDER BY schema_name, enum_name, enumsortorder;

\echo ''
\echo '------------------------------------------------------------'
\echo '6. EXTENSIONS'
\echo '------------------------------------------------------------'
SELECT extname, extversion
FROM pg_extension
ORDER BY extname;

\echo ''
\echo '------------------------------------------------------------'
\echo '7. TIMESCALEDB — HYPERTABLES (DYNAMIC)'
\echo '------------------------------------------------------------'
DO $$
DECLARE
    r RECORD;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'timescaledb_information'
          AND table_name = 'hypertables'
    ) THEN
        FOR r IN
            EXECUTE 'SELECT hypertable_schema, hypertable_name, compression_enabled
                     FROM timescaledb_information.hypertables
                     ORDER BY hypertable_schema, hypertable_name'
        LOOP
            RAISE NOTICE 'hypertable: %.% (compression=%)',
                r.hypertable_schema, r.hypertable_name, r.compression_enabled;
        END LOOP;
    ELSE
        RAISE NOTICE 'No Timescale hypertables view present.';
    END IF;
END $$;

\echo ''
\echo '------------------------------------------------------------'
\echo '8. TIMESCALEDB — RETENTION & COMPRESSION POLICIES (JOBS)'
\echo '------------------------------------------------------------'

DO $$
DECLARE
    r RECORD;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'timescaledb_information'
          AND table_name = 'jobs'
    ) THEN
        FOR r IN
            EXECUTE $q$
                SELECT
                  proc_name,
                  hypertable_schema,
                  hypertable_name,
                  config
                FROM timescaledb_information.jobs
                WHERE proc_name IN ('policy_retention', 'policy_compression')
                  AND hypertable_schema = 'public'
                  AND hypertable_name IN ('ohlcv', 'options_chains')
                ORDER BY proc_name, hypertable_name
            $q$
        LOOP
            RAISE NOTICE '% | %.% | %',
                r.proc_name,
                r.hypertable_schema,
                r.hypertable_name,
                r.config;
        END LOOP;
    ELSE
        RAISE NOTICE 'timescaledb_information.jobs not present.';
    END IF;
END $$;

\echo ''
\echo '------------------------------------------------------------'
\echo '9. LEGACY / DEPRECATED ARTIFACT CHECK'
\echo '------------------------------------------------------------'
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname ILIKE '%b4%'
   OR tablename ILIKE '%deprecated%'
ORDER BY schemaname, tablename;

\echo ''
\echo '------------------------------------------------------------'
\echo '10. OBJECT COUNT SUMMARY'
\echo '------------------------------------------------------------'
SELECT 'tables' AS object_type, COUNT(*) FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'indexes', COUNT(*) FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'constraints', COUNT(*) FROM information_schema.table_constraints
WHERE table_schema NOT IN ('pg_catalog', 'information_schema');

\echo ''
\echo '============================================================'
\echo 'END OF KAPMAN SCHEMA PARITY VERIFICATION'
\echo '============================================================'