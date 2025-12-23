from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class OptionContractVol:
    """Lightweight representation of an options contract for volatility metrics."""

    strike: float
    contract_type: str  # "call" or "put"
    delta: Optional[float]
    iv: Optional[float]
    dte: Optional[int]
    volume: int
    open_interest: int


def calculate_average_iv(contracts: Iterable[OptionContractVol], weighted: bool = True) -> Optional[float]:
    """Return the average IV across contracts, weighting by OI when possible."""
    valid = [c for c in contracts if c.iv is not None]
    if not valid:
        return None

    if weighted:
        total_oi = sum(c.open_interest for c in valid)
        if total_oi > 0:
            weighted_iv = sum(c.iv * c.open_interest for c in valid) / total_oi
            return round(weighted_iv, 4)
    # fallback to unweighted average
    return round(mean(c.iv for c in valid), 4)


def calculate_put_call_ratio(contracts: Iterable[OptionContractVol]) -> Optional[float]:
    put_oi = sum(c.open_interest for c in contracts if c.contract_type == "put")
    call_oi = sum(c.open_interest for c in contracts if c.contract_type == "call")
    if call_oi <= 0:
        return None
    return round(put_oi / call_oi, 4)


def calculate_oi_ratio(contracts: Iterable[OptionContractVol]) -> Optional[float]:
    total_volume = sum(c.volume for c in contracts)
    total_open_interest = sum(c.open_interest for c in contracts)
    if total_open_interest <= 0:
        return None
    return round(total_volume / total_open_interest, 4)


def _find_25_delta_iv(contracts: Iterable[OptionContractVol], contract_type: str) -> Optional[float]:
    """Find the IV closest to a 25 delta contract for calls or puts."""
    normalized_type = contract_type.lower()
    target_delta = 0.25 if normalized_type == "call" else -0.25
    candidates = [c for c in contracts if c.contract_type == normalized_type and c.iv is not None]
    if not candidates:
        return None

    with_delta = [c for c in candidates if c.delta is not None]
    if with_delta:
        closest = min(with_delta, key=lambda c: abs((c.delta or 0.0) - target_delta))
        if abs((closest.delta or 0.0) - target_delta) <= 0.15:
            return closest.iv

    sorted_by_strike = sorted(candidates, key=lambda c: c.strike)
    if not sorted_by_strike:
        return None

    if len(sorted_by_strike) >= 3:
        if normalized_type == "put":
            idx = max(0, int(len(sorted_by_strike) * 0.25))
        else:
            idx = min(len(sorted_by_strike) - 1, int(len(sorted_by_strike) * 0.75))
        return sorted_by_strike[idx].iv

    return sorted_by_strike[len(sorted_by_strike) // 2].iv


def calculate_iv_skew(contracts: Iterable[OptionContractVol]) -> Optional[float]:
    put_iv = _find_25_delta_iv(contracts, "put")
    call_iv = _find_25_delta_iv(contracts, "call")
    if put_iv is None or call_iv is None:
        return None
    skew = (put_iv - call_iv) * 100
    return round(skew, 2)


def calculate_iv_term_structure(
    contracts: Iterable[OptionContractVol], *, short_dte: int = 30, long_dte: int = 90
) -> Optional[float]:
    def _avg_for_target(target: int, tolerance: int) -> Optional[float]:
        matches = [
            c.iv
            for c in contracts
            if c.iv is not None and c.dte is not None and c.dte >= 0 and abs(c.dte - target) <= tolerance
        ]
        if not matches:
            return None
        return mean(matches)

    short_iv = _avg_for_target(short_dte, tolerance=15)
    long_iv = _avg_for_target(long_dte, tolerance=30)
    if short_iv is None or long_iv is None:
        return None
    term_structure = (long_iv - short_iv) * 100
    return round(term_structure, 2)


def calculate_iv_rank(
    current_average_iv: Optional[float],
    history: Iterable[Optional[float]],
    min_history_points: int = 20,
) -> Optional[float]:
    if current_average_iv is None:
        return None
    history_values = [h for h in history if h is not None]
    if len(history_values) < min_history_points:
        return None
    iv_min = min(history_values)
    iv_max = max(history_values)
    if iv_max == iv_min:
        return None
    rank = (current_average_iv - iv_min) / (iv_max - iv_min) * 100.0
    rank = max(0.0, min(100.0, rank))
    return round(rank, 2)
