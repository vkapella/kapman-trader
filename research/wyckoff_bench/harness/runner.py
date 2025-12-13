"""
Benchmark runner: loads OHLCV, executes implementations, and writes signal parquet.
"""

from __future__ import annotations

import uuid
import logging
import json
import numpy as np
logger = logging.getLogger(__name__)
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import pandas as pd
import yaml

from .contract import EVENT_ORDER, SCORE_ORDER, WyckoffImplementation, signal_rows
from .loader_pg import DEFAULT_CACHE_DIR, load_ohlcv
from . import evaluator, report
from research.wyckoff_bench.implementations import (
    kapman_v0_handwritten_structural,
    kapman_v0_claude,
    kapman_v0_chatgpt_wyckoff_core,
    baseline_vsa,
    baseline_tv_heuristic,
    baseline_hybrid_rules,
)


IMPLEMENTATION_BUILDERS = {
    "kapman_v0_handwritten_structural": kapman_v0_handwritten_structural.build,
    "kapman_v0_claude": kapman_v0_claude.build,
    "kapman_v0_chatgpt_wyckoff_core": kapman_v0_chatgpt_wyckoff_core.build,
    "baseline_vsa": baseline_vsa.build,
    "baseline_tv_heuristic": baseline_tv_heuristic.build,
    "baseline_hybrid_rules": baseline_hybrid_rules.build,
}


