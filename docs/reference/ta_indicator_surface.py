"""
KapMan MVP — A2 Metric Surface Contract (Authoritative Reference)

This module defines the *authoritative* technical-indicator and pattern-recognition
surface to be computed from KapMan OHLCV and persisted into daily_snapshots.

Intent
------
- Keep the A2 GitHub story durable (contract-level)
- Put the detailed metric surface here so:
  - Windsurf/Codex prompts can be precise
  - Tests can assert stable keys
  - Future changes are explicit and versioned

Sources
-------
- pandas-ta style indicators via the `ta` Python library:
  https://github.com/bukosabino/ta (library)
- TA-Lib Python wrapper (candlestick pattern recognition):
  Documentation index: https://ta-lib.github.io/ta-lib-python/doc_index.html
  Pattern functions:    https://ta-lib.github.io/ta-lib-python/func_groups/pattern_recognition.html
  Project repo:         https://github.com/TA-Lib/ta-lib-python

Manual (non-library) metrics
----------------------------
These are computed directly from OHLCV (pandas/numpy), not from `ta` or TA-Lib:
- price_metrics_json:
  - rvol (Relative Volume)
  - vsi  (Volume Surprise Index)
  - hv   (Historical Volatility)
- SMA variants (explicit, not the `ta` default output name):
  - sma_14, sma_20, sma_50, sma_200

Notes
-----
- This file is intended as a *reference surface contract*.
- The production A2 job should implement deterministic computation + persistence.
- If an indicator cannot be computed (missing columns, insufficient history, runtime error),
  the output value MUST be present as None (serialized as NULL in JSONB).

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

# Optional imports; A2 implementation should include these deps in requirements.
try:
    import ta as ta_lib  # type: ignore
except Exception:  # pragma: no cover
    ta_lib = None  # type: ignore

try:
    import talib  # type: ignore
except Exception:  # pragma: no cover
    talib = None  # type: ignore


# --------------------------------------------------------------------------------------
# External reference URLs (for prompts / documentation)
# --------------------------------------------------------------------------------------

TA_LIB_DOC_INDEX_URL = "https://ta-lib.github.io/ta-lib-python/doc_index.html"
TA_LIB_PATTERN_RECOG_URL = "https://ta-lib.github.io/ta-lib-python/func_groups/pattern_recognition.html"
TA_LIB_REPO_URL = "https://github.com/TA-Lib/ta-lib-python"


# --------------------------------------------------------------------------------------
# Locked A2 output shape keys
# --------------------------------------------------------------------------------------

TECHNICAL_TOP_LEVEL_CATEGORIES: Tuple[str, ...] = (
    "momentum",
    "volatility",
    "trend",
    "volume",
    "others",
    "pattern_recognition",
)

PRICE_METRICS_KEYS: Tuple[str, ...] = (
    "rvol",
    "vsi",
    "hv",
)

SMA_VARIANTS: Tuple[int, ...] = (14, 20, 50, 200)
SMA_OUTPUT_KEYS: Tuple[str, ...] = tuple(f"sma_{w}" for w in SMA_VARIANTS)


# --------------------------------------------------------------------------------------
# Authoritative TA indicator registry (from your Polygon MCP reference module)
#
# This is the surface the A2 job must compute (latest value only per output).
# --------------------------------------------------------------------------------------

INDICATOR_REGISTRY: Dict[str, Dict[str, Dict[str, Any]]] = {
    "momentum": {
        "awesome_oscillator": {
            "class": "AwesomeOscillatorIndicator",
            "module": "momentum",
            "description": "Awesome Oscillator - measures market momentum using 5 and 34 period SMAs of midpoint",
            "outputs": ["awesome_oscillator"],
            "required": ["high", "low"],
            "params": {"window1": 5, "window2": 34},
        },
        "kama": {
            "class": "KAMAIndicator",
            "module": "momentum",
            "description": "Kaufman's Adaptive Moving Average - adapts to market volatility",
            "outputs": ["kama"],
            "required": ["close"],
            "params": {"window": 10, "pow1": 2, "pow2": 30},
        },
        "ppo": {
            "class": "PercentagePriceOscillator",
            "module": "momentum",
            "description": "Percentage Price Oscillator - momentum oscillator measuring difference between EMAs",
            "outputs": ["ppo", "ppo_signal", "ppo_hist"],
            "required": ["close"],
            "params": {"window_slow": 26, "window_fast": 12, "window_sign": 9},
        },
        "pvo": {
            "class": "PercentageVolumeOscillator",
            "module": "momentum",
            "description": "Percentage Volume Oscillator - momentum oscillator for volume",
            "outputs": ["pvo", "pvo_signal", "pvo_hist"],
            "required": ["volume"],
            "params": {"window_slow": 26, "window_fast": 12, "window_sign": 9},
        },
        "roc": {
            "class": "ROCIndicator",
            "module": "momentum",
            "description": "Rate of Change - pure momentum oscillator measuring percent change",
            "outputs": ["roc"],
            "required": ["close"],
            "params": {"window": 12},
        },
        "rsi": {
            "class": "RSIIndicator",
            "module": "momentum",
            "description": "Relative Strength Index - measures overbought/oversold conditions",
            "outputs": ["rsi"],
            "required": ["close"],
            "params": {"window": 14},
        },
        "stochrsi": {
            "class": "StochRSIIndicator",
            "module": "momentum",
            "description": "Stochastic RSI - combines stochastic oscillator with RSI",
            "outputs": ["stochrsi", "stochrsi_k", "stochrsi_d"],
            "required": ["close"],
            "params": {"window": 14, "smooth1": 3, "smooth2": 3},
        },
        "stoch": {
            "class": "StochasticOscillator",
            "module": "momentum",
            "description": "Stochastic Oscillator - shows closing price relative to high-low range",
            "outputs": ["stoch", "stoch_signal"],
            "required": ["high", "low", "close"],
            "params": {"window": 14, "smooth_window": 3},
        },
        "tsi": {
            "class": "TSIIndicator",
            "module": "momentum",
            "description": "True Strength Index - momentum oscillator based on double smoothing",
            "outputs": ["tsi"],
            "required": ["close"],
            "params": {"window_slow": 25, "window_fast": 13},
        },
        "ultimate_oscillator": {
            "class": "UltimateOscillator",
            "module": "momentum",
            "description": "Ultimate Oscillator - combines short, medium, and long-term momentum",
            "outputs": ["ultimate_oscillator"],
            "required": ["high", "low", "close"],
            "params": {"window1": 7, "window2": 14, "window3": 28, "weight1": 4.0, "weight2": 2.0, "weight3": 1.0},
        },
        "williams_r": {
            "class": "WilliamsRIndicator",
            "module": "momentum",
            "description": "Williams %R - momentum indicator showing overbought/oversold levels",
            "outputs": ["williams_r"],
            "required": ["high", "low", "close"],
            "params": {"lbp": 14},
        },
    },
    "volatility": {
        "atr": {
            "class": "AverageTrueRange",
            "module": "volatility",
            "description": "Average True Range - measures market volatility",
            "outputs": ["average_true_range"],
            "required": ["high", "low", "close"],
            "params": {"window": 14},
        },
        "bbands": {
            "class": "BollingerBands",
            "module": "volatility",
            "description": "Bollinger Bands - volatility bands placed above and below moving average",
            "outputs": [
                "bollinger_hband",
                "bollinger_lband",
                "bollinger_mavg",
                "bollinger_pband",
                "bollinger_wband",
                "bollinger_hband_indicator",
                "bollinger_lband_indicator",
            ],
            "required": ["close"],
            "params": {"window": 20, "window_dev": 2},
        },
        "donchian": {
            "class": "DonchianChannel",
            "module": "volatility",
            "description": "Donchian Channel - highest high and lowest low over n periods",
            "outputs": [
                "donchian_channel_hband",
                "donchian_channel_lband",
                "donchian_channel_mband",
                "donchian_channel_pband",
                "donchian_channel_wband",
            ],
            "required": ["high", "low", "close"],
            "params": {"window": 20},
        },
        "keltner": {
            "class": "KeltnerChannel",
            "module": "volatility",
            "description": "Keltner Channel - volatility-based envelope using ATR",
            "outputs": [
                "keltner_channel_hband",
                "keltner_channel_lband",
                "keltner_channel_mband",
                "keltner_channel_pband",
                "keltner_channel_wband",
                "keltner_channel_hband_indicator",
                "keltner_channel_lband_indicator",
            ],
            "required": ["high", "low", "close"],
            "params": {"window": 20, "window_atr": 10},
        },
        "ulcer_index": {
            "class": "UlcerIndex",
            "module": "volatility",
            "description": "Ulcer Index - measures downside risk/volatility",
            "outputs": ["ulcer_index"],
            "required": ["close"],
            "params": {"window": 14},
        },
    },
    "trend": {
        "adx": {
            "class": "ADXIndicator",
            "module": "trend",
            "description": "Average Directional Index - measures trend strength",
            "outputs": ["adx", "adx_pos", "adx_neg"],
            "required": ["high", "low", "close"],
            "params": {"window": 14},
        },
        "aroon": {
            "class": "AroonIndicator",
            "module": "trend",
            "description": "Aroon Indicator - identifies trend changes and strength",
            "outputs": ["aroon_up", "aroon_down", "aroon_indicator"],
            "required": ["high", "low"],
            "params": {"window": 25},
        },
        "cci": {
            "class": "CCIIndicator",
            "module": "trend",
            "description": "Commodity Channel Index - measures price deviation from average",
            "outputs": ["cci"],
            "required": ["high", "low", "close"],
            "params": {"window": 20, "constant": 0.015},
        },
        "dpo": {
            "class": "DPOIndicator",
            "module": "trend",
            "description": "Detrended Price Oscillator - removes trend to identify cycles",
            "outputs": ["dpo"],
            "required": ["close"],
            "params": {"window": 20},
        },
        "ema": {
            "class": "EMAIndicator",
            "module": "trend",
            "description": "Exponential Moving Average - weighted moving average",
            "outputs": ["ema_indicator"],
            "required": ["close"],
            "params": {"window": 14},
        },
        "ichimoku": {
            "class": "IchimokuIndicator",
            "module": "trend",
            "description": "Ichimoku Cloud - comprehensive trend indicator",
            "outputs": ["ichimoku_conversion_line", "ichimoku_base_line", "ichimoku_a", "ichimoku_b"],
            "required": ["high", "low"],
            "params": {"window1": 9, "window2": 26, "window3": 52},
        },
        "kst": {
            "class": "KSTIndicator",
            "module": "trend",
            "description": "Know Sure Thing - momentum oscillator based on ROC",
            "outputs": ["kst", "kst_sig", "kst_diff"],
            "required": ["close"],
            "params": {"roc1": 10, "roc2": 15, "roc3": 20, "roc4": 30, "window1": 10, "window2": 10, "window3": 10, "window4": 15, "nsig": 9},
        },
        "macd": {
            "class": "MACD",
            "module": "trend",
            "description": "Moving Average Convergence Divergence - trend-following momentum",
            "outputs": ["macd", "macd_signal", "macd_diff"],
            "required": ["close"],
            "params": {"window_slow": 26, "window_fast": 12, "window_sign": 9},
        },
        "mass_index": {
            "class": "MassIndex",
            "module": "trend",
            "description": "Mass Index - predicts trend reversals",
            "outputs": ["mass_index"],
            "required": ["high", "low"],
            "params": {"window_fast": 9, "window_slow": 25},
        },
        "psar": {
            "class": "PSARIndicator",
            "module": "trend",
            "description": "Parabolic SAR - stop and reverse indicator",
            "outputs": ["psar", "psar_up", "psar_down", "psar_up_indicator", "psar_down_indicator"],
            "required": ["high", "low", "close"],
            "params": {"step": 0.02, "max_step": 0.2},
        },
        # NOTE: SMAIndicator default output name is `sma_indicator` in `ta`,
        # but KapMan A2 contract requires explicit variants sma_14/20/50/200.
        "sma": {
            "class": "SMAIndicator",
            "module": "trend",
            "description": "Simple Moving Average - explicit window variants required by KapMan A2",
            "outputs": ["sma_14", "sma_20", "sma_50", "sma_200"],
            "required": ["close"],
            "params": {"windows": list(SMA_VARIANTS)},
        },
        "stc": {
            "class": "STCIndicator",
            "module": "trend",
            "description": "Schaff Trend Cycle - combines MACD with stochastic",
            "outputs": ["stc"],
            "required": ["close"],
            "params": {"window_slow": 50, "window_fast": 23, "cycle": 10, "smooth1": 3, "smooth2": 3},
        },
        "trix": {
            "class": "TRIXIndicator",
            "module": "trend",
            "description": "TRIX - rate of change of triple EMA",
            "outputs": ["trix"],
            "required": ["close"],
            "params": {"window": 15},
        },
        "vortex": {
            "class": "VortexIndicator",
            "module": "trend",
            "description": "Vortex Indicator - identifies trend direction and reversals",
            "outputs": ["vortex_indicator_pos", "vortex_indicator_neg", "vortex_indicator_diff"],
            "required": ["high", "low", "close"],
            "params": {"window": 14},
        },
        "wma": {
            "class": "WMAIndicator",
            "module": "trend",
            "description": "Weighted Moving Average - linearly weighted average",
            "outputs": ["wma"],
            "required": ["close"],
            "params": {"window": 9},
        },
    },
    "volume": {
        "adi": {
            "class": "AccDistIndexIndicator",
            "module": "volume",
            "description": "Accumulation/Distribution Index - volume-based indicator",
            "outputs": ["acc_dist_index"],
            "required": ["high", "low", "close", "volume"],
            "params": {},
        },
        "cmf": {
            "class": "ChaikinMoneyFlowIndicator",
            "module": "volume",
            "description": "Chaikin Money Flow - measures buying/selling pressure",
            "outputs": ["chaikin_money_flow"],
            "required": ["high", "low", "close", "volume"],
            "params": {"window": 20},
        },
        "eom": {
            "class": "EaseOfMovementIndicator",
            "module": "volume",
            "description": "Ease of Movement - relates price change to volume",
            "outputs": ["ease_of_movement", "sma_ease_of_movement"],
            "required": ["high", "low", "volume"],
            "params": {"window": 14},
        },
        "fi": {
            "class": "ForceIndexIndicator",
            "module": "volume",
            "description": "Force Index - measures force behind price movements",
            "outputs": ["force_index"],
            "required": ["close", "volume"],
            "params": {"window": 13},
        },
        "mfi": {
            "class": "MFIIndicator",
            "module": "volume",
            "description": "Money Flow Index - volume-weighted RSI",
            "outputs": ["money_flow_index"],
            "required": ["high", "low", "close", "volume"],
            "params": {"window": 14},
        },
        "nvi": {
            "class": "NegativeVolumeIndexIndicator",
            "module": "volume",
            "description": "Negative Volume Index - tracks price on down-volume days",
            "outputs": ["negative_volume_index"],
            "required": ["close", "volume"],
            "params": {},
        },
        "obv": {
            "class": "OnBalanceVolumeIndicator",
            "module": "volume",
            "description": "On Balance Volume - cumulative volume indicator",
            "outputs": ["on_balance_volume"],
            "required": ["close", "volume"],
            "params": {},
        },
        "vpt": {
            "class": "VolumePriceTrendIndicator",
            "module": "volume",
            "description": "Volume Price Trend - cumulative volume weighted by price change",
            "outputs": ["volume_price_trend"],
            "required": ["close", "volume"],
            "params": {},
        },
        "vwap": {
            "class": "VolumeWeightedAveragePrice",
            "module": "volume",
            "description": "Volume Weighted Average Price - average price weighted by volume",
            "outputs": ["volume_weighted_average_price"],
            "required": ["high", "low", "close", "volume"],
            "params": {"window": 14},
        },
    },
    "others": {
        "cr": {
            "class": "CumulativeReturnIndicator",
            "module": "others",
            "description": "Cumulative Return - total return over period",
            "outputs": ["cumulative_return"],
            "required": ["close"],
            "params": {},
        },
        "dlr": {
            "class": "DailyLogReturnIndicator",
            "module": "others",
            "description": "Daily Log Return - logarithmic daily returns",
            "outputs": ["daily_log_return"],
            "required": ["close"],
            "params": {},
        },
        "dr": {
            "class": "DailyReturnIndicator",
            "module": "others",
            "description": "Daily Return - simple daily returns",
            "outputs": ["daily_return"],
            "required": ["close"],
            "params": {},
        },
    },
}

# --------------------------------------------------------------------------------------
# TA-Lib candlestick pattern recognition surface (authoritative list from user)
# --------------------------------------------------------------------------------------

PATTERN_RECOGNITION_FUNCTIONS: Tuple[str, ...] = (
    "CDL2CROWS",
    "CDL3BLACKCROWS",
    "CDL3INSIDE",
    "CDL3LINESTRIKE",
    "CDL3OUTSIDE",
    "CDL3STARSINSOUTH",
    "CDL3WHITESOLDIERS",
    "CDLABANDONEDBABY",
    "CDLADVANCEBLOCK",
    "CDLBELTHOLD",
    "CDLBREAKAWAY",
    "CDLCLOSINGMARUBOZU",
    "CDLCONCEALBABYSWALL",
    "CDLCOUNTERATTACK",
    "CDLDARKCLOUDCOVER",
    "CDLDOJI",
    "CDLDOJISTAR",
    "CDLDRAGONFLYDOJI",
    "CDLENGULFING",
    "CDLEVENINGDOJISTAR",
    "CDLEVENINGSTAR",
    "CDLGAPSIDESIDEWHITE",
    "CDLGRAVESTONEDOJI",
    "CDLHAMMER",
    "CDLHANGINGMAN",
    "CDLHARAMI",
    "CDLHARAMICROSS",
    "CDLHIGHWAVE",
    "CDLHIKKAKE",
    "CDLHIKKAKEMOD",
    "CDLHOMINGPIGEON",
    "CDLIDENTICAL3CROWS",
    "CDLINNECK",
    "CDLINVERTEDHAMMER",
    "CDLKICKING",
    "CDLKICKINGBYLENGTH",
    "CDLLADDERBOTTOM",
    "CDLLONGLEGGEDDOJI",
    "CDLLONGLINE",
    "CDLMARUBOZU",
    "CDLMATCHINGLOW",
    "CDLMATHOLD",
    "CDLMORNINGDOJISTAR",
    "CDLMORNINGSTAR",
    "CDLONNECK",
    "CDLPIERCING",
    "CDLRICKSHAWMAN",
    "CDLRISEFALL3METHODS",
    "CDLSEPARATINGLINES",
    "CDLSHOOTINGSTAR",
    "CDLSHORTLINE",
    "CDLSPINNINGTOP",
    "CDLSTALLEDPATTERN",
    "CDLSTICKSANDWICH",
    "CDLTAKURI",
    "CDLTASUKIGAP",
    "CDLTHRUSTING",
    "CDLTRISTAR",
    "CDLUNIQUE3RIVER",
    "CDLUPSIDEGAP2CROWS",
    "CDLXSIDEGAP3METHODS",
)

def _camel_to_snake(name: str) -> str:
    """Convert CDLFOO to cdlfoo (simple lower) for JSON keys."""
    return name.lower()

PATTERN_RECOGNITION_OUTPUT_KEYS: Tuple[str, ...] = tuple(_camel_to_snake(n) for n in PATTERN_RECOGNITION_FUNCTIONS)


# --------------------------------------------------------------------------------------
# Helper functions for inventory / contract assertions
# --------------------------------------------------------------------------------------

def get_all_indicator_names() -> List[str]:
    names: List[str] = []
    for category in INDICATOR_REGISTRY.values():
        names.extend(category.keys())
    # pattern_recognition is represented separately
    names.append("pattern_recognition")
    return sorted(set(names))

def get_all_indicators_info() -> Dict[str, Any]:
    """Returns indicator metadata (descriptions, outputs, required columns, default params)."""
    result: Dict[str, Any] = {}
    total_outputs = 0
    for category, indicators in INDICATOR_REGISTRY.items():
        result[category] = {}
        for name, info in indicators.items():
            result[category][name] = {
                "description": info.get("description"),
                "outputs": info.get("outputs", []),
                "required_data": info.get("required", []),
                "default_params": info.get("params", {}),
            }
            total_outputs += len(info.get("outputs", []))
    # Add pattern recognition as contract info
    result["pattern_recognition"] = {
        "candlestick_patterns": {
            "description": "TA-Lib candlestick pattern recognition functions; integer outputs",
            "outputs": list(PATTERN_RECOGNITION_OUTPUT_KEYS),
            "required_data": ["open", "high", "low", "close"],
            "default_params": {},
        }
    }
    total_outputs += len(PATTERN_RECOGNITION_OUTPUT_KEYS)

    return {
        "total_indicators": sum(len(v) for v in INDICATOR_REGISTRY.values()) + 1,
        "total_outputs": total_outputs,
        "categories": result,
        "price_metrics": list(PRICE_METRICS_KEYS),
        "sma_variants": list(SMA_OUTPUT_KEYS),
    }


# --------------------------------------------------------------------------------------
# Optional computation helpers (useful for unit tests / reference)
#
# A2 production job may reuse these patterns but is not required to import this module.
# --------------------------------------------------------------------------------------

def compute_indicator_latest(df: pd.DataFrame, category: str, name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Compute a single indicator and return latest outputs as Python scalars (float/int) or None.
    For KapMan A2, failures should return None values, not raise.
    """
    if ta_lib is None:
        return {"error": "ta library not available", "outputs": {k: None for k in INDICATOR_REGISTRY.get(category, {}).get(name, {}).get("outputs", [])}}

    info = INDICATOR_REGISTRY.get(category, {}).get(name)
    if not info:
        return {"error": f"Unknown indicator: {category}.{name}", "outputs": {}}

    # SMA variants are handled explicitly (not via method names).
    if category == "trend" and name == "sma":
        out: Dict[str, Any] = {}
        for w in info["params"]["windows"]:
            key = f"sma_{w}"
            try:
                module = getattr(ta_lib, info["module"])
                klass = getattr(module, info["class"])
                ind = klass(close=df["close"], window=int(w))
                series = ind.sma_indicator()
                val = series.iloc[-1] if len(series) else None
                out[key] = float(val) if pd.notna(val) else None
            except Exception:
                out[key] = None
        return {"outputs": out}

    module = getattr(ta_lib, info["module"])
    klass = getattr(module, info["class"])

    final_params = dict(info.get("params", {}))
    if params:
        final_params.update(params)

    kwargs: Dict[str, Any] = {}
    for req in info.get("required", []):
        if req not in df.columns:
            # missing input column; return nulls for outputs
            return {"outputs": {k: None for k in info.get("outputs", [])}}
        kwargs[req] = df[req]
    kwargs.update(final_params)

    out: Dict[str, Any] = {}
    try:
        indicator = klass(**kwargs)
        for output_name in info.get("outputs", []):
            method = getattr(indicator, output_name, None)
            if callable(method):
                series = method()
                if series is not None and len(series) > 0:
                    val = series.iloc[-1]
                    out[output_name] = float(val) if pd.notna(val) else None
                else:
                    out[output_name] = None
            else:
                out[output_name] = None
        return {"outputs": out}
    except Exception:
        return {"outputs": {k: None for k in info.get("outputs", [])}}

def compute_pattern_recognition_latest(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute TA-Lib candlestick patterns (latest value only).
    Outputs are ints (or None).
    """
    out: Dict[str, Any] = {k: None for k in PATTERN_RECOGNITION_OUTPUT_KEYS}
    if talib is None:
        return out

    # Validate required columns
    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            return out

    o = df["open"].astype(float).values
    h = df["high"].astype(float).values
    l = df["low"].astype(float).values
    c = df["close"].astype(float).values

    for func_name in PATTERN_RECOGNITION_FUNCTIONS:
        key = _camel_to_snake(func_name)
        func = getattr(talib, func_name, None)
        if func is None:
            out[key] = None
            continue
        try:
            series = func(o, h, l, c)
            if series is not None and len(series) > 0:
                val = series[-1]
                out[key] = int(val) if val is not None else None
            else:
                out[key] = None
        except Exception:
            out[key] = None
    return out
