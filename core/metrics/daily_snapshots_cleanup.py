from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from core.daily_snapshots import CANONICAL_DAILY_SNAPSHOT_UTC_TIME, LEGACY_A3_SPLIT_UTC_TIMES


@dataclass(frozen=True)
class SplitDailySnapshotsReport:
    split_rows: int
    split_rows_with_canonical: int
    split_rows_missing_canonical: int
    canonical_rows_missing_dealer_metrics: int
    canonical_rows_updated: int = 0
    split_rows_deleted: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "split_rows": self.split_rows,
            "split_rows_with_canonical": self.split_rows_with_canonical,
            "split_rows_missing_canonical": self.split_rows_missing_canonical,
            "canonical_rows_missing_dealer_metrics": self.canonical_rows_missing_dealer_metrics,
            "canonical_rows_updated": self.canonical_rows_updated,
            "split_rows_deleted": self.split_rows_deleted,
        }


def _scope_clause(start_date: Optional[date], end_date: Optional[date]) -> tuple[str, list[Any]]:
    if start_date and end_date:
        return "AND split.ny_date >= %s AND split.ny_date <= %s", [start_date, end_date]
    if start_date:
        return "AND split.ny_date >= %s", [start_date]
    if end_date:
        return "AND split.ny_date <= %s", [end_date]
    return "", []


def _candidate_rows_sql(scope_clause: str) -> str:
    return f"""
        WITH split_rows AS (
            SELECT
                ds.time AS split_time,
                ds.ticker_id,
                ds.dealer_metrics_json,
                ds.model_version,
                (ds.time AT TIME ZONE 'America/New_York')::date AS ny_date
            FROM public.daily_snapshots ds
            WHERE (ds.time AT TIME ZONE 'UTC')::time = ANY(%s)
              AND (
                  ds.dealer_metrics_json IS NOT NULL
                  OR COALESCE(ds.model_version, '') ILIKE 'A3%%'
              )
        )
        SELECT
            split.split_time,
            split.ticker_id,
            split.dealer_metrics_json,
            split.ny_date,
            canon.time AS canonical_time,
            canon.dealer_metrics_json AS canonical_dealer_metrics_json
        FROM split_rows split
        LEFT JOIN public.daily_snapshots canon
          ON canon.ticker_id = split.ticker_id
         AND (canon.time AT TIME ZONE 'America/New_York')::date = split.ny_date
         AND (canon.time AT TIME ZONE 'UTC')::time = %s
        WHERE 1=1
        {scope_clause}
    """


def summarize_split_daily_snapshots(
    conn,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> SplitDailySnapshotsReport:
    scope_clause, scope_params = _scope_clause(start_date, end_date)
    sql = _candidate_rows_sql(scope_clause)
    params: list[Any] = [list(LEGACY_A3_SPLIT_UTC_TIMES), CANONICAL_DAILY_SNAPSHOT_UTC_TIME]
    params.extend(scope_params)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH candidates AS (
                {sql}
            )
            SELECT
                COUNT(*) AS split_rows,
                COUNT(*) FILTER (WHERE canonical_time IS NOT NULL) AS split_rows_with_canonical,
                COUNT(*) FILTER (WHERE canonical_time IS NULL) AS split_rows_missing_canonical,
                COUNT(*) FILTER (
                    WHERE canonical_time IS NOT NULL
                      AND canonical_dealer_metrics_json IS NULL
                      AND dealer_metrics_json IS NOT NULL
                ) AS canonical_rows_missing_dealer_metrics
            FROM candidates
            """,
            params,
        )
        row = cur.fetchone()

    return SplitDailySnapshotsReport(
        split_rows=int(row[0] or 0),
        split_rows_with_canonical=int(row[1] or 0),
        split_rows_missing_canonical=int(row[2] or 0),
        canonical_rows_missing_dealer_metrics=int(row[3] or 0),
    )


def cleanup_split_daily_snapshots(
    conn,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    apply: bool = False,
) -> SplitDailySnapshotsReport:
    report = summarize_split_daily_snapshots(conn, start_date=start_date, end_date=end_date)
    if not apply or report.split_rows_with_canonical == 0:
        return report

    scope_clause, scope_params = _scope_clause(start_date, end_date)
    params: list[Any] = [list(LEGACY_A3_SPLIT_UTC_TIMES), CANONICAL_DAILY_SNAPSHOT_UTC_TIME]
    params.extend(scope_params)
    candidate_sql = _candidate_rows_sql(scope_clause)

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH candidates AS (
                    {candidate_sql}
                )
                UPDATE public.daily_snapshots AS canon
                SET dealer_metrics_json = candidates.dealer_metrics_json
                FROM candidates
                WHERE canon.time = candidates.canonical_time
                  AND canon.ticker_id = candidates.ticker_id
                  AND canon.dealer_metrics_json IS NULL
                  AND candidates.dealer_metrics_json IS NOT NULL
                """,
                params,
            )
            updated = cur.rowcount

            cur.execute(
                f"""
                WITH candidates AS (
                    {candidate_sql}
                )
                DELETE FROM public.daily_snapshots AS split
                USING candidates
                WHERE split.time = candidates.split_time
                  AND split.ticker_id = candidates.ticker_id
                  AND candidates.canonical_time IS NOT NULL
                """,
                params,
            )
            deleted = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return SplitDailySnapshotsReport(
        split_rows=report.split_rows,
        split_rows_with_canonical=report.split_rows_with_canonical,
        split_rows_missing_canonical=report.split_rows_missing_canonical,
        canonical_rows_missing_dealer_metrics=report.canonical_rows_missing_dealer_metrics,
        canonical_rows_updated=int(updated or 0),
        split_rows_deleted=int(deleted or 0),
    )
