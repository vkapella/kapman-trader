from __future__ import annotations

import importlib.util
import json
import logging
import math
import multiprocessing as mp
import os
import time
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import Json


DEFAULT_MODEL_VERSION = "MVP-v1"
DEFAULT_TICKER_CHUNK_SIZE = 500

RVOL_WINDOW_DAYS = 20
VSI_WINDOW_DAYS = 20
HV_WINDOW_DAYS = 20
HV_ANNUALIZATION_DAYS = 252

logger = logging.getLogger(__name__)
_WARNED_INDICATOR_ERRORS: set[str] = set()
_WARNED_PATTERN_ERRORS: bool = False
_WARNED_PATTERN_BACKEND_UNAVAILABLE: bool = False


@dataclass(frozen=True)
class A2ChunkWorkItem:
    snapshot_date: date
    snapshot_time: datetime
    chunk_index: int
    total_chunks_for_date: int
    ticker_ids: list[str]


@dataclass(frozen=True)
class A2WorkerArgs:
    worker_id: int
    db_url: str
    work_items: list[A2ChunkWorkItem]
    model_version: str
    enable_pattern_indicators: bool


@dataclass(frozen=True)
class A2WorkerResult:
    worker_id: int
    pid: int
    stats: A2BatchStats


def partition_chunks_for_workers(
    chunks: Sequence[Any], *, workers: int
) -> list[list[Any]]:
    """
    Deterministically assign chunks to workers in round-robin order.

    - Stable: same input order => same assignment for a given `workers`
    - Load-balanced: avoids large contiguous blocks per worker
    """
    if workers <= 0:
        raise ValueError("workers must be > 0")
    assignments: list[list[Any]] = [[] for _ in range(workers)]
    for idx, chunk in enumerate(chunks):
        assignments[idx % workers].append(chunk)
    return assignments


def _configure_worker_logging() -> logging.Logger:
    """
    Child processes spawned via 'spawn' do not inherit the parent logging config.
    Keep worker logging minimal (warnings/errors) to stderr.
    """
    worker_log = logging.getLogger("kapman.a2.worker")
    if worker_log.handlers:
        return worker_log
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    handler.setLevel(logging.WARNING)
    worker_log.addHandler(handler)
    worker_log.setLevel(logging.WARNING)
    worker_log.propagate = False
    return worker_log


def _run_a2_worker(args: A2WorkerArgs) -> A2WorkerResult:
    worker_log = _configure_worker_logging()
    t0 = time.monotonic()
    stats = A2BatchStats.empty()
    stats.dates = sorted({w.snapshot_date.isoformat() for w in args.work_items})
    stats.pattern_indicators_enabled = bool(args.enable_pattern_indicators)
    if args.enable_pattern_indicators:
        stats.pattern_backend_available = bool(getattr(_indicator_surface(), "talib", None) is not None)
    else:
        stats.pattern_backend_available = False

    with psycopg2.connect(args.db_url) as conn:
        for work in args.work_items:
            stats.total_chunks += 1
            chunk_start = time.monotonic()
            technical_by_ticker, price_by_ticker = _compute_chunk_payloads(
                conn,
                ticker_ids=work.ticker_ids,
                snapshot_date=work.snapshot_date,
                enable_pattern_indicators=args.enable_pattern_indicators,
                stats=stats,
                log=worker_log,
            )

            for ticker_id in work.ticker_ids:
                technical = technical_by_ticker.get(str(ticker_id))
                if technical is None:
                    technical = compute_technical_indicators_json(
                        pd.DataFrame(columns=["open", "high", "low", "close", "volume"]),
                        enable_pattern_indicators=args.enable_pattern_indicators,
                        stats=None,
                        log=worker_log,
                    )
                price_metrics = price_by_ticker.get(str(ticker_id)) or {"rvol": None, "vsi": None, "hv": None}

                _upsert_daily_snapshot(
                    conn,
                    snapshot_time=work.snapshot_time,
                    ticker_id=ticker_id,
                    technical_indicators_json=technical,
                    price_metrics_json=price_metrics,
                    model_version=args.model_version,
                    created_at=datetime.now(timezone.utc),
                )
                stats.snapshots_written += 1
                stats.tickers_processed += 1

            conn.commit()
            chunk_elapsed_sec = time.monotonic() - chunk_start
            stats.chunk_times_sec.append(chunk_elapsed_sec)
            stats.chunk_time_sec_total += chunk_elapsed_sec

    stats.duration_seconds = time.monotonic() - t0
    return A2WorkerResult(worker_id=args.worker_id, pid=os.getpid(), stats=stats)


