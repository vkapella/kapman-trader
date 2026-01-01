from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Optional

import pandas as pd


def normalize_ohlcv(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    if ohlcv_df is None or ohlcv_df.empty:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    data = ohlcv_df.copy()
    data["symbol"] = data["symbol"].astype(str).str.upper()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=["symbol", "date"])
    return data.sort_values(["symbol", "date"]).reset_index(drop=True)


def build_regime_df(snapshots_df: pd.DataFrame) -> pd.DataFrame:
    columns = ["symbol", "date", "regime"]
    if snapshots_df is None or snapshots_df.empty:
        return pd.DataFrame(columns=columns)

    data = snapshots_df.copy()
    if "symbol" not in data.columns or "date" not in data.columns:
        return pd.DataFrame(columns=columns)

    data["symbol"] = data["symbol"].astype(str).str.upper()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["regime"] = data.get("wyckoff_regime")
    data["regime"] = data["regime"].astype(str).str.upper()
    data = data.dropna(subset=["symbol", "date", "regime"])
    return data[columns].sort_values(["symbol", "date"]).reset_index(drop=True)


def build_events_df(snapshots_df: pd.DataFrame, detector: str = "baseline") -> pd.DataFrame:
    columns = ["symbol", "date", "event", "score", "detector"]
    if snapshots_df is None or snapshots_df.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []
    for row in snapshots_df.itertuples(index=False):
        symbol = str(getattr(row, "symbol", "")).upper()
        raw_date = getattr(row, "date", None)
        snapshot_date = pd.to_datetime(raw_date, errors="coerce")
        if not symbol or pd.isna(snapshot_date):
            continue

        events_json = getattr(row, "events_json", None)
        event_rows = _extract_events_from_json(events_json, snapshot_date)

        events_detected = getattr(row, "events_detected", None)
        primary_event = getattr(row, "primary_event", None)

        if event_rows:
            for event_row in event_rows:
                event_name = _normalize_event_name(event_row.get("event") or event_row.get("label"))
                event_date = _coerce_event_date(event_row.get("date")) or snapshot_date
                score = _coerce_score(event_row.get("score"))
                if not event_name:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "date": event_date,
                        "event": event_name,
                        "score": score,
                        "detector": detector,
                    }
                )
            continue

        detected_list = _normalize_event_list(events_detected)
        if detected_list:
            for ev in detected_list:
                rows.append(
                    {
                        "symbol": symbol,
                        "date": snapshot_date,
                        "event": ev,
                        "score": None,
                        "detector": detector,
                    }
                )
            continue

        fallback_event = _normalize_event_name(primary_event)
        if fallback_event:
            rows.append(
                {
                    "symbol": symbol,
                    "date": snapshot_date,
                    "event": fallback_event,
                    "score": None,
                    "detector": detector,
                }
            )

    if not rows:
        return pd.DataFrame(columns=columns)

    data = pd.DataFrame(rows, columns=columns)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["symbol", "date", "event"])
    return data.sort_values(["symbol", "date", "event"]).reset_index(drop=True)


def _normalize_event_list(events: Any) -> list[str]:
    if events is None:
        return []
    if isinstance(events, (list, tuple)):
        values = events
    else:
        values = [events]
    normalized = []
    for value in values:
        name = _normalize_event_name(value)
        if name:
            normalized.append(name)
    return normalized


def _normalize_event_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    name = str(value).strip().upper()
    return name or None


def _coerce_event_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    return pd.to_datetime(value, errors="coerce")


def _coerce_score(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        score = float(value)
    except Exception:
        return None
    if pd.isna(score):
        return None
    return score


def _extract_events_from_json(events_json: Any, snapshot_date: Any) -> list[dict]:
    if events_json is None:
        return []
    data = events_json
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        events = data.get("events")
        if isinstance(events, list):
            return [ev for ev in events if isinstance(ev, dict)]
        return []
    if isinstance(data, list):
        return [ev for ev in data if isinstance(ev, dict)]
    return []
