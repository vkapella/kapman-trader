from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import logging

from core.ingestion.tickers.polygon_reference import PolygonTicker, fetch_all_active_tickers


def _resp(url: str, payload: dict) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(200, json=payload, request=req)


@pytest.mark.unit
def test_polygon_reference_paginates_next_url_and_aggregates() -> None:
    base_url = "https://api.polygon.io/v3/reference/tickers"
    next_url = "https://api.polygon.io/v3/reference/tickers?cursor=abc"

    calls: list[tuple[str, dict]] = []

    def fake_get(self, url: str, **kwargs):
        calls.append((url, kwargs))
        if url == base_url:
            return _resp(
                url,
                {
                    "results": [
                        {
                            "ticker": "AAPL",
                            "name": "Apple Inc.",
                            "primary_exchange": "XNAS",
                            "type": "CS",
                            "currency_name": "usd",
                            "active": True,
                        },
                        {"name": "MISSING_TICKER_FIELD"},
                    ],
                    "next_url": next_url,
                },
            )
        return _resp(
            url,
            {
                "results": [
                    {
                        "ticker": "MSFT",
                        "name": "Microsoft",
                        "primary_exchange": "XNAS",
                        "type": "CS",
                        "currency_name": "USD",
                        "active": True,
                    }
                ],
                "next_url": None,
            },
        )

    with patch("httpx.Client.get", new=fake_get):
        tickers = fetch_all_active_tickers(api_key="test-key", base_url=base_url, limit=2)

    assert [t.symbol for t in tickers] == ["AAPL", "MSFT"]
    assert tickers[0] == PolygonTicker(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="XNAS",
        asset_type="CS",
        currency="USD",
        is_active=True,
    )
    assert tickers[1].symbol == "MSFT"

    assert calls[0][0] == base_url
    assert calls[0][1]["params"]["apiKey"] == "test-key"
    assert calls[0][1]["params"]["active"] == "true"

    assert calls[1][0].startswith(next_url)
    assert "apiKey=test-key" in calls[1][0]


@pytest.mark.unit
def test_polygon_reference_filters_and_skips_overlength(caplog: pytest.LogCaptureFixture) -> None:
    base_url = "https://api.polygon.io/v3/reference/tickers"
    caplog.set_level(logging.INFO, logger="core.ingestion.tickers.polygon_reference")

    def fake_get(self, url: str, **kwargs):
        return _resp(
            url,
            {
                "results": [
                    {"ticker": "AAPL", "name": "Apple", "type": "CS", "market": "stocks", "active": True},
                    {"ticker": "SPY", "name": "SPDR S&P 500", "type": "ETF", "market": "stocks", "active": True},
                    {"ticker": "BABA", "name": "Alibaba", "type": "ADRC", "market": "stocks", "active": True},
                    {"ticker": "AAPL_OPT", "name": "AAPL option", "type": "OS", "market": "options"},
                    {"ticker": "THIS_SYMBOL_IS_WAY_TOO_LONG_FOR_DB", "type": "CS", "market": "stocks"},
                    {"ticker": "BTC-USD", "type": "CRYPTO", "market": "crypto"},
                    {"ticker": "ABC", "type": "PFD", "market": "stocks"},
                ],
                "next_url": None,
            },
        )

    with patch("httpx.Client.get", new=fake_get):
        tickers = fetch_all_active_tickers(api_key="test-key", base_url=base_url, limit=1000)

    assert [t.symbol for t in tickers] == ["AAPL", "SPY", "BABA"]

    text = "\n".join(r.message for r in caplog.records)
    assert "Skipping symbol > 20 chars" in text
    assert "options_excluded" in text
    assert "market_excluded:crypto" in text
    assert "type_excluded:PFD" in text