@dataclass
class A2BatchStats:
    dates: list[str]
    tickers_processed: int
    snapshots_written: int
    total_chunks: int
    chunk_times_sec: list[float]
    chunk_time_sec_total: float
    indicators_computed_total: int
    indicators_null_total: int
    pattern_indicators_enabled: bool
    pattern_backend_available: bool
    pattern_indicators_attempted: int
    pattern_indicators_present: int
    technical_indicator_time_sec: float
    pattern_indicator_time_sec: float
    duration_seconds: float

    @classmethod
    def empty(cls) -> "A2BatchStats":
        return cls(
            dates=[],
            tickers_processed=0,
            snapshots_written=0,
            total_chunks=0,
            chunk_times_sec=[],
            chunk_time_sec_total=0.0,
            indicators_computed_total=0,
            indicators_null_total=0,
            pattern_indicators_enabled=False,
            pattern_backend_available=False,
            pattern_indicators_attempted=0,
            pattern_indicators_present=0,
            technical_indicator_time_sec=0.0,
            pattern_indicator_time_sec=0.0,
            duration_seconds=0.0,
        )

    def to_log_extra(self) -> Dict[str, Any]:
        return {
            "dates": self.dates,
            "tickers_processed": self.tickers_processed,
            "snapshots_written": self.snapshots_written,
            "total_chunks": self.total_chunks,
            "chunk_times_sec": self.chunk_times_sec,
            "chunk_time_sec_total": self.chunk_time_sec_total,
            "indicators_computed_total": self.indicators_computed_total,
            "indicators_null_total": self.indicators_null_total,
            "pattern_indicators_enabled": self.pattern_indicators_enabled,
            "pattern_backend_available": self.pattern_backend_available,
            "pattern_indicators_attempted": self.pattern_indicators_attempted,
            "pattern_indicators_present": self.pattern_indicators_present,
            "technical_indicator_time_sec": self.technical_indicator_time_sec,
            "pattern_indicator_time_sec": self.pattern_indicator_time_sec,
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


def partition_ticker_ids(ticker_ids: Sequence[str], *, chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    return [list(ticker_ids[i : i + chunk_size]) for i in range(0, len(ticker_ids), chunk_size)]


def compute_eta_seconds(
    *,
    cumulative_chunk_time_sec: float,
    tickers_processed_so_far: int,
    remaining_tickers: int,
) -> tuple[float, float]:
    if tickers_processed_so_far <= 0 or cumulative_chunk_time_sec <= 0:
        return (0.0, 0.0)
    avg = cumulative_chunk_time_sec / float(tickers_processed_so_far)
    return (avg, avg * float(max(0, remaining_tickers)))


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


def _compute_chunk_price_metrics_latest(
    ohlcv_long: pd.DataFrame, *, ticker_ids: Sequence[str]
) -> Dict[str, Dict[str, Optional[float]]]:
    """
    Compute A2 price metrics for a chunk (latest value only per ticker).

    Uses the exact single-ticker implementation to preserve byte-for-byte outputs.
    """
    out: Dict[str, Dict[str, Optional[float]]] = {
        str(tid): {"rvol": None, "vsi": None, "hv": None} for tid in ticker_ids
    }
    if not ticker_ids or ohlcv_long.empty:
        return out

    for tid, group_df in ohlcv_long.groupby("ticker_id", sort=False):
        ticker_id = str(tid)
        if ticker_id not in out:
            continue
        ticker_ohlcv = group_df[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
        out[ticker_id] = compute_price_metrics_json(ticker_ohlcv)
    return out


def _compute_chunk_technical_indicators_latest(
    ohlcv_long: pd.DataFrame,
    *,
    ticker_ids: Sequence[str],
    enable_pattern_indicators: bool,
    stats: Optional[A2BatchStats],
    log: logging.Logger,
) -> Dict[str, Dict[str, Any]]:
    """
    Vectorized computation of A2 technical indicators for a chunk (latest value only per ticker).

    Implementation uses wide DataFrames (row_index × tickers) to preserve per-ticker
    numerical behavior while avoiding the per-ticker indicator loop.
    """
    surface = _indicator_surface()
    ticker_ids_s = [str(t) for t in ticker_ids]
    out: Dict[str, Dict[str, Any]] = {}
    if not ticker_ids_s:
        return out

    for tid in ticker_ids_s:
        technical: Dict[str, Any] = {cat: {} for cat in surface.TECHNICAL_TOP_LEVEL_CATEGORIES}
        for category, indicators in surface.INDICATOR_REGISTRY.items():
            technical[category] = {
                name: {k: None for k in info.get("outputs", [])} for name, info in indicators.items()
            }
        technical["pattern_recognition"] = {k: None for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS}
        out[tid] = technical

    if ohlcv_long.empty:
        if stats is not None:
            for _ in ticker_ids_s:
                for category, indicators in surface.INDICATOR_REGISTRY.items():
                    for info in indicators.values():
                        for _ in info.get("outputs", []):
                            stats.indicators_computed_total += 1
                            stats.indicators_null_total += 1
                if enable_pattern_indicators and getattr(surface, "talib", None) is not None:
                    stats.pattern_indicators_attempted += len(surface.PATTERN_RECOGNITION_OUTPUT_KEYS)
        return out

    last_row = (
        ohlcv_long.groupby("ticker_id", sort=False)["row_index"].max().astype("int64")
    )
    last_rows = np.array([int(last_row.get(t, -1)) for t in ticker_ids_s], dtype="int64")
    valid = last_rows >= 0
    col_idx = np.arange(len(ticker_ids_s), dtype="int64")

    wide = (
        ohlcv_long.set_index(["row_index", "ticker_id"])[
            ["open", "high", "low", "close", "volume"]
        ]
        .unstack("ticker_id")
    )
    wide = wide.reindex(
        columns=pd.MultiIndex.from_product(
            [["open", "high", "low", "close", "volume"], ticker_ids_s]
        )
    )
    open_df = wide["open"]
    high_df = wide["high"]
    low_df = wide["low"]
    close_df = wide["close"]
    volume_df = wide["volume"]

    def _latest(df: pd.DataFrame) -> np.ndarray:
        arr = df.to_numpy()
        values = np.full(len(ticker_ids_s), np.nan, dtype="float64")
        if valid.any():
            values[valid] = arr[last_rows[valid], col_idx[valid]]
        return values

    def _assign(category: str, name: str, outputs: Dict[str, pd.DataFrame]) -> None:
        for output_key, df in outputs.items():
            vals = _latest(df)
            for tid, v in zip(ticker_ids_s, vals):
                out[tid][category][name][output_key] = _as_scalar_or_none(v)

    def _warn_once(category: str, name: str) -> None:
        warn_key = f"{category}.{name}"
        if warn_key in _WARNED_INDICATOR_ERRORS:
            return
        _WARNED_INDICATOR_ERRORS.add(warn_key)
        log.warning("[A2] indicator failed category=%s name=%s", category, name)

    def _nanmax3(a: pd.DataFrame, b: pd.DataFrame, c: pd.DataFrame) -> pd.DataFrame:
        stacked = np.stack([a.to_numpy(), b.to_numpy(), c.to_numpy()], axis=0)
        return pd.DataFrame(np.nanmax(stacked, axis=0), index=a.index, columns=a.columns)

    technical_t0 = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with np.errstate(divide="ignore", invalid="ignore"):
            # --- momentum ---
            try:
                median_price = 0.5 * (high_df + low_df)
                ao = median_price.rolling(5, min_periods=5).mean() - median_price.rolling(
                    34, min_periods=34
                ).mean()
                _assign("momentum", "awesome_oscillator", {"awesome_oscillator": ao})
            except Exception:
                _warn_once("momentum", "awesome_oscillator")

            try:
                emafast = close_df.ewm(span=12, min_periods=12, adjust=False).mean()
                emaslow = close_df.ewm(span=26, min_periods=26, adjust=False).mean()
                ppo = ((emafast - emaslow) / emaslow) * 100
                ppo_signal = ppo.ewm(span=9, min_periods=9, adjust=False).mean()
                ppo_hist = ppo - ppo_signal
                _assign(
                    "momentum",
                    "ppo",
                    {"ppo": ppo, "ppo_signal": ppo_signal, "ppo_hist": ppo_hist},
                )
            except Exception:
                _warn_once("momentum", "ppo")

            try:
                emafast = volume_df.ewm(span=12, min_periods=12, adjust=False).mean()
                emaslow = volume_df.ewm(span=26, min_periods=26, adjust=False).mean()
                pvo = ((emafast - emaslow) / emaslow) * 100
                pvo_signal = pvo.ewm(span=9, min_periods=9, adjust=False).mean()
                pvo_hist = pvo - pvo_signal
                _assign(
                    "momentum",
                    "pvo",
                    {"pvo": pvo, "pvo_signal": pvo_signal, "pvo_hist": pvo_hist},
                )
            except Exception:
                _warn_once("momentum", "pvo")

            try:
                roc = ((close_df - close_df.shift(12)) / close_df.shift(12)) * 100
                _assign("momentum", "roc", {"roc": roc})
            except Exception:
                _warn_once("momentum", "roc")

            rsi = None
            try:
                diff = close_df.diff(1)
                up = diff.where(diff > 0, 0.0)
                down = -diff.where(diff < 0, 0.0)
                emaup = up.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
                emadn = down.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
                rs = emaup / emadn
                rsi = pd.DataFrame(
                    np.where(emadn == 0, 100, 100 - (100 / (1 + rs))),
                    index=close_df.index,
                    columns=close_df.columns,
                )
                _assign("momentum", "rsi", {"rsi": rsi})
            except Exception:
                _warn_once("momentum", "rsi")

            try:
                if rsi is None:
                    raise RuntimeError("rsi unavailable")
                lowest_rsi = rsi.rolling(14).min()
                highest_rsi = rsi.rolling(14).max()
                stochrsi = (rsi - lowest_rsi) / (highest_rsi - lowest_rsi)
                stochrsi_k = stochrsi.rolling(3).mean()
                stochrsi_d = stochrsi_k.rolling(3).mean()
                _assign(
                    "momentum",
                    "stochrsi",
                    {
                        "stochrsi": stochrsi,
                        "stochrsi_k": stochrsi_k,
                        "stochrsi_d": stochrsi_d,
                    },
                )
            except Exception:
                _warn_once("momentum", "stochrsi")

            try:
                smin = low_df.rolling(14, min_periods=14).min()
                smax = high_df.rolling(14, min_periods=14).max()
                stoch_k = 100 * (close_df - smin) / (smax - smin)
                stoch_d = stoch_k.rolling(3, min_periods=3).mean()
                _assign("momentum", "stoch", {"stoch": stoch_k, "stoch_signal": stoch_d})
            except Exception:
                _warn_once("momentum", "stoch")

            try:
                diff_close = close_df - close_df.shift(1)
                smoothed = (
                    diff_close.ewm(span=25, min_periods=25, adjust=False)
                    .mean()
                    .ewm(span=13, min_periods=13, adjust=False)
                    .mean()
                )
                smoothed_abs = (
                    diff_close.abs()
                    .ewm(span=25, min_periods=25, adjust=False)
                    .mean()
                    .ewm(span=13, min_periods=13, adjust=False)
                    .mean()
                )
                tsi = (smoothed / smoothed_abs) * 100
                _assign("momentum", "tsi", {"tsi": tsi})
            except Exception:
                _warn_once("momentum", "tsi")

            try:
                close_shift = close_df.shift(1)
                tr1 = high_df - low_df
                tr2 = (high_df - close_shift).abs()
                tr3 = (low_df - close_shift).abs()
                true_range = _nanmax3(tr1, tr2, tr3)

                min_low_or_close = pd.DataFrame(
                    np.minimum(low_df.to_numpy(), close_shift.to_numpy()),
                    index=close_df.index,
                    columns=close_df.columns,
                )
                buying_pressure = close_df - min_low_or_close

                avg_s = buying_pressure.rolling(7, min_periods=7).sum() / true_range.rolling(
                    7, min_periods=7
                ).sum()
                avg_m = buying_pressure.rolling(14, min_periods=14).sum() / true_range.rolling(
                    14, min_periods=14
                ).sum()
                avg_l = buying_pressure.rolling(28, min_periods=28).sum() / true_range.rolling(
                    28, min_periods=28
                ).sum()
                uo = 100.0 * ((4.0 * avg_s) + (2.0 * avg_m) + (1.0 * avg_l)) / (4.0 + 2.0 + 1.0)
                _assign("momentum", "ultimate_oscillator", {"ultimate_oscillator": uo})
            except Exception:
                _warn_once("momentum", "ultimate_oscillator")

            try:
                highest_high = high_df.rolling(14, min_periods=14).max()
                lowest_low = low_df.rolling(14, min_periods=14).min()
                wr = -100 * (highest_high - close_df) / (highest_high - lowest_low)
                _assign("momentum", "williams_r", {"williams_r": wr})
            except Exception:
                _warn_once("momentum", "williams_r")

            # --- volatility ---
            try:
                mavg = close_df.rolling(20, min_periods=20).mean()
                mstd = close_df.rolling(20, min_periods=20).std(ddof=0)
                hband = mavg + (2 * mstd)
                lband = mavg - (2 * mstd)
                wband = ((hband - lband) / mavg) * 100
                denom = (hband - lband).where(hband != lband, np.nan)
                pband = (close_df - lband) / denom
                hband_ind = pd.DataFrame(
                    np.where(close_df > hband, 1.0, 0.0),
                    index=close_df.index,
                    columns=close_df.columns,
                )
                lband_ind = pd.DataFrame(
                    np.where(close_df < lband, 1.0, 0.0),
                    index=close_df.index,
                    columns=close_df.columns,
                )
                _assign(
                    "volatility",
                    "bbands",
                    {
                        "bollinger_mavg": mavg,
                        "bollinger_hband": hband,
                        "bollinger_lband": lband,
                        "bollinger_wband": wband,
                        "bollinger_pband": pband,
                        "bollinger_hband_indicator": hband_ind,
                        "bollinger_lband_indicator": lband_ind,
                    },
                )
            except Exception:
                _warn_once("volatility", "bbands")

            try:
                hband = high_df.rolling(20, min_periods=20).max()
                lband = low_df.rolling(20, min_periods=20).min()
                mband = ((hband - lband) / 2.0) + lband
                mavg = close_df.rolling(20, min_periods=20).mean()
                wband = ((hband - lband) / mavg) * 100
                pband = (close_df - lband) / (hband - lband)
                _assign(
                    "volatility",
                    "donchian",
                    {
                        "donchian_channel_hband": hband,
                        "donchian_channel_lband": lband,
                        "donchian_channel_mband": mband,
                        "donchian_channel_pband": pband,
                        "donchian_channel_wband": wband,
                    },
                )
            except Exception:
                _warn_once("volatility", "donchian")

            try:
                tp_m = ((high_df + low_df + close_df) / 3.0).rolling(20, min_periods=20).mean()
                tp_high = (((4 * high_df) - (2 * low_df) + close_df) / 3.0).rolling(20, min_periods=0).mean()
                tp_low = (((-2 * high_df) + (4 * low_df) + close_df) / 3.0).rolling(20, min_periods=0).mean()
                wband = ((tp_high - tp_low) / tp_m) * 100
                pband = (close_df - tp_low) / (tp_high - tp_low)
                hband_ind = pd.DataFrame(
                    np.where(close_df > tp_high, 1.0, 0.0),
                    index=close_df.index,
                    columns=close_df.columns,
                )
                lband_ind = pd.DataFrame(
                    np.where(close_df < tp_low, 1.0, 0.0),
                    index=close_df.index,
                    columns=close_df.columns,
                )
                _assign(
                    "volatility",
                    "keltner",
                    {
                        "keltner_channel_hband": tp_high,
                        "keltner_channel_lband": tp_low,
                        "keltner_channel_mband": tp_m,
                        "keltner_channel_pband": pband,
                        "keltner_channel_wband": wband,
                        "keltner_channel_hband_indicator": hband_ind,
                        "keltner_channel_lband_indicator": lband_ind,
                    },
                )
            except Exception:
                _warn_once("volatility", "keltner")

            try:
                ui_max = close_df.rolling(14, min_periods=1).max()
                r_i = 100 * (close_df - ui_max) / ui_max

                def _ui_func(x: np.ndarray) -> float:
                    return float(np.sqrt((x ** 2 / 14).sum()))

                ulcer = r_i.rolling(14).apply(_ui_func, raw=True)
                _assign("volatility", "ulcer_index", {"ulcer_index": ulcer})
            except Exception:
                _warn_once("volatility", "ulcer_index")

            # --- trend ---
            # Aroon remains NULL-only (surface signature mismatch); preserve behavior.

            try:
                tp = (high_df + low_df + close_df) / 3.0
                tp_ma = tp.rolling(20, min_periods=20).mean()

                def _mad(x: np.ndarray) -> float:
                    return float(np.mean(np.abs(x - np.mean(x))))

                tp_mad = tp.rolling(20, min_periods=20).apply(_mad, raw=True)
                cci = (tp - tp_ma) / (0.015 * tp_mad)
                _assign("trend", "cci", {"cci": cci})
            except Exception:
                _warn_once("trend", "cci")

            try:
                shifted = close_df.shift(int((0.5 * 20) + 1)).fillna(close_df.mean())
                sma = close_df.rolling(20, min_periods=20).mean()
                dpo = shifted - sma
                _assign("trend", "dpo", {"dpo": dpo})
            except Exception:
                _warn_once("trend", "dpo")

            try:
                ema14 = close_df.ewm(span=14, min_periods=14, adjust=False).mean()
                _assign("trend", "ema", {"ema_indicator": ema14})
            except Exception:
                _warn_once("trend", "ema")

            try:
                conv = 0.5 * (
                    high_df.rolling(9, min_periods=9).max()
                    + low_df.rolling(9, min_periods=9).min()
                )
                base = 0.5 * (
                    high_df.rolling(26, min_periods=26).max()
                    + low_df.rolling(26, min_periods=26).min()
                )
                spana = 0.5 * (conv + base)
                spanb = 0.5 * (
                    high_df.rolling(52, min_periods=0).max()
                    + low_df.rolling(52, min_periods=0).min()
                )
                _assign(
                    "trend",
                    "ichimoku",
                    {
                        "ichimoku_conversion_line": conv,
                        "ichimoku_base_line": base,
                        "ichimoku_a": spana,
                        "ichimoku_b": spanb,
                    },
                )
            except Exception:
                _warn_once("trend", "ichimoku")

            try:
                mean_close = close_df.mean()

                def _rocma(r: int, w: int) -> pd.DataFrame:
                    shifted = close_df.shift(r).fillna(mean_close)
                    roc = (close_df - shifted) / shifted
                    return roc.rolling(w, min_periods=w).mean()

                rocma1 = _rocma(10, 10)
                rocma2 = _rocma(15, 10)
                rocma3 = _rocma(20, 10)
                rocma4 = _rocma(30, 15)
                kst = 100 * (rocma1 + 2 * rocma2 + 3 * rocma3 + 4 * rocma4)
                kst_sig = kst.rolling(9, min_periods=0).mean()
                kst_diff = kst - kst_sig
                _assign("trend", "kst", {"kst": kst, "kst_sig": kst_sig, "kst_diff": kst_diff})
            except Exception:
                _warn_once("trend", "kst")

            try:
                emafast = close_df.ewm(span=12, min_periods=12, adjust=False).mean()
                emaslow = close_df.ewm(span=26, min_periods=26, adjust=False).mean()
                macd = emafast - emaslow
                macd_signal = macd.ewm(span=9, min_periods=9, adjust=False).mean()
                macd_diff = macd - macd_signal
                _assign("trend", "macd", {"macd": macd, "macd_signal": macd_signal, "macd_diff": macd_diff})
            except Exception:
                _warn_once("trend", "macd")

            try:
                amplitude = high_df - low_df
                ema1 = amplitude.ewm(span=9, min_periods=9, adjust=False).mean()
                ema2 = ema1.ewm(span=9, min_periods=9, adjust=False).mean()
                mass = ema1 / ema2
                mass_index = mass.rolling(25, min_periods=25).sum()
                _assign("trend", "mass_index", {"mass_index": mass_index})
            except Exception:
                _warn_once("trend", "mass_index")

            try:
                for w in (14, 20, 50, 200):
                    sma_w = close_df.rolling(w, min_periods=w).mean()
                    _assign("trend", "sma", {f"sma_{w}": sma_w})
            except Exception:
                _warn_once("trend", "sma")

            try:
                emafast = close_df.ewm(span=23, min_periods=23, adjust=False).mean()
                emaslow = close_df.ewm(span=50, min_periods=50, adjust=False).mean()
                macd = emafast - emaslow
                macd_min = macd.rolling(window=10).min()
                macd_max = macd.rolling(window=10).max()
                stoch_k = 100 * (macd - macd_min) / (macd_max - macd_min)
                stoch_d = stoch_k.ewm(span=3, min_periods=3, adjust=False).mean()
                stoch_d_min = stoch_d.rolling(window=10).min()
                stoch_d_max = stoch_d.rolling(window=10).max()
                stoch_kd = 100 * (stoch_d - stoch_d_min) / (stoch_d_max - stoch_d_min)
                stc = stoch_kd.ewm(span=3, min_periods=3, adjust=False).mean()
                _assign("trend", "stc", {"stc": stc})
            except Exception:
                _warn_once("trend", "stc")

            try:
                ema1 = close_df.ewm(span=15, min_periods=15, adjust=False).mean()
                ema2 = ema1.ewm(span=15, min_periods=15, adjust=False).mean()
                ema3 = ema2.ewm(span=15, min_periods=15, adjust=False).mean()
                ema3_shift = ema3.shift(1).fillna(ema3.mean())
                trix = ((ema3 - ema3_shift) / ema3_shift) * 100
                _assign("trend", "trix", {"trix": trix})
            except Exception:
                _warn_once("trend", "trix")

            try:
                close_shift = close_df.shift(1).fillna(close_df.mean())
                tr1 = high_df - low_df
                tr2 = (high_df - close_shift).abs()
                tr3 = (low_df - close_shift).abs()
                true_range = _nanmax3(tr1, tr2, tr3)
                trn = true_range.rolling(14, min_periods=14).sum()
                vmp = (high_df - low_df.shift(1)).abs()
                vmm = (low_df - high_df.shift(1)).abs()
                vip = vmp.rolling(14, min_periods=14).sum() / trn
                vin = vmm.rolling(14, min_periods=14).sum() / trn
                vid = vip - vin
                _assign(
                    "trend",
                    "vortex",
                    {
                        "vortex_indicator_pos": vip,
                        "vortex_indicator_neg": vin,
                        "vortex_indicator_diff": vid,
                    },
                )
            except Exception:
                _warn_once("trend", "vortex")

            try:
                window = 9
                weights = np.array(
                    [i * 2 / (window * (window + 1)) for i in range(1, window + 1)],
                    dtype="float64",
                )

                def _wma_fn(x: np.ndarray) -> float:
                    return float((weights * x).sum())

                wma = close_df.rolling(window).apply(_wma_fn, raw=True)
                _assign("trend", "wma", {"wma": wma})
            except Exception:
                _warn_once("trend", "wma")

            # --- volume ---
            try:
                clv = ((close_df - low_df) - (high_df - close_df)) / (high_df - low_df)
                clv = clv.fillna(0.0)
                adi = (clv * volume_df).cumsum()
                _assign("volume", "adi", {"acc_dist_index": adi})
            except Exception:
                _warn_once("volume", "adi")

            try:
                clv = ((close_df - low_df) - (high_df - close_df)) / (high_df - low_df)
                mfv = clv.fillna(0.0) * volume_df
                cmf = mfv.rolling(20, min_periods=20).sum() / volume_df.rolling(20, min_periods=20).sum()
                _assign("volume", "cmf", {"chaikin_money_flow": cmf})
            except Exception:
                _warn_once("volume", "cmf")

            try:
                emv = ((high_df.diff(1) + low_df.diff(1)) * (high_df - low_df) / (2 * volume_df)) * 100000000
                sma_emv = emv.rolling(14, min_periods=14).mean()
                _assign("volume", "eom", {"ease_of_movement": emv, "sma_ease_of_movement": sma_emv})
            except Exception:
                _warn_once("volume", "eom")

            try:
                fi_series = (close_df - close_df.shift(1)) * volume_df
                fi = fi_series.ewm(span=13, min_periods=13, adjust=False).mean()
                _assign("volume", "fi", {"force_index": fi})
            except Exception:
                _warn_once("volume", "fi")

            try:
                tp = (high_df + low_df + close_df) / 3.0
                tp_shift = tp.shift(1)
                up_down = pd.DataFrame(
                    np.where(tp > tp_shift, 1, np.where(tp < tp_shift, -1, 0)),
                    index=tp.index,
                    columns=tp.columns,
                )
                mfr = tp * volume_df * up_down

                def _pos_sum(x: np.ndarray) -> float:
                    return float(np.sum(np.where(x >= 0.0, x, 0.0)))

                def _neg_sum(x: np.ndarray) -> float:
                    return float(np.sum(np.where(x < 0.0, x, 0.0)))

                pos_mf = mfr.rolling(14, min_periods=14).apply(_pos_sum, raw=True)
                neg_mf = abs(mfr.rolling(14, min_periods=14).apply(_neg_sum, raw=True))
                mfi_ratio = pos_mf / neg_mf
                mfi = 100 - (100 / (1 + mfi_ratio))
                _assign("volume", "mfi", {"money_flow_index": mfi})
            except Exception:
                _warn_once("volume", "mfi")

            try:
                obv = pd.DataFrame(
                    np.where(close_df < close_df.shift(1), -volume_df, volume_df),
                    index=close_df.index,
                    columns=close_df.columns,
                ).cumsum()
                _assign("volume", "obv", {"on_balance_volume": obv})
            except Exception:
                _warn_once("volume", "obv")

            try:
                close_shift = close_df.shift(1).fillna(close_df.mean())
                vpt = volume_df * ((close_df - close_shift) / close_shift)
                vpt_total = vpt.shift(1).fillna(vpt.mean()) + vpt
                _assign("volume", "vpt", {"volume_price_trend": vpt_total})
            except Exception:
                _warn_once("volume", "vpt")

            try:
                tp = (high_df + low_df + close_df) / 3.0
                total_pv = (tp * volume_df).rolling(14, min_periods=14).sum()
                total_vol = volume_df.rolling(14, min_periods=14).sum()
                vwap = total_pv / total_vol
                _assign("volume", "vwap", {"volume_weighted_average_price": vwap})
            except Exception:
                _warn_once("volume", "vwap")

            # --- others ---
            try:
                first_close = close_df.iloc[0]
                cr = ((close_df / first_close) - 1) * 100
                _assign("others", "cr", {"cumulative_return": cr})
            except Exception:
                _warn_once("others", "cr")

            try:
                dlr = np.log(close_df).diff() * 100
                _assign("others", "dlr", {"daily_log_return": dlr})
            except Exception:
                _warn_once("others", "dlr")

            try:
                prev_close = close_df.shift(1).fillna(close_df.mean())
                dr = ((close_df / prev_close) - 1) * 100
                _assign("others", "dr", {"daily_return": dr})
            except Exception:
                _warn_once("others", "dr")

    # Fallback (exact per-ticker) for iterative indicators:
    fallback = {
        ("momentum", "kama"),
        ("volatility", "atr"),
        ("trend", "adx"),
        ("trend", "psar"),
        ("volume", "nvi"),
    }

    for tid, group_df in ohlcv_long.groupby("ticker_id", sort=False):
        ticker_id = str(tid)
        if ticker_id not in out:
            continue
        ticker_ohlcv = group_df[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with np.errstate(divide="ignore", invalid="ignore"):
                for category, name in fallback:
                    try:
                        result = surface.compute_indicator_latest(ticker_ohlcv, category, name)
                        outputs = result.get("outputs", {}) if isinstance(result, dict) else {}
                        for k in out[ticker_id][category][name].keys():
                            out[ticker_id][category][name][k] = _as_scalar_or_none(outputs.get(k))
                    except Exception:
                        _warn_once(category, name)

    if stats is not None:
        stats.technical_indicator_time_sec += time.perf_counter() - technical_t0

    # Pattern recognition (optional)
    pattern_t0 = time.perf_counter()
    if enable_pattern_indicators and getattr(surface, "talib", None) is not None:
        for tid, group_df in ohlcv_long.groupby("ticker_id", sort=False):
            ticker_id = str(tid)
            if ticker_id not in out:
                continue
            ticker_ohlcv = group_df[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        out[ticker_id]["pattern_recognition"] = surface.compute_pattern_recognition_latest(
                            ticker_ohlcv
                        )
            except Exception:
                global _WARNED_PATTERN_ERRORS
                if not _WARNED_PATTERN_ERRORS:
                    _WARNED_PATTERN_ERRORS = True
                    log.warning("[A2] pattern_recognition failed")
                out[ticker_id]["pattern_recognition"] = {k: None for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS}
    else:
        if enable_pattern_indicators and getattr(surface, "talib", None) is None:
            global _WARNED_PATTERN_BACKEND_UNAVAILABLE
            if not _WARNED_PATTERN_BACKEND_UNAVAILABLE:
                _WARNED_PATTERN_BACKEND_UNAVAILABLE = True
                log.info("[A2] pattern backend unavailable; emitting NULL patterns")
        for tid in ticker_ids_s:
            out[tid]["pattern_recognition"] = {k: None for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS}

    if stats is not None:
        if enable_pattern_indicators:
            stats.pattern_indicator_time_sec += time.perf_counter() - pattern_t0
        for tid in ticker_ids_s:
            patterns = out[tid].get("pattern_recognition") or {}
            if enable_pattern_indicators and getattr(surface, "talib", None) is not None:
                stats.pattern_indicators_attempted += len(patterns)
            for v in patterns.values():
                if v is not None:
                    stats.pattern_indicators_present += 1

        for tid in ticker_ids_s:
            tech = out[tid]
            for category, indicators in surface.INDICATOR_REGISTRY.items():
                for name, info in indicators.items():
                    for output_key in info.get("outputs", []):
                        stats.indicators_computed_total += 1
                        if tech[category][name].get(output_key) is None:
                            stats.indicators_null_total += 1

    return out


def _compute_chunk_price_metrics_latest_groupby(
    ohlcv_long: pd.DataFrame, *, ticker_ids: Sequence[str]
) -> Dict[str, Dict[str, Optional[float]]]:
    """
    Vectorized computation of A2 price metrics for a chunk (latest value only per ticker).
    """
    out: Dict[str, Dict[str, Optional[float]]] = {
        str(tid): {"rvol": None, "vsi": None, "hv": None} for tid in ticker_ids
    }
    if ohlcv_long.empty or not ticker_ids:
        return out

    key = ohlcv_long["ticker_id"]
    g_close = ohlcv_long.groupby("ticker_id", sort=False)["close"]
    g_volume = ohlcv_long.groupby("ticker_id", sort=False)["volume"]

    last_pos = ohlcv_long.groupby("ticker_id", sort=False)["row_index"].idxmax()
    last_pos_values = last_pos.to_numpy()
    last_tickers_present = last_pos.index.to_list()

    try:
        volume_prior = g_volume.shift(1)
        mean_prior = (
            volume_prior.groupby(key, sort=False)
            .rolling(RVOL_WINDOW_DAYS, min_periods=RVOL_WINDOW_DAYS)
            .mean()
            .reset_index(level=0, drop=True)
        )
        std_prior = (
            volume_prior.groupby(key, sort=False)
            .rolling(RVOL_WINDOW_DAYS, min_periods=RVOL_WINDOW_DAYS)
            .std(ddof=0)
            .reset_index(level=0, drop=True)
        )

        rvol_series = (ohlcv_long["volume"] / mean_prior).where(
            mean_prior.notna() & np.isfinite(mean_prior) & (mean_prior > 0)
        )
        vsi_series = ((ohlcv_long["volume"] - mean_prior) / std_prior).where(
            rvol_series.notna() & std_prior.notna() & np.isfinite(std_prior) & (std_prior > 0)
        )

        rvol_last = rvol_series.to_numpy()[last_pos_values]
        vsi_last = vsi_series.to_numpy()[last_pos_values]
        for tid, rvol_v, vsi_v in zip(last_tickers_present, rvol_last, vsi_last):
            out[str(tid)]["rvol"] = _as_scalar_or_none(rvol_v)
            out[str(tid)]["vsi"] = _as_scalar_or_none(vsi_v)
    except Exception:
        logger.exception("[A2] price metrics rvol/vsi failed; emitting NULL")

    try:
        close_shift = g_close.shift(1)
        log_returns = np.log(ohlcv_long["close"] / close_shift)
        hv_std = (
            log_returns.groupby(key, sort=False)
            .rolling(HV_WINDOW_DAYS, min_periods=HV_WINDOW_DAYS)
            .std(ddof=0)
            .reset_index(level=0, drop=True)
        )
        hv_series = hv_std * math.sqrt(HV_ANNUALIZATION_DAYS)
        hv_last = hv_series.to_numpy()[last_pos_values]
        for tid, hv_v in zip(last_tickers_present, hv_last):
            out[str(tid)]["hv"] = _as_scalar_or_none(hv_v)
    except Exception:
        logger.exception("[A2] price metrics hv failed; emitting NULL")

    return out


def _compute_chunk_technical_indicators_latest_groupby(
    ohlcv_long: pd.DataFrame,
    *,
    ticker_ids: Sequence[str],
    enable_pattern_indicators: bool,
    stats: Optional[A2BatchStats],
    log: logging.Logger,
) -> Dict[str, Dict[str, Any]]:
    """
    Vectorized computation of A2 technical indicators for a chunk (latest value only per ticker).

    Preserves A2 invariants:
    - deterministic/idempotent
    - emits all keys with None on failure
    - does not change indicator surface contract
    """
    surface = _indicator_surface()
    out: Dict[str, Dict[str, Any]] = {}
    if not ticker_ids:
        return out

    for tid in ticker_ids:
        technical: Dict[str, Any] = {cat: {} for cat in surface.TECHNICAL_TOP_LEVEL_CATEGORIES}
        for category, indicators in surface.INDICATOR_REGISTRY.items():
            technical[category] = {
                name: {k: None for k in info.get("outputs", [])} for name, info in indicators.items()
            }
        technical["pattern_recognition"] = {k: None for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS}
        out[str(tid)] = technical

    if ohlcv_long.empty:
        if stats is not None:
            for _ in ticker_ids:
                for category, indicators in surface.INDICATOR_REGISTRY.items():
                    for info in indicators.values():
                        for _ in info.get("outputs", []):
                            stats.indicators_computed_total += 1
                            stats.indicators_null_total += 1
                if enable_pattern_indicators and getattr(surface, "talib", None) is not None:
                    stats.pattern_indicators_attempted += len(surface.PATTERN_RECOGNITION_OUTPUT_KEYS)
        return out

    key = ohlcv_long["ticker_id"]
    g_close = ohlcv_long.groupby("ticker_id", sort=False)["close"]
    g_open = ohlcv_long.groupby("ticker_id", sort=False)["open"]
    g_high = ohlcv_long.groupby("ticker_id", sort=False)["high"]
    g_low = ohlcv_long.groupby("ticker_id", sort=False)["low"]
    g_volume = ohlcv_long.groupby("ticker_id", sort=False)["volume"]

    last_pos = ohlcv_long.groupby("ticker_id", sort=False)["row_index"].idxmax()
    last_pos_values = last_pos.to_numpy()
    last_tickers_present = last_pos.index.to_list()

    def _ema(series: pd.Series, *, span: int, min_periods: int) -> pd.Series:
        return (
            series.groupby(key, sort=False)
            .ewm(span=span, min_periods=min_periods, adjust=False)
            .mean()
            .reset_index(level=0, drop=True)
        )

    def _ema_alpha(series: pd.Series, *, alpha: float, min_periods: int) -> pd.Series:
        return (
            series.groupby(key, sort=False)
            .ewm(alpha=alpha, min_periods=min_periods, adjust=False)
            .mean()
            .reset_index(level=0, drop=True)
        )

    def _rolling(series: pd.Series, *, window: int, min_periods: Optional[int] = None):
        if min_periods is None:
            return series.groupby(key, sort=False).rolling(window)
        return series.groupby(key, sort=False).rolling(window, min_periods=min_periods)

    def _shift_fill_mean(g: pd.core.groupby.generic.SeriesGroupBy, periods: int) -> pd.Series:
        shifted = g.shift(periods)
        return shifted.fillna(g.transform("mean"))

    def _assign_latest(category: str, name: str, outputs: Dict[str, pd.Series]) -> None:
        for output_key, series in outputs.items():
            vals = series.to_numpy()[last_pos_values]
            for tid, v in zip(last_tickers_present, vals):
                out[str(tid)][category][name][output_key] = _as_scalar_or_none(v)

    t0 = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with np.errstate(divide="ignore", invalid="ignore"):
            # --- momentum ---
            try:
                median_price = 0.5 * (ohlcv_long["high"] + ohlcv_long["low"])
                ao = (
                    _rolling(median_price, window=5, min_periods=5).mean().reset_index(level=0, drop=True)
                    - _rolling(median_price, window=34, min_periods=34).mean().reset_index(level=0, drop=True)
                )
                _assign_latest("momentum", "awesome_oscillator", {"awesome_oscillator": ao})
            except Exception:
                warn_key = "momentum.awesome_oscillator"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "awesome_oscillator")

            try:
                emafast = _ema(ohlcv_long["close"], span=12, min_periods=12)
                emaslow = _ema(ohlcv_long["close"], span=26, min_periods=26)
                ppo = ((emafast - emaslow) / emaslow) * 100
                ppo_signal = _ema(ppo, span=9, min_periods=9)
                ppo_hist = ppo - ppo_signal
                _assign_latest(
                    "momentum",
                    "ppo",
                    {"ppo": ppo, "ppo_signal": ppo_signal, "ppo_hist": ppo_hist},
                )
            except Exception:
                warn_key = "momentum.ppo"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "ppo")

            try:
                emafast = _ema(ohlcv_long["volume"], span=12, min_periods=12)
                emaslow = _ema(ohlcv_long["volume"], span=26, min_periods=26)
                pvo = ((emafast - emaslow) / emaslow) * 100
                pvo_signal = _ema(pvo, span=9, min_periods=9)
                pvo_hist = pvo - pvo_signal
                _assign_latest(
                    "momentum",
                    "pvo",
                    {"pvo": pvo, "pvo_signal": pvo_signal, "pvo_hist": pvo_hist},
                )
            except Exception:
                warn_key = "momentum.pvo"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "pvo")

            try:
                roc = ((ohlcv_long["close"] - g_close.shift(12)) / g_close.shift(12)) * 100
                _assign_latest("momentum", "roc", {"roc": roc})
            except Exception:
                warn_key = "momentum.roc"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "roc")

            try:
                diff = g_close.diff(1)
                up = diff.where(diff > 0, 0.0)
                down = -diff.where(diff < 0, 0.0)
                emaup = _ema_alpha(up, alpha=1 / 14, min_periods=14)
                emadn = _ema_alpha(down, alpha=1 / 14, min_periods=14)
                rs = emaup / emadn
                rsi = pd.Series(
                    np.where(emadn == 0, 100, 100 - (100 / (1 + rs))),
                    index=ohlcv_long.index,
                )
                _assign_latest("momentum", "rsi", {"rsi": rsi})
            except Exception:
                warn_key = "momentum.rsi"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "rsi")

            try:
                # StochRSI uses the RSI series above.
                lowest_rsi = _rolling(rsi, window=14).min().reset_index(level=0, drop=True)
                highest_rsi = _rolling(rsi, window=14).max().reset_index(level=0, drop=True)
                stochrsi = (rsi - lowest_rsi) / (highest_rsi - lowest_rsi)
                stochrsi_k = _rolling(stochrsi, window=3).mean().reset_index(level=0, drop=True)
                stochrsi_d = _rolling(stochrsi_k, window=3).mean().reset_index(level=0, drop=True)
                _assign_latest(
                    "momentum",
                    "stochrsi",
                    {"stochrsi": stochrsi, "stochrsi_k": stochrsi_k, "stochrsi_d": stochrsi_d},
                )
            except Exception:
                warn_key = "momentum.stochrsi"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "stochrsi")

            try:
                smin = _rolling(ohlcv_long["low"], window=14, min_periods=14).min().reset_index(level=0, drop=True)
                smax = _rolling(ohlcv_long["high"], window=14, min_periods=14).max().reset_index(level=0, drop=True)
                stoch_k = 100 * (ohlcv_long["close"] - smin) / (smax - smin)
                stoch_d = _rolling(stoch_k, window=3, min_periods=3).mean().reset_index(level=0, drop=True)
                _assign_latest("momentum", "stoch", {"stoch": stoch_k, "stoch_signal": stoch_d})
            except Exception:
                warn_key = "momentum.stoch"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "stoch")

            try:
                diff_close = ohlcv_long["close"] - g_close.shift(1)
                sm1 = diff_close.groupby(key, sort=False).ewm(span=25, min_periods=25, adjust=False).mean().reset_index(level=0, drop=True)
                sm = sm1.groupby(key, sort=False).ewm(span=13, min_periods=13, adjust=False).mean().reset_index(level=0, drop=True)
                sm_abs1 = abs(diff_close).groupby(key, sort=False).ewm(span=25, min_periods=25, adjust=False).mean().reset_index(level=0, drop=True)
                sm_abs = sm_abs1.groupby(key, sort=False).ewm(span=13, min_periods=13, adjust=False).mean().reset_index(level=0, drop=True)
                tsi = (sm / sm_abs) * 100
                _assign_latest("momentum", "tsi", {"tsi": tsi})
            except Exception:
                warn_key = "momentum.tsi"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "tsi")

            try:
                close_shift = g_close.shift(1)
                tr1 = ohlcv_long["high"] - ohlcv_long["low"]
                tr2 = (ohlcv_long["high"] - close_shift).abs()
                tr3 = (ohlcv_long["low"] - close_shift).abs()
                true_range = pd.DataFrame({"tr1": tr1, "tr2": tr2, "tr3": tr3}).max(axis=1)
                buying_pressure = ohlcv_long["close"] - pd.DataFrame(
                    {"low": ohlcv_long["low"], "close": close_shift}
                ).min(axis=1, skipna=False)

                avg_s = (
                    _rolling(buying_pressure, window=7, min_periods=7).sum().reset_index(level=0, drop=True)
                    / _rolling(true_range, window=7, min_periods=7).sum().reset_index(level=0, drop=True)
                )
                avg_m = (
                    _rolling(buying_pressure, window=14, min_periods=14).sum().reset_index(level=0, drop=True)
                    / _rolling(true_range, window=14, min_periods=14).sum().reset_index(level=0, drop=True)
                )
                avg_l = (
                    _rolling(buying_pressure, window=28, min_periods=28).sum().reset_index(level=0, drop=True)
                    / _rolling(true_range, window=28, min_periods=28).sum().reset_index(level=0, drop=True)
                )
                uo = 100.0 * ((4.0 * avg_s) + (2.0 * avg_m) + (1.0 * avg_l)) / (4.0 + 2.0 + 1.0)
                _assign_latest("momentum", "ultimate_oscillator", {"ultimate_oscillator": uo})
            except Exception:
                warn_key = "momentum.ultimate_oscillator"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "ultimate_oscillator")

            try:
                highest_high = _rolling(ohlcv_long["high"], window=14, min_periods=14).max().reset_index(level=0, drop=True)
                lowest_low = _rolling(ohlcv_long["low"], window=14, min_periods=14).min().reset_index(level=0, drop=True)
                wr = -100 * (highest_high - ohlcv_long["close"]) / (highest_high - lowest_low)
                _assign_latest("momentum", "williams_r", {"williams_r": wr})
            except Exception:
                warn_key = "momentum.williams_r"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "momentum", "williams_r")

            # --- volatility ---
            try:
                mavg = _rolling(ohlcv_long["close"], window=20, min_periods=20).mean().reset_index(level=0, drop=True)
                mstd = _rolling(ohlcv_long["close"], window=20, min_periods=20).std(ddof=0).reset_index(level=0, drop=True)
                hband = mavg + (2 * mstd)
                lband = mavg - (2 * mstd)
                wband = ((hband - lband) / mavg) * 100
                pband = (ohlcv_long["close"] - lband) / (hband - lband).where(hband != lband, np.nan)
                hband_ind = pd.Series(np.where(ohlcv_long["close"] > hband, 1.0, 0.0), index=ohlcv_long.index)
                lband_ind = pd.Series(np.where(ohlcv_long["close"] < lband, 1.0, 0.0), index=ohlcv_long.index)
                _assign_latest(
                    "volatility",
                    "bbands",
                    {
                        "bollinger_mavg": mavg,
                        "bollinger_hband": hband,
                        "bollinger_lband": lband,
                        "bollinger_wband": wband,
                        "bollinger_pband": pband,
                        "bollinger_hband_indicator": hband_ind,
                        "bollinger_lband_indicator": lband_ind,
                    },
                )
            except Exception:
                warn_key = "volatility.bbands"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volatility", "bbands")

            try:
                hband = _rolling(ohlcv_long["high"], window=20, min_periods=20).max().reset_index(level=0, drop=True)
                lband = _rolling(ohlcv_long["low"], window=20, min_periods=20).min().reset_index(level=0, drop=True)
                mband = ((hband - lband) / 2.0) + lband
                mavg = _rolling(ohlcv_long["close"], window=20, min_periods=20).mean().reset_index(level=0, drop=True)
                wband = ((hband - lband) / mavg) * 100
                pband = (ohlcv_long["close"] - lband) / (hband - lband)
                _assign_latest(
                    "volatility",
                    "donchian",
                    {
                        "donchian_channel_hband": hband,
                        "donchian_channel_lband": lband,
                        "donchian_channel_mband": mband,
                        "donchian_channel_pband": pband,
                        "donchian_channel_wband": wband,
                    },
                )
            except Exception:
                warn_key = "volatility.donchian"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volatility", "donchian")

            try:
                tp = ((ohlcv_long["high"] + ohlcv_long["low"] + ohlcv_long["close"]) / 3.0)
                tp_m = _rolling(tp, window=20, min_periods=20).mean().reset_index(level=0, drop=True)
                tp_high = _rolling((((4 * ohlcv_long["high"]) - (2 * ohlcv_long["low"]) + ohlcv_long["close"]) / 3.0), window=20, min_periods=0).mean().reset_index(level=0, drop=True)
                tp_low = _rolling((((-2 * ohlcv_long["high"]) + (4 * ohlcv_long["low"]) + ohlcv_long["close"]) / 3.0), window=20, min_periods=0).mean().reset_index(level=0, drop=True)
                wband = ((tp_high - tp_low) / tp_m) * 100
                pband = (ohlcv_long["close"] - tp_low) / (tp_high - tp_low)
                hband_ind = pd.Series(np.where(ohlcv_long["close"] > tp_high, 1.0, 0.0), index=ohlcv_long.index)
                lband_ind = pd.Series(np.where(ohlcv_long["close"] < tp_low, 1.0, 0.0), index=ohlcv_long.index)
                _assign_latest(
                    "volatility",
                    "keltner",
                    {
                        "keltner_channel_hband": tp_high,
                        "keltner_channel_lband": tp_low,
                        "keltner_channel_mband": tp_m,
                        "keltner_channel_pband": pband,
                        "keltner_channel_wband": wband,
                        "keltner_channel_hband_indicator": hband_ind,
                        "keltner_channel_lband_indicator": lband_ind,
                    },
                )
            except Exception:
                warn_key = "volatility.keltner"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volatility", "keltner")

            try:
                ui_max = _rolling(ohlcv_long["close"], window=14, min_periods=1).max().reset_index(level=0, drop=True)
                r_i = 100 * (ohlcv_long["close"] - ui_max) / ui_max

                def _ui_func(x: np.ndarray) -> float:
                    return float(np.sqrt((x ** 2 / 14).sum()))

                ulcer = _rolling(r_i, window=14).apply(_ui_func, raw=True).reset_index(level=0, drop=True)
                _assign_latest("volatility", "ulcer_index", {"ulcer_index": ulcer})
            except Exception:
                warn_key = "volatility.ulcer_index"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volatility", "ulcer_index")

            # --- trend ---
            # Aroon is currently NULL-only due to surface signature mismatch; preserve behavior.
            # (compute_indicator_latest passes high/low which ta.AroonIndicator does not accept.)

            try:
                def _mad(x: np.ndarray) -> float:
                    return float(np.mean(np.abs(x - np.mean(x))))

                tp = (ohlcv_long["high"] + ohlcv_long["low"] + ohlcv_long["close"]) / 3.0
                tp_ma = _rolling(tp, window=20, min_periods=20).mean().reset_index(level=0, drop=True)
                tp_mad = _rolling(tp, window=20, min_periods=20).apply(_mad, raw=True).reset_index(level=0, drop=True)
                cci = (tp - tp_ma) / (0.015 * tp_mad)
                _assign_latest("trend", "cci", {"cci": cci})
            except Exception:
                warn_key = "trend.cci"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "cci")

            try:
                shifted = g_close.shift(int((0.5 * 20) + 1))
                shifted = shifted.fillna(g_close.transform("mean"))
                sma = _rolling(ohlcv_long["close"], window=20, min_periods=20).mean().reset_index(level=0, drop=True)
                dpo = shifted - sma
                _assign_latest("trend", "dpo", {"dpo": dpo})
            except Exception:
                warn_key = "trend.dpo"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "dpo")

            try:
                ema14 = _ema(ohlcv_long["close"], span=14, min_periods=14)
                _assign_latest("trend", "ema", {"ema_indicator": ema14})
            except Exception:
                warn_key = "trend.ema"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "ema")

            try:
                conv = 0.5 * (
                    _rolling(ohlcv_long["high"], window=9, min_periods=9).max().reset_index(level=0, drop=True)
                    + _rolling(ohlcv_long["low"], window=9, min_periods=9).min().reset_index(level=0, drop=True)
                )
                base = 0.5 * (
                    _rolling(ohlcv_long["high"], window=26, min_periods=26).max().reset_index(level=0, drop=True)
                    + _rolling(ohlcv_long["low"], window=26, min_periods=26).min().reset_index(level=0, drop=True)
                )
                spana = 0.5 * (conv + base)
                spanb = 0.5 * (
                    _rolling(ohlcv_long["high"], window=52, min_periods=0).max().reset_index(level=0, drop=True)
                    + _rolling(ohlcv_long["low"], window=52, min_periods=0).min().reset_index(level=0, drop=True)
                )
                _assign_latest(
                    "trend",
                    "ichimoku",
                    {
                        "ichimoku_conversion_line": conv,
                        "ichimoku_base_line": base,
                        "ichimoku_a": spana,
                        "ichimoku_b": spanb,
                    },
                )
            except Exception:
                warn_key = "trend.ichimoku"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "ichimoku")

            try:
                mean_close = g_close.transform("mean")
                def _rocma(r: int, w: int) -> pd.Series:
                    shifted = g_close.shift(r).fillna(mean_close)
                    roc = ((ohlcv_long["close"] - shifted) / shifted)
                    return _rolling(roc, window=w, min_periods=w).mean().reset_index(level=0, drop=True)

                rocma1 = _rocma(10, 10)
                rocma2 = _rocma(15, 10)
                rocma3 = _rocma(20, 10)
                rocma4 = _rocma(30, 15)
                kst = 100 * (rocma1 + 2 * rocma2 + 3 * rocma3 + 4 * rocma4)
                kst_sig = _rolling(kst, window=9, min_periods=0).mean().reset_index(level=0, drop=True)
                kst_diff = kst - kst_sig
                _assign_latest("trend", "kst", {"kst": kst, "kst_sig": kst_sig, "kst_diff": kst_diff})
            except Exception:
                warn_key = "trend.kst"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "kst")

            try:
                emafast = _ema(ohlcv_long["close"], span=12, min_periods=12)
                emaslow = _ema(ohlcv_long["close"], span=26, min_periods=26)
                macd = emafast - emaslow
                macd_signal = _ema(macd, span=9, min_periods=9)
                macd_diff = macd - macd_signal
                _assign_latest("trend", "macd", {"macd": macd, "macd_signal": macd_signal, "macd_diff": macd_diff})
            except Exception:
                warn_key = "trend.macd"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "macd")

            try:
                amplitude = ohlcv_long["high"] - ohlcv_long["low"]
                ema1 = _ema(amplitude, span=9, min_periods=9)
                ema2 = _ema(ema1, span=9, min_periods=9)
                mass = ema1 / ema2
                mass_index = _rolling(mass, window=25, min_periods=25).sum().reset_index(level=0, drop=True)
                _assign_latest("trend", "mass_index", {"mass_index": mass_index})
            except Exception:
                warn_key = "trend.mass_index"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "mass_index")

            try:
                for w in (14, 20, 50, 200):
                    sma_w = _rolling(ohlcv_long["close"], window=w, min_periods=w).mean().reset_index(level=0, drop=True)
                    _assign_latest("trend", "sma", {f"sma_{w}": sma_w})
            except Exception:
                warn_key = "trend.sma"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "sma")

            try:
                emafast = _ema(ohlcv_long["close"], span=23, min_periods=23)
                emaslow = _ema(ohlcv_long["close"], span=50, min_periods=50)
                macd = emafast - emaslow
                macd_min = _rolling(macd, window=10).min().reset_index(level=0, drop=True)
                macd_max = _rolling(macd, window=10).max().reset_index(level=0, drop=True)
                stoch_k = 100 * (macd - macd_min) / (macd_max - macd_min)
                stoch_d = _ema(stoch_k, span=3, min_periods=3)
                stoch_d_min = _rolling(stoch_d, window=10).min().reset_index(level=0, drop=True)
                stoch_d_max = _rolling(stoch_d, window=10).max().reset_index(level=0, drop=True)
                stoch_kd = 100 * (stoch_d - stoch_d_min) / (stoch_d_max - stoch_d_min)
                stc = _ema(stoch_kd, span=3, min_periods=3)
                _assign_latest("trend", "stc", {"stc": stc})
            except Exception:
                warn_key = "trend.stc"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "stc")

            try:
                ema1 = _ema(ohlcv_long["close"], span=15, min_periods=15)
                ema2 = _ema(ema1, span=15, min_periods=15)
                ema3 = _ema(ema2, span=15, min_periods=15)
                ema3_mean = ema3.groupby(key, sort=False).transform("mean")
                ema3_shift = ema3.groupby(key, sort=False).shift(1).fillna(ema3_mean)
                trix = ((ema3 - ema3_shift) / ema3_shift) * 100
                _assign_latest("trend", "trix", {"trix": trix})
            except Exception:
                warn_key = "trend.trix"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "trix")

            try:
                close_mean = g_close.transform("mean")
                close_shift = g_close.shift(1).fillna(close_mean)
                tr1 = ohlcv_long["high"] - ohlcv_long["low"]
                tr2 = (ohlcv_long["high"] - close_shift).abs()
                tr3 = (ohlcv_long["low"] - close_shift).abs()
                true_range = pd.DataFrame({"tr1": tr1, "tr2": tr2, "tr3": tr3}).max(axis=1)
                trn = _rolling(true_range, window=14, min_periods=14).sum().reset_index(level=0, drop=True)
                vmp = (ohlcv_long["high"] - g_low.shift(1)).abs()
                vmm = (ohlcv_long["low"] - g_high.shift(1)).abs()
                vip = _rolling(vmp, window=14, min_periods=14).sum().reset_index(level=0, drop=True) / trn
                vin = _rolling(vmm, window=14, min_periods=14).sum().reset_index(level=0, drop=True) / trn
                vid = vip - vin
                _assign_latest("trend", "vortex", {"vortex_indicator_pos": vip, "vortex_indicator_neg": vin, "vortex_indicator_diff": vid})
            except Exception:
                warn_key = "trend.vortex"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "vortex")

            try:
                window = 9
                weights = np.array([i * 2 / (window * (window + 1)) for i in range(1, window + 1)], dtype="float64")

                def _wma_fn(x: np.ndarray) -> float:
                    return float((weights * x).sum())

                wma = _rolling(ohlcv_long["close"], window=window).apply(_wma_fn, raw=True).reset_index(level=0, drop=True)
                _assign_latest("trend", "wma", {"wma": wma})
            except Exception:
                warn_key = "trend.wma"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "trend", "wma")

            # --- volume ---
            try:
                clv = ((ohlcv_long["close"] - ohlcv_long["low"]) - (ohlcv_long["high"] - ohlcv_long["close"])) / (
                    ohlcv_long["high"] - ohlcv_long["low"]
                )
                clv = clv.fillna(0.0)
                adi = (clv * ohlcv_long["volume"]).groupby(key, sort=False).cumsum()
                _assign_latest("volume", "adi", {"acc_dist_index": adi})
            except Exception:
                warn_key = "volume.adi"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volume", "adi")

            try:
                clv = ((ohlcv_long["close"] - ohlcv_long["low"]) - (ohlcv_long["high"] - ohlcv_long["close"])) / (
                    ohlcv_long["high"] - ohlcv_long["low"]
                )
                mfv = clv.fillna(0.0) * ohlcv_long["volume"]
                cmf = (
                    _rolling(mfv, window=20, min_periods=20).sum().reset_index(level=0, drop=True)
                    / _rolling(ohlcv_long["volume"], window=20, min_periods=20).sum().reset_index(level=0, drop=True)
                )
                _assign_latest("volume", "cmf", {"chaikin_money_flow": cmf})
            except Exception:
                warn_key = "volume.cmf"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volume", "cmf")

            try:
                emv = (
                    (g_high.diff(1) + g_low.diff(1)) * (ohlcv_long["high"] - ohlcv_long["low"]) / (2 * ohlcv_long["volume"])
                )
                emv *= 100000000
                sma_emv = _rolling(emv, window=14, min_periods=14).mean().reset_index(level=0, drop=True)
                _assign_latest("volume", "eom", {"ease_of_movement": emv, "sma_ease_of_movement": sma_emv})
            except Exception:
                warn_key = "volume.eom"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volume", "eom")

            try:
                fi_series = (ohlcv_long["close"] - g_close.shift(1)) * ohlcv_long["volume"]
                fi = _ema(fi_series, span=13, min_periods=13)
                _assign_latest("volume", "fi", {"force_index": fi})
            except Exception:
                warn_key = "volume.fi"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volume", "fi")

            try:
                tp = (ohlcv_long["high"] + ohlcv_long["low"] + ohlcv_long["close"]) / 3.0
                tp_shift = tp.groupby(key, sort=False).shift(1)
                up_down = np.where(tp > tp_shift, 1, np.where(tp < tp_shift, -1, 0))
                mfr = tp * ohlcv_long["volume"] * pd.Series(up_down, index=ohlcv_long.index)

                def _pos_sum(x: np.ndarray) -> float:
                    return float(np.sum(np.where(x >= 0.0, x, 0.0)))

                def _neg_sum(x: np.ndarray) -> float:
                    return float(np.sum(np.where(x < 0.0, x, 0.0)))

                pos_mf = _rolling(mfr, window=14, min_periods=14).apply(_pos_sum, raw=True).reset_index(level=0, drop=True)
                neg_mf = abs(_rolling(mfr, window=14, min_periods=14).apply(_neg_sum, raw=True).reset_index(level=0, drop=True))
                mfi_ratio = pos_mf / neg_mf
                mfi = 100 - (100 / (1 + mfi_ratio))
                _assign_latest("volume", "mfi", {"money_flow_index": mfi})
            except Exception:
                warn_key = "volume.mfi"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volume", "mfi")

            try:
                close_shift = g_close.shift(1)
                obv = np.where(ohlcv_long["close"] < close_shift, -ohlcv_long["volume"], ohlcv_long["volume"])
                obv = pd.Series(obv, index=ohlcv_long.index).groupby(key, sort=False).cumsum()
                _assign_latest("volume", "obv", {"on_balance_volume": obv})
            except Exception:
                warn_key = "volume.obv"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volume", "obv")

            try:
                close_mean = g_close.transform("mean")
                close_shift = g_close.shift(1).fillna(close_mean)
                vpt = ohlcv_long["volume"] * ((ohlcv_long["close"] - close_shift) / close_shift)
                vpt_mean = vpt.groupby(key, sort=False).transform("mean")
                vpt_shift = vpt.groupby(key, sort=False).shift(1).fillna(vpt_mean)
                vpt_series = vpt_shift + vpt
                _assign_latest("volume", "vpt", {"volume_price_trend": vpt_series})
            except Exception:
                warn_key = "volume.vpt"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volume", "vpt")

            try:
                tp = (ohlcv_long["high"] + ohlcv_long["low"] + ohlcv_long["close"]) / 3.0
                tpv = tp * ohlcv_long["volume"]
                total_pv = _rolling(tpv, window=14, min_periods=14).sum().reset_index(level=0, drop=True)
                total_vol = _rolling(ohlcv_long["volume"], window=14, min_periods=14).sum().reset_index(level=0, drop=True)
                vwap = total_pv / total_vol
                _assign_latest("volume", "vwap", {"volume_weighted_average_price": vwap})
            except Exception:
                warn_key = "volume.vwap"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "volume", "vwap")

            # --- others ---
            try:
                first_close = g_close.transform("first")
                cr = ((ohlcv_long["close"] / first_close) - 1) * 100
                _assign_latest("others", "cr", {"cumulative_return": cr})
            except Exception:
                warn_key = "others.cr"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "others", "cr")

            try:
                dlr = np.log(ohlcv_long["close"]).groupby(key, sort=False).diff() * 100
                _assign_latest("others", "dlr", {"daily_log_return": dlr})
            except Exception:
                warn_key = "others.dlr"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "others", "dlr")

            try:
                close_mean = g_close.transform("mean")
                prev_close = g_close.shift(1).fillna(close_mean)
                dr = ((ohlcv_long["close"] / prev_close) - 1) * 100
                _assign_latest("others", "dr", {"daily_return": dr})
            except Exception:
                warn_key = "others.dr"
                if warn_key not in _WARNED_INDICATOR_ERRORS:
                    _WARNED_INDICATOR_ERRORS.add(warn_key)
                    log.warning("[A2] indicator failed category=%s name=%s", "others", "dr")

    # Fallback indicators that are iterative/heavy to reproduce exactly in a vectorized groupby:
    # - kama, atr, adx, psar, nvi
    fallback = {
        ("momentum", "kama"),
        ("volatility", "atr"),
        ("trend", "adx"),
        ("trend", "psar"),
        ("volume", "nvi"),
    }

    for tid, group_df in ohlcv_long.groupby("ticker_id", sort=False):
        ticker_id = str(tid)
        if ticker_id not in out:
            continue
        ticker_ohlcv = group_df[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with np.errstate(divide="ignore", invalid="ignore"):
                for category, name in fallback:
                    try:
                        result = surface.compute_indicator_latest(ticker_ohlcv, category, name)
                        outputs = result.get("outputs", {}) if isinstance(result, dict) else {}
                        for k in out[ticker_id][category][name].keys():
                            out[ticker_id][category][name][k] = _as_scalar_or_none(outputs.get(k))
                    except Exception:
                        warn_key = f"{category}.{name}"
                        if warn_key not in _WARNED_INDICATOR_ERRORS:
                            _WARNED_INDICATOR_ERRORS.add(warn_key)
                            log.warning("[A2] indicator failed category=%s name=%s", category, name)

    if stats is not None:
        stats.technical_indicator_time_sec += time.perf_counter() - t0

    # Pattern recognition (optional)
    pattern_t0 = time.perf_counter()
    if enable_pattern_indicators and getattr(surface, "talib", None) is not None:
        for tid, group_df in ohlcv_long.groupby("ticker_id", sort=False):
            ticker_id = str(tid)
            if ticker_id not in out:
                continue
            ticker_ohlcv = group_df[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        out[ticker_id]["pattern_recognition"] = surface.compute_pattern_recognition_latest(
                            ticker_ohlcv
                        )
            except Exception:
                global _WARNED_PATTERN_ERRORS
                if not _WARNED_PATTERN_ERRORS:
                    _WARNED_PATTERN_ERRORS = True
                    log.warning("[A2] pattern_recognition failed")
                out[ticker_id]["pattern_recognition"] = {k: None for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS}
    else:
        if enable_pattern_indicators and getattr(surface, "talib", None) is None:
            global _WARNED_PATTERN_BACKEND_UNAVAILABLE
            if not _WARNED_PATTERN_BACKEND_UNAVAILABLE:
                _WARNED_PATTERN_BACKEND_UNAVAILABLE = True
                log.info("[A2] pattern backend unavailable; emitting NULL patterns")
        for tid in ticker_ids:
            out[str(tid)]["pattern_recognition"] = {k: None for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS}

    if stats is not None:
        patterns_present = 0
        if enable_pattern_indicators:
            stats.pattern_indicator_time_sec += time.perf_counter() - pattern_t0
        for tid in ticker_ids:
            patterns = out[str(tid)].get("pattern_recognition") or {}
            if enable_pattern_indicators and getattr(surface, "talib", None) is not None:
                stats.pattern_indicators_attempted += len(patterns)
            for v in patterns.values():
                if v is not None:
                    patterns_present += 1
        stats.pattern_indicators_present += patterns_present

        for tid in ticker_ids:
            tech = out[str(tid)]
            for category, indicators in surface.INDICATOR_REGISTRY.items():
                for name, info in indicators.items():
                    for output_key in info.get("outputs", []):
                        stats.indicators_computed_total += 1
                        if tech[category][name].get(output_key) is None:
                            stats.indicators_null_total += 1

    return out


def _compute_chunk_payloads(
    conn,
    *,
    ticker_ids: Sequence[str],
    snapshot_date: date,
    enable_pattern_indicators: bool,
    stats: Optional[A2BatchStats],
    log: logging.Logger,
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Optional[float]]]]:
    """
    Compute technical indicators + price metrics for a ticker chunk.
    """
    ohlcv_long = _load_ohlcv_history_for_tickers(conn, ticker_ids=ticker_ids, snapshot_date=snapshot_date)
    technical = _compute_chunk_technical_indicators_latest(
        ohlcv_long,
        ticker_ids=ticker_ids,
        enable_pattern_indicators=enable_pattern_indicators,
        stats=stats,
        log=log,
    )
    price = _compute_chunk_price_metrics_latest(ohlcv_long, ticker_ids=ticker_ids)
    return technical, price


