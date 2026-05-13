from __future__ import annotations

from dataclasses import dataclass

CONFIRMATION_STATUS_UNCONFIRMED = "unconfirmed_pipeline_observation"

DATA_QUALITY_FLAGS = (
    "missing_snapshot",
    "stale_snapshot",
    "missing_ohlcv",
    "missing_metric_category",
    "duplicate_same_day_snapshots",
    "missing_watchlist_membership",
)

METRIC_CATEGORY_TO_COLUMN = {
    "price": "price_metrics_json",
    "technical": "technical_indicators_json",
    "volatility": "volatility_metrics_json",
    "dealer": "dealer_metrics_json",
}


@dataclass(frozen=True)
class DataQualityFlagSet:
    missing_snapshot: bool = False
    stale_snapshot: bool = False
    missing_ohlcv: bool = False
    missing_metric_category: bool = False
    duplicate_same_day_snapshots: bool = False
    missing_watchlist_membership: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "missing_snapshot": self.missing_snapshot,
            "stale_snapshot": self.stale_snapshot,
            "missing_ohlcv": self.missing_ohlcv,
            "missing_metric_category": self.missing_metric_category,
            "duplicate_same_day_snapshots": self.duplicate_same_day_snapshots,
            "missing_watchlist_membership": self.missing_watchlist_membership,
        }
