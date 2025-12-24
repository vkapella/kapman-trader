from __future__ import annotations

import statistics
from typing import Optional

import pytest

from core.metrics.volatility_metrics import (
    OptionContractVol,
    VolatilityMetricsCounts,
    VOLATILITY_METRIC_KEYS,
    calculate_average_iv,
    calculate_back_month_iv,
    calculate_front_month_iv,
    calculate_iv_rank,
    calculate_iv_skew,
    calculate_iv_skew_call_put,
    calculate_iv_stddev,
    calculate_iv_term_structure,
    calculate_iv_term_structure_slope,
    calculate_iv_percentile,
    calculate_oi_ratio,
    calculate_put_call_oi_ratio,
    calculate_put_call_volume_ratio,
    compute_volatility_metrics,
)


def _contract(
    *,
    contract_type: str,
    iv: Optional[float],
    delta: Optional[float] = None,
    dte: Optional[int] = None,
    open_interest: int = 0,
    volume: int = 0,
    strike: float = 100.0,
) -> OptionContractVol:
    return OptionContractVol(
        strike=strike,
        contract_type=contract_type,
        delta=delta,
        iv=iv,
        dte=dte,
        volume=volume,
        open_interest=open_interest,
    )


def test_calculate_average_iv_weighted() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.2, open_interest=10),
        _contract(contract_type="put", iv=0.4, open_interest=30),
    ]
    assert calculate_average_iv(contracts) == 0.35


def test_calculate_average_iv_fallback_to_simple_mean() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.25, open_interest=0),
        _contract(contract_type="put", iv=0.35, open_interest=0),
    ]
    assert calculate_average_iv(contracts) == 0.3


def test_calculate_put_call_oi_ratio() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.1, open_interest=20),
        _contract(contract_type="put", iv=0.2, open_interest=40),
    ]
    assert calculate_put_call_oi_ratio(contracts) == 2.0


def test_calculate_put_call_volume_ratio() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.2, volume=30),
        _contract(contract_type="put", iv=0.2, volume=70),
    ]
    assert calculate_put_call_volume_ratio(contracts) == pytest.approx(2.3333, abs=1e-4)


def test_calculate_put_call_volume_ratio_without_calls() -> None:
    contracts = [
        _contract(contract_type="put", iv=0.2, volume=10),
    ]
    assert calculate_put_call_volume_ratio(contracts) is None


def test_calculate_oi_ratio() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.2, volume=30, open_interest=10),
        _contract(contract_type="put", iv=0.2, volume=70, open_interest=30),
    ]
    assert calculate_oi_ratio(contracts) == 2.5


def test_calculate_oi_ratio_no_open_interest() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.2, volume=10, open_interest=0),
    ]
    assert calculate_oi_ratio(contracts) is None


def test_calculate_iv_stddev_is_zero_for_single_value() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.2),
    ]
    assert calculate_iv_stddev(contracts) == 0.0


def test_calculate_iv_stddev() -> None:
    values = [0.15, 0.25, 0.35]
    contracts = [_contract(contract_type="call", iv=v) for v in values]
    expected = round(statistics.pstdev(values), 4)
    assert calculate_iv_stddev(contracts) == expected


def test_calculate_iv_skew_prefers_delta() -> None:
    contracts = [
        _contract(contract_type="put", iv=0.3, delta=-0.24),
        _contract(contract_type="call", iv=0.2, delta=0.24),
    ]
    assert calculate_iv_skew(contracts) == 10.0


def test_calculate_iv_skew_strike_fallback() -> None:
    contracts = [
        _contract(contract_type="put", iv=0.4, delta=None, strike=90.0),
        _contract(contract_type="put", iv=0.2, delta=None, strike=80.0),
        _contract(contract_type="put", iv=0.5, delta=None, strike=100.0),
        _contract(contract_type="call", iv=0.2, delta=None, strike=110.0),
        _contract(contract_type="call", iv=0.15, delta=None, strike=120.0),
        _contract(contract_type="call", iv=0.25, delta=None, strike=130.0),
    ]
    assert calculate_iv_skew(contracts) == -5.0


