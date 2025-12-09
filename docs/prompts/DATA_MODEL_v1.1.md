# KAPMAN TRADING SYSTEM - DATA MODEL v1.1
## Enhanced Schema Reference (Post Sprint 1 Refactor)

**Version:** 1.1  
**Date:** December 9, 2025  
**Status:** Ready for Sprint 2 Implementation

---

## Schema Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KAPMAN DATA MODEL v1.1                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  UNIVERSE LAYER (All ~15K Tickers)                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ohlcv_daily (TimescaleDB Hypertable)                               │   │
│  │  • Full Polygon universe stored                                      │   │
│  │  • 3-year retention, compressed after 1 year                        │   │
│  │  • ~15K tickers × 252 days × 3 years = ~11M rows/year               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  WATCHLIST LAYER (50-100 Tracked Tickers)                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  options_chains          → Raw contract-level data                  │   │
│  │  options_daily_summary   → Aggregated OI, Greeks, GEX per symbol    │   │
│  │  daily_snapshots         → Wyckoff + all metrics (enhanced)         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  RECOMMENDATION LAYER                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  recommendations         → Trade suggestions with justification     │   │
│  │  recommendation_outcomes → Accuracy tracking (Brier scores)         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  REFERENCE LAYER                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  tickers                 → Universe with tier classification        │   │
│  │  portfolios              → Watchlist groupings                      │   │
│  │  portfolio_tickers       → Many-to-many with priority               │   │
│  │  model_parameters        → Algorithm version control                │   │
│  │  job_runs                → Pipeline audit trail                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Table: daily_snapshots (Enhanced)

The central table for all analysis results. Now includes 45+ columns organized by category.

### Column Reference

