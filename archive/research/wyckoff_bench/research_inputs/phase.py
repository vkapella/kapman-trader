"""
Wyckoff phase classification, volatility analysis, and confidence scoring.
"""


def adjust_thresholds_for_volatility(base_thresholds, hv, volatility_regimes):
    """
    Adjust RSI/ADX thresholds based on volatility regime (v1.3.0).
    
    Logic:
    - High volatility: Widen RSI bands (RSI can stay extreme longer)
    - Low volatility: Narrow RSI bands (more sensitive to moves)
    - Medium volatility: Use base thresholds unchanged
    
    Returns adjusted thresholds dict.
    """
    adjusted = {}
    
    is_high_vol = hv > volatility_regimes.get("high", {}).get("min", 30)
    is_low_vol = hv < volatility_regimes.get("low", {}).get("max", 15)
    
    for phase, threshold in base_thresholds.items():
        rsi_min = threshold["rsi_range"]["min"]
        rsi_max = threshold["rsi_range"]["max"]
        
        if is_high_vol:
            if phase == "A":
                rsi_max = min(100, rsi_max + 10)
            elif phase == "E":
                rsi_min = max(0, rsi_min - 10)
            elif phase == "C":
                rsi_min = max(0, rsi_min - 5)
                rsi_max = min(100, rsi_max + 5)
                
        elif is_low_vol:
            if phase == "A":
                rsi_max = max(rsi_min + 5, rsi_max - 5)
            elif phase == "E":
                rsi_min = min(rsi_max - 5, rsi_min + 5)
            elif phase == "C":
                rsi_min = min(50, rsi_min + 3)
                rsi_max = max(50, rsi_max - 3)
        
        adjusted[phase] = {
            "rsi_range": {"min": rsi_min, "max": rsi_max},
            "adx_range": threshold["adx_range"],
            "description": threshold["description"]
        }
    
    return adjusted


def calculate_phase_confidence(rsi, adx, classified_phase, thresholds, gex_slope=None):
    """
    Calculate 0-1 confidence score for phase classification (v1.3.0).
    
    Based on:
    - Distance from threshold boundaries (center of range = high confidence)
    - Dealer metric agreement (e.g., Phase C expects neutral GEX_Slope)
    - ADX strength consistency with phase
    
    Returns: float 0-1 (higher = more confident)
    """
    if classified_phase not in thresholds:
        return 0.5
    
    phase_thresh = thresholds[classified_phase]
    
    rsi_min = phase_thresh["rsi_range"]["min"]
    rsi_max = phase_thresh["rsi_range"]["max"]
    rsi_center = (rsi_min + rsi_max) / 2
    rsi_range_width = rsi_max - rsi_min
    
    if rsi_range_width > 0:
        rsi_distance = abs(rsi - rsi_center) / (rsi_range_width / 2)
        rsi_confidence = max(0.0, 1.0 - rsi_distance)
    else:
        rsi_confidence = 0.5
    
    adx_min = phase_thresh["adx_range"]["min"]
    adx_max = phase_thresh["adx_range"]["max"]
    
    if adx_min <= adx <= adx_max:
        adx_range_width = adx_max - adx_min
        if adx_range_width > 0:
            adx_distance = min(abs(adx - adx_min), abs(adx - adx_max)) / (adx_range_width / 2)
            adx_confidence = max(0.5, 1.0 - adx_distance * 0.5)
        else:
            adx_confidence = 1.0
    else:
        adx_confidence = 0.3
    
    dealer_confidence = 0.8
    
    if gex_slope is not None:
        if classified_phase == "C":
            dealer_confidence = 1.0 - abs(gex_slope - 0.5) * 2
        elif classified_phase in ["B", "D"]:
            dealer_confidence = gex_slope if gex_slope > 0.5 else 0.5
        elif classified_phase in ["A", "E"]:
            dealer_confidence = 0.8
    
    confidence = (rsi_confidence * 0.4 + adx_confidence * 0.3 + dealer_confidence * 0.3)
    return float(max(0.0, min(1.0, confidence)))


