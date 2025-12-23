from __future__ import annotations

from datetime import date, datetime, timezone

from core.ingestion.options.pipeline import deduplicate_option_rows


def test_option_rows_deduplicated_and_prefer_best_row() -> None:
    shared_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    shared_key = {
        "time": shared_time,
        "ticker_id": "TEST",
        "expiration_date": date(2023, 2, 1),
        "strike_price": 100.0,
        "option_type": "call",
    }

    rows = [
        {**shared_key, "row_id": "first_seen", "volume": 10, "open_interest": None, "gamma": None},
        {
            **shared_key,
            "row_id": "open_interest_preferred",
            "volume": 1,
            "open_interest": 5,
            "gamma": None,
        },
        {
            **shared_key,
            "row_id": "gamma_preferred",
            "volume": 2,
            "open_interest": 3,
            "gamma": 0.1,
        },
        {
            "time": shared_time,
            "ticker_id": "OTHER",
            "expiration_date": date(2023, 2, 1),
            "strike_price": 105.0,
            "option_type": "call",
            "row_id": "unique_key",
            "volume": 7,
            "open_interest": 1,
            "gamma": 0.01,
        },
    ]

    deduped_rows, duplicates_removed = deduplicate_option_rows(rows)

    assert duplicates_removed == 2
    assert len(deduped_rows) == 2
    assert deduped_rows[0]["row_id"] == "gamma_preferred"
    assert deduped_rows[1]["row_id"] == "unique_key"

    conflict_keys = {
        (
            row["time"],
            row["ticker_id"],
            row["expiration_date"],
            row["strike_price"],
            row["option_type"],
        )
        for row in deduped_rows
    }
    assert len(conflict_keys) == len(deduped_rows)
