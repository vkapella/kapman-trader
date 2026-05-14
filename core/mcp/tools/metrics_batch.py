from __future__ import annotations

from typing import Any

from core.mcp.tools.metrics import get_metrics


BATCH_CAP = 30
BATCH_CAP_ERROR = "BATCH_CAP_EXCEEDED"


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        symbol = str(raw).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _batch_cap_error(received: int) -> dict[str, Any]:
    return {"error": BATCH_CAP_ERROR, "max": BATCH_CAP, "received": received}


def get_metrics_batch(symbols: list[str], as_of_date: str) -> dict[str, Any]:
    if len(symbols) > BATCH_CAP:
        return _batch_cap_error(len(symbols))

    requested = _normalize_symbols(symbols)
    results: dict[str, dict[str, Any]] = {}
    missing_symbols: list[str] = []

    for symbol in requested:
        try:
            result = get_metrics(symbol, as_of_date=as_of_date)
        except ValueError:
            missing_symbols.append(symbol)
            continue
        if result.get("data_quality_flags", {}).get("missing_snapshot"):
            missing_symbols.append(symbol)
            continue
        results[symbol] = result

    return {
        "results": results,
        "missing_symbols": missing_symbols,
        "as_of_date": as_of_date,
    }
