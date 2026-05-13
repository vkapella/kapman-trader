from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from core.mcp.db.connection import readonly_connection
from core.mcp.db import queries


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("as_of_date must be YYYY-MM-DD") from exc


def _passes_list_filter(value: Optional[str], raw_filter: Any) -> bool:
    if raw_filter is None:
        return True
    if isinstance(raw_filter, list):
        includes = {str(v).upper() for v in raw_filter}
        return (value or "").upper() in includes
    if isinstance(raw_filter, dict):
        includes = {str(v).upper() for v in raw_filter.get("include", [])}
        excludes = {str(v).upper() for v in raw_filter.get("exclude", [])}
        token = (value or "").upper()
        if includes and token not in includes:
            return False
        if token in excludes:
            return False
        return True
    raise ValueError("list filters must be list or object with include/exclude")


def screen_watchlist(as_of_date: Optional[str] = None, filters: Optional[dict[str, Any]] = None, limit: int = 50) -> dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit must be > 0")
    parsed_date = _parse_date(as_of_date)
    filters = filters or {}

    with readonly_connection() as conn:
        rows = queries.screen_rows(conn, as_of_date=parsed_date)

    out: list[dict[str, Any]] = []
    for row in rows:
        if not _passes_list_filter(row["regime"], filters.get("regime")):
            continue
        if not _passes_list_filter(row["primary_event"], filters.get("primary_event")):
            continue

        iv_rank = row.get("iv_rank")
        dgpi = row.get("dgpi")
        rvol = row.get("rvol")
        if filters.get("iv_rank_min") is not None and (iv_rank is None or iv_rank < filters["iv_rank_min"]):
            continue
        if filters.get("iv_rank_max") is not None and (iv_rank is None or iv_rank > filters["iv_rank_max"]):
            continue
        if filters.get("dgpi_min") is not None and (dgpi is None or dgpi < filters["dgpi_min"]):
            continue
        if filters.get("rvol_min") is not None and (rvol is None or rvol < filters["rvol_min"]):
            continue
        if filters.get("exclude_missing_data") and (not row["has_snapshot"] or iv_rank is None or dgpi is None or rvol is None):
            continue

        out.append(row)

    out.sort(key=lambda r: ((r.get("dgpi") is None), -(r.get("dgpi") or -10**9), r["symbol"]))
    return {
        "effective_as_of_date": parsed_date.isoformat() if parsed_date else None,
        "count": min(len(out), limit),
        "results": out[:limit],
    }
