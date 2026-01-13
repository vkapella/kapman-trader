#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2

from core.charting import (
    PANEL_SPECS,
    normalize_snapshot_payload,
    resolve_metric_series,
    series_has_values,
)
from core.charting.metrics_registry import CLI_GROUP_ALIASES, METRIC_REGISTRY, MetricSpec
from core.ingestion.ohlcv.db import default_db_url

MA_PERIODS = (20, 50, 200)
ADX_GROUP_KEYS = ("ADX", "ADX_POS", "ADX_NEG")
MA_KEYS = {metric.key for metric in METRIC_REGISTRY if metric.cli_group == "MA"}
MA_KEYS.update(CLI_GROUP_ALIASES.get("MA", set()))
MA_KEYS.update({"SMA14", "EMA_INDICATOR", "WMA", "KAMA"})
BBANDS_KEYS = [metric.key for metric in METRIC_REGISTRY if metric.key.startswith("BBANDS_")]


@dataclass(frozen=True)
class ChartOutputs:
    png_paths: list[Path]
    pdf_paths: list[Path]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate OHLCV + TA chart packs (PNG + PDF) for LLM processing "
            "from persisted KapMan OHLCV data."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbols", type=str, help="Comma-separated symbols (e.g., AAPL,MSFT)")
    group.add_argument("--watchlist", type=str, help="Watchlist name")
    parser.add_argument("--start-date", type=_parse_date, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=_parse_date, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--bars", type=int, default=90, help="Bars to include (default: 90)")
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data/chart_packs/",
        help="Output directory (default: data/chart_packs/)",
    )
    parser.add_argument(
        "--pdf-batch-size",
        type=int,
        default=30,
        help="PNG batch size per PDF (default: 30)",
    )
    parser.add_argument(
        "--ta-metrics",
        type=str,
        default=None,
        help="Comma-separated metric keys or groups (derived from the metrics registry)",
    )
    return parser


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (expected YYYY-MM-DD)") from e


def parse_symbols(value: str) -> list[str]:
    symbols = [s.strip().upper() for s in value.split(",") if s.strip()]
    seen = set()
    ordered: list[str] = []
    for sym in symbols:
        if sym not in seen:
            ordered.append(sym)
            seen.add(sym)
    return sorted(ordered)


def _registry_index() -> tuple[dict[str, MetricSpec], dict[str, list[MetricSpec]]]:
    key_map: dict[str, MetricSpec] = {}
    group_map: dict[str, list[MetricSpec]] = {}
    for metric in METRIC_REGISTRY:
        key_map[metric.key.upper()] = metric
        group_key = metric.cli_group.upper()
        group_map.setdefault(group_key, []).append(metric)

    for alias, alias_keys in CLI_GROUP_ALIASES.items():
        alias_key = alias.upper()
        if alias_key in group_map:
            continue
        alias_metrics = [metric for metric in METRIC_REGISTRY if metric.key in alias_keys]
        if alias_metrics:
            group_map[alias_key] = alias_metrics

    return key_map, group_map


def parse_ta_metrics(value: str | None) -> list[MetricSpec]:
    if value is None:
        return []
    tokens = [m.strip().upper() for m in value.split(",") if m.strip()]
    if not tokens:
        return []
    key_map, group_map = _registry_index()
    invalid: list[str] = []
    seen = set()
    ordered: list[MetricSpec] = []
    for token in tokens:
        if token in key_map:
            metric = key_map[token]
            if metric.key not in seen:
                ordered.append(metric)
                seen.add(metric.key)
            continue
        if token in group_map:
            for metric in group_map[token]:
                if metric.key not in seen:
                    ordered.append(metric)
                    seen.add(metric.key)
            continue
        invalid.append(token)

    if invalid:
        valid_keys = [metric.key for metric in METRIC_REGISTRY]
        valid_groups = sorted(group_map.keys())
        raise ValueError(
            "Invalid --ta-metrics entries: "
            f"{', '.join(invalid)}. "
            "Valid metric keys: "
            f"{', '.join(valid_keys)}. "
            "Valid groups: "
            f"{', '.join(valid_groups)}"
        )

    return ordered


def _configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger("kapman.chart_pack")


def _resolve_imagemagick() -> list[str]:
    for cmd in ("magick", "convert"):
        if shutil.which(cmd):
            return [cmd]
    raise SystemExit(
        "ImageMagick not found. Install ImageMagick and ensure `magick` or `convert` is in PATH."
    )


def _ensure_positive(name: str, value: int) -> int:
    if value <= 0:
        raise SystemExit(f"--{name} must be a positive integer")
    return value


