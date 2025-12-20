from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

logger = logging.getLogger(__name__)


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if int(value) == value else None
        s = str(value).strip()
        return int(s) if s.isdigit() else None
    except (ValueError, TypeError):
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _map_option_type(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    if s in {"C", "CALL"}:
        return "C"
    if s in {"P", "PUT"}:
        return "P"
    return None


@dataclass(frozen=True)
class NormalizedPolygonSnapshot:
    break_even_price: Decimal | None
    implied_volatility: Decimal | None
    open_interest: int | None

    contract_ticker: str | None
    strike_price: Decimal | None
    expiration_date: date | None
    contract_type: str | None
    exercise_style: str | None
    shares_per_contract: int | None

    delta: Decimal | None
    gamma: Decimal | None
    theta: Decimal | None
    vega: Decimal | None

    day_open: Decimal | None
    day_high: Decimal | None
    day_low: Decimal | None
    day_close: Decimal | None
    day_volume: int | None
    day_vwap: Decimal | None

    bid: Decimal | None
    ask: Decimal | None
    last: Decimal | None
    midpoint: Decimal | None

    underlying_ticker: str | None
    underlying_price: Decimal | None

    def db_expiration_date(self) -> date | None:
        return self.expiration_date

    def db_strike_price(self) -> Decimal | None:
        if self.strike_price is None:
            return None
        try:
            return self.strike_price.quantize(Decimal("0.0001"))
        except (InvalidOperation, ValueError):
            return None

    def db_option_type(self) -> str | None:
        return _map_option_type(self.contract_type)


def normalize_polygon_snapshot_result(raw: dict[str, Any]) -> NormalizedPolygonSnapshot:
    details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
    greeks = raw.get("greeks") if isinstance(raw.get("greeks"), dict) else {}
    day = raw.get("day") if isinstance(raw.get("day"), dict) else {}
    last_quote = raw.get("last_quote") if isinstance(raw.get("last_quote"), dict) else {}
    last_trade = raw.get("last_trade") if isinstance(raw.get("last_trade"), dict) else {}
    underlying_asset = raw.get("underlying_asset") if isinstance(raw.get("underlying_asset"), dict) else {}

    return NormalizedPolygonSnapshot(
        break_even_price=_parse_decimal(raw.get("break_even_price")),
        implied_volatility=_parse_decimal(raw.get("implied_volatility")),
        open_interest=_parse_int(raw.get("open_interest")),
        contract_ticker=(details.get("ticker") if details.get("ticker") is not None else None),
        strike_price=_parse_decimal(details.get("strike_price")),
        expiration_date=_parse_date(details.get("expiration_date")),
        contract_type=(details.get("contract_type") if details.get("contract_type") is not None else None),
        exercise_style=(details.get("exercise_style") if details.get("exercise_style") is not None else None),
        shares_per_contract=_parse_int(details.get("shares_per_contract")),
        delta=_parse_decimal(greeks.get("delta")),
        gamma=_parse_decimal(greeks.get("gamma")),
        theta=_parse_decimal(greeks.get("theta")),
        vega=_parse_decimal(greeks.get("vega")),
        day_open=_parse_decimal(day.get("open")),
        day_high=_parse_decimal(day.get("high")),
        day_low=_parse_decimal(day.get("low")),
        day_close=_parse_decimal(day.get("close")),
        day_volume=_parse_int(day.get("volume")),
        day_vwap=_parse_decimal(day.get("vwap")),
        bid=_parse_decimal(last_quote.get("bid")),
        ask=_parse_decimal(last_quote.get("ask")),
        last=_parse_decimal(last_trade.get("price")),
        midpoint=_parse_decimal(last_quote.get("midpoint")),
        underlying_ticker=(underlying_asset.get("ticker") if underlying_asset.get("ticker") is not None else None),
        underlying_price=_parse_decimal(underlying_asset.get("price")),
    )


def normalize_polygon_snapshot_results(results: Iterable[dict[str, Any]]) -> list[NormalizedPolygonSnapshot]:
    normalized: list[NormalizedPolygonSnapshot] = []
    raw_count = 0
    dropped_non_dict = 0
    for raw in results:
        raw_count += 1
        if not isinstance(raw, dict):
            dropped_non_dict += 1
            continue
        normalized.append(normalize_polygon_snapshot_result(raw))

    logger.debug(
        "Normalized Polygon snapshot results",
        extra={
            "stage": "normalizer",
            "raw": raw_count,
            "normalized": len(normalized),
            "dropped_non_dict": dropped_non_dict,
        },
    )
    return normalized
