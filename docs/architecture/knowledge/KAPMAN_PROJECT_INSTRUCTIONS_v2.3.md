KAPMAN_PROJECT_INSTRUCTIONS_v2

Format trading analysis into compact self-contained HTML using KapMan style (see KAPMAN_REPORT_STYLE_GLOSSARY_v2 for CSS).
All behavioral rules, content model, field constraints, and section ordering live here.

---

MODE DETECTION

Determine mode from the input:
- SCREENING: input contains ticker list, Danelfin CSV, "screen", "scan", "pass 1", "pass 2", "new ideas", "candidates", or "watchlist"
- PORTFOLIO: input contains P/L data, DTE, existing contract details, "positions", "holdings", "trade management", "portfolio", or account names (Schwab/Fidelity)
- HYBRID: input contains both screening candidates AND existing positions
- If unclear: ask the user which mode before proceeding

For HYBRID: output Screening Plan first, then Portfolio Management Plan, as separate titled sections.

---

PRE-SCREEN MACRO GATE (added 2026-04-04)

Before running Pass 1 screening, assess the macro regime using live data:

Step 1: Fetch SPY spot vs gamma flip via Schwab get_dealer_metrics(["SPY"])
Step 2: Read SPY DGPI from the same call

Gate logic:
| SPY Condition       | SPY DGPI   | Allowed Actions |
|---------------------|------------|-----------------|
| Above gamma flip    | Any        | Full screening — all structures eligible |
| Below gamma flip    | DGPI > -20 | Screening allowed — flag hostile macro in subtitle |
| Below gamma flip    | DGPI ≤ -20 | BLOCK new long-call entries. CSPs, hedges, LEAPs only. Output Macro Regime card. Skip full ACT/BUY column. |

When macro gate blocks long-call entries:
- Output a compact "MACRO REGIME" card above the screening table
- Format: "SPY $X | Below flip ($Y) | DGPI [Z] | Regime: MARKDOWN |
  Long-call entries blocked. CSP / hedge / LEAPs eligible only."
- Still run Pass 1 and Pass 2 for CSP and LEAPS candidates
- Do not suppress the MONITOR or CONDITIONAL columns

Note: This gate supplements, not replaces, individual ticker Pass 1
criteria. A ticker can pass its own Pass 1 filters and still be blocked
by the macro gate.

---

OUTPUT RULES (ALL MODES)

- Return HTML only
- Include full <style> block from GLOSSARY reference CSS
- Dense tables with compact section headers
- Semantic row colors and text colors per GLOSSARY
- Compact badge tags per GLOSSARY
- Landscape/PDF friendly (target one page or near-one-page)
- No markdown fences wrapping the HTML
- No pre/post explanation outside the HTML
- Claude: create HTML file using create_file tool and present via present_files
- ChatGPT: return raw HTML inline, no code fences

---

FIELD LENGTH CONSTRAINTS (HARD CAPS)

These are mandatory. If content exceeds the cap, use a numbered superscript (¹²³) and place expanded detail in the Footnotes section.

| Field                        | Max Words | Max Lines |
|------------------------------|-----------|-----------|
| Screening Rationale (ACT)    | 25        | 2         |
| Screening Rationale (MON)    | 15        | 1         |
| Screening Rationale (COND)   | 15        | 1         |
| Portfolio Action (ACT)       | 30        | 2         |
| Portfolio Note (HOLD)        | 15        | 1         |
| Alert Action On Trigger      | 12        | 1         |
| Discard Reason               | 10        | 1         |
| Weekly Checklist Action      | 15        | 1         |
| Risk Detail                  | 20        | 1         |

Rationale style: lead with the primary signal or verb. No embedded metrics that already have their own columns. No rule IDs (those go in legend only).

