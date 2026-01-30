\timing on
\echo '============================================================'
\echo ' B2 STALL ROOT CAUSE DASHBOARD'
\echo '============================================================'

------------------------------------------------------------
-- 1) GLOBAL MAX SNAPSHOT DATE (NY)
------------------------------------------------------------
\echo ''
\echo '--- GLOBAL MAX DAILY_SNAPSHOTS (NY DATE) ---'
SELECT
  max((time AT TIME ZONE 'America/New_York')::date) AS max_ny_date,
  max(time) AS max_time_utc,
  count(*) FILTER (WHERE (time AT TIME ZONE 'America/New_York')::date >= (current_date - 10)) AS rows_last_10_calendar_days
FROM daily_snapshots;

------------------------------------------------------------
-- 2) B2 EVENTS LAST SEEN (NY)
------------------------------------------------------------
\echo ''
\echo '--- EVENTS_JSON LAST SEEN (NY DATE) ---'
SELECT
  max((time AT TIME ZONE 'America/New_York')::date) AS last_events_ny_date,
  max(time) AS last_events_time_utc,
  count(*) AS total_rows_with_events
FROM daily_snapshots
WHERE events_json IS NOT NULL;

------------------------------------------------------------
-- 3) PER-DAY EVENTS COUNTS (LAST 15 TRADING DAYS PRESENT IN SNAPSHOTS)
------------------------------------------------------------
\echo ''
\echo '--- EVENTS COUNTS VS SNAPSHOT COUNTS (LAST 15 SNAPSHOT DAYS) ---'
WITH last_days AS (
  SELECT DISTINCT (time AT TIME ZONE 'America/New_York')::date AS ny_date
  FROM daily_snapshots
  ORDER BY 1 DESC
  LIMIT 15
)
SELECT
  d.ny_date,
  count(*) AS snapshot_rows,
  count(*) FILTER (WHERE ds.events_json IS NOT NULL) AS rows_with_events,
  round(100.0 * count(*) FILTER (WHERE ds.events_json IS NOT NULL) / nullif(count(*),0), 2) AS pct_events
FROM last_days d
JOIN daily_snapshots ds
  ON (ds.time AT TIME ZONE 'America/New_York')::date = d.ny_date
GROUP BY d.ny_date
ORDER BY d.ny_date DESC;

------------------------------------------------------------
-- 4) WYCKOFF REGIME COVERAGE (B1) FOR SAME DAYS
------------------------------------------------------------
\echo ''
\echo '--- WYCKOFF REGIME COVERAGE (B1) LAST 15 SNAPSHOT DAYS ---'
WITH last_days AS (
  SELECT DISTINCT (time AT TIME ZONE 'America/New_York')::date AS ny_date
  FROM daily_snapshots
  ORDER BY 1 DESC
  LIMIT 15
)
SELECT
  d.ny_date,
  count(*) AS snapshot_rows,
  count(*) FILTER (WHERE ds.wyckoff_regime IS NOT NULL) AS rows_with_regime,
  round(100.0 * count(*) FILTER (WHERE ds.wyckoff_regime IS NOT NULL) / nullif(count(*),0), 2) AS pct_regime
FROM last_days d
JOIN daily_snapshots ds
  ON (ds.time AT TIME ZONE 'America/New_York')::date = d.ny_date
GROUP BY d.ny_date
ORDER BY d.ny_date DESC;

------------------------------------------------------------
-- 5) B2 TABLES ADVANCEMENT CHECK (if they are populated by B2)
------------------------------------------------------------
\echo ''
\echo '--- WYCKOFF CONTEXT EVENTS LAST SEEN ---'
SELECT
  max((event_time AT TIME ZONE 'America/New_York')::date) AS last_ny_date,
  max(event_time) AS last_time_utc,
  count(*) AS total_rows
FROM wyckoff_context_events;

\echo ''
\echo '--- WYCKOFF SEQUENCE EVENTS LAST SEEN ---'
SELECT
  max((event_time AT TIME ZONE 'America/New_York')::date) AS last_ny_date,
  max(event_time) AS last_time_utc,
  count(*) AS total_rows
FROM wyckoff_sequence_events;

\echo ''
\echo '============================================================'
\echo ' B2 STALL DASHBOARD COMPLETE'
\echo '============================================================'