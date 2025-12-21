from __future__ import annotations

import importlib.util
import json
import logging
import math
import time
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import pandas as pd
import numpy as np
from psycopg2.extras import Json


DEFAULT_MODEL_VERSION = "MVP-v1"

RVOL_WINDOW_DAYS = 20
VSI_WINDOW_DAYS = 20
HV_WINDOW_DAYS = 20
HV_ANNUALIZATION_DAYS = 252

logger = logging.getLogger(__name__)
_WARNED_INDICATOR_ERRORS: set[str] = set()
_WARNED_PATTERN_ERRORS: bool = False


@dataclass
class A2BatchStats:
    dates: list[str]
    tickers_processed: int
    snapshots_written: int
    indicators_computed_total: int
    indicators_null_total: int
    pattern_indicators_present: int
    duration_seconds: float

    @classmethod
    def empty(cls) -> "A2BatchStats":
        return cls(
            dates=[],
            tickers_processed=0,
            snapshots_written=0,
            indicators_computed_total=0,
            indicators_null_total=0,
            pattern_indicators_present=0,
            duration_seconds=0.0,
        )

    def to_log_extra(self) -> Dict[str, Any]:
        return {
            "dates": self.dates,
            "tickers_processed": self.tickers_processed,
            "snapshots_written": self.snapshots_written,
            "indicators_computed_total": self.indicators_computed_total,
            "indicators_null_total": self.indicators_null_total,
            "pattern_indicators_present": self.pattern_indicators_present,
            "duration_seconds": self.duration_seconds,
        }