Good: "Highest DGPI, MACD Buy, strong DI spread. Spread mandatory (IV elevated). Earnings 70d clear."
Bad: "RULE DEALER_009 shows DGPI +72.1 long gamma with ADX 33.6 and DI+ 36.8 vs 17.4. IV/HV 1.271 means RULE SIGNAL_008 requires spread structure. $115C OI 3,892..."

---

RULE ID PLACEMENT

Rule IDs (e.g., DEALER_009, SIGNAL_008, VALIDATION_001) appear ONLY in the Legend/Footer section.
In body text, use plain descriptive language:
- "spread mandatory (IV elevated)" not "RULE SIGNAL_008"
- "chain too thin" not "RULE DEALER_012 FULL = ≥25"
- "flip breached" not "below gamma flip per RULE DEALER_004"

---

SECTION ROW CAPS

| Section              | Max Rows | Overflow Handling                              |
|----------------------|----------|------------------------------------------------|
| ACT TODAY            | unlimited| —                                              |
| MONITOR              | 5        | Excess → compact watchlist (ticker + blocker)  |
| CONDITIONAL          | 5        | Ranked. Excess → "+ N more conditional"        |
| DISCARD              | 5        | Excess → "+ N more discarded"                  |
| KEY RISKS            | 4        | Prioritize by impact                           |
| ALERTS               | 12       | One STOP + one SCALE per ACT ticker            |
| WoW CHANGES          | 6        | Only material status changes                   |
| PORTFOLIO RISK       | 5        | Prioritize by urgency                          |
| MARKET ENVIRONMENT   | 0 rows   | Compress into subtitle line (see below)        |

---

MARKET ENVIRONMENT RULE

Do NOT create a separate Market Environment table. Compress macro context into the subtitle line.
Format: "SPY $685 (below flip) | VIX 22 ⚠️ | Oil +12% (Iran D5) | Jobs FRI | Fed 3/17 hold"
This saves 4-6 table rows while preserving the context.

---

DATA DUPLICATION RULE

Each section owns UNIQUE information. Do not repeat data across sections.

| Data Point       | Owned By          | Other Sections Reference As          |
|------------------|-------------------|--------------------------------------|
| Stop level       | Main table        | Alert table says "Stop triggered"    |
| Scale levels     | Main table        | Alert table says "Scale target hit"  |
| Flip distance    | Main table        | Checklist references ticker only     |
| P/L              | Main table        | Cross-account shows combined only    |
| Contract details | Main table        | Alert/checklist use ticker shorthand |

Alert Action column must contain NEW information not in the main table:
Good: "Flip zone breached — exit all" or "Chain depth confirmed — upgrade to ACT"
Bad: "Close at $105 stop" (already in main table Stop column)

---

CONTRACT AND STRIKE RULES

- Do not invent exact strikes or expirations unless explicitly supplied from validated Schwab MCP option-chain data.
- If chain data is unavailable, use these labels:
  - Candidate call zone $X–$Y
  - Candidate put zone $X–$Y
  - Candidate debit spread zone $X/$Y
  - Needs chain validation
  - Candidate zone only
- Never present unvalidated contract selection as confirmed
- Treat stops and scale-outs as mechanical outputs when derived from dealer/volatility data:
  - Stop = gamma flip level (rounded to nearest dollar)
  - Scale 1 = nearest call wall
  - Scale 2 = second call wall or short strike (spreads)

---

DATA QUALITY RULES

- If data is weak, say so directly in the Chain column badge and in the rationale:
  - Weak chain / Limited liquidity / Invalid post-filter / Not actionable yet / Below flip / Poor structure / Near event risk
- If data is missing: "Not provided" / "Needs validation" / "Candidate zone only"
- Do not guess or interpolate missing data

EARNINGS DATE LOOKUP POLICY (added 2026-04-04)

When fetching earnings dates via web search or web_fetch:
- Use web_fetch with tool version web_fetch_20260209 when available.
  This enables dynamic filtering — Claude extracts only the date field
  from the full page, reducing token consumption and improving accuracy.
- Fallback: standard web_search for "[TICKER] next earnings date [year]"
- Earnings date must be confirmed before any Pass 1 output is finalized.
  Earnings within 60 days → flag candidate. Earnings within 30 days →
  block new long-premium entry per Pass 1 criteria.


IV SOURCE POLICY (updated 2026-04-04)

Pass 1 — IV source:
  Polygon avg_iv via get_options_metrics(include=['volatility']) is
  usable for directional IV screening.
  Polygon options metrics are aggregate symbol-level signals for screening,
  not contract-level chain validation.
  Post-fix multiplier vs ground truth is 1.02–1.07×. Residual +1–4pp positive
  bias is expected (volatility smile) and acceptable for Pass 1 classification.
  Subtitle format: IV/HV: Polygon avg_iv (directional)

Pass 2 — IV source:
  Schwab ATM chain "volatility" field is authoritative for all IV/HV ratio
  calculations and SIGNAL_008 spread structure decisions. Extract from the
  nearest-to-ATM strike at the target expiry. Never use Schwab's
  "theoreticalVolatility" field — it is hardcoded to 29.0 on every contract.
  Subtitle format: IV/HV: Schwab ATM chain
  
Field priority tiers:
- Tier 1 (ALWAYS show): Ticker, Type, Spot, DGPI, vs Flip, Stop, Scale, Conf
- Tier 2 (show when available): IV/HV, Chain quality, Call Wall
- Tier 3 (sidebar only, never in main table): Net GEX, term structure slope, specific OI counts, individual Greeks

---

STOP AND SCALE DERIVATION

When dealer data is available, stops and scales are mechanical:

| Field    | Source                          | Rule                              |
|----------|---------------------------------|-----------------------------------|
| Stop     | Gamma flip level                | Round to nearest whole dollar     |
| Scale 1  | Nearest call wall above spot    | 50% position exit                 |
| Scale 2  | Second call wall or short strike| Close remainder                   |

For spreads: Scale = approach short strike → close for near-max value.
For CSPs: Scale = premium decays to ≤30% of credit → buy to close.
Default scale plan if no walls available: 50% at +50% gain, trail remainder to cost basis.

---

══════════════════════════════════════════════════════
SCREENING MODE
══════════════════════════════════════════════════════

TITLE FORMAT

Weekly: "KapMan Weekly Screening Plan | [Sector if focused] | [Date]"
Daily: "KapMan Daily Screening Plan | [Sector if focused] | [Date]"

SUBTITLE FORMAT (one line)

[MCP status] | [Time] | Pass 1: [N] tickers → [N] candidates ([criteria]) | Pass 2: [N] Act · [N] Monitor · [N] Conditional · [N] Discard | Chain sources: [list]. IV/HV: [source].

If macro context is relevant, append: | SPY $X ([flip status]) | VIX X | [dominant catalyst]

SECTION ORDER (fixed, do not rearrange)

1. Title + Subtitle
2. Unified Screening Table (single table, section header bars separate ACT/MON/COND groups)
3. Two-column sidebar:
   - Left: Dealer Snapshot (if >5 tickers) OR Discards
   - Right: Alerts To Set
4. Two-column sidebar (if needed):
   - Left: Key Risks (max 4 rows)
   - Right: WoW Changes (weekly only)
5. Footnotes (if any rationale overflow)
6. Legend/Footer

UNIFIED SCREENING TABLE — COLUMN SCHEMA

ALL screening rows (ACT Spread, ACT Long Call, Monitor, Conditional) use ONE table with these columns:

| # | Column      | Width  | Align  | Content                                              |
|---|-------------|--------|--------|------------------------------------------------------|
| 1 | Ticker      | 45px   | center | Bold. Ranked badge below for top picks: #1 PICK, #2  |
| 2 | Type        | 55px   | center | Long Call / Spread / CSP / Long Put                  |
| 3 | Structure   | 90px   | left   | ACT: exact contract "JUN18 $115/$120C"               |
|   |             |        |        | MON/COND: "Candidate call zone $55–60"               |
| 4 | Spot        | 45px   | center | Current price                                        |
| 5 | DGPI        | 40px   | center | Colored green/red                                    |
| 6 | vs Flip     | 65px   | center | Badge: "+$12 ✅" or "−$5 ❌"                         |
| 7 | IV/HV       | 40px   | center | Red if >1.2 (spread mandatory). Green if <1.0        |
| 8 | Chain       | 50px   | center | Badge: High/Med/Low + contract count                 |
| 9 | Stop        | 45px   | center | Underlying price. Bold. Color-coded.                 |
| 10| Scale       | 65px   | left   | "$119→50% / $120→close" format. Max 2 levels.        |
| 11| Rationale   | 180px  | left   | MAX 25 words (ACT) / 15 words (MON/COND). See caps.  |
| 12| Conf        | 45px   | center | High/Med/Low badge                                   |

Section header bars within the table separate categories:
- 🔵 VERTICAL SPREADS — ACT TODAY (IV/HV >1.2)
- 🟢 LONG CALLS — ACT TODAY (IV/HV <1.2)
- 🟡 MONITOR — ENTRY DEFERRED
- 🟣 CONDITIONAL — BLOCKED

DEALER SNAPSHOT TABLE (sidebar, optional)

Compact summary of all screened tickers sorted by DGPI descending.

| Column    | Content                       |
|-----------|-------------------------------|
| Ticker    | Bold                          |
| Spot      | Price                         |
| DGPI      | Colored                       |
| Flip      | Level                         |
| vs Flip   | Badge                         |
| Chain     | Badge + count                 |
| Decision  | ACT/MON/COND/DISC             |

ALERTS TABLE (sidebar)

| Column          | Content                                          |
|-----------------|--------------------------------------------------|
| Ticker          | —                                                |
| Type            | STOP / SCALE / ENTRY                             |
| Level           | Price. Red for stops, green for scale/entry.     |
| Action          | MAX 12 words. New info only, not repeated data.  |

DISCARDS TABLE (sidebar)

| Column   | Content                              |
|----------|--------------------------------------|
| Ticker   | Bold                                 |
| Reason   | MAX 10 words. One line.              |

WoW CHANGES TABLE (sidebar, weekly only)

| Column   | Content                              |
|----------|--------------------------------------|
| Ticker   | —                                    |
| Prior    | Badge with prior status              |
| Current  | Badge with current status            |
| Delta    | Short description of change          |

KEY RISKS TABLE

| Column   | Content                              |
|----------|--------------------------------------|
| Risk     | Bold label                           |
| Detail   | MAX 20 words                         |

Max 4 rows. Prioritize: sector concentration, chain quality gaps, earnings proximity, macro event risk.

RANKING PRIORITY (for ordering ACT rows)

1. Actionability (can you execute today?)
2. Chain quality (Full > Limited > Invalid)
3. DGPI strength + flip buffer
4. IV/HV alignment with structure type
5. Technical confirmation (MACD, ADX, DI spread)
6. Earnings clearance

---

══════════════════════════════════════════════════════
PORTFOLIO MODE
══════════════════════════════════════════════════════

TITLE FORMAT

Weekly: "KapMan Weekly Portfolio Plan — [Account] | [Date Range]"
Daily: "KapMan Daily Portfolio Plan — [Account] | [Date]"

SUBTITLE FORMAT (one line)

Account Value: $X | Cash: $X (Y%) | Total G/L: $X (Y%) | SPY $X ([flip status]) | VIX X | [dominant catalyst] | [next key event]

Do NOT create a separate Market Environment table. All macro context lives here.

SECTION ORDER (fixed, do not rearrange)

1. Title + Subtitle
2. ACT / DECIDE — options needing action (full detail table)
3. HOLD / MONITOR — options being tracked (lighter table)
4. Two-column sidebar:
   - Left: Equities (if any)
   - Right: Weekly Checklist
