---
system: KapMan
doc_type: strategy
version: 2.3
last_validated: 2026-04-04
market_regime: all
confidence: strict
tags:
  - validation
  - strike_selection
  - anti_hallucination
  - options
---

# VALIDATION_STRIKE_SELECTION

## [KapMan] Objective
Capture all implemented strike/expiration validation and anti-hallucination constraints in AI output and options-chain ingestion paths.

## [KapMan] Decision Table
| Input Value | Normalization Rule | Output |
|---|---|---|
| `option_type` in `{C, CALL}` | Map to call code | `C` |
| `option_type` in `{P, PUT}` | Map to put code | `P` |
| other `option_type` | Reject | null |
| `option_strategy` in `{LONG_CALL, LONG_PUT, CSP, VERTICAL_SPREAD}` | Pass-through | same |
| `CALL_DEBIT_SPREAD`/`PUT_DEBIT_SPREAD` | Map debit spread family | `VERTICAL_SPREAD` |
| unsupported `option_strategy` | Reject | null |
| non-ISO expiration | Parse fails | null |
| non-numeric strike | Parse fails | null |

## [KapMan] Rule Catalog
### RULE VALIDATION_001
RULE_ID: VALIDATION_001  
SOURCE_FILE: core/providers/ai/base.py  
SOURCE_LINE: 391-392  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: System prompt explicitly forbids model-generated strike and expiration assumptions.
LOGIC:
- IF: AI recommendation is generated under base agent prompt
- THEN: "Never assume strike or expiration validity"
- AND: "Do not include strikes, expirations, or option chains"
- THRESHOLD: Hard prompt instruction
CONTEXT: Primary anti-hallucination instruction at model-control layer.

### RULE VALIDATION_002
RULE_ID: VALIDATION_002  
SOURCE_FILE: core/providers/ai/response_parser.py  
SOURCE_LINE: 91-97, 120-135; schemas/ai/wyckoff_context_evaluation.v1.schema.json 16-20, 47-56  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Context-evaluator output must satisfy strict schema checks for confidence range and conditional recommendation fields.
LOGIC:
- IF: `confidence_score` is not numeric or outside `[0,1]`
- THEN: Reject response
- IF: `conditional_recommendation` missing required keys or wrong types
- THEN: Reject response
- THRESHOLD: `confidence_score` bounds `0..1`
CONTEXT: Blocks malformed AI payloads before any persistence.

### RULE VALIDATION_003
RULE_ID: VALIDATION_003  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 553-561, 621  
CATEGORY: Validation  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Option type is normalized to single-letter enum-compatible values only.
LOGIC:
- IF: value in `{C, CALL}`
- THEN: `option_type = C`
- IF: value in `{P, PUT}`
- THEN: `option_type = P`
- ELSE: `option_type = None`
- THRESHOLD: Enumerated mapping only
CONTEXT: Enforces compatibility with database option_type semantics.

### RULE VALIDATION_004
RULE_ID: VALIDATION_004  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 501-509, 622  
CATEGORY: Validation  
RULE_TYPE: Classification  
CONFIDENCE: STRICT  
DESCRIPTION: Option strategy is normalized into supported storage strategy classes.
LOGIC:
- IF: strategy class is supported enum value
- THEN: Keep value
- IF: strategy class is call/put debit spread
- THEN: Map to `VERTICAL_SPREAD`
- ELSE: set to null
- THRESHOLD: Explicit enum mapping table
CONTEXT: Prevents unsupported strategy labels from reaching persistence.

### RULE VALIDATION_005
RULE_ID: VALIDATION_005  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 533-550  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRONG  
DESCRIPTION: Option expiration parser accepts only valid ISO date/datetime inputs.
LOGIC:
- IF: expiration parses as valid `date` or ISO `datetime`
- THEN: return parsed date
- ELSE: return null
- THRESHOLD: ISO parse pass/fail
CONTEXT: Rejects non-date hallucinations early.

