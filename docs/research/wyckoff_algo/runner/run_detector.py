from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pandas as pd
import sqlalchemy as sa

# Ensure archive research package (benchmark contract/evaluator) is importable.
REPO_ROOT = Path(__file__).resolve().parents[4]
ARCHIVE_PATH = REPO_ROOT / "archive"
if str(ARCHIVE_PATH) not in sys.path:
    sys.path.insert(0, str(ARCHIVE_PATH))

# Allow direct imports from docs/research/wyckoff_algo without package execution.
WYCKOFF_ROOT = Path(__file__).resolve().parents[1]
if str(WYCKOFF_ROOT) not in sys.path:
    sys.path.insert(0, str(WYCKOFF_ROOT))

RESEARCH_INPUTS = REPO_ROOT / "docs" / "research_inputs"
if str(RESEARCH_INPUTS) not in sys.path:
    sys.path.insert(0, str(RESEARCH_INPUTS))

from research.wyckoff_bench.harness.contract import EVENT_ORDER, signal_rows
from research.wyckoff_bench.harness.evaluator import _load_event_role_direction_map

from legacy.kapman_v0_handwritten_structural import KapmanV0HandwrittenStructural
from runner.load_ohlcv import _lookup_date_bounds, _make_engine, _read_watchlist, load_ohlcv

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "outputs" / "raw" / "events.parquet"
OUTPUT_CSV_PATH = Path(__file__).resolve().parents[1] / "outputs" / "raw" / "events.csv"
OUTPUT_TIMELINE_CSV_PATH = Path(__file__).resolve().parents[1] / "outputs" / "raw" / "events_timeline.csv"
COVERAGE_DIR = Path(__file__).resolve().parents[1] / "outputs" / "raw" / "coverage"
RAW_CONFIG_PATH = Path(__file__).resolve().parents[1] / "outputs" / "raw" / "config.yaml"


def _enrich_rows(
    raw_rows: List[Dict],
    ohlcv_by_symbol: Dict[str, pd.DataFrame],
    role_map: Dict[str, Dict[str, str]],
) -> List[Dict]:
    """Add event metadata required by downstream benchmarking."""
    enriched: List[Dict] = []
    for row in raw_rows:
        time_val = pd.to_datetime(row.get("time"))
        symbol = row.get("symbol")

        event_code = None
        for code in EVENT_ORDER:
            if bool(row.get(f"event_{code.value.lower()}", False)):
                event_code = code.value
                break
        if not event_code:
            continue

        df_sym = ohlcv_by_symbol.get(symbol)
        bar_index = None
        if df_sym is not None:
            matches = df_sym.index[df_sym["time"] == time_val].tolist()
            if matches:
                bar_index = int(matches[0])

        role_info = role_map.get(event_code, {})
        direction = row.get("direction") or role_info.get("direction")
        role = row.get("role") or role_info.get("role")

        enriched.append(
            {
                **row,
                "event": event_code,
                "direction": direction,
                "role": role,
                "event_date": time_val,
                "bar_index": bar_index,
                "impl": row.get("impl") or "kapman_v0_handwritten_structural",
            }
        )
    return enriched


def _load_config(path: Path = RAW_CONFIG_PATH) -> Dict:
    if not path.exists():
        return {}
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_watchlist_path(cfg_watchlist: str | None) -> Path:
    if not cfg_watchlist:
        return _read_watchlist.__defaults__[0]  # type: ignore[attr-defined]
    p = Path(cfg_watchlist)
    if not p.is_absolute():
        p = RAW_CONFIG_PATH.parent / p
    return p


