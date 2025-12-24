from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Iterable, List, Optional, Sequence, Tuple, Dict

DEFAULT_SHORT_DTE = 30
DEFAULT_LONG_DTE = 90
DEFAULT_SHORT_TOLERANCE = 15
DEFAULT_LONG_TOLERANCE = 30
DEFAULT_MIN_HISTORY_POINTS = 20


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


def calculate_average_iv(contracts: Iterable[OptionContractVol], *, weighted: bool = True) -> Optional[float]:
    """Return the average IV across contracts, weighting by OI when possible."""
    values = [c for c in contracts if c.iv is not None]
    if not values:
        return None

    if weighted:
        total_oi = sum(c.open_interest for c in values)
        if total_oi > 0:
            weighted_iv = sum(c.iv * c.open_interest for c in values) / total_oi
            return round(weighted_iv, 4)
    return round(mean(c.iv for c in values), 4)


def calculate_put_call_oi_ratio(contracts: Iterable[OptionContractVol]) -> Optional[float]:
    put_oi = sum(c.open_interest for c in contracts if c.contract_type == "put")
    call_oi = sum(c.open_interest for c in contracts if c.contract_type == "call")
    if call_oi <= 0:
        return None
    return round(put_oi / call_oi, 4)


def calculate_put_call_ratio(contracts: Iterable[OptionContractVol]) -> Optional[float]:
    return calculate_put_call_oi_ratio(contracts)


def calculate_put_call_volume_ratio(contracts: Iterable[OptionContractVol]) -> Optional[float]:
    put_volume = sum(c.volume for c in contracts if c.contract_type == "put")
    call_volume = sum(c.volume for c in contracts if c.contract_type == "call")
    if call_volume <= 0:
        return None
    return round(put_volume / call_volume, 4)


def calculate_oi_ratio(contracts: Iterable[OptionContractVol]) -> Optional[float]:
    total_volume = sum(c.volume for c in contracts)
    total_open_interest = sum(c.open_interest for c in contracts)
    if total_open_interest <= 0:
        return None
    return round(total_volume / total_open_interest, 4)


def calculate_iv_stddev(contracts: Iterable[OptionContractVol]) -> Optional[float]:
    values = [c.iv for c in contracts if c.iv is not None]
    if not values:
        return None
    return round(pstdev(values), 4)


def _find_25_delta_iv(contracts: Iterable[OptionContractVol], contract_type: str) -> Optional[float]:
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


def calculate_iv_skew_call_put(avg_call_iv: Optional[float], avg_put_iv: Optional[float]) -> Optional[float]:
    if avg_call_iv is None or avg_put_iv is None:
        return None
    skew = (avg_put_iv - avg_call_iv) * 100
    return round(skew, 2)