5. Cross-Account Overlap (if multi-account)
6. Alerts To Set
7. Portfolio Risk Summary (max 5 rows)
8. Footnotes (if any)
9. Legend/Footer

ACT / DECIDE TABLE — COLUMN SCHEMA

Positions that need a decision this week.

| # | Column      | Width  | Align  | Content                                              |
|---|-------------|--------|--------|------------------------------------------------------|
| 1 | Ticker      | 45px   | center | Bold                                                 |
| 2 | Position    | 100px  | left   | Compact: "2× MAY15 $50C" or "Bull 240/250 Apr17"    |
| 3 | DTE         | 30px   | center | Days. Red if <30.                                    |
| 4 | P/L         | 65px   | center | "−$384 (−27%)" format. Color-coded.                  |
| 5 | Flip Status | 60px   | center | Badge: Above ✅ / Below ❌ + distance               |
| 6 | Stop        | 45px   | center | Underlying price. Bold. Color-coded.                 |
| 7 | Scale       | 65px   | left   | Max 2 levels                                         |
| 8 | Action      | 165px  | left   | MAX 30 words. Lead with verb.                        |
| 9 | Priority    | 35px   | center | 🔴 / 🟡 / 🟢                                       |

Action field style: start with the verb. "Close 2×. Halve exposure. Below flip, fading momentum." or "Hold. Alert at $248. Close by 4/1 if stalled below $245."

HOLD / MONITOR TABLE — COLUMN SCHEMA (lighter)

Positions being tracked. Less detail needed.

| # | Column      | Width  | Align  | Content                                              |
|---|-------------|--------|--------|------------------------------------------------------|
| 1 | Ticker      | 45px   | center | Bold                                                 |
| 2 | Position    | 90px   | left   | Compact notation                                     |
| 3 | DTE         | 30px   | center | Days                                                 |
| 4 | P/L         | 60px   | center | Color-coded                                          |
| 5 | Flip Status | 55px   | center | Badge                                                |
| 6 | Next Level  | 60px   | center | THE one price triggering next decision               |
| 7 | Note        | 150px  | left   | MAX 15 words.                                        |

EQUITIES TABLE (sidebar)

| Column   | Content                              |
|----------|--------------------------------------|
| Ticker   | Bold                                 |
| Qty      | Shares                               |
| P/L      | Color-coded                          |
| Stop     | Price                                |
| Scale    | Trim level                           |
| Note     | MAX 10 words                         |

WEEKLY CHECKLIST (sidebar)

| Column   | Content                              |
|----------|--------------------------------------|
| Day      | Day of week + date                   |
| Priority | 🔴 / 🟡                             |
| Ticker   | —                                    |
| Action   | MAX 15 words. Specific instruction.  |

Include upcoming events row at bottom: ex-divs, earnings, Fed, economic data.

CROSS-ACCOUNT OVERLAP TABLE

Required when positions exist in both Schwab and Fidelity.

| Column           | Content                              |
|------------------|--------------------------------------|
| Ticker           | Bold                                 |
| Schwab Position  | Compact notation                     |
| Fidelity Position| Compact notation                     |
| Combined Exposure| Total contracts + note               |
| Unified Stop     | Single stop across accounts          |
| Unified Scale    | Coordinated scale plan               |
| Unified Action   | MAX 15 words                         |

ALERTS TABLE

Same schema as Screening mode alerts.

PORTFOLIO RISK SUMMARY

| Column           | Content                              |
|------------------|--------------------------------------|
| Risk Factor      | Bold label                           |
| Current Exposure | Data point. Color-coded.             |
| Mitigation       | MAX 15 words                         |

Standard risk factors to check: cash position, downside protection, sector concentration, cross-account oversizing, short-DTE cluster.

---

══════════════════════════════════════════════════════
FOOTNOTES SECTION
══════════════════════════════════════════════════════

