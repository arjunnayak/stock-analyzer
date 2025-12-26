# Quick Start: Backfill UBER Data

This guide will walk you through backfilling UBER data into your R2 instance as an end-to-end test.

## Prerequisites

### 1. **EODHD API Key** (Free tier available)

Sign up at https://eodhd.com (free tier: 20 API calls/day)

```bash
export EODHD_API_KEY=your_eodhd_api_key_here
```

### 2. **Cloudflare R2 Credentials**

Get from Cloudflare Dashboard → R2 → Manage R2 API Tokens

```bash
export AWS_ACCESS_KEY_ID=your_r2_access_key_id
export AWS_SECRET_ACCESS_KEY=your_r2_secret_access_key
export R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
export R2_BUCKET_NAME=stock-analyzer
```

### 3. **Create .env.local File** (Recommended)

```bash
# Create .env.local in project root
cat > .env.local <<EOF
# EODHD API
EODHD_API_KEY=your_key_here

# R2 Storage
AWS_ACCESS_KEY_ID=your_r2_key
AWS_SECRET_ACCESS_KEY=your_r2_secret
R2_ENDPOINT_URL=https://xxxxx.r2.cloudflarestorage.com
R2_BUCKET_NAME=stock-analyzer

# Database (optional for now)
# DATABASE_URL=postgresql://user:pass@localhost:5432/stocks
EOF

# Load environment variables
source .env.local
# or on some systems:
export $(cat .env.local | grep -v '^#' | xargs)
```

## Step-by-Step Backfill

### Step 1: Verify Configuration

```bash
# Test R2 connection
python -c "from src.storage.r2_client import R2Client; r = R2Client(); print('✓ R2 connected')"

# Test EODHD connection
python -c "from src.ingest.eodhd_client import EODHDClient; e = EODHDClient(); print('✓ EODHD connected')"
```

### Step 2: Run UBER Backfill

```bash
# Backfill last 5 years (default)
python scripts/backfill_uber.py

# Or specify custom date range
python scripts/backfill_uber.py --start-date 2020-01-01 --end-date 2024-12-31
```

**Expected output:**
```
╔====================================================================╗
║                    UBER DATA BACKFILL                              ║
╚====================================================================╝

Ticker: UBER
Date Range: 2019-12-26 to 2024-12-26
Duration: 1827 days

======================================================================
Checking Configuration
======================================================================
✓ EODHD API client configured
✓ R2 storage client configured

======================================================================
STEP 1: Ingest Price Data
======================================================================
Fetching UBER price data from EODHD...
Date range: 2019-12-26 to 2024-12-26

✓ SUCCESS
  Rows ingested: 1258
  Files written: 61
  Storage: R2 prices/v1/UBER/YYYY/MM/data.parquet

======================================================================
STEP 2: Verify Price Data in R2
======================================================================

✓ SUCCESS - Price data readable
  Rows: 22
  Date range: 2024-11-26 to 2024-12-26
  Latest close: $65.43

Sample data (last 5 days):
         date   open   high    low  close    volume
2024-12-20  64.50  65.20  64.10  64.85  18234567
...

======================================================================
STEP 3: Compute Technical Signals
======================================================================
Computing SMA 200 for UBER...

✓ SUCCESS
  Rows computed: 1258
  Files written: 61
  Storage: R2 signals_technical/v1/UBER/YYYY/MM/data.parquet

======================================================================
STEP 4: Verify Technical Signals
======================================================================

✓ SUCCESS - Technical signals computed
  Rows: 365
  Latest date: 2024-12-26
  Latest close: $65.43
  SMA-200: $62.18
  Position: above_sma

======================================================================
STEP 5: Check Fundamental Data Availability
======================================================================

⚠️  No fundamental data in R2 yet
  Note: Fundamentals must be ingested separately
  For MVP, you can:
    1. Backfill from Dolt (if running locally)
    2. Manually ingest from EODHD Fundamentals API
    3. Skip valuation signals for now (use technical only)

======================================================================
STEP 6: Compute Valuation Signals
======================================================================

⚠️  SKIPPED - No fundamental data available
  Valuation signals require quarterly fundamental data

======================================================================
STEP 7: Test Valuation Regime Detection
======================================================================

⚠️  SKIPPED - No valuation data available

======================================================================
BACKFILL SUMMARY
======================================================================
✓ PASS   Ingest Prices
✓ PASS   Verify Prices
✓ PASS   Compute Technical
✓ PASS   Verify Technical
✗ FAIL   Check Fundamentals
✗ FAIL   Compute Valuation
✗ FAIL   Test Valuation Regime

======================================================================
Completed: 4/7 steps successful

✅ UBER data backfill successful!

You can now:
  - View price data: TimeSeriesReader().get_prices('UBER', ...)
  - View signals: TimeSeriesReader().r2.get_timeseries('signals_technical', 'UBER', ...)
  - Run pipeline: SignalPipeline().evaluate_ticker_for_user(...)
```