def test_calculate_iv_skew_call_put_differs() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.12, open_interest=10),
        _contract(contract_type="call", iv=0.14, open_interest=10),
        _contract(contract_type="put", iv=0.22, open_interest=30),
    ]
    avg_call = calculate_average_iv([c for c in contracts if c.contract_type == "call"])
    avg_put = calculate_average_iv([c for c in contracts if c.contract_type == "put"])
    assert calculate_iv_skew_call_put(avg_call, avg_put) == pytest.approx((avg_put - avg_call) * 100, rel=1e-9)


def test_calculate_iv_skew_call_put_missing_inputs() -> None:
    assert calculate_iv_skew_call_put(None, 0.2) is None
    assert calculate_iv_skew_call_put(0.2, None) is None


def test_calculate_front_and_back_month_iv() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.1, dte=28),
        _contract(contract_type="call", iv=0.11, dte=32),
        _contract(contract_type="call", iv=0.25, dte=88),
        _contract(contract_type="call", iv=0.26, dte=92),
    ]
    assert calculate_front_month_iv(contracts) == pytest.approx(0.105, abs=1e-6)
    assert calculate_back_month_iv(contracts) == pytest.approx(0.255, abs=1e-6)


def test_calculate_iv_term_structure() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.15, dte=29),
        _contract(contract_type="call", iv=0.15, dte=31),
        _contract(contract_type="call", iv=0.25, dte=88),
        _contract(contract_type="call", iv=0.25, dte=92),
    ]
    assert calculate_iv_term_structure(contracts) == 10.0


def test_calculate_iv_term_structure_slope() -> None:
    slope = calculate_iv_term_structure_slope(0.1, 0.2, short_dte=30, long_dte=90)
    assert slope == pytest.approx(0.17, abs=1e-6)


def test_calculate_iv_percentile() -> None:
    history = [0.18, 0.2, 0.22, 0.24]
    assert calculate_iv_percentile(0.22, history, min_history_points=2) == pytest.approx(75.0, abs=1e-6)


def test_calculate_iv_percentile_insufficient_history() -> None:
    history = [0.2]
    assert calculate_iv_percentile(0.25, history, min_history_points=2) is None


def test_calculate_iv_rank() -> None:
    history = [0.2, 0.3, 0.4]
    assert calculate_iv_rank(0.35, history, min_history_points=3) == 75.0


def test_calculate_iv_rank_insufficient_history() -> None:
    history = [0.2]
    assert calculate_iv_rank(0.25, history, min_history_points=2) is None


def test_compute_volatility_metrics_includes_all_keys() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.15, open_interest=10, dte=28),
        _contract(contract_type="put", iv=0.2, open_interest=15, dte=90),
    ]
    history = [0.14, 0.15, 0.16, 0.17] * 10
    metrics, counts = compute_volatility_metrics(contracts=contracts, history=history, min_history_points=5)
    assert set(metrics.keys()) == set(VOLATILITY_METRIC_KEYS)
    assert counts.total_contracts == 2
    assert counts.contracts_with_iv == 2
    assert counts.call_contracts == 1
    assert counts.put_contracts == 1
    assert metrics["avg_iv"] is not None
    assert metrics["iv_rank"] is not None


def test_volatility_metrics_counts_to_dict() -> None:
    counts = VolatilityMetricsCounts.from_contracts(
        [
            _contract(contract_type="call", iv=0.1, dte=30),
            _contract(contract_type="put", iv=0.2, dte=90),
        ]
    )
    payload = counts.to_dict()
    assert payload["total_contracts"] == 2
    assert payload["call_contracts"] == 1
    assert payload["put_contracts"] == 1
