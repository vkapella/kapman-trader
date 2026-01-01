from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _bootstrap_ci(
    data: np.ndarray, n_bootstrap: int = 1000, ci: float = 0.95
) -> tuple[float, float]:
    values = np.asarray(data, dtype=float)
    values = values[~np.isnan(values)]
    if values.size == 0:
        return np.nan, np.nan

    n_bootstrap = max(1, int(n_bootstrap))
    rng = np.random.default_rng()
    medians = np.empty(n_bootstrap, dtype=float)
    for i in range(n_bootstrap):
        sample = rng.choice(values, size=values.size, replace=True)
        medians[i] = np.median(sample)

    alpha = (1.0 - ci) / 2.0
    low = np.quantile(medians, alpha)
    high = np.quantile(medians, 1.0 - alpha)
    return float(low), float(high)


def add_forward_returns(
    events_df: pd.DataFrame, price_df: pd.DataFrame, forward_windows: Iterable[int]
) -> pd.DataFrame:
    forward_windows = sorted(set(int(w) for w in forward_windows))
    base_columns = list(events_df.columns) + [f"fwd_{w}" for w in forward_windows]
    if events_df.empty:
        return pd.DataFrame(columns=base_columns)

    price = price_df[["date", "close"]].copy()
    price["date"] = pd.to_datetime(price["date"])
    price = price.sort_values("date").reset_index(drop=True)
    price.set_index("date", inplace=True)

    for window in forward_windows:
        price[f"fwd_{window}"] = price["close"].shift(-window) / price["close"] - 1.0

    events = events_df.copy()
    events["date"] = pd.to_datetime(events["date"])
    events = events.sort_values("date").set_index("date")

    for window in forward_windows:
        events[f"fwd_{window}"] = price[f"fwd_{window}"].reindex(events.index)

    return events.reset_index()


def summarize_forward_returns(
    forward_df: pd.DataFrame,
    coverage_years: float,
    bootstrap_ci_enabled: bool = False,
    bootstrap_resamples: int = 1000,
) -> pd.DataFrame:
    columns = [
        "detector",
        "event",
        "density",
        "median_fwd_20",
        "win_rate_20",
        "p5_fwd_20",
        "stability_delta",
        "event_count",
    ]
    if bootstrap_ci_enabled:
        columns.extend(["median_ci_low", "median_ci_high"])
    if forward_df.empty:
        return pd.DataFrame(columns=columns)

    fwd = forward_df.copy()
    fwd["date"] = pd.to_datetime(fwd["date"])

    results = []
    grouped = fwd.groupby(["detector", "event"])
    for (detector, event), grp in grouped:
        fwd20 = grp["fwd_20"].dropna()
        median_20 = fwd20.median() if not fwd20.empty else np.nan
        win_rate_20 = (fwd20 > 0).mean() if not fwd20.empty else np.nan
        p5 = fwd20.quantile(0.05) if not fwd20.empty else np.nan

        if grp["date"].empty:
            stability_delta = np.nan
        else:
            t_min, t_max = grp["date"].min(), grp["date"].max()
            midpoint = t_min + (t_max - t_min) / 2
            first = grp[grp["date"] <= midpoint]["fwd_20"].dropna()
            second = grp[grp["date"] > midpoint]["fwd_20"].dropna()
            stability_delta = (
                second.median() - first.median() if not first.empty and not second.empty else np.nan
            )

        density = len(grp) / coverage_years if coverage_years else np.nan

        row = {
            "detector": detector,
            "event": event,
            "density": density,
            "median_fwd_20": median_20,
            "win_rate_20": win_rate_20,
            "p5_fwd_20": p5,
            "stability_delta": stability_delta,
            "event_count": len(grp),
        }
        if bootstrap_ci_enabled:
            ci_low, ci_high = _bootstrap_ci(fwd20.to_numpy(), bootstrap_resamples)
            row["median_ci_low"] = ci_low
            row["median_ci_high"] = ci_high
        results.append(row)

    return pd.DataFrame(results, columns=columns).sort_values(["detector", "event"]).reset_index(drop=True)


def build_comparison_table(summary_df: pd.DataFrame) -> pd.DataFrame:
    columns = ["detector", "event", "density", "median_fwd_20", "win_rate_20", "p5_fwd_20", "stability_delta"]
    if summary_df.empty:
        return pd.DataFrame(columns=columns)
    return summary_df[columns].copy()


