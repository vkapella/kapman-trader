# Wyckoff Portfolio Tracker

## Overview

This full-stack web application tracks stock portfolios using Wyckoff analysis and options trading strategies. It integrates with the Polygon.io API wrapper and a custom Wyckoff analysis module to provide daily forecasts and trade recommendations. Users can manage multiple portfolios, track securities, and view comprehensive Wyckoff analysis dashboards with technical indicators and dealer positioning. A daily job automates analysis and stores historical snapshots for performance tracking. The project aims to provide a trustworthy fintech solution for informed trading decisions.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Framework:** React with TypeScript, Vite, and Shadcn/ui (New York style) based on Radix UI and Tailwind CSS for a clean fintech aesthetic.

**Routing:** Wouter for client-side routing, including Dashboard, Portfolio, Ticker, and All Tickers views.

**State Management:** TanStack Query for server state management; component-level state with React hooks.

**Key Components:** TickerDetail for comprehensive analysis, WyckoffChecklistPanel, TechnicalMetricsPanel, DealerMetricsPanel, and a multi-tab interface for various data views.

**Design Decisions:** Component-based architecture, type-safe API abstraction, shared type definitions, responsive design, real-time data refresh, resizable table columns, and E2E testing attributes.

### Backend Architecture

**Runtime:** Node.js with Express.js REST API.

**Language:** TypeScript with ES modules.

**API Design:** RESTful endpoints for portfolios, tickers, daily snapshots, and job management.

**Design Decisions:** Storage abstraction (repository pattern), service layer for external integrations (Wyckoff, Polygon, OpenAI), scheduled daily analysis jobs, Zod schema validation, Wyckoff-based fallback for OpenAI, 30-second API call timeouts, and non-blocking optional data collection with graceful error handling.

### Data Storage

**Database:** PostgreSQL (Neon serverless driver) with Drizzle ORM.

**Schema Design:** Includes `portfolios`, `tickers`, `portfolio_tickers`, `daily_snapshots` (capturing Wyckoff analysis, market metrics, technical indicators, dealer metrics, volatility metrics, and AI forecasts), and `forecast_evaluations` (for future accuracy tracking).

**Design Decisions:** Normalized relational schema, indexed symbols and dates, comprehensive JSONB fields for metrics, timestamp tracking, and Zod schema generation from Drizzle.

### System Design Choices

The application uses a microservices-like approach with dedicated services for external API interactions and Wyckoff analysis. It prioritizes data integrity and availability through fallbacks (e.g., Wyckoff for OpenAI) and robust error handling. The daily job processes tickers concurrently with rate limiting and exponential backoff for API stability.

## External Dependencies

**Market Data Services:**
- **Polygon.io API (Unified):** All market data now flows through `https://kapman-polygon-apix-wrapper.replit.app`:
  - Real-time and historical OHLCV data
  - Technical indicators (RSI, MACD, SMA, EMA, Bollinger Bands, Stochastic, ATR)
  - Wyckoff price/volume metrics (Relative Volume, Volume Surge Index, Historical Volatility, HV-IV Diff)
  - Options chain data (expirations, strikes) via Polygon passthrough
  - Dealer metrics (GEX, Gamma Flip, Put/Call walls) derived from options snapshot
  - Volatility metrics mapped from Wyckoff price metrics
- **Wyckoff Analysis Module:** Custom service for Wyckoff phase determination via `https://kapman-wyckoff-analysis-module-v2.replit.app`.
- **OpenAI API:** GPT-4 integration for contextual trade recommendations, with a Wyckoff-based fallback. Batch jobs use `gpt-5-mini`, while on-demand analysis uses `gpt-4.1`.

## Recent Changes & Enforcement (December 1, 2025)

**CRITICAL REQUIREMENT ENFORCED: Real-Data-Only Strikes**
- User explicitly requires: NO AI-generated strikes. AI must select best strikes/expiration dates FROM SCHWAB DATA ONLY.
- Fixed Schwab CSV parser to correctly read columns: exp(2), strike(4), type(5)
- Updated `kapmanAiService.ts` to throw errors if no real Schwab strike data is available
- All forecasts now fail-fast if Schwab data is empty, preventing AI hallucination

**Updated Guardrails (server/guardrails/compact/Kapman_Policy_Compact.md)**
- Section 5a: Complete rewrite with Wyckoff-aware strike/expiration selection rules
- Strike Selection: AI MUST use only callStrikes, putStrikes, or allStrikes from real market data
- Expiration Selection: AI applies Wyckoff phase-aware DTE selection:
  - Accumulation: 30-45 DTE (entry), 45-90 DTE (swing), 10-14 months (LEAPS)
  - Markup: 30-60 DTE (momentum), 60-90 DTE (swing), 10-14 months (LEAPS)
  - Distribution: 30-45 DTE (trim/hedge), 45-90 DTE (swing), 10-14 months (LEAPS)
  - Markdown: 30-45 DTE (protection), 45-90 DTE (swing), 10-14 months (LEAPS)
