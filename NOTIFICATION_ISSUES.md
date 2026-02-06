# GitHub Automation & Notification Issues - Analysis

## Issue: No Notifications Received

### Root Cause Analysis

After investigating the GitHub Actions workflows and notification configuration, I've identified **why you're not getting notifications**:

## Finding 1: Notifications Only Sent on FAILURE

**Current Configuration:**
```yaml
- name: Notify on failure
  if: failure()
  uses: dawidd6/action-send-mail@v3
  with:
    to: ${{ secrets.ALERT_EMAIL }}
    subject: '[ALERT] Daily Pipeline Failed'
```

**What this means:**
- ✅ You **WILL** get an email if the pipeline **FAILS**
- ❌ You **WON'T** get any email if the pipeline **SUCCEEDS**
- ❌ No confirmation that automation is running daily

**Why you haven't received notifications:**

### Scenario A: Pipelines Are Running Successfully (Main Branch)
If the pipelines on the **main branch** are running and succeeding:
- No failure = no email
- You have zero visibility into automation health
- Data may be up-to-date but you don't know it

### Scenario B: Pipelines Aren't Running at All (Bug We Just Fixed)
If the pipelines on **main branch** have the original bug:
- STEP 1 (ingestion) is being skipped on scheduled runs
- Pipeline appears to succeed (processes stale 2025-12-31 data)
- No failure = no email
- Data is NOT up-to-date

**The fix on branch `claude/fix-pipeline-date-issue-CvciG` hasn't been merged to main yet**, so scheduled runs on main still have the bug!

---

## Finding 2: No Success Notifications Configured

**Current success step:**
```yaml
- name: Report pipeline success
  if: success()
  run: |
    echo "✅ Daily Pipeline Completed Successfully"
    echo "All steps completed:"
    echo "  ✓ Price data ingested"
    ...
```

**Problem:** This only logs to GitHub Actions console - **no email is sent**!

---

## Finding 3: Scheduled Workflows Run from Main Branch Only

**Critical insight:**
- Scheduled workflows (cron) **ALWAYS** run from the **default branch (main)**
- Your fixes are on branch `claude/fix-pipeline-date-issue-CvciG`
- Until merged, scheduled runs still use the buggy code

**Timeline:**
1. **Before fixes:** Daily cron skips ingestion, processes 2025-12-31 data, succeeds → no email
2. **After fixes (on feature branch):** Manual triggers work, but scheduled runs still broken on main
3. **After merge:** Scheduled runs will work correctly

---

## Recommended Fixes

### Immediate: Add Success Notifications

Add this step to `.github/workflows/daily-pipeline.yml`:

```yaml
- name: Notify on success
  if: success()
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: ${{ secrets.SMTP_HOST }}
    server_port: ${{ secrets.SMTP_PORT }}
    username: ${{ secrets.SMTP_USER }}
    password: ${{ secrets.SMTP_PASSWORD }}
    subject: '[✓] Daily Pipeline Succeeded'
    to: ${{ secrets.ALERT_EMAIL }}
    from: Material Changes Alerts <noreply@materialchanges.app>
    body: |
      The daily pipeline completed successfully.

      Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
      Date: ${{ github.event.head_commit.timestamp }}

      Summary:
      - Price data ingested
      - Features computed
      - Templates evaluated
      - Alerts sent to users

      Check the logs for details: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

### Short-term: Merge the Fix

**Merge PR for branch `claude/fix-pipeline-date-issue-CvciG` to main**

This ensures scheduled runs will:
1. Actually ingest new data
2. Process current dates (not 2025-12-31)
3. Send proper alerts to users

### Long-term: Add Daily Health Check Workflow

Create a separate workflow that runs AFTER the daily pipeline to verify:
- Data was ingested for current date
- Features were computed for current date
- Alerts were sent (if any)

**Example workflow: `.github/workflows/health-check.yml`**
```yaml
name: Daily Health Check

on:
  schedule:
    # Run 1 hour after daily pipeline (12 AM UTC)
    - cron: '0 0 * * *'
  workflow_dispatch:

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run python scripts/check_automation_health.py
        env:
          ENV: REMOTE
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          AWS_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          R2_ENDPOINT_URL: ${{ secrets.R2_ENDPOINT_URL }}
          R2_BUCKET_NAME: ${{ secrets.R2_BUCKET_NAME }}

      - name: Send health report
        if: always()
        uses: dawidd6/action-send-mail@v3
        with:
          server_address: ${{ secrets.SMTP_HOST }}
          server_port: ${{ secrets.SMTP_PORT }}
          username: ${{ secrets.SMTP_USER }}
          password: ${{ secrets.SMTP_PASSWORD }}
          subject: '[HEALTH] Daily Automation Report'
          to: ${{ secrets.ALERT_EMAIL }}
          from: Material Changes Alerts <noreply@materialchanges.app>
          body: |
            Daily automation health check completed.

            Check the logs for detailed results:
            ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

---

## Current Status

### What We Know:
1. ✅ Notification infrastructure is configured (SMTP secrets, email action)
2. ❌ Only failure notifications enabled (no success emails)
3. ❌ Bugs in main branch prevent proper data ingestion on scheduled runs
4. ✅ Fixes exist on feature branch but not merged yet

### What We Don't Know (Need to Check):
1. Are scheduled runs actually executing on main?
2. What's the current date of data in production?
3. Have there been any recent failures?

### How to Check:
1. **GitHub Actions tab** → Check recent workflow runs
   - Look for "Daily Pipeline" runs
   - Check if they're running at 11 PM UTC
   - Review logs to see what date they processed

2. **Check production data:**
   ```bash
   # Run this in GitHub Actions or with production credentials
   uv run python scripts/check_automation_health.py
   ```

3. **Review alert history in Supabase:**
   ```sql
   SELECT
     DATE(sent_at) as date,
     COUNT(*) as alert_count
   FROM alert_history
   WHERE sent_at >= NOW() - INTERVAL '7 days'
   GROUP BY DATE(sent_at)
   ORDER BY date DESC;
   ```

---

## Action Items

### Priority 1 (Critical):
- [ ] **Merge the pipeline fix PR** to enable proper data ingestion
- [ ] **Add success notifications** to daily and weekly workflows
- [ ] **Verify the merge worked** by checking tomorrow's scheduled run

### Priority 2 (Important):
- [ ] **Create health check workflow** for daily monitoring
- [ ] **Review last 7 days of GitHub Actions** runs to understand current state
- [ ] **Check production data dates** to confirm what's actually being processed

### Priority 3 (Nice to have):
- [ ] Set up GitHub Actions failure notifications in Slack/Discord
- [ ] Create dashboard showing last run dates and status
- [ ] Add more detailed success emails (e.g., "10 triggers fired, 3 alerts sent")

---

## Questions to Answer

1. **What branch is currently deployed?**
   - Scheduled workflows run from main branch only
   - Is main branch up-to-date with fixes?

2. **When was the last successful price ingestion?**
   - Check R2 for latest data in `prices/v1/*/2026/01/`
   - Check features for latest computed date

3. **Are users actually receiving stock alerts?**
   - Check `alert_history` table
   - Verify SMTP credentials are working

4. **Should you get notifications even when no alerts fire?**
   - Current setup: Pipeline can succeed without sending any user alerts (if no templates trigger)
   - Should you get a "pipeline ran successfully, no triggers" notification?

---

## Next Steps

1. **Merge the PR** - This is blocking proper automation
2. **Add success notifications** - Get visibility into automation health
3. **Run manual health check** - Understand current state
4. **Monitor for 2-3 days** - Confirm automation is working as expected

