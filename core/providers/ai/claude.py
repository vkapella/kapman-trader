import os
from typing import Any, Optional

import anthropic

from .base import AIProvider, ProviderResponse


def _content_text(content_block: Any) -> str:
    if hasattr(content_block, "text"):
        return str(content_block.text)
    if isinstance(content_block, dict) and "text" in content_block:
        return str(content_block["text"])
    return str(content_block)


class ClaudeProvider(AIProvider):
    provider_id = "anthropic"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def invoke(self, model_id: str, system_prompt: str, user_prompt: str) -> ProviderResponse:
        response = self.client.messages.create(
            model=model_id,
            max_tokens=1400,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = _content_text(response.content[0]) if response.content else ""
        model_version = getattr(response, "model", None)
        return ProviderResponse(content=content, model_version=model_version)
