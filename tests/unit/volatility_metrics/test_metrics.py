from core.metrics.volatility_metrics import (
    OptionContractVol,
    calculate_average_iv,
    calculate_iv_rank,
    calculate_iv_skew,
    calculate_iv_term_structure,
    calculate_oi_ratio,
    calculate_put_call_ratio,
)
from typing import Optional


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


def test_calculate_put_call_ratio() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.1, open_interest=20),
        _contract(contract_type="put", iv=0.2, open_interest=40),
    ]
    assert calculate_put_call_ratio(contracts) == 2.0


def test_calculate_put_call_ratio_no_calls() -> None:
    contracts = [
        _contract(contract_type="put", iv=0.2, open_interest=10),
    ]
    assert calculate_put_call_ratio(contracts) is None


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


def test_calculate_iv_term_structure() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.15, dte=28),
        _contract(contract_type="call", iv=0.15, dte=32),
        _contract(contract_type="call", iv=0.25, dte=88),
        _contract(contract_type="call", iv=0.25, dte=92),
    ]
    assert calculate_iv_term_structure(contracts) == 10.0


def test_calculate_iv_term_structure_insufficient() -> None:
    contracts = [
        _contract(contract_type="call", iv=0.15, dte=10),
    ]
    assert calculate_iv_term_structure(contracts) is None


def test_calculate_iv_rank() -> None:
    history = [0.2, 0.3, 0.4]
    assert calculate_iv_rank(0.35, history, min_history_points=3) == 75.0


def test_calculate_iv_rank_insufficient_history() -> None:
    history = [0.2]
    assert calculate_iv_rank(0.25, history, min_history_points=2) is None
