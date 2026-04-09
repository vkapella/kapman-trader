#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# KapMan SAFE CATCH-UP SCRIPT
#
# Usage:
#   scripts/cron/catchup_START_DATE_to_END_DATE.sh [START_DATE END_DATE]
#
# Examples:
#   scripts/cron/catchup_START_DATE_to_END_DATE.sh
#     Automatic catch-up. The script checks the last OHLCV date in the DB,
#     resolves the next missing trading day through the previous market day,
#     skips weekends and NYSE holidays, and only continues if A0 adds new data.
#
#   scripts/cron/catchup_START_DATE_to_END_DATE.sh 2026-04-06 2026-04-06
#     Explicit single-day catch-up. The script skips the date if it is a weekend
#     or NYSE holiday, then ingests and hydrates the remaining trading day(s).
#
#   scripts/cron/catchup_START_DATE_to_END_DATE.sh 2026-04-03 2026-04-06
#     Explicit multi-day catch-up. The script skips weekends and NYSE holidays
#     inside the requested span, then backfills the remaining trading day(s).
#
# Order:
#   A0  OHLCV
#   A1  Options Chains
#   A2  Local TA
#   A4  Volatility Metrics
#   A3  Dealer Metrics
#   B2  Wyckoff Structural Events
#   B1  Wyckoff Regime
#   B4  Wyckoff Derived
#   B4.1 Canonical Sequences
#
# GUARANTEES:
# - OHLCV anchors all dates
# - Downstream steps run only when A0 adds OHLCV rows
# - No phantom daily_snapshots rows
# - NY trading date remains canonical
# ============================================================

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
RUN_TS_UTC="$(date -u +"%Y-%m-%dT%H-%M-%SZ")"
SCRIPT_START_TS="$(date +%s)"
REPORT_DIR="${REPO_ROOT}/data/cron_reports"
STEP_TIMINGS_FILE="$(mktemp -t kapman_catchup_timings.XXXXXX)"
EFFECTIVE_TRADING_DATES_FILE="$(mktemp -t kapman_catchup_effective_dates.XXXXXX)"
AVAILABLE_TRADING_DATES_FILE="$(mktemp -t kapman_catchup_available_dates.XXXXXX)"
PRE_A0_COUNTS_FILE="$(mktemp -t kapman_catchup_pre_a0_counts.XXXXXX)"
POST_A0_COUNTS_FILE="$(mktemp -t kapman_catchup_post_a0_counts.XXXXXX)"
CHANGED_A0_DATES_FILE="$(mktemp -t kapman_catchup_changed_a0_dates.XXXXXX)"

cleanup() {
  rm -f \
    "${STEP_TIMINGS_FILE}" \
    "${EFFECTIVE_TRADING_DATES_FILE}" \
    "${AVAILABLE_TRADING_DATES_FILE}" \
    "${PRE_A0_COUNTS_FILE}" \
    "${POST_A0_COUNTS_FILE}" \
    "${CHANGED_A0_DATES_FILE}"
}

trap cleanup EXIT

format_duration() {
  local total_seconds="$1"
  printf "%02d:%02d:%02d" \
    "$((total_seconds / 3600))" \
    "$(((total_seconds % 3600) / 60))" \
    "$((total_seconds % 60))"
}

record_timing() {
  local elapsed_sec="$1"
  local label="$2"
  printf "%s\t%s\n" "${elapsed_sec}" "${label}" >> "${STEP_TIMINGS_FILE}"
}

