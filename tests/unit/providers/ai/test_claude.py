import pytest
from unittest.mock import patch, MagicMock
from core.providers.ai.base import AnalysisContext, Recommendation
from core.providers.ai.claude import ClaudeProvider
import json

@pytest.mark.asyncio
class TestClaudeProvider:
    @pytest.fixture
    def test_context(self):
        """Fixture for test AnalysisContext."""
        return AnalysisContext(
            symbol="AAPL",
            wyckoff_phase="Phase B",
            phase_confidence=85,
            events_detected=["Spring", "Test"],
            bc_data={"phase": "accumulation", "sentiment": "bullish"},
            available_strikes=[150.0, 155.0, 160.0],
            available_expirations=["2025-12-15", "2025-12-22"],
            bc_score=80,
            spring_score=70,
            technical_indicators={"rsi": 65, "macd": "bullish"},
            dealer_metrics={"inventory": "high", "positioning": "long"}
        )

    @pytest.fixture
    def test_recommendation(self):
        """Fixture for test Recommendation."""
        return Recommendation(
            symbol="AAPL",
            direction="LONG",
            action="BUY",
            strategy="Wyckoff Spring",
            entry_target=150.0,
            stop_loss=145.0,
            profit_target=165.0,
            justification="Test justification",
            confidence=0.9
        )

    @pytest.fixture
    def provider(self):
        """Fixture for ClaudeProvider instance."""
        return ClaudeProvider(api_key="test-key")

    @pytest.mark.unit
    async def test_generate_justification(self, provider, test_context, test_recommendation):
        """Test generating a justification."""
        # Create a mock response for the synchronous API call
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test justification")]
        
        with patch.object(provider.client.messages, 'create', return_value=mock_response) as mock_create:
            result = await provider.generate_justification(
                recommendation=test_recommendation,
                context=test_context
            )
            assert "Test justification" in result
            mock_create.assert_called_once()

    @pytest.mark.unit
    async def test_generate_recommendation(self, provider, test_context):
        """Test generating a recommendation."""
        # Create a properly formatted JSON string for the mock response
        recommendation_data = {
            "symbol": "AAPL",
            "direction": "LONG",
            "action": "BUY",
            "strategy": "Wyckoff Spring",
            "entry_target": 150.0,
            "stop_loss": 145.0,
            "profit_target": 165.0,
            "justification": "Test justification",
            "confidence": 0.9
        }
        
        # Create a mock response for the synchronous API call
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(recommendation_data))]
        
        with patch.object(provider.client.messages, 'create', return_value=mock_response) as mock_create:
            result = await provider.generate_recommendation(context=test_context)
            assert isinstance(result, Recommendation)
            assert result.symbol == "AAPL"
            assert result.direction == "LONG"
            mock_create.assert_called_once()