def detect_macd_signal(macd_line, macd_signal, macd_hist, rsi=None):
    """
    Detect MACD momentum signals (v1.4.0).
    
    Returns bullish/bearish/neutral based on:
    - MACD line vs Signal line (crossover detection)
    - MACD histogram momentum (increasing/decreasing)
    - RSI confirmation (optional)
    
    Args:
        macd_line: MACD line value (normalized 0-1, or raw)
        macd_signal: MACD signal line value
        macd_hist: MACD histogram value
        rsi: Optional RSI value for confirmation (0-100 scale)
    
    Returns:
        str: "bullish", "bearish", "neutral", or "n/a"
    """
    if macd_line is None or macd_signal is None or macd_hist is None:
        return "n/a"
    
    bullish_signals = 0
    bearish_signals = 0
    
    if macd_line > macd_signal:
        bullish_signals += 1
    elif macd_line < macd_signal:
        bearish_signals += 1
    
    if macd_hist > 0.5:
        bullish_signals += 1
    elif macd_hist < 0.5:
        bearish_signals += 1
    
    if rsi is not None:
        if rsi > 50:
            bullish_signals += 0.5
        elif rsi < 50:
            bearish_signals += 0.5
    
    if bullish_signals >= 2:
        return "bullish"
    elif bearish_signals >= 2:
        return "bearish"
    else:
        return "neutral"


def classify_phase(rsi, adx, thresholds, gex_slope=None, gamma_flip=None, price=None, net_gex=None):
    """
    Enhanced Wyckoff phase classification with dealer positioning integration.
    
    Dealer positioning modifiers:
    - GEX_Slope > 0: Dealers long gamma, dampens volatility → favors consolidation
    - GEX_Slope < 0: Dealers short gamma, amplifies volatility → favors trend phases
    - Price above Gamma_Flip: Bullish positioning → favors markup
    - Price below Gamma_Flip: Bearish positioning → favors markdown/accumulation
    - Net_GEX > 0: Call-heavy → bullish bias
    - Net_GEX < 0: Put-heavy → bearish bias
    """
    
    base_phase = None
    base_desc = None
    for phase, t in thresholds.items():
        if t["rsi_range"]["min"] <= rsi <= t["rsi_range"]["max"] and \
           t["adx_range"]["min"] <= adx <= t["adx_range"]["max"]:
            base_phase = phase
            base_desc = t["description"]
            break
    
    if not base_phase:
        base_phase = "C"
        base_desc = "Consolidation - Neutral zone"
    
    if gex_slope is not None and gamma_flip is not None and price is not None:
        
        dealers_long_gamma = gex_slope > 0.5
        price_above_flip = price > gamma_flip
        
        if not dealers_long_gamma and adx > 0.25:
            if rsi > 0.6 and (price_above_flip or (net_gex and net_gex > 0)):
                return "B", "Markup - Strong uptrend with dealer amplification"
            elif rsi < 0.4 and (not price_above_flip or (net_gex and net_gex < 0)):
                return "E", "Markdown - Strong downtrend with dealer amplification"
        
        if price_above_flip == False and rsi < 0.4 and dealers_long_gamma:
            return "A", "Accumulation - Bottom formation, dealers stabilizing"
        
        if price_above_flip == True and rsi > 0.6 and dealers_long_gamma:
            return "D", "Distribution - Top formation, dealers stabilizing"
        
        if dealers_long_gamma and adx < 0.2:
            return "C", "Consolidation - Range-bound, dealers suppressing volatility"
        
        if base_desc:
            if dealers_long_gamma:
                base_desc += " (dealers long gamma, volatility dampened)"
            else:
                base_desc += " (dealers short gamma, volatility amplified)"
    
    return base_phase, base_desc if base_desc else "Unknown phase"


def classify_volatility(hv, regimes):
    """Classify volatility regime based on historical volatility."""
    for reg, b in regimes.items():
        if "max" in b and hv <= b["max"]:
            return reg
        if "min" in b and hv >= b["min"] and ("max" not in b or hv <= b["max"]):
            return reg
    return "medium"
