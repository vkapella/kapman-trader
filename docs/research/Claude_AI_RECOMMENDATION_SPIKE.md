# AI Recommendation Integration Spike
## KapMan Stories C1-C3 Pre-Implementation Analysis

**Date:** January 1, 2026  
**Author:** Victor Kapella / Claude  
**Status:** SPIKE - Pre-Story Design  
**Target Stories:** C1 (Strike Validator), C2 (Recommendation Persistence), C3 (Claude Interface)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Goal

Design an AI-driven trade recommendation system that:
1. Consumes rich context from KapMan's data layers (Wyckoff, dealer, TA, options)
2. Produces actionable, scoreable trade recommendations
3. Validates recommendations against real market data (no hallucinated strikes)
4. Enables iterative prompt refinement via outcome tracking

### 1.2 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Annual Return | 50-100% | Realized P&L vs SPY benchmark |
| Win Rate (20-day) | >55% | Directional accuracy |
| Recommendation Quality | 0 hallucinated strikes | Validation gate |
| Feedback Loop Latency | <7 days | First scored outcome |
| Prompt Iteration Cycle | <1 hour | Config change to new run |

### 1.3 Current State Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| OHLCV Data | ✅ Complete | 730 days, 15K+ tickers |
| Options Chains | ✅ Complete | 140 watchlist tickers |
| Technical Indicators | ✅ Complete | 84+ indicators |
| Dealer Metrics | ✅ Complete | GEX, DGPI, walls, gamma flip |
| Volatility Metrics | ✅ Complete | IV, skew, term structure |
| Price Metrics | ✅ Complete | RVOL, VSI, HV |
| Wyckoff Events | ✅ Complete | 8 events, regime classification |
| Claude Provider | ⚠️ Partial | Basic abstraction exists |
| Strike Validation | ❌ Missing | Story C1 |
| Recommendation Schema | ❌ Missing | Story C2 |
| Prompt Engineering | ❌ Missing | Story C3 |

---

## 2. DATA PAYLOAD DESIGN

### 2.1 Recommendation Request Contract

The AI receives a structured JSON payload per symbol containing all available context:

```json
{
  "request_metadata": {
    "request_id": "uuid-v4",
    "timestamp": "2026-01-01T16:00:00Z",
    "symbol": "NVDA",
    "analysis_date": "2026-01-01"
  },
  
  "price_context": {
    "current_price": 144.50,
    "price_1d_ago": 142.80,
    "price_5d_ago": 138.20,
    "price_20d_ago": 135.00,
    "price_change_1d_pct": 1.19,
    "price_change_5d_pct": 4.56,
    "price_change_20d_pct": 7.04,
    "support_level": 130.00,
    "resistance_level": 150.00
  },
  
  "wyckoff_context": {
    "regime": "ACCUMULATION",
    "regime_confidence": 0.85,
    "regime_duration_days": 12,
    "events_detected": ["SC", "AR", "SPRING"],
    "primary_event": "SPRING",
    "event_date": "2025-12-28",
    "event_score": 2.3,
    "bc_score": 8,
    "spring_score": 9,
    "prior_regime": "MARKDOWN",
    "sequence_status": "SC→AR→SPRING (awaiting SOS)"
  },
  
  "technical_context": {
    "rsi_14": 45.5,
    "macd_line": 1.23,
    "macd_signal": 0.95,
    "macd_histogram": 0.28,
    "sma_20": 142.50,
    "sma_50": 138.00,
    "sma_200": 125.00,
    "ema_12": 143.20,
    "ema_26": 141.80,
    "adx_14": 25.5,
    "atr_14": 4.20,
    "bbands_upper": 152.00,
    "bbands_middle": 142.50,
    "bbands_lower": 133.00,
    "bbands_pband": 0.72,
    "stoch_k": 55.2,
    "stoch_d": 52.8,
    "obv_trend": "rising",
    "vwap": 143.80
  },
  
  "dealer_context": {
    "status": "FULL",
    "gex_total": 1500000000,
    "gex_net": -500000000,
    "gamma_flip_level": 145.00,
    "call_wall_primary": 150.00,
    "put_wall_primary": 135.00,
    "dgpi": 25.5,
    "dealer_position": "short_gamma",
    "confidence": "high",
    "eligible_options_count": 450
  },
  
  "volatility_context": {
    "iv_rank": 35,
    "iv_percentile": 40,
    "average_iv": 0.42,
    "hv_20": 0.38,
    "hv_60": 0.35,
    "iv_hv_diff": 0.04,
    "iv_skew_25d": -0.05,
    "iv_term_structure": 0.02,
    "put_call_ratio_oi": 0.85,
    "vix_level": 18.5
  },
  
  "price_metrics": {
    "rvol": 1.35,
    "vsi": 0.85,
    "volume_trend_5d": "increasing"
  },
  
  "options_chain_summary": {
    "expiration_dates": ["2026-01-17", "2026-01-24", "2026-01-31", "2026-02-21"],
    "atm_strikes": [142, 143, 144, 145, 146],
    "high_oi_calls": [
      {"strike": 150, "expiry": "2026-01-17", "oi": 45000, "iv": 0.45},
      {"strike": 155, "expiry": "2026-02-21", "oi": 32000, "iv": 0.48}
    ],
    "high_oi_puts": [
      {"strike": 135, "expiry": "2026-01-17", "oi": 38000, "iv": 0.50},
      {"strike": 130, "expiry": "2026-02-21", "oi": 28000, "iv": 0.52}
    ],
    "total_call_oi": 250000,
    "total_put_oi": 212500
  },
  
  "available_contracts": {
    "calls": [
      {"strike": 145, "expiry": "2026-01-17", "bid": 2.50, "ask": 2.65, "iv": 0.44, "delta": 0.52, "theta": -0.08, "vega": 0.12},
      {"strike": 150, "expiry": "2026-01-17", "bid": 1.20, "ask": 1.35, "iv": 0.45, "delta": 0.35, "theta": -0.06, "vega": 0.10},
      {"strike": 145, "expiry": "2026-02-21", "bid": 5.80, "ask": 6.10, "iv": 0.43, "delta": 0.55, "theta": -0.04, "vega": 0.22}
    ],
    "puts": [
      {"strike": 140, "expiry": "2026-01-17", "bid": 1.80, "ask": 1.95, "iv": 0.46, "delta": -0.38, "theta": -0.07, "vega": 0.11},
      {"strike": 135, "expiry": "2026-01-17", "bid": 0.85, "ask": 0.95, "iv": 0.50, "delta": -0.22, "theta": -0.04, "vega": 0.08}
    ]
  },
  
  "constraints": {
    "max_position_size_usd": 10000,
    "max_contracts": 10,
    "allowed_strategies": ["LONG_CALL", "LONG_PUT", "CASH_SECURED_PUT", "VERTICAL_SPREAD"],
    "min_days_to_expiry": 14,
    "max_days_to_expiry": 60,
    "max_bid_ask_spread_pct": 0.10
  }
}
```

