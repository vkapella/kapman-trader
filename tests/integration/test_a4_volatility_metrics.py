from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone

import psycopg2
import pytest
from psycopg2.extras import Json

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.metrics.a4_volatility_metrics_job import run_volatility_metrics_job
from core.metrics.volatility_metrics import calculate_iv_rank


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _snapshot_time_for_date(snapshot_date: date) -> datetime:
    return datetime(
        snapshot_date.year,
        snapshot_date.month,
        snapshot_date.day,
        23,
        59,
        59,
        999999,
        tzinfo=timezone.utc,
    )


def _insert_daily_snapshot(
    conn,
    *,
    ticker_id: str,
    snapshot_time: datetime,
    metrics_json: dict | None,
    technical_json: dict | None,
    price_json: dict | None,
    dealer_json: dict | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (
                time,
                ticker_id,
                technical_indicators_json,
                dealer_metrics_json,
                price_metrics_json,
                volatility_metrics_json,
                model_version,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                snapshot_time,
                ticker_id,
                Json(technical_json) if technical_json is not None else None,
                Json(dealer_json) if dealer_json is not None else None,
                Json(price_json) if price_json is not None else None,
                Json(metrics_json) if metrics_json is not None else None,
                "pre-a4",
                snapshot_time,
            ),
        )
    conn.commit()


def _seed_watchlist_and_tickers(conn, symbols: list[str], snapshot_date: date) -> list[str]:
    ticker_ids: list[str] = []
    with conn.cursor() as cur:
        for symbol in symbols:
            cur.execute("INSERT INTO tickers (symbol) VALUES (%s) RETURNING id::text", (symbol,))
            ticker_id = cur.fetchone()[0]
            ticker_ids.append(ticker_id)
            cur.execute(
                """
                INSERT INTO watchlists (watchlist_id, symbol, active, source, effective_date)
                VALUES (%s, %s, TRUE, %s, %s)
                """,
                ("a4_test", symbol, "integration", snapshot_date),
            )
    conn.commit()
    return ticker_ids


