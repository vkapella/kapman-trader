from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MetricSpec:
    key: str
    panel: str
    json_path: tuple[str, ...]
    label: str
    color: str
    kind: str
    cli_group: str
    linewidth: float = 1.0
    alpha: float = 1.0
    negative_color: str | None = None


@dataclass(frozen=True)
class PanelSpec:
    key: str
    order: int
    ylabel: str | None = None
    y_limits: tuple[float, float] | None = None
    reference_lines: tuple[float, ...] = ()


PANEL_REGISTRY: tuple[PanelSpec, ...] = (
    PanelSpec(key="PRICE", order=0, ylabel="Price"),
    PanelSpec(key="RSI", order=1, ylabel="RSI(14)", y_limits=(0.0, 100.0), reference_lines=(70.0, 30.0)),
    PanelSpec(key="MACD", order=2, ylabel="MACD", reference_lines=(0.0,)),
    PanelSpec(key="ADX", order=3, ylabel="ADX(14)"),
    PanelSpec(key="OBV", order=4, ylabel="OBV"),
)

PANEL_SPECS = {panel.key: panel for panel in PANEL_REGISTRY}
PANEL_ORDER = tuple(panel.key for panel in sorted(PANEL_REGISTRY, key=lambda item: item.order))


METRIC_REGISTRY: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="SMA20",
        panel="PRICE",
        json_path=("trend", "sma", "sma_20"),
        label="SMA20",
        color="#1f77b4",
        kind="line",
        cli_group="MA",
    ),
    MetricSpec(
        key="SMA50",
        panel="PRICE",
        json_path=("trend", "sma", "sma_50"),
        label="SMA50",
        color="#ff7f0e",
        kind="line",
        cli_group="MA",
    ),
    MetricSpec(
        key="SMA200",
        panel="PRICE",
        json_path=("trend", "sma", "sma_200"),
        label="SMA200",
        color="#9467bd",
        kind="line",
        cli_group="MA",
    ),
    MetricSpec(
        key="RSI",
        panel="RSI",
        json_path=("momentum", "rsi", "rsi"),
        label="RSI",
        color="#1f77b4",
        kind="line",
        cli_group="RSI",
    ),
    MetricSpec(
        key="MACD",
        panel="MACD",
        json_path=("trend", "macd", "macd"),
        label="MACD",
        color="#1f77b4",
        kind="line",
        cli_group="MACD",
    ),
    MetricSpec(
        key="MACD_SIGNAL",
        panel="MACD",
        json_path=("trend", "macd", "macd_signal"),
        label="Signal",
        color="#ff7f0e",
        kind="line",
        cli_group="MACD",
    ),
    MetricSpec(
        key="MACD_HIST",
        panel="MACD",
        json_path=("trend", "macd", "macd_diff"),
        label="Hist",
        color="#2ca02c",
        kind="hist",
        cli_group="MACD",
        alpha=0.4,
        negative_color="#d62728",
    ),
    MetricSpec(
        key="ADX",
        panel="ADX",
        json_path=("trend", "adx", "adx"),
        label="ADX(14)",
        color="#2ca02c",
        kind="line",
        cli_group="ADX",
    ),
    MetricSpec(
        key="OBV",
        panel="OBV",
        json_path=("volume", "obv", "on_balance_volume"),
        label="OBV",
        color="#9467bd",
        kind="line",
        cli_group="OBV",
    ),
)


def filter_metrics(requested_groups: Iterable[str]) -> list[MetricSpec]:
    if not requested_groups:
        return []
    requested = set(requested_groups)
    return [metric for metric in METRIC_REGISTRY if metric.cli_group in requested]


def select_panels(metrics: Iterable[MetricSpec], available_metric_keys: set[str]) -> list[str]:
    panels = {"PRICE"}
    for metric in metrics:
        if metric.key in available_metric_keys:
            panels.add(metric.panel)
    ordered: list[str] = []
    for key in PANEL_ORDER:
        if key in panels:
            ordered.append(key)
    return ordered