### 2.2 Recommendation Response Contract

```json
{
  "response_metadata": {
    "request_id": "uuid-v4",
    "model": "claude-sonnet-4-20250514",
    "response_timestamp": "2026-01-01T16:00:05Z",
    "processing_time_ms": 2500
  },
  
  "recommendation": {
    "action": "OPEN",
    "strategy": "LONG_CALL",
    "conviction": "HIGH",
    "symbol": "NVDA",
    
    "primary_leg": {
      "type": "CALL",
      "strike": 145,
      "expiry": "2026-02-21",
      "quantity": 5,
      "direction": "BUY",
      "entry_price_target": 5.95,
      "entry_price_limit": 6.10
    },
    
    "secondary_leg": null,
    
    "position_sizing": {
      "max_risk_usd": 2975,
      "contracts": 5,
      "total_premium_usd": 2975,
      "breakeven": 150.95
    },
    
    "targets": {
      "profit_target_pct": 50,
      "stop_loss_pct": 40,
      "time_stop_days": 30,
      "price_target": 155.00,
      "price_stop": 138.00
    },
    
    "rationale": {
      "primary_thesis": "SPRING event detected in ACCUMULATION phase with high dealer short gamma positioning suggests imminent upside breakout.",
      "supporting_factors": [
        "Wyckoff sequence SC→AR→SPRING complete, awaiting SOS confirmation",
        "Dealer short gamma at $145 creates upside squeeze potential",
        "RSI at 45.5 not overbought, room for expansion",
        "IV rank at 35 makes calls relatively cheap",
        "Price above all major SMAs (20/50/200)"
      ],
      "risk_factors": [
        "Gamma flip at $145 may act as near-term resistance",
        "BC score at 8 suggests some distribution pressure",
        "ATR of 4.20 implies significant daily volatility"
      ],
      "catalyst_timeline": "5-15 days for SOS confirmation"
    },
    
    "forecast": {
      "direction": "UP",
      "confidence_pct": 72,
      "expected_move_pct": 8.0,
      "time_horizon_days": 20
    }
  },
  
  "validation_status": {
    "strikes_valid": true,
    "expiry_valid": true,
    "constraints_met": true,
    "validation_errors": []
  },
  
  "alternatives": [
    {
      "strategy": "VERTICAL_SPREAD",
      "description": "145/155 call spread for reduced risk",
      "max_risk": 1500,
      "max_profit": 3500,
      "breakeven": 148.00
    }
  ]
}
```

---

## 3. PROMPT ENGINEERING FRAMEWORK

### 3.1 Prompt Architecture

The prompt system uses a **layered approach**:

```
┌─────────────────────────────────────────────────────┐
│  LAYER 1: SYSTEM CONTEXT (Static)                   │
│  - Role definition                                  │
│  - Methodology overview (Wyckoff + dealer)          │
│  - Output format requirements                       │
│  - Constraint enforcement rules                     │
├─────────────────────────────────────────────────────┤
│  LAYER 2: STRATEGY RULES (Semi-static)              │
│  - Entry signal definitions                         │
│  - Exit signal definitions                          │
│  - Position sizing rules                            │
│  - Risk management parameters                       │
├─────────────────────────────────────────────────────┤
│  LAYER 3: MARKET CONTEXT (Daily)                    │
│  - VIX level and regime                             │
│  - SPY/QQQ positioning                              │
│  - Sector rotation signals                          │
├─────────────────────────────────────────────────────┤
│  LAYER 4: SYMBOL DATA (Per-request)                 │
│  - Full payload from Section 2.1                    │
└─────────────────────────────────────────────────────┘
```

### 3.2 System Prompt Template

