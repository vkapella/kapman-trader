from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest

from core.ingestion.options.normalizer import normalize_unicorn_contracts
from core.providers.market_data.unicorn_options import UnicornOptionsProvider


@pytest.mark.unit
def test_normalize_unicorn_contracts_drops_expired() -> None:
    snapshot_date = date(2025, 1, 2)
    raw = [
        {"attributes": {"exp_date": "2025-01-01", "strike": 100, "type": "call"}},
        {"attributes": {"exp_date": "2025-01-03", "strike": 100, "type": "put", "volume": 10}},
    ]

    normalized = normalize_unicorn_contracts(raw, snapshot_date=snapshot_date)
    assert len(normalized) == 1
    assert normalized[0].db_option_type() == "P"
    assert normalized[0].expiration_date == date(2025, 1, 3)
    assert normalized[0].volume == 10


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unicorn_provider_paginates_with_limit_and_offset() -> None:
    provider = UnicornOptionsProvider(api_token="token", max_retries=1, request_timeout=0.1)
    responses = [
        {
            "data": [{"attributes": {"exp_date": "2025-01-03", "strike": 100, "type": "call"}}],
            "links": {"next": "https://eodhd.com/mp/unicornbay/options/contracts?page[offset]=1000"},
        },
        {
            "data": [{"attributes": {"exp_date": "2025-01-04", "strike": 110, "type": "put"}}],
            "links": {},
        },
    ]

    class _Client:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def get(self, url, params=None):
            url_obj = httpx.URL(url)
            if params is not None:
                url_obj = url_obj.copy_with(params=params)
            requested_url = str(url_obj)
            self.calls.append(requested_url)
            payload = responses.pop(0)
            return httpx.Response(200, json=payload, request=httpx.Request("GET", requested_url))

        async def aclose(self):
            return None

    client = _Client()
    collected = []
    pages = []

    async def on_page(count: int) -> None:
        pages.append(count)

    async for row in provider.fetch_options_snapshot_chain(
        "AAPL",
        snapshot_date=date(2025, 1, 1),
        client=client,
        on_page=on_page,
    ):
        collected.append(row)

    assert len(collected) == 2
    assert pages == [1, 1]
    first_params = httpx.URL(client.calls[0]).params
    second_params = httpx.URL(client.calls[1]).params
    assert first_params.get("page[limit]") == "1000"
    assert first_params.get("page[offset]") == "0"
    assert second_params.get("page[limit]") == "1000"
    assert second_params.get("page[offset]") == "1000"
