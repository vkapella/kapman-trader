# KAPMAN TRADER — RESEARCH ARCHITECTURE (WYCKOFF BENCH)
**Version:** 1.0  
**Scope:** Research-only Wyckoff benchmarking (no changes to `core/`)  
**Owner:** Research track

---

## 1. Purpose & Scope
- Build a deterministic Wyckoff benchmarking harness separate from production code.  
- Evaluate multiple Wyckoff implementations against the same OHLCV data, events, and scoring contract.  
- Outputs are research artifacts only (`research/wyckoff_bench/**`, `docs/research_inputs/**`), never consumed by `core/`.

## 2. Separation From Production
- No imports from `core/` or `api/`; research code must be self-contained.  
- Input dependencies live under `docs/research_inputs/` (prompts, rulebooks, handwritten Wyckoff code, configs).  
- All outputs stay under `research/wyckoff_bench/outputs/`; do not write to production tables.  
- Postgres access is read-only against `ohlcv_daily` for OHLCV pulls.

## 3. Directory Layout (Research Track)
```
docs/
  KAPMAN_RESEARCH_ARCHITECTURE_v1.0.md
  WINDSURF_RESEARCH_GUIDE_v1.0.md
  research_inputs/        # provided logic/config artifacts
research/wyckoff_bench/
  README.md
  config/bench.default.yaml
  harness/
    contract.py           # event/score types + protocol
    loader_pg.py          # OHLCV reader + parquet cache
    runner.py             # orchestrates implementations
    evaluator.py          # returns/MAE/MFE + summaries
    report.py             # tabular comparison outputs
  implementations/
    kapman_v0_handwritten_structural.py
    kapman_v0_claude.py
    kapman_v0_chatgpt_wyckoff_core.py
    baseline_vsa.py
    baseline_tv_heuristic.py
    baseline_hybrid_rules.py
  outputs/
    cache/ (created at runtime)
    .gitkeep
tests/unit/research_wyckoff_bench/
  test_contract.py, test_loader_pg.py, test_evaluator.py, test_runner_smoke.py
```

## 4. Harness Contract
- **Events (MVP-8):** `SC`, `AR`, `ST`, `SPRING`, `TEST`, `SOS`, `BC`, `SOW`.  
- **Scores:** `bc_score`, `spring_score`, `composite_score` (normalized 0–100).  
- **Signal:** `{symbol, time, events: dict[EventCode,bool], scores: dict[ScoreName,float], debug?: dict}`.  
- **Implementation Protocol:** `.name` + `analyze(df_symbol: pd.DataFrame, cfg: dict) -> list[WyckoffSignal]`.

## 5. Data Access (Postgres / Timescale)
- Source table: `ohlcv_daily` with columns `time, open, high, low, close, volume, symbol`.  
- `DATABASE_URL` comes from environment; connections are ephemeral (no pooling).  
- Default range: last 730 trading days (approx; derived from max date in table).  
- Loader writes/reads parquet cache under `research/wyckoff_bench/outputs/cache/` keyed by symbols + date range.

## 6. Benchmark Flow
1) **Load OHLCV** via `harness/loader_pg.py` (with parquet cache).  
2) **Run implementations** under a shared contract; write `signals_<run_id>.parquet`.  
3) **Evaluate** forward returns (+5/+10/+20/+40) and MAE/MFE (20-day window).  
4) **Report** summaries + comparison tables (`summary_<run_id>.parquet/.csv`, `comparison_<run_id>.csv`).

## 7. Implementations (Pass #1)
- `kapman_v0_handwritten_structural`: wraps uploaded structural Wyckoff code + configs.  
- `kapman_v0_claude`: deterministic Claude rules (volume/spread/location/structure) with debug rationale.  
- `kapman_v0_chatgpt_wyckoff_core`: deterministic schematic rules from `KapMan_Deterministic_Schematic_Rules_v2.2.md` + `wyckoff_config.json` (no metric weights).  
- Baselines: `baseline_vsa`, `baseline_tv_heuristic`, `baseline_hybrid_rules`.

## 8. Outputs & Interpretation
- **Signals parquet:** per-implementation signals with event booleans + normalized scores.  
- **Summary parquet/csv:** per-event + horizon aggregates (hit density, forward returns, MAE/MFE).  
- **Comparison csv:** best implementation per event/horizon based on composite return/MAE trade-off.

## 9. Adding New Implementations (Research Only)
- Drop adapter into `research/wyckoff_bench/implementations/`.  
- Conform to contract; read configs only from `docs/research_inputs/`.  
- Register in `bench.default.yaml` and runner CLI.

## 10. Determinism & Repeatability
- Fixed symbol universe (default 20) and date range.  
- Parquet cache pins datasets per run.  
- No randomness; implementations must be pure functions of OHLCV + config.  
- Tests enforce deterministic outputs with synthetic fixtures.

## Canonical Wyckoff Research Abstraction
- Wyckoff layer outputs only `(event, direction, role, horizon, confidence)`; instruments are downstream policy decisions.  
- Direction is market structure: `UP` = growth/markup, `DOWN` = contraction/markdown.  
- Role is exposure-relative: `ENTRY` initiates exposure in the direction; `EXIT` reduces exposure in the direction.  
- Instrument selection (CALL, PUT, CSP, SPREAD) is **not** part of Wyckoff research and is handled later in policy.  
- Examples:  
  - `SPRING → UP / ENTRY` (e.g., buy calls or sell CSPs)  
  - `BC → DOWN / ENTRY` (e.g., buy puts)  
  - `BC → UP / EXIT` (e.g., close calls)  
- BC is not a failed long-entry signal; it is a valid DOWN-entry signal. First-run benchmarks provide evidence, not proof.

## Benchmark Diagnostics and Negative Evidence
- Zero-signal outcomes are meaningful: they indicate either true absence of pattern or implementation non-participation.  
- Coverage (which events an implementation is capable of emitting) is distinct from performance (returns/MAE/MFE).  
- Diagnostics capture which implementations ran, how many bars/symbols they processed, and per-event signal counts to prevent false superiority claims when an algorithm simply abstains.  

## Consolidated Wyckoff Diagnostic Benchmark
- Coverage ≠ quality: supporting an event only proves the adapter can emit it, not that returns or path metrics are acceptable.  
- Signal density matters because Wyckoff cores must be sparse: structural events should be exceptional, not chronic noise.  
- Entry vs Exit roles remain explicit so structural outputs map cleanly into downstream risk policy layers.  
- This consolidated benchmark runs all implementations over identical data, capturing coverage + signal density without scoring to determine architectural eligibility only; it intentionally avoids naming a winner or interpreting performance.  

## ENTRY-Only, Direction-Aware Benchmark
- UP directional return: `(PH / P0) - 1`; DOWN directional return: `(P0 / PH) - 1` (profits when price declines).  
- Direction and role stay separate: BC is treated as DOWN/ENTRY, SPRING as UP/ENTRY; EXIT logic is excluded from this pass.  
- MAE_dir is directional: UP uses `min_close/P0 - 1`; DOWN uses `P0/max_close - 1` (more negative is worse).  
- Instrument selection (CALL/PUT/CSP/spreads) remains downstream; this layer only scores structural ENTRY signals by direction.  
- Role filtering is strict: only role==ENTRY is scored; EXIT/IGNORE are dropped.  