def evaluate_bc_effect(forward_df: pd.DataFrame, forward_windows: list[int]) -> pd.DataFrame:
    rows = []
    if forward_df.empty:
        return pd.DataFrame(
            columns=[
                "window",
                "count_bc",
                "count_baseline",
                "median_bc",
                "median_baseline",
                "median_delta",
                "win_rate_bc",
                "win_rate_baseline",
                "win_rate_delta",
                "p5_bc",
                "p5_baseline",
                "p5_delta",
            ]
        )

    bc_df = evaluate_event_effect(forward_df, forward_windows, "BC").rename(
        columns={
            "count_event": "count_bc",
            "median_event": "median_bc",
            "win_rate_event": "win_rate_bc",
            "p5_event": "p5_bc",
        }
    )
    if "event" in bc_df.columns:
        bc_df = bc_df.drop(columns=["event"])
    return bc_df[
        [
            "window",
            "count_bc",
            "count_baseline",
            "median_bc",
            "median_baseline",
            "median_delta",
            "win_rate_bc",
            "win_rate_baseline",
            "win_rate_delta",
            "p5_bc",
            "p5_baseline",
            "p5_delta",
        ]
    ]


def evaluate_event_effect(
    forward_df: pd.DataFrame, forward_windows: list[int], event_name: str
) -> pd.DataFrame:
    rows = []
    if forward_df.empty:
        return pd.DataFrame(
            columns=[
                "window",
                "event",
                "count_event",
                "count_baseline",
                "median_event",
                "median_baseline",
                "median_delta",
                "win_rate_event",
                "win_rate_baseline",
                "win_rate_delta",
                "p5_event",
                "p5_baseline",
                "p5_delta",
            ]
        )

    for window in forward_windows:
        col = f"fwd_{int(window)}"
        if col not in forward_df.columns:
            event_vals = pd.Series(dtype="float64")
            base_vals = pd.Series(dtype="float64")
        else:
            event_vals = forward_df.loc[forward_df["event"] == event_name, col].dropna()
            base_vals = forward_df.loc[forward_df["event"] != event_name, col].dropna()

        median_event = event_vals.median() if not event_vals.empty else np.nan
        median_base = base_vals.median() if not base_vals.empty else np.nan
        win_event = (event_vals > 0).mean() if not event_vals.empty else np.nan
        win_base = (base_vals > 0).mean() if not base_vals.empty else np.nan
        p5_event = event_vals.quantile(0.05) if not event_vals.empty else np.nan
        p5_base = base_vals.quantile(0.05) if not base_vals.empty else np.nan

        rows.append(
            {
                "window": int(window),
                "event": event_name,
                "count_event": int(event_vals.shape[0]),
                "count_baseline": int(base_vals.shape[0]),
                "median_event": median_event,
                "median_baseline": median_base,
                "median_delta": median_event - median_base
                if pd.notna(median_event) and pd.notna(median_base)
                else np.nan,
                "win_rate_event": win_event,
                "win_rate_baseline": win_base,
                "win_rate_delta": win_event - win_base if pd.notna(win_event) and pd.notna(win_base) else np.nan,
                "p5_event": p5_event,
                "p5_baseline": p5_base,
                "p5_delta": p5_event - p5_base if pd.notna(p5_event) and pd.notna(p5_base) else np.nan,
            }
        )

    return pd.DataFrame(rows)