### RULE VALIDATION_006
RULE_ID: VALIDATION_006  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 524-530  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRONG  
DESCRIPTION: Option strike parser accepts only numeric inputs and quantizes precision.
LOGIC:
- IF: value parses as decimal
- THEN: `strike = quantize(0.0001)`
- ELSE: return null
- THRESHOLD: precision `0.0001`
CONTEXT: Standardizes strike precision when parsing is used.

### RULE VALIDATION_007
RULE_ID: VALIDATION_007  
SOURCE_FILE: core/metrics/c4_batch_ai_screening_job.py  
SOURCE_LINE: 642-647, 676-683  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Persisted recommendation rows intentionally force option strike and option expiration to null.
LOGIC:
- IF: Building persistence tuple
- THEN: assign `option_strike=None` and `option_expiration=None`
- AND: UPSERT preserves these null fields unless explicitly changed upstream
- THRESHOLD: Hardcoded null assignment
CONTEXT: Prevents model hallucination from becoming stored strike selection.

### RULE VALIDATION_008
RULE_ID: VALIDATION_008  
SOURCE_FILE: core/pipeline/options_normalizer.py  
SOURCE_LINE: 62-67  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Normalized options-chain contracts are dropped when expiration, strike, or option type is missing/invalid.
LOGIC:
- IF: `expiration is None` OR `strike is None` OR `option_type is None`
- THEN: Drop contract row
- THRESHOLD: Required-triplet completeness
CONTEXT: Enforces ingest-time contract identity integrity.

### RULE VALIDATION_009
RULE_ID: VALIDATION_009  
SOURCE_FILE: core/ingestion/options/pipeline.py  
SOURCE_LINE: 377-410, 602-614  
CATEGORY: Validation  
RULE_TYPE: Conditional  
CONFIDENCE: STRICT  
DESCRIPTION: Invalid options rows are excluded from DB upsert and counted/logged.
LOGIC:
- IF: `db_expiration_date`, `db_strike_price`, or `db_option_type` is null
- THEN: Append to invalid list and skip row
- THEN: Log missing-required-fields diagnostics
- THRESHOLD: Required fields are mandatory
CONTEXT: Protects options-chain key integrity before persistence.

### RULE VALIDATION_010
RULE_ID: VALIDATION_010  
SOURCE_FILE: db/migrations/0001_schema_baseline_2026_01.sql  
SOURCE_LINE: 257, 270-271  
CATEGORY: Validation  
RULE_TYPE: Constraint  
CONFIDENCE: STRICT  
DESCRIPTION: Database enforces options-chain identity uniqueness and option type semantics.
LOGIC:
- IF: Inserting `options_chains` row
- THEN: Unique key on `(time,ticker_id,expiration_date,strike_price,option_type)` must hold
- AND: `option_type` must be in `{C,P}`
- THRESHOLD: Hard DB constraints
CONTEXT: Final authority-layer validation against malformed contract keys.

## [KapMan] Anti-Patterns
- NEVER persist model-invented strike or expiration values in C4 recommendations.
- NEVER bypass schema validation for confidence range or conditional recommendation shape.
- NEVER allow unsupported option strategy labels to pass through unnormalized.
- NEVER ingest options contracts missing expiration/strike/option type identity fields.

## [KapMan] Source Mapping
- `core/providers/ai/base.py`: 391-392
- `core/providers/ai/response_parser.py`: 91-97, 120-135
- `schemas/ai/wyckoff_context_evaluation.v1.schema.json`: 16-20, 47-56
- `core/metrics/c4_batch_ai_screening_job.py`: 501-509, 524-550, 553-561, 621-647, 676-683
- `core/pipeline/options_normalizer.py`: 62-67
- `core/ingestion/options/pipeline.py`: 377-410, 602-614
- `db/migrations/0001_schema_baseline_2026_01.sql`: 257, 270-271

## [KapMan] Change Log
| Date | Version | Change |
|---|---|---|
| 2026-02-13 | 1.0 | Initial extraction of strike/expiration validation and anti-hallucination controls. |
| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