@lru_cache(maxsize=1)
def _indicator_surface():
    """
    Dynamically import the authoritative indicator surface contract from:
    `docs/reference/ta_indicator_surface.py`.
    """
    root = Path(__file__).resolve().parents[2]
    surface_path = root / "docs" / "reference" / "ta_indicator_surface.py"
    spec = importlib.util.spec_from_file_location(
        "kapman_ta_indicator_surface", surface_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to import indicator surface at {surface_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _as_scalar_or_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (int, str, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    if hasattr(value, "item"):
        try:
            return _as_scalar_or_none(value.item())
        except Exception:
            return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def _sanitize_for_json(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return _as_scalar_or_none(obj)


def _json_dumps_strict(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _snapshot_time_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)


def _format_elapsed(seconds: float) -> str:
    seconds_i = max(0, int(seconds))
    h = seconds_i // 3600
    m = (seconds_i % 3600) // 60
    s = seconds_i % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def compute_price_metrics_json(ohlcv: pd.DataFrame) -> Dict[str, Optional[float]]:
    """
    Deterministic A2 price metric definitions (latest value only).

    - rvol: Relative volume = volume[t] / mean(volume[t-window : t-1])
    - vsi:  Volume Surprise Index (local) = (volume[t] - mean_prior) / std_prior
            where mean_prior/std_prior are computed over volume[t-window : t-1].
    - hv:   Historical volatility = std(log_returns[t-window+1 : t]) * sqrt(252)
            using ddof=0, annualized.
    """
    out: Dict[str, Optional[float]] = {"rvol": None, "vsi": None, "hv": None}
    if ohlcv.empty:
        return out

    if "volume" in ohlcv.columns:
        volume = pd.to_numeric(ohlcv["volume"], errors="coerce").astype("float64")
        if len(volume) >= RVOL_WINDOW_DAYS + 1:
            prior = volume.iloc[-RVOL_WINDOW_DAYS - 1 : -1]
            mean_prior = float(prior.mean()) if len(prior) else float("nan")
            if not (math.isnan(mean_prior) or math.isinf(mean_prior)) and mean_prior > 0:
                out["rvol"] = _as_scalar_or_none(float(volume.iloc[-1] / mean_prior))

            std_prior = float(prior.std(ddof=0)) if len(prior) else float("nan")
            if (
                not (math.isnan(std_prior) or math.isinf(std_prior))
                and std_prior > 0
                and out["rvol"] is not None
            ):
                out["vsi"] = _as_scalar_or_none(
                    float((volume.iloc[-1] - mean_prior) / std_prior)
                )

    if "close" in ohlcv.columns:
        close = pd.to_numeric(ohlcv["close"], errors="coerce").astype("float64")
        if len(close) >= HV_WINDOW_DAYS + 1:
            log_returns = np.log(close / close.shift(1))
            window_std = float(log_returns.iloc[-HV_WINDOW_DAYS:].std(ddof=0))
            if not (math.isnan(window_std) or math.isinf(window_std)):
                out["hv"] = _as_scalar_or_none(
                    float(window_std * math.sqrt(HV_ANNUALIZATION_DAYS))
                )

    return out


def compute_technical_indicators_json(
    ohlcv: pd.DataFrame,
    *,
    stats: Optional[A2BatchStats] = None,
    log: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    surface = _indicator_surface()
    log = log or logger

    technical: Dict[str, Any] = {
        cat: {} for cat in surface.TECHNICAL_TOP_LEVEL_CATEGORIES
    }

    for category, indicators in surface.INDICATOR_REGISTRY.items():
        technical[category] = {}
        for name, info in indicators.items():
            outputs = {k: None for k in info.get("outputs", [])}
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        result = surface.compute_indicator_latest(ohlcv, category, name)
                computed = result.get("outputs", {}) if isinstance(result, dict) else {}
                for key in outputs.keys():
                    outputs[key] = _as_scalar_or_none(computed.get(key))
            except Exception:
                warn_key = f"{category}.{name}"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", category, name)

            if stats is not None:
                for v in outputs.values():
                    stats.indicators_computed_total += 1
                    if v is None:
                        stats.indicators_null_total += 1

            if log.isEnabledFor(logging.DEBUG):
                log.debug("[A2] indicator computed category=%s name=%s outputs=%s", category, name, outputs)
            technical[category][name] = outputs

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with np.errstate(divide="ignore", invalid="ignore"):
                technical["pattern_recognition"] = surface.compute_pattern_recognition_latest(
                    ohlcv
                )
    except Exception:
        global _WARNED_PATTERN_ERRORS
        if not _WARNED_PATTERN_ERRORS:
            _WARNED_PATTERN_ERRORS = True
            log.warning("[A2] pattern_recognition failed")
        technical["pattern_recognition"] = {
            k: None for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS
        }

    if stats is not None:
        patterns = technical.get("pattern_recognition") or {}
        for v in patterns.values():
            if v is None:
                continue
            try:
                if int(v) != 0:
                    stats.pattern_indicators_present += 1
            except Exception:
                continue

    return technical


def _fetch_active_ticker_ids(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT id::text FROM tickers WHERE is_active = TRUE ORDER BY id")
        return [r[0] for r in cur.fetchall()]


def _fetch_tickers_missing_snapshot(conn, snapshot_time: datetime) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT t.id::text
            FROM tickers t
            WHERE t.is_active = TRUE
              AND NOT EXISTS (
                SELECT 1 FROM daily_snapshots s
                WHERE s.time = %s AND s.ticker_id = t.id
              )
            ORDER BY t.id
            """,
            (snapshot_time,),
        )
        return [r[0] for r in cur.fetchall()]


def _load_ohlcv_history(conn, ticker_id: str, snapshot_date: date) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM ohlcv
            WHERE ticker_id = %s AND date <= %s
            ORDER BY date ASC
            """,
            (ticker_id, snapshot_date),
        )
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(
        rows, columns=["date", "open", "high", "low", "close", "volume"]
    )
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("float64")
    df = df.drop(columns=["date"])
    return df


def _upsert_daily_snapshot(
    conn,
    *,
    snapshot_time: datetime,
    ticker_id: str,
    technical_indicators_json: Dict[str, Any],
    price_metrics_json: Dict[str, Any],
    model_version: str,
    created_at: datetime,
) -> None:
    technical_sanitized = _sanitize_for_json(technical_indicators_json)
    price_sanitized = _sanitize_for_json(price_metrics_json)

    _json_dumps_strict(technical_sanitized)
    _json_dumps_strict(price_sanitized)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (
              time,
              ticker_id,
              technical_indicators_json,
              price_metrics_json,
              model_version,
              created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, ticker_id)
            DO UPDATE SET
              technical_indicators_json = EXCLUDED.technical_indicators_json,
              price_metrics_json       = EXCLUDED.price_metrics_json,
              model_version            = EXCLUDED.model_version,
              created_at               = EXCLUDED.created_at
            """,
            (
                snapshot_time,
                ticker_id,
                Json(technical_sanitized, dumps=_json_dumps_strict),
                Json(price_sanitized, dumps=_json_dumps_strict),
                model_version,
                created_at,
            ),
        )


def run_a2_local_ta_job(
    conn,
    *,
    snapshot_dates: Sequence[date],
    model_version: str = DEFAULT_MODEL_VERSION,
    fill_missing: bool = False,
    heartbeat_every: int = 50,
    verbose: bool = False,
    log: Optional[logging.Logger] = None,
) -> None:
    """
    Batch-only A2 job runner.

    - Deterministic: computed JSON depends only on input OHLCV history
    - Idempotent: upsert into (time, ticker_id) primary key
    - Safe to rerun/backfill: inserts or overwrites only A2-owned columns
    """
    log = log or logger
    if not snapshot_dates:
        return

    run_start = time.monotonic()
    stats = A2BatchStats.empty()
    stats.dates = [d.isoformat() for d in snapshot_dates]

    if fill_missing:
        snapshot_plan: Dict[date, list[str]] = {}
        for d in snapshot_dates:
            snapshot_plan[d] = _fetch_tickers_missing_snapshot(conn, _snapshot_time_utc(d))
    else:
        ticker_ids = _fetch_active_ticker_ids(conn)
        snapshot_plan = {d: ticker_ids for d in snapshot_dates}

    for d in snapshot_dates:
        date_start = time.monotonic()
        snapshot_time = _snapshot_time_utc(d)
        ticker_ids = snapshot_plan.get(d, [])
        total = len(ticker_ids)
        for i, ticker_id in enumerate(ticker_ids, start=1):
            if verbose:
                log.info("[A2] ticker snapshot_date=%s ticker_id=%s", d.isoformat(), ticker_id)
            ohlcv = _load_ohlcv_history(conn, ticker_id, d)

            technical = compute_technical_indicators_json(ohlcv, stats=stats, log=log)
            price_metrics = compute_price_metrics_json(ohlcv)

            _upsert_daily_snapshot(
                conn,
                snapshot_time=snapshot_time,
                ticker_id=ticker_id,
                technical_indicators_json=technical,
                price_metrics_json=price_metrics,
                model_version=model_version,
                created_at=datetime.now(timezone.utc),
            )
            stats.snapshots_written += 1
            stats.tickers_processed += 1

            if heartbeat_every > 0 and i % heartbeat_every == 0:
                elapsed = _format_elapsed(time.monotonic() - date_start)
                log.info(
                    "[A2] progress snapshot_date=%s processed=%s/%s elapsed=%s",
                    d.isoformat(),
                    i,
                    total,
                    elapsed,
                )

        conn.commit()

    stats.duration_seconds = time.monotonic() - run_start
    log.info(
        "[A2] SUMMARY\n"
        "  dates: %s\n"
        "  tickers: %s\n"
        "  snapshots_written: %s\n"
        "  indicators_computed: %s\n"
        "  indicators_null: %s\n"
        "  pattern_indicators_present: %s\n"
        "  duration_sec: %.3f",
        ",".join(stats.dates),
        stats.tickers_processed,
        stats.snapshots_written,
        stats.indicators_computed_total,
        stats.indicators_null_total,
        stats.pattern_indicators_present,
        stats.duration_seconds,
        extra={"a2_summary": True, "a2_stats": stats.to_log_extra()},
    )


def get_indicator_surface_for_tests():
    """
    Test helper to allow assertions against the authoritative surface without
    importing `docs/` as a Python package.
    """
    return _indicator_surface()