def calculate_iv_term_structure(
    contracts: Iterable[OptionContractVol], *, short_dte: int = DEFAULT_SHORT_DTE, long_dte: int = DEFAULT_LONG_DTE
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

    short_iv = _avg_for_target(short_dte, tolerance=DEFAULT_SHORT_TOLERANCE)
    long_iv = _avg_for_target(long_dte, tolerance=DEFAULT_LONG_TOLERANCE)
    if short_iv is None or long_iv is None:
        return None
    term_structure = (long_iv - short_iv) * 100
    return round(term_structure, 2)


def calculate_front_month_iv(
    contracts: Iterable[OptionContractVol],
    *,
    short_dte: int = DEFAULT_SHORT_DTE,
    tolerance: int = DEFAULT_SHORT_TOLERANCE,
) -> Optional[float]:
    return _average_iv_for_dte_target(contracts, target=short_dte, tolerance=tolerance)


def calculate_back_month_iv(
    contracts: Iterable[OptionContractVol],
    *,
    long_dte: int = DEFAULT_LONG_DTE,
    tolerance: int = DEFAULT_LONG_TOLERANCE,
) -> Optional[float]:
    return _average_iv_for_dte_target(contracts, target=long_dte, tolerance=tolerance)


def _average_iv_for_dte_target(
    contracts: Iterable[OptionContractVol],
    *,
    target: int,
    tolerance: int,
) -> Optional[float]:
    matches = [
        c.iv
        for c in contracts
        if c.iv is not None and c.dte is not None and c.dte >= 0 and abs(c.dte - target) <= tolerance
    ]
    if not matches:
        return None
    return round(mean(matches), 4)


def calculate_iv_term_structure_slope(
    front_month_iv: Optional[float],
    back_month_iv: Optional[float],
    *,
    short_dte: int = DEFAULT_SHORT_DTE,
    long_dte: int = DEFAULT_LONG_DTE,
) -> Optional[float]:
    if front_month_iv is None or back_month_iv is None or long_dte == short_dte:
        return None
    slope = ((back_month_iv - front_month_iv) * 100.0) / (long_dte - short_dte)
    return round(slope, 2)


def calculate_iv_percentile(
    current_average_iv: Optional[float],
    history: Iterable[Optional[float]],
    *,
    min_history_points: int = DEFAULT_MIN_HISTORY_POINTS,
) -> Optional[float]:
    if current_average_iv is None:
        return None
    values = [h for h in history if h is not None]
    if len(values) < min_history_points:
        return None
    count = sum(1 for value in values if value <= current_average_iv)
    percentile = (count / len(values)) * 100.0
    percentile = max(0.0, min(100.0, percentile))
    return round(percentile, 2)


def calculate_iv_rank(
    current_average_iv: Optional[float],
    history: Iterable[Optional[float]],
    *,
    min_history_points: int = DEFAULT_MIN_HISTORY_POINTS,
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


@dataclass(frozen=True)
class VolatilityMetricsCounts:
    total_contracts: int
    contracts_with_iv: int
    call_contracts: int
    call_contracts_with_iv: int
    put_contracts: int
    put_contracts_with_iv: int
    front_month_contracts: int
    back_month_contracts: int
    total_volume: int
    total_open_interest: int

    @classmethod
    def from_contracts(
        cls,
        contracts: Iterable[OptionContractVol],
        *,
        short_dte: int = DEFAULT_SHORT_DTE,
        short_tolerance: int = DEFAULT_SHORT_TOLERANCE,
        long_dte: int = DEFAULT_LONG_DTE,
        long_tolerance: int = DEFAULT_LONG_TOLERANCE,
    ) -> "VolatilityMetricsCounts":
        contracts_list = list(contracts)
        total_contracts = len(contracts_list)
        contracts_with_iv = sum(1 for c in contracts_list if c.iv is not None)
        call_contracts = sum(1 for c in contracts_list if c.contract_type == "call")
        call_contracts_with_iv = sum(
            1 for c in contracts_list if c.contract_type == "call" and c.iv is not None
        )
        put_contracts = sum(1 for c in contracts_list if c.contract_type == "put")
        put_contracts_with_iv = sum(
            1 for c in contracts_list if c.contract_type == "put" and c.iv is not None
        )
        front_month_contracts = sum(
            1
            for c in contracts_list
            if c.dte is not None and abs(c.dte - short_dte) <= short_tolerance and c.dte >= 0
        )
        back_month_contracts = sum(
            1
            for c in contracts_list
            if c.dte is not None and abs(c.dte - long_dte) <= long_tolerance and c.dte >= 0
        )
        total_volume = sum(c.volume for c in contracts_list)
        total_open_interest = sum(c.open_interest for c in contracts_list)
        return cls(
            total_contracts=total_contracts,
            contracts_with_iv=contracts_with_iv,
            call_contracts=call_contracts,
            call_contracts_with_iv=call_contracts_with_iv,
            put_contracts=put_contracts,
            put_contracts_with_iv=put_contracts_with_iv,
            front_month_contracts=front_month_contracts,
            back_month_contracts=back_month_contracts,
            total_volume=total_volume,
            total_open_interest=total_open_interest,
        )

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_contracts": self.total_contracts,
            "contracts_with_iv": self.contracts_with_iv,
            "call_contracts": self.call_contracts,
            "call_contracts_with_iv": self.call_contracts_with_iv,
            "put_contracts": self.put_contracts,
            "put_contracts_with_iv": self.put_contracts_with_iv,
            "front_month_contracts": self.front_month_contracts,
            "back_month_contracts": self.back_month_contracts,
            "total_volume": self.total_volume,
            "total_open_interest": self.total_open_interest,
        }


def compute_volatility_metrics(
    *,
    contracts: Iterable[OptionContractVol],
    history: Sequence[Optional[float]],
    short_dte: int = DEFAULT_SHORT_DTE,
    long_dte: int = DEFAULT_LONG_DTE,
    min_history_points: int = DEFAULT_MIN_HISTORY_POINTS,
) -> Tuple[Dict[str, Optional[float]], VolatilityMetricsCounts]:
    contracts_list = list(contracts)
    counts = VolatilityMetricsCounts.from_contracts(
        contracts_list,
        short_dte=short_dte,
        short_tolerance=DEFAULT_SHORT_TOLERANCE,
        long_dte=long_dte,
        long_tolerance=DEFAULT_LONG_TOLERANCE,
    )
    avg_iv = calculate_average_iv(contracts_list)
    avg_call_iv = calculate_average_iv(
        [c for c in contracts_list if c.contract_type == "call"]
    )
    avg_put_iv = calculate_average_iv(
        [c for c in contracts_list if c.contract_type == "put"]
    )
    iv_rank = calculate_iv_rank(
        avg_iv, history, min_history_points=min_history_points
    )
    iv_percentile = calculate_iv_percentile(
        avg_iv, history, min_history_points=min_history_points
    )
    front_month = calculate_front_month_iv(
        contracts_list, short_dte=short_dte, tolerance=DEFAULT_SHORT_TOLERANCE
    )
    back_month = calculate_back_month_iv(
        contracts_list, long_dte=long_dte, tolerance=DEFAULT_LONG_TOLERANCE
    )
    iv_term_structure = calculate_iv_term_structure(
        contracts_list, short_dte=short_dte, long_dte=long_dte
    )
    iv_term_structure_slope = calculate_iv_term_structure_slope(
        front_month, back_month, short_dte=short_dte, long_dte=long_dte
    )
    iv_skew_call_put_val = calculate_iv_skew_call_put(avg_call_iv, avg_put_iv)
    metrics = {
        "avg_iv": avg_iv,
        "average_iv": avg_iv,
        "avg_call_iv": avg_call_iv,
        "avg_put_iv": avg_put_iv,
        "iv_stddev": calculate_iv_stddev(contracts_list),
        "iv_skew_call_put": iv_skew_call_put_val,
        "iv_skew": calculate_iv_skew(contracts_list),
        "put_call_oi_ratio": calculate_put_call_oi_ratio(contracts_list),
        "put_call_volume_ratio": calculate_put_call_volume_ratio(contracts_list),
        "iv_percentile": iv_percentile,
        "iv_rank": iv_rank,
        "front_month_iv": front_month,
        "back_month_iv": back_month,
        "iv_term_structure": iv_term_structure,
        "iv_term_structure_slope": iv_term_structure_slope,
    }
    return metrics, counts


_EMPTY_VOLATILITY_METRICS, _ = compute_volatility_metrics(contracts=[], history=[])
VOLATILITY_METRIC_KEYS = tuple(_EMPTY_VOLATILITY_METRICS.keys())
