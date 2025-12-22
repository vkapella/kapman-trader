from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import httpx
import psycopg2
import pytest
from unittest.mock import patch

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.ingestion.options.normalizer import normalize_unicorn_contracts
from core.ingestion.options.pipeline import ingest_options_chains_from_watchlists
from core.ingestion.options import pipeline as a1_pipeline


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


class _CountingProvider:
    name = "unicorn"

    def __init__(self, mapping: dict[str, list[dict[str, Any]]]) -> None:
        self.mapping = mapping
        self.request_timeout = 0.1
        self.calls: list[str] = []

    async def fetch_options_snapshot_chain(self, underlying: str, snapshot_date=None, on_page=None, **kwargs):
        sym = underlying.upper()
        self.calls.append(sym)
        rows = self.mapping.get(sym, [])
        if on_page is not None:
            await on_page(len(rows))
        for row in rows:
            yield row

    def normalize_results(self, raw_results: list[dict[str, Any]], *, snapshot_date):
        return normalize_unicorn_contracts(raw_results, snapshot_date=snapshot_date)


class _FailingProvider(_CountingProvider):
    def __init__(self, success_mapping: dict[str, list[dict[str, Any]]], fail_symbol: str) -> None:
        super().__init__(success_mapping)
        self.fail_symbol = fail_symbol.upper()

    async def fetch_options_snapshot_chain(self, underlying: str, snapshot_date=None, on_page=None, **kwargs):
        sym = underlying.upper()
        self.calls.append(sym)
        rows = self.mapping.get(sym, [])
        if rows and on_page is not None:
            await on_page(len(rows))
        for row in rows:
            yield row
        if sym == self.fail_symbol:
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("synthetic failure", request=request, response=response)


@pytest.mark.integration
@pytest.mark.db
def test_cli_provider_overrides_env(monkeypatch) -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    monkeypatch.setenv("OPTIONS_PROVIDER", "polygon")
    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        _seed_ticker(conn, "AAPL")
        _seed_watchlist_symbol(conn, "wl1", "AAPL", active=True)
        conn.commit()

    provider = _CountingProvider(
        {
            "AAPL": [
                {"attributes": {"contract": "AAPL1", "exp_date": "2026-01-16", "strike": 150, "type": "call", "bid": 1.0, "ask": 1.1, "last": 1.05, "volume": 10, "open_interest": 100}}
            ],
        }
    )

    snapshot_time = datetime(2025, 12, 20, 0, 0, tzinfo=timezone.utc)
    with patch.object(a1_pipeline, "_build_provider", return_value=provider) as mock_build:
        report = ingest_options_chains_from_watchlists(
            db_url=db_url,
            api_key="cli-key",
            snapshot_time=snapshot_time,
            concurrency=1,
            provider_name="unicorn",
        )

    assert mock_build.call_args.args[0] == "unicorn"
    assert report.provider == "unicorn"

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM options_chains")
            assert int(cur.fetchone()[0]) == 1


@pytest.mark.integration
@pytest.mark.db
def test_unicorn_ingestion_dedupes_symbols_and_calls_once() -> None:
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
        conn.commit()

    provider = _CountingProvider(
        {
            "AAPL": [
                {"attributes": {"contract": "AAPL1", "exp_date": "2026-01-16", "strike": 150, "type": "call", "bid": 1.0, "ask": 1.1, "last": 1.05, "volume": 10, "open_interest": 100}}
            ],
            "MSFT": [
                {"attributes": {"contract": "MSFT1", "exp_date": "2026-01-16", "strike": 200, "type": "put", "bid": 2.0, "ask": 2.1, "last": 2.05, "volume": 20, "open_interest": 200}}
            ],
        }
    )

    snapshot_time = datetime(2025, 12, 20, 0, 0, tzinfo=timezone.utc)
    report = ingest_options_chains_from_watchlists(
        db_url=db_url,
        api_key="test",
        snapshot_time=snapshot_time,
        concurrency=2,
        provider=provider,
    )

    assert report.provider == "unicorn"
    assert sorted(provider.calls) == ["AAPL", "MSFT"]

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM options_chains")
            assert int(cur.fetchone()[0]) == 2


@pytest.mark.integration
@pytest.mark.db
def test_unicorn_ingestion_soft_fails_per_ticker() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        _seed_ticker(conn, "AAPL")
        _seed_ticker(conn, "MSFT")
        _seed_watchlist_symbol(conn, "wl1", "AAPL", active=True)
        _seed_watchlist_symbol(conn, "wl1", "MSFT", active=True)
        conn.commit()

    provider = _FailingProvider(
        {
            "AAPL": [
                {"attributes": {"contract": "AAPL1", "exp_date": "2026-01-16", "strike": 150, "type": "call", "bid": 1.0, "ask": 1.1, "last": 1.05, "volume": 10, "open_interest": 100}}
            ],
            "MSFT": [
                {"attributes": {"contract": "MSFT1", "exp_date": "2026-01-16", "strike": 200, "type": "put", "bid": 2.0, "ask": 2.1, "last": 2.05, "volume": 20, "open_interest": 200}}
            ],
        },
        fail_symbol="AAPL",
    )

    snapshot_time = datetime(2025, 12, 20, 0, 0, tzinfo=timezone.utc)
    report = ingest_options_chains_from_watchlists(
        db_url=db_url,
        api_key="test",
        snapshot_time=snapshot_time,
        concurrency=1,
        provider=provider,
    )

    ok = [o for o in report.outcomes if o.ok]
    failed = [o for o in report.outcomes if not o.ok]
    assert len(ok) == 1
    assert len(failed) == 1

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM options_chains")
            assert int(cur.fetchone()[0]) == 1