market_calendar_py() {
  python - "$@" <<'PY'
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import sys


def easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def observed_fixed_holiday(year: int, month: int, day: int) -> date:
    d = date(year, month, day)
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(weeks=n - 1)


def last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def nyse_holidays(year: int) -> set[date]:
    holidays = {
        observed_fixed_holiday(year, 1, 1),
        nth_weekday_of_month(year, 1, 0, 3),   # MLK Day
        nth_weekday_of_month(year, 2, 0, 3),   # Presidents Day
        easter_sunday(year) - timedelta(days=2),  # Good Friday
        last_weekday_of_month(year, 5, 0),     # Memorial Day
        observed_fixed_holiday(year, 7, 4),
        nth_weekday_of_month(year, 9, 0, 1),   # Labor Day
        nth_weekday_of_month(year, 11, 3, 4),  # Thanksgiving
        observed_fixed_holiday(year, 12, 25),
    }
    if year >= 2022:
        holidays.add(observed_fixed_holiday(year, 6, 19))  # Juneteenth

    # Known one-off closure present in local OHLCV history.
    if year == 2025:
        holidays.add(date(2025, 1, 9))

    return holidays


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


def next_trading_day(after_date: date) -> date:
    d = after_date + timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def previous_trading_day(before_date: date) -> date:
    d = before_date - timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def trading_days_in_range(start: date, end: date) -> list[date]:
    if end < start:
        return []
    dates: list[date] = []
    d = start
    while d <= end:
        if is_trading_day(d):
            dates.append(d)
        d += timedelta(days=1)
    return dates


command = sys.argv[1]
if command == "today-et":
    now_et = datetime.now(ZoneInfo("America/New_York"))
    print(now_et.date().isoformat())
elif command == "next-trading-day":
    print(next_trading_day(date.fromisoformat(sys.argv[2])).isoformat())
elif command == "previous-trading-day":
    print(previous_trading_day(date.fromisoformat(sys.argv[2])).isoformat())
elif command == "list-trading-days":
    start = date.fromisoformat(sys.argv[2])
    end = date.fromisoformat(sys.argv[3])
    for d in trading_days_in_range(start, end):
        print(d.isoformat())
else:
    raise SystemExit(f"unknown command: {command}")
PY
}

print_runtime_summary() {
  echo
  echo "============================================================"
  echo "RUNTIME SUMMARY (LONGEST FIRST)"
  echo "============================================================"
  while IFS=$'\t' read -r elapsed_sec label; do
    printf "%6ss  %s (%s)\n" "${elapsed_sec}" "${label}" "$(format_duration "${elapsed_sec}")"
  done < <(sort -rn "${STEP_TIMINGS_FILE}")

  local total_runtime_sec
  total_runtime_sec="$(( $(date +%s) - SCRIPT_START_TS ))"
  echo "TOTAL_RUNTIME_SEC=${total_runtime_sec} TOTAL_RUNTIME_HMS=$(format_duration "${total_runtime_sec}")"
}

query_ohlcv_coverage() {
  local range_start="$1"
  local range_end="$2"
  docker exec -i -e PGPASSWORD="${PGPASSWORD:-kapman_password_here}" kapman-db \
    psql -U kapman -d kapman -t -A -F '|' <<SQL
SELECT
  COUNT(*)::bigint AS row_count,
  COUNT(DISTINCT date)::bigint AS date_count
FROM ohlcv
WHERE date BETWEEN '${range_start}' AND '${range_end}';
SQL
}

query_ohlcv_max_date() {
  docker exec -i -e PGPASSWORD="${PGPASSWORD:-kapman_password_here}" kapman-db \
    psql -U kapman -d kapman -t -A <<SQL
SELECT COALESCE(MAX(date)::text, '')
FROM ohlcv;
SQL
}

write_ohlcv_counts_by_date() {
  local range_start="$1"
  local range_end="$2"
  local output_file="$3"
  docker exec -i -e PGPASSWORD="${PGPASSWORD:-kapman_password_here}" kapman-db \
    psql -U kapman -d kapman -t -A -F '|' <<SQL > "${output_file}"
SELECT date::text, COUNT(*)::bigint
FROM ohlcv
WHERE date BETWEEN '${range_start}' AND '${range_end}'
GROUP BY 1
ORDER BY 1;
SQL
}

