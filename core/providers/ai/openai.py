import json
import os
from typing import Optional, Tuple

import httpx
import logging

from .base import AIProvider, ProviderResponse
from .prompt_loader import load_schema

logger = logging.getLogger("kapman.ai.openai")
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


def _ai_dump_enabled() -> bool:
    return os.getenv("AI_DUMP") == "1"


def _extract_ticker_from_prompt(prompt_text: str) -> Optional[str]:
    marker = "CONTEXT:"
    if marker not in prompt_text:
        return None
    payload_text = prompt_text.rsplit(marker, 1)[-1].strip()
    if not payload_text:
        return None
    try:
        payload = json.loads(payload_text)
    except Exception:
        return None
    if isinstance(payload, dict):
        snapshot = payload.get("snapshot_payload") or {}
        if isinstance(snapshot, dict):
            symbol = snapshot.get("symbol") or snapshot.get("ticker")
            if isinstance(symbol, str) and symbol:
                return symbol
    return None


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

    def _extract_responses_text(self, resp_json: dict) -> str:
        output_text = resp_json.get("output_text")
        if isinstance(output_text, str) and output_text:
            return output_text

        texts = []
        output = resp_json.get("output", [])
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "message":
                    continue
                content = item.get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "output_text":
                        text = block.get("text")
                        if text:
                            texts.append(str(text))

        if not texts:
            raise RuntimeError("OpenAI response contained no output_text")

        return "\n".join(texts)

    async def invoke(self, model_id: str, system_prompt: str, user_prompt: str) -> ProviderResponse:
        system_prompt, user_prompt = _split_combined_prompt(system_prompt, user_prompt)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        schema = load_schema(SCHEMA_NAME)
        payload = {
            "model": model_id,
            "input": user_prompt,
            "instructions": system_prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "kapman_a1_contract_v1",
                    "schema": schema,
                }
            },
            "temperature": 0,
            "top_p": 1,
        }
        endpoint = "responses"
        if _ai_dump_enabled():
            print(
                "[AI_DUMP] "
                + json.dumps(
                    {
                        "event": "openai_request",
                        "model": model_id,
                        "endpoint": f"/v1/{endpoint}",
                        "payload": payload,
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
        if _ai_dump_enabled() and endpoint == "responses":
            logger.info(
                "[AI_DUMP] "
                + json.dumps(
                    {
                        "event": "ai_request_dump",
                        "provider": "openai",
                        "model": model_id,
                        "ticker": _extract_ticker_from_prompt(user_prompt),
                        "payload": payload,
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(f"{self.base_url}/{endpoint}", headers=headers, json=payload)
                if _ai_dump_enabled():
                    print(
                        "[AI_DUMP] "
                        + json.dumps(
                            {
                                "event": "openai_raw_response",
                                "status_code": response.status_code,
                                "body": response.text,
                            },
                            ensure_ascii=True,
                            separators=(",", ":"),
                        )
                    )
                if response.status_code == 400:
                    logger.error(
                        "OpenAI request 400",
                        extra={
                            "payload": payload,
                            "response_body": response.text,
                        },
                    )
                response.raise_for_status()
                data = response.json()
                if _ai_dump_enabled():
                    parsed_output = data.get("output")
                    print(
                        "[AI_DUMP] "
                        + json.dumps(
                            {
                                "event": "openai_parsed_output",
                                "parsed": parsed_output,
                            },
                            ensure_ascii=True,
                            separators=(",", ":"),
                        )
                    )
                if _ai_dump_enabled() and endpoint == "responses":
                    logger.info(
                        "[AI_DUMP] "
                        + json.dumps(
                            {
                                "event": "ai_response_dump",
                                "provider": "openai",
                                "model": model_id,
                                "ticker": _extract_ticker_from_prompt(user_prompt),
                                "raw_response": response.text,
                            },
                            ensure_ascii=True,
                            separators=(",", ":"),
                        )
                    )
        except httpx.HTTPStatusError as exc:
            resp = exc.response
            body_snippet = ""
            request_id = None
            if resp is not None:
                body_snippet = (resp.text or "")[:2000]
                request_id = resp.headers.get("x-request-id")
            status_code = resp.status_code if resp is not None else "unknown"
            detail = f"OpenAI HTTP {status_code}: {body_snippet} (request_id={request_id})"
            raise RuntimeError(detail) from exc
        except Exception as exc:
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
        try:
            content = self._extract_responses_text(data)
        except Exception as exc:
            logger.debug("openai_raw_response", extra={"output": data.get("output")})
            raise RuntimeError(f"OpenAI response parsing failed: {exc}") from exc
        model_version = data.get("model") or model_id
        return ProviderResponse(content=content, model_version=model_version)
