"""
Volatility Metrics Module

Schwab-equivalent volatility metrics from options data:
- IV Skew (25 Delta)
- IV Term Structure
- OI Ratio (Volume/Open Interest)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class OptionContractVol:
    """Represents a single options contract for volatility metrics calculation."""
    strike: float
    contract_type: str  # 'call' or 'put'
    delta: Optional[float] = None
    iv: Optional[float] = None
    dte: int = 30
    volume: int = 0
    open_interest: int = 0


def find_25_delta_iv(contracts: List[OptionContractVol], contract_type: str) -> Optional[float]:
    """
    Find the implied volatility at approximately 25 delta.
    
    25 delta options are commonly used for skew measurement because they
    represent a standardized out-of-the-money strike.
    
    Uses a fallback strategy:
    1. Try to find contract closest to 25 delta (within 15 delta tolerance)
    2. If no delta available, fallback to OTM options by strike distribution
    
    Args:
        contracts: List of option contracts
        contract_type: 'call' or 'put'
        
    Returns:
        IV at 25 delta or None if not found
    """
    type_lower = contract_type.lower()
    
    # Filter contracts of correct type with IV
    type_contracts = [
        c for c in contracts 
        if c.contract_type.lower() == type_lower 
        and c.iv is not None
    ]
    
    if not type_contracts:
        return None
    
    # Strategy 1: Use delta if available
    with_delta = [c for c in type_contracts if c.delta is not None]
    
    if with_delta:
        # Target delta: 0.25 for calls, -0.25 for puts
        target_delta = 0.25 if type_lower == 'call' else -0.25
        
        # Find the contract closest to 25 delta
        closest = min(with_delta, key=lambda c: abs(c.delta - target_delta))
        
        # Accept if within 15 delta (more lenient tolerance)
        if abs(closest.delta - target_delta) <= 0.15:
            return closest.iv
    
    # Strategy 2: Fallback to approximate 25% OTM by strike distribution
    # Sort strikes and pick ~25% percentile for puts (low strikes), 75% for calls (high strikes)
    sorted_contracts = sorted(type_contracts, key=lambda c: c.strike)
    
    if len(sorted_contracts) >= 3:
        if type_lower == 'put':
            # 25% OTM puts are low strikes
            idx = max(0, int(len(sorted_contracts) * 0.25))
        else:
            # 25% OTM calls are high strikes
            idx = min(len(sorted_contracts) - 1, int(len(sorted_contracts) * 0.75))
        return sorted_contracts[idx].iv
    
    # Last resort: return median IV
    return sorted_contracts[len(sorted_contracts) // 2].iv


def calculate_iv_skew(contracts: List[OptionContractVol]) -> Optional[float]:
    """
    Calculate IV Skew: IV(25Δ put) - IV(25Δ call).
    
    Positive skew = Higher put IV (fear/hedging demand)
    Negative skew = Higher call IV (bullish speculation)
    
    Args:
        contracts: List of option contracts with delta and IV
        
    Returns:
        IV skew in percentage points or None if insufficient data
    """
    put_iv = find_25_delta_iv(contracts, "put")
    call_iv = find_25_delta_iv(contracts, "call")
    
    if put_iv is None or call_iv is None:
        return None
    
    # Return skew in percentage points
    skew = (put_iv - call_iv) * 100
    return round(skew, 2)


def calculate_iv_term_structure(contracts: List[OptionContractVol], short_dte: int = 30, long_dte: int = 90) -> Optional[float]:
    """
    Calculate IV Term Structure: IV(long-dated) - IV(short-dated).
    
    Positive = Backwardation (near-term IV higher than long-term)
    Negative = Contango (long-term IV higher than near-term)
    
    Note: This returns long_iv - short_iv, so:
    - Positive value = contango (normal)
    - Negative value = backwardation (inverted, often during crisis)
    
    Args:
        contracts: List of option contracts with DTE and IV
        short_dte: Target short-term DTE (default 30)
        long_dte: Target long-term DTE (default 90)
        
    Returns:
        Term structure in percentage points or None if insufficient data
    """
    # Filter contracts with valid IV
    valid_contracts = [c for c in contracts if c.iv is not None]
    
    if not valid_contracts:
        return None
    
    # Find contracts closest to target DTEs
    short_term = [c for c in valid_contracts if abs(c.dte - short_dte) <= 15]
    long_term = [c for c in valid_contracts if abs(c.dte - long_dte) <= 30]
    
    if not short_term or not long_term:
        return None
    
    # Average IV for each term
    short_iv = sum(c.iv for c in short_term) / len(short_term)
    long_iv = sum(c.iv for c in long_term) / len(long_term)
    
    # Term structure in percentage points
    term_structure = (long_iv - short_iv) * 100
    return round(term_structure, 2)


def calculate_oi_ratio(contracts: List[OptionContractVol]) -> Optional[float]:
    """
    Calculate OI Ratio: Total Volume / Total Open Interest.
    
    Higher ratio = More speculative/trading activity relative to positions
    Lower ratio = More stable/hedging positions
    
    Args:
        contracts: List of option contracts
        
    Returns:
        OI ratio or None if no open interest
    """
    total_volume = sum(c.volume for c in contracts)
    total_oi = sum(c.open_interest for c in contracts)
    
    if total_oi <= 0:
        return None
    
    ratio = total_volume / total_oi
    return round(ratio, 4)


def calculate_put_call_ratio(contracts: List[OptionContractVol]) -> Optional[float]:
    """
    Calculate Put/Call Ratio by open interest.
    
    > 1.0 = More puts than calls (bearish sentiment)
    < 1.0 = More calls than puts (bullish sentiment)
    
    Args:
        contracts: List of option contracts
        
    Returns:
        Put/Call ratio or None if no call OI
    """
    put_oi = sum(c.open_interest for c in contracts if c.contract_type.lower() == 'put')
    call_oi = sum(c.open_interest for c in contracts if c.contract_type.lower() == 'call')
    
    if call_oi <= 0:
        return None
    
    ratio = put_oi / call_oi
    return round(ratio, 4)


def calculate_average_iv(contracts: List[OptionContractVol], weighted: bool = True) -> Optional[float]:
    """
    Calculate average implied volatility across all contracts.
    
    Args:
        contracts: List of option contracts
        weighted: If True, weight by open interest
        
    Returns:
        Average IV as decimal or None if no data
    """
    valid = [c for c in contracts if c.iv is not None]
    
    if not valid:
        return None
    
    if weighted:
        total_oi = sum(c.open_interest for c in valid)
        if total_oi <= 0:
            # Fall back to simple average
            return sum(c.iv for c in valid) / len(valid)
        weighted_iv = sum(c.iv * c.open_interest for c in valid) / total_oi
        return round(weighted_iv, 4)
    else:
        return round(sum(c.iv for c in valid) / len(valid), 4)


def calculate_volatility_metrics(
    contracts: List[OptionContractVol],
    spot: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate all volatility metrics from options chain data.
    
    Args:
        contracts: List of OptionContractVol objects with Greeks, IV, and OI
        spot: Optional current underlying price (for ATM calculations)
        
    Returns:
        Dictionary with all volatility metrics
    """
    if not contracts:
        return {
            "iv_skew": None,
            "iv_term_structure": None,
            "oi_ratio": None,
            "put_call_ratio": None,
            "average_iv": None
        }
    
    return {
        "iv_skew": calculate_iv_skew(contracts),
        "iv_term_structure": calculate_iv_term_structure(contracts),
        "oi_ratio": calculate_oi_ratio(contracts),
        "put_call_ratio": calculate_put_call_ratio(contracts),
        "average_iv": calculate_average_iv(contracts)
    }
