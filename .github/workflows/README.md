# GitHub Actions Workflows

This directory contains automated workflows for the stock analyzer MVP.

## Workflow Overview

**3 Simple Workflows:**

1. **Daily Pipeline** - End-of-day data ingestion, metrics computation, and alert evaluation
2. **CI/CD** - Testing and validation on code changes
3. **Backfill** - Manual/adhoc historical data backfills

---

## 1. Daily Pipeline (`daily-pipeline.yml`)

**Purpose:** Complete end-of-day workflow that keeps data fresh and sends alerts

**Schedule:** Daily at 11 PM UTC (6 PM ET) - after market close + data availability

**What it does (in sequence):**

1. **Ingest Prices** (5-10 min)
   - Fetches all tickers from active watchlists
   - Retrieves latest 7 days of price data from EODHD API
   - Merges with existing data in R2 (deduplicates by date)

2. **Compute Metrics** (5-15 min)
   - Computes valuation metrics (EV/Revenue, EV/EBITDA) for watchlist tickers
   - Incremental update - only computes missing dates
   - Writes to R2 storage

3. **Evaluate & Alert** (2-5 min)
   - Evaluates all active watchlists
   - Detects material changes (valuation regime, trend breaks)
   - Generates and sends email alerts
   - Logs results for validation metrics

**Total runtime:** ~15-30 minutes

**Manual trigger:**
```bash
# Run full pipeline for all watchlist tickers
gh workflow run daily-pipeline.yml

# Run for specific tickers only
gh workflow run daily-pipeline.yml -f tickers="AAPL MSFT GOOGL"

# Skip price ingestion (use existing data)
gh workflow run daily-pipeline.yml -f skip_ingestion=true

# Skip metrics computation
gh workflow run daily-pipeline.yml -f skip_metrics=true
```

**Required secrets:**
- `SUPABASE_URL` - Supabase API URL
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key (full access)
- `R2_ACCESS_KEY_ID` - Cloudflare R2 access key
- `R2_SECRET_ACCESS_KEY` - Cloudflare R2 secret
- `R2_ENDPOINT_URL` - R2 endpoint URL
- `R2_BUCKET_NAME` - R2 bucket name
- `EODHD_API_KEY` - EODHD data provider API key
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` - Email delivery
- `ALERT_EMAIL` - Email for failure notifications

**Why it's important:** This single workflow ensures fresh data → accurate metrics → timely alerts, all in one atomic operation.

---

## 2. CI/CD (`ci.yml`)

**Purpose:** Run tests and validation on code changes

**Triggers:**
- Push to `main` or `claude/**` branches
- Pull requests to `main`

**What it does:**
- Runs unit tests (`test_valuation_regime.py`)
- Lints code with ruff
- Type checks with mypy
- Validates data pipeline connectivity (on PRs only)

**No secrets required for basic tests**

**Uses:** `uv` for fast dependency installation

---

## 3. Backfill (`backfill.yml`)

**Purpose:** Manual/adhoc historical data backfills

**Triggers:** Manual only

**What it does:**
- Backfills historical data for any dataset (prices, fundamentals, technical, valuation)
- Supports date range and ticker filtering
- Verifies backfill results

**Usage examples:**

```bash
# Backfill all prices for AAPL since 2020
gh workflow run backfill.yml \
  -f dataset=prices \
  -f tickers=AAPL \
  -f start_date=2020-01-01

# Backfill fundamentals for specific date range
gh workflow run backfill.yml \
  -f dataset=fundamentals \
  -f start_date=2023-01-01 \
  -f end_date=2024-01-01
```

**Required secrets:** Same as daily pipeline

---

## Setting Up Secrets

Navigate to your GitHub repository settings:

**Settings → Secrets and variables → Actions → New repository secret**

Add all secrets listed in the Daily Pipeline section above (9 total).

---

## Monitoring

### View Workflow Runs

```bash
# List recent runs
gh run list

# View specific run
gh run view <run-id>

# Download logs
gh run download <run-id>

# Watch a workflow in real-time
gh run watch
```

### Artifacts

All workflows upload logs as artifacts:
- **Daily pipeline logs**: Retained for 7 days
- **Backfill logs**: Retained for 30 days

### Notifications

The daily pipeline sends email alerts on failure to `ALERT_EMAIL`.

---

## Cost Optimization

### GitHub Actions Free Tier

- **2,000 minutes/month** for private repos
- **Unlimited** for public repos

### Our Usage (estimated):

- **Daily pipeline**: ~20 min/day = 600 min/month
- **CI/CD**: ~3 min/run × 20 runs = 60 min/month
- **Total**: ~660 min/month (well within free tier)

### Tips:

1. Use `timeout-minutes` to prevent runaway jobs
2. `uv` provides fast dependency installation (no caching needed)
3. Daily pipeline is incremental - only processes new data
4. Use `workflow_dispatch` for manual testing without affecting quotas

---

## Troubleshooting

### Daily pipeline fails at ingestion step

**Symptoms:** Price ingestion fails with API errors

**Solutions:**
- Check EODHD API key is valid
- Verify API rate limits not exceeded
- Test locally: `uv run python scripts/ingest_prices.py --tickers AAPL`

### Daily pipeline fails at metrics step

**Symptoms:** Valuation computation fails for some tickers

**Solutions:**
- Check if fundamental data exists in R2
- Run backfill for fundamentals: `gh workflow run backfill.yml -f dataset=fundamentals`
- Test locally: `uv run python scripts/compute_metrics.py --ticker AAPL --valuation-only`

### Daily pipeline fails at evaluation step

**Symptoms:** Signal evaluation or alert sending fails

**Solutions:**
- Check Supabase connection (watchlist data)
- Verify SMTP credentials for email delivery
- Test locally: `uv run python -m src.signals.pipeline`

### Secrets not available

Verify secrets are set in repository settings and named exactly as in workflow files.

### R2 connection errors

Verify R2 credentials and endpoint URL. Test locally:
```bash
uv run python -c "from src.storage.r2_client import R2Client; R2Client().list_keys()"
```

---

## Migration from Old Workflows

If you have the old separate workflows (`ingest-prices.yml`, `daily-evaluation.yml`, `compute-metrics.yml`), they are now consolidated into `daily-pipeline.yml`.

**Old setup:**
- 10 PM UTC: Ingest prices
- 11 PM UTC: Evaluate signals
- Weekly: Compute metrics

**New setup:**
- 11 PM UTC: Daily pipeline (all three steps in sequence)

**Benefits:**
- Simpler to monitor (one workflow instead of three)
- Guaranteed execution order
- Single failure notification
- Easier to debug (all logs in one place)

---

## Next Steps

After workflows are set up:

1. **Test manually**: Run daily pipeline via GitHub UI to verify
2. **Monitor first scheduled run**: Check logs and artifacts
3. **Set up alerts**: Configure `ALERT_EMAIL` for failure notifications
4. **Review costs**: Monitor GitHub Actions usage in Settings → Billing

---

**Note:** All workflows use `ubuntu-latest` runners, Python 3.10, and `uv` for fast, deterministic dependency installation.
