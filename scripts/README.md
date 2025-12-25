# Scripts

Utility scripts for data ingestion, testing, and management.

## Available Scripts

### test_ingest_and_read.py

Comprehensive test script that verifies the entire data pipeline:

1. Configuration loading
2. R2/MinIO connection
3. EODHD API access
4. Data ingestion (fetch from API, store in R2)
5. Data reading (retrieve from R2)

**Usage:**

```bash
# Make sure services are running first
make start

# Run the test
python scripts/test_ingest_and_read.py

# Or use make
make test-pipeline
```

## Direct Module Usage

You can also use the ingestion and reading modules directly:

### Ingest Prices

```bash
# Ingest price data for test tickers
python -m src.ingest.ingest_prices
```

### Read Data

```bash
# Read and display stored data
python -m src.reader
```

### Test R2 Client

```bash
# Test R2/MinIO connection
python -m src.storage.r2_client
```

### Test EODHD Client

```bash
# Test EODHD API connection
python -m src.ingest.eodhd_client
```

### Test Configuration

```bash
# Display current configuration
python -m src.config
```
