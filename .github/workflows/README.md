# GitHub Actions Workflows

This directory contains automated workflows for the stock analyzer MVP.

## Workflows

### 1. Daily Signal Evaluation (`daily-evaluation.yml`)

**Purpose:** Run the daily batch job to evaluate signals and send alerts

**Schedule:** Daily at 6 PM ET (11 PM UTC)

**What it does:**
- Evaluates all active watchlists
- Detects material changes (valuation regime, trend breaks)
- Generates and sends email alerts
- Logs results for validation metrics

**Manual trigger:**
```bash
# Trigger via GitHub UI or CLI
gh workflow run daily-evaluation.yml
```

**Required secrets:**
- `SUPABASE_URL` - Supabase API URL (e.g., https://xxx.supabase.co)
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key (full access for backend/CI)
- `R2_ACCESS_KEY_ID` - Cloudflare R2 access key
- `R2_SECRET_ACCESS_KEY` - Cloudflare R2 secret
- `R2_ENDPOINT_URL` - R2 endpoint
- `R2_BUCKET_NAME` - R2 bucket name
- `EODHD_API_KEY` - EODHD data provider API key
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` - Email delivery
- `ALERT_EMAIL` - Email to notify on failures

---

### 2. CI/CD (`ci.yml`)

**Purpose:** Run tests and validation on PRs and pushes

**Triggers:**
- Push to `main` or `claude/**` branches
- Pull requests to `main`

**What it does:**
- Runs unit tests (`test_valuation_regime.py`)
- Lints code with ruff
- Type checks with mypy
- Validates data pipeline connectivity

**No secrets required for basic tests**

---

### 3. Compute Valuation Metrics (`compute-metrics.yml`)

**Purpose:** Weekly batch job to backfill/update valuation metrics in R2

**Schedule:** Weekly on Sundays at 2 AM UTC

**What it does:**
- Computes EV/Revenue and EV/EBITDA for all active tickers
- Calculates TTM revenue and EBITDA from quarterly data
- Writes results to R2 storage
- Handles incremental updates (only recomputes missing dates)

**Manual trigger with options:**
```bash
gh workflow run compute-metrics.yml \
  -f tickers="AAPL,MSFT,GOOGL" \
  -f force=true
```

**Required secrets:** Same as daily evaluation

---

### 4. Data Backfill (`backfill.yml`)

**Purpose:** One-time or catch-up data backfill

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

# Backfill valuation metrics for all active tickers
gh workflow run backfill.yml \
  -f dataset=valuation

# Backfill fundamentals for specific date range
gh workflow run backfill.yml \
  -f dataset=fundamentals \
  -f start_date=2023-01-01 \
  -f end_date=2024-01-01
```

**Required secrets:** Same as daily evaluation

---

## Setting Up Secrets

Navigate to your GitHub repository settings:

**Settings → Secrets and variables → Actions → New repository secret**

Add all required secrets listed above.

### Development/Testing Secrets

For testing workflows without production data:

```bash
# Local testing (create .env.github file)
DATABASE_URL=postgresql://user:pass@localhost:5432/stocks
R2_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com
R2_BUCKET_NAME=stock-analyzer-dev
R2_ACCESS_KEY_ID=your_key
R2_SECRET_ACCESS_KEY=your_secret
EODHD_API_KEY=your_api_key
```

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
```

### Artifacts

All workflows upload logs as artifacts:
- **Daily evaluation logs**: Retained for 7 days
- **Metrics computation logs**: Retained for 14 days
- **Backfill logs**: Retained for 30 days

### Notifications

The daily evaluation workflow sends email alerts on failure to `ALERT_EMAIL`.

---

## Cost Optimization

### GitHub Actions Free Tier

- **2,000 minutes/month** for private repos
- **Unlimited** for public repos

### Our Usage (estimated):

- **Daily evaluation**: ~5 min/day = 150 min/month
- **Weekly metrics**: ~15 min/week = 60 min/month
- **CI/CD**: ~3 min/run × 20 runs = 60 min/month
- **Total**: ~270 min/month (well within free tier)

### Tips:

1. Use `timeout-minutes` to prevent runaway jobs
2. Cache Python dependencies with `cache: 'pip'`
3. Run expensive jobs weekly, not daily
4. Use `workflow_dispatch` for manual/testing workflows

---

## Troubleshooting

### Workflow fails with "Module not found"

Check that dependencies are installed:
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -e .
```

### Secrets not available

Verify secrets are set in repository settings and named exactly as in workflow files.

### Timeout issues

Increase `timeout-minutes` for large data processing jobs:
```yaml
jobs:
  compute-metrics:
    timeout-minutes: 120  # 2 hours
```

### R2 connection errors

Verify R2 credentials and endpoint URL. Test locally first:
```bash
python -c "from src.storage.r2_client import R2Client; R2Client().list_keys()"
```

---

## Next Steps

After workflows are set up:

1. **Test manually**: Run each workflow via GitHub UI to verify
2. **Monitor first runs**: Check logs and artifacts
3. **Set up alerts**: Configure `ALERT_EMAIL` for failure notifications
4. **Add metrics**: Instrument code to track validation hooks
5. **Optimize schedules**: Adjust cron times based on data availability

---

**Note:** All workflows use `ubuntu-latest` runners and Python 3.10 for consistency with local development.
