---
system: KapMan
doc_type: strategy
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strong
tags:
  - pipeline
  - orchestration
  - dependencies
  - scheduling
---

# PIPELINE_ORCHESTRATION

## [KapMan] Objective
Capture implemented pipeline phase ordering, dependency gates, and sequencing constraints across daily and catch-up execution scripts.

## [KapMan] Decision Table
| Script | Implemented Order |
|---|---|
| `scripts/cron/kapman_daily_run.sh` | A1 watchlist -> A0 OHLCV -> A1 options -> A2 -> A4 -> A3 -> B2 -> B1 -> B4 -> B4.1 -> dashboards |
| `scripts/cron/catchup_START_DATE_to_END_DATE.sh` | A0 -> A1 -> A2 -> A4 -> A3 -> B2 -> B1 -> B4 -> B4.1 |
| `scripts/cron/resume-from-A3.sh` | A3 -> B2 -> B1 -> B4 -> B4.1 |

| B2 Dependency Gate | Rule |
|---|---|
| Driver dates | Use existing `daily_snapshots` NY dates, not prior B2 output |
| Snapshot coverage | Fail fast unless every `(ticker, target_date)` snapshot exists |
| OHLCV quality | Reject duplicate/non-monotonic/gapped (`>4` days) histories |

## [KapMan] Rule Catalog
### RULE PIPELINE_001
RULE_ID: PIPELINE_001  
SOURCE_FILE: scripts/cron/kapman_daily_run.sh  
SOURCE_LINE: 95-176  
CATEGORY: Strategy  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Daily cron execution enforces full stage order ending with B4 before B4.1.
LOGIC:
- IF: Running daily cron path
- THEN: Execute A-stage metrics before B-stage Wyckoff modules
- AND: Run B4 before B4.1
- THRESHOLD: Fixed script order
CONTEXT: Defines canonical daily orchestration path for production runbook.

### RULE PIPELINE_002
RULE_ID: PIPELINE_002  
SOURCE_FILE: scripts/cron/catchup_START_DATE_to_END_DATE.sh  
SOURCE_LINE: 13-23, 53-142  
CATEGORY: Strategy  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Catch-up orchestration runs B4 before B4.1.
LOGIC:
- IF: Running catch-up script
- THEN: Execute B4 derived aggregation before B4.1 sequence generation
- THRESHOLD: Fixed script order
CONTEXT: Matches the daily and resume execution paths.

### RULE PIPELINE_003
RULE_ID: PIPELINE_003  
SOURCE_FILE: scripts/cron/resume-from-A3.sh  
SOURCE_LINE: 6-44  
CATEGORY: Strategy  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Resume-from-A3 path executes A3 first, then B2/B1, then B4 before B4.1.
LOGIC:
- IF: Resuming pipeline from A3
- THEN: Run A3 -> B2 -> B1 -> B4 -> B4.1
- THRESHOLD: Fixed script order
CONTEXT: Matches daily-run B4-before-B4.1 ordering.

### RULE PIPELINE_004
RULE_ID: PIPELINE_004  
SOURCE_FILE: core/metrics/b2_wyckoff_structural_events_job.py  
SOURCE_LINE: 97-132, 135-177, 421-426  
CATEGORY: Strategy  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: B2 uses authoritative daily snapshot dates and requires complete per-date snapshot coverage before processing.
LOGIC:
- IF: Running B2
- THEN: Load target dates from `daily_snapshots` in NY time
- AND: Verify each target date has all requested ticker snapshots
- IF: Any date is incomplete
- THEN: Raise error and stop
- THRESHOLD: Full ticker coverage required per target date
CONTEXT: Prevents synthetic B2 rows when upstream snapshot state is incomplete.