def _latest_ohlcv_date(conn) -> date | None:
    with conn.cursor() as cur:
        cur.execute("SELECT max(date) FROM ohlcv")
        return cur.fetchone()[0]


def _load_watchlist_symbols(conn, watchlist: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT symbol
            FROM watchlists
            WHERE watchlist_id = %s AND active = TRUE
            ORDER BY symbol ASC
            """,
            (watchlist,),
        )
        rows = [r[0].upper() for r in cur.fetchall()]
    return rows


def _fetch_ohlcv(
    conn,
    symbol: str,
    *,
    start_date: date | None,
    end_date: date | None,
    bars: int,
) -> pd.DataFrame:
    params: list[object] = [symbol]
    clauses = ["t.symbol = %s"]
    if start_date is not None:
        clauses.append("o.date >= %s")
        params.append(start_date)
    if end_date is not None:
        clauses.append("o.date <= %s")
        params.append(end_date)
    where_sql = " AND ".join(clauses)
    sql = f"""
        SELECT o.date, o.open, o.high, o.low, o.close, o.volume
        FROM ohlcv o
        JOIN tickers t ON t.id = o.ticker_id
        WHERE {where_sql}
        ORDER BY o.date DESC
        LIMIT %s
    """
    params.append(bars)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _fetch_daily_snapshots(
    conn,
    symbol: str,
    dates: list[date],
) -> dict[date, dict[str, object]]:
    if not dates:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ds.time::date,
                ds.technical_indicators_json,
                ds.dealer_metrics_json,
                ds.volatility_metrics_json
            FROM daily_snapshots ds
            JOIN tickers t ON t.id = ds.ticker_id
            WHERE t.symbol = %s AND ds.time::date = ANY(%s)
            """,
            (symbol, dates),
        )
        rows = cur.fetchall()
    return {
        row[0]: {
            "technical": row[1],
            "dealer": row[2],
            "volatility": row[3],
        }
        for row in rows
    }


def _apply_panel_legend(ax) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    filtered: list[tuple[object, str]] = []
    seen: set[str] = set()
    for handle, label in zip(handles, labels):
        if not label or label.startswith("_"):
            continue
        if label in seen:
            continue
        filtered.append((handle, label))
        seen.add(label)
    if filtered:
        ax.legend(
            [item[0] for item in filtered],
            [item[1] for item in filtered],
            loc="upper left",
            fontsize=8,
            frameon=False,
        )


