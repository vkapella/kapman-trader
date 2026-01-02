from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import psycopg2
import pytest
from psycopg2.extras import Json

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.metrics.c4_batch_ai_screening_job import run_batch_ai_screening


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _seed_watchlist_snapshot(
    conn,
    *,
    symbol: str,
    snapshot_time: datetime,
) -> None:
    snapshot_date = snapshot_time.date()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickers (symbol) VALUES (%s) RETURNING id::text", (symbol,))
        ticker_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO watchlists (watchlist_id, symbol, active, source, effective_date)
            VALUES (%s, %s, TRUE, %s, %s)
            """,
            ("c4_test", symbol, "integration", snapshot_date),
        )
        cur.execute(
            """
            INSERT INTO daily_snapshots (
                time,
                ticker_id,
                wyckoff_regime,
                wyckoff_regime_confidence,
                events_detected,
                technical_indicators_json,
                volatility_metrics_json,
                dealer_metrics_json,
                price_metrics_json,
                model_version,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                snapshot_time,
                ticker_id,
                "MARKUP",
                0.85,
                ["SOS"],
                Json({"adx": 25}),
                Json({"iv_rank": 55}),
                Json({"spot_price": 185.5}),
                Json({"close": 185.5}),
                "c4-test",
                snapshot_time,
            ),
        )
    conn.commit()


@pytest.mark.integration
@pytest.mark.db
def test_c4_batch_ai_screening_dry_run() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_time = datetime(2025, 12, 5, 23, 59, 59, 999999, tzinfo=timezone.utc)
    symbols = ["AAPL", "MSFT"]

    with psycopg2.connect(db_url) as conn:
        for symbol in symbols:
            _seed_watchlist_snapshot(conn, symbol=symbol, snapshot_time=snapshot_time)

        log = logging.getLogger("test.c4")
        log.handlers.clear()
        log.addHandler(logging.NullHandler())

        responses = run_batch_ai_screening(
            conn,
            snapshot_time=snapshot_time,
            ai_provider="anthropic",
            ai_model="test-model",
            batch_size=2,
            batch_wait_seconds=0.0,
            max_retries=0,
            backoff_base_seconds=0.0,
            dry_run=True,
            log=log,
        )

    assert [entry["ticker"] for entry in responses] == symbols
    for entry in responses:
        raw = entry["raw_normalized_response"]
        assert raw["primary_recommendation"]["rationale_summary"] == "Dry-run stub response."
        assert raw["snapshot_metadata"]["ticker"] in symbols