| Category | Column | Type | Description | Source |
|----------|--------|------|-------------|--------|
| **Identity** | time | TIMESTAMPTZ | Snapshot timestamp | System |
| | symbol | VARCHAR(20) | Ticker symbol | System |
| **Wyckoff Phase** | wyckoff_phase | CHAR(1) | Phase A-E | Wyckoff Engine |
| | phase_score | NUMERIC(4,3) | Phase confidence score | Wyckoff Engine |
| | phase_confidence | NUMERIC(4,3) | Overall confidence | Wyckoff Engine |
| | phase_sub_stage | VARCHAR(20) | Sub-stage detail | Wyckoff Engine |
| **Wyckoff Events** | events_detected | VARCHAR(20)[] | Array of events | Wyckoff Engine |
| | primary_event | VARCHAR(20) | Most significant event | Wyckoff Engine |
| | primary_event_confidence | NUMERIC(4,3) | Event confidence | Wyckoff Engine |
| | events_json | JSONB | Detailed event data | Wyckoff Engine |
| **Wyckoff Scores** | bc_score | INTEGER | Buying Climax (0-28) | Wyckoff Engine |
| | spring_score | INTEGER | Spring (0-12) | Wyckoff Engine |
| | composite_score | NUMERIC(4,3) | Combined score | Wyckoff Engine |
| **Technical - Momentum** | rsi_14 | NUMERIC(6,2) | 14-period RSI | Polygon MCP |
| | macd_line | NUMERIC(12,4) | MACD line | Polygon MCP |
| | macd_signal | NUMERIC(12,4) | MACD signal | Polygon MCP |
| | macd_histogram | NUMERIC(12,4) | MACD histogram | Polygon MCP |
| | stoch_k | NUMERIC(6,2) | Stochastic %K | Polygon MCP |
| | stoch_d | NUMERIC(6,2) | Stochastic %D | Polygon MCP |
| | mfi_14 | NUMERIC(6,2) | Money Flow Index | Polygon MCP |
| **Technical - Trend** | sma_20 | NUMERIC(12,4) | 20-day SMA | Polygon MCP |
| | sma_50 | NUMERIC(12,4) | 50-day SMA | Polygon MCP |
| | sma_200 | NUMERIC(12,4) | 200-day SMA | Polygon MCP |
| | ema_12 | NUMERIC(12,4) | 12-day EMA | Polygon MCP |
| | ema_26 | NUMERIC(12,4) | 26-day EMA | Polygon MCP |
| | adx_14 | NUMERIC(6,2) | ADX trend strength | Polygon MCP |
| **Technical - Volatility** | atr_14 | NUMERIC(12,4) | 14-day ATR | Polygon MCP |
| | bbands_upper | NUMERIC(12,4) | Bollinger upper | Polygon MCP |
| | bbands_middle | NUMERIC(12,4) | Bollinger middle | Polygon MCP |
| | bbands_lower | NUMERIC(12,4) | Bollinger lower | Polygon MCP |
| | bbands_width | NUMERIC(8,4) | Band width % | Calculated |
| **Technical - Volume** | obv | BIGINT | On-Balance Volume | Polygon MCP |
| | vwap | NUMERIC(12,4) | VWAP | OHLCV data |
| **Dealer Metrics** | gex_total | NUMERIC(18,2) | Total Gamma Exposure | Polygon MCP |
| | gex_net | NUMERIC(18,2) | Net directional GEX | Polygon MCP |
| | gamma_flip_level | NUMERIC(12,4) | Gamma flip price | Polygon MCP |
| | call_wall_primary | NUMERIC(12,2) | Top call OI strike | Polygon MCP |
| | call_wall_primary_oi | INTEGER | OI at call wall | Polygon MCP |
| | put_wall_primary | NUMERIC(12,2) | Top put OI strike | Polygon MCP |
| | put_wall_primary_oi | INTEGER | OI at put wall | Polygon MCP |
| | dgpi | NUMERIC(5,2) | Dealer Gamma Pressure Index | Polygon MCP |
| | dealer_position | VARCHAR(15) | long_gamma/short_gamma/neutral | Polygon MCP |
| **Volatility Metrics** | iv_skew_25d | NUMERIC(6,4) | 25-delta IV skew | Polygon MCP |
| | iv_term_structure | NUMERIC(6,4) | IV term structure | Polygon MCP |
| | put_call_ratio_oi | NUMERIC(6,4) | P/C ratio (OI) | Polygon MCP |
| | put_call_ratio_volume | NUMERIC(6,4) | P/C ratio (volume) | Polygon MCP |
| | average_iv | NUMERIC(6,4) | Weighted avg IV | Polygon MCP |
| | iv_rank | NUMERIC(5,2) | IV rank (0-100) | Calculated |
| | iv_percentile | NUMERIC(5,2) | IV percentile | Calculated |
| **Price Metrics** | rvol | NUMERIC(8,4) | Relative Volume | Polygon MCP |
| | vsi | NUMERIC(8,4) | Volume Surge Index | Polygon MCP |
| | hv_20 | NUMERIC(6,4) | 20-day HV | Polygon MCP |
| | hv_60 | NUMERIC(6,4) | 60-day HV | Polygon MCP |
| | iv_hv_diff | NUMERIC(6,4) | IV minus HV | Calculated |
| | price_vs_sma20 | NUMERIC(6,4) | Price % from SMA20 | Calculated |
| | price_vs_sma50 | NUMERIC(6,4) | Price % from SMA50 | Calculated |
| | price_vs_sma200 | NUMERIC(6,4) | Price % from SMA200 | Calculated |
| **JSONB Storage** | technical_indicators_json | JSONB | All 84 indicators | Polygon MCP |
| | dealer_metrics_json | JSONB | Full dealer data | Polygon MCP |
| | volatility_metrics_json | JSONB | Full vol data | Polygon MCP |
| | price_metrics_json | JSONB | Full price data | Polygon MCP |
| | checklist_json | JSONB | Wyckoff checklist | Wyckoff Engine |
| **Metadata** | volatility_regime | VARCHAR(20) | low/normal/high/extreme | Calculated |
| | model_version | VARCHAR(50) | Algorithm version | System |
| | data_quality | VARCHAR(20) | complete/partial/stale | System |
| | created_at | TIMESTAMPTZ | Record creation | System |

---

## Table: options_daily_summary (New)

Aggregated options metrics per symbol per day. Source data for dealer calculations.

| Column | Type | Description |
|--------|------|-------------|
| time | TIMESTAMPTZ | Snapshot date |
| symbol | VARCHAR(20) | Ticker symbol |
| total_call_oi | INTEGER | Sum of all call OI |
| total_put_oi | INTEGER | Sum of all put OI |
| total_oi | INTEGER | Generated: call + put OI |
| total_call_volume | INTEGER | Sum of all call volume |
| total_put_volume | INTEGER | Sum of all put volume |
| total_volume | INTEGER | Generated: call + put volume |
| put_call_oi_ratio | NUMERIC(6,4) | Generated: put OI / call OI |
| put_call_volume_ratio | NUMERIC(6,4) | Generated: put vol / call vol |
| weighted_avg_iv | NUMERIC(6,4) | OI-weighted average IV |
| top_call_strike_1/2/3 | NUMERIC(12,2) | Top 3 call strikes by OI |
| top_call_oi_1/2/3 | INTEGER | OI at top call strikes |
| top_put_strike_1/2/3 | NUMERIC(12,2) | Top 3 put strikes by OI |
| top_put_oi_1/2/3 | INTEGER | OI at top put strikes |
| total_call_gamma | NUMERIC(18,8) | Aggregate call gamma |
| total_put_gamma | NUMERIC(18,8) | Aggregate put gamma |
| total_call_delta | NUMERIC(18,8) | Aggregate call delta |
| total_put_delta | NUMERIC(18,8) | Aggregate put delta |
| calculated_gex | NUMERIC(18,2) | Computed GEX |
| calculated_net_gex | NUMERIC(18,2) | Computed Net GEX |
| nearest_expiry | DATE | Closest expiration |
| expirations_count | INTEGER | Number of expirations |
| contracts_analyzed | INTEGER | Total contracts |
| data_completeness | NUMERIC(4,3) | Quality score (0-1) |