```yaml
# config/prompts/recommendation_system.yaml

version: "1.0"
name: "kapman_trade_recommendation"
description: "Generate options trade recommendations using Wyckoff + dealer analysis"

system_prompt: |
  You are a professional options trader and market analyst for Kapman Investments.
  Your role is to analyze market data and generate actionable trade recommendations.

  ## Your Methodology
  
  You combine two complementary analytical frameworks:
  
  1. **Wyckoff Market Analysis**
     - Identify market phases: Accumulation → Markup → Distribution → Markdown
     - Detect structural events: SC, AR, SPRING, SOS (bullish) or BC, AR_TOP, UT, SOW (bearish)
     - Entry signals: SPRING + SOS confirmation = strong bullish entry
     - Exit signals: BC Score ≥ 24 = immediate exit, SOW = reduce position
  
  2. **Dealer Positioning Analysis**
     - Short gamma dealers = volatility amplification, breakout support
     - Long gamma dealers = mean reversion, range-bound
     - Gamma flip level = key inflection point
     - Call/Put walls = support/resistance from options positioning
  
  ## Output Requirements
  
  1. **ALWAYS output valid JSON** matching the exact schema provided
  2. **NEVER hallucinate strikes or expirations** - only use contracts from available_contracts
  3. **ALWAYS respect constraints** (max position size, allowed strategies, DTE limits)
  4. **PROVIDE clear rationale** with specific references to data points
  5. **INCLUDE risk factors** - be balanced, not promotional
  6. **STATE conviction level** honestly based on signal confluence

  ## Conviction Framework
  
  - **HIGH**: Multiple confirming signals (Wyckoff + dealer + TA alignment)
  - **MEDIUM**: Primary signal present with some confirmation
  - **LOW**: Speculative or mixed signals
  - **NO_TRADE**: Conflicting signals or constraints not met

  ## Position Sizing Rules
  
  - Max 5% of portfolio per position (use constraints.max_position_size_usd)
  - Scale position size with conviction (HIGH=100%, MEDIUM=60%, LOW=30%)
  - Never exceed max_contracts limit
  
  ## Strategy Selection Guide
  
  - **LONG_CALL**: Bullish, IV rank < 50, expecting breakout
  - **LONG_PUT**: Bearish, IV rank < 50, expecting breakdown
  - **CASH_SECURED_PUT**: Bullish, IV rank > 50, willing to own shares
  - **VERTICAL_SPREAD**: Directional with defined risk, IV rank > 40

strategy_rules: |
  ## Entry Signal Scoring
  
  ### Bullish Entry (SPRING Setup)
  | Signal | Points |
  |--------|--------|
  | SPRING event detected | +3 |
  | Regime = ACCUMULATION | +2 |
  | SOS confirmed | +3 |
  | Dealer short gamma | +2 |
  | RSI < 60 | +1 |
  | Price > SMA 20 | +1 |
  | IV rank < 40 | +1 |
  
  Score interpretation:
  - 10+ = HIGH conviction
  - 7-9 = MEDIUM conviction
  - 4-6 = LOW conviction
  - <4 = NO_TRADE
  
  ### Bearish Entry (BC/UT Setup)
  | Signal | Points |
  |--------|--------|
  | BC event detected | +3 |
  | Regime = DISTRIBUTION | +2 |
  | SOW confirmed | +3 |
  | Dealer long gamma | +2 |
  | RSI > 70 | +1 |
  | Price < SMA 20 | +1 |
  | IV rank < 40 | +1 |

  ## Exit Signal Rules
  
  | Condition | Action |
  |-----------|--------|
  | BC Score ≥ 24 | EXIT IMMEDIATELY |
  | BC Score ≥ 20 | PREPARE EXIT (tighten stops) |
  | SOW detected | REDUCE by 50% |
  | Time stop hit | EXIT at market |
  | Profit target hit | EXIT or trail |
  | Stop loss hit | EXIT immediately |

output_schema: |
  {
    "recommendation": {
      "action": "OPEN | CLOSE | HOLD | NO_TRADE",
      "strategy": "LONG_CALL | LONG_PUT | CASH_SECURED_PUT | VERTICAL_SPREAD",
      "conviction": "HIGH | MEDIUM | LOW | NO_TRADE",
      "symbol": "string",
      "primary_leg": { ... },
      "secondary_leg": { ... } | null,
      "position_sizing": { ... },
      "targets": { ... },
      "rationale": { ... },
      "forecast": { ... }
    },
    "validation_status": { ... },
    "alternatives": [ ... ]
  }
```

### 3.3 Prompt Versioning Strategy

```
config/prompts/
├── recommendation_system.yaml      # Current production
├── versions/
│   ├── v1.0_baseline.yaml         # Initial version
│   ├── v1.1_tighter_stops.yaml    # Iteration after drawdown
│   ├── v1.2_sector_rotation.yaml  # Added sector context
│   └── v2.0_multi_leg.yaml        # Added spread strategies
└── experiments/
    ├── exp001_momentum_bias.yaml   # Testing momentum weighting
    └── exp002_vol_regime.yaml      # Testing vol regime switching
```

---

## 4. VALIDATION LAYER (Story C1)

### 4.1 Strike/Expiry Validator