### RULE PIPELINE_005
RULE_ID: PIPELINE_005  
SOURCE_FILE: core/metrics/b2_wyckoff_structural_events_job.py  
SOURCE_LINE: 180-182, 241-245  
CATEGORY: Strategy  
RULE_TYPE: Formula  
CONFIDENCE: STRONG  
DESCRIPTION: B2 OHLCV lookback start is extended by `required_bars * 3` days to absorb weekends/holidays.
LOGIC:
- IF: Computing OHLCV fetch window for B2
- THEN: `required_bars = max(min_bars_in_range, range_lookback, vol_lookback, lookback_trend)`
- AND: `lookback_start = start_date - required_bars*3 days`
- THRESHOLD: Multiplier `3`
CONTEXT: Reduces underfetch risk without trading-calendar dependency.

### RULE PIPELINE_006
RULE_ID: PIPELINE_006  
SOURCE_FILE: core/metrics/b2_wyckoff_structural_events_job.py  
SOURCE_LINE: 355-370, 448-457  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: B2 rejects OHLCV series with empty data, missing/null dates, duplicate dates, non-monotonic ordering, or gaps above limit.
LOGIC:
- IF: Any contiguity check fails
- THEN: Skip ticker and count data-quality error
- THRESHOLD: `MAX_GAP_DAYS = 4`
CONTEXT: Protects event detection from broken time series continuity.

### RULE PIPELINE_007
RULE_ID: PIPELINE_007  
SOURCE_FILE: core/metrics/b4_wyckoff_derived_job.py  
SOURCE_LINE: 539-540, 598-606  
CATEGORY: Strategy  
RULE_TYPE: Conditional  
CONFIDENCE: STRONG  
DESCRIPTION: Snapshot evidence writing in B4 is feature-gated.
LOGIC:
- IF: `include_evidence == True`
- THEN: Build and persist `wyckoff_snapshot_evidence`
- ELSE: Skip evidence row generation
- THRESHOLD: Boolean gate default false unless CLI flag provided
CONTEXT: Allows operational control over enriched downstream evidence payload.

### RULE PIPELINE_008
RULE_ID: PIPELINE_008  
SOURCE_FILE: core/metrics/b4_1_wyckoff_sequences_job.py  
SOURCE_LINE: 371-393, 484  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: B4.1 fails fast if required tables are missing.
LOGIC:
- IF: Any required table in `{daily_snapshots, wyckoff_regime_transitions, wyckoff_sequences, wyckoff_sequence_events}` is absent
- THEN: Raise runtime error before ticker loop
- THRESHOLD: All required tables must exist
CONTEXT: Prevents partial sequence writes against incomplete schema.

### RULE PIPELINE_009
RULE_ID: PIPELINE_009  
SOURCE_FILE: scripts/cron/kapman_daily_run.sh; scripts/cron/catchup_START_DATE_to_END_DATE.sh; scripts/cron/resume-from-A3.sh  
SOURCE_LINE: 159-175; 126-142; 29-44  
CATEGORY: Strategy  
RULE_TYPE: Classification  
CONFIDENCE: STRONG  
DESCRIPTION: B4/B4.1 ordering is consistent across scripts.
LOGIC:
- IF: Running any supported orchestration script
- THEN: B4 runs before B4.1
- THRESHOLD: N/A
CONTEXT: Canonical sequences always evaluate after derived transition facts are available.

---
### RULE PIPELINE_010
RULE_ID: PIPELINE_010
SOURCE_FILE: polygon_mcp_server (external API)
SOURCE_LINE: N/A
CATEGORY: Strategy
RULE_TYPE: Constraint
CONFIDENCE: STRICT
DESCRIPTION: Polygon MCP tool surface consolidated 2026-03-28. All legacy
single-symbol endpoints are deprecated. Use canonical endpoints for all
Pass 1 screening to minimize tool turns and context window consumption.
LOGIC:
- IF: Fetching IV / volatility metrics for 1 symbol
- THEN: Use get_options_metrics(symbol, include=["volatility"])
- IF: Fetching IV / volatility metrics for 2+ symbols
- THEN: Use get_batch_options_metrics(symbols=[], include=["volatility"])
- AND: Max 30 symbols per call. Validated 30/30, 0 errors, 2026-03-28.
- IF: Fetching HV / price metrics for 1 symbol
- THEN: Use get_options_metrics(symbol, include=["price"])
- IF: Fetching HV / price metrics for 2+ symbols
- THEN: Use get_batch_options_metrics(symbols=[], include=["price"])
- IF: Fetching Polygon dealer metrics for 1 symbol
- THEN: Use get_options_metrics(symbol, include=["dealer"])
- IF: Fetching Polygon dealer metrics for 2+ symbols
- THEN: Use get_batch_options_metrics(symbols=[], include=["dealer"])
- NOTE: Schwab dealer metrics remain authoritative for Pass 2 per DEALER_012.
  Polygon dealer metrics are directional-hint only (stale spot price anchoring).