## What Just Happened?

✅ **Price data ingested** - 5 years of OHLCV data from EODHD
✅ **Technical signals computed** - SMA-200, trend detection
⚠️ **Valuation signals skipped** - Need fundamental data (see below)

## Verify Data in R2

```python
from src.reader import TimeSeriesReader
from datetime import date, timedelta

reader = TimeSeriesReader()

# Read prices
end = date.today()
start = end - timedelta(days=30)
prices = reader.get_prices("UBER", start, end)
print(f"Price rows: {len(prices)}")
print(prices.tail())

# Read technical signals
technical = reader.r2.get_timeseries("signals_technical", "UBER", start, end)
print(f"\nTechnical rows: {len(technical)}")
print(technical[['date', 'close', 'sma_200', 'trend_position']].tail())
```

## Adding Fundamental Data (Optional)

To enable valuation regime detection, you need quarterly fundamental data.

### Option 1: Use EODHD Fundamentals API

```python
from src.ingest.eodhd_client import EODHDClient
from src.storage.r2_client import R2Client
from datetime import date
import pandas as pd

# Fetch fundamentals from EODHD
client = EODHDClient()
fundamentals = client.get_fundamentals("UBER")  # If this method exists

# TODO: Parse quarterly data and structure as:
# columns: date, sales, income_before_depreciation, shares_outstanding,
#          long_term_debt, cash_and_equivalents, etc.

# Write to R2
r2 = R2Client()
# ... partition by month and write
```

### Option 2: Use Dolt Database (If Running Locally)

```bash
# If you have Dolt running locally with earnings data
python scripts/backfill_from_dolt.py --tickers UBER --fundamentals-only
```

### Option 3: Skip Valuation for MVP

For initial testing, you can run the pipeline with **technical signals only**:
- Trend breaks (200-day MA crossovers)
- Price movements

Valuation regime alerts will be skipped until fundamental data is available.

## Test the Pipeline

Now that UBER data is loaded, test the full signal evaluation:

```python
from src.signals.pipeline import SignalPipeline
from datetime import datetime

# You'll need a test user and entity in the database
# For now, test signal detection directly:

from src.signals.technical import TechnicalSignals
from src.reader import TimeSeriesReader
from datetime import date, timedelta

reader = TimeSeriesReader()
end = date.today()
start = end - timedelta(days=365)

# Get prices
df = reader.get_prices("UBER", start, end)

# Compute signals
df = TechnicalSignals.compute_all_technical_signals(df)

# Get latest
latest = TechnicalSignals.get_latest_signals(df)

print(f"\nUBER Latest Signals:")
print(f"  Close: ${latest['close']:.2f}")
print(f"  SMA-200: ${latest['sma_200']:.2f}")
print(f"  Trend: {latest['trend_position']}")
print(f"  Crossover: {latest.get('crossover', 'None')}")
```

## Troubleshooting

### Error: "EODHD_API_KEY not set"

```bash
export EODHD_API_KEY=your_key_here
```

### Error: "R2 connection failed"

Check all R2 credentials are set:
```bash
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY
echo $R2_ENDPOINT_URL
echo $R2_BUCKET_NAME
```

### Error: "No data returned from EODHD"

- Check API key is valid
- Verify ticker is correct ("UBER" for US exchange)
- Check free tier limits (20 calls/day)

### R2 Bucket Doesn't Exist

Create bucket in Cloudflare Dashboard or via CLI:
```bash
aws s3 mb s3://stock-analyzer --endpoint-url=$R2_ENDPOINT_URL
```

## Next Steps

After successful backfill:

1. **Add more tickers** - Run for AAPL, MSFT, TSLA, etc.
2. **Set up PostgreSQL** - Add users and watchlists
3. **Test full pipeline** - Run daily evaluation
4. **Add fundamental data** - Enable valuation regime detection
5. **Test email delivery** - Send test alert

## Cost Estimate

**EODHD Free Tier:**
- 20 API calls/day
- 1 ticker = 1 call for 5 years of data
- Sufficient for testing 10-20 tickers

**Cloudflare R2 Free Tier:**
- 10 GB storage
- 1 million Class A operations/month (writes)
- 10 million Class B operations/month (reads)
- Sufficient for 100+ tickers

**Total cost for testing:** $0

---

**You're ready to backfill UBER!** 🚀

Just run: `python scripts/backfill_uber.py`