```python
# core/recommendations/validators.py

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Dict, Any
from enum import Enum

class ValidationError(str, Enum):
    INVALID_STRIKE = "strike_not_in_chain"
    INVALID_EXPIRY = "expiry_not_available"
    STRIKE_EXPIRY_MISMATCH = "strike_not_available_for_expiry"
    EXCEEDS_MAX_CONTRACTS = "exceeds_max_contracts"
    EXCEEDS_MAX_POSITION = "exceeds_max_position_size"
    INSUFFICIENT_DTE = "below_min_dte"
    EXCESSIVE_DTE = "above_max_dte"
    WIDE_SPREAD = "bid_ask_spread_too_wide"
    STRATEGY_NOT_ALLOWED = "strategy_not_in_allowed_list"
    MISSING_REQUIRED_FIELD = "required_field_missing"

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[str]
    corrected_recommendation: Optional[Dict[str, Any]] = None

class RecommendationValidator:
    """
    Validates AI recommendations against real market data.
    CRITICAL: Zero tolerance for hallucinated strikes.
    """
    
    def __init__(self, options_chain: Dict[str, Any], constraints: Dict[str, Any]):
        self.chain = options_chain
        self.constraints = constraints
        self._build_valid_contracts()
    
    def _build_valid_contracts(self):
        """Build lookup sets for O(1) validation."""
        self.valid_calls = set()
        self.valid_puts = set()
        self.valid_expiries = set(self.chain.get("expiration_dates", []))
        
        for contract in self.chain.get("available_contracts", {}).get("calls", []):
            key = (contract["strike"], contract["expiry"])
            self.valid_calls.add(key)
        
        for contract in self.chain.get("available_contracts", {}).get("puts", []):
            key = (contract["strike"], contract["expiry"])
            self.valid_puts.add(key)
    
    def validate(self, recommendation: Dict[str, Any]) -> ValidationResult:
        """
        Full validation of recommendation against market reality.
        Returns ValidationResult with detailed error information.
        """
        errors = []
        warnings = []
        
        rec = recommendation.get("recommendation", {})
        
        # Strategy validation
        if rec.get("strategy") not in self.constraints.get("allowed_strategies", []):
            errors.append(ValidationError.STRATEGY_NOT_ALLOWED)
        
        # Primary leg validation
        primary = rec.get("primary_leg", {})
        if primary:
            leg_errors = self._validate_leg(primary)
            errors.extend(leg_errors)
        
        # Secondary leg validation (for spreads)
        secondary = rec.get("secondary_leg")
        if secondary:
            leg_errors = self._validate_leg(secondary)
            errors.extend(leg_errors)
        
        # Position sizing validation
        sizing = rec.get("position_sizing", {})
        if sizing.get("contracts", 0) > self.constraints.get("max_contracts", 999):
            errors.append(ValidationError.EXCEEDS_MAX_CONTRACTS)
        
        if sizing.get("total_premium_usd", 0) > self.constraints.get("max_position_size_usd", 999999):
            errors.append(ValidationError.EXCEEDS_MAX_POSITION)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_leg(self, leg: Dict[str, Any]) -> List[ValidationError]:
        """Validate a single option leg."""
        errors = []
        
        strike = leg.get("strike")
        expiry = leg.get("expiry")
        leg_type = leg.get("type", "").upper()
        
        # Check expiry exists
        if expiry not in self.valid_expiries:
            errors.append(ValidationError.INVALID_EXPIRY)
            return errors  # Can't validate strike without valid expiry
        
        # Check strike/expiry combination exists
        key = (strike, expiry)
        if leg_type == "CALL" and key not in self.valid_calls:
            errors.append(ValidationError.STRIKE_EXPIRY_MISMATCH)
        elif leg_type == "PUT" and key not in self.valid_puts:
            errors.append(ValidationError.STRIKE_EXPIRY_MISMATCH)
        
        # Check DTE constraints
        if expiry:
            dte = self._calculate_dte(expiry)
            if dte < self.constraints.get("min_days_to_expiry", 0):
                errors.append(ValidationError.INSUFFICIENT_DTE)
            if dte > self.constraints.get("max_days_to_expiry", 999):
                errors.append(ValidationError.EXCESSIVE_DTE)
        
        return errors
    
    def _calculate_dte(self, expiry: str) -> int:
        """Calculate days to expiration."""
        from datetime import datetime
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        return (exp_date - date.today()).days
```

### 4.2 Validation Integration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    RECOMMENDATION FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Build Payload ──► 2. Call Claude ──► 3. Parse Response     │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  [Data Assembly]     [API Call]         [JSON Parse]           │
│                                                                 │
│                              │                                  │
│                              ▼                                  │
│                   ┌─────────────────────┐                       │
│                   │  4. VALIDATE        │                       │
│                   │  ────────────────   │                       │
│                   │  • Strike exists?   │                       │
│                   │  • Expiry exists?   │                       │
│                   │  • Within limits?   │                       │
│                   │  • Spread OK?       │                       │
│                   └─────────┬───────────┘                       │
│                             │                                   │
│              ┌──────────────┴──────────────┐                    │
│              ▼                             ▼                    │
│        [VALID]                       [INVALID]                  │
│           │                              │                      │
│           ▼                              ▼                      │
│    5. Persist to DB              Log validation error           │
│                                  Optionally retry with          │
│                                  corrected constraints          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. PERSISTENCE SCHEMA (Story C2)

### 5.1 Recommendations Table