- IF: Fetching technical indicators for 1 symbol
- THEN: Use get_technical_analysis(symbol, mode="common") for standard set
- OR: Use get_technical_analysis(symbol, mode="single", indicator="adx") for ADX/DI+/DI-
- IF: Fetching technical indicators for 2+ symbols
- THEN: Use get_batch_technical_analysis(symbols=[], mode="common")
- AND: Default max 30 symbols per call per Polygon MCP canonical batch guidance.
- IF: Fetching OHLCV / price history for 1 symbol
- THEN: Use get_symbol_data(symbol, data_type="aggregates", timespan="day", limit=200)
- IF: Fetching OHLCV / price history for 2+ symbols
- THEN: Use get_batch_symbol_data(symbols=[], data_type="aggregates", timespan="day", limit=200)
- NEVER: Call get_volatility_metrics — deprecated 2026-03-28
- NEVER: Call get_price_metrics — deprecated 2026-03-28
- NEVER: Call get_technical_indicators — deprecated 2026-03-28
- NEVER: Call get_single_indicator — deprecated 2026-03-28
- NEVER: Call get_indicator_by_category — deprecated 2026-03-28
- NEVER: Call get_all_ta_indicators — deprecated 2026-03-28
- NEVER: Call get_stock_aggregates — deprecated 2026-03-28
- NEVER: Call get_batch_quotes — deprecated 2026-03-28
- NEVER: Call get_batch_stock_aggregates — deprecated 2026-03-28
- NEVER: Call get_batch_options_metrics with more than 30 symbols
- NEVER: Call get_batch_technical_analysis with more than the Polygon MCP canonical batch max (default 30 symbols unless server-configured otherwise)
PERFORMANCE:
- Batch vs sequential (30 symbols): 1 tool call vs 30 (97% turn reduction)
- Token overhead reduction: ~41% (envelope/wrapper savings; payload identical)
- Latency: ~3-5s batch vs ~45-60s sequential
CONTEXT: Consolidates all Polygon MCP tool routing decisions into a single
authoritative rule. Supersedes scattered per-tool guidance in external
references. get_batch_technical_analysis previously documented as unreliable
— that caveat is retracted as of 2026-03-28; batch TA is now stable.
---

### RULE PIPELINE_011
RULE_ID: PIPELINE_011
SOURCE_FILE: claude_api (platform behavior)
SOURCE_LINE: N/A
CATEGORY: Strategy
RULE_TYPE: Constraint
CONFIDENCE: STRICT
DESCRIPTION: Context compaction may summarize early tool results in long
sessions. Always re-fetch live dealer metrics at Pass 2 regardless of
whether Pass 1 data appears present in context.
LOGIC:
- IF: Running Pass 2 dealer validation (Schwab get_dealer_metrics)
- THEN: Always call get_dealer_metrics fresh — do NOT reuse Pass 1
  values even if they appear visible in conversation history
- REASON: Claude Sonnet 4.6 / Opus 4.6 context compaction (beta,
  2026-03) auto-summarizes earlier conversation turns when context
  grows large. Compacted numeric values (DGPI, flip levels, GEX) may
  be rounded or approximated in the summary. Pass 2 requires
  authoritative live values.
- NEVER: Carry forward Pass 1 Schwab dealer output as authoritative
  for Pass 2 strike selection or SIGNAL_008 spread decisions
CONTEXT: Compaction is active in beta for Sonnet 4.6 and Opus 4.6 as
of 2026-03. Long screening sessions (30+ tickers) are most at risk.
This rule is a hard operational guard, not a soft recommendation.

