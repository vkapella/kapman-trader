from __future__ import annotations

import math

from core.metrics.dealer_metrics_calc import (
    _authoritative_dealer_module,  # type: ignore
    build_option_contract,
    calculate_metrics,
)


def _ref():
    return _authoritative_dealer_module()


def test_contract_gex_signs() -> None:
    module = _ref()
    spot = 50.0
    call = build_option_contract(
        strike=50.0,
        option_type="call",
        gamma=0.02,
        delta=0.5,
        open_interest=100,
        volume=10,
        iv=None,
        dte=10,
    )
    put = build_option_contract(
        strike=50.0,
        option_type="put",
        gamma=-0.02,
        delta=-0.5,
        open_interest=100,
        volume=10,
        iv=None,
        dte=10,
    )

    call_gex = module.calculate_contract_gex(call, spot)
    put_gex = module.calculate_contract_gex(put, spot)

    # Base magnitude
    expected = 0.02 * 100 * (spot**2) * 0.01 * 100
    assert math.isclose(abs(call_gex), expected)
    assert math.isclose(abs(put_gex), expected)
    assert call_gex < 0
    assert put_gex < 0  # put gamma from provider is typically negative


def test_strike_aggregation_and_net() -> None:
    module = _ref()
    contracts = [
        build_option_contract(
            strike=100,
            option_type="call",
            gamma=0.02,
            delta=0.5,
            open_interest=200,
            volume=5,
            iv=None,
            dte=20,
        ),
        build_option_contract(
            strike=100,
            option_type="put",
            gamma=-0.01,
            delta=-0.4,
            open_interest=100,
            volume=5,
            iv=None,
            dte=20,
        ),
    ]
    strike_gex = module.calculate_strike_gex(contracts, 100.0)
    assert len(strike_gex) == 1
    total = sum(abs(v) for v in strike_gex.values())
    net = sum(strike_gex.values())
    assert total > 0
    assert net < 0  # call overwhelms put due to sign inversion


def test_gamma_flip_interpolation() -> None:
    module = _ref()
    strike_gex = {90.0: -100.0, 100.0: 50.0, 110.0: 100.0}
    flip = module.find_gamma_flip(strike_gex)
    assert flip == 105.0


def test_walls_ordering_top_n() -> None:
    module = _ref()
    contracts = [
        build_option_contract(strike=100, option_type="call", gamma=0.01, delta=0.5, open_interest=300, volume=1, iv=None, dte=15),
        build_option_contract(strike=105, option_type="call", gamma=0.01, delta=0.5, open_interest=500, volume=1, iv=None, dte=15),
        build_option_contract(strike=95, option_type="call", gamma=0.01, delta=0.5, open_interest=200, volume=1, iv=None, dte=15),
        build_option_contract(strike=90, option_type="put", gamma=-0.01, delta=-0.4, open_interest=800, volume=1, iv=None, dte=15),
        build_option_contract(strike=85, option_type="put", gamma=-0.01, delta=-0.4, open_interest=600, volume=1, iv=None, dte=15),
        build_option_contract(strike=80, option_type="put", gamma=-0.01, delta=-0.4, open_interest=700, volume=1, iv=None, dte=15),
    ]
    calls = module.find_walls(contracts, "call", top_n=3)
    puts = module.find_walls(contracts, "put", top_n=3)

    assert [w["strike"] for w in calls] == [105, 100, 95]
    assert [w["strike"] for w in puts] == [90, 80, 85]


def test_gex_slope_and_dgpi() -> None:
    module = _ref()
    strike_gex = {98.0: -10.0, 100.0: 20.0, 102.0: 40.0}
    slope = module.calculate_gex_slope(strike_gex, 100.0, range_pct=0.02)
    assert math.isclose(slope, 17.5, rel_tol=1e-6)

    dgpi = module.calculate_dgpi(net_gex=50_000, gex_slope=slope, iv_rank=50.0)
    assert dgpi is not None
    assert -100 <= dgpi <= 100
    assert dgpi > 0


def test_position_and_confidence() -> None:
    module = _ref()
    contracts = [
        build_option_contract(strike=100 + i, option_type="call", gamma=0.01, delta=0.5, open_interest=150, volume=2, iv=None, dte=20)
        for i in range(10)
    ]
    confidence = module.determine_confidence(contracts)
    assert confidence in {"medium", "high"}
    position = module.determine_position(net_gex=0.5)
    assert position == "neutral"


def test_calculate_metrics_edge_cases() -> None:
    res = calculate_metrics([], spot=100.0)
    assert res.confidence == "invalid"
    assert res.gex_total is None

    contracts = [
        build_option_contract(strike=100, option_type="call", gamma=0.01, delta=0.5, open_interest=200, volume=1, iv=None, dte=10),
        build_option_contract(strike=105, option_type="put", gamma=-0.01, delta=-0.5, open_interest=200, volume=1, iv=None, dte=10),
    ]
    res2 = calculate_metrics(contracts, spot=100.0, walls_top_n=2, gex_slope_range_pct=0.02)
    assert res2.gex_total is not None
    assert res2.gex_net is not None
    assert len(res2.call_walls) <= 2 and len(res2.put_walls) <= 2
