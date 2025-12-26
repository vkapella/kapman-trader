"""
Metric normalization and composite scoring functions.
"""
import numpy as np


def normalize_zscore(values, window=252, min_periods=30):
    """Z-score normalization with fallback for low sample count."""
    if not isinstance(values, (list, tuple)):
        values = [values]
    if len(values) < min_periods:
        return 0
    arr = np.array(values[-window:])
    return float((arr[-1] - arr.mean()) / (arr.std() or 1))


def normalize_0_to_1(value, min_val, max_val):
    """Normalize value to 0-1 range with bounds checking."""
    if max_val == min_val:
        return 0.5
    normalized = (value - min_val) / (max_val - min_val)
    return float(max(0.0, min(1.0, normalized)))


def normalize_dealer_metric(key, value, underlying_price=None):
    """Apply appropriate normalization to dealer positioning metrics."""
    
    if key in ["DGPI", "OI_Ratio"]:
        return float(value)
    
    if key in ["rsi_rsi", "adx_ADX_14", "adx_ADXR_14_2"]:
        return normalize_0_to_1(value, 0, 100)
    
    if underlying_price and key in ["Gamma_Flip", "Call_Wall", "Put_Wall"]:
        distance_pct = abs(value - underlying_price) / underlying_price * 100
        return normalize_0_to_1(distance_pct, 0, 20)
    
    if key in ["GEX", "Net_GEX"]:
        if abs(value) < 1e6:
            return 0.5
        sign = np.sign(value)
        log_magnitude = np.log10(abs(value))
        if sign > 0:
            return 0.5 + normalize_0_to_1(log_magnitude, 6, 12) * 0.5
        else:
            return 0.5 - normalize_0_to_1(log_magnitude, 6, 12) * 0.5
    
    if key == "GEX_Slope":
        if abs(value) < 1e6:
            return 0.5
        sign = np.sign(value)
        log_magnitude = np.log10(abs(value))
        if sign > 0:
            return 0.5 + normalize_0_to_1(log_magnitude, 6, 10) * 0.5
        else:
            return 0.5 - normalize_0_to_1(log_magnitude, 6, 10) * 0.5
    
    if key in ["IV_Skew", "Historical_Volatility"]:
        return normalize_0_to_1(value, 0, 100)
    
    if key == "Expected_Move":
        return normalize_0_to_1(value, 0, 50)
    
    if key.startswith("macd_"):
        return normalize_0_to_1(value, -10, 10)
    
    if key in ["Relative_Volume", "Volume_Surge_Index"]:
        return normalize_0_to_1(value, 0, 3)
    
    if key in ["sma_sma", "ema_ema"]:
        return float(value)
    
    return float(value)


def normalize_metrics(metrics, cfg):
    """Apply intelligent normalization based on metric type."""
    normed = {}
    raw = {}
    skip_keys = {"symbol", "metadata", "filters", "rate_limiter", "timestamp"}
    
    underlying_price = metrics.get("underlying_price", None)
    
    for k, v in metrics.items():
        if k in skip_keys:
            continue
        
        if isinstance(v, (int, float)):
            numeric_val = float(v)
        elif isinstance(v, list):
            if len(v) > 0 and all(isinstance(x, (int, float)) for x in v):
                numeric_val = float(v[-1])
            elif len(v) > 0:
                numeric_val = float(v[0]) if isinstance(v[0], (int, float)) else 0
            else:
                numeric_val = 0
        elif v is None:
            numeric_val = 0
        else:
            continue
        
        raw[k] = numeric_val
        normed[k] = normalize_dealer_metric(k, numeric_val, underlying_price)
    
    normed["_raw"] = raw
    
    return normed


def composite_score(metrics, weights, render_type):
    """Weighted composite score of normalized metrics."""
    w = weights["weights"]
    score = sum(metrics.get(k, 0) * w.get(k, 0) for k in w)
    return float(score * weights["render_weight"].get(render_type, 1.0))
