import os
from typing import Optional, Dict, Any
import anthropic
from .base import AIProvider, AnalysisContext, Recommendation, ModelInfo


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Claude provider with API key."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"  # Updated to the latest Sonnet 4 model

    async def generate_recommendation(self, context: AnalysisContext) -> Recommendation:
        """Generate a trading recommendation using Claude."""
        try:
            # Convert context to a string representation using Pydantic v2 method
            context_str = context.model_dump_json(indent=2)
            
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
            content = response.content[0].text
            import json
            data = json.loads(content)
            
            return Recommendation.model_validate(data)
            
        except Exception as e:
            raise Exception(f"Failed to generate recommendation: {str(e)}")

    async def generate_justification(self, recommendation: Recommendation, context: AnalysisContext) -> str:
        """Generate a detailed justification for a recommendation."""
        try:
            prompt = f"""Provide a detailed justification for the following trading recommendation.

Recommendation:
{recommendation.model_dump_json(indent=2)}

Context:
{context.model_dump_json(indent=2)}

Provide a detailed explanation of why this trade makes sense given the current market conditions,
technical indicators, and any relevant patterns or signals. Include potential risks and your
confidence level in this recommendation."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Could not generate justification: {str(e)}"

    def get_model_info(self) -> ModelInfo:
        """Get information about the AI model being used."""
        return ModelInfo(
            provider="Anthropic",
            model=self.model,
            version="1.0"
        )