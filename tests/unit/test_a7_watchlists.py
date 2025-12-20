from __future__ import annotations

from pathlib import Path

import pytest

from core.ingestion.watchlists.loader import (
    WatchlistLoadError,
    compute_reconcile_diff,
    list_watchlist_files,
    normalize_symbol,
    parse_watchlist_file,
)


@pytest.mark.unit
def test_normalize_symbol_accepts_uppercase_and_dot() -> None:
    assert normalize_symbol("aapl") == "AAPL"
    assert normalize_symbol("brk.b") == "BRK.B"


@pytest.mark.unit
def test_normalize_symbol_ignores_blank_and_comments() -> None:
    assert normalize_symbol("") is None
    assert normalize_symbol("   ") is None
    assert normalize_symbol("# comment") is None


@pytest.mark.unit
def test_normalize_symbol_rejects_invalid_symbols() -> None:
    assert normalize_symbol("AAPL$") is None
    assert normalize_symbol("A APL") is None
    assert normalize_symbol("123") is None


@pytest.mark.unit
def test_parse_watchlist_file_parses_and_dedupes(tmp_path: Path, caplog) -> None:
    caplog.set_level("WARNING")
    p = tmp_path / "ai_growth.txt"
    p.write_text(
        "\n"
        "# Header ignored\n"
        "aapl\n"
        "AAPL\n"
        "MSFT\n"
        "INVALID$\n"
        "brk.b\n",
        encoding="utf-8",
    )

    parsed = parse_watchlist_file(p)
    assert parsed.watchlist_id == "ai_growth"
    assert parsed.symbols == ["AAPL", "MSFT", "BRK.B"]
    assert parsed.duplicate_symbols == ["AAPL"]
    assert parsed.invalid_lines == ["INVALID$"]

    assert any("deduped" in rec.message for rec in caplog.records)
    assert any("skipped" in rec.message for rec in caplog.records)


@pytest.mark.unit
def test_parse_watchlist_file_empty_hard_fails(tmp_path: Path) -> None:
    p = tmp_path / "empty.txt"
    p.write_text("\n# only comments\n\n", encoding="utf-8")
    with pytest.raises(WatchlistLoadError, match="Empty watchlist file"):
        parse_watchlist_file(p)


@pytest.mark.unit
def test_parse_watchlist_file_missing_hard_fails(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(WatchlistLoadError, match="not found"):
        parse_watchlist_file(missing)


@pytest.mark.unit
def test_list_watchlist_files_missing_dir_hard_fails(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(WatchlistLoadError, match="directory not found"):
        list_watchlist_files(missing)


@pytest.mark.unit
def test_compute_reconcile_diff_inserts_reactivates_and_deactivates() -> None:
    existing = {"AAPL": True, "MSFT": False}
    incoming = {"MSFT", "GOOG"}
    diff = compute_reconcile_diff(existing=existing, incoming=incoming)
    assert diff.inserted == ["GOOG"]
    assert diff.reactivated == ["MSFT"]
    assert diff.soft_deactivated == ["AAPL"]