def _fetch_universe_symbols(engine: sa.Engine, start_ts, end_ts, min_days: int) -> List[str]:
    recent_cutoff = end_ts - pd.Timedelta(days=7)
    query = sa.text(
        """
        SELECT t.symbol AS symbol
        FROM ohlcv o
        JOIN tickers t ON o.ticker_id = t.id
        WHERE o.date >= :start
        GROUP BY t.symbol
        HAVING COUNT(*) >= :min_days
           AND MAX(o.date) >= :recent_cutoff
        ORDER BY t.symbol
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"start": start_ts, "min_days": min_days, "recent_cutoff": recent_cutoff}).fetchall()
    return [r.symbol.upper() for r in rows]


def _write_coverage_reports(events_df: pd.DataFrame) -> None:
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
    if events_df.empty:
        pd.DataFrame(columns=["event", "total_count", "symbols_with_event", "avg_events_per_symbol", "density"]).to_csv(
            COVERAGE_DIR / "event_coverage_summary.csv", index=False
        )
        pd.DataFrame(columns=["symbol", "total_events", "events_per_year"]).to_csv(
            COVERAGE_DIR / "symbol_event_density.csv", index=False
        )
        pd.DataFrame(columns=["event", "min_gap_days", "median_gap_days", "p95_gap_days"]).to_csv(
            COVERAGE_DIR / "event_spacing_stats.csv", index=False
        )
        return

    events_df["event_date"] = pd.to_datetime(events_df["event_date"])
    symbol_col = "symbol" if "symbol" in events_df.columns else "ticker"
    overall_span_years = max(
        (events_df["event_date"].max() - events_df["event_date"].min()).days / 365.25,
        1e-6,
    )

    summary_rows = []
    for ev, grp in events_df.groupby("event"):
        total = len(grp)
        sym_count = grp[symbol_col].nunique()
        avg_per_sym = total / sym_count if sym_count else 0
        density = total / max(sym_count, 1) / overall_span_years
        summary_rows.append(
            {
                "event": ev,
                "total_count": total,
                "symbols_with_event": sym_count,
                "avg_events_per_symbol": avg_per_sym,
                "density": density,
            }
        )
    pd.DataFrame(summary_rows).to_csv(COVERAGE_DIR / "event_coverage_summary.csv", index=False)

    density_rows = []
    for sym, grp in events_df.groupby(symbol_col):
        total = len(grp)
        span_years = max((grp["event_date"].max() - grp["event_date"].min()).days / 365.25, 1e-6)
        density_rows.append(
            {
                "symbol": sym,
                "total_events": total,
                "events_per_year": total / span_years,
            }
        )
    pd.DataFrame(density_rows).to_csv(COVERAGE_DIR / "symbol_event_density.csv", index=False)

    spacing_rows = []
    for ev, grp in events_df.groupby("event"):
        gaps: List[float] = []
        for _, g_sym in grp.groupby(symbol_col):
            dates = g_sym["event_date"].sort_values().unique()
            if len(dates) < 2:
                continue
            diffs = pd.Series(dates).diff().dt.days.dropna()
            gaps.extend(diffs.tolist())
        if not gaps:
            spacing_rows.append({"event": ev, "min_gap_days": None, "median_gap_days": None, "p95_gap_days": None})
            continue
        gaps_series = pd.Series(gaps)
        spacing_rows.append(
            {
                "event": ev,
                "min_gap_days": gaps_series.min(),
                "median_gap_days": gaps_series.median(),
                "p95_gap_days": gaps_series.quantile(0.95),
            }
        )
    pd.DataFrame(spacing_rows).to_csv(COVERAGE_DIR / "event_spacing_stats.csv", index=False)


def run_detector(output_path: Path = OUTPUT_PATH) -> pd.DataFrame:
    """Execute the legacy handwritten detector across configured universe/watchlist."""
    cfg = _load_config()
    batch_size = int(cfg.get("batch_size", 250))
    min_days = int(cfg.get("min_days", 252))
    use_universe = str(cfg.get("universe")).lower() == "all"
    watchlist_path = _resolve_watchlist_path(cfg.get("watchlist"))

    engine = _make_engine()
    start_ts, end_ts = _lookup_date_bounds(engine)

    if use_universe:
        symbols = _fetch_universe_symbols(engine, start_ts, end_ts, min_days)
        if not symbols:
            raise RuntimeError("Universe mode requested but no eligible symbols were found.")
        logger.info("Universe mode enabled: %s symbols eligible.", len(symbols))
    else:
        symbols = _read_watchlist(watchlist_path)
        logger.info("Watchlist mode enabled: %s symbols from %s.", len(symbols), watchlist_path)

    impl = KapmanV0HandwrittenStructural()
    role_map = _load_event_role_direction_map()

    all_rows: List[Dict] = []
    total_symbols = len(symbols)
    for start in range(0, total_symbols, batch_size):
        batch_symbols = symbols[start : start + batch_size]
        logger.info("Processing batch %s-%s / %s symbols", start + 1, min(start + batch_size, total_symbols), total_symbols)
        ohlcv_by_symbol = load_ohlcv(
            symbols=batch_symbols,
            engine=engine,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        if not ohlcv_by_symbol:
            logger.warning("No OHLCV loaded for batch starting at index %s.", start)
            continue

        for symbol, df_sym in ohlcv_by_symbol.items():
            signals = impl.analyze(df_sym, cfg={})
            base_rows = signal_rows(signals, impl.name)
            enriched = _enrich_rows(base_rows, ohlcv_by_symbol, role_map)
            all_rows.extend(enriched)
            logger.info("Detected %s events for %s", len(enriched), symbol)

    events_df = pd.DataFrame(all_rows)
    events_df = events_df.sort_values(["symbol", "event_date"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Parquet (existing behavior).
    events_df.to_parquet(output_path, index=False)

    # CSV mirror for chart inspection.
    csv_cols = ["symbol", "event", "direction", "role", "event_date", "bar_index", "impl"]
    events_df[csv_cols].to_csv(OUTPUT_CSV_PATH, index=False)

    # Timeline CSV (lightweight chart helper).
    timeline_cols = ["symbol", "event_date", "event", "direction", "role"]
    events_df[timeline_cols].to_csv(OUTPUT_TIMELINE_CSV_PATH, index=False)

    _write_coverage_reports(events_df)

    logger.info(
        "Wrote %s events to %s (csv=%s, timeline=%s)",
        len(events_df),
        output_path,
        OUTPUT_CSV_PATH,
        OUTPUT_TIMELINE_CSV_PATH,
    )

    return events_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_detector()
