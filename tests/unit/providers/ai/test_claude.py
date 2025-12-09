import unittest
from unittest.mock import MagicMock, patch
import asyncio
from core.providers.ai.claude import ClaudeProvider
from core.providers.ai.base import AnalysisContext, Recommendation

class TestClaudeProvider(unittest.TestCase):
    """Test cases for ClaudeProvider."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.provider = ClaudeProvider(api_key="test-key")
        self.test_context = AnalysisContext(
            symbol="AAPL",
            wyckoff_phase="Phase B",
            phase_confidence=0.85,
            events_detected=["Spring", "Test"],
            bc_data={"phase": "accumulation", "sentiment": "bullish"},
            available_strikes=[150.0, 155.0, 160.0],
            available_expirations=["2025-12-15", "2025-12-22"]
        )
        
    @patch('anthropic.Anthropic')
    async def test_generate_recommendation(self, mock_anthropic):
        """Test generating a trading recommendation."""
        # Mock the Claude API response
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [{
            "text": """{
                "symbol": "AAPL",
                "direction": "LONG",
                "action": "BUY",
                "confidence": 0.85,
                "strategy": "LONG_CALL",
                "strike": 155.0,
                "expiration": "2025-12-15",
                "entry_target": 152.5,
                "stop_loss": 148.0,
                "profit_target": 165.0,
                "justification": "Bullish technicals and positive dealer flow"
            }"""
        }]

        mock_client.messages.create.return_value = mock_message

        # Test the method
        recommendation = await self.provider.generate_recommendation(self.test_context)

        # Verify the results
        self.assertIsInstance(recommendation, Recommendation)
        self.assertEqual(recommendation.symbol, "AAPL")
        self.assertEqual(recommendation.direction, "LONG")
        self.assertEqual(recommendation.action, "BUY")
        
    @patch('anthropic.Anthropic')
    async def test_generate_justification(self, mock_anthropic):
        """Test generating a trading justification."""
        # Mock the Claude API response
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        test_recommendation = Recommendation(
            symbol="AAPL",
            direction="LONG",
            action="BUY",
            confidence=0.85,
            strategy="LONG_CALL",
            strike=155.0,
            expiration="2025-12-15",
            entry_target=152.5,
            stop_loss=148.0,
            profit_target=165.0,
            justification="Test justification"
        )

        mock_message = MagicMock()
        mock_message.content = [{"text": "This is a detailed justification for the trade."}]
        mock_client.messages.create.return_value = mock_message

        # Test the method
        justification = await self.provider.generate_justification(
            recommendation=test_recommendation,
            context=self.test_context
        )

        # Verify the results
        self.assertIsInstance(justification, str)
        self.assertIn("justification", justification.lower())

    def run_async(self, coro):
        """Run an async test."""
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_generate_recommendation_sync(self):
        """Test generate_recommendation in a sync context."""
        with patch.object(self.provider, 'generate_recommendation') as mock_method:
            mock_method.return_value = "test_recommendation"
            result = self.run_async(self.test_generate_recommendation(None))
            self.assertIsNotNone(result)

    def test_generate_justification_sync(self):
        """Test generate_justification in a sync context."""
        with patch.object(self.provider, 'generate_justification') as mock_method:
            mock_method.return_value = "test_justification"
            result = self.run_async(self.test_generate_justification(None))
            self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()
