# Pre-Sprint 2 Database Cleanup Guide

## Overview
This script addresses three critical issues before Sprint 2 development:
1. Missing `events_json` column in `daily_snapshots` table
2. Missing `notes` column in `model_parameters` table  
3. Failed view creation due to missing columns

## Execution Methods

### Option 1: Execute via psql (Recommended)
```bash
# From your local machine or container
psql "postgresql://kapman_user:your_password@localhost:5432/kapman_trading" -f pre_sprint2_cleanup.sql
```

### Option 2: Execute via Docker
```bash
# Copy script into container
docker cp pre_sprint2_cleanup.sql kapman-timescaledb:/tmp/

# Execute inside container
docker exec -it kapman-timescaledb psql -U kapman_user -d kapman_trading -f /tmp/pre_sprint2_cleanup.sql
```

### Option 3: Execute via DBeaver/GUI Tool
1. Open DBeaver and connect to your TimescaleDB instance
2. Open a new SQL Editor
3. Copy/paste the contents of `pre_sprint2_cleanup.sql`
4. Execute the script (Ctrl+Enter or Execute button)

## What the Script Does

### Step 1: Add events_json Column
Adds JSONB column to store detected Wyckoff events:
```json
[
  {
    "event_type": "SPRING",
    "confidence": 0.85,
    "price_level": 150.25,
    "volume_context": "climactic"
  }
]
```

### Step 2: Add notes Column
Adds TEXT column to `model_parameters` for configuration notes and rationale.

### Step 3-6: Recreate Views
Drops and recreates three dependent views in correct order:
- `v_wyckoff_events`: All detected events across symbols
- `v_entry_signals`: Filtered bullish/bearish entry opportunities
- `v_exit_signals`: Take-profit and stop-loss signals

### Step 7: Verification
Runs automated checks to confirm all columns and views were created successfully.

## Expected Output

You should see output similar to:
```
ALTER TABLE
COMMENT
ALTER TABLE
COMMENT
DROP VIEW
DROP VIEW
DROP VIEW
CREATE VIEW
COMMENT
CREATE VIEW
COMMENT
CREATE VIEW
COMMENT

         check_item          |  status   
-----------------------------+-----------
 daily_snapshots.events_json | ✓ EXISTS
 model_parameters.notes      | ✓ EXISTS
 v_wyckoff_events           | ✓ EXISTS
 v_entry_signals            | ✓ EXISTS
 v_exit_signals             | ✓ EXISTS
(5 rows)
```

## Rollback Plan (if needed)

If something goes wrong, you can rollback:

```sql
-- Remove added columns
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS events_json;
ALTER TABLE model_parameters DROP COLUMN IF EXISTS notes;

-- Drop views
DROP VIEW IF EXISTS v_exit_signals CASCADE;
DROP VIEW IF EXISTS v_entry_signals CASCADE;
DROP VIEW IF EXISTS v_wyckoff_events CASCADE;
```

## Post-Execution Verification

After running the script, verify the database state:

```sql
-- Check daily_snapshots column count (should be 65 now)
SELECT COUNT(*) as column_count 
FROM information_schema.columns 
WHERE table_name = 'daily_snapshots';

-- Check that views return data structure
SELECT * FROM v_wyckoff_events LIMIT 1;
SELECT * FROM v_entry_signals LIMIT 1;
SELECT * FROM v_exit_signals LIMIT 1;
```

## Integration with Sprint 2

Once this cleanup is complete, Sprint 2 can proceed with:
- Wyckoff event detection logic populating `events_json`
- Entry/exit signal generation using the new views
- AI recommendation engine querying these views

## Notes

- The script is idempotent (safe to run multiple times)
- All operations use `IF NOT EXISTS` / `IF EXISTS` clauses
- No existing data will be modified or deleted
- Views use LEFT JOINs to handle missing data gracefully
