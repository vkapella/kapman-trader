from __future__ import annotations

import os
from datetime import date, datetime, timezone

import psycopg2
import pytest
from psycopg2.extras import Json

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.daily_snapshots import canonical_daily_snapshot_time
from core.mcp.tools.metrics import get_metrics
from core.mcp.tools.screen_watchlist import screen_watchlist
from core.mcp.tools.wyckoff_proposal import get_wyckoff_proposal_context


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _seed(conn):
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.tickers (id, symbol, name, created_at) VALUES (%s, %s, %s, %s)",
            ("00000000-0000-0000-0000-000000000001", "AMD", "Advanced Micro Devices", now),
        )
        cur.execute(
            "INSERT INTO public.watchlists (watchlist_id, symbol, active, source, effective_date) VALUES (%s,%s,%s,%s,%s)",
            ("core", "AMD", True, "test", date(2026, 1, 10)),
        )
        cur.execute(
            "INSERT INTO public.watchlists (watchlist_id, symbol, active, source, effective_date) VALUES (%s,%s,%s,%s,%s)",
            ("core", "TSLA", True, "test", date(2026, 1, 10)),
        )
        cur.execute(
            "INSERT INTO public.tickers (id, symbol, name, created_at) VALUES (%s, %s, %s, %s)",
            ("00000000-0000-0000-0000-000000000002", "TSLA", "Tesla", now),
        )

        snap_time = canonical_daily_snapshot_time(date(2026, 1, 10))
        dup_time = snap_time.replace(hour=23, minute=59, second=59, microsecond=999998)
        cur.execute(
            """
            INSERT INTO public.daily_snapshots (
                time, ticker_id, wyckoff_regime, wyckoff_regime_confidence, wyckoff_regime_set_by_event,
                events_detected, primary_event, events_json, technical_indicators_json, dealer_metrics_json,
                volatility_metrics_json, price_metrics_json, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                dup_time,
                "00000000-0000-0000-0000-000000000001",
                None,
                None,
                None,
                ["SC"],
                "SC",
                Json({"events": ["SC"]}),
                Json({"rsi": 55.0}),
                Json({"dgpi": 0.1}),
                Json({"iv_rank": 0.4}),
                Json({"rvol": 1.5}),
                now,
            ),
        )
        cur.execute(
            """
            INSERT INTO public.daily_snapshots (
                time, ticker_id, wyckoff_regime, wyckoff_regime_confidence, wyckoff_regime_set_by_event,
                events_detected, primary_event, events_json, technical_indicators_json, dealer_metrics_json,
                volatility_metrics_json, price_metrics_json, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                snap_time,
                "00000000-0000-0000-0000-000000000001",
                "MARKUP",
                0.78,
                "SOS",
                ["SOS"],
                "SOS",
                Json({"events": ["SOS"]}),
                Json({"rsi": 61.0, "macd": 1.2, "adx": 20.0, "obv": 1000, "sma": {"20": 120}, "ema": {"20": 121}}),
                Json({"dgpi": 0.8, "net_gex": 1500}),
                Json({"iv_rank": 0.6, "average_iv": 0.31, "put_call_ratio": 0.8}),
                Json({"rvol": 1.8, "vsi": 1.1, "hv": 0.2}),
                now,
            ),
        )
        cur.execute(
            """
            INSERT INTO public.daily_snapshots (time, ticker_id, wyckoff_regime, primary_event, created_at)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (snap_time, "00000000-0000-0000-0000-000000000002", "ACCUMULATION", "SC", now),
        )

        cur.execute(
            "INSERT INTO public.ohlcv (ticker_id, date, open, high, low, close, volume, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("00000000-0000-0000-0000-000000000001", date(2026, 1, 9), 100, 110, 95, 108, 1000000, now),
        )
        cur.execute(
            "INSERT INTO public.wyckoff_regime_transitions (ticker_id, date, prior_regime, new_regime, duration_bars) VALUES (%s,%s,%s,%s,%s)",
            ("00000000-0000-0000-0000-000000000001", date(2026, 1, 10), "ACCUMULATION", "MARKUP", 5),
        )
        cur.execute(
            "INSERT INTO public.wyckoff_sequences (ticker_id, sequence_id, start_date, completion_date, events_in_sequence) VALUES (%s,%s,%s,%s,%s)",
            ("00000000-0000-0000-0000-000000000001", "SOS-LPS", date(2026, 1, 1), date(2026, 1, 10), Json(["SOS", "LPS"])),
        )
        cur.execute(
            "INSERT INTO public.wyckoff_sequence_events (ticker_id, sequence_id, completion_date, event_type, event_date, event_role, event_order) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("00000000-0000-0000-0000-000000000001", "SOS-LPS", date(2026, 1, 10), "SOS", date(2026, 1, 9), "start", 1),
        )
        cur.execute(
            "INSERT INTO public.wyckoff_context_events (ticker_id, event_date, event_type, prior_regime, context_label) VALUES (%s,%s,%s,%s,%s)",
            ("00000000-0000-0000-0000-000000000001", date(2026, 1, 9), "SOS", "ACCUMULATION", "context"),
        )
        cur.execute(
            "INSERT INTO public.wyckoff_snapshot_evidence (ticker_id, date, evidence_json) VALUES (%s,%s,%s)",
            ("00000000-0000-0000-0000-000000000001", date(2026, 1, 10), Json({"confidence": 0.7})),
        )
    conn.commit()


@pytest.fixture()
def seeded_db(monkeypatch):
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())
    with psycopg2.connect(db_url) as conn:
        _seed(conn)

    monkeypatch.setenv("DATABASE_URL", db_url)
    return db_url


def test_get_wyckoff_proposal_context_shape(seeded_db):
    result = get_wyckoff_proposal_context("AMD", as_of_date="2026-01-10", lookback_days=30)
    assert result["symbol"] == "AMD"
    assert result["pipeline_reading"]["confirmation_status"] == "unconfirmed_pipeline_observation"
    assert result["pipeline_reading"]["regime"] == "MARKUP"
    assert result["data_quality_flags"]["duplicate_same_day_snapshots"] is True


def test_get_metrics_filter_and_nulls(seeded_db):
    result = get_metrics("AMD", include=["price", "technical"], metric_keys=["rvol", "missing_key"])
    assert set(result["metrics"].keys()) == {"price", "technical"}
    assert result["metrics"]["price"]["rvol"] == 1.8
    assert result["metrics"]["technical"]["missing_key"] is None


def test_screen_watchlist_filters_limit(seeded_db):
    result = screen_watchlist(filters={"regime": ["MARKUP"], "dgpi_min": 0.5}, limit=1)
    assert result["count"] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["symbol"] == "AMD"


def test_missing_snapshot_and_missing_ohlcv_flags(seeded_db):
    result = get_wyckoff_proposal_context("AMD", as_of_date="2025-01-01", lookback_days=30)
    assert result["data_quality_flags"]["missing_snapshot"] is True
    assert result["data_quality_flags"]["missing_ohlcv"] is True


def test_no_writes_during_tool_calls(seeded_db):
    with psycopg2.connect(seeded_db) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.daily_snapshots")
            before = cur.fetchone()[0]

    get_wyckoff_proposal_context("AMD", as_of_date="2026-01-10", lookback_days=30)
    get_metrics("AMD")
    screen_watchlist(limit=10)

    with psycopg2.connect(seeded_db) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.daily_snapshots")
            after = cur.fetchone()[0]

    assert before == after
