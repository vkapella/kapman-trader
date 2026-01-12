import importlib.util
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import core.metrics.c4_batch_ai_screening_job as c4_job
import core.providers.ai.invoke as ai_invoke


def _load_trace_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "run_c4_batch_ai_screening.py"
    spec = importlib.util.spec_from_file_location("run_c4_batch_ai_screening", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _invoke_with_trace(module, *, snapshot_payload: dict, trace_dir: Path, run_id: str) -> None:
    config = module.LLMTraceConfig(mode="full", trace_dir=trace_dir, run_id=run_id)
    writer = module.LLMTraceWriter(config)
    with module.TraceHooks(writer):
        ai_invoke.invoke_planning_agent(
            provider_id="openai",
            model_id="gpt-5",
            snapshot_payload=snapshot_payload,
            option_context={},
            authority_constraints={},
            instructions={},
            prompt_version="test",
            kapman_model_version="test",
            debug=False,
            dry_run=True,
        )


def test_llm_trace_emitted_on_serialization_failure(tmp_path: Path) -> None:
    module = _load_trace_module()
    bad_payload = {"symbol": "AAPL", "bad": object()}
    run_id = "run-failure"

    with pytest.raises(RuntimeError):
        _invoke_with_trace(module, snapshot_payload=bad_payload, trace_dir=tmp_path, run_id=run_id)

    target_dir = tmp_path / run_id / "AAPL"
    assert (target_dir / "02_openai_payload_raw.json").exists()
    assert (target_dir / "02b_openai_payload_normalization_error.json").exists()
    assert (target_dir / "99_openai_ticker_failure.json").exists()


def test_dry_run_emits_payload_traces(tmp_path: Path) -> None:
    module = _load_trace_module()
    payload = {"symbol": "AAPL", "metric": Decimal("1.5")}
    run_id = "run-dry"

    _invoke_with_trace(module, snapshot_payload=payload, trace_dir=tmp_path, run_id=run_id)

    target_dir = tmp_path / run_id / "AAPL"
    assert (target_dir / "02_openai_payload_raw.json").exists()
    assert (target_dir / "02b_openai_payload_normalized.json").exists()


def test_failed_ticker_does_not_block_batch(monkeypatch) -> None:
    fixed_time = datetime(2026, 1, 10, tzinfo=timezone.utc)

    monkeypatch.setattr(c4_job, "_resolve_snapshot_time", lambda _conn, _provided: fixed_time)
    monkeypatch.setattr(c4_job, "_fetch_watchlist_tickers", lambda _conn: [("t1", "AAA"), ("t2", "BBB")])
    monkeypatch.setattr(c4_job, "_load_daily_snapshot", lambda *_args, **_kwargs: {"wyckoff_regime": "UNKNOWN"})
    monkeypatch.setattr(c4_job, "_load_wyckoff_regime_transitions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(c4_job, "_load_wyckoff_sequences", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(c4_job, "_load_wyckoff_sequence_events", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(c4_job, "_load_wyckoff_snapshot_evidence", lambda *_args, **_kwargs: [])

    calls = {"count": 0}

    def _fake_invoke_planning_agent(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        return {"conditional_recommendation": {"direction": "NEUTRAL", "action": "HOLD"}}

    monkeypatch.setattr(c4_job, "invoke_planning_agent", _fake_invoke_planning_agent)

    conn = MagicMock()
    log = MagicMock()

    responses = c4_job.run_batch_ai_screening(
        conn,
        snapshot_time=fixed_time,
        ai_provider="openai",
        ai_model="gpt-5",
        batch_size=2,
        dry_run=True,
        log=log,
    )

    assert len(responses) == 2
    assert responses[0]["raw_normalized_response"]["error"] == "boom"
    assert responses[1]["raw_normalized_response"]["conditional_recommendation"]["action"] == "HOLD"
