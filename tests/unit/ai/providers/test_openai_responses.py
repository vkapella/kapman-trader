from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from core.providers.ai.openai import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_responses_payload_and_text(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    calls: list[tuple[str, dict | None, dict | None]] = []

    async def mock_post(url, headers=None, json=None):
        calls.append((str(url), headers, json))
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "ok"}],
                },
            ],
            "model": "gpt-5-nano",
        }
        return httpx.Response(200, json=payload, request=httpx.Request("POST", str(url)))

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=mock_post)):
        provider = OpenAIProvider()
        response = await provider.invoke(model_id="gpt-5-nano", system_prompt="SYS", user_prompt="USER")

    assert response.content == "ok"
    assert response.model_version == "gpt-5-nano"
    assert calls[0][0].endswith("/responses")
    assert calls[0][1]["Authorization"] == "Bearer test"
    assert calls[0][1]["Content-Type"] == "application/json"
    assert "messages" not in calls[0][2]
    assert calls[0][2]["model"] == "gpt-5-nano"
    assert calls[0][2]["input"] == "USER"
    assert calls[0][2]["instructions"] == "SYS"
    assert calls[0][2]["temperature"] == 0
    assert calls[0][2]["top_p"] == 1
    assert calls[0][2]["text"]["format"]["type"] == "json_schema"
    assert "schema" in calls[0][2]["text"]["format"]
    assert "response_format" not in calls[0][2]
    assert set(calls[0][2].keys()) == {
        "model",
        "input",
        "instructions",
        "text",
        "temperature",
        "top_p",
    }


@pytest.mark.asyncio
async def test_openai_responses_malformed_output_raises(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    async def mock_post(url, headers=None, json=None):
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "refusal", "text": "nope"}],
                },
            ]
        }
        return httpx.Response(200, json=payload, request=httpx.Request("POST", str(url)))

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=mock_post)):
        provider = OpenAIProvider()
        with pytest.raises(RuntimeError, match="no output_text"):
            await provider.invoke(model_id="gpt-5-nano", system_prompt="SYS", user_prompt="USER")


@pytest.mark.asyncio
async def test_openai_responses_output_text_precedence(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    async def mock_post(url, headers=None, json=None):
        payload = {"output_text": "direct", "output": []}
        return httpx.Response(200, json=payload, request=httpx.Request("POST", str(url)))

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=mock_post)):
        provider = OpenAIProvider()
        response = await provider.invoke(model_id="gpt-5-nano", system_prompt="SYS", user_prompt="USER")

    assert response.content == "direct"


@pytest.mark.asyncio
async def test_openai_responses_multiple_output_text_blocks(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    async def mock_post(url, headers=None, json=None):
        payload = {
            "output": [
                {
                    "type": "reasoning",
                    "content": [{"type": "summary_text", "text": "skip"}],
                },
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "one"},
                        {"type": "output_text", "text": "two"},
                    ],
                },
            ]
        }
        return httpx.Response(200, json=payload, request=httpx.Request("POST", str(url)))

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=mock_post)):
        provider = OpenAIProvider()
        response = await provider.invoke(model_id="gpt-5-nano", system_prompt="SYS", user_prompt="USER")

    assert response.content == "one\ntwo"
