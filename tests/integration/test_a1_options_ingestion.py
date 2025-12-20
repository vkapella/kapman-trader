from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.ingestion.options.pipeline import ingest_options_chains_from_watchlists
from core.providers.market_data.polygon_options import PolygonOptionsProvider


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _seed_ticker(conn, symbol: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tickers (symbol, name, is_active, created_at) VALUES (%s, %s, TRUE, NOW()) RETURNING id::text",
            (symbol.upper(), symbol.upper()),
        )
        return str(cur.fetchone()[0])


def _seed_watchlist_symbol(conn, watchlist_id: str, symbol: str, *, active: bool = True) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO watchlists (watchlist_id, symbol, active, source, effective_date)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (watchlist_id, symbol) DO UPDATE SET active = EXCLUDED.active, updated_at = NOW()
            """,
            (watchlist_id, symbol.upper(), bool(active), "test", datetime(2025, 12, 20).date()),
        )


def _polygon_contract(
    *,
    ticker: str,
    expiration_date: str,
    strike_price: float | int,
    contract_type: str,
    bid: float | None = None,
    ask: float | None = None,
    last: float | None = None,
    volume: int | None = None,
    open_interest: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "details": {
            "ticker": ticker,
            "expiration_date": expiration_date,
            "strike_price": strike_price,
            "contract_type": contract_type,
        }
    }
    if bid is not None or ask is not None:
        payload["last_quote"] = {"bid": bid, "ask": ask}
    if last is not None:
        payload["last_trade"] = {"price": last}
    if volume is not None:
        payload["day"] = {"volume": volume, "close": last}
    if open_interest is not None:
        payload["open_interest"] = open_interest
    return payload


class _FakeProvider:
    def __init__(self, mapping: dict[str, list[dict[str, Any]]]) -> None:
        self.mapping = mapping
        self.request_timeout = 1.0

    async def fetch_options_snapshot_chain(self, underlying: str, **kwargs):
        for snap in self.mapping.get(underlying.upper(), []):
            yield snap


@pytest.mark.integration
@pytest.mark.db
def test_a1_ingests_multiple_symbols_is_idempotent_and_no_duplicates() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        _seed_ticker(conn, "AAPL")
        _seed_ticker(conn, "MSFT")
        _seed_watchlist_symbol(conn, "wl1", "AAPL", active=True)
        _seed_watchlist_symbol(conn, "wl2", "AAPL", active=True)
        _seed_watchlist_symbol(conn, "wl1", "MSFT", active=True)
        _seed_watchlist_symbol(conn, "wl1", "TSLA", active=False)
        conn.commit()

    provider = _FakeProvider(
        {
            "AAPL": [
                _polygon_contract(
                    ticker="O:AAPL260116C00055000",
                    expiration_date="2026-01-16",
                    strike_price=55,
                    contract_type="call",
                    bid=1.0,
                    ask=1.1,
                    last=1.05,
                    volume=10,
                    open_interest=100,
                ),
                _polygon_contract(
                    ticker="O:AAPL260116P00050000",
                    expiration_date="2026-01-16",
                    strike_price=50,
                    contract_type="put",
                    bid=2.0,
                    ask=2.1,
                    last=2.05,
                    volume=20,
                    open_interest=200,
                ),
            ],
            "MSFT": [
                _polygon_contract(
                    ticker="O:MSFT260116C00100000",
                    expiration_date="2026-01-16",
                    strike_price=100,
                    contract_type="call",
                    bid=3.0,
                    ask=3.1,
                    last=3.05,
                    volume=30,
                    open_interest=300,
                ),
            ],
        }
    )

    snapshot_time = datetime(2025, 12, 20, 0, 0, tzinfo=timezone.utc)
    ingest_options_chains_from_watchlists(
        db_url=db_url,
        api_key="test",
        snapshot_time=snapshot_time,
        concurrency=2,
        provider=provider,  # type: ignore[arg-type]
    )

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM options_chains")
            assert int(cur.fetchone()[0]) == 3
            cur.execute(
                """
                SELECT 1
                FROM options_chains
                GROUP BY time, ticker_id, expiration_date, strike_price, option_type
                HAVING COUNT(*) > 1
                """
            )
            assert cur.fetchone() is None

    ingest_options_chains_from_watchlists(
        db_url=db_url,
        api_key="test",
        snapshot_time=snapshot_time,
        concurrency=2,
        provider=provider,  # type: ignore[arg-type]
    )

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM options_chains")
            assert int(cur.fetchone()[0]) == 3


@pytest.mark.integration
@pytest.mark.db
def test_a1_persists_multiple_snapshot_times_for_same_contracts() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        ticker_id = _seed_ticker(conn, "AAPL")
        _seed_watchlist_symbol(conn, "wl1", "AAPL", active=True)
        conn.commit()

    contract_a = "O:AAPL260116C00055000"
    contract_b = "O:AAPL260116P00050000"

    provider = _FakeProvider(
        {
            "AAPL": [
                _polygon_contract(
                    ticker=contract_a,
                    expiration_date="2026-01-16",
                    strike_price=55,
                    contract_type="call",
                    bid=1.0,
                    ask=1.1,
                    last=1.05,
                    volume=10,
                    open_interest=100,
                ),
                _polygon_contract(
                    ticker=contract_b,
                    expiration_date="2026-01-16",
                    strike_price=50,
                    contract_type="put",
                    bid=2.0,
                    ask=2.1,
                    last=2.05,
                    volume=20,
                    open_interest=200,
                ),
            ]
        }
    )

    t1 = datetime(2025, 12, 20, 0, 0, tzinfo=timezone.utc)
    ingest_options_chains_from_watchlists(
        db_url=db_url,
        api_key="test",
        snapshot_time=t1,
        concurrency=1,
        provider=provider,  # type: ignore[arg-type]
    )

    provider.mapping["AAPL"] = [
        _polygon_contract(
            ticker=contract_a,
            expiration_date="2026-01-16",
            strike_price=55,
            contract_type="call",
            bid=1.2,
            ask=1.3,
            last=1.25,
            volume=11,
            open_interest=101,
        ),
        _polygon_contract(
            ticker=contract_b,
            expiration_date="2026-01-16",
            strike_price=50,
            contract_type="put",
            bid=2.2,
            ask=2.3,
            last=2.25,
            volume=21,
            open_interest=201,
        ),
    ]
    t2 = datetime(2025, 12, 21, 0, 0, tzinfo=timezone.utc)
    ingest_options_chains_from_watchlists(
        db_url=db_url,
        api_key="test",
        snapshot_time=t2,
        concurrency=1,
        provider=provider,  # type: ignore[arg-type]
    )

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM options_chains WHERE ticker_id = %s", (ticker_id,))
            assert int(cur.fetchone()[0]) == 4

            cur.execute(
                """
                SELECT bid, ask, last, volume, open_interest
                FROM options_chains
                WHERE ticker_id = %s
                  AND time = %s
                  AND option_type = 'P'
                  AND strike_price = 50.0000
                """,
                (ticker_id, t2),
            )
            row = cur.fetchone()
            assert row is not None
            assert (float(row[0]), float(row[1]), float(row[2]), row[3], row[4]) == (2.2, 2.3, 2.25, 21, 201)


@pytest.mark.integration
@pytest.mark.db
def test_a1_pagination_ingests_all_pages_end_to_end() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        _seed_ticker(conn, "AAPL")
        _seed_watchlist_symbol(conn, "wl1", "AAPL", active=True)
        conn.commit()

    contract_a = _polygon_contract(
        ticker="O:AAPL260116C00055000",
        expiration_date="2026-01-16",
        strike_price=55,
        contract_type="call",
        bid=1.0,
        ask=1.1,
        last=1.05,
        volume=10,
        open_interest=100,
    )
    contract_b = _polygon_contract(
        ticker="O:AAPL260116P00050000",
        expiration_date="2026-01-16",
        strike_price=50,
        contract_type="put",
        bid=2.0,
        ask=2.1,
        last=2.05,
        volume=20,
        open_interest=200,
    )

    async def mock_get(url, params=None):
        if str(url).startswith("https://api.polygon.io/v3/snapshot/options/AAPL"):
            payload = {"results": [contract_a], "next_url": "https://api.polygon.io/next"}
            return httpx.Response(200, json=payload, request=httpx.Request("GET", str(url)))
        if str(url).startswith("https://api.polygon.io/next"):
            payload = {"results": [contract_b]}
            return httpx.Response(200, json=payload, request=httpx.Request("GET", str(url)))
        raise AssertionError(f"Unexpected url: {url}")

    provider = PolygonOptionsProvider(api_key="test")
    t1 = datetime(2025, 12, 20, 0, 0, tzinfo=timezone.utc)

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=mock_get)):
        ingest_options_chains_from_watchlists(
            db_url=db_url,
            api_key="test",
            snapshot_time=t1,
            concurrency=1,
            provider=provider,
        )

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM options_chains")
            assert int(cur.fetchone()[0]) == 2
