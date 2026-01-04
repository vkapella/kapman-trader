from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from core.providers.ai.openai import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_http_error_includes_details(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(
        400,
        request=request,
        headers={"x-request-id": "req_123"},
        content=b"bad request",
    )

    async def mock_post(_url, headers=None, json=None):
        raise httpx.HTTPStatusError("bad", request=request, response=response)

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=mock_post)):
        provider = OpenAIProvider()
        with pytest.raises(RuntimeError) as exc_info:
            await provider.invoke(model_id="gpt-5-mini", system_prompt="SYS", user_prompt="USER")

    message = str(exc_info.value)
    assert "HTTP 400" in message
    assert "bad request" in message
    assert "request_id=req_123" in message
