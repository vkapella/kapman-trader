"""
Pydantic models for API requests and responses.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    symbols: list[str]
    include_historical: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbols": ["AAPL", "MSFT"],
                "include_historical": False
            }
        }


class WyckoffAnalysis(BaseModel):
    symbol: str
    wyckoff_phase: str
    phase_description: str
    phase_score: float
    phase_confidence: float
    volatility_regime: str
    macd_signal: str
    trend_strength: float
    composite_score: float
    metrics: dict
    data_quality: str
    volatility_adjusted: bool = False
    wyckoff_checklist: dict
    
    class Config:
        exclude_none = False


class WyckoffStructuralEvent(BaseModel):
    idx: int
    date: str
    label: str
    score: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None


class WyckoffStructuralPhase(BaseModel):
    name: str
    start_idx: int
    end_idx: int
    start_date: str
    end_date: str


class WyckoffStructuralAnalysis(BaseModel):
    """
    Response model for structural Wyckoff analysis (OHLCV-only).

    This is intentionally loose on some nested structures (phases/bands) so we
    can iterate on them without breaking the API. The UI primarily needs:
      - events        (for markers)
      - phases/bands  (for shaded regions)
      - per_bar_phase (for per-candle regime labeling)

    per_bar_phase is aligned 1:1 with the OHLCV series used in the
    structural engine. Each entry is either:
      - "Accumulation"
      - "Markup"
      - "Distribution"
      - "Markdown"
      - None  (no structural phase assigned for that bar)
    """

    symbol: str
    events: List[WyckoffStructuralEvent]
    phases: Dict[str, Any]
    bands: List[Dict[str, Any]]
    per_bar_phase: List[Optional[str]]


class StructuralAnalysisRequest(BaseModel):
    symbols: List[str]
    timespan: str = "day"
    limit: int = 300
    config_id: Optional[str] = None
    params_override: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbols": ["AAPL", "MSFT"],
                "timespan": "day",
                "limit": 300,
                "config_id": "wyckoff_structural_v1",
                "params_override": {
                    "min_phase_bars": 5,
                    "sc_vol_z": 2.5
                }
            }
        }
