import asyncio
import logging
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from core.providers.market_data.polygon_options import PolygonOptionsProvider


@pytest.mark.asyncio
async def test_pagination_handled(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test")

    responses = [
        {"results": [{"id": 1}], "next_url": "https://api.polygon.io/next"},
        {"results": [{"id": 2}]},
    ]

    async def mock_get(url, params=None):
        payload = responses.pop(0)
        response = httpx.Response(200, json=payload, request=httpx.Request("GET", url))
        return response

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=mock_get)) as mock_call:
        provider = PolygonOptionsProvider()
        result = await provider.get_options_chain("AAPL", as_of_date=date(2024, 1, 1))

    assert [r["id"] for r in result] == [1, 2]
    assert mock_call.await_count == 2


@pytest.mark.asyncio
async def test_retries_on_transient(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test")

    request = httpx.Request("GET", "https://api.polygon.io/v3/snapshot/options/MSFT")

    async def fail_once(url, params=None):
        if fail_once.called:
            return httpx.Response(200, json={"results": []}, request=request)
        fail_once.called = True
        raise httpx.TimeoutException("timeout", request=request)

    fail_once.called = False

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fail_once)):
        provider = PolygonOptionsProvider(max_retries=2)
        result = await provider.get_options_chain("MSFT")

    assert result == []


@pytest.mark.asyncio
async def test_logs_include_required_fields(monkeypatch, caplog):
    monkeypatch.setenv("POLYGON_API_KEY", "test")
    caplog.set_level(logging.INFO)

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(
            return_value=httpx.Response(
                200, json={"results": []}, request=httpx.Request("GET", "x")
            )
        ),
    ):
        provider = PolygonOptionsProvider()
        await provider.get_options_chain("IBM")

    record = next(r for r in caplog.records if r.levelname == "INFO")
    assert getattr(record, "stage") == "provider"
    assert getattr(record, "symbol") == "IBM"
