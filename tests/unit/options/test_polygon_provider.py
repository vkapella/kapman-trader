from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from core.providers.market_data.polygon_options import PolygonOptionsProvider


@pytest.mark.asyncio
async def test_snapshot_chain_paginates_and_appends_api_key_to_next_url(monkeypatch) -> None:
    monkeypatch.setenv("POLYGON_API_KEY", "test")

    calls: list[tuple[str, dict | None]] = []

    async def mock_get(url, params=None):
        calls.append((str(url), params))
        if len(calls) == 1:
            payload = {"results": [{"id": 1}], "next_url": "https://api.polygon.io/next"}
        else:
            payload = {"results": [{"id": 2}]}
        return httpx.Response(200, json=payload, request=httpx.Request("GET", str(url)))

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=mock_get)):
        provider = PolygonOptionsProvider()
        rows = [r async for r in provider.fetch_options_snapshot_chain("AAPL", limit=1)]

    assert [r["id"] for r in rows] == [1, 2]
    assert len(calls) == 2
    assert calls[0][1] == {"apiKey": "test", "limit": 1}
    assert "apiKey=test" in calls[1][0]


@pytest.mark.asyncio
async def test_snapshot_chain_logs_include_stage_and_symbol(monkeypatch, caplog) -> None:
    monkeypatch.setenv("POLYGON_API_KEY", "test")
    caplog.set_level(logging.INFO)

    async def mock_get(url, params=None):
        return httpx.Response(200, json={"results": []}, request=httpx.Request("GET", str(url)))

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=mock_get)):
        provider = PolygonOptionsProvider()
        rows = [r async for r in provider.fetch_options_snapshot_chain("IBM", limit=1)]

    assert rows == []
    record = next(r for r in caplog.records if r.levelname == "INFO" and r.message == "Polygon snapshot fetch started")
    assert getattr(record, "stage") == "provider"
    assert getattr(record, "symbol") == "IBM"
