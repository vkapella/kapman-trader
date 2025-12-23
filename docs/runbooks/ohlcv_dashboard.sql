\echo '==== OHLCV DASHBOARD ===='
\pset pager off

-- ============================================================
-- PARAMETERS
-- ============================================================
-- DAYS_BACK: how many calendar days to inspect (default via -v)
-- SYMBOL_LIMIT: top-N symbols to show in per-symbol section

-- ============================================================
-- GLOBAL SUMMARY
-- ============================================================
WITH bounds AS (
    SELECT
        (current_date - :'DAYS_BACK'::int) AS start_date,
        current_date AS end_date
),
all_time AS (
    SELECT
        min(date) AS earliest_date,
        max(date) AS latest_date,
        count(*) AS total_rows,
        count(DISTINCT ticker_id) AS distinct_symbols
    FROM public.ohlcv
),
in_range AS (
    SELECT
        count(*) AS total_rows,
        count(DISTINCT ticker_id) AS distinct_symbols
    FROM public.ohlcv o
    JOIN bounds b ON o.date BETWEEN b.start_date AND b.end_date
)
SELECT
    b.start_date,
    b.end_date,
    :'DAYS_BACK'::int AS days_back,
    a.earliest_date,
    a.latest_date,
    a.total_rows        AS total_rows_all_time,
    a.distinct_symbols  AS distinct_symbols_all_time,
    r.total_rows        AS total_rows_in_range,
    r.distinct_symbols AS distinct_symbols_in_range
FROM bounds b, all_time a, in_range r;

-- ============================================================
\echo ''
\echo '---- DAILY OHLCV COVERAGE (BY DAY) ----'
-- ============================================================

WITH bounds AS (
    SELECT
        (current_date - :'DAYS_BACK'::int) AS start_date,
        current_date AS end_date
),
base AS (
    SELECT
        o.date,
        o.ticker_id,
        o.open,
        o.high,
        o.low,
        o.close,
        o.volume
    FROM public.ohlcv o
    JOIN bounds b ON o.date BETWEEN b.start_date AND b.end_date
)
SELECT
    date,
    count(*)                       AS rows,
    count(DISTINCT ticker_id)      AS symbols,
    count(volume)                  AS volume_rows,
    count(open)                    AS open_rows,
    count(close)                   AS close_rows
FROM base
GROUP BY date
ORDER BY date DESC;

-- ============================================================
\echo ''
\echo '---- PER-SYMBOL DETAIL (LATEST DAY) ----'
-- ============================================================

WITH latest_day AS (
    SELECT max(date) AS date FROM public.ohlcv
),
per_symbol AS (
    SELECT
        t.symbol,
        count(*) AS rows,
        sum(o.volume) AS total_volume,
        min(o.date) AS first_date,
        max(o.date) AS last_date
    FROM public.ohlcv o
    JOIN latest_day d ON o.date = d.date
    JOIN public.tickers t ON t.id = o.ticker_id
    GROUP BY t.symbol
)
SELECT *
FROM per_symbol
ORDER BY rows DESC
LIMIT :'SYMBOL_LIMIT'::int;

-- ============================================================
\echo ''
\echo '---- NULL FIELD COUNTS (ALL DATA) ----'
-- ============================================================

WITH null_checks AS (
    SELECT
        count(*) FILTER (WHERE open   IS NULL) AS null_open,
        count(*) FILTER (WHERE high   IS NULL) AS null_high,
        count(*) FILTER (WHERE low    IS NULL) AS null_low,
        count(*) FILTER (WHERE close  IS NULL) AS null_close,
        count(*) FILTER (WHERE volume IS NULL) AS null_volume
    FROM public.ohlcv
)
SELECT * FROM null_checks;