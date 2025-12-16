import os
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("ASYNC_DATABASE_URL", "sqlite+aiosqlite:///:memory:?cache=shared")

from core.pipeline import options_ingestion
from core.pipeline.options_ingestion import handle_symbol_event, run_batch


class ProviderStub:
    def __init__(self, fail_symbol=None):
        self.fail_symbol = fail_symbol
        self.calls = []

    async def get_options_chain(self, symbol, as_of_date=None):
        self.calls.append(symbol)
        if symbol == self.fail_symbol:
            raise RuntimeError("boom")
        return [
            {"expiration_date": "2024-01-19", "strike_price": 100, "option_type": "call"}
        ]


@pytest.mark.asyncio
async def test_batch_processes_symbols_sorted():
    provider = ProviderStub()
    with patch(
        "core.pipeline.options_ingestion.upsert_option_chains",
        new=AsyncMock(return_value={"inserted": 1, "updated": 0, "skipped": 0, "total": 1}),
    ):
        result = await run_batch(symbols=["MSFT", "AAPL"], provider=provider, as_of_date=date(2024, 1, 1))

    assert result["symbols_processed"] == ["AAPL", "MSFT"]
    assert provider.calls == ["AAPL", "MSFT"]


@pytest.mark.asyncio
async def test_event_handler_invokes_runner():
    with patch(
        "core.pipeline.options_ingestion.ingest_symbol",
        new=AsyncMock(return_value={"inserted": 1}),
    ) as ingest:
        await handle_symbol_event({"symbol": "TSLA"})
        ingest.assert_awaited_once()
        ingest.assert_awaited_with("TSLA", provider=None)


@pytest.mark.asyncio
async def test_failure_does_not_block_next_symbol():
    provider = ProviderStub(fail_symbol="FAIL")
    with patch(
        "core.pipeline.options_ingestion.upsert_option_chains",
        new=AsyncMock(return_value={"inserted": 1, "updated": 0, "skipped": 0, "total": 1}),
    ):
        result = await run_batch(symbols=["FAIL", "GOOD"], provider=provider, as_of_date=date(2024, 1, 1))

    assert result["error_count"] == 1
    assert "GOOD" in result["symbols_processed"]
