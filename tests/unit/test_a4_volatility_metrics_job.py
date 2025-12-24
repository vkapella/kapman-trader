from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.metrics.a4_volatility_metrics_job import _determine_processing_status, DEFAULT_HISTORY_LOOKBACK
from core.metrics.volatility_metrics import OptionContractVol


def _sample_contract() -> OptionContractVol:
    return OptionContractVol(
        strike=100.0,
        contract_type="call",
        delta=0.25,
        iv=0.2,
        dte=30,
        volume=10,
        open_interest=20,
    )


def _options_time() -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_missing_options_data_returns_invalid_status() -> None:
    status, diagnostics = _determine_processing_status(
        metrics={"avg_iv": 0.2},
        contracts=[],
        options_snapshot_time=None,
        history_points=0,
    )
    assert status == "MISSING_OPTIONS"
    assert diagnostics == ["missing_options_data"]


def test_partial_when_avg_iv_missing() -> None:
    status, diagnostics = _determine_processing_status(
        metrics={"avg_iv": None},
        contracts=[_sample_contract()],
        options_snapshot_time=_options_time(),
        history_points=DEFAULT_HISTORY_LOOKBACK,
    )
    assert status == "PARTIAL"
    assert "missing_average_iv" in diagnostics
    assert "partial_metrics" in diagnostics


def test_success_even_with_insufficient_history() -> None:
    status, diagnostics = _determine_processing_status(
        metrics={"avg_iv": 0.25},
        contracts=[_sample_contract()],
        options_snapshot_time=_options_time(),
        history_points=5,
    )
    assert status == "SUCCESS"
    assert diagnostics == ["insufficient_iv_history"]


def test_success_with_sufficient_history_has_no_diagnostics() -> None:
    status, diagnostics = _determine_processing_status(
        metrics={"avg_iv": 0.25},
        contracts=[_sample_contract()],
        options_snapshot_time=_options_time(),
        history_points=DEFAULT_HISTORY_LOOKBACK,
    )
    assert status == "SUCCESS"
    assert diagnostics == []
