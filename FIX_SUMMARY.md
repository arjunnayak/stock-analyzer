# Daily Pipeline Date Issue - Fix Summary

## Problem

The daily pipeline was only processing data through December 31, 2025, even though it was running on January 5, 2026 (and multiple trading days had occurred since then).

## Root Cause

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

## The Fix

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

## Changes Made

### Modified Files
- `.github/workflows/daily-pipeline.yml` - Fixed all 3 step conditions

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

## Commit

```
commit 0a4b56d
Fix daily pipeline not ingesting data for 2026
```

## Next Steps

1. ✅ Fix is now on branch `claude/fix-pipeline-date-issue-CvciG`
2. Wait for tonight's run OR manually trigger to verify
3. Merge to main once verified
4. Monitor for a few days to ensure continuous operation
