import json
import os
from typing import Any, Dict, Optional

import anthropic

from .base import AIProvider, AnalysisContext, ModelInfo, Recommendation


def _model_dump_json(model: Any, *, indent: int = 2) -> str:
    if hasattr(model, "model_dump_json"):
        return model.model_dump_json(indent=indent)
    return model.json(indent=indent)


def _recommendation_from_dict(data: Dict[str, Any]) -> Recommendation:
    if hasattr(Recommendation, "model_validate"):
        return Recommendation.model_validate(data)
    return Recommendation.parse_obj(data)


def _content_text(content_block: Any) -> str:
    if hasattr(content_block, "text"):
        return str(content_block.text)
    if isinstance(content_block, dict) and "text" in content_block:
        return str(content_block["text"])
    return str(content_block)


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Claude provider with API key."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self._client: Any | None = None
        self.model = "claude-sonnet-4-20250514"  # Updated to the latest Sonnet 4 model

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def generate_recommendation(self, context: AnalysisContext) -> Recommendation:
        """Generate a trading recommendation using Claude."""
        try:
            context_str = _model_dump_json(context, indent=2)
            
            # Create the prompt
            prompt = f"""You are an expert options trader. Analyze the following market context and provide a trading recommendation.

Context:
{context_str}

Provide your recommendation in the following JSON format:
{{
    "symbol": "AAPL",
    "direction": "LONG|SHORT|NEUTRAL",
    "action": "BUY|SELL|HOLD|HEDGE",
    "confidence": 0.0-1.0,
    "strategy": "LONG_CALL|LONG_PUT|CSP|VERTICAL_SPREAD|etc",
    "strike": 0.0,
    "expiration": "YYYY-MM-DD",
    "entry_target": 0.0,
    "stop_loss": 0.0,
    "profit_target": 0.0,
    "justification": "Detailed explanation of the recommendation"
}}"""

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                system="You are a professional options trading assistant that provides clear, concise trading recommendations based on technical analysis.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse the response
            content = _content_text(response.content[0])
            data = json.loads(content)
            return _recommendation_from_dict(data)
            
        except Exception as e:
            raise Exception(f"Failed to generate recommendation: {str(e)}")

    async def generate_justification(self, recommendation: Recommendation, context: AnalysisContext) -> str:
        """Generate a detailed justification for a recommendation."""
        try:
            prompt = f"""Provide a detailed justification for the following trading recommendation.

Recommendation:
{_model_dump_json(recommendation, indent=2)}

Context:
{_model_dump_json(context, indent=2)}

Provide a detailed explanation of why this trade makes sense given the current market conditions,
technical indicators, and any relevant patterns or signals. Include potential risks and your
confidence level in this recommendation."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return _content_text(response.content[0])
            
        except Exception as e:
            return f"Could not generate justification: {str(e)}"

    def get_model_info(self) -> ModelInfo:
        """Get information about the AI model being used."""
        return ModelInfo(
            provider="Anthropic",
            model=self.model,
            version="1.0"
        )
