from __future__ import annotations

import pytest

from core.providers.ai import invoke as invoke_module


def test_invoke_provider_error_includes_type(monkeypatch) -> None:
    async def _fake_invoke(_provider_id: str, _model_id: str, _prompt_text: str) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(invoke_module, "_invoke_provider", _fake_invoke)

    response = invoke_module.invoke_planning_agent(
        provider_id="openai",
        model_id="gpt-5-mini",
        snapshot_payload={"symbol": "AAPL", "snapshot_time": "2026-01-10T00:00:00+00:00"},
        option_context={
            "option_chain_snapshot": [
                {"expiration": "2026-01-17", "strike": 150, "type": "CALL"}
            ]
        },
        authority_constraints={},
        instructions={},
        prompt_version="test",
        kapman_model_version="test",
        debug=False,
        dry_run=False,
    )

    assert response["context_evaluation"]["status"] == "REJECTED"
    assert response["context_evaluation"]["failure_type"] == "SCHEMA_FAIL"
    assert response["option_recommendations"]["primary"] is None
    assert "Provider invocation failed: RuntimeError: boom" in response["context_evaluation"]["reason"]