def compute_technical_indicators_json(
    ohlcv: pd.DataFrame,
    *,
    enable_pattern_indicators: bool = False,
    stats: Optional[A2BatchStats] = None,
    log: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    surface = _indicator_surface()
    log = log or logger

    technical: Dict[str, Any] = {
        cat: {} for cat in surface.TECHNICAL_TOP_LEVEL_CATEGORIES
    }

    t0 = time.perf_counter()
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
    if stats is not None:
        stats.technical_indicator_time_sec += time.perf_counter() - t0

    pattern_t0 = time.perf_counter()
    if enable_pattern_indicators and getattr(surface, "talib", None) is not None:
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
    else:
        if enable_pattern_indicators and getattr(surface, "talib", None) is None:
            global _WARNED_PATTERN_BACKEND_UNAVAILABLE
            if not _WARNED_PATTERN_BACKEND_UNAVAILABLE:
                _WARNED_PATTERN_BACKEND_UNAVAILABLE = True
                log.info("[A2] pattern backend unavailable; emitting NULL patterns")
        technical["pattern_recognition"] = {
            k: None for k in surface.PATTERN_RECOGNITION_OUTPUT_KEYS
        }

    if stats is not None:
        if enable_pattern_indicators:
            stats.pattern_indicator_time_sec += time.perf_counter() - pattern_t0
        patterns = technical.get("pattern_recognition") or {}
        if enable_pattern_indicators and getattr(surface, "talib", None) is not None:
            stats.pattern_indicators_attempted += len(patterns)
        for v in patterns.values():
            if v is not None:
                stats.pattern_indicators_present += 1

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


def build_snapshot_ticker_plan(
    conn, *, snapshot_dates: Sequence[date], fill_missing: bool
) -> Dict[date, list[str]]:
    if fill_missing:
        snapshot_plan: Dict[date, list[str]] = {}
        for d in snapshot_dates:
            snapshot_plan[d] = _fetch_tickers_missing_snapshot(conn, _snapshot_time_utc(d))
        return snapshot_plan

    ticker_ids = _fetch_active_ticker_ids(conn)
    return {d: ticker_ids for d in snapshot_dates}


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


def _load_ohlcv_history_for_tickers(
    conn, *, ticker_ids: Sequence[str], snapshot_date: date
) -> pd.DataFrame:
    """
    Load OHLCV history for many tickers in a single query.

    Returns a long DataFrame with deterministic ordering within each ticker.
    """
    cols = ["ticker_id", "row_index", "open", "high", "low", "close", "volume"]
    if not ticker_ids:
        return pd.DataFrame(columns=cols)

    if not hasattr(conn, "cursor"):
        # Unit-test fallback (DummyConn) where _load_ohlcv_history is monkeypatched.
        frames: list[pd.DataFrame] = []
        for ticker_id in ticker_ids:
            ohlcv = _load_ohlcv_history(conn, ticker_id, snapshot_date).copy()
            if ohlcv.empty:
                continue
            ohlcv.insert(0, "row_index", range(len(ohlcv)))
            ohlcv.insert(0, "ticker_id", str(ticker_id))
            frames.append(ohlcv)
        if not frames:
            return pd.DataFrame(columns=cols)
        out = pd.concat(frames, ignore_index=True)
        out = out[cols]
        out["ticker_id"] = out["ticker_id"].astype(str)
        out["row_index"] = pd.to_numeric(out["row_index"], errors="coerce").astype("int64")
        out = out.sort_values(["ticker_id", "row_index"], kind="mergesort").reset_index(drop=True)
        return out

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticker_id::text, date, open, high, low, close, volume
            FROM ohlcv
            WHERE ticker_id::text = ANY(%s)
              AND date <= %s
            ORDER BY ticker_id::text ASC, date ASC
            """,
            (list(map(str, ticker_ids)), snapshot_date),
        )
        rows = cur.fetchall()

    if not rows:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(
        rows, columns=["ticker_id", "date", "open", "high", "low", "close", "volume"]
    )
    df["ticker_id"] = df["ticker_id"].astype(str)
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("float64")
    df = df.sort_values(["ticker_id", "date"], kind="mergesort").reset_index(drop=True)
    df["row_index"] = df.groupby("ticker_id", sort=False).cumcount()
    df = df.drop(columns=["date"])
    df = df[cols]
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
    enable_pattern_indicators: bool = False,
    ticker_chunk_size: int = DEFAULT_TICKER_CHUNK_SIZE,
    ticker_ids_by_date: Optional[Dict[date, list[str]]] = None,
    workers: int = 1,
    db_url: Optional[str] = None,
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
    stats.pattern_indicators_enabled = bool(enable_pattern_indicators)
    if enable_pattern_indicators:
        stats.pattern_backend_available = bool(getattr(_indicator_surface(), "talib", None) is not None)
    else:
        stats.pattern_backend_available = False

    snapshot_plan = (
        ticker_ids_by_date
        if ticker_ids_by_date is not None
        else build_snapshot_ticker_plan(conn, snapshot_dates=snapshot_dates, fill_missing=fill_missing)
    )

    if workers <= 1:
        for d in snapshot_dates:
            date_start = time.monotonic()
            snapshot_time = _snapshot_time_utc(d)
            ticker_ids = snapshot_plan.get(d, [])
            total = len(ticker_ids)
            chunks = partition_ticker_ids(ticker_ids, chunk_size=ticker_chunk_size)

            date_processed = 0
            date_chunks_completed_time_sec = 0.0

            for chunk_index, chunk in enumerate(chunks, start=1):
                stats.total_chunks += 1
                chunk_start = time.monotonic()

                technical_by_ticker, price_by_ticker = _compute_chunk_payloads(
                    conn,
                    ticker_ids=chunk,
                    snapshot_date=d,
                    enable_pattern_indicators=enable_pattern_indicators,
                    stats=stats,
                    log=log,
                )

                for ticker_id in chunk:
                    if verbose:
                        log.info("[A2] ticker snapshot_date=%s ticker_id=%s", d.isoformat(), ticker_id)

                    technical = technical_by_ticker.get(str(ticker_id))
                    if technical is None:
                        technical = compute_technical_indicators_json(
                            pd.DataFrame(columns=["open", "high", "low", "close", "volume"]),
                            enable_pattern_indicators=enable_pattern_indicators,
                            stats=None,
                            log=log,
                        )
                    price_metrics = price_by_ticker.get(str(ticker_id)) or {"rvol": None, "vsi": None, "hv": None}

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
                    date_processed += 1

                    if heartbeat_every > 0 and date_processed % heartbeat_every == 0:
                        elapsed = _format_elapsed(time.monotonic() - date_start)
                        remaining = total - date_processed
                        cumulative_time_so_far = date_chunks_completed_time_sec + (time.monotonic() - chunk_start)
                        _, eta_sec = compute_eta_seconds(
                            cumulative_chunk_time_sec=cumulative_time_so_far,
                            tickers_processed_so_far=date_processed,
                            remaining_tickers=remaining,
                        )
                        log.info(
                            "[A2] progress snapshot_date=%s\n"
                            "  processed=%s/%s\n"
                            "  elapsed=%s\n"
                            "  eta=%s",
                            d.isoformat(),
                            date_processed,
                            total,
                            elapsed,
                            _format_elapsed(eta_sec),
                        )

                conn.commit()
                chunk_elapsed_sec = time.monotonic() - chunk_start
                date_chunks_completed_time_sec += chunk_elapsed_sec

                stats.chunk_times_sec.append(chunk_elapsed_sec)
                stats.chunk_time_sec_total += chunk_elapsed_sec

                remaining = total - date_processed
                avg_sec_per_ticker, eta_sec = compute_eta_seconds(
                    cumulative_chunk_time_sec=date_chunks_completed_time_sec,
                    tickers_processed_so_far=date_processed,
                    remaining_tickers=remaining,
                )
                log.debug(
                    "[A2] CHUNK %s/%s\n"
                    "  tickers_in_chunk=%s\n"
                    "  chunk_elapsed_sec=%.3f\n"
                    "  avg_sec_per_ticker=%.6f\n"
                    "  remaining_tickers=%s\n"
                    "  eta_remaining_sec=%.3f",
                    chunk_index,
                    len(chunks),
                    len(chunk),
                    chunk_elapsed_sec,
                    avg_sec_per_ticker,
                    remaining,
                    eta_sec,
                )
    else:
        if not db_url:
            raise ValueError("db_url is required when workers > 1")

        work_items: list[A2ChunkWorkItem] = []
        for d in snapshot_dates:
            snapshot_time = _snapshot_time_utc(d)
            ticker_ids = snapshot_plan.get(d, [])
            chunks = partition_ticker_ids(ticker_ids, chunk_size=ticker_chunk_size)
            total_chunks_for_date = len(chunks)
            for chunk_index, chunk in enumerate(chunks, start=1):
                work_items.append(
                    A2ChunkWorkItem(
                        snapshot_date=d,
                        snapshot_time=snapshot_time,
                        chunk_index=chunk_index,
                        total_chunks_for_date=total_chunks_for_date,
                        ticker_ids=chunk,
                    )
                )

        if not work_items:
            stats.duration_seconds = time.monotonic() - run_start
            log.info(
                "[A2] SUMMARY\n"
                "  dates: %s\n"
                "  tickers: %s\n"
                "  snapshots_written: %s\n"
                "  total_chunks: %s\n"
                "  mean_chunk_time_sec: %.3f\n"
                "  p95_chunk_time_sec: %.3f\n"
                "  avg_sec_per_ticker: %.6f\n"
                "  indicators_computed: %s\n"
                "  indicators_null: %s\n"
                "  pattern_indicators_enabled: %s\n"
                "  pattern_backend_available: %s\n"
                "  pattern_indicators_attempted: %s\n"
                "  pattern_indicators_present: %s\n"
                "  technical_indicator_time_sec: %.3f\n"
                "  pattern_indicator_time_sec: %.3f\n"
                "  duration_sec: %.3f",
                ",".join(stats.dates),
                stats.tickers_processed,
                stats.snapshots_written,
                stats.total_chunks,
                0.0,
                0.0,
                0.0,
                stats.indicators_computed_total,
                stats.indicators_null_total,
                stats.pattern_indicators_enabled,
                stats.pattern_backend_available,
                stats.pattern_indicators_attempted,
                stats.pattern_indicators_present,
                stats.technical_indicator_time_sec,
                stats.pattern_indicator_time_sec if stats.pattern_indicators_enabled else 0.0,
                stats.duration_seconds,
                extra={"a2_summary": True, "a2_stats": stats.to_log_extra()},
            )
            return

        effective_workers = max(1, min(int(workers), len(work_items)))
        assignments = partition_chunks_for_workers(work_items, workers=effective_workers)

        ctx = mp.get_context("spawn")
        pool = None
        try:
            pool = ctx.Pool(processes=effective_workers)
            worker_args: list[A2WorkerArgs] = [
                A2WorkerArgs(
                    worker_id=worker_id,
                    db_url=db_url,
                    work_items=items,
                    model_version=model_version,
                    enable_pattern_indicators=enable_pattern_indicators,
                )
                for worker_id, items in enumerate(assignments)
            ]
            results: list[A2WorkerResult] = pool.map(_run_a2_worker, worker_args)
            pool.close()
            pool.join()
        except KeyboardInterrupt:
            log.warning("[A2] KeyboardInterrupt; terminating worker pool")
            if pool is not None:
                pool.terminate()
                pool.join()
            raise
        except Exception:
            log.exception("[A2] Worker pool failed; terminating worker pool")
            if pool is not None:
                pool.terminate()
                pool.join()
            raise

        estimated_single_process_sec = 0.0
        for result in results:
            worker_stats = result.stats
            estimated_single_process_sec += float(worker_stats.duration_seconds)
            stats.tickers_processed += worker_stats.tickers_processed
            stats.snapshots_written += worker_stats.snapshots_written
            stats.total_chunks += worker_stats.total_chunks
            stats.chunk_times_sec.extend(worker_stats.chunk_times_sec)
            stats.chunk_time_sec_total += worker_stats.chunk_time_sec_total
            stats.indicators_computed_total += worker_stats.indicators_computed_total
            stats.indicators_null_total += worker_stats.indicators_null_total
            stats.pattern_indicators_attempted += worker_stats.pattern_indicators_attempted
            stats.pattern_indicators_present += worker_stats.pattern_indicators_present
            stats.technical_indicator_time_sec += worker_stats.technical_indicator_time_sec
            stats.pattern_indicator_time_sec += worker_stats.pattern_indicator_time_sec

        for result in sorted(results, key=lambda r: r.worker_id):
            w = result.stats
            tickers_per_sec = (w.tickers_processed / w.duration_seconds) if w.duration_seconds > 0 else 0.0
            log.info(
                "[A2] WORKER worker_id=%s pid=%s chunks=%s tickers=%s tickers_per_sec=%.2f duration_sec=%.3f",
                result.worker_id,
                result.pid,
                w.total_chunks,
                w.tickers_processed,
                tickers_per_sec,
                w.duration_seconds,
            )

        wall_sec = time.monotonic() - run_start
        speedup = (estimated_single_process_sec / wall_sec) if wall_sec > 0 else 0.0
        throughput = (stats.tickers_processed / wall_sec) if wall_sec > 0 else 0.0
        log.info(
            "[A2] PARALLEL runtime_sec=%.3f estimated_single_process_sec=%.3f speedup=%.2f throughput_tickers_per_sec=%.2f workers=%s",
            wall_sec,
            estimated_single_process_sec,
            speedup,
            throughput,
            effective_workers,
        )

    stats.duration_seconds = time.monotonic() - run_start
    mean_chunk_time = (
        stats.chunk_time_sec_total / float(stats.total_chunks) if stats.total_chunks else 0.0
    )
    p95_chunk_time = 0.0
    if stats.chunk_times_sec:
        sorted_times = sorted(stats.chunk_times_sec)
        idx = max(0, math.ceil(0.95 * len(sorted_times)) - 1)
        p95_chunk_time = float(sorted_times[idx])
    avg_sec_per_ticker_all = (
        stats.chunk_time_sec_total / float(stats.tickers_processed) if stats.tickers_processed else 0.0
    )
    log.info(
        "[A2] SUMMARY\n"
        "  dates: %s\n"
        "  tickers: %s\n"
        "  snapshots_written: %s\n"
        "  total_chunks: %s\n"
        "  mean_chunk_time_sec: %.3f\n"
        "  p95_chunk_time_sec: %.3f\n"
        "  avg_sec_per_ticker: %.6f\n"
        "  indicators_computed: %s\n"
        "  indicators_null: %s\n"
        "  pattern_indicators_enabled: %s\n"
        "  pattern_backend_available: %s\n"
        "  pattern_indicators_attempted: %s\n"
        "  pattern_indicators_present: %s\n"
        "  technical_indicator_time_sec: %.3f\n"
        "  pattern_indicator_time_sec: %.3f\n"
        "  duration_sec: %.3f",
        ",".join(stats.dates),
        stats.tickers_processed,
        stats.snapshots_written,
        stats.total_chunks,
        mean_chunk_time,
        p95_chunk_time,
        avg_sec_per_ticker_all,
        stats.indicators_computed_total,
        stats.indicators_null_total,
        stats.pattern_indicators_enabled,
        stats.pattern_backend_available,
        stats.pattern_indicators_attempted,
        stats.pattern_indicators_present,
        stats.technical_indicator_time_sec,
        stats.pattern_indicator_time_sec if stats.pattern_indicators_enabled else 0.0,
        stats.duration_seconds,
        extra={"a2_summary": True, "a2_stats": stats.to_log_extra()},
    )


def get_indicator_surface_for_tests():
    """
    Test helper to allow assertions against the authoritative surface without
    importing `docs/` as a Python package.
    """
    return _indicator_surface()