### RULE PIPELINE_012
RULE_ID: PIPELINE_012
SOURCE_FILE: claude_code (MCP platform behavior)
SOURCE_LINE: N/A
CATEGORY: Strategy
RULE_TYPE: Constraint
CONFIDENCE: STRONG
DESCRIPTION: MCP tool result size may truncate large options chains
silently. The _meta["anthropic/maxResultSizeChars"] annotation raises
the ceiling to 500K characters when set on the MCP server side.
LOGIC:
- IF: Schwab get_option_chain or get_advanced_option_chain returns a
  chain that appears truncated (missing far strikes, incomplete expiry
  coverage, or fewer contracts than expected)
- THEN: Suspect MCP result size truncation
- AND: Reduce strike_count parameter and re-call, OR split into
  multiple targeted expiry calls
- NOTE: The 500K override requires annotation on the MCP server side.
  If your Schwab MCP instance does not expose this annotation, the
  practical workaround is smaller strike_count batches (8-10 vs 14-16).
- NEVER: Assume a truncated chain is a complete chain for DEALER_012
  quality classification (Full / Limited / Invalid)
CONTEXT: Claude Code MCP servers support
_meta["anthropic/maxResultSizeChars"] up to 500K as of 2026-04.
Large options chains for high-OI names (SPY, NVDA, AAPL) are most
likely to hit default truncation thresholds.

## [KapMan] Anti-Patterns
- NEVER run B2 without upstream daily snapshot coverage checks.
- NEVER assume B4 and B4.1 order is uniform across all orchestration scripts.
- NEVER ignore OHLCV contiguity errors when running structural event detection.
- NEVER assume evidence rows are always present; they are gated by `include_evidence`.
- NEVER call deprecated Polygon endpoints (get_volatility_metrics,
  get_price_metrics, get_technical_indicators, get_single_indicator,
  get_stock_aggregates, etc.) — use canonical replacements per PIPELINE_010.
- NEVER call get_batch_options_metrics with more than 30 symbols.
- NEVER call get_batch_technical_analysis with more than the Polygon MCP canonical batch max (default 30 symbols unless server-configured otherwise).
- NEVER reuse Pass 1 Schwab dealer metrics for Pass 2 validation —
  always re-fetch live (PIPELINE_011, compaction guard).
- NEVER assume a Schwab chain result is complete if strike count is
  lower than requested — suspect MCP truncation (PIPELINE_012).

## [KapMan] Source Mapping
- `scripts/cron/kapman_daily_run.sh`: 95-176
- `scripts/cron/catchup_START_DATE_to_END_DATE.sh`: 13-23, 53-142
- `scripts/cron/resume-from-A3.sh`: 6-44
- `core/metrics/b2_wyckoff_structural_events_job.py`: 97-132, 135-182, 241-245, 355-370, 421-457
- `core/metrics/b4_wyckoff_derived_job.py`: 539-540, 598-606
- `core/metrics/b4_1_wyckoff_sequences_job.py`: 371-393, 484
- `polygon_mcp_server`: canonical tool surface per PIPELINE_010 (2026-03-28)
- `claude_api (compaction behavior)`: PIPELINE_011 (2026-04-04)
- `claude_code (MCP result size)`: PIPELINE_012 (2026-04-04)

## [KapMan] Change Log
| Date       | Version | Change |
|------------|---------|--------|
| 2026-02-13 | 1.0     | Initial orchestration and dependency extraction. |
| 2026-03-28 | 2.2     | Added RULE PIPELINE_010: Polygon MCP canonical tool surface routing rules. All legacy single-symbol endpoints deprecated. Batch anti-patterns added. get_batch_technical_analysis unreliable caveat retracted. |
| 2026-04-04 | 2.3     | Added RULE PIPELINE_011: context compaction guard — always re-fetch dealer metrics at Pass 2. Added RULE PIPELINE_012: MCP tool result truncation awareness for large chains. Updated anti-patterns and source mapping. Standardized to v2.3 production baseline. |