def evaluate_sos_after_bc_effect(
    forward_df: pd.DataFrame, forward_windows: list[int], lookback_days: int
) -> pd.DataFrame:
    rows = []
    if forward_df.empty:
        return pd.DataFrame(
            columns=[
                "window",
                "event",
                "lookback_days",
                "count_event",
                "count_baseline",
                "median_event",
                "median_baseline",
                "median_delta",
                "win_rate_event",
                "win_rate_baseline",
                "win_rate_delta",
                "p5_event",
                "p5_baseline",
                "p5_delta",
            ]
        )

    df = forward_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    sos_after_bc_mask = pd.Series(False, index=df.index)
    for _, group in df.groupby("symbol", sort=False):
        group = group.sort_values("date")
        last_bc_date = None
        for idx, row in group.iterrows():
            if row["event"] == "BC":
                last_bc_date = row["date"]
                continue
            if row["event"] == "SOS" and last_bc_date is not None:
                delta_days = (row["date"] - last_bc_date).days
                if 0 < delta_days <= lookback_days:
                    sos_after_bc_mask.at[idx] = True

    sos_after_bc_df = df.loc[sos_after_bc_mask]
    base_df = df.loc[df["event"] == "BC"]
    if base_df.empty:
        base_df = df.loc[df["event"] != "SOS"]

    for window in forward_windows:
        col = f"fwd_{int(window)}"
        if col not in df.columns:
            event_vals = pd.Series(dtype="float64")
            base_vals = pd.Series(dtype="float64")
        else:
            event_vals = sos_after_bc_df[col].dropna()
            base_vals = base_df[col].dropna()

        median_event = event_vals.median() if not event_vals.empty else np.nan
        median_base = base_vals.median() if not base_vals.empty else np.nan
        win_event = (event_vals > 0).mean() if not event_vals.empty else np.nan
        win_base = (base_vals > 0).mean() if not base_vals.empty else np.nan
        p5_event = event_vals.quantile(0.05) if not event_vals.empty else np.nan
        p5_base = base_vals.quantile(0.05) if not base_vals.empty else np.nan

        rows.append(
            {
                "window": int(window),
                "event": "SOS_AFTER_BC",
                "lookback_days": int(lookback_days),
                "count_event": int(event_vals.shape[0]),
                "count_baseline": int(base_vals.shape[0]),
                "median_event": median_event,
                "median_baseline": median_base,
                "median_delta": median_event - median_base
                if pd.notna(median_event) and pd.notna(median_base)
                else np.nan,
                "win_rate_event": win_event,
                "win_rate_baseline": win_base,
                "win_rate_delta": win_event - win_base if pd.notna(win_event) and pd.notna(win_base) else np.nan,
                "p5_event": p5_event,
                "p5_baseline": p5_base,
                "p5_delta": p5_event - p5_base if pd.notna(p5_event) and pd.notna(p5_base) else np.nan,
            }
        )

    return pd.DataFrame(rows)


def evaluate_path_dependency(
    baseline_df: pd.DataFrame, incremental_df: pd.DataFrame
) -> pd.DataFrame:
    columns = [
        "total_events",
        "matched_events",
        "moved_events",
        "mean_date_delta",
        "median_date_delta",
        "unmatched_baseline",
        "unmatched_incremental",
    ]

    if baseline_df is None:
        baseline_df = pd.DataFrame(columns=["symbol", "event", "date"])
    if incremental_df is None:
        incremental_df = pd.DataFrame(columns=["symbol", "event", "date"])

    base = baseline_df.copy()
    inc = incremental_df.copy()

    if "date" in base.columns:
        base["date"] = pd.to_datetime(base["date"], errors="coerce")
    if "date" in inc.columns:
        inc["date"] = pd.to_datetime(inc["date"], errors="coerce")

    base = base[["symbol", "event", "date"]] if not base.empty else base
    inc = inc[["symbol", "event", "date"]] if not inc.empty else inc

    merged = base.merge(
        inc, on=["symbol", "event"], how="outer", suffixes=("_baseline", "_incremental")
    )

    date_delta = (
        merged["date_baseline"] - merged["date_incremental"]
        if "date_baseline" in merged.columns and "date_incremental" in merged.columns
        else pd.Series(dtype="float64")
    )
    date_delta = date_delta.abs().dt.days if not date_delta.empty else pd.Series(dtype="float64")

    matched_mask = merged["date_baseline"].notna() & merged["date_incremental"].notna()
    moved_mask = matched_mask & (date_delta > 0)
    unmatched_baseline = merged["date_baseline"].notna() & merged["date_incremental"].isna()
    unmatched_incremental = merged["date_baseline"].isna() & merged["date_incremental"].notna()

    metrics = {
        "total_events": int(base.shape[0]),
        "matched_events": int(matched_mask.sum()),
        "moved_events": int(moved_mask.sum()),
        "mean_date_delta": float(date_delta[matched_mask].mean())
        if matched_mask.any()
        else np.nan,
        "median_date_delta": float(date_delta[matched_mask].median())
        if matched_mask.any()
        else np.nan,
        "unmatched_baseline": int(unmatched_baseline.sum()),
        "unmatched_incremental": int(unmatched_incremental.sum()),
    }

    return pd.DataFrame([metrics], columns=columns)
