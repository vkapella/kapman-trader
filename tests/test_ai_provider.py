"""
Tests for AI providers.
"""
import unittest
from unittest.mock import patch, MagicMock
import asyncio
from datetime import datetime
from core.providers.ai.base import AnalysisContext, Recommendation

class TestClaudeProvider(unittest.TestCase):
    """Test cases for ClaudeProvider."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.test_context = AnalysisContext(
            symbol="AAPL",
            wyckoff_phase="Phase B",
            phase_confidence=0.85,
            events_detected=["Spring", "Test"],
            bc_score=75,
            spring_score=80,
            technical_indicators={"rsi": 65, "macd": 1.2},
            dealer_metrics={"flow": "positive", "sentiment": "bullish"},
            available_strikes=[150, 155, 160],
            available_expirations=["2025-12-15", "2025-12-22"]
        )
        
        # Set up test environment
        import os
        os.environ['ANTHROPIC_API_KEY'] = 'test-api-key'
    
    def setUp(self):
        # Import here to avoid loading dependencies during test discovery
        from core.providers.ai.claude import ClaudeProvider
        self.provider = ClaudeProvider(api_key="test-api-key")
    
    @patch('anthropic.Anthropic')
    def test_generate_recommendation(self, mock_anthropic):
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
        
        # Run the async test
        async def run_test():
            return await self.provider.generate_recommendation(self.test_context)
            
        # Execute the coroutine
        loop = asyncio.get_event_loop()
        recommendation = loop.run_until_complete(run_test())
        
        # Verify the results
        self.assertIsInstance(recommendation, Recommendation)
        self.assertEqual(recommendation.symbol, "AAPL")
        self.assertEqual(recommendation.direction, "LONG")
        self.assertEqual(recommendation.action, "BUY")
        self.assertGreaterEqual(recommendation.confidence, 0)
        self.assertLessEqual(recommendation.confidence, 1)
        
    @patch('anthropic.Anthropic')
    def test_generate_justification(self, mock_anthropic):
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
        
        # Run the async test
        async def run_test():
            return await self.provider.generate_justification(
                recommendation=test_recommendation,
                context=self.test_context
            )
            
        # Execute the coroutine
        loop = asyncio.get_event_loop()
        justification = loop.run_until_complete(run_test())
        
        # Verify the results
        self.assertIsInstance(justification, str)
        self.assertGreater(len(justification), 0)

if __name__ == '__main__':
    unittest.main()
