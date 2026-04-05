#!/usr/bin/env bash
set -euo pipefail

START_DATE="${1:-2026-01-07}"
END_DATE="${2:-2026-01-09}"

echo "============================================================"
echo "Normalize split daily_snapshots rows for ${START_DATE}..${END_DATE}"
echo "============================================================"

python -m scripts.cleanup_split_daily_snapshots \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}"

echo
echo "Applying cleanup..."
python -m scripts.cleanup_split_daily_snapshots \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --apply