def _seed_option_snapshot(
    conn,
    *,
    ticker_id: str,
    snapshot_time: datetime,
    contracts: list[dict],
) -> None:
    with conn.cursor() as cur:
        for contract in contracts:
            cur.execute(
                """
                INSERT INTO options_chains (
                    time,
                    ticker_id,
                    expiration_date,
                    strike_price,
                    option_type,
                    bid,
                    ask,
                    last,
                    volume,
                    open_interest,
                    implied_volatility,
                    delta,
                    gamma,
                    theta,
                    vega
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot_time,
                    ticker_id,
                    contract["expiration_date"],
                    contract["strike_price"],
                    contract["option_type"],
                    None,
                    None,
                    None,
                    contract["volume"],
                    contract["open_interest"],
                    contract["implied_volatility"],
                    contract["delta"],
                    None,
                    None,
                    None,
                ),
            )
    conn.commit()


@pytest.mark.integration
@pytest.mark.db
def test_a4_volatility_metrics_batch_behavior(caplog) -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_date = date(2025, 12, 5)
    snapshot_time = _snapshot_time_for_date(snapshot_date)
    symbols = ["AAPL", "MSFT"]
    history_values = [0.18 + i * 0.005 for i in range(25)]
    expected_iv_rank = calculate_iv_rank(0.2494, history_values)

    # Specific option chains for the late snapshot
    long_expiry = date(2026, 3, 5)
    short_expiry = date(2026, 1, 4)
    late_contracts = [
        {
            "expiration_date": short_expiry,
            "strike_price": 100.0,
            "option_type": "C",
            "delta": 0.25,
            "implied_volatility": 0.18,
            "volume": 100,
            "open_interest": 120,
        },
        {
            "expiration_date": long_expiry,
            "strike_price": 100.0,
            "option_type": "C",
            "delta": 0.22,
            "implied_volatility": 0.25,
            "volume": 150,
            "open_interest": 140,
        },
        {
            "expiration_date": short_expiry,
            "strike_price": 95.0,
            "option_type": "P",
            "delta": -0.24,
            "implied_volatility": 0.3,
            "volume": 90,
            "open_interest": 110,
        },
        {
            "expiration_date": long_expiry,
            "strike_price": 95.0,
            "option_type": "P",
            "delta": -0.22,
            "implied_volatility": 0.27,
            "volume": 80,
            "open_interest": 130,
        },
    ]

    # Insert baseline data
    with psycopg2.connect(db_url) as conn:
        ticker_ids = _seed_watchlist_and_tickers(conn, symbols, snapshot_date)
        for ticker_id in ticker_ids:
            for offset, value in enumerate(history_values, start=1):
                prev_time = snapshot_time - timedelta(days=offset)
                _insert_daily_snapshot(
                    conn,
                    ticker_id=ticker_id,
                    snapshot_time=prev_time,
                    metrics_json={"status": "ok", "metrics": {"average_iv": value}},
                    technical_json={"legacy": True},
                    price_json={"price": 1},
                    dealer_json={"dealer": "persist"},
                )
            # Pre-create the snapshot row to test non-clobbering
            _insert_daily_snapshot(
                conn,
                ticker_id=ticker_id,
                snapshot_time=snapshot_time,
                metrics_json=None,
                technical_json={"marker": "keep"},
                price_json={"price": "stable"},
                dealer_json={"status": "unchanged"},
            )

        early_snapshot = snapshot_time.replace(hour=14, minute=0, second=0, microsecond=0)
        late_snapshot = snapshot_time.replace(hour=15, minute=0, second=0, microsecond=0)
        for ticker_id in ticker_ids:
            _seed_option_snapshot(
                conn,
                ticker_id=ticker_id,
                snapshot_time=early_snapshot,
                contracts=[
                    {**contract, "implied_volatility": contract["implied_volatility"] - 0.02}
                    for contract in late_contracts
                ],
            )
            _seed_option_snapshot(
                conn,
                ticker_id=ticker_id,
                snapshot_time=late_snapshot,
                contracts=late_contracts,
            )

        log = logging.getLogger("kapman.a4")
        caplog.set_level(logging.INFO, logger="kapman.a4")
        run_volatility_metrics_job(
            conn,
            snapshot_dates=[snapshot_date],
            fill_missing=False,
            heartbeat_every=1,
            verbose=True,
            debug=False,
            log=log,
        )

        records = [rec.message for rec in caplog.records if rec.levelno == logging.INFO]
        assert any("[A4] START" in msg for msg in records)
        assert any("[A4] END" in msg for msg in records)
        assert any("[A4] HEARTBEAT" in msg for msg in records)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ticker_id::text, technical_indicators_json::text, volatility_metrics_json::text
                FROM daily_snapshots
                WHERE time = %s
                ORDER BY ticker_id
                """,
                (snapshot_time,),
            )
            rows = cur.fetchall()
        assert len(rows) == len(ticker_ids)

        metrics_by_ticker: dict[str, dict] = {}
        for ticker_id, technical_text, volatility_text in rows:
            technical = json.loads(technical_text)
            assert technical == {"marker": "keep"}
            metrics = json.loads(volatility_text)
            assert metrics["status"] == "ok"
            assert metrics["options_snapshot_time"] == late_snapshot.isoformat()
            metric_values = metrics["metrics"]
            assert pytest.approx(0.2494, abs=1e-4) == metric_values["average_iv"]
            assert pytest.approx(0.84, abs=1e-4) == metric_values["oi_ratio"]
            assert pytest.approx(0.9231, abs=1e-4) == metric_values["put_call_ratio_oi"]
            assert metric_values["iv_skew"] == 12.0
            assert metric_values["iv_term_structure"] == 2.0
            assert pytest.approx(expected_iv_rank, abs=1e-2) == metric_values["iv_rank"]
            metrics_by_ticker[ticker_id] = metrics

        assert first_json is not None
        run_volatility_metrics_job(
            conn,
            snapshot_dates=[snapshot_date],
            fill_missing=False,
            heartbeat_every=1,
            verbose=True,
            debug=False,
            log=log,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ticker_id::text, volatility_metrics_json::text FROM daily_snapshots WHERE time = %s ORDER BY ticker_id",
                (snapshot_time,),
            )
            second_rows = cur.fetchall()
        for ticker_id, text in second_rows:
            assert json.loads(text) == metrics_by_ticker[ticker_id]
