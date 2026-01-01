from __future__ import annotations

import argparse
import importlib.util
import logging
import math
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

import pandas as pd
import psycopg2

from core.ingestion.ohlcv import db as ohlcv_db
from .fetch_prod_data import fetch_prod_data
from .prod_adapter import build_events_df, build_regime_df, normalize_ohlcv
from .metrics import EvalMetrics, format_count


@dataclass
class RunMetadata:
    start_date: str
    end_date: str
    git_sha: str
    run_timestamp: str


FORWARD_WINDOWS = [5, 10, 20]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_research_module(name: str, rel_path: str):
    repo_root = _repo_root()
    path = repo_root / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git_revision() -> str:
    try:
        sha_bytes = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_repo_root(),
            stderr=subprocess.DEVNULL,
        )
        return sha_bytes.decode().strip()
    except Exception:
        return "unknown"


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _metadata(start: date, end: date) -> RunMetadata:
    return RunMetadata(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        git_sha=_git_revision(),
        run_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _coverage_years(price_df: pd.DataFrame) -> float:
    if price_df is None or price_df.empty or "date" not in price_df.columns:
        return 0.0
    dates = pd.to_datetime(price_df["date"], errors="coerce").dropna()
    if dates.empty:
        return 0.0
    return (dates.max() - dates.min()).days / 365.25


def _add_metadata(df: pd.DataFrame, meta: RunMetadata) -> pd.DataFrame:
    if df is None:
        df = pd.DataFrame()
    data = df.copy()
    data["start_date"] = meta.start_date
    data["end_date"] = meta.end_date
    data["git_sha"] = meta.git_sha
    data["run_timestamp"] = meta.run_timestamp
    return data


def _align_columns(
    df: pd.DataFrame, benchmark_columns: Optional[Iterable[str]], meta: RunMetadata
) -> pd.DataFrame:
    if not benchmark_columns:
        return df
    benchmark_columns = list(benchmark_columns)
    meta_cols = {"start_date", "end_date", "git_sha", "run_timestamp"}
    if not meta_cols.issubset(set(benchmark_columns)):
        return df
    aligned = df.reindex(columns=benchmark_columns)
    return aligned


def _write_csv(
    df: pd.DataFrame,
    path: Path,
    meta: RunMetadata,
    benchmark_columns: Optional[Iterable[str]] = None,
    metrics: Optional[EvalMetrics] = None,
) -> None:
    data = _add_metadata(df, meta)
    data = _align_columns(data, benchmark_columns, meta)
    data.to_csv(path, index=False)
    if metrics is not None:
        metrics.tick_csv_written(path.name, len(data))


def _read_benchmark_columns(benchmark_dir: Optional[Path], filename: str) -> Optional[list[str]]:
    if not benchmark_dir:
        return None
    path = benchmark_dir / filename
    if not path.exists():
        return None
    try:
        return list(pd.read_csv(path, nrows=0).columns)
    except Exception:
        return None


def _copy_benchmark_outputs(benchmark_dir: Optional[Path], bench_out: Path) -> None:
    if not benchmark_dir or not benchmark_dir.exists():
        return
    bench_out.mkdir(parents=True, exist_ok=True)
    for item in benchmark_dir.iterdir():
        if item.is_file() and item.suffix.lower() == ".csv":
            shutil.copy2(item, bench_out / item.name)


def _fetch_symbol_universe(symbols: Optional[Iterable[str]]) -> list[str]:
    if symbols:
        return sorted({str(sym).strip().upper() for sym in symbols if str(sym).strip()})

    db_url = ohlcv_db.default_db_url()
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT UPPER(symbol)
                FROM tickers
                WHERE is_active = TRUE
                ORDER BY UPPER(symbol)
                """
            )
            rows = cur.fetchall()
    return [str(row[0]) for row in rows]


def _split_batches(symbols: list[str], workers: int) -> list[list[str]]:
    if workers <= 0:
        return []
    if not symbols:
        return [[] for _ in range(workers)]
    chunk_size = int(math.ceil(len(symbols) / workers))
    batches = []
    for i in range(workers):
        start = i * chunk_size
        end = start + chunk_size
        batch = symbols[start:end]
        if batch:
            batches.append(batch)
    return batches


def _write_worker_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _merge_worker_csvs(worker_dirs: list[Path], filename: str) -> pd.DataFrame:
    frames = []
    for wdir in worker_dirs:
        path = wdir / filename
        if not path.exists():
            continue
        try:
            frames.append(pd.read_csv(path))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _sort_df(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    available = [col for col in columns if col in df.columns]
    if not available:
        return df
    return df.sort_values(available).reset_index(drop=True)


def _worker_eval(
    worker_id: int,
    symbols: list[str],
    start_date: date,
    end_date: date,
    output_dir: Path,
    verbose_metrics: bool,
    heartbeat_every: int,
    queue: Optional[mp.Queue],
) -> dict:
    if verbose_metrics:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(f"prod_vs_bench.worker.{worker_id}")
    metrics = EvalMetrics(
        verbose=verbose_metrics,
        heartbeat_every=heartbeat_every,
        logger=logger,
        prefix=f"[EVAL][W{worker_id}]",
    )
    metrics.set_total_symbols(len(symbols))
    metrics.set_forward_windows(len(FORWARD_WINDOWS))

    if verbose_metrics:
        logger.info("%s start symbols=%s", metrics.prefix, len(symbols))
    if queue is not None:
        queue.put({"type": "start", "worker": worker_id, "symbols": len(symbols)})

    try:
        eval_mod = _load_research_module("research_eval", "docs/research_inputs/eval.py")
        regime_mod = _load_research_module("research_regime_eval", "docs/research_inputs/regime_eval.py")
        contextual_mod = _load_research_module(
            "research_contextual_eval", "docs/research_inputs/contextual_event_eval.py"
        )
        transition_mod = _load_research_module("research_transition_labels", "docs/research_inputs/transition_labels.py")
        sequence_mod = _load_research_module("research_sequence_labels", "docs/research_inputs/sequence_labels.py")

        prod_data = fetch_prod_data(start_date=start_date, end_date=end_date, symbols=symbols)
        ohlcv_df = normalize_ohlcv(prod_data.ohlcv)
        events_df = build_events_df(prod_data.snapshots, detector="baseline")
        regime_df = build_regime_df(prod_data.snapshots)

        metrics.tick_rows(len(ohlcv_df))
        metrics.tick_rows(len(events_df))
        metrics.tick_rows(len(regime_df))
        metrics.tick_events(len(events_df))

        transition_events = transition_mod.label_regime_transitions(regime_df)
        if transition_events.empty:
            transition_events = transition_events.reindex(
                columns=["symbol", "date", "transition", "prior_regime", "new_regime", "detector", "event"]
            )
        else:
            transition_events = transition_events.copy()
            transition_events["detector"] = "transition"
            transition_events["event"] = transition_events["transition"]
        metrics.tick_rows(len(transition_events))
        metrics.tick_events(len(transition_events))

        sequence_events = sequence_mod.label_event_sequences(events_df)
        if sequence_events.empty:
            sequence_events = sequence_events.reindex(columns=["symbol", "date", "sequence_id", "detector", "event"])
        else:
            sequence_events = sequence_events.copy()
            sequence_events["detector"] = "sequence"
            sequence_events["event"] = sequence_events["sequence_id"]
        metrics.tick_rows(len(sequence_events))
        metrics.tick_events(len(sequence_events))

        contextual_events = contextual_mod.attach_prior_regime(events_df, regime_df)
        if contextual_events.empty:
            contextual_events = contextual_events.reindex(
                columns=["symbol", "date", "event", "prior_regime", "base_event", "detector"]
            )
        else:
            contextual_events = contextual_events.copy()
            contextual_events["base_event"] = contextual_events["event"]
            contextual_events["event"] = contextual_events.apply(
                lambda row: f"{row['event']}:{row['prior_regime']}"
                if pd.notna(row.get("prior_regime"))
                else f"{row['event']}:UNKNOWN",
                axis=1,
            )
            contextual_events["detector"] = "contextual"
        metrics.tick_rows(len(contextual_events))
        metrics.tick_events(len(contextual_events))

        def progress_cb(metrics_snapshot: EvalMetrics) -> None:
            if queue is None:
                return
            queue.put(
                {
                    "type": "progress",
                    "worker": worker_id,
                    **metrics_snapshot.progress_payload(),
                }
            )

        baseline_forward = _add_forward_returns_by_symbol(
            eval_mod, events_df, ohlcv_df, metrics, progress_cb
        )
        transition_forward = _add_forward_returns_by_symbol(
            eval_mod, transition_events, ohlcv_df, metrics, progress_cb
        )
        sequence_forward = _add_forward_returns_by_symbol(
            eval_mod, sequence_events, ohlcv_df, metrics, progress_cb
        )
        contextual_forward = _add_forward_returns_by_symbol(
            eval_mod, contextual_events, ohlcv_df, metrics, progress_cb
        )

        daily_forward = _add_daily_forward_returns_by_symbol(regime_mod, ohlcv_df, metrics, progress_cb)

        worker_dir = output_dir / f"worker_{worker_id}"
        _write_worker_csv(ohlcv_df, worker_dir / "ohlcv.csv")
        _write_worker_csv(regime_df, worker_dir / "regime.csv")
        _write_worker_csv(daily_forward, worker_dir / "daily_forward_returns.csv")
        _write_worker_csv(events_df, worker_dir / "baseline_events.csv")
        _write_worker_csv(baseline_forward, worker_dir / "baseline_forward_returns.csv")
        _write_worker_csv(transition_events, worker_dir / "transition_events.csv")
        _write_worker_csv(transition_forward, worker_dir / "transition_forward_returns.csv")
        _write_worker_csv(sequence_events, worker_dir / "sequence_events.csv")
        _write_worker_csv(sequence_forward, worker_dir / "sequence_forward_returns.csv")
        _write_worker_csv(contextual_events, worker_dir / "contextual_events.csv")
        _write_worker_csv(contextual_forward, worker_dir / "contextual_forward_returns.csv")

        elapsed = max(time.monotonic() - metrics.start_time, 0.0)
        if verbose_metrics:
            logger.info(
                "%s done symbols=%s rows=%s elapsed=%ss",
                metrics.prefix,
                metrics.symbols_processed,
                format_count(metrics.rows_scanned),
                int(elapsed),
            )
        if queue is not None:
            queue.put(
                {
                    "type": "done",
                    "worker": worker_id,
                    "symbols_processed": metrics.symbols_processed,
                    "rows_scanned": metrics.rows_scanned,
                    "events_evaluated": metrics.events_evaluated,
                    "elapsed": elapsed,
                }
            )
        return {
            "worker": worker_id,
            "symbols_processed": metrics.symbols_processed,
            "rows_scanned": metrics.rows_scanned,
            "events_evaluated": metrics.events_evaluated,
            "elapsed": elapsed,
            "worker_dir": str(worker_dir),
        }
    except Exception as exc:
        if queue is not None:
            queue.put({"type": "error", "worker": worker_id, "message": str(exc)})
            queue.put({"type": "done", "worker": worker_id, "symbols_processed": 0, "rows_scanned": 0, "elapsed": 0})
        raise


def _add_forward_returns_by_symbol(
    eval_mod,
    events_df: pd.DataFrame,
    price_df: pd.DataFrame,
    metrics: Optional[EvalMetrics] = None,
    progress_cb: Optional[Callable[[EvalMetrics], None]] = None,
) -> pd.DataFrame:
    if events_df is None or events_df.empty:
        return eval_mod.add_forward_returns(events_df, price_df, FORWARD_WINDOWS)

    if "symbol" in events_df.columns and "symbol" in price_df.columns:
        frames = []
        for symbol in sorted(events_df["symbol"].dropna().unique()):
            if metrics is not None:
                emitted = metrics.tick_symbol(str(symbol))
                if emitted and progress_cb is not None:
                    progress_cb(metrics)
            evs = events_df[events_df["symbol"] == symbol]
            prices = price_df[price_df["symbol"] == symbol]
            frames.append(eval_mod.add_forward_returns(evs, prices, FORWARD_WINDOWS))
        if not frames:
            return eval_mod.add_forward_returns(events_df, price_df, FORWARD_WINDOWS)
        return pd.concat(frames, ignore_index=True)

    return eval_mod.add_forward_returns(events_df, price_df, FORWARD_WINDOWS)


def _add_daily_forward_returns_by_symbol(
    regime_mod,
    price_df: pd.DataFrame,
    metrics: Optional[EvalMetrics] = None,
    progress_cb: Optional[Callable[[EvalMetrics], None]] = None,
) -> pd.DataFrame:
    if price_df is None or price_df.empty:
        return pd.DataFrame()
    if "symbol" in price_df.columns:
        frames = []
        for symbol in sorted(price_df["symbol"].dropna().unique()):
            if metrics is not None:
                emitted = metrics.tick_symbol(str(symbol))
                if emitted and progress_cb is not None:
                    progress_cb(metrics)
            prices = price_df[price_df["symbol"] == symbol]
            frames.append(regime_mod.add_forward_returns_daily(prices, FORWARD_WINDOWS))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return regime_mod.add_forward_returns_daily(price_df, FORWARD_WINDOWS)


def _log_complete_summary(
    *,
    logger: logging.Logger,
    total_symbols: int,
    workers: int,
    duration_sec: float,
    max_worker_time: float,
    min_worker_time: float,
) -> None:
    avg_rate = total_symbols / duration_sec if duration_sec > 0 else 0.0
    logger.info("[EVAL] COMPLETE")
    logger.info("  symbols_total=%s", total_symbols)
    logger.info("  workers=%s", workers)
    logger.info("  duration_sec=%s", int(duration_sec))
    logger.info("  avg_sym_per_sec=%.2f", avg_rate)
    logger.info("  max_worker_time=%s", int(max_worker_time))
    logger.info("  min_worker_time=%s", int(min_worker_time))


def _run_eval_serial(
    *,
    start_date: date,
    end_date: date,
    symbols: Optional[Iterable[str]],
    benchmark_dir: Optional[Path],
    output_dir: Path,
    verbose_metrics: bool,
    heartbeat_every: int,
) -> None:
    logger = logging.getLogger("prod_vs_bench.eval")
    metrics = EvalMetrics(
        verbose=verbose_metrics,
        heartbeat_every=heartbeat_every,
        logger=logger,
    )

    eval_mod = _load_research_module("research_eval", "docs/research_inputs/eval.py")
    regime_mod = _load_research_module("research_regime_eval", "docs/research_inputs/regime_eval.py")
    contextual_mod = _load_research_module(
        "research_contextual_eval", "docs/research_inputs/contextual_event_eval.py"
    )
    transition_mod = _load_research_module("research_transition_labels", "docs/research_inputs/transition_labels.py")
    sequence_mod = _load_research_module("research_sequence_labels", "docs/research_inputs/sequence_labels.py")

    meta = _metadata(start_date, end_date)
    prod_data = fetch_prod_data(start_date=start_date, end_date=end_date, symbols=symbols)
    ohlcv_df = normalize_ohlcv(prod_data.ohlcv)
    events_df = build_events_df(prod_data.snapshots, detector="baseline")
    regime_df = build_regime_df(prod_data.snapshots)

    metrics.set_total_symbols(len(symbol_list))
    metrics.symbols_processed = len(symbol_list)
    metrics.tick_rows(len(ohlcv_df))
    metrics.tick_rows(len(events_df))
    metrics.tick_rows(len(regime_df))
    metrics.tick_rows(len(transition_events))
    metrics.tick_rows(len(sequence_events))
    metrics.tick_rows(len(contextual_events))
    metrics.tick_events(len(events_df))
    metrics.tick_events(len(transition_events))
    metrics.tick_events(len(sequence_events))
    metrics.tick_events(len(contextual_events))
    metrics.set_forward_windows(len(FORWARD_WINDOWS))
    metrics.set_total_symbols(ohlcv_df["symbol"].nunique() if "symbol" in ohlcv_df.columns else None)

    coverage_years = _coverage_years(ohlcv_df)

    prod_out = output_dir / "prod"
    prod_out.mkdir(parents=True, exist_ok=True)

    bench_out = output_dir / "bench"
    bench_out.mkdir(parents=True, exist_ok=True)

    transition_events = transition_mod.label_regime_transitions(regime_df)
    if transition_events.empty:
        transition_events = transition_events.reindex(
            columns=["symbol", "date", "transition", "prior_regime", "new_regime", "detector", "event"]
        )
    else:
        transition_events = transition_events.copy()
        transition_events["detector"] = "transition"
        transition_events["event"] = transition_events["transition"]
    metrics.tick_rows(len(transition_events))
    metrics.tick_events(len(transition_events))

    sequence_events = sequence_mod.label_event_sequences(events_df)
    if sequence_events.empty:
        sequence_events = sequence_events.reindex(columns=["symbol", "date", "sequence_id", "detector", "event"])
    else:
        sequence_events = sequence_events.copy()
        sequence_events["detector"] = "sequence"
        sequence_events["event"] = sequence_events["sequence_id"]
    metrics.tick_rows(len(sequence_events))
    metrics.tick_events(len(sequence_events))

    contextual_events = contextual_mod.attach_prior_regime(events_df, regime_df)
    if contextual_events.empty:
        contextual_events = contextual_events.reindex(
            columns=["symbol", "date", "event", "prior_regime", "base_event", "detector"]
        )
    else:
        contextual_events = contextual_events.copy()
        contextual_events["base_event"] = contextual_events["event"]
        contextual_events["event"] = contextual_events.apply(
            lambda row: f"{row['event']}:{row['prior_regime']}"
            if pd.notna(row.get("prior_regime"))
            else f"{row['event']}:UNKNOWN",
            axis=1,
        )
        contextual_events["detector"] = "contextual"
    metrics.tick_rows(len(contextual_events))
    metrics.tick_events(len(contextual_events))

    baseline_forward = _add_forward_returns_by_symbol(eval_mod, events_df, ohlcv_df, metrics)
    transition_forward = _add_forward_returns_by_symbol(eval_mod, transition_events, ohlcv_df, metrics)
    sequence_forward = _add_forward_returns_by_symbol(eval_mod, sequence_events, ohlcv_df, metrics)
    contextual_forward = _add_forward_returns_by_symbol(eval_mod, contextual_events, ohlcv_df, metrics)

    baseline_summary = eval_mod.summarize_forward_returns(baseline_forward, coverage_years)
    transition_summary = eval_mod.summarize_forward_returns(transition_forward, coverage_years)
    sequence_summary = eval_mod.summarize_forward_returns(sequence_forward, coverage_years)
    contextual_summary = eval_mod.summarize_forward_returns(contextual_forward, coverage_years)

    incremental_baseline = eval_mod.build_comparison_table(baseline_summary)
    transition_comparison = eval_mod.build_comparison_table(transition_summary)
    sequence_comparison = eval_mod.build_comparison_table(sequence_summary)
    contextual_comparison = eval_mod.build_comparison_table(contextual_summary)

    daily_forward = _add_daily_forward_returns_by_symbol(regime_mod, ohlcv_df, metrics)
    baseline_regime_summary = regime_mod.summarize_regimes(regime_df, daily_forward)
    baseline_regime_pairwise = regime_mod.pairwise_vs_baseline(baseline_regime_summary)

    files = {
        "baseline_events.csv": events_df,
        "baseline_forward_returns.csv": baseline_forward,
        "baseline_regime_summary.csv": baseline_regime_summary,
        "baseline_regime_pairwise.csv": baseline_regime_pairwise,
        "transition_events.csv": transition_events,
        "transition_forward_returns.csv": transition_forward,
        "transition_summary.csv": transition_summary,
        "sequence_events.csv": sequence_events,
        "sequence_forward_returns.csv": sequence_forward,
        "sequence_summary.csv": sequence_summary,
        "contextual_events.csv": contextual_events,
        "contextual_forward_returns.csv": contextual_forward,
        "contextual_summary.csv": contextual_summary,
        "incremental_baseline_comparison.csv": incremental_baseline,
        "transition_comparison.csv": transition_comparison,
        "sequence_comparison.csv": sequence_comparison,
        "contextual_comparison.csv": contextual_comparison,
    }

    for filename, df in files.items():
        benchmark_columns = _read_benchmark_columns(benchmark_dir, filename)
        _write_csv(df, prod_out / filename, meta, benchmark_columns, metrics)

    _copy_benchmark_outputs(benchmark_dir, bench_out)
    metrics.log_summary()
    if verbose_metrics:
        duration = max(time.monotonic() - metrics.start_time, 0.0)
        total_symbols = metrics.symbols_processed
        _log_complete_summary(
            logger=logger,
            total_symbols=total_symbols,
            workers=1,
            duration_sec=duration,
            max_worker_time=duration,
            min_worker_time=duration,
        )


def run_eval(
    *,
    start_date: date,
    end_date: date,
    symbols: Optional[Iterable[str]],
    benchmark_dir: Optional[Path],
    output_dir: Path,
    verbose_metrics: bool = False,
    heartbeat_every: int = 25,
    workers: Optional[int] = None,
    max_workers: int = 8,
) -> None:
    cpu_count = os.cpu_count() or 1
    default_workers = min(6, cpu_count)
    worker_count = int(workers) if workers is not None else default_workers
    worker_count = max(1, worker_count)
    max_workers = max(1, int(max_workers))
    worker_count = min(worker_count, max_workers)

    if worker_count <= 1:
        _run_eval_serial(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            benchmark_dir=benchmark_dir,
            output_dir=output_dir,
            verbose_metrics=verbose_metrics,
            heartbeat_every=heartbeat_every,
        )
        return

    logger = logging.getLogger("prod_vs_bench.eval")
    metrics = EvalMetrics(
        verbose=verbose_metrics,
        heartbeat_every=heartbeat_every,
        logger=logger,
    )
    metrics.set_forward_windows(len(FORWARD_WINDOWS))

    symbol_list = _fetch_symbol_universe(symbols)
    metrics.set_total_symbols(len(symbol_list))

    batches = _split_batches(symbol_list, worker_count)
    worker_count = len(batches)
    if worker_count <= 1:
        _run_eval_serial(
            start_date=start_date,
            end_date=end_date,
            symbols=symbol_list,
            benchmark_dir=benchmark_dir,
            output_dir=output_dir,
            verbose_metrics=verbose_metrics,
            heartbeat_every=heartbeat_every,
        )
        return

    worker_root = output_dir / "workers"
    if worker_root.exists():
        shutil.rmtree(worker_root)
    worker_root.mkdir(parents=True, exist_ok=True)

    ctx = mp.get_context("spawn")
    manager = ctx.Manager()
    queue = manager.Queue()
    monitor_lock = threading.Lock()
    monitor_state = {
        "worker_counts": {},
        "next_heartbeat": heartbeat_every,
    }

    def monitor() -> None:
        done_workers = 0
        while done_workers < worker_count:
            msg = queue.get()
            if not isinstance(msg, dict):
                continue
            msg_type = msg.get("type")
            if msg_type == "done":
                done_workers += 1
            if msg_type not in {"progress", "done"}:
                if msg_type == "error":
                    logger.error("[EVAL] worker_error worker=%s message=%s", msg.get("worker"), msg.get("message"))
                continue
            worker_id = msg.get("worker")
            if worker_id is None:
                continue
            with monitor_lock:
                monitor_state["worker_counts"][worker_id] = {
                    "symbols_processed": int(msg.get("symbols_processed", 0)),
                    "rows_scanned": int(msg.get("rows_scanned", 0)),
                    "events_evaluated": int(msg.get("events_evaluated", 0)),
                }
                total_symbols = sum(
                    count["symbols_processed"] for count in monitor_state["worker_counts"].values()
                )
                total_rows = sum(count["rows_scanned"] for count in monitor_state["worker_counts"].values())
                total_events = sum(count["events_evaluated"] for count in monitor_state["worker_counts"].values())
                if verbose_metrics and heartbeat_every > 0:
                    while total_symbols >= monitor_state["next_heartbeat"]:
                        elapsed = max(time.monotonic() - metrics.start_time, 0.0)
                        rate = total_symbols / elapsed if elapsed > 0 else 0.0
                        logger.info(
                            "[EVAL] progress symbols=%s/%s rows=%s events=%s elapsed=%ss rate=%.2f sym/s",
                            total_symbols,
                            metrics.total_symbols if metrics.total_symbols is not None else "?",
                            format_count(total_rows),
                            format_count(total_events),
                            int(elapsed),
                            rate,
                        )
                        monitor_state["next_heartbeat"] += heartbeat_every

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

    futures = []
    results = []
    start_time = time.monotonic()
    with ctx.Pool(processes=worker_count) as pool:
        try:
            for idx, batch in enumerate(batches, start=1):
                futures.append(
                    pool.apply_async(
                        _worker_eval,
                        kwds={
                            "worker_id": idx,
                            "symbols": batch,
                            "start_date": start_date,
                            "end_date": end_date,
                            "output_dir": worker_root,
                            "verbose_metrics": verbose_metrics,
                            "heartbeat_every": heartbeat_every,
                            "queue": queue,
                        },
                    )
                )
            for future in futures:
                results.append(future.get())
        except Exception:
            pool.terminate()
            raise

    duration = max(time.monotonic() - start_time, 0.0)
    monitor_thread.join(timeout=1.0)

    worker_dirs = [Path(result["worker_dir"]) for result in results]

    eval_mod = _load_research_module("research_eval", "docs/research_inputs/eval.py")
    regime_mod = _load_research_module("research_regime_eval", "docs/research_inputs/regime_eval.py")

    meta = _metadata(start_date, end_date)

    ohlcv_df = _merge_worker_csvs(worker_dirs, "ohlcv.csv")
    regime_df = _merge_worker_csvs(worker_dirs, "regime.csv")
    daily_forward = _merge_worker_csvs(worker_dirs, "daily_forward_returns.csv")
    events_df = _merge_worker_csvs(worker_dirs, "baseline_events.csv")
    baseline_forward = _merge_worker_csvs(worker_dirs, "baseline_forward_returns.csv")
    transition_events = _merge_worker_csvs(worker_dirs, "transition_events.csv")
    transition_forward = _merge_worker_csvs(worker_dirs, "transition_forward_returns.csv")
    sequence_events = _merge_worker_csvs(worker_dirs, "sequence_events.csv")
    sequence_forward = _merge_worker_csvs(worker_dirs, "sequence_forward_returns.csv")
    contextual_events = _merge_worker_csvs(worker_dirs, "contextual_events.csv")
    contextual_forward = _merge_worker_csvs(worker_dirs, "contextual_forward_returns.csv")

    ohlcv_df = _sort_df(ohlcv_df, ["symbol", "date"])
    regime_df = _sort_df(regime_df, ["symbol", "date"])
    daily_forward = _sort_df(daily_forward, ["symbol", "date"])
    events_df = _sort_df(events_df, ["symbol", "date", "event", "detector"])
    baseline_forward = _sort_df(baseline_forward, ["symbol", "date", "event", "detector"])
    transition_events = _sort_df(transition_events, ["symbol", "date", "event", "detector"])
    transition_forward = _sort_df(transition_forward, ["symbol", "date", "event", "detector"])
    sequence_events = _sort_df(sequence_events, ["symbol", "date", "sequence_id", "event", "detector"])
    sequence_forward = _sort_df(sequence_forward, ["symbol", "date", "event", "detector"])
    contextual_events = _sort_df(contextual_events, ["symbol", "date", "event", "detector"])
    contextual_forward = _sort_df(contextual_forward, ["symbol", "date", "event", "detector"])

    metrics.tick_rows(len(ohlcv_df))
    metrics.tick_rows(len(events_df))
    metrics.tick_rows(len(regime_df))
    metrics.tick_events(len(events_df))

    coverage_years = _coverage_years(ohlcv_df)

    baseline_summary = eval_mod.summarize_forward_returns(baseline_forward, coverage_years)
    transition_summary = eval_mod.summarize_forward_returns(transition_forward, coverage_years)
    sequence_summary = eval_mod.summarize_forward_returns(sequence_forward, coverage_years)
    contextual_summary = eval_mod.summarize_forward_returns(contextual_forward, coverage_years)

    incremental_baseline = eval_mod.build_comparison_table(baseline_summary)
    transition_comparison = eval_mod.build_comparison_table(transition_summary)
    sequence_comparison = eval_mod.build_comparison_table(sequence_summary)
    contextual_comparison = eval_mod.build_comparison_table(contextual_summary)

    baseline_regime_summary = regime_mod.summarize_regimes(regime_df, daily_forward)
    baseline_regime_pairwise = regime_mod.pairwise_vs_baseline(baseline_regime_summary)

    prod_out = output_dir / "prod"
    prod_out.mkdir(parents=True, exist_ok=True)
    bench_out = output_dir / "bench"
    bench_out.mkdir(parents=True, exist_ok=True)

    files = {
        "baseline_events.csv": events_df,
        "baseline_forward_returns.csv": baseline_forward,
        "baseline_regime_summary.csv": baseline_regime_summary,
        "baseline_regime_pairwise.csv": baseline_regime_pairwise,
        "transition_events.csv": transition_events,
        "transition_forward_returns.csv": transition_forward,
        "transition_summary.csv": transition_summary,
        "sequence_events.csv": sequence_events,
        "sequence_forward_returns.csv": sequence_forward,
        "sequence_summary.csv": sequence_summary,
        "contextual_events.csv": contextual_events,
        "contextual_forward_returns.csv": contextual_forward,
        "contextual_summary.csv": contextual_summary,
        "incremental_baseline_comparison.csv": incremental_baseline,
        "transition_comparison.csv": transition_comparison,
        "sequence_comparison.csv": sequence_comparison,
        "contextual_comparison.csv": contextual_comparison,
    }

    for filename, df in files.items():
        benchmark_columns = _read_benchmark_columns(benchmark_dir, filename)
        _write_csv(df, prod_out / filename, meta, benchmark_columns, metrics)

    _copy_benchmark_outputs(benchmark_dir, bench_out)
    metrics.log_summary()

    if verbose_metrics and results:
        total_symbols = len(symbol_list)
        worker_times = [result["elapsed"] for result in results if result is not None]
        max_worker_time = max(worker_times) if worker_times else duration
        min_worker_time = min(worker_times) if worker_times else duration
        _log_complete_summary(
            logger=logger,
            total_symbols=total_symbols,
            workers=worker_count,
            duration_sec=duration,
            max_worker_time=max_worker_time,
            min_worker_time=min_worker_time,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run production Wyckoff evaluation against benchmark outputs.")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--benchmark-dir",
        default=None,
        help="Benchmark output directory to mirror into outputs/bench and align schemas",
    )
    parser.add_argument(
        "--output-dir",
        default="tools/prod_vs_bench/outputs",
        help="Output directory root",
    )
    parser.add_argument("--symbols", default=None, help="Comma-separated symbols override")
    parser.add_argument("--verbose-metrics", action="store_true", help="Enable verbose progress metrics logging")
    parser.add_argument(
        "--heartbeat-every",
        type=int,
        default=25,
        help="Emit heartbeat every N symbols when verbose metrics enabled",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Worker processes (default: min(6, cpu_count))",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Hard cap on workers",
    )

    args = parser.parse_args()
    if args.verbose_metrics:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    benchmark_dir = Path(args.benchmark_dir) if args.benchmark_dir else None
    output_dir = Path(args.output_dir)

    run_eval(
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        benchmark_dir=benchmark_dir,
        output_dir=output_dir,
        verbose_metrics=args.verbose_metrics,
        heartbeat_every=args.heartbeat_every,
        workers=args.workers,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()
