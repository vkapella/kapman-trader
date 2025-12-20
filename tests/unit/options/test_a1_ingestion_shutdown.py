from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from core.ingestion.options import pipeline as a1_pipeline
from core.providers.market_data.polygon_options import PolygonOptionsProvider


class _DummyConn:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_run_completes_and_returns_report(monkeypatch) -> None:
    monkeypatch.setenv("KAPMAN_OPTIONS_INGEST_PROGRESS_S", "3600")

    monkeypatch.setattr(a1_pipeline.options_db, "connect", lambda db_url: _DummyConn())
    monkeypatch.setattr(a1_pipeline.options_db, "options_ingest_lock_key", lambda: 1)
    monkeypatch.setattr(a1_pipeline.options_db, "try_advisory_lock", lambda conn, key: True)
    monkeypatch.setattr(a1_pipeline.options_db, "advisory_unlock", lambda conn, key: None)
    monkeypatch.setattr(a1_pipeline.options_db, "fetch_ticker_ids", lambda conn, symbols: {s: "tid" for s in symbols})

    async def fake_ingest_one_symbol(**kwargs):
        return a1_pipeline.SymbolIngestionOutcome(
            symbol=kwargs["symbol"],
            ok=True,
            snapshot_rows_fetched=1,
            snapshot_rows_normalized=1,
            rows_persisted=1,
            elapsed_s=0.001,
        )

    monkeypatch.setattr(a1_pipeline, "_ingest_one_symbol", fake_ingest_one_symbol)

    provider = PolygonOptionsProvider(api_key="test")
    report = await a1_pipeline._run_ingestion(
        db_url="postgresql://example.invalid/db",
        api_key="test",
        snapshot_time=datetime(2025, 12, 20, tzinfo=timezone.utc),
        as_of_date=None,
        concurrency=1,
        symbols=["AAPL"],
        mode="adhoc",
        provider=provider,
    )

    assert report.cancelled is False
    assert report.total_rows_persisted == 1


@pytest.mark.asyncio
async def test_run_cancellation_returns_cancelled_report(monkeypatch) -> None:
    monkeypatch.setenv("KAPMAN_OPTIONS_INGEST_PROGRESS_S", "3600")

    monkeypatch.setattr(a1_pipeline.options_db, "connect", lambda db_url: _DummyConn())
    monkeypatch.setattr(a1_pipeline.options_db, "options_ingest_lock_key", lambda: 1)
    monkeypatch.setattr(a1_pipeline.options_db, "try_advisory_lock", lambda conn, key: True)
    monkeypatch.setattr(a1_pipeline.options_db, "advisory_unlock", lambda conn, key: None)
    monkeypatch.setattr(a1_pipeline.options_db, "fetch_ticker_ids", lambda conn, symbols: {s: "tid" for s in symbols})

    started = asyncio.Event()

    async def slow_ingest_one_symbol_v2(**kwargs):
        started.set()
        await asyncio.sleep(10)
        return a1_pipeline.SymbolIngestionOutcome(
            symbol=kwargs["symbol"],
            ok=True,
            snapshot_rows_fetched=0,
            snapshot_rows_normalized=0,
            rows_persisted=0,
            elapsed_s=10.0,
        )

    monkeypatch.setattr(a1_pipeline, "_ingest_one_symbol", slow_ingest_one_symbol_v2)

    provider = PolygonOptionsProvider(api_key="test")
    task = asyncio.create_task(
        a1_pipeline._run_ingestion(
            db_url="postgresql://example.invalid/db",
            api_key="test",
            snapshot_time=datetime(2025, 12, 20, tzinfo=timezone.utc),
            as_of_date=None,
            concurrency=1,
            symbols=["AAPL"],
            mode="adhoc",
            provider=provider,
        )
    )
    await started.wait()
    task.cancel()
    report = await task

    assert report.cancelled is True
