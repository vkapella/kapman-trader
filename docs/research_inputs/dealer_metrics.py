"""
Dealer Metrics Module

Schwab-equivalent dealer positioning metrics from options data:
- Gamma Exposure (GEX)
- Net GEX
- Gamma Flip Level
- Call/Put Walls
- GEX Slope
- Dealer Gamma Pressure Index (DGPI)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import math


@dataclass
class OptionContract:
    """Represents a single options contract for dealer metrics calculation."""
    strike: float
    contract_type: str  # 'call' or 'put'
    gamma: Optional[float] = None
    delta: Optional[float] = None
    open_interest: int = 0
    volume: int = 0
    iv: Optional[float] = None
    dte: int = 30


@dataclass
class DealerMetrics:
    """Container for all dealer metrics results."""
    gamma_exposure: Optional[float] = None
    net_gex: Optional[float] = None
    gamma_flip: Optional[float] = None
    call_walls: List[Dict[str, Any]] = field(default_factory=list)
    put_walls: List[Dict[str, Any]] = field(default_factory=list)
    gex_slope: Optional[float] = None
    dealer_gamma_pressure_index: Optional[float] = None
    position: str = "unknown"  # 'long_gamma', 'short_gamma', 'neutral', 'unknown'
    confidence: str = "low"  # 'high', 'medium', 'low', 'invalid'
    metadata: Optional[Dict[str, Any]] = None


def calculate_contract_gex(contract: OptionContract, spot: float, contract_multiplier: int = 100) -> float:
    """
    Calculate Gamma Exposure for a single contract.
    
    GEX = Gamma * Open Interest * Spot^2 * 0.01 * Contract Multiplier
    
    Dealers are typically short options, so:
    - Short calls = negative gamma exposure
    - Short puts = positive gamma exposure
    
    Args:
        contract: OptionContract with gamma and OI
        spot: Current underlying price
        contract_multiplier: Options multiplier (usually 100)
        
    Returns:
        GEX value for this contract
    """
    if contract.gamma is None or contract.open_interest <= 0:
        return 0.0
    
    # Base GEX calculation
    gex = contract.gamma * contract.open_interest * (spot ** 2) * 0.01 * contract_multiplier
    
    # Dealers are typically short options
    # Short calls = dealers have negative gamma (they lose when price moves)
    # Short puts = dealers have positive gamma (they gain when price moves)
    if contract.contract_type.lower() == 'call':
        gex = -gex  # Dealers short calls = negative gamma
    # Puts stay positive (dealers short puts = positive gamma, but put gamma is already negative)
    
    return gex


def calculate_strike_gex(contracts: List[OptionContract], spot: float) -> Dict[float, float]:
    """
    Calculate total GEX per strike price.
    
    Args:
        contracts: List of option contracts
        spot: Current underlying price
        
    Returns:
        Dictionary mapping strike -> total GEX at that strike
    """
    strike_gex = {}
    
    for contract in contracts:
        gex = calculate_contract_gex(contract, spot)
        strike = contract.strike
        
        if strike in strike_gex:
            strike_gex[strike] += gex
        else:
            strike_gex[strike] = gex
    
    return strike_gex


def find_gamma_flip(strike_gex: Dict[float, float]) -> Optional[float]:
    """
    Find the gamma flip level - where cumulative GEX crosses zero.
    
    This is the price level where dealers switch from long to short gamma.
    
    Args:
        strike_gex: Dictionary of strike -> GEX values
        
    Returns:
        Gamma flip strike price or None if not found
    """
    if not strike_gex:
        return None
    
    # Sort strikes
    sorted_strikes = sorted(strike_gex.keys())
    
    # Calculate cumulative GEX from lowest strike
    cumulative = 0.0
    prev_strike = None
    prev_cumulative = None
    
    for strike in sorted_strikes:
        cumulative += strike_gex[strike]
        
        # Check for zero crossing
        if prev_cumulative is not None:
            if (prev_cumulative < 0 and cumulative >= 0) or (prev_cumulative > 0 and cumulative <= 0):
                # Interpolate the flip point
                if cumulative != prev_cumulative:
                    ratio = abs(prev_cumulative) / abs(cumulative - prev_cumulative)
                    flip = prev_strike + ratio * (strike - prev_strike)
                    return round(flip, 2)
        
        prev_strike = strike
        prev_cumulative = cumulative
    
    return None


def find_walls(contracts: List[OptionContract], contract_type: str, top_n: int = 3) -> List[Dict[str, Any]]:
    """
    Find top N strikes with highest open interest for given contract type.
    
    These represent support (put walls) and resistance (call walls) levels.
    
    Args:
        contracts: List of option contracts
        contract_type: 'call' or 'put'
        top_n: Number of walls to return
        
    Returns:
        List of dicts with strike and open_interest
    """
    filtered = [c for c in contracts if c.contract_type.lower() == contract_type.lower() and c.open_interest > 0]
    
    # Sort by open interest descending
    sorted_contracts = sorted(filtered, key=lambda c: c.open_interest, reverse=True)
    
    walls = []
    for c in sorted_contracts[:top_n]:
        walls.append({
            "strike": c.strike,
            "open_interest": c.open_interest,
            "volume": c.volume
        })
    
    return walls


def calculate_gex_slope(strike_gex: Dict[float, float], spot: float, range_pct: float = 0.02) -> Optional[float]:
    """
    Calculate GEX slope - rate of change of GEX with respect to price.
    
    Positive slope = GEX increases as price rises (stabilizing)
    Negative slope = GEX decreases as price rises (destabilizing)
    
    Args:
        strike_gex: Dictionary of strike -> GEX values
        spot: Current underlying price
        range_pct: Percentage range to calculate slope (default 2%)
        
    Returns:
        GEX slope or None if insufficient data
    """
    if not strike_gex or spot <= 0:
        return None
    
    lower_bound = spot * (1 - range_pct)
    upper_bound = spot * (1 + range_pct)
    
    # Sum GEX in lower and upper ranges
    lower_gex = sum(gex for strike, gex in strike_gex.items() if lower_bound <= strike < spot)
    upper_gex = sum(gex for strike, gex in strike_gex.items() if spot <= strike <= upper_bound)
    
    # Slope is change in GEX per unit price
    price_range = upper_bound - lower_bound
    if price_range <= 0:
        return None
    
    slope = (upper_gex - lower_gex) / price_range
    return round(slope, 4)


def calculate_dgpi(net_gex: float, gex_slope: Optional[float], iv_rank: Optional[float] = None) -> Optional[float]:
    """
    Calculate Dealer Gamma Pressure Index (DGPI).
    
    Combines net GEX direction with slope and optionally IV rank.
    Output is bounded to [-100, 100] for consistent interpretation.
    
    DGPI > 0 = Bullish pressure (dealers hedging supports price)
    DGPI < 0 = Bearish pressure (dealers hedging pressures price)
    
    Interpretation scale:
    - |DGPI| < 10: Low dealer pressure
    - |DGPI| 10-30: Moderate dealer pressure
    - |DGPI| 30-60: Significant dealer pressure
    - |DGPI| > 60: Extreme dealer pressure
    
    Args:
        net_gex: Net gamma exposure
        gex_slope: GEX slope value
        iv_rank: Optional IV rank (0-100) for weighting
        
    Returns:
        DGPI value bounded to [-100, 100] or None if insufficient data
    """
    if net_gex is None:
        return None
    
    # Base DGPI is normalized net GEX using log scaling
    # This normalizes across different market cap tickers
    if net_gex == 0:
        base_dgpi = 0.0
    else:
        sign = 1 if net_gex > 0 else -1
        # Log10 scaling with adjustment to get reasonable range
        # GEX of 1M -> ~6, GEX of 1B -> ~9, etc.
        base_dgpi = sign * math.log10(abs(net_gex) + 1) * 10
    
    # Adjust by slope if available (small multiplier)
    if gex_slope is not None and gex_slope != 0:
        # Clamp slope effect to avoid extreme values
        slope_effect = max(-0.3, min(0.3, gex_slope * 0.01))
        base_dgpi *= (1 + slope_effect)
    
    # Weight by IV rank if available (high IV = more significant)
    if iv_rank is not None:
        iv_weight = 0.7 + (iv_rank / 333)  # Range: 0.7 to 1.0
        base_dgpi *= iv_weight
    
    # Bound output to [-100, 100] for consistent interpretation
    bounded_dgpi = max(-100, min(100, base_dgpi))
    
    return round(bounded_dgpi, 2)


def determine_position(net_gex: float, threshold: float = 1000000) -> str:
    """
    Determine dealer positioning based on net GEX.
    
    Args:
        net_gex: Net gamma exposure
        threshold: Threshold for significant positioning
        
    Returns:
        Position string: 'long_gamma', 'short_gamma', 'neutral'
    """
    if abs(net_gex) < threshold:
        return "neutral"
    elif net_gex > 0:
        return "long_gamma"
    else:
        return "short_gamma"


def determine_confidence(contracts: List[OptionContract], min_contracts: int = 10, min_oi: int = 1000) -> str:
    """
    Determine confidence level of the metrics based on data quality.
    
    Args:
        contracts: List of option contracts
        min_contracts: Minimum contracts for medium confidence
        min_oi: Minimum total OI for high confidence
        
    Returns:
        Confidence string: 'high', 'medium', 'low', 'invalid'
    """
    if not contracts:
        return "invalid"
    
    total_oi = sum(c.open_interest for c in contracts)
    contracts_with_gamma = sum(1 for c in contracts if c.gamma is not None)
    
    if contracts_with_gamma < 5:
        return "invalid"
    elif contracts_with_gamma >= min_contracts and total_oi >= min_oi:
        return "high"
    elif contracts_with_gamma >= min_contracts // 2:
        return "medium"
    else:
        return "low"


def calculate_dealer_metrics(
    contracts: List[OptionContract],
    spot: float,
    iv: Optional[float] = None,
    dte: Optional[int] = None,
    iv_rank: Optional[float] = None
) -> DealerMetrics:
    """
    Calculate all dealer metrics from options chain data.
    
    Args:
        contracts: List of OptionContract objects with Greeks and OI
        spot: Current underlying price
        iv: Optional implied volatility for expected move
        dte: Optional days to expiration for expected move
        iv_rank: Optional IV rank (0-100) for DGPI calculation
        
    Returns:
        DealerMetrics object with all calculated values
    """
    if not contracts or spot <= 0:
        return DealerMetrics(confidence="invalid")
    
    # Calculate per-strike GEX
    strike_gex = calculate_strike_gex(contracts, spot)
    
    if not strike_gex:
        return DealerMetrics(confidence="invalid")
    
    # Total and net GEX
    gamma_exposure = sum(abs(gex) for gex in strike_gex.values())
    net_gex = sum(strike_gex.values())
    
    # Gamma flip level
    gamma_flip = find_gamma_flip(strike_gex)
    
    # Call and put walls
    call_walls = find_walls(contracts, "call", top_n=3)
    put_walls = find_walls(contracts, "put", top_n=3)
    
    # GEX slope
    gex_slope = calculate_gex_slope(strike_gex, spot)
    
    # DGPI
    dgpi = calculate_dgpi(net_gex, gex_slope, iv_rank)
    
    # Position and confidence
    position = determine_position(net_gex)
    confidence = determine_confidence(contracts)
    
    # Metadata
    metadata = {
        "contracts_analyzed": len(contracts),
        "contracts_with_gamma": sum(1 for c in contracts if c.gamma is not None),
        "total_open_interest": sum(c.open_interest for c in contracts),
        "strikes_count": len(strike_gex),
        "spot_price": spot
    }
    
    return DealerMetrics(
        gamma_exposure=round(gamma_exposure, 2) if gamma_exposure else None,
        net_gex=round(net_gex, 2) if net_gex else None,
        gamma_flip=gamma_flip,
        call_walls=call_walls,
        put_walls=put_walls,
        gex_slope=gex_slope,
        dealer_gamma_pressure_index=dgpi,
        position=position,
        confidence=confidence,
        metadata=metadata
    )
