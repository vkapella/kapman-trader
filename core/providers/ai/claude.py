import os
from typing import Any, Optional, Tuple

import anthropic

from .base import AIProvider, ProviderResponse
from .prompt_loader import load_schema

SCHEMA_NAME = "ai/wyckoff_context_evaluation.v1.schema.json"
SYSTEM_MARKER = "<<<SYSTEM_PROMPT>>>"
USER_MARKER = "<<<USER_PROMPT>>>"


def _split_combined_prompt(system_prompt: str, user_prompt: str) -> Tuple[str, str]:
    if system_prompt and system_prompt.strip():
        return system_prompt, user_prompt
    if user_prompt and SYSTEM_MARKER in user_prompt and USER_MARKER in user_prompt:
        _, remainder = user_prompt.split(SYSTEM_MARKER, 1)
        if USER_MARKER in remainder:
            system_text, user_text = remainder.split(USER_MARKER, 1)
            return system_text.strip(), user_text.strip()
    return system_prompt, user_prompt


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
        system_prompt, user_prompt = _split_combined_prompt(system_prompt, user_prompt)
        schema = load_schema(SCHEMA_NAME)
        response = self.client.messages.create(
            model=model_id,
            max_tokens=1400,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            response_format={"type": "json_schema", "json_schema": schema},
        )
        content = _content_text(response.content[0]) if response.content else ""
        model_version = getattr(response, "model", None)
        return ProviderResponse(content=content, model_version=model_version)