def _load_entry_events_map(path: Path | str | None = None) -> Dict[str, Dict[str, str]]:
    cfg_path = Path(path) if path else Path(__file__).resolve().parents[1] / "config" / "event_role_direction_map.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _precompute_ta(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    df["rsi_14"] = rsi.fillna(50.0).astype("float64")

    # ADX 14
    plus_dm = (high.diff().where(lambda x: x > low.diff(), 0)).fillna(0.0)
    minus_dm = (low.diff().where(lambda x: x > high.diff(), 0) * -1).fillna(0.0)
    tr_components = pd.concat(
        [(high - low).abs(), (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    )
    tr = tr_components.max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean() / atr.replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean()
    df["adx_14"] = adx.fillna(20.0).astype("float64")

    # ATR 14
    df["atr_14"] = atr.fillna(0.0).astype("float64")

    # Volume MA 20
    df["vol_ma_20"] = volume.rolling(20, min_periods=1).mean().fillna(0.0).astype("float64")

    return df


def load_bench_config(path: Path | str | None) -> Dict:
    if path is None:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def select_implementations(names: Iterable[str] | None) -> List[WyckoffImplementation]:
    if not names:
        selected = list(IMPLEMENTATION_BUILDERS.keys())
    else:
        lowers = [n.lower() for n in names]
        if "all" in lowers:
            selected = list(IMPLEMENTATION_BUILDERS.keys())
        else:
            selected = lowers
    impls: List[WyckoffImplementation] = []
    for name in selected:
        # Research harness normalizes implementation names for CLI ergonomics.
        key = name.lower()
        builder = IMPLEMENTATION_BUILDERS.get(key)
        if not builder:
            valid = ", ".join(sorted(IMPLEMENTATION_BUILDERS.keys()))
            raise ValueError(f"Unknown implementation: {name}. Valid implementations: {valid}")
        impls.append(builder())
    return impls


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add missing event/score columns when no signals are produced."""
    if df.empty:
        base: Dict[str, list] = {}
        for code in EVENT_ORDER:
            base[f"event_{code.value.lower()}"] = []
        for name in SCORE_ORDER:
            base[name.value] = []
        df = pd.DataFrame(base)
    return df


def run_benchmark(
    symbols: Sequence[str],
    *,
    start: datetime | str | None = None,
    end: datetime | str | None = None,
    impl_names: Iterable[str] | None = None,
    impl_cfg: Dict[str, Dict] | None = None,
    loader_cfg: Dict | None = None,
    output_dir: Path | str = "research/wyckoff_bench/outputs",
    run_id: str | None = None,
    database_url: str | None = None,
    diagnostics_only: bool = False,
    entry_only: bool = False,
):
    """
    Run selected implementations over the given symbols.

    Returns:
        signals_df, price_df, signals_path, summary_path, comparison_path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    loader_cfg = loader_cfg or {}
    cache_dir = loader_cfg.get("cache_dir", DEFAULT_CACHE_DIR)

    price_df = load_ohlcv(
        symbols,
        start=start,
        end=end,
        cache_dir=cache_dir,
        database_url=database_url,
    )
    if price_df.empty:
        raise RuntimeError("Loaded OHLCV dataset is empty; cannot run benchmark.")
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        if col in price_df.columns:
            price_df[col] = pd.to_numeric(price_df[col], errors="coerce").astype("float64")
    if entry_only:
        price_df = price_df.dropna(subset=numeric_cols)
        if price_df.empty:
            raise RuntimeError("No OHLCV data remaining after numeric coercion.")

    # Precompute TA per symbol once, centrally.
    frames: List[pd.DataFrame] = []
    for sym, df_sym in price_df.groupby("symbol"):
        frames.append(_precompute_ta(df_sym.reset_index(drop=True)))
    price_df = pd.concat(frames, ignore_index=True) if frames else price_df

    impls = select_implementations(impl_names)
    impl_cfg = impl_cfg or {}
    run_identifier = run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S") + f"_{uuid.uuid4().hex[:6]}"

    diagnostics_rows: List[Dict] = []
    coverage_rows: List[Dict] = []

    entry_events: set[str] = set()
    entry_stats: Dict[str, Dict[str, int]] = {}
    if entry_only:
        mapping = _load_entry_events_map()
        entry_events = {ev for ev, info in mapping.items() if info.get("role", "").upper() == "ENTRY"}

    all_rows: List[Dict] = []
    for impl in impls:
        cfg = impl_cfg.get(impl.name, {})
        supported_events = getattr(impl, "SUPPORTED_EVENTS", EVENT_ORDER)
        supported_set = {
            ev.value if hasattr(ev, "value") else str(ev) for ev in supported_events
        }
        for ev in EVENT_ORDER:
            coverage_rows.append(
                {
                    "impl": impl.name,
                    "event": ev.value,
                    "supported": ev.value in supported_set,
                }
            )

        if entry_only and not (supported_set & entry_events):
            logger.info(f"[ENTRY-ONLY] Skipping {impl.name}: no ENTRY events supported")
            continue

        symbols_processed = set()
        bars_evaluated = 0
        event_signal_counts = {ev.value: 0 for ev in EVENT_ORDER}
        symbols_failed = set()

        for symbol, df_symbol in price_df.groupby("symbol"):
            symbols_processed.add(symbol)
            bars_evaluated += len(df_symbol)
            if diagnostics_only:
                continue

            try:
                signals = impl.analyze(df_symbol, cfg)
            except Exception as e:
                if entry_only:
                    symbols_failed.add(symbol)
                    logger.warning(f"[ENTRY-ONLY] {impl.name} failed for {symbol}: {e}")
                    continue
                raise
            all_rows.extend(signal_rows(signals, impl.name))
            for sig in signals:
                for ev, flag in sig.events.items():
                    if flag:
                        ev_key = ev.value if hasattr(ev, "value") else str(ev)
                        event_signal_counts[ev_key] = event_signal_counts.get(ev_key, 0) + 1

        if entry_only:
            entry_stats[impl.name] = {
                "symbols_processed": len(symbols_processed),
                "symbols_scored": len(symbols_processed - symbols_failed),
                "symbols_failed": len(symbols_failed),
                "bars_evaluated": bars_evaluated,
            }

        for ev in EVENT_ORDER:
            diagnostics_rows.append(
                {
                    "impl": impl.name,
                    "event": ev.value,
                    "symbols_processed": len(symbols_processed),
                    "bars_evaluated": bars_evaluated,
                    "candidates_found": None,
                    "signals_emitted": 0 if diagnostics_only else event_signal_counts.get(ev.value, 0),
                }
            )

    if diagnostics_only:
        # Consolidated outputs only; no signals or scoring.
        diag_df = pd.DataFrame(diagnostics_rows)
        coverage_df = pd.DataFrame(coverage_rows)
        diag_path = output_path / "consolidated_implementation_diagnostics.csv"
        coverage_path = output_path / "consolidated_implementation_coverage.csv"
        diag_df.to_csv(diag_path, index=False)
        coverage_df.to_csv(coverage_path, index=False)
        return None, None, None, None, None

    signals_df = _ensure_columns(pd.DataFrame(all_rows))
    signals_path = output_path / f"signals_{run_identifier}.parquet"
    signals_df.to_parquet(signals_path, index=False)

    evaluated_df, summary_df, directional_summary_df = evaluator.evaluate_signals(signals_df, price_df)
    summary_path, comparison_path, comparison_directional_path = report.write_reports(
        evaluated_df, summary_df, directional_summary_df, output_path, run_identifier
    )

    entry_summary_path = None
    entry_scored_path = None
    if entry_only:
        scored_df, entry_summary_df = evaluator.evaluate_entry_directional(signals_df, price_df)
        if entry_stats:
            scored_df["symbols_processed"] = scored_df["impl"].map(lambda x: entry_stats.get(x, {}).get("symbols_processed"))
            scored_df["symbols_scored"] = scored_df["impl"].map(lambda x: entry_stats.get(x, {}).get("symbols_scored"))
            scored_df["symbols_failed"] = scored_df["impl"].map(lambda x: entry_stats.get(x, {}).get("symbols_failed"))
            scored_df["bars_evaluated"] = scored_df["impl"].map(lambda x: entry_stats.get(x, {}).get("bars_evaluated"))
            entry_summary_df["symbols_processed"] = entry_summary_df["impl"].map(lambda x: entry_stats.get(x, {}).get("symbols_processed"))
            entry_summary_df["symbols_scored"] = entry_summary_df["impl"].map(lambda x: entry_stats.get(x, {}).get("symbols_scored"))
            entry_summary_df["symbols_failed"] = entry_summary_df["impl"].map(lambda x: entry_stats.get(x, {}).get("symbols_failed"))
            entry_summary_df["bars_evaluated"] = entry_summary_df["impl"].map(lambda x: entry_stats.get(x, {}).get("bars_evaluated"))
        entry_scored_path = output_path / "entry_direction_scored.parquet"
        scored_df.to_parquet(entry_scored_path, index=False)
        entry_summary_path, _ = report.write_entry_summary(entry_summary_df, output_path)

    if diagnostics_rows:
        diag_df = pd.DataFrame(diagnostics_rows)
        diag_filename = (
            "consolidated_implementation_diagnostics.csv" if diagnostics_only else "implementation_diagnostics.csv"
        )
        diag_path = output_path / diag_filename
        diag_df.to_csv(diag_path, index=False)
    if coverage_rows:
        coverage_df = pd.DataFrame(coverage_rows)
        coverage_filename = (
            "consolidated_implementation_coverage.csv" if diagnostics_only else "implementation_coverage.csv"
        )
        coverage_path = output_path / coverage_filename
        coverage_df.to_csv(coverage_path, index=False)

    return signals_df, price_df, signals_path, summary_path, comparison_path