**Retention:** 90 days

---

## Table: tickers (Enhanced)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| symbol | VARCHAR(20) | Ticker symbol (unique) |
| name | VARCHAR(255) | Company name |
| sector | VARCHAR(100) | Sector classification |
| is_active | BOOLEAN | Include in universe |
| **universe_tier** | VARCHAR(20) | sp500/russell3000/polygon_full/custom/etf/index |
| **last_ohlcv_date** | DATE | Most recent OHLCV loaded |
| **last_analysis_date** | DATE | Most recent Wyckoff analysis |
| **options_enabled** | BOOLEAN | Fetch options data |
| created_at | TIMESTAMPTZ | Record creation |
| updated_at | TIMESTAMPTZ | Last update |

---

## Helper Views

### v_latest_snapshots
Most recent snapshot per symbol with key metrics for dashboard display.

### v_watchlist_tickers  
Tickers in portfolios requiring daily analysis, with priority.

### v_alerts
Active alert conditions:
- BC_CRITICAL: BC Score >= 24
- BC_WARNING: BC Score >= 20
- SPRING_ENTRY: Spring Score >= 9 with low BC
- VOLUME_SURGE: VSI > 2

---

## Helper Functions

### fn_symbols_needing_ohlcv(target_date)
Returns symbols that need OHLCV data loaded for the target date.

### fn_watchlist_needing_analysis(target_date)
Returns watchlist symbols that have fresh OHLCV but need analysis.

---

## Index Strategy

| Index | Purpose | Query Pattern |
|-------|---------|---------------|
| idx_snapshots_rsi | RSI screening | WHERE rsi_14 < 30 |
| idx_snapshots_adx | Trend strength | WHERE adx_14 > 25 |
| idx_snapshots_dgpi | Dealer pressure | WHERE dgpi > 50 |
| idx_snapshots_gamma_flip | Gamma flip alerts | WHERE close > gamma_flip_level |
| idx_snapshots_iv | IV screening | WHERE average_iv > 0.5 |
| idx_snapshots_pcr | Sentiment | WHERE put_call_ratio_oi > 1.5 |
| idx_snapshots_rvol | Volume confirmation | WHERE rvol > 2.0 |
| idx_snapshots_vsi | Volume surge | WHERE vsi > 2 |
| idx_snapshots_wyckoff_volume | Event + volume | Wyckoff event with high RVOL |

---

## Data Flow

```
Daily Pipeline (4:00 AM ET)
│
├─► Phase 1: S3 OHLCV Load (30 sec)
│   └─► Download us_stocks_sip/day_aggs
│   └─► INSERT all ~15K tickers to ohlcv_daily
│   └─► UPDATE tickers.last_ohlcv_date
│
├─► Phase 2: Watchlist Enrichment (5-10 min)
│   └─► For each watchlist ticker:
│       ├─► Polygon API: Options Snapshot (OI + Greeks + IV)
│       ├─► INSERT to options_chains
│       ├─► AGGREGATE to options_daily_summary
│       ├─► Polygon MCP: get_all_ta_indicators
│       ├─► Polygon MCP: get_dealer_metrics
│       ├─► Polygon MCP: get_volatility_metrics
│       └─► Polygon MCP: get_price_metrics
│
├─► Phase 3: Wyckoff Analysis (2-5 min)
│   └─► For each watchlist ticker:
│       ├─► Phase classification
│       ├─► Event detection (8 events)
│       ├─► BC/Spring scoring
│       └─► INSERT to daily_snapshots (all columns)
│
├─► Phase 4: Recommendations (5-10 min)
│   └─► For P1 tickers with actionable signals:
│       ├─► Claude API: Generate recommendation
│       └─► INSERT to recommendations
│
└─► Phase 5: Notifications
    └─► Email daily summary
    └─► Alert on BC >= 24
```

---

## Storage Estimates

| Table | Rows/Day | Rows/Year | Size/Year |
|-------|----------|-----------|-----------|
| ohlcv_daily | 15,000 | 3.8M | ~2GB |
| options_chains | 50,000 | 12.6M | ~5GB |
| options_daily_summary | 100 | 25K | ~50MB |
| daily_snapshots | 100 | 25K | ~100MB |
| recommendations | 10 | 2.5K | ~10MB |

**Total:** ~7-8GB/year (before compression)
**After compression (1 year):** ~2-3GB/year
