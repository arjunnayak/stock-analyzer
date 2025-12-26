# Backfill Guide: Loading Data from Dolt Database

This guide explains how to use the Dolt backfill CLI to load historical price and fundamental data into R2 storage.

## What is Dolt?

[Dolt](https://www.dolthub.com/) is a SQL database with Git-like versioning capabilities. It's perfect for storing historical market data because:
- **Versioning**: Track changes to data over time
- **Branching**: Test data transformations safely
- **SQL**: Standard MySQL protocol for querying
- **Portable**: Clone data like a Git repository

## Prerequisites

### 1. Install Dolt

```bash
# macOS
brew install dolt

# Linux
sudo bash -c 'curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh | sudo bash'

# Windows
# Download from https://github.com/dolthub/dolt/releases
```

### 2. Install MySQL Connector

```bash
uv add mysql-connector-python
# or
pip install mysql-connector-python
```

### 3. Start Dolt SQL Server

```bash
# Create database directory
mkdir -p ~/dolt/market_data
cd ~/dolt/market_data

# Initialize Dolt database
dolt init

# Start SQL server
dolt sql-server --host 0.0.0.0 --port 3306
```

## Expected Database Schema

The backfill script expects the following tables in your Dolt database:

### Prices Table

```sql
CREATE TABLE prices (
    ticker VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(20, 4),
    high DECIMAL(20, 4),
    low DECIMAL(20, 4),
    close DECIMAL(20, 4),
    adj_close DECIMAL(20, 4),
    volume BIGINT,
    PRIMARY KEY (ticker, date),
    INDEX idx_ticker (ticker),
    INDEX idx_date (date)
);
```

### Fundamentals Table

```sql
CREATE TABLE fundamentals (
    ticker VARCHAR(20) NOT NULL,
    period_end DATE NOT NULL,
    fiscal_year INT,
    fiscal_quarter VARCHAR(10),
    revenue DECIMAL(20, 2),
    gross_profit DECIMAL(20, 2),
    operating_income DECIMAL(20, 2),
    net_income DECIMAL(20, 2),
    eps_diluted DECIMAL(20, 4),
    shares_diluted BIGINT,
    total_assets DECIMAL(20, 2),
    total_liabilities DECIMAL(20, 2),
    cash_and_equivalents DECIMAL(20, 2),
    operating_cash_flow DECIMAL(20, 2),
    capex DECIMAL(20, 2),
    free_cash_flow DECIMAL(20, 2),
    PRIMARY KEY (ticker, period_end),
    INDEX idx_ticker (ticker),
    INDEX idx_period_end (period_end)
);
```

## Usage Examples

### Basic Usage

```bash
# Backfill specific tickers
python scripts/backfill_from_dolt.py --tickers AAPL MSFT GOOGL

# Using make
make backfill ARGS='--tickers AAPL MSFT'
```

### Backfill from File

Create a ticker list file (one ticker per line):

```bash
# tickers.txt
AAPL
MSFT
GOOGL
TSLA
NVDA
```

Then run:

```bash
python scripts/backfill_from_dolt.py --ticker-file tickers.txt

# Or with make
make backfill ARGS='--ticker-file tickers.txt'
```

### Backfill All Tickers

```bash
# Backfill everything in Dolt database
python scripts/backfill_from_dolt.py --all
```

### Date Range Filtering

```bash
# Backfill specific date range
python scripts/backfill_from_dolt.py \
  --tickers AAPL \
  --start-date 2020-01-01 \
  --end-date 2024-12-31
```

### Dataset Selection

```bash
# Only backfill price data
python scripts/backfill_from_dolt.py --tickers AAPL --prices-only

# Only backfill fundamentals
python scripts/backfill_from_dolt.py --tickers AAPL --fundamentals-only
```

### Dry Run

```bash
# See what would happen without writing data
python scripts/backfill_from_dolt.py --tickers AAPL --dry-run
```

### Custom Dolt Connection

```bash
python scripts/backfill_from_dolt.py \
  --tickers AAPL \
  --dolt-host localhost \
  --dolt-port 3306 \
  --dolt-database market_data \
  --dolt-user root \
  --dolt-password secret
```

## CLI Options

```
Ticker Selection (required, mutually exclusive):
  --tickers AAPL MSFT     List of ticker symbols
  --ticker-file FILE      File with tickers (one per line)
  --all                   Backfill all tickers in database

Date Range (optional):
  --start-date YYYY-MM-DD Start date for data
  --end-date YYYY-MM-DD   End date for data

Dataset Selection (optional):
  --prices-only           Only backfill price data
  --fundamentals-only     Only backfill fundamental data

Dolt Connection (optional):
  --dolt-host HOST        Dolt host (default: localhost)
  --dolt-port PORT        Dolt port (default: 3306)
  --dolt-database DB      Database name (default: market_data)
  --dolt-user USER        Database user (default: root)
  --dolt-password PASS    Database password (default: empty)

Options:
  --dry-run               Show what would happen without writing
  --verbose, -v           Verbose output
```

## Output Format

The backfill script provides detailed progress output:

```
======================================================================
DOLT → R2 BACKFILL
======================================================================

[1/3] AAPL
----------------------------------------------------------------------

Backfilling prices for AAPL...
  ✓ Fetched 1,256 rows from Dolt
  Merged: 0 existing + 1,256 new = 1,256 total
  ✓ Wrote 1,256 rows to prices/v1/AAPL/2024/01/data.parquet
  ...
  ✓ Wrote 13 monthly files to R2

Backfilling fundamentals for AAPL...
  ✓ Fetched 40 rows from Dolt
  ✓ Wrote 4 monthly files to R2

======================================================================
BACKFILL SUMMARY
======================================================================
Total tickers processed: 3
Successful: 6
No data: 0
Total rows: 3,768
Total files: 39
```

## Loading Data into Dolt

### Option 1: Import from CSV

```sql
-- From Dolt SQL shell
LOAD DATA INFILE '/path/to/prices.csv'
INTO TABLE prices
FIELDS TERMINATED BY ','
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;
```

### Option 2: Import from Pandas

```python
import pandas as pd
import mysql.connector

# Connect to Dolt
conn = mysql.connector.connect(
    host='localhost',
    port=3306,
    database='market_data',
    user='root'
)

# Load data
df = pd.read_csv('prices.csv')

# Insert into Dolt
df.to_sql('prices', conn, if_exists='append', index=False)

# Commit changes (Git-like!)
cursor = conn.cursor()
cursor.execute("CALL dolt_commit('-Am', 'Added price data')")
```

### Option 3: Clone Public Dataset

```bash
# Clone DolthubBot's stock prices dataset
dolt clone dolthub/stock-prices

cd stock-prices
dolt sql-server
```

## Best Practices

1. **Start with Dry Run**: Always test with `--dry-run` first
2. **Incremental Backfills**: Use date ranges to backfill incrementally
3. **Commit Often**: Commit Dolt changes frequently
4. **Version Data**: Use Dolt branches for experimental data
5. **Monitor Progress**: Use verbose mode for large backfills

## Troubleshooting

### Connection Refused

```bash
# Check if Dolt SQL server is running
lsof -i :3306

# Start Dolt SQL server
dolt sql-server
```

### Table Not Found

```bash
# Verify tables exist
dolt sql -q "SHOW TABLES"

# Check schema
dolt sql -q "DESCRIBE prices"
```

### Duplicate Key Errors

The backfill script uses `merge_and_put()` which automatically handles duplicates. If you see errors, check your Dolt data for inconsistencies.

## Integration with Signal Pipeline

After backfilling, the data is immediately available for signal computation:

```bash
# Backfill data
make backfill ARGS='--tickers AAPL MSFT'

# Compute signals
make test-signals

# Run daily evaluation
make run-daily-eval
```

## Performance Tips

- **Parallel Backfills**: Run multiple backfill processes for different ticker sets
- **Date Ranges**: Backfill recent data frequently, historical data less often
- **Batch Size**: For large ticker lists, break into smaller batches
- **Dolt Caching**: Dolt caches queries, so repeated backfills are faster

## Next Steps

1. Set up your Dolt database with historical data
2. Run a dry-run backfill to verify
3. Backfill production data
4. Schedule periodic backfills for updates
5. Integrate with signal computation pipeline
