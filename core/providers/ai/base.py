from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class AnalysisContext(BaseModel):
    """Context for market analysis."""
    symbol: str
    wyckoff_phase: str
    phase_confidence: float
    events_detected: List[str]
    bc_score: int
    spring_score: int
    technical_indicators: Dict[str, Any]
    dealer_metrics: Dict[str, Any]
    available_strikes: List[float]
    available_expirations: List[str]

class Recommendation(BaseModel):
    """Trading recommendation from AI analysis."""
    symbol: str
    direction: str  # LONG, SHORT, NEUTRAL
    action: str  # BUY, SELL, HOLD, HEDGE
    confidence: float
    strategy: str  # LONG_CALL, LONG_PUT, CSP, VERTICAL_SPREAD
    strike: Optional[float] = None
    expiration: Optional[str] = None
    entry_target: float
    stop_loss: float
    profit_target: float
    justification: str

class ModelInfo(BaseModel):
    """Information about the AI model being used."""
    provider: str
    model: str
    version: str

class AIProvider(ABC):
    """Base class for all AI providers."""
    
    @abstractmethod
    async def generate_recommendation(self, context: AnalysisContext) -> Recommendation:
        """Generate a trading recommendation based on the analysis context."""
        pass
    
    @abstractmethod
    async def generate_justification(
        self, 
        recommendation: Recommendation, 
        context: AnalysisContext
    ) -> str:
        """Generate a detailed justification for a recommendation."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Get information about the AI model being used."""
        pass