write_available_trading_dates() {
  local range_start="$1"
  local range_end="$2"
  local effective_dates_file="$3"
  local output_file="$4"
  python - "${range_start}" "${range_end}" "${effective_dates_file}" "${output_file}" <<'PY'
from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

from core.ingestion.ohlcv.s3_flatfiles import (
    default_s3_flatfiles_config,
    get_s3_client,
    list_available_dates_in_range,
)


start = date.fromisoformat(sys.argv[1])
end = date.fromisoformat(sys.argv[2])
effective_dates_path = Path(sys.argv[3])
output_path = Path(sys.argv[4])

effective_dates = {
    date.fromisoformat(line.strip())
    for line in effective_dates_path.read_text().splitlines()
    if line.strip()
}

cfg = default_s3_flatfiles_config()
s3 = get_s3_client(cfg)
available = list_available_dates_in_range(
    s3,
    bucket=cfg.bucket,
    prefix=cfg.prefix,
    start=start,
    end=end,
)

selected = [d.isoformat() for d in available if d in effective_dates]
output_path.write_text("".join(f"{d}\n" for d in selected))
PY
}

write_changed_ohlcv_dates() {
  local pre_counts_file="$1"
  local post_counts_file="$2"
  local output_file="$3"
  python - "${pre_counts_file}" "${post_counts_file}" "${output_file}" <<'PY'
from __future__ import annotations

from pathlib import Path
import sys


def load_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        day, count = raw.split("|", 1)
        counts[day] = int(count)
    return counts


pre = load_counts(Path(sys.argv[1]))
post = load_counts(Path(sys.argv[2]))
changed = sorted(day for day, count in post.items() if count > pre.get(day, 0))
Path(sys.argv[3]).write_text("".join(f"{day}\n" for day in changed))
PY
}

run_a0_for_dates() {
  local total=0
  local date_value
  while IFS= read -r date_value; do
    [[ -n "${date_value}" ]] && total="$((total + 1))"
  done < "${AVAILABLE_TRADING_DATES_FILE}"

  local index=0
  while IFS= read -r date_value; do
    [[ -z "${date_value}" ]] && continue
    index="$((index + 1))"
    echo "--- A0 ingest ${index}/${total}: ${date_value} ---"
    python -m scripts.ingest_ohlcv incremental \
      --date "${date_value}" \
      --verbosity normal
  done < "${AVAILABLE_TRADING_DATES_FILE}"
}

run_step() {
  local step_id="$1"
  local step_label="$2"
  shift 2

  echo
  echo "============================================================"
  echo "${step_label} (${step_id})"
  echo "============================================================"

  local started_at ended_at elapsed_sec
  started_at="$(date +%s)"
  "$@"
  ended_at="$(date +%s)"
  elapsed_sec="$((ended_at - started_at))"

  record_timing "${elapsed_sec}" "${step_id} ${step_label}"
  echo "STEP TIMING step=${step_id} elapsed_sec=${elapsed_sec} elapsed_hms=$(format_duration "${elapsed_sec}")"
}