def _render_chart(
    symbol: str,
    df: pd.DataFrame,
    price_overlays: list[MetricSpec],
    panel_entries: list[list[MetricSpec]],
    metric_series: dict[str, pd.Series],
    output_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.edgecolor": "#333333",
            "axes.grid": True,
            "grid.color": "#dddddd",
            "grid.linewidth": 0.5,
        }
    )

    x = np.arange(len(df))
    dates = df["date"].dt.strftime("%Y-%m-%d").tolist()
    height_ratios = [3.6] + [1.2] * len(panel_entries)
    fig = plt.figure(figsize=(12, sum(height_ratios) + 0.7))
    gs = fig.add_gridspec(nrows=len(height_ratios), ncols=1, height_ratios=height_ratios, hspace=0.18)

    axes: list[plt.Axes] = []
    for i in range(len(height_ratios)):
        if i == 0:
            ax = fig.add_subplot(gs[i, 0])
        else:
            ax = fig.add_subplot(gs[i, 0], sharex=axes[0])
        axes.append(ax)

    ax_price = axes[0]
    candle_width = 0.6
    for idx, row in df.iterrows():
        open_p = row["open"]
        close_p = row["close"]
        high_p = row["high"]
        low_p = row["low"]
        if pd.isna(open_p) or pd.isna(close_p) or pd.isna(high_p) or pd.isna(low_p):
            continue
        color = "#2ca02c" if close_p >= open_p else "#d62728"
        ax_price.vlines(idx, low_p, high_p, color=color, linewidth=1)
        lower = min(open_p, close_p)
        height = max(abs(close_p - open_p), 0.0001)
        ax_price.add_patch(
            Rectangle(
                (idx - candle_width / 2, lower),
                candle_width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=1,
            )
        )

    ax_vol = ax_price.twinx()
    max_vol = df["volume"].max() if not df["volume"].empty else 0
    if pd.isna(max_vol) or max_vol <= 0:
        max_vol = 1
    vol_colors = ["#4c72b0" if row["close"] >= row["open"] else "#c44e52" for _, row in df.iterrows()]
    ax_vol.bar(x, df["volume"].fillna(0.0), width=candle_width, color=vol_colors, alpha=0.3)
    ax_vol.set_ylim(0, max_vol * 5)
    ax_vol.set_ylabel("Volume", labelpad=8)
    ax_vol.yaxis.set_label_position("right")
    ax_vol.yaxis.tick_right()
    ax_vol.tick_params(axis="y", labelsize=8, pad=4)
    ax_vol.spines["left"].set_visible(False)
    ax_vol.grid(False)
    ax_vol.set_zorder(0)
    ax_price.set_zorder(2)
    ax_price.patch.set_alpha(0)
    ax_price.set_title(f"{symbol} OHLCV", loc="left")
    ax_price.set_ylabel(PANEL_SPECS["PRICE"].ylabel)
    ax_price.margins(x=0.01)

    for metric in price_overlays:
        series = metric_series.get(metric.key)
        if series is None or not series_has_values(series):
            continue
        if metric.kind == "hist":
            mask = series.notna().to_numpy()
            values = series.to_numpy()[mask]
            positions = x[mask]
            if metric.negative_color:
                colors = [metric.color if v >= 0 else metric.negative_color for v in values]
            else:
                colors = metric.color
            ax_price.bar(positions, values, color=colors, alpha=metric.alpha, label=metric.label)
        else:
            ax_price.plot(
                x,
                series.values,
                color=metric.color,
                linewidth=metric.linewidth,
                alpha=metric.alpha,
                label=metric.label,
            )
    _apply_panel_legend(ax_price)

    panel_idx = 1
    for panel_metrics in panel_entries:
        ax = axes[panel_idx]
        has_series = False
        for metric in panel_metrics:
            series = metric_series.get(metric.key)
            if series is None or not series_has_values(series):
                continue
            has_series = True
            if metric.kind == "hist":
                mask = series.notna().to_numpy()
                values = series.to_numpy()[mask]
                positions = x[mask]
                if metric.negative_color:
                    colors = [metric.color if v >= 0 else metric.negative_color for v in values]
                else:
                    colors = metric.color
                ax.bar(positions, values, color=colors, alpha=metric.alpha, label=metric.label)
            else:
                ax.plot(
                    x,
                    series.values,
                    color=metric.color,
                    linewidth=metric.linewidth,
                    alpha=metric.alpha,
                    label=metric.label,
                )
        if not has_series:
            panel_idx += 1
            continue
        if len(panel_metrics) == 1:
            ax.set_ylabel(panel_metrics[0].label)
        _apply_panel_legend(ax)
        panel_idx += 1

    for i, ax in enumerate(axes):
        if i < len(axes) - 1:
            ax.tick_params(labelbottom=False)
        ax.grid(True, axis="y")

    tick_count = min(6, len(x))
    if tick_count > 0:
        indices = np.linspace(0, len(x) - 1, tick_count, dtype=int)
        axes[-1].set_xticks(indices)
        axes[-1].set_xticklabels([dates[i] for i in indices], rotation=45, ha="right")

    axes[-1].tick_params(axis="x", pad=6)
    fig.tight_layout(rect=[0, 0.04, 1, 0.98])
    fig.subplots_adjust(bottom=0.16)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _render_pdf_batches(
    imagemagick_cmd: list[str],
    png_paths: list[Path],
    *,
    pdf_dir: Path,
    batch_size: int,
) -> list[Path]:
    pdf_paths: list[Path] = []
    for i in range(0, len(png_paths), batch_size):
        batch = png_paths[i : i + batch_size]
        batch_id = (i // batch_size) + 1
        pdf_path = pdf_dir / f"charts_{batch_id}.pdf"
        cmd = imagemagick_cmd + ["-density", "150"] + [str(p) for p in batch] + [str(pdf_path)]
        subprocess.run(cmd, check=True)
        pdf_paths.append(pdf_path)
    return pdf_paths


def main(argv: list[str]) -> int:
    log = _configure_logging()
    args = build_parser().parse_args(argv)

    bars = _ensure_positive("bars", args.bars)
    batch_size = _ensure_positive("pdf-batch-size", args.pdf_batch_size)
    try:
        requested_metrics = parse_ta_metrics(args.ta_metrics)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    metric_by_key = {metric.key: metric for metric in METRIC_REGISTRY}
    expanded_metrics = list(requested_metrics)
    requested_keys = {metric.key for metric in requested_metrics}
    if requested_keys.intersection(ADX_GROUP_KEYS):
        for key in ADX_GROUP_KEYS:
            if key not in requested_keys and key in metric_by_key:
                expanded_metrics.append(metric_by_key[key])
                requested_keys.add(key)
    if requested_keys.intersection(BBANDS_KEYS):
        for key in BBANDS_KEYS:
            if key not in requested_keys and key in metric_by_key:
                expanded_metrics.append(metric_by_key[key])
                requested_keys.add(key)

    db_url = default_db_url()
    imagemagick_cmd = _resolve_imagemagick()

    out_root = Path(args.out_dir).expanduser().resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / run_id
    png_dir = run_dir / "png"
    pdf_dir = run_dir / "pdf"
    mpl_config_dir = run_dir / "mplconfig"
    for path in (png_dir, pdf_dir, mpl_config_dir):
        path.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(mpl_config_dir)

    with psycopg2.connect(db_url) as conn:
        if args.symbols:
            symbols = parse_symbols(args.symbols)
            if not symbols:
                raise SystemExit("No symbols provided after parsing --symbols")
        else:
            symbols = _load_watchlist_symbols(conn, args.watchlist)
            if not symbols:
                raise SystemExit(f"No active symbols found for watchlist: {args.watchlist}")

        end_date = args.end_date
        if end_date is None:
            end_date = _latest_ohlcv_date(conn)
            if end_date is None:
                raise SystemExit("No OHLCV data available to determine end date")

        png_paths: list[Path] = []
        skipped = 0
        for idx, symbol in enumerate(symbols, start=1):
            try:
                df = _fetch_ohlcv(
                    conn,
                    symbol,
                    start_date=args.start_date,
                    end_date=end_date,
                    bars=bars,
                )
                if df.empty:
                    log.warning("No OHLCV rows for %s; skipping", symbol)
                    skipped += 1
                    continue

                metric_series: dict[str, pd.Series] = {}
                if expanded_metrics:
                    ohlcv_dates = df["date"].dt.date.tolist()
                    snapshots_raw = _fetch_daily_snapshots(conn, symbol, ohlcv_dates)
                    snapshots_by_source: dict[str, dict[date, object]] = {
                        "technical": {},
                        "dealer": {},
                        "volatility": {},
                    }
                    for snap_date, payloads in snapshots_raw.items():
                        for source in snapshots_by_source:
                            payload = payloads.get(source)
                            snapshots_by_source[source][snap_date] = normalize_snapshot_payload(
                                payload, logger=log
                            )

                    for metric in expanded_metrics:
                        source_payloads = snapshots_by_source.get(metric.source, {})
                        try:
                            metric_series[metric.key] = resolve_metric_series(
                                source_payloads,
                                df["date"],
                                metric.json_path,
                                logger=log,
                            )
                        except Exception:
                            log.exception("Failed to resolve metric %s on %s", metric.key, symbol)
                            metric_series[metric.key] = pd.Series(np.nan, index=df["date"])

                metrics_with_data: set[str] = set()
                for metric in expanded_metrics:
                    series = metric_series.get(metric.key)
                    if series is not None and series_has_values(series):
                        metrics_with_data.add(metric.key)
                    else:
                        log.warning("No persisted values for %s on %s; skipping", metric.key, symbol)

                if expanded_metrics and not metrics_with_data:
                    log.warning("No persisted metrics resolved for %s; rendering price panel only", symbol)

                png_name = f"{idx:03d}_{symbol}.png"
                png_path = png_dir / png_name
                overlay_keys = MA_KEYS.union(BBANDS_KEYS)
                price_overlays: list[MetricSpec] = []
                seen_overlays: set[str] = set()
                for metric in expanded_metrics:
                    if metric.key in overlay_keys and metric.key in metrics_with_data:
                        if metric.key not in seen_overlays:
                            price_overlays.append(metric)
                            seen_overlays.add(metric.key)

                panel_entries: list[list[MetricSpec]] = []
                seen_panels: set[str] = set()
                adx_panel_added = False
                for metric in expanded_metrics:
                    if metric.key in overlay_keys:
                        continue
                    if metric.key in ADX_GROUP_KEYS:
                        if not adx_panel_added:
                            adx_panel_added = True
                            adx_metrics = [
                                metric_by_key[key]
                                for key in ADX_GROUP_KEYS
                                if key in metric_by_key and key in metrics_with_data
                            ]
                            if adx_metrics:
                                panel_entries.append(adx_metrics)
                        continue
                    if metric.key in metrics_with_data and metric.key not in seen_panels:
                        panel_entries.append([metric])
                        seen_panels.add(metric.key)

                _render_chart(symbol, df, price_overlays, panel_entries, metric_series, png_path)
                png_paths.append(png_path)
            except Exception:
                log.exception("Failed to render %s; skipping", symbol)
                skipped += 1

    pdf_paths = _render_pdf_batches(
        imagemagick_cmd,
        png_paths,
        pdf_dir=pdf_dir,
        batch_size=batch_size,
    )

    log.info(
        "chart_pack completed: symbols=%d rendered=%d skipped=%d pdf_batches=%d out_dir=%s",
        len(symbols),
        len(png_paths),
        skipped,
        len(pdf_paths),
        run_dir,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
