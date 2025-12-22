from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from core.ingestion.options import pipeline as a1_pipeline
from core.ingestion.options.normalizer import NormalizedOptionContract


class _DummyConn:
    def cursor(self) -> "_DummyConn":
        return self

    def __enter__(self) -> "_DummyConn":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


class _DuplicateUnicornProvider:
    name = "unicorn"
    request_timeout = 0.1

    async def fetch_options_snapshot_chain(self, underlying: str, **kwargs) -> Any:
        yield {}
        yield {}

    def normalize_results(self, raw_results: list[dict[str, Any]], *, snapshot_date: date) -> list[NormalizedOptionContract]:
        contract = NormalizedOptionContract(
            contract_symbol="O:AAPL1",
            expiration_date=date(2026, 1, 16),
            strike_price=Decimal("55"),
            option_type="C",
            bid=Decimal("1.00"),
            ask=Decimal("1.05"),
            last=Decimal("1.02"),
            volume=10,
            open_interest=100,
            implied_volatility=Decimal("0.20"),
            delta=Decimal("0.10"),
            gamma=Decimal("0.05"),
            theta=Decimal("-0.01"),
            vega=Decimal("0.03"),
        )
        contract_dupe = NormalizedOptionContract(
            contract_symbol="O:AAPL2",
            expiration_date=date(2026, 1, 16),
            strike_price=Decimal("55"),
            option_type="C",
            bid=Decimal("1.10"),
            ask=Decimal("1.15"),
            last=Decimal("1.12"),
            volume=12,
            open_interest=120,
            implied_volatility=Decimal("0.25"),
            delta=Decimal("0.15"),
            gamma=Decimal("0.06"),
            theta=Decimal("-0.02"),
            vega=Decimal("0.04"),
        )
        return [contract, contract_dupe]


@pytest.mark.asyncio
async def test_unicorn_dedup_prevents_conflict(monkeypatch) -> None:
    recorded_rows: list[list[dict[str, Any]]] = []

    def _fake_upsert(conn, *, rows: list[dict[str, Any]]) -> int:
        recorded_rows.append(rows.copy())
        return len(rows)

    monkeypatch.setattr(a1_pipeline, "_upsert_options_chains_rows_transactional", _fake_upsert)
    monkeypatch.setattr(a1_pipeline.options_db, "connect", lambda db_url: _DummyConn())

    provider = _DuplicateUnicornProvider()
    async def _progress_cb(**kwargs) -> None:
        return None

    outcome = await a1_pipeline._ingest_one_symbol(
        db_url="postgresql://example.invalid/db",
        provider=provider,
        symbol="AAPL",
        ticker_id="ticker-1",
        snapshot_time=datetime(2025, 12, 20, tzinfo=timezone.utc),
        http_client=None,
        progress_cb=_progress_cb,
    )

    assert outcome.ok
    assert recorded_rows, "No rows were written"
    assert len(recorded_rows[0]) == 1
