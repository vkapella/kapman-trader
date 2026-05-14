from __future__ import annotations

from datetime import date, datetime
from typing import Any

from core.mcp.db.connection import readonly_connection
from core.mcp.db import queries
from core.mcp.tools.metrics_batch import BATCH_CAP, BATCH_CAP_ERROR, _normalize_symbols


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("as_of_date must be YYYY-MM-DD") from exc


def screen_symbols(symbols: list[str], as_of_date: str) -> dict[str, Any]:
    if len(symbols) > BATCH_CAP:
        return {"error": BATCH_CAP_ERROR, "max": BATCH_CAP, "received": len(symbols)}

    requested = _normalize_symbols(symbols)
    parsed_date = _parse_date(as_of_date)

    with readonly_connection() as conn:
        rows = queries.screen_rows_for_symbols(conn, symbols=requested, as_of_date=parsed_date)

    rows_by_symbol = {row["symbol"]: row for row in rows}
    missing_symbols = [
        symbol
        for symbol in requested
        if symbol not in rows_by_symbol or not rows_by_symbol[symbol]["has_snapshot"]
    ]
    results = [
        row
        for row in rows
        if row["symbol"] in requested and row["has_snapshot"]
    ]
    results.sort(key=lambda r: ((r.get("dgpi") is None), -(r.get("dgpi") or -10**9), r["symbol"]))

    return {
        "effective_as_of_date": parsed_date.isoformat(),
        "count": len(results),
        "results": results,
        "missing_symbols": missing_symbols,
    }
