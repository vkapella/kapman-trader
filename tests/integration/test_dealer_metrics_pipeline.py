from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.ingestion.options.db import upsert_options_chains_rows
from core.metrics.dealer_metrics_job import _snapshot_time_utc, run_dealer_metrics_job


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _seed_ticker(conn, *, symbol: str, spot: Decimal, snapshot_date: date) -> str:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickers (symbol) VALUES (%s) RETURNING id::text", (symbol,))
        ticker_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO watchlists (watchlist_id, symbol, active, source, effective_date)
            VALUES (%s, %s, TRUE, %s, %s)
            """,
            ("default", symbol, "test", snapshot_date),
        )
        cur.execute(
            """
            INSERT INTO ohlcv (ticker_id, date, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ticker_id,
                snapshot_date,
                spot,
                spot + Decimal("1.0"),
                spot - Decimal("1.0"),
                spot,
                1_000_000,
            ),
        )
    conn.commit()
    return ticker_id


def _options_row(
    *,
    snapshot_time: datetime,
    ticker_id: str,
    expiration_date: date,
    strike: Decimal,
    option_type: str,
    bid: Decimal,
    ask: Decimal,
    last: Decimal,
    volume: int,
    open_interest: int,
    gamma: Decimal,
    delta: Decimal,
) -> dict:
    return {
        "time": snapshot_time,
        "ticker_id": ticker_id,
        "expiration_date": expiration_date,
        "strike_price": strike,
        "option_type": option_type,
        "bid": bid,
        "ask": ask,
        "last": last,
        "volume": volume,
        "open_interest": open_interest,
        "implied_volatility": Decimal("0.30"),
        "delta": delta,
        "gamma": gamma,
        "theta": None,
        "vega": None,
    }


@pytest.mark.integration
@pytest.mark.db
def test_dealer_metrics_pipeline_persists_metrics_and_invalid_soft_fail() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_date = date(2025, 1, 2)
    snapshot_time = _snapshot_time_utc(snapshot_date)

    with psycopg2.connect(db_url) as conn:
        good_ticker = _seed_ticker(conn, symbol="AAPL", spot=Decimal("100.0"), snapshot_date=snapshot_date)
        bad_ticker = _seed_ticker(conn, symbol="MSFT", spot=Decimal("200.0"), snapshot_date=snapshot_date)

        rows: list[dict] = []
        # Calls (primary wall at 100)
        call_strikes = [Decimal("100"), Decimal("105"), Decimal("110"), Decimal("115"), Decimal("120"), Decimal("125")]
        call_ois = [400, 300, 200, 180, 150, 140]
        if len(call_strikes) != len(call_ois):
            raise ValueError("call_strikes and call_ois must have equal length")
        for idx, (strike, oi) in enumerate(zip(call_strikes, call_ois)):
            rows.append(
                _options_row(
                    snapshot_time=snapshot_time,
                    ticker_id=good_ticker,
                    expiration_date=snapshot_date + timedelta(days=30 + idx),
                    strike=strike,
                    option_type="C",
                    bid=Decimal("1.00") + Decimal(idx) * Decimal("0.01"),
                    ask=Decimal("1.05") + Decimal(idx) * Decimal("0.01"),
                    last=Decimal("1.02") + Decimal(idx) * Decimal("0.01"),
                    volume=10 + idx,
                    open_interest=oi,
                    gamma=Decimal("0.02"),
                    delta=Decimal("0.5"),
                )
            )

        # Puts (primary wall at 90)
        put_strikes = [Decimal("90"), Decimal("95"), Decimal("85"), Decimal("80"), Decimal("75"), Decimal("70")]
        put_ois = [420, 360, 320, 280, 260, 240]
        if len(put_strikes) != len(put_ois):
            raise ValueError("put_strikes and put_ois must have equal length")
        for idx, (strike, oi) in enumerate(zip(put_strikes, put_ois)):
            rows.append(
                _options_row(
                    snapshot_time=snapshot_time,
                    ticker_id=good_ticker,
                    expiration_date=snapshot_date + timedelta(days=35 + idx),
                    strike=strike,
                    option_type="P",
                    bid=Decimal("1.10") + Decimal(idx) * Decimal("0.01"),
                    ask=Decimal("1.15") + Decimal(idx) * Decimal("0.01"),
                    last=Decimal("1.12") + Decimal(idx) * Decimal("0.01"),
                    volume=12 + idx,
                    open_interest=oi,
                    gamma=Decimal("-0.02"),
                    delta=Decimal("-0.5"),
                )
            )

        upsert_options_chains_rows(conn, rows=rows)

        # Bad ticker: no options at snapshot_time -> should soft-fail as invalid.
        run_dealer_metrics_job(conn, snapshot_dates=[snapshot_date])

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ticker_id::text, dealer_metrics_json::text
                FROM daily_snapshots
                WHERE time = %s
                ORDER BY ticker_id
                """,
                (snapshot_time,),
            )
            results = cur.fetchall()

        assert len(results) == 2
        payloads = {tid: json.loads(text) for tid, text in results}

        good = payloads[good_ticker]
        assert good["confidence"] in {"high", "medium"}
        assert good["call_walls"][0]["strike"] == 100.0
        assert good["put_walls"][0]["strike"] == 90.0
        assert len(good["call_walls"]) == 3
        assert len(good["put_walls"]) == 3
        assert good["gex_total"] is not None
        assert good["gex_net"] is not None
        assert good["metadata"]["filters"]["max_dte_days"] == 90
        assert good["metadata"]["spot"] == 100.0

        bad = payloads[bad_ticker]
        assert bad["confidence"] == "invalid"
        assert "diagnostics" in bad["metadata"]
