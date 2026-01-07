# Daily Pipeline Date Issue - Fix Summary

## Problem

The daily pipeline was only processing data through December 31, 2025, even though it was running on January 5, 2026 (and multiple trading days had occurred since then).

## Root Causes (Two Separate Issues)

### Issue 1: Workflow Step Conditions

**Critical Bug in `.github/workflows/daily-pipeline.yml`**

Lines 70, 95, and 134 had incorrect conditional logic:

```yaml
# WRONG - This fails for scheduled runs
if: ${{ !inputs.skip_ingestion }}
if: ${{ !inputs.skip_features }}
if: ${{ !inputs.skip_templates }}
```

**Why This Broke Scheduled Runs:**

1. The `inputs` context only exists for `workflow_dispatch` (manual) triggers
2. For `schedule` (cron) triggers, `inputs` is undefined/null
3. When GitHub Actions evaluates `!inputs.skip_ingestion` with undefined inputs:
   - It evaluates to `false`
   - The step is **SKIPPED**

**Result:** STEP 1 (price ingestion) never ran on automatic daily runs, so:
- No new price data was fetched from EODHD API
- R2 storage only had data through Dec 31, 2025
- STEP 2 (features) correctly found "latest available data" = Dec 31
- Pipeline appeared to work but was processing stale data

**Fix for Issue 1:**

Changed all three step conditions to:

```yaml
# CORRECT - Handles both scheduled and manual runs
if: ${{ github.event_name == 'schedule' || !inputs.skip_ingestion }}
if: ${{ github.event_name == 'schedule' || !inputs.skip_features }}
if: ${{ github.event_name == 'schedule' || !inputs.skip_templates }}
```

**This ensures:**
- **Scheduled runs (cron)**: Always run all steps (`github.event_name == 'schedule'` is true)
- **Manual runs**: Respect skip flags (`!inputs.skip_*` is evaluated)

---

### Issue 2: Date Discovery Logic

**Critical Bug in `src/features/pipeline_daily.py`**

After fixing Issue 1, STEP 1 successfully ingested data for 2026-01-02, 2026-01-03, and 2026-01-06. However, STEP 2 still processed 2025-12-31.

**The Problem:**

Lines 111-121 checked for the latest date in this order:
1. ✅ Check snapshots first (fast) → Found `2025-12-31` snapshot
2. ❌ **Never checked ingestion data** because snapshot was found
3. Used stale date `2025-12-31`

**Why this failed:**
- Newly ingested data was in `prices/v1/AAPL/2026/01/data.parquet`
- No **snapshot** existed for 2026-01-06 yet
- Old `2025-12-31` snapshot still existed (< 7 days old, considered "fresh")
- Pipeline chose old snapshot, ignored new ingestion data

**Fix for Issue 2:**

Reversed the priority in date discovery:

```python
# OLD (wrong priority)
1. Check snapshots first
2. If no snapshot, check ingestion data

# NEW (correct priority)
1. Check ingestion data first (absolute latest)
2. If no ingestion data, fall back to snapshots
```

**This ensures:** After STEP 1 ingests new data, STEP 2 always discovers and processes the latest date, even if snapshots haven't been created yet.

## Changes Made

### Modified Files
- `.github/workflows/daily-pipeline.yml` - Fixed all 3 step conditions (Issue 1)
- `.github/workflows/daily-backfill.yml` - Modernized and disabled auto-schedule
- `src/features/pipeline_daily.py` - Fixed date discovery priority (Issue 2)

### New Diagnostic Scripts (for future debugging)
- `scripts/debug_date_issue.py` - Checks system date, R2 data, and EODHD API
- `scripts/check_recent_price_data.py` - Verifies R2 has data for recent dates

## Testing the Fix

### Immediate Verification

Wait for tonight's scheduled run (11 PM UTC / 6 PM ET) and check:

```bash
# After the pipeline runs, check R2 for 2026 data
uv run python scripts/check_recent_price_data.py
```

Expected output should show data for January 2026.

### Manual Test (Don't Wait)

Trigger a manual run now:

1. Go to GitHub Actions → Daily Pipeline
2. Click "Run workflow"
3. Leave all inputs empty (defaults)
4. Click "Run workflow"

Or via CLI:
```bash
gh workflow run daily-pipeline.yml
```

Check logs to confirm STEP 1 runs and fetches recent data.

## Why The Pipeline Seemed to Work

The pipeline didn't fail or error out because:
1. STEP 2 is designed to auto-discover the latest available data (within 7 days)
2. December 31 was within the 7-day lookback window
3. All subsequent steps ran successfully with Dec 31 data
4. No error messages were generated

The only symptom was the log line:
```
✓ Using latest available price data: 2025-12-31
```

## Long-term Recommendation

Consider adding a validation check to STEP 0 that alerts if data is > 3 days old during normal trading weeks. This would catch similar issues faster.

Example check:
```python
# In pipeline_daily.py, Step 0
data_age_days = (date.today() - run_date).days
if data_age_days > 3 and not is_holiday_week():
    print(f"⚠️  WARNING: Data is {data_age_days} days old")
```

## Files Changed

- `.github/workflows/daily-pipeline.yml` (3 lines)
- `scripts/debug_date_issue.py` (new)
- `scripts/check_recent_price_data.py` (new)

## Commits

```
commit 0a4b56d - Fix daily pipeline not ingesting data for 2026 (Issue 1)
commit a2bbda4 - Fix and disable automatic daily backfill workflow
commit 798fed5 - Fix date discovery to check ingestion data before snapshots (Issue 2)
```

## Next Steps

1. ✅ Both fixes are now on branch `claude/fix-pipeline-date-issue-CvciG`
2. **Test by manually triggering the workflow again** to verify it now processes 2026-01-06
3. Expected output: `✓ Using latest available price data: 2026-01-06`
4. Merge to main once verified
5. Monitor for a few days to ensure continuous operation

## Expected Behavior After Fix

When you run the pipeline now:
1. **STEP 1**: Ingests prices from EODHD (2025-12-31 to 2026-01-07)
   - Writes to `prices/v1/*/2026/01/data.parquet`
2. **STEP 2**: Date discovery checks ingestion data
   - Finds latest date: **2026-01-06** (most recent trading day)
   - Creates snapshot for 2026-01-06
   - Computes features for 2026-01-06
3. **STEP 3**: Evaluates templates using 2026-01-06 data
