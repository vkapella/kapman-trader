CREATE OR REPLACE VIEW v_a3_health_dashboard AS
SELECT
    ds.time,
    ds.ticker_id,
    t.symbol,
    NULLIF(ds.dealer_metrics_json ->> 'spot_price', '')::numeric AS spot_price,
    ds.dealer_metrics_json ->> 'spot_price_source' AS spot_price_source,
    (ds.dealer_metrics_json ->> 'eligible_options_count')::int AS eligible_options,
    (ds.dealer_metrics_json ->> 'total_options_count')::int AS total_options,
    ds.dealer_metrics_json ->> 'status' AS a3_status,
    ds.dealer_metrics_json ->> 'failure_reason' AS dealer_failure_reason,
    ds.dealer_metrics_json ->> 'spot_price_source' AS spot_price_source
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE ds.dealer_metrics_json IS NOT NULL;

COMMENT ON VIEW v_a3_health_dashboard IS
    'A3 dealer metrics health per ticker, including spot price diagnostics and failure reason';
