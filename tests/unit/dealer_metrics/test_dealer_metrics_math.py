from __future__ import annotations

from datetime import datetime, timezone
import math

from core.metrics.dealer_metrics_calc import (
    _authoritative_dealer_module,  # type: ignore
    build_option_contract,
    calculate_metrics,
)
from core.metrics.dealer_metrics_job import FilterStats, _build_payload, _json_dumps_strict


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
    calls = module.find_walls(contracts, "call", 100.0, top_n=3)
    puts = module.find_walls(contracts, "put", 100.0, top_n=3)

    assert [int(w["strike"]) for w in calls] == [105, 100, 95]
    assert [int(w["strike"]) for w in puts] == [90, 85, 80]


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


def test_proximity_weighting_prefers_near_strike() -> None:
    module = _ref()
    spot = 100.0
    near = build_option_contract(
        strike=100,
        option_type="call",
        gamma=0.02,
        delta=0.5,
        open_interest=200,
        volume=10,
        iv=None,
        dte=10,
    )
    far = build_option_contract(
        strike=118,
        option_type="call",
        gamma=0.02,
        delta=0.5,
        open_interest=600,
        volume=10,
        iv=None,
        dte=10,
    )

    walls = module.find_walls([near, far], "call", spot, top_n=2, max_moneyness=0.2)
    assert len(walls) == 2
    assert walls[0]["strike"] == 100
    assert walls[1]["strike"] == 118


def test_moneyness_filter_excludes_deep_otm() -> None:
    module = _ref()
    spot = 100.0
    near = build_option_contract(
        strike=100,
        option_type="call",
        gamma=0.02,
        delta=0.5,
        open_interest=200,
        volume=10,
        iv=None,
        dte=10,
    )
    far = build_option_contract(
        strike=118,
        option_type="call",
        gamma=0.02,
        delta=0.5,
        open_interest=600,
        volume=10,
        iv=None,
        dte=10,
    )

    walls = module.find_walls([near, far], "call", spot, top_n=2, max_moneyness=0.1)
    assert len(walls) == 1
    assert walls[0]["strike"] == 100


def test_empty_wall_output_returns_empty_list() -> None:
    module = _ref()
    assert module.find_walls([], "call", 100.0, top_n=3) == []


def test_deterministic_json_output_for_identical_inputs() -> None:
    module = _ref()
    spot = 100.0
    contracts = [
        build_option_contract(
            strike=100,
            option_type="call",
            gamma=0.02,
            delta=0.5,
            open_interest=200,
            volume=10,
            iv=None,
            dte=10,
        ),
        build_option_contract(
            strike=103,
            option_type="call",
            gamma=0.025,
            delta=0.5,
            open_interest=150,
            volume=10,
            iv=None,
            dte=10,
        ),
        build_option_contract(
            strike=95,
            option_type="put",
            gamma=-0.02,
            delta=-0.4,
            open_interest=180,
            volume=10,
            iv=None,
            dte=10,
        ),
    ]

    params = {
        "max_dte_days": 90,
        "min_open_interest": 100,
        "min_volume": 1,
        "walls_top_n": 3,
        "gex_slope_range_pct": 0.02,
        "max_moneyness": 0.2,
    }

    snapshot_time = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    snapshot_date = snapshot_time.date()

    payloads = []
    for candidate in (contracts, list(reversed(contracts))):
        computation = calculate_metrics(candidate, spot=spot, walls_top_n=3, max_moneyness=0.2)
        payload = _build_payload(
            computation=computation,
            snapshot_time=snapshot_time,
            snapshot_date=snapshot_date,
            ticker_id="1",
            symbol="TEST",
            spot=spot,
            spot_source="mock",
            spot_resolution_strategy="mock",
            effective_options_time=snapshot_time,
            options_time_resolution_strategy="mock",
            effective_trading_date=snapshot_date,
            attempted_spot_sources=["mock"],
            filter_stats=FilterStats(total=len(candidate)),
            params=params,
            diagnostics=[],
            contracts_used=len(candidate),
            processing_status="SUCCESS",
            failure_reason=None,
            quality_status="FULL",
            status_reason="full_thresholds_met",
            eligible_options=len(candidate),
            total_options=len(candidate),
            max_moneyness=0.2,
        )
        payloads.append(_json_dumps_strict(payload))

    assert payloads[0] == payloads[1]


def test_payload_primary_references_first_wall_and_distance() -> None:
    module = _ref()
    spot = 100.0
    contracts = [
        build_option_contract(
            strike=102,
            option_type="call",
            gamma=0.02,
            delta=0.5,
            open_interest=250,
            volume=1,
            iv=None,
            dte=15,
        ),
        build_option_contract(
            strike=95,
            option_type="put",
            gamma=-0.02,
            delta=-0.4,
            open_interest=180,
            volume=2,
            iv=None,
            dte=15,
        ),
    ]
    params = {
        "max_dte_days": 90,
        "min_open_interest": 100,
        "min_volume": 1,
        "walls_top_n": 3,
        "gex_slope_range_pct": 0.02,
        "max_moneyness": 0.2,
    }
    snapshot_time = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    snapshot_date = snapshot_time.date()
    computation = calculate_metrics(contracts, spot=spot, walls_top_n=2, max_moneyness=0.2)
    payload = _build_payload(
        computation=computation,
        snapshot_time=snapshot_time,
        snapshot_date=snapshot_date,
        ticker_id="TICKER",
        symbol="TEST",
        spot=spot,
        spot_source="mock",
        spot_resolution_strategy="mock",
        effective_options_time=snapshot_time,
        options_time_resolution_strategy="mock",
        effective_trading_date=snapshot_date,
        attempted_spot_sources=["mock"],
        filter_stats=FilterStats(total=len(contracts)),
        params=params,
        diagnostics=[],
        contracts_used=len(contracts),
        processing_status="SUCCESS",
        failure_reason=None,
        quality_status="FULL",
        status_reason="full_thresholds_met",
        eligible_options=len(contracts),
        total_options=len(contracts),
        max_moneyness=0.2,
    )

    assert payload["spot_price"] == spot
    call_wall = payload["call_walls"][0]
    primary_call_wall = payload["primary_call_wall"]
    assert primary_call_wall == call_wall
    assert primary_call_wall is not call_wall
    expected_call_distance = round(abs(102 - spot), 6)
    assert primary_call_wall["distance_from_spot"] == expected_call_distance
    put_wall = payload["put_walls"][0]
    primary_put_wall = payload["primary_put_wall"]
    assert primary_put_wall == put_wall
    assert primary_put_wall is not put_wall
    expected_put_distance = round(abs(95 - spot), 6)
    assert primary_put_wall["distance_from_spot"] == expected_put_distance
