import os
from typing import Optional

import httpx

from .base import AIProvider, ProviderResponse


class OpenAIProvider(AIProvider):
    provider_id = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    async def invoke(self, model_id: str, system_prompt: str, user_prompt: str) -> ProviderResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "top_p": 1,
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = ""
        if data.get("choices"):
            message = data["choices"][0].get("message", {})
            content = message.get("content", "") or ""
        model_version = data.get("model") or model_id
        return ProviderResponse(content=content, model_version=model_version)