```sql
-- migrations/XXX_create_recommendations.sql

CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Request context
    request_id UUID NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    analysis_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Recommendation core
    action VARCHAR(20) NOT NULL,  -- OPEN, CLOSE, HOLD, NO_TRADE
    strategy VARCHAR(30) NOT NULL, -- LONG_CALL, LONG_PUT, CSP, VERTICAL_SPREAD
    conviction VARCHAR(20) NOT NULL, -- HIGH, MEDIUM, LOW, NO_TRADE
    
    -- Primary leg
    primary_leg_type VARCHAR(10), -- CALL, PUT
    primary_strike DECIMAL(10,2),
    primary_expiry DATE,
    primary_quantity INTEGER,
    primary_direction VARCHAR(10), -- BUY, SELL
    primary_entry_price DECIMAL(10,4),
    
    -- Secondary leg (for spreads)
    secondary_leg_type VARCHAR(10),
    secondary_strike DECIMAL(10,2),
    secondary_expiry DATE,
    secondary_quantity INTEGER,
    secondary_direction VARCHAR(10),
    secondary_entry_price DECIMAL(10,4),
    
    -- Position sizing
    max_risk_usd DECIMAL(12,2),
    total_premium_usd DECIMAL(12,2),
    breakeven_price DECIMAL(10,2),
    
    -- Targets
    profit_target_pct DECIMAL(5,2),
    stop_loss_pct DECIMAL(5,2),
    time_stop_days INTEGER,
    price_target DECIMAL(10,2),
    price_stop DECIMAL(10,2),
    
    -- Forecast
    forecast_direction VARCHAR(10), -- UP, DOWN
    forecast_confidence_pct DECIMAL(5,2),
    forecast_expected_move_pct DECIMAL(5,2),
    forecast_horizon_days INTEGER,
    
    -- Full context (for audit/replay)
    request_payload JSONB NOT NULL,
    response_payload JSONB NOT NULL,
    rationale JSONB NOT NULL,
    
    -- Validation
    validation_passed BOOLEAN NOT NULL DEFAULT TRUE,
    validation_errors TEXT[],
    
    -- AI metadata
    model_version VARCHAR(50) NOT NULL,
    prompt_version VARCHAR(20) NOT NULL,
    processing_time_ms INTEGER,
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING, EXECUTED, EXPIRED, CANCELLED
    executed_at TIMESTAMPTZ,
    execution_price DECIMAL(10,4),
    
    UNIQUE(symbol, analysis_date, strategy)
);

-- Indexes for common queries
CREATE INDEX idx_recommendations_symbol_date ON recommendations(symbol, analysis_date DESC);
CREATE INDEX idx_recommendations_status ON recommendations(status);
CREATE INDEX idx_recommendations_conviction ON recommendations(conviction);
CREATE INDEX idx_recommendations_created ON recommendations(created_at DESC);
```

### 5.2 Recommendation Outcomes Table

```sql
-- migrations/XXX_create_recommendation_outcomes.sql

CREATE TABLE recommendation_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID NOT NULL REFERENCES recommendations(id),
    
    -- Measurement points
    entry_date DATE NOT NULL,
    entry_price DECIMAL(10,4) NOT NULL,
    
    -- 5-day outcome
    price_5d DECIMAL(10,4),
    return_5d_pct DECIMAL(8,4),
    direction_correct_5d BOOLEAN,
    measured_at_5d TIMESTAMPTZ,
    
    -- 10-day outcome
    price_10d DECIMAL(10,4),
    return_10d_pct DECIMAL(8,4),
    direction_correct_10d BOOLEAN,
    measured_at_10d TIMESTAMPTZ,
    
    -- 20-day outcome
    price_20d DECIMAL(10,4),
    return_20d_pct DECIMAL(8,4),
    direction_correct_20d BOOLEAN,
    measured_at_20d TIMESTAMPTZ,
    
    -- 40-day outcome
    price_40d DECIMAL(10,4),
    return_40d_pct DECIMAL(8,4),
    direction_correct_40d BOOLEAN,
    measured_at_40d TIMESTAMPTZ,
    
    -- Brier scores (probability calibration)
    brier_5d DECIMAL(6,4),
    brier_10d DECIMAL(6,4),
    brier_20d DECIMAL(6,4),
    brier_40d DECIMAL(6,4),
    
    -- MAE/MFE (trade quality)
    max_adverse_excursion_pct DECIMAL(8,4),
    max_favorable_excursion_pct DECIMAL(8,4),
    
    -- Option-specific outcomes (if position taken)
    option_entry_price DECIMAL(10,4),
    option_exit_price DECIMAL(10,4),
    option_pnl_usd DECIMAL(12,2),
    option_pnl_pct DECIMAL(8,4),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outcomes_recommendation ON recommendation_outcomes(recommendation_id);
CREATE INDEX idx_outcomes_entry_date ON recommendation_outcomes(entry_date);
```

### 5.3 Scoring Aggregates View

```sql
-- views/recommendation_performance.sql

CREATE OR REPLACE VIEW recommendation_performance AS
SELECT 
    r.prompt_version,
    r.model_version,
    r.conviction,
    r.strategy,
    
    -- Sample counts
    COUNT(*) as total_recommendations,
    COUNT(o.id) as scored_recommendations,
    
    -- Win rates by horizon
    AVG(CASE WHEN o.direction_correct_5d THEN 1.0 ELSE 0.0 END) as win_rate_5d,
    AVG(CASE WHEN o.direction_correct_10d THEN 1.0 ELSE 0.0 END) as win_rate_10d,
    AVG(CASE WHEN o.direction_correct_20d THEN 1.0 ELSE 0.0 END) as win_rate_20d,
    AVG(CASE WHEN o.direction_correct_40d THEN 1.0 ELSE 0.0 END) as win_rate_40d,
    
    -- Average returns
    AVG(o.return_5d_pct) as avg_return_5d,
    AVG(o.return_10d_pct) as avg_return_10d,
    AVG(o.return_20d_pct) as avg_return_20d,
    AVG(o.return_40d_pct) as avg_return_40d,
    
    -- Brier scores (lower is better, 0 = perfect)
    AVG(o.brier_5d) as avg_brier_5d,
    AVG(o.brier_10d) as avg_brier_10d,
    AVG(o.brier_20d) as avg_brier_20d,
    AVG(o.brier_40d) as avg_brier_40d,
    
    -- Trade quality
    AVG(o.max_adverse_excursion_pct) as avg_mae,
    AVG(o.max_favorable_excursion_pct) as avg_mfe,
    AVG(o.option_pnl_pct) as avg_option_return
    
FROM recommendations r
LEFT JOIN recommendation_outcomes o ON r.id = o.recommendation_id
WHERE r.validation_passed = TRUE
GROUP BY r.prompt_version, r.model_version, r.conviction, r.strategy;
```

---

## 6. CLAUDE INTERFACE (Story C3)

### 6.1 Provider Abstraction

