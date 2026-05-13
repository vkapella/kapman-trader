from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from core.mcp.db.connection import readonly_connection
from core.mcp.db import queries
from core.mcp.schema import METRIC_CATEGORY_TO_COLUMN


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("as_of_date must be YYYY-MM-DD") from exc


def get_metrics(
    symbol: str,
    as_of_date: Optional[str] = None,
    include: Optional[list[str]] = None,
    metric_keys: Optional[list[str]] = None,
) -> dict[str, Any]:
    if not symbol or not symbol.strip():
        raise ValueError("symbol is required")
    requested = include or ["price", "technical", "volatility", "dealer"]
    invalid = [k for k in requested if k not in METRIC_CATEGORY_TO_COLUMN]
    if invalid:
        raise ValueError(f"unsupported include categories: {invalid}")
    parsed_date = _parse_date(as_of_date)

    with readonly_connection() as conn:
        ticker = queries.resolve_ticker(conn, symbol)
        if not ticker:
            raise ValueError(f"unknown symbol: {symbol}")
        snap = queries.latest_snapshot_for_symbol(conn, ticker_id=ticker["ticker_id"], as_of_date=parsed_date)

    result: dict[str, Any] = {
        "symbol": ticker["symbol"],
        "ticker_id": ticker["ticker_id"],
        "effective_as_of_date": parsed_date.isoformat() if parsed_date else None,
        "latest_eligible_snapshot_date": snap["ny_date"].isoformat() if snap else None,
        "metrics": {},
        "data_quality_flags": {
            "missing_snapshot": snap is None,
            "missing_metric_category": False,
        },
    }

    if not snap:
        for category in requested:
            result["metrics"][category] = {}
        if metric_keys:
            for category in requested:
                result["metrics"][category] = {k: None for k in metric_keys}
        return result

    any_missing_category = False
    for category in requested:
        blob = snap.get(METRIC_CATEGORY_TO_COLUMN[category]) or {}
        if not blob:
            any_missing_category = True
        if metric_keys:
            result["metrics"][category] = {k: blob.get(k) for k in metric_keys}
        else:
            result["metrics"][category] = blob
    result["data_quality_flags"]["missing_metric_category"] = any_missing_category
    return result
