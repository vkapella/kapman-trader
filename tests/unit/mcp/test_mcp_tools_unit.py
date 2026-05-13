from __future__ import annotations

import pytest

from core.mcp.tools.metrics import get_metrics
from core.mcp.tools.screen_watchlist import screen_watchlist
from core.mcp.tools.wyckoff_proposal import get_wyckoff_proposal_context


def test_invalid_date_validation():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        get_metrics("AMD", as_of_date="2026/01/01")


def test_missing_symbol_validation():
    with pytest.raises(ValueError, match="symbol is required"):
        get_wyckoff_proposal_context("", lookback_days=90)


def test_screen_limit_validation():
    with pytest.raises(ValueError, match="limit"):
        screen_watchlist(limit=0)


def test_metrics_include_validation():
    with pytest.raises(ValueError, match="unsupported include"):
        get_metrics("AMD", include=["foo"])
