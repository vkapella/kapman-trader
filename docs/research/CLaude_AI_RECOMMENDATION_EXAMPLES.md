# AI Recommendation System - Examples & Test Fixtures

## 1. COMPLETE EXAMPLE: NVDA Bullish Setup

### 1.1 Input Payload (Real Data Format)

This is what gets sent to Claude after assembling data from `daily_snapshots`, `options_chains`, and constraints:

```json
{
  "request_metadata": {
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "timestamp": "2026-01-01T16:00:00Z",
    "symbol": "NVDA",
    "analysis_date": "2026-01-01"
  },
  
  "wyckoff_context": {
    "regime": "ACCUMULATION",
    "regime_confidence": 0.85,
    "events_detected": ["SC", "AR", "SPRING"],
    "primary_event": "SPRING",
    "event_score": 2.3,
    "bc_score": 8,
    "spring_score": 9,
    "sequence_status": "SC→AR→SPRING (awaiting SOS)"
  },
  
  "dealer_context": {
    "status": "FULL",
    "gex_total": 1500000000,
    "gex_net": -500000000,
    "gamma_flip_level": 145.00,
    "call_wall_primary": 150.00,
    "put_wall_primary": 135.00,
    "dealer_position": "short_gamma",
    "confidence": "high"
  },
  
  "technical_context": {
    "rsi_14": 45.5,
    "macd_histogram": 0.28,
    "adx_14": 25.5,
    "price_vs_sma20": "above"
  },
  
  "volatility_context": {
    "iv_rank": 35,
    "average_iv": 0.42,
    "hv_20": 0.38
  },
  
  "available_contracts": {
    "calls": [
      {"strike": 145, "expiry": "2026-02-21", "bid": 5.80, "ask": 6.10, "delta": 0.55}
    ]
  },
  
  "constraints": {
    "max_position_size_usd": 10000,
    "max_contracts": 10,
    "allowed_strategies": ["LONG_CALL", "LONG_PUT", "CASH_SECURED_PUT", "VERTICAL_SPREAD"]
  }
}
```

### 1.2 Expected Claude Response

```json
{
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
      "entry_price_target": 5.95
    },
    
    "position_sizing": {
      "max_risk_usd": 2975,
      "contracts": 5,
      "breakeven": 150.95
    },
    
    "rationale": {
      "primary_thesis": "SPRING event in ACCUMULATION with dealer short gamma creates high-probability bullish setup.",
      "supporting_factors": [
        "Wyckoff SPRING detected (score 9/12)",
        "Dealer short gamma at $145 gamma flip",
        "RSI at 45.5 provides room for expansion",
        "IV rank at 35 makes calls relatively cheap"
      ],
      "risk_factors": [
        "Gamma flip at $145 may act as resistance",
        "BC score at 8 suggests early distribution activity"
      ]
    },
    
    "forecast": {
      "direction": "UP",
      "confidence_pct": 72,
      "expected_move_pct": 8.0,
      "time_horizon_days": 20
    }
  }
}
```

---

## 2. VALIDATION TEST CASES

```python
# tests/fixtures/validation_fixtures.py

VALID_RECOMMENDATION = {
    "recommendation": {
        "action": "OPEN",
        "strategy": "LONG_CALL",
        "conviction": "HIGH",
        "symbol": "NVDA",
        "primary_leg": {
            "type": "CALL",
            "strike": 145,
            "expiry": "2026-02-21",
            "quantity": 5
        },
        "position_sizing": {"contracts": 5, "total_premium_usd": 2975}
    }
}

INVALID_STRIKE_RECOMMENDATION = {
    "recommendation": {
        "primary_leg": {
            "type": "CALL",
            "strike": 147,  # Not in available_contracts
            "expiry": "2026-02-21"
        }
    }
}

SAMPLE_OPTIONS_CHAIN = {
    "expiration_dates": ["2026-01-17", "2026-01-31", "2026-02-21"],
    "available_contracts": {
        "calls": [
            {"strike": 145, "expiry": "2026-02-21"},
            {"strike": 150, "expiry": "2026-02-21"}
        ]
    }
}

SAMPLE_CONSTRAINTS = {
    "max_position_size_usd": 10000,
    "max_contracts": 10,
    "allowed_strategies": ["LONG_CALL", "LONG_PUT", "CASH_SECURED_PUT", "VERTICAL_SPREAD"]
}
```

---

## 3. OUTCOME SCORING TEST CASES

```python
# tests/fixtures/outcome_fixtures.py

# Correct bullish prediction
CORRECT_BULLISH = {
    "predicted_direction": "UP",
    "predicted_confidence": 72,
    "actual_return_20d": 8.5,
    "expected_brier_20d": 0.0784,   # (0.72 - 1.0)^2
    "expected_direction_correct": True
}

# Incorrect bullish prediction
INCORRECT_BULLISH = {
    "predicted_direction": "UP",
    "predicted_confidence": 72,
    "actual_return_20d": -8.0,
    "expected_brier_20d": 0.5184,   # (0.72 - 0.0)^2
    "expected_direction_correct": False
}

# Brier score formula
def calculate_brier_score(confidence_pct: float, direction_correct: bool) -> float:
    probability = confidence_pct / 100.0
    outcome = 1.0 if direction_correct else 0.0
    return (probability - outcome) ** 2
```

---

## 4. PERFORMANCE ANALYSIS QUERIES

### Weekly Dashboard

```sql
SELECT 
    DATE_TRUNC('week', r.analysis_date) as week,
    COUNT(*) as recommendations,
    AVG(CASE WHEN o.direction_correct_20d THEN 100.0 ELSE 0.0 END) as win_rate_pct,
    AVG(o.return_20d_pct) as avg_return_pct,
    AVG(o.brier_20d) as brier_score
FROM recommendations r
JOIN recommendation_outcomes o ON r.id = o.recommendation_id
WHERE r.validation_passed = TRUE
GROUP BY DATE_TRUNC('week', r.analysis_date)
ORDER BY week DESC;
```

### Conviction Calibration

```sql
SELECT 
    r.conviction,
    COUNT(*) as count,
    AVG(r.forecast_confidence_pct) as stated_confidence,
    AVG(CASE WHEN o.direction_correct_20d THEN 100.0 ELSE 0.0 END) as actual_win_rate,
    AVG(r.forecast_confidence_pct) - AVG(CASE WHEN o.direction_correct_20d THEN 100.0 ELSE 0.0 END) as calibration_gap
FROM recommendations r
JOIN recommendation_outcomes o ON r.id = o.recommendation_id
GROUP BY r.conviction;
```

---

## 5. GO-LIVE CHECKLIST

### Pre-Launch
- [ ] Strike validator passes all test fixtures
- [ ] Schema deployed to all environments
- [ ] Claude API authentication working
- [ ] JSON parsing handles edge cases

### First Week
- [ ] Review every recommendation manually
- [ ] Track validation failures (target: 0)
- [ ] Monitor API latency
- [ ] Verify outcome collection running

### First Month Targets
| Metric | Target |
|--------|--------|
| Recommendations | 50+ |
| Validation pass rate | 100% |
| Win rate (20d) | >55% |
| Brier score | <0.30 |

---

**END OF EXAMPLES**