```python
# core/providers/ai/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum

class AIProvider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"

@dataclass
class AIConfig:
    provider: AIProvider
    model: str
    api_key: str
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout_seconds: int = 60

@dataclass
class AIResponse:
    content: str
    model: str
    usage: Dict[str, int]
    latency_ms: int
    raw_response: Dict[str, Any]

class AIProviderBase(ABC):
    """Abstract base for AI providers."""
    
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        config: AIConfig
    ) -> AIResponse:
        pass
    
    @abstractmethod
    def parse_json_response(self, response: AIResponse) -> Dict[str, Any]:
        pass
```

### 6.2 Claude Implementation

```python
# core/providers/ai/claude.py

import anthropic
import json
import time
from typing import Dict, Any

from .base import AIProviderBase, AIConfig, AIResponse

class ClaudeProvider(AIProviderBase):
    """Claude API provider implementation."""
    
    def __init__(self):
        self.client = None
    
    def _ensure_client(self, api_key: str):
        if self.client is None:
            self.client = anthropic.Anthropic(api_key=api_key)
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        config: AIConfig
    ) -> AIResponse:
        self._ensure_client(config.api_key)
        
        start_time = time.time()
        
        response = self.client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return AIResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            },
            latency_ms=latency_ms,
            raw_response=response.model_dump()
        )
    
    def parse_json_response(self, response: AIResponse) -> Dict[str, Any]:
        """Extract JSON from response, handling markdown code blocks."""
        content = response.content.strip()
        
        # Handle ```json ... ``` blocks
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            content = "\n".join(json_lines)
        
        return json.loads(content)
```

### 6.3 Recommendation Service

```python
# core/recommendations/service.py

import uuid
from datetime import datetime, date
from typing import Dict, Any, Optional, List
import yaml

from ..providers.ai.base import AIConfig, AIProvider
from ..providers.ai.claude import ClaudeProvider
from .validators import RecommendationValidator, ValidationResult
from .payload_builder import PayloadBuilder

class RecommendationService:
    """
    Orchestrates the full recommendation workflow:
    1. Build data payload
    2. Generate recommendation via AI
    3. Validate against real market data
    4. Persist to database
    """
    
    def __init__(
        self,
        ai_config: AIConfig,
        prompt_config_path: str = "config/prompts/recommendation_system.yaml"
    ):
        self.ai_config = ai_config
        self.prompt_config = self._load_prompt_config(prompt_config_path)
        self.provider = self._get_provider()
    
    def _load_prompt_config(self, path: str) -> Dict[str, Any]:
        with open(path) as f:
            return yaml.safe_load(f)
    
    def _get_provider(self):
        if self.ai_config.provider == AIProvider.CLAUDE:
            return ClaudeProvider()
        raise ValueError(f"Unsupported provider: {self.ai_config.provider}")
    
    async def generate_recommendation(
        self,
        symbol: str,
        analysis_date: date,
        daily_snapshot: Dict[str, Any],
        options_chain: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a validated recommendation for a symbol.
        
        Returns full recommendation response with validation status.
        """
        request_id = str(uuid.uuid4())
        
        # 1. Build payload
        payload = PayloadBuilder.build(
            request_id=request_id,
            symbol=symbol,
            analysis_date=analysis_date,
            snapshot=daily_snapshot,
            options_chain=options_chain,
            constraints=constraints
        )
        
        # 2. Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(payload)
        
        # 3. Call AI
        response = await self.provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=self.ai_config
        )
        
        # 4. Parse response
        recommendation = self.provider.parse_json_response(response)
        
        # 5. Validate
        validator = RecommendationValidator(options_chain, constraints)
        validation = validator.validate(recommendation)
        
        # 6. Enrich with metadata
        recommendation["response_metadata"] = {
            "request_id": request_id,
            "model": response.model,
            "response_timestamp": datetime.utcnow().isoformat(),
            "processing_time_ms": response.latency_ms
        }
        recommendation["validation_status"] = {
            "strikes_valid": validation.is_valid,
            "validation_errors": [e.value for e in validation.errors]
        }
        
        return {
            "request_payload": payload,
            "recommendation": recommendation,
            "validation": validation,
            "ai_response": response
        }
    
    def _build_system_prompt(self) -> str:
        """Assemble full system prompt from config."""
        parts = [
            self.prompt_config.get("system_prompt", ""),
            self.prompt_config.get("strategy_rules", ""),
            self.prompt_config.get("output_schema", "")
        ]
        return "\n\n".join(parts)
    
    def _build_user_prompt(self, payload: Dict[str, Any]) -> str:
        """Build user prompt with data payload."""
        return f"""
Analyze the following market data and generate a trade recommendation.

## Market Data

```json
{json.dumps(payload, indent=2, default=str)}
```

## Instructions

1. Analyze all provided context (Wyckoff, dealer, technical, volatility)
2. Score the setup using the entry signal framework
3. Select appropriate strategy based on conviction and IV environment
4. Choose specific strikes and expirations from available_contracts ONLY
5. Size position according to constraints and conviction
6. Output valid JSON matching the required schema

Respond with ONLY the JSON recommendation object, no additional text.
"""
```

---

## 7. FEEDBACK LOOP DESIGN

### 7.1 Outcome Collection Schedule

