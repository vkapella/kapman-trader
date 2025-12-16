"""
KapMan Story A2 — Local TA + Price Metric Computation

This module implements a minimal, self-contained subset of TA-Lib-compatible
indicator semantics for MVP use.

Indicators:
- RSI(14) using Wilder smoothing
- MACD(12,26,9)
- SMA(20), SMA(50)
- EMA(12), EMA(26)
- RVOL(20), VSI(20)
- HV(20)

No external TA libraries are required.
"""

from __future__ import annotations

from typing import Dict, Optional
import math
import numpy as np
import pandas as pd


def _last_or_none(series: pd.Series) -> Optional[float]:
    if series is None or series.empty:
        return None
    v = series.iloc[-1]
    if pd.isna(v):
        return None
    return float(v)


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi_pandas_ta(close: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI implementation aligned with pandas-ta / TradingView semantics.

    NOTE:
    This intentionally does NOT match strict TA-Lib seeding.
    It matches pandas-ta to preserve historical behavior and unit tests.
    """
    import numpy as np
    import pandas as pd

    if len(close) < period + 1:
        return pd.Series(np.nan, index=close.index, dtype="float64")

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    rsi = pd.Series(np.nan, index=close.index, dtype="float64")

    # --- pandas-ta seed: uses period + 1 values ---
    avg_gain = gain.iloc[1 : period + 1].mean()
    avg_loss = loss.iloc[1 : period + 1].mean()

    rs = np.inf if avg_loss == 0 else avg_gain / avg_loss
    rsi.iloc[period] = 100 - (100 / (1 + rs))

    # --- Wilder smoothing thereafter ---
    for i in range(period + 1, len(close)):
        avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period

        rs = np.inf if avg_loss == 0 else avg_gain / avg_loss
        rsi.iloc[i] = 100 - (100 / (1 + rs))

    return rsi


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)

    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(
        span=signal, adjust=False, min_periods=signal
    ).mean()
    macd_hist = macd_line - macd_signal

    return macd_line, macd_signal, macd_hist


def rvol(volume: pd.Series, window: int = 20) -> Optional[float]:
    if len(volume) < window + 1:
        return None
    denom = volume.iloc[-window - 1 : -1].mean()
    if denom <= 0 or pd.isna(denom):
        return None
    return float(volume.iloc[-1] / denom)


def hv_annualized(close: pd.Series, window: int = 20) -> Optional[float]:
    if len(close) < window + 1:
        return None
    log_ret = np.log(close / close.shift(1))
    hv = log_ret.iloc[-window:].std(ddof=0)
    if pd.isna(hv):
        return None
    return float(hv * math.sqrt(252))


def compute_ta_price_snapshot(ohlcv: pd.DataFrame) -> Dict[str, Optional[float]]:
    if ohlcv.empty:
        return {}

    close = ohlcv["close"]
    volume = ohlcv["volume"]

    out: Dict[str, Optional[float]] = {}

    out["rsi_14"] = _last_or_none(rsi_pandas_ta(close, 14))

    macd_line, macd_signal, macd_hist = macd(close, 12, 26, 9)
    out["macd_line"] = _last_or_none(macd_line)
    out["macd_signal"] = _last_or_none(macd_signal)
    out["macd_histogram"] = _last_or_none(macd_hist)

    out["sma_20"] = _last_or_none(close.rolling(20, min_periods=20).mean())
    out["sma_50"] = _last_or_none(close.rolling(50, min_periods=50).mean())
    out["ema_12"] = _last_or_none(_ema(close, 12))
    out["ema_26"] = _last_or_none(_ema(close, 26))

    rvol_val = rvol(volume, 20)
    out["rvol"] = rvol_val
    out["vsi"] = rvol_val

    out["hv_20"] = hv_annualized(close, 20)

    return out
