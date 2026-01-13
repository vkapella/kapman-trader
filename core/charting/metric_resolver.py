from __future__ import annotations

import json
import logging
from datetime import date
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


def resolve_json_path(payload: object, path: Sequence[str]) -> object | None:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        if key not in current:
            return None
        current = current[key]
    return current


def normalize_snapshot_payload(payload: object, logger: logging.Logger | None = None) -> dict | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            if logger:
                logger.warning("Failed to decode technical_indicators_json payload")
            return None
    if logger:
        logger.warning("Unexpected technical_indicators_json type: %s", type(payload).__name__)
    return None


def resolve_metric_series(
    snapshots_by_date: dict[date, object],
    date_index: Iterable[pd.Timestamp],
    path: Sequence[str],
    *,
    logger: logging.Logger | None = None,
) -> pd.Series:
    values: list[float] = []
    for ts in date_index:
        snapshot_date = ts.date() if hasattr(ts, "date") else ts
        payload = snapshots_by_date.get(snapshot_date)
        if payload is None:
            values.append(np.nan)
            continue
        if not isinstance(payload, dict):
            payload = normalize_snapshot_payload(payload, logger=logger)
            if payload is None:
                values.append(np.nan)
                continue
        try:
            value = resolve_json_path(payload, path)
        except Exception as exc:
            if logger:
                logger.warning("Failed to resolve metric path %s", ".".join(path), exc_info=exc)
            values.append(np.nan)
            continue
        if isinstance(value, (int, float)):
            values.append(float(value))
        else:
            values.append(np.nan)
    return pd.Series(values, index=pd.Index(date_index))


def series_has_values(series: pd.Series) -> bool:
    return bool(series.dropna().shape[0])
