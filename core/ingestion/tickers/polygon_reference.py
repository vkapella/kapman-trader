from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

import httpx


class PolygonReferenceError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolygonTicker:
    symbol: str
    name: str | None
    exchange: str | None
    asset_type: str | None
    currency: str | None
    is_active: bool


def _append_api_key(url: str, api_key: str) -> str:
    if "apiKey=" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}apiKey={api_key}"


def fetch_all_active_tickers(
    *,
    api_key: str,
    base_url: str = "https://api.polygon.io/v3/reference/tickers",
    limit: int = 1000,
    timeout_s: float = 60.0,
) -> list[PolygonTicker]:
    if not api_key:
        raise PolygonReferenceError("POLYGON_API_KEY is not set")

    params = {"active": "true", "limit": str(limit), "apiKey": api_key}
    next_url: str | None = base_url
    tickers: list[PolygonTicker] = []

    accepted = 0
    rejected_by_reason: dict[str, int] = {}

    allowed_stock_types = {"CS", "ETF", "ADRC", "ADR"}
    option_markets = {"options"}
    option_types = {"OS", "OPTION", "OP"}

    with httpx.Client(timeout=timeout_s) as client:
        while next_url:
            if next_url == base_url:
                resp = client.get(next_url, params=params)
            else:
                resp = client.get(_append_api_key(next_url, api_key))

            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise PolygonReferenceError(
                    f"Polygon reference tickers request failed: {exc.response.status_code}"
                ) from exc

            data: dict[str, Any] = resp.json()
            results: Iterable[dict[str, Any]] = data.get("results") or []

            for item in results:
                symbol = (item.get("ticker") or "").strip().upper()
                if not symbol:
                    rejected_by_reason["missing_symbol"] = rejected_by_reason.get("missing_symbol", 0) + 1
                    continue

                if len(symbol) > 20:
                    rejected_by_reason["symbol_too_long"] = rejected_by_reason.get("symbol_too_long", 0) + 1
                    logger.warning("Skipping symbol > 20 chars: %s", symbol)
                    continue

                market = (item.get("market") or "").strip().lower()
                asset_type = (item.get("type") or "").strip().upper()

                if market in option_markets or asset_type in option_types:
                    rejected_by_reason["options_excluded"] = rejected_by_reason.get("options_excluded", 0) + 1
                    continue

                # Prefer market when available; Polygon's stock universe is market=stocks.
                if market and market != "stocks":
                    key = f"market_excluded:{market}"
                    rejected_by_reason[key] = rejected_by_reason.get(key, 0) + 1
                    continue

                if asset_type not in allowed_stock_types:
                    key = f"type_excluded:{asset_type or 'UNKNOWN'}"
                    rejected_by_reason[key] = rejected_by_reason.get(key, 0) + 1
                    continue

                currency = item.get("currency_name")
                tickers.append(
                    PolygonTicker(
                        symbol=symbol,
                        name=item.get("name"),
                        exchange=item.get("primary_exchange"),
                        asset_type=item.get("type"),
                        currency=(currency.upper() if isinstance(currency, str) and currency else None),
                        is_active=bool(item.get("active", True)),
                    )
                )
                accepted += 1

            next_url = data.get("next_url")

    logger.info(
        "Polygon tickers: accepted=%s rejected=%s",
        accepted,
        sum(rejected_by_reason.values()),
    )
    if rejected_by_reason:
        for reason in sorted(rejected_by_reason.keys()):
            logger.info("Polygon tickers rejected: %s=%s", reason, rejected_by_reason[reason])

    return tickers