```
┌────────────────────────────────────────────────────────────────┐
│                    OUTCOME COLLECTION TIMELINE                  │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Day 0: Recommendation generated                                │
│         ├─ Stored in recommendations table                      │
│         └─ outcome_collector scheduled                          │
│                                                                  │
│  Day 5: First measurement                                        │
│         ├─ Fetch current price                                   │
│         ├─ Calculate 5d return                                   │
│         ├─ Score direction accuracy                              │
│         └─ Calculate Brier score                                 │
│                                                                  │
│  Day 10: Second measurement                                      │
│          └─ Same calculations for 10d horizon                    │
│                                                                  │
│  Day 20: Third measurement                                       │
│          └─ Same calculations for 20d horizon                    │
│                                                                  │
│  Day 40: Final measurement                                       │
│          ├─ Same calculations for 40d horizon                    │
│          └─ Calculate MAE/MFE over full period                   │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### 7.2 Brier Score Calculation

```python
def calculate_brier_score(
    predicted_probability: float,
    predicted_direction: str,
    actual_return: float
) -> float:
    """
    Calculate Brier score for probability calibration.
    
    Brier Score = (probability - outcome)²
    
    Where:
    - probability = predicted confidence (0-1)
    - outcome = 1 if direction correct, 0 if incorrect
    
    Lower is better:
    - 0.00 = perfect calibration
    - 0.25 = random guessing at 50%
    - 1.00 = always wrong at 100% confidence
    """
    # Determine if prediction was correct
    actual_direction = "UP" if actual_return > 0 else "DOWN"
    outcome = 1.0 if predicted_direction == actual_direction else 0.0
    
    # Convert confidence to probability
    probability = predicted_probability / 100.0
    
    # Brier score
    return (probability - outcome) ** 2
```

### 7.3 Performance Dashboard Queries

```sql
-- Weekly performance summary
SELECT 
    DATE_TRUNC('week', r.analysis_date) as week,
    COUNT(*) as recommendations,
    AVG(CASE WHEN o.direction_correct_20d THEN 1.0 ELSE 0.0 END) as win_rate_20d,
    AVG(o.return_20d_pct) as avg_return_20d,
    AVG(o.brier_20d) as avg_brier_20d,
    SUM(CASE WHEN r.conviction = 'HIGH' THEN 1 ELSE 0 END) as high_conviction_count,
    AVG(CASE WHEN r.conviction = 'HIGH' THEN o.return_20d_pct END) as high_conviction_return
FROM recommendations r
JOIN recommendation_outcomes o ON r.id = o.recommendation_id
WHERE r.validation_passed = TRUE
  AND o.price_20d IS NOT NULL
GROUP BY DATE_TRUNC('week', r.analysis_date)
ORDER BY week DESC;

-- Conviction accuracy analysis
SELECT 
    r.conviction,
    COUNT(*) as count,
    AVG(CASE WHEN o.direction_correct_20d THEN 1.0 ELSE 0.0 END) as actual_win_rate,
    AVG(r.forecast_confidence_pct) as avg_stated_confidence,
    AVG(o.brier_20d) as calibration_score
FROM recommendations r
JOIN recommendation_outcomes o ON r.id = o.recommendation_id
WHERE r.validation_passed = TRUE
  AND o.price_20d IS NOT NULL
GROUP BY r.conviction
ORDER BY 
    CASE r.conviction 
        WHEN 'HIGH' THEN 1 
        WHEN 'MEDIUM' THEN 2 
        WHEN 'LOW' THEN 3 
    END;

-- Strategy performance comparison
SELECT 
    r.strategy,
    COUNT(*) as count,
    AVG(o.return_20d_pct) as avg_return,
    STDDEV(o.return_20d_pct) as return_stddev,
    AVG(o.return_20d_pct) / NULLIF(STDDEV(o.return_20d_pct), 0) as sharpe_proxy,
    AVG(o.max_adverse_excursion_pct) as avg_mae,
    AVG(o.max_favorable_excursion_pct) as avg_mfe
FROM recommendations r
JOIN recommendation_outcomes o ON r.id = o.recommendation_id
WHERE r.validation_passed = TRUE
  AND o.price_20d IS NOT NULL
GROUP BY r.strategy;
```

---

## 8. ITERATION WORKFLOW

### 8.1 Prompt Tuning Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROMPT ITERATION CYCLE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ANALYZE OUTCOMES                                            │
│     └─ Query recommendation_performance view                    │
│     └─ Identify systematic failures                             │
│     └─ Example: "HIGH conviction losing at 45%"                 │
│                                                                  │
│  2. HYPOTHESIZE                                                  │
│     └─ "Model overweighting dealer metrics"                     │
│     └─ "Missing sector rotation context"                        │
│     └─ "Stop losses too tight"                                   │
│                                                                  │
│  3. MODIFY PROMPT                                               │
│     └─ Create new version in config/prompts/versions/           │
│     └─ Adjust scoring weights                                   │
│     └─ Add/remove context                                       │
│     └─ Tighten/loosen rules                                     │
│                                                                  │
│  4. TEST                                                         │
│     └─ Run on historical data (replay mode)                     │
│     └─ Compare to baseline                                      │
│     └─ Statistical significance check                           │
│                                                                  │
│  5. DEPLOY                                                       │
│     └─ Update prompt_version in config                          │
│     └─ Run forward for minimum 2 weeks                          │
│     └─ Return to step 1                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Guardrail Additions

Based on outcome analysis, add guardrails to the system:

```yaml
# config/guardrails.yaml

position_limits:
  max_single_position_pct: 5.0
  max_sector_exposure_pct: 25.0
  max_correlation_to_spy: 0.8
  
signal_filters:
  min_conviction_for_trade: "MEDIUM"
  require_wyckoff_event: true
  require_dealer_confirmation: true
  
risk_rules:
  max_daily_loss_pct: 2.0
  max_weekly_loss_pct: 5.0
  pause_after_consecutive_losses: 3
  
iv_environment:
  prefer_spreads_above_iv_rank: 50
  prefer_long_options_below_iv_rank: 30
  
time_filters:
  avoid_earnings_within_days: 7
  avoid_fomc_within_days: 2
  avoid_friday_expirations: true