if [[ $# -ne 0 && $# -ne 2 ]]; then
  echo "Usage: $0 [START_DATE END_DATE]"
  echo "Examples:"
  echo "  $0"
  echo "  $0 2026-04-06 2026-04-06"
  echo "  $0 2026-04-03 2026-04-06"
  exit 1
fi

mkdir -p "${REPORT_DIR}"

echo "==> Activating environment"
cd "${REPO_ROOT}"
source "${REPO_ROOT}/venv/bin/activate"
set -a
source "${REPO_ROOT}/.env"
set +a

echo "==> Ensuring Docker environment is running"
docker compose up -d

if [[ $# -eq 2 ]]; then
  REQUEST_MODE="explicit"
  REQUESTED_START_DATE="$1"
  REQUESTED_END_DATE="$2"
else
  REQUEST_MODE="auto"
  LAST_OHLCV_DATE="$(query_ohlcv_max_date | tr -d '[:space:]')"
  if [[ -z "${LAST_OHLCV_DATE}" ]]; then
    echo "ERROR: ohlcv is empty. Provide explicit START_DATE and END_DATE for bootstrap."
    exit 1
  fi
  TODAY_ET="$(market_calendar_py today-et)"
  REQUESTED_START_DATE="$(market_calendar_py next-trading-day "${LAST_OHLCV_DATE}")"
  REQUESTED_END_DATE="$(market_calendar_py previous-trading-day "${TODAY_ET}")"
fi

REPORT_FILE="${REPORT_DIR}/kapman_catchup_${REQUESTED_START_DATE}_${REQUESTED_END_DATE}_${RUN_TS_UTC}.log"
exec > >(tee -a "${REPORT_FILE}") 2>&1

echo "==> KapMan SAFE CATCH-UP"
echo "==> Request mode: ${REQUEST_MODE}"
echo "==> Requested calendar range: ${REQUESTED_START_DATE} → ${REQUESTED_END_DATE}"
if [[ "${REQUEST_MODE}" == "auto" ]]; then
  echo "==> Last OHLCV date in DB: ${LAST_OHLCV_DATE}"
fi
echo "==> Report file: ${REPORT_FILE}"

market_calendar_py list-trading-days "${REQUESTED_START_DATE}" "${REQUESTED_END_DATE}" > "${EFFECTIVE_TRADING_DATES_FILE}"

if [[ ! -s "${EFFECTIVE_TRADING_DATES_FILE}" ]]; then
  if [[ "${REQUEST_MODE}" == "auto" ]]; then
    echo "==> SAFE CATCH-UP STOPPED: DB is already current through the previous market day."
  else
    echo "==> SAFE CATCH-UP STOPPED: no NYSE trading days fall inside the requested range."
  fi
  exit 0
fi

EFFECTIVE_TRADING_DATES_COUNT="$(grep -c . "${EFFECTIVE_TRADING_DATES_FILE}")"
EFFECTIVE_START_DATE="$(sed -n '1p' "${EFFECTIVE_TRADING_DATES_FILE}")"
EFFECTIVE_END_DATE="$(tail -n 1 "${EFFECTIVE_TRADING_DATES_FILE}")"
echo "==> Effective trading-day range: ${EFFECTIVE_START_DATE} → ${EFFECTIVE_END_DATE} (${EFFECTIVE_TRADING_DATES_COUNT} trading day(s))"

write_available_trading_dates \
  "${EFFECTIVE_START_DATE}" \
  "${EFFECTIVE_END_DATE}" \
  "${EFFECTIVE_TRADING_DATES_FILE}" \
  "${AVAILABLE_TRADING_DATES_FILE}"

if [[ ! -s "${AVAILABLE_TRADING_DATES_FILE}" ]]; then
  echo "==> SAFE CATCH-UP STOPPED: no upstream OHLCV files are currently available for the resolved trading-day range."
  echo "==> Wait for the Polygon/Massive publish, then rerun this script."
  exit 0
fi

AVAILABLE_TRADING_DATES_COUNT="$(grep -c . "${AVAILABLE_TRADING_DATES_FILE}")"
A0_START_DATE="$(sed -n '1p' "${AVAILABLE_TRADING_DATES_FILE}")"
A0_END_DATE="$(tail -n 1 "${AVAILABLE_TRADING_DATES_FILE}")"
echo "==> Upstream OHLCV files currently available for: ${A0_START_DATE} → ${A0_END_DATE} (${AVAILABLE_TRADING_DATES_COUNT} trading day(s))"

IFS='|' read -r PRE_A0_ROWS PRE_A0_DATES <<< "$(query_ohlcv_coverage "${A0_START_DATE}" "${A0_END_DATE}")"
write_ohlcv_counts_by_date "${A0_START_DATE}" "${A0_END_DATE}" "${PRE_A0_COUNTS_FILE}"
echo "==> Pre-A0 OHLCV coverage rows=${PRE_A0_ROWS} dates=${PRE_A0_DATES}"

run_step "A0" "STEP 1: OHLCV BASE INGEST" \
  run_a0_for_dates

IFS='|' read -r POST_A0_ROWS POST_A0_DATES <<< "$(query_ohlcv_coverage "${A0_START_DATE}" "${A0_END_DATE}")"
write_ohlcv_counts_by_date "${A0_START_DATE}" "${A0_END_DATE}" "${POST_A0_COUNTS_FILE}"
write_changed_ohlcv_dates "${PRE_A0_COUNTS_FILE}" "${POST_A0_COUNTS_FILE}" "${CHANGED_A0_DATES_FILE}"
A0_ROWS_ADDED="$((POST_A0_ROWS - PRE_A0_ROWS))"
A0_DATES_ADDED="$((POST_A0_DATES - PRE_A0_DATES))"
echo "==> Post-A0 OHLCV coverage rows=${POST_A0_ROWS} dates=${POST_A0_DATES} delta_rows=${A0_ROWS_ADDED} delta_dates=${A0_DATES_ADDED}"

if [[ ! -s "${CHANGED_A0_DATES_FILE}" || "${A0_ROWS_ADDED}" -le 0 ]]; then
  echo "==> SAFE CATCH-UP STOPPED: A0 did not add any new OHLCV data for the resolved trading-day range."
  echo "==> Downstream processing skipped. Wait for the upstream OHLCV publish, then rerun this script."
  print_runtime_summary
  exit 0
fi

CHANGED_A0_DATES_COUNT="$(grep -c . "${CHANGED_A0_DATES_FILE}")"
START_DATE="$(sed -n '1p' "${CHANGED_A0_DATES_FILE}")"
END_DATE="$(tail -n 1 "${CHANGED_A0_DATES_FILE}")"
echo "==> Downstream pipeline range: ${START_DATE} → ${END_DATE} (${CHANGED_A0_DATES_COUNT} trading day(s) added or expanded by A0)"

run_step "A1" "STEP 2: OPTIONS CHAINS INGEST" \
  python -m scripts.ingest_options \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --emit-summary

run_step "A2" "STEP 3: LOCAL TA + PRICE METRICS" \
  python -m scripts.run_a2_local_ta \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --quiet

run_step "A4" "STEP 4: VOLATILITY METRICS" \
  python -m scripts.run_a4_volatility_metrics \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --quiet

run_step "A3" "STEP 5: DEALER METRICS" \
  python -m scripts.run_a3_dealer_metrics \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --fill-missing \
    --quiet

run_step "B2" "STEP 6: WYCKOFF STRUCTURAL EVENTS" \
  python -m scripts.run_b2_wyckoff_structural_events \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --heartbeat

run_step "B1" "STEP 7: WYCKOFF REGIME" \
  python -m scripts.run_b1_wyckoff_regime \
    --heartbeat

run_step "B4" "STEP 8: WYCKOFF DERIVED" \
  python -m scripts.run_b4_wyckoff_derived \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --heartbeat \
    --include-evidence

run_step "B4.1" "STEP 9: WYCKOFF SEQUENCES" \
  python -m scripts.run_b4_1_wyckoff_sequences \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --heartbeat

run_step "CHECK" "POSTCHECK: DEALER SNAPSHOT DATE SAFETY" \
  docker exec -i -e PGPASSWORD="${PGPASSWORD:-kapman_password_here}" kapman-db \
    psql -U kapman -d kapman -v ON_ERROR_STOP=1 -X -q <<SQL
SELECT
  (time AT TIME ZONE 'UTC')::date              AS utc_date,
  (time AT TIME ZONE 'America/New_York')::date AS ny_date,
  COUNT(*) AS rows
FROM daily_snapshots
WHERE dealer_metrics_json IS NOT NULL
  AND (time AT TIME ZONE 'America/New_York')::date
      BETWEEN '${START_DATE}' AND '${END_DATE}'
GROUP BY 1,2
ORDER BY 1;
SQL

print_runtime_summary
echo "==> SAFE CATCH-UP COMPLETE: ${START_DATE} → ${END_DATE}"