- Strike Confidence Rules: ATM for swing, OTM calls in bullish phases, OTM puts in defensive phases

**Updated AI Prompt (server/services/kapmanAiService.ts)**
- Explicitly instructs AI to apply Wyckoff-aware best practices
- Specifies exact DTE ranges per Wyckoff phase
- Prohibits hallucination: "DO NOT hallucinate, estimate, or generate strikes outside provided data"
- Requires: "If perfect match unavailable, select closest real strikes and note adjustment in 'notes'"

**Fixed Dealer Metrics Display (server/routes.ts)**
- Fixed `normalizeDealerMetrics()` to extract Put/Call OI from `metadata.put_count` and `metadata.call_count`
- Dealer metrics now display accurate Put/Call OI ratios instead of all 0s

**Schwab Gamma_Flip Algorithm Corrected (December 1, 2025)**
- **Issue:** Old algorithm weighted gamma by open interest (OI), causing cumulative gamma values to be astronomically large and returning unrealistic strike prices far from current price (e.g., $80 flip when price is $509)
- **Fix Applied by Schwab:**
  - Removed OI weighting: Uses raw gamma values directly (already normalized Greeks)
  - Finds actual zero crossings: Looks for where cumulative gamma transitions from positive to negative
  - Returns realistic strikes: Now returns strikes very close to current price (as intended)
- **Code Updated:** Removed validation filter in `normalizeDealerMetrics()`, now trusts Gamma_Flip values directly since they're accurate strike prices

**Fixed Issues (December 1, 2025 - Evening)**
- **Unrealistic Gamma Flip Strikes**: Fixed by making dealer metrics conditional on options chain availability
  - Problem: Gamma flip was calculated for symbols with no tradable options, causing unrealistic strikes
  - Solution: Only fetch dealer metrics if options chain has real strike data (`allStrikes.length > 0`)
  - Impact: Gamma flip now only displays for symbols with real market options

## Migration: Schwab → Polygon (December 3, 2025)

**Completed Migration:**
- Replaced Schwab API with unified Polygon.io API wrapper for all options/dealer/volatility data
- `server/services/polygon.ts` extended with new endpoints:
  - `getOptionsChain(symbol)` - Uses Polygon passthrough to `/v3/reference/options/contracts`
  - `getDealerMetrics(symbols)` - Uses Polygon passthrough to `/v3/snapshot/options/{underlying}`, derives GEX from gamma*OI
  - `getVolatilityMetrics(symbols)` - Maps from Wyckoff price metrics (Historical_Volatility, HV_IV_Diff)
- `server/services/dailyJob.ts` updated to use polygonService instead of schwabService
- `server/routes.ts` updated for on-demand forecasts to use Polygon options chain
- `server/services/kapmanAiService.ts` comments updated to reference Polygon

**Benefits:**
- Single API source reduces complexity and potential points of failure
- Polygon has broader symbol coverage than Schwab
- Unified authentication (KAPMAN_AUTHENTICATION_TOKEN)

**Known Limitations:**
- Dealer metrics (GEX, Gamma Flip) derived from Polygon options snapshot data
- Some Polygon endpoints may require upgraded plan for real-time data
- Options chain data limited to 1000 contracts per request

## STEP 3C: Registry-Driven Structural Config (December 3, 2025)

**Implemented Registry-Driven Wyckoff Config System:**
- Centralized config management via kapman-registry service
- Version-aware configs (structural_v1, v2, etc.) for A/B testing analysis parameters
- 5-minute in-memory caching to reduce network latency
- Graceful fallback to `server/registry_cache/wyckoff_config.json` if registry unavailable

**New Files:**
- `server/services/wyckoffStructuralConfigRegistry.ts` - Registry client with caching
  - Fetches from `/api/configs/wyckoff/structural/{configId}`
  - Uses KAPMAN_REGISTRY_URL and KAPMAN_AUTHENTICATION_TOKEN

**Updated Files:**
- `server/services/wyckoffStructuralClient.ts` - Added configId/paramsOverride support
- `server/services/wyckoffStructuralIngest.ts` - Fetches registry config before analysis

**Environment Variables:**
- KAPMAN_REGISTRY_URL = https://KapMan-Registry.replit.app
- KAPMAN_AUTHENTICATION_TOKEN (shared across services)