```

---

## 9. IMPLEMENTATION PLAN

### 9.1 Story C1: Strike Validator (3 points)

**Scope:**
- `RecommendationValidator` class
- Strike/expiry lookup against options chain
- Constraint enforcement (DTE, position size, spread width)
- Validation result with detailed errors

**Test Cases:**
| Test | Input | Expected |
|------|-------|----------|
| Valid recommendation | Strike in chain, constraints met | is_valid=True |
| Invalid strike | Strike not in chain | STRIKE_EXPIRY_MISMATCH error |
| Invalid expiry | Expiry not available | INVALID_EXPIRY error |
| Over max contracts | 20 contracts, limit 10 | EXCEEDS_MAX_CONTRACTS error |
| Under min DTE | 7 DTE, min 14 | INSUFFICIENT_DTE error |

**Acceptance Criteria:**
- [ ] 100% of hallucinated strikes rejected
- [ ] All constraint violations detected
- [ ] Unit test coverage ≥80%

### 9.2 Story C2: Recommendation Persistence (5 points)

**Scope:**
- `recommendations` table migration
- `recommendation_outcomes` table migration
- Repository class with CRUD operations
- Performance view creation

**Test Cases:**
| Test | Input | Expected |
|------|-------|----------|
| Insert recommendation | Valid recommendation | Row persisted |
| Duplicate prevention | Same symbol/date/strategy | Upsert or error |
| Outcome attachment | Outcome for existing rec | Linked correctly |
| Performance query | Date range | Aggregates returned |

**Acceptance Criteria:**
- [ ] Schema deployed to all environments
- [ ] CRUD operations working
- [ ] Performance view queryable
- [ ] Integration tests passing

### 9.3 Story C3: Claude Interface (5 points)

**Scope:**
- `AIProviderBase` abstract class
- `ClaudeProvider` implementation
- `PayloadBuilder` for data assembly
- `RecommendationService` orchestration
- YAML prompt configuration

**Test Cases:**
| Test | Input | Expected |
|------|-------|----------|
| Generate recommendation | Full payload | Valid JSON response |
| Parse JSON response | Claude response | Dict extracted |
| Handle code blocks | ```json wrapped | Cleaned JSON |
| Timeout handling | Slow response | Graceful failure |
| Invalid JSON | Malformed response | ParseError raised |

**Acceptance Criteria:**
- [ ] Claude API integration working
- [ ] Prompt configuration hot-reloadable
- [ ] Response parsing robust
- [ ] Error handling comprehensive
- [ ] Logging complete

---

## 10. RISK ANALYSIS

### 10.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Claude hallucinates strikes | Medium | High | Strict validation layer (C1) |
| API rate limiting | Low | Medium | Retry logic, backoff |
| JSON parsing failures | Medium | Medium | Robust parser, fallback |
| Prompt drift over time | Medium | High | Version control, A/B testing |
| Database bloat | Low | Low | Retention policies |

### 10.2 Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Overfit to recent regime | High | High | Regime-aware evaluation |
| False confidence in backtests | High | High | Paper trading phase |
| Drawdown cascade | Medium | High | Position limits, circuit breakers |
| Model changes (Claude updates) | Medium | Medium | Model pinning, regression tests |

---

## 11. NEXT STEPS

### Immediate (This Week)
1. Review and finalize this spike document
2. Create GitHub issues for C1, C2, C3 with test specs
3. Implement C1 (Strike Validator) - lowest dependency
4. Begin C2 schema migration in parallel

### Short-term (Next 2 Weeks)
1. Complete C2 persistence layer
2. Implement C3 Claude interface
3. Run first live recommendations
4. Begin outcome collection

### Medium-term (Next Month)
1. Accumulate 4+ weeks of scored outcomes
2. First prompt iteration cycle
3. Dashboard for performance monitoring
4. Guardrail refinement

---

## 12. APPENDIX: SAMPLE PROMPTS

### A. Entry Signal Prompt (Bullish)

```
## Current Signal Analysis for NVDA

### Wyckoff Context
- Regime: ACCUMULATION (85% confidence)
- Events: SC → AR → SPRING detected
- Spring Score: 9/12 (HIGH)
- BC Score: 8/28 (LOW - no distribution concern)

### Dealer Context
- Position: SHORT_GAMMA
- GEX Net: -$500M (dealers will amplify moves)
- Gamma Flip: $145 (above current $144.50)
- Call Wall: $150 (first major resistance)
- Put Wall: $135 (strong support)

### Technical Context
- RSI: 45.5 (neutral, room to run)
- MACD: Bullish crossover (histogram positive)
- Price vs SMAs: Above 20/50/200 (trend confirmation)
- ADX: 25.5 (trending, not extreme)

### Volatility Context
- IV Rank: 35 (relatively cheap options)
- IV/HV Spread: +4% (slight premium, acceptable)
- P/C Ratio: 0.85 (slightly bullish positioning)

### Scoring
| Factor | Points |
|--------|--------|
| SPRING detected | +3 |
| ACCUMULATION regime | +2 |
| Dealer short gamma | +2 |
| RSI < 60 | +1 |
| Price > SMA 20 | +1 |
| IV rank < 40 | +1 |
| **TOTAL** | **10** → HIGH CONVICTION |

### Recommended Action
OPEN LONG_CALL
- Strike: 145 (just above gamma flip)
- Expiry: Feb 21 (51 DTE)
- Contracts: 5
- Entry: $5.95 (mid)
- Risk: $2,975 (100% of premium)
- Target: $8.93 (+50%)
- Stop: $3.57 (-40%)
```

---

**END OF SPIKE DOCUMENT**

*This document should be reviewed before writing stories C1-C3.*
