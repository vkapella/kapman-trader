"""
Report generation for Wyckoff benchmark summaries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pandas as pd


def _comparison_from_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build comparison table: best impl per event/horizon using return + MAE ranks.
    """
    rows = []
    if summary_df.empty:
        return pd.DataFrame(columns=["event", "horizon", "impl", "mean_return", "mae_mean", "composite_rank"])

    for (event, horizon), group in summary_df.groupby(["event", "horizon"]):
        ranked = group.copy()
        ranked["return_rank"] = ranked["mean_return"].rank(ascending=False, method="min")
        ranked["mae_rank"] = ranked["mae_mean"].rank(ascending=True, method="min")
        ranked["composite_rank"] = (ranked["return_rank"] + ranked["mae_rank"]) / 2
        best = ranked.sort_values(["composite_rank", "mean_return"], ascending=[True, False]).iloc[0]
        rows.append(
            {
                "event": event,
                "horizon": horizon,
                "impl": best["impl"],
                "mean_return": best["mean_return"],
                "mae_mean": best["mae_mean"],
                "composite_rank": best["composite_rank"],
            }
        )
    return pd.DataFrame(rows)


def _comparison_directional_from_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build comparison table with direction/role awareness.
    """
    rows = []
    if summary_df.empty:
        return pd.DataFrame(
            columns=["event", "direction", "role", "horizon", "impl", "mean_return", "mae_mean", "signal_count", "composite_rank"]
        )

    for (event, direction, role, horizon), group in summary_df.groupby(["event", "direction", "role", "horizon"]):
        ranked = group.copy()
        ranked["return_rank"] = ranked["mean_return"].rank(ascending=False, method="min")
        ranked["mae_rank"] = ranked["mae_mean"].rank(ascending=True, method="min")
        ranked["composite_rank"] = (ranked["return_rank"] + ranked["mae_rank"]) / 2
        best = ranked.sort_values(["composite_rank", "mean_return"], ascending=[True, False]).iloc[0]
        rows.append(
            {
                "event": event,
                "direction": direction,
                "role": role,
                "horizon": horizon,
                "impl": best["impl"],
                "mean_return": best["mean_return"],
                "mae_mean": best["mae_mean"],
                "signal_count": best["signal_count"],
                "composite_rank": best["composite_rank"],
            }
        )
    return pd.DataFrame(rows)


def write_reports(
    evaluated_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    directional_summary_df: pd.DataFrame | None,
    output_dir: Path | str,
    run_id: str,
) -> Tuple[Path, Path, Path]:
    """
    Persist summary + comparison artifacts.
    Returns (summary_path, comparison_path, comparison_directional_path).
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    summary_path_parquet = output_path / f"summary_{run_id}.parquet"
    summary_path_csv = output_path / f"summary_{run_id}.csv"
    summary_df.to_parquet(summary_path_parquet, index=False)
    summary_df.to_csv(summary_path_csv, index=False)

    comparison_df = _comparison_from_summary(summary_df)
    comparison_path = output_path / f"comparison_{run_id}.csv"
    comparison_df.to_csv(comparison_path, index=False)

    comparison_directional_path = output_path / f"comparison_directional_{run_id}.csv"
    if directional_summary_df is not None:
        comp_dir_df = _comparison_directional_from_summary(directional_summary_df)
        comp_dir_df.to_csv(comparison_directional_path, index=False)
        # Latest snapshot without run_id for convenience
        (output_path / "comparison_directional.csv").write_text(comp_dir_df.to_csv(index=False))

    return summary_path_parquet, comparison_path, comparison_directional_path


def write_entry_summary(
    summary_df: pd.DataFrame,
    output_dir: Path | str,
) -> Tuple[Path, Path | None]:
    """
    Persist entry-only directional summary and optional scored parquet path.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary_path = output_path / "entry_direction_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    return summary_path, None
