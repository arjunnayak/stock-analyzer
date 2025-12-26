# Backfill UBER Data Using Dolt (No API Requests!)

This guide shows you how to backfill UBER data using your local Dolt database instead of consuming EODHD API requests.

## Why Use Dolt?

- **Free**: No API rate limits or request quotas
- **Fast**: Local database queries
- **Complete**: Includes both price and fundamental data
- **Versioned**: Git-like versioning for historical data

## Prerequisites

1. **Dolt databases running** (stocks + earnings)
2. **R2 storage configured** (local MinIO or Cloudflare R2)
3. **mysql-connector-python installed**

## Quick Start

### Step 1: Start Dolt Services

```bash
# Start both Dolt databases
docker-compose up -d dolt-stocks dolt-earnings

# Verify they're running
docker ps | grep dolt
```

You should see:
```
stock-analyzer-dolt-stocks     Up
stock-analyzer-dolt-earnings   Up
```

### Step 2: Verify Dolt Connection

```bash
# Test stocks DB connection
mysql -h 127.0.0.1 -P 3306 -u root -e "SELECT COUNT(*) FROM stocks.ohlcv WHERE act_symbol='UBER'"

# Test earnings DB connection
mysql -h 127.0.0.1 -P 3307 -u root -e "SELECT COUNT(*) FROM earnings.income_statement WHERE act_symbol='UBER'"
```

### Step 3: Run UBER Backfill with Dolt

```bash
python scripts/backfill_uber.py --use-dolt
```

This will:
1. ✓ Fetch price data from Dolt stocks DB
2. ✓ Fetch fundamental data from Dolt earnings DB
3. ✓ Write to R2 storage
4. ✓ Compute technical signals (SMA-200)
5. ✓ Compute valuation signals (EV/Revenue, EV/EBITDA)
6. ✓ Test valuation regime detection

**No EODHD API requests used!** 🎉

### Step 4: Customize Date Range (Optional)

```bash
# Last 3 years only
python scripts/backfill_uber.py --use-dolt \
  --start-date 2022-01-01 \
  --end-date 2024-12-26

# Last 10 years for better percentile analysis
python scripts/backfill_uber.py --use-dolt \
  --start-date 2015-01-01 \
  --end-date 2024-12-26
```

## Command Reference

```bash
# Full usage
python scripts/backfill_uber.py --help

# Basic Dolt backfill
python scripts/backfill_uber.py --use-dolt

# With custom date range
python scripts/backfill_uber.py --use-dolt \
  --start-date 2020-01-01 \
  --end-date 2024-12-26

# Custom Dolt ports (if different)
python scripts/backfill_uber.py --use-dolt \
  --stocks-port 3306 \
  --earnings-port 3307 \
  --dolt-host localhost
```

## Expected Output

```
╔====================================================================╗
║                    UBER DATA BACKFILL                             ║
╚====================================================================╝

Ticker: UBER
Date Range: 2019-12-31 to 2024-12-26
Duration: 1822 days
Data Source: Dolt Database

======================================================================
Checking Configuration
======================================================================
✓ Connected to Dolt stocks DB (port 3306)
✓ Connected to Dolt earnings DB (port 3307)
✓ Dolt client configured
✓ R2 storage client configured

======================================================================
STEP 1: Ingest Price Data (from Dolt)
======================================================================
Fetching UBER price data from Dolt...
Date range: 2019-12-31 to 2024-12-26
✓ Fetched 1,247 rows from Dolt

✓ SUCCESS
  Rows ingested: 1,247
  Files written: 61
  Storage: R2 prices/v1/UBER/YYYY/MM/data.parquet

======================================================================
STEP 1.5: Ingest Fundamental Data (from Dolt)
======================================================================
Fetching UBER fundamental data from Dolt...
✓ Fetched 20 rows from Dolt

✓ SUCCESS
  Rows ingested: 20
  Files written: 5
  Storage: R2 fundamentals/v1/UBER/YYYY/MM/data.parquet

[... continues with technical and valuation signals ...]

======================================================================
BACKFILL SUMMARY
======================================================================
✓ PASS   Ingest Prices
✓ PASS   Ingest Fundamentals
✓ PASS   Verify Prices
✓ PASS   Compute Technical
✓ PASS   Verify Technical
✓ PASS   Check Fundamentals
✓ PASS   Compute Valuation
✓ PASS   Test Valuation Regime

======================================================================
Completed: 8/8 steps successful

✅ UBER data backfill successful!
```

## Troubleshooting

### Error: "Can't connect to MySQL server on localhost:3306"

**Cause**: Dolt databases not running

**Solution**:
```bash
# Start Dolt services
docker-compose up -d dolt-stocks dolt-earnings

# Check they're running
docker ps | grep dolt
```

### Error: "mysql-connector-python not installed"

**Cause**: Missing Python MySQL driver

**Solution**:
```bash
pip install mysql-connector-python
```

### Error: "No price data found in Dolt for UBER"

**Cause**: UBER not in your Dolt database

**Solution**:
1. Check if UBER exists:
   ```bash
   mysql -h 127.0.0.1 -P 3306 -u root -e "SELECT DISTINCT act_symbol FROM stocks.ohlcv" | grep UBER
   ```

2. If not found, try another ticker:
   ```bash
   # List available tickers
   mysql -h 127.0.0.1 -P 3306 -u root -e "SELECT DISTINCT act_symbol FROM stocks.ohlcv LIMIT 10"
   ```

3. Or use the generic backfill script:
   ```bash
   python scripts/backfill_from_dolt.py --tickers AAPL MSFT GOOGL
   ```

### Performance: Slow Queries

**Cause**: Dolt database not indexed

**Solution**:
```bash
# Add indexes to Dolt tables
docker exec -it stock-analyzer-dolt-stocks dolt sql -q \
  "CREATE INDEX idx_symbol_date ON ohlcv(act_symbol, date)"

docker exec -it stock-analyzer-dolt-earnings dolt sql -q \
  "CREATE INDEX idx_symbol_date ON income_statement(act_symbol, date)"
```

## Comparison: Dolt vs EODHD

| Feature | Dolt | EODHD API |
|---------|------|-----------|
| **Cost** | Free (local) | Limited free requests |
| **Speed** | Fast (local queries) | Slower (network calls) |
| **Rate Limits** | None | Yes (20 free/day) |
| **Historical Data** | Complete archive | API-dependent |
| **Fundamentals** | Included | Separate API calls |
| **Offline Use** | Yes | No |

## Next Steps

After successful backfill:

1. **Test Signal Evaluation**:
   ```python
   from src.signals.pipeline import SignalPipeline

   pipeline = SignalPipeline()
   pipeline.evaluate_ticker_for_user("UBER", "user123", "user123")
   ```

2. **Backfill More Tickers**:
   ```bash
   # Use the generic Dolt backfill script
   python scripts/backfill_from_dolt.py --tickers UBER LYFT ABNB
   ```

3. **Set Up Daily Pipeline**:
   - See `.github/workflows/daily-evaluation.yml`
   - Configure to run at 6 PM ET daily

---

**Summary**: Using `--use-dolt` saves your precious EODHD API requests for production use while allowing unlimited local testing and development! 🚀
