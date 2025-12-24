\echo '==== OPTIONS CHAINS DASHBOARD ===='

/* ------------------------------------------------------------
   1. Latest Snapshot Summary
------------------------------------------------------------ */
WITH latest AS (
    SELECT max(time) AS snapshot_time
    FROM public.options_chains
)
SELECT
    l.snapshot_time,
    count(DISTINCT oc.ticker_id)      AS symbols_loaded,
    count(*)                          AS total_contracts,
    count(oc.open_interest)           AS oi_rows,
    count(oc.gamma)                   AS gamma_rows,
    count(oc.implied_volatility)      AS iv_rows
FROM public.options_chains oc
JOIN latest l ON oc.time = l.snapshot_time
GROUP BY l.snapshot_time;

/* ------------------------------------------------------------
   2. Per-Symbol Coverage (Top 25)
------------------------------------------------------------ */
WITH latest AS (
    SELECT max(time) AS snapshot_time
    FROM public.options_chains
),
per_symbol AS (
    SELECT
        t.symbol,
        count(*)                        AS contracts,
        count(oc.open_interest)         AS oi_rows,
        count(oc.gamma)                 AS gamma_rows,
        count(oc.implied_volatility)    AS iv_rows
    FROM public.options_chains oc
    JOIN latest l ON oc.time = l.snapshot_time
    JOIN public.tickers t ON t.id = oc.ticker_id
    GROUP BY t.symbol
)
SELECT *
FROM per_symbol
ORDER BY contracts DESC
LIMIT 25;

/* ------------------------------------------------------------
   3. Null Coverage Diagnostics
------------------------------------------------------------ */
WITH latest AS (
    SELECT max(time) AS snapshot_time
    FROM public.options_chains
)
SELECT
    count(*) FILTER (WHERE open_interest IS NULL)       AS null_open_interest,
    count(*) FILTER (WHERE gamma IS NULL)               AS null_gamma,
    count(*) FILTER (WHERE implied_volatility IS NULL)  AS null_iv,
    count(*) FILTER (WHERE bid IS NULL)                 AS null_bid,
    count(*) FILTER (WHERE ask IS NULL)                 AS null_ask
FROM public.options_chains oc
JOIN latest l ON oc.time = l.snapshot_time;

/* ------------------------------------------------------------
   4. Expiration Distribution
------------------------------------------------------------ */
WITH latest AS (
    SELECT max(time) AS snapshot_time
    FROM public.options_chains
)
SELECT
    expiration_date,
    count(*) AS contracts
FROM public.options_chains oc
JOIN latest l ON oc.time = l.snapshot_time
GROUP BY expiration_date
ORDER BY expiration_date;

\echo '==== DAILY OPTIONS SNAPSHOT COVERAGE (BY DAY) ===='

WITH daily AS (
    SELECT
        date_trunc('day', time) AS snapshot_day,
        COUNT(DISTINCT ticker_id) AS symbols_loaded,
        COUNT(*) AS total_contracts,
        COUNT(open_interest) AS oi_rows,
        COUNT(gamma) AS gamma_rows,
        COUNT(implied_volatility) AS iv_rows
    FROM public.options_chains
    GROUP BY 1
),
expected AS (
    SELECT
        COUNT(*) AS expected_symbols
    FROM public.watchlists
    WHERE active = true
)
SELECT
    d.snapshot_day::date                AS snapshot_date,
    d.symbols_loaded,
    e.expected_symbols,
    (d.symbols_loaded = e.expected_symbols) AS full_symbol_coverage,
    d.total_contracts,
    d.oi_rows,
    d.gamma_rows,
    d.iv_rows
FROM daily d
CROSS JOIN expected e
ORDER BY snapshot_date DESC;