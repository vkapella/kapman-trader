from __future__ import annotations

import pytest

from core.providers.ai import invoke as invoke_module


def test_invoke_provider_error_includes_type(monkeypatch) -> None:
    async def _fake_invoke(_provider_id: str, _model_id: str, _prompt_text: str) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(invoke_module, "_invoke_provider", _fake_invoke)

    with pytest.raises(RuntimeError, match="Provider invocation failed: RuntimeError: boom"):
        invoke_module.invoke_planning_agent(
            provider_id="openai",
            model_id="gpt-5-mini",
            snapshot_payload={
                "symbol": "AAPL",
                "snapshot_time": "2026-01-10T00:00:00+00:00",
                "daily_snapshot": {"wyckoff_regime": "MARKUP", "wyckoff_regime_confidence": 0.8},
            },
            option_context={},
            authority_constraints={},
            instructions={},
            prompt_version="test",
            kapman_model_version="test",
            debug=False,
            dry_run=False,
        )
