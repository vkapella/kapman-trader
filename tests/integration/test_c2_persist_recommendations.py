from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import psycopg2
import pytest
from psycopg2.extras import Json

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.metrics import c4_batch_ai_screening_job as c4_module


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


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
            ("c2_test", symbol, "integration", snapshot_date),
        )
        cur.execute(
            """
            INSERT INTO daily_snapshots (
                time,
                ticker_id,
                wyckoff_regime,
                wyckoff_regime_confidence,
                wyckoff_regime_set_by_event,
                events_json,
                bc_score,
                spring_score,
                composite_score,
                technical_indicators_json,
                dealer_metrics_json,
                volatility_metrics_json,
                price_metrics_json,
                model_version,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                snapshot_time,
                ticker_id,
                "MARKUP",
                0.85,
                "SOS",
                Json({"events": ["SOS"]}),
                10,
                4,
                12.5,
                Json({"adx": 25}),
                Json({"spot_price": 185.5}),
                Json({"iv_rank": 55}),
                Json({"close": 185.5}),
                "c4-test",
                snapshot_time,
            ),
        )
    conn.commit()


def _fake_response(symbol: str, snapshot_time: datetime) -> dict:
    return {
        "context_label": "MARKUP",
        "confidence_score": 0.75,
        "metric_assessment": {
            "supporting": ["wyckoff_regime", "bc_score"],
            "contradicting": [],
            "neutral": ["volatility_metrics_json"],
        },
        "metric_weights": {"wyckoff_regime": 0.5, "bc_score": 0.2, "volatility_metrics_json": 0.1},
        "discarded_metrics": [],
        "conditional_recommendation": {
            "direction": "LONG",
            "action": "PROCEED",
            "option_type": None,
            "option_strategy": None,
        },
    }


@pytest.mark.integration
@pytest.mark.db
def test_c2_persist_recommendations_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_time = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
    symbol = "AAPL"

    with psycopg2.connect(db_url) as conn:
        _seed_watchlist_snapshot(conn, symbol=symbol, snapshot_time=snapshot_time)

        def _fake_invoke_planning_agent(**_kwargs):
            return _fake_response(symbol, snapshot_time)

        monkeypatch.setattr(c4_module, "invoke_planning_agent", _fake_invoke_planning_agent)

        log = logging.getLogger("test.c2")
        log.handlers.clear()
        log.addHandler(logging.NullHandler())

        c4_module.run_batch_ai_screening(
            conn,
            snapshot_time=snapshot_time,
            ai_provider="anthropic",
            ai_model="test-model",
            batch_size=1,
            batch_wait_seconds=0.0,
            max_retries=0,
            backoff_base_seconds=0.0,
            dry_run=False,
            log=log,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), MAX(justification) FROM recommendations")
            count1, justification = cur.fetchone()

        c4_module.run_batch_ai_screening(
            conn,
            snapshot_time=snapshot_time,
            ai_provider="anthropic",
            ai_model="test-model",
            batch_size=1,
            batch_wait_seconds=0.0,
            max_retries=0,
            backoff_base_seconds=0.0,
            dry_run=False,
            log=log,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM recommendations")
            count2 = cur.fetchone()[0]

    assert count1 == 1
    assert count2 == 1
    assert justification == _canonical_json(_fake_response(symbol, snapshot_time))