Placed between the last content section and the Legend/Footer.
Used for rationale overflow when content exceeds field caps.

Format:
¹ COP: $115C OI=3,892, $120C OI=5,554. Apr17 alt $115/$120 (OI=5,026/2,223) for higher gamma.
² HON: Down 3.24% today. Confirm close above $228 flip before full size. Use standard HON only (skip HON1/SOLS).

Footnotes are numbered sequentially. Superscript number appears in the rationale cell of the main table.

---

══════════════════════════════════════════════════════
LEGEND / FOOTER
══════════════════════════════════════════════════════

Every report ends with a legend containing:

1. DATA SOURCES: Which MCP servers, which tickers, timestamps, any fallbacks
   "Schwab MCP (dealer 31/31, chains COP/CVX/HON) · Polygon (price metrics) · Danelfin (IV/HV, technicals) · 2026-03-05 15:12 EST"

2. RULE IDS: All rules referenced in the report (the ONLY place these appear)
   "Rules applied: DEALER_001/002/009/010/012 · SIGNAL_008 · VALIDATION_001/007"

3. DEFINITIONS:
   "Stop = underlying close price, exit option position. Scale = staged profit exit. Flip = gamma flip level from Schwab dealer metrics."

4. CAVEATS: Any data quality issues
   "†DINO/OVV: 0 contracts after min_oi=100 filter — DGPI from unfiltered pool, reduce size."

---

══════════════════════════════════════════════════════
DECLUTTER RULES
══════════════════════════════════════════════════════

Apply these checks before finalizing output:

- Remove any repeated stop/scale/target data across sections
- Compress every rationale to meet word caps
- Remove decorative commentary ("This is an excellent setup because...")
- Remove rule IDs from body text (legend only)
- Omit empty sections entirely (no "No items" placeholders)
- Prefer fewer stronger rows over many weak rows
- If a section has only 1 row, consider merging it into another section
- No emojis in data cells (emojis OK in section headers only)
- Maximize signal-to-noise ratio
- Do not repeat macro gate output inside individual ticker rationale.
  The macro card is shown once at the top; ticker rows assume the
  reader has seen it.

---

══════════════════════════════════════════════════════
TERMINOLOGY
══════════════════════════════════════════════════════

Use KapMan terminology consistently:
- DGPI (not "dealer gamma pressure" in full)
- Flip / gamma flip (not "gamma flip level" every time)
- Above/Below flip (not "price is above the gamma flip level")
- Call wall / put wall (not "call-side weighted OI resistance")
- Chain quality: Full / Limited / Invalid (per DEALER_012)
- Net GEX (not "gamma exposure")
- IV/HV ratio (not "implied to historical volatility ratio")
- DTE (not "days to expiration" every time)
- Scale (not "scale-out plan" or "profit-taking levels")
- Compact contract notation: "2× MAY15 $50C" or "Bull 240/250 Apr17"

---

VERSION

| Date       | Version | Change |
|------------|---------|--------|
| 2026-03-01 | 1.0     | Initial instructions (ChatGPT draft) |
| 2026-03-08 | 2.0     | Complete rewrite. Added: mode detection rules, hard field caps, unified column schemas, fixed section ordering, row count caps, data duplication rules, footnote overflow, market env compression, rule ID placement rules, stop/scale derivation, contract rules, data quality tiers, declutter checklist, terminology guide. Removed: content model (was duplicated from glossary). Separated behavioral rules from visual spec. |
| 2026-03-27 | 2.1     | Added IV source policy (Polygon avg_iv for Pass 1, Schwab ATM for Pass 2). Updated terminology guide. |
| 2026-04-04 | 2.3     | Added Pre-Screen Macro Gate section. Added Earnings Date Lookup Policy with web_fetch_20260209. Fixed IV Source Policy to reference canonical get_options_metrics endpoint. Added declutter rule for macro card placement. Standardized to v2.3 production baseline. |
