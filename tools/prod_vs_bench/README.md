Production vs Benchmark Wyckoff Forward Metrics Comparator

Purpose
- Compare production Wyckoff outputs against benchmark outputs using the same evaluation logic.

How to run
- Run production evaluation:
  python -m tools.prod_vs_bench.run_prod_eval --start-date 2023-12-28 --end-date 2025-12-24 --benchmark-dir "/App Development/wyckoff_fast_bench/outputs/011_Enhance_Wyckoff_Sequence" --output-dir tools/prod_vs_bench/outputs

- Compare outputs:
  python -m tools.prod_vs_bench.compare_outputs --prod-dir tools/prod_vs_bench/outputs/prod --bench-dir docs/research_outputs/011_Enhance_Wyckoff_Sequence --output-dir tools/prod_vs_bench/outputs/comparison

Required environment variables
- DATABASE_URL must be set for kapman-db access.

Interpretation
- Compare CSV outputs in tools/prod_vs_bench/outputs/comparison to determine if production matches, exceeds, or underperforms benchmarks.
- Deltas are computed as prod minus benchmark and missing rows are flagged.

Known causes of divergence
- Different data coverage or date ranges between prod and benchmark.
- Missing production events or regime assignments for the specified window.
- Symbol coverage mismatches.
