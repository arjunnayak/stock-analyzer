Below is a **simple MVP technical spec** (no sharding) for storing daily-batch time-series in **Cloudflare R2**, optimized for **ticker-first access** and low implementation complexity.

---

## MVP R2 Time-Series Storage Spec (Daily Batches, Ticker-First)

### Goals

* Store and retrieve historical time-series by **ticker** efficiently.
* Daily batch ingestion (once per day).
* Keep implementation simple: **predictable prefixes**, **append-friendly**, minimal moving parts.
* Support datasets:

  1. daily prices (5y)
  2. quarterly fundamentals (5y)
  3. daily valuation signals (5y)
  4. daily technical signals (2y)

### Non-goals (MVP)

* Cross-ticker analytics directly from R2
* Advanced partition sharding
* Incremental per-row upserts inside files
* Complex schema evolution

---

## 1) Bucket + Prefix Layout

### Bucket

* `market-data` (or similar)

### Root prefix convention

```
{dataset}/v1/{ticker}/{year}/{month}/{filename}
```

Where:

* `dataset ∈ {prices, fundamentals, signals_valuation, signals_technical}`
* `ticker` = uppercased symbol (e.g. `AAPL`)
* `year` = `YYYY`
* `month` = `MM` (zero-padded)
* `filename` describes date span + format

### Example keys

**Prices**

```
prices/v1/AAPL/2024/01/data.parquet
```

**Valuation signals**

```
signals_valuation/v1/AAPL/2024/01/data.parquet
```

**Technical signals**

```
signals_technical/v1/AAPL/2024/01/data.parquet
```

**Fundamentals (quarterly)**
Option A (keep same structure, quarterly rows inside monthly file by period_end month):

```
fundamentals/v1/AAPL/2024/06/data.parquet
```

Option B (simpler conceptually: one file per year):

```
fundamentals/v1/AAPL/2024/data.parquet
```

**MVP recommendation**

* Daily datasets: **monthly files** (`YYYY/MM/data.parquet`)
* Fundamentals: **one file per ticker** for MVP, or **yearly** if you prefer smaller updates.

---

## 2) File Format

### MVP choice

**Parquet** for all datasets.

Why:

* Smaller than CSV/JSON
* Easy to read/write in Python
* Column projection later if needed

Compression:

* `zstd` if available, else `snappy`

---

## 3) Schema Definitions (Parquet)

### 3.1 `prices` (daily)

Partitioned by month; one row per trading day.

Columns:

* `date` (DATE) — trading date (UTC)
* `open` (FLOAT64)
* `high` (FLOAT64)
* `low` (FLOAT64)
* `close` (FLOAT64)
* `adj_close` (FLOAT64)
* `volume` (INT64)

Constraints:

* Unique by `date` within a ticker.

### 3.2 `signals_valuation` (daily)

Columns:

* `date` (DATE)
* `pe_ttm` (FLOAT64, nullable)
* `pb` (FLOAT64, nullable)
* `ps_ttm` (FLOAT64, nullable)
* `ev_ebitda_ttm` (FLOAT64, nullable)
* `fcf_yield_ttm` (FLOAT64, nullable)
* `earnings_yield_ttm` (FLOAT64, nullable)
* `…` (additional signals as needed; keep MVP ≤ 20 columns)

### 3.3 `signals_technical` (daily)

Columns:

* `date` (DATE)
* `rsi_14` (FLOAT64, nullable)
* `sma_20` (FLOAT64, nullable)
* `sma_50` (FLOAT64, nullable)
* `ema_20` (FLOAT64, nullable)
* `macd` (FLOAT64, nullable)
* `macd_signal` (FLOAT64, nullable)
* `bb_upper` (FLOAT64, nullable)
* `bb_lower` (FLOAT64, nullable)
* `…` (MVP ≤ 30 columns)

### 3.4 `fundamentals` (quarterly)

Row per fiscal quarter.

Columns (MVP subset):

* `period_end` (DATE)
* `fiscal_year` (INT32)
* `fiscal_quarter` (STRING like `Q1..Q4`)
* `revenue` (FLOAT64, nullable)
* `gross_profit` (FLOAT64, nullable)
* `operating_income` (FLOAT64, nullable)
* `net_income` (FLOAT64, nullable)
* `eps_diluted` (FLOAT64, nullable)
* `shares_diluted` (FLOAT64, nullable)
* `total_assets` (FLOAT64, nullable)
* `total_liabilities` (FLOAT64, nullable)
* `cash_and_equivalents` (FLOAT64, nullable)
* `operating_cash_flow` (FLOAT64, nullable)
* `capex` (FLOAT64, nullable)
* `free_cash_flow` (FLOAT64, nullable)

Constraints:

* Unique by `period_end` within a ticker.

---

## 4) Ingestion Strategy (Daily Batch)

### Key decision: immutable monthly rewrites

To keep it simple: **rewrite the current month file per ticker** on every daily batch.

Process per ticker per dataset:

1. Determine “effective date” = batch date (e.g., 2025-12-25).
2. Compute target prefix:

   * `dataset/v1/{ticker}/{YYYY}/{MM}/data.parquet`
3. Download existing monthly file if it exists.
4. Merge new rows (by `date` or `period_end`) with existing rows.

   * De-dupe on key (`date` for daily, `period_end` for fundamentals).
   * Sort by key ascending.
5. Write parquet locally.
6. Upload to same key (overwrite).

Why this is MVP-friendly:

* No need for object versioning / delta logs
* Simple read model (one file per month)
* Backfills are easy: just rewrite the month(s) affected

Performance note:

* This is fine for MVP. The month file for one ticker is small (tens of rows).

### Parallelism

* Run per ticker in parallel with a bounded worker pool (e.g., 16–64), to avoid overwhelming R2 and your compute.

---

## 5) Read API Contract (Backend)

Provide a minimal internal library used by API endpoints.

### Function: `get_timeseries(ticker, dataset, start_date, end_date) -> DataFrame/JSON`

Behavior:

1. Normalize ticker uppercase.
2. Determine months between `start_date..end_date` inclusive.
3. For each month:

   * Construct key: `dataset/v1/{ticker}/{YYYY}/{MM}/data.parquet`
   * GET if exists, skip if missing.
4. Concatenate, filter to date range, sort.
5. Return.

### Fundamentals

If you choose “single file per ticker”:

* key: `fundamentals/v1/{ticker}/data.parquet`
* Just GET once and filter by `period_end`.

---

## 6) Metadata & “What exists” (Optional but useful)

For MVP, skip manifests.

If you want one small helper:

* store a simple JSON after each successful batch:

```
_meta/v1/{dataset}/{ticker}.json
```

Contents:

* `last_updated_at` (ISO timestamp)
* `min_date`, `max_date`
* `row_count`
* `months_present`: ["2024-01", "2024-02", ...]

This is optional; do it only if listing becomes annoying.

---

## 7) Backfills & Corrections

Backfill strategy:

* Identify affected date range.
* Re-run ingestion for affected tickers/datasets and rewrite the impacted months.

No special handling needed beyond “rewrite month file”.

---

## 8) Error Handling & Idempotency

* All ingestion steps should be **idempotent**:

  * Running the batch twice yields the same file (dedupe + sort).
* On upload failure:

  * retry with exponential backoff (e.g., 3–5 retries)
* Log per ticker/dataset:

  * success, rows added, rows updated, final row count

---

## 9) Implementation Checklist for Coding Agent

### Setup

* R2 credentials in env vars:

  * `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET`
* Use S3-compatible SDK (AWS SDK / boto3 / aws-sdk-js)

### Core modules

1. `r2_client.py|ts`

   * `get_object(key)`, `put_object(key, bytes)`, `head_object(key)`
2. `keys.py|ts`

   * `build_key(dataset, ticker, date)` → monthly path
   * `build_key_range(dataset, ticker, start_date, end_date)` → list of month keys
3. `parquet_io.py|ts`

   * `read_parquet(bytes) -> df`
   * `write_parquet(df) -> bytes`
4. `merge.py|ts`

   * `merge_dedupe_sort(existing_df, new_df, key_col)`
5. `ingest_daily_batch.py|ts`

   * loops tickers × datasets
   * bounded parallelism
   * overwrite monthly files

### Acceptance criteria

* Can ingest one day for 6,000 tickers for:

  * prices + signals_valuation + signals_technical (optionally fundamentals separately)
* Can read back any ticker range quickly using month-key construction (no LIST required)
* Re-running the same batch produces identical outputs (same row counts, no dupes)

---

If you tell me your preferred language/runtime for the agent (**Python vs Node**) I’ll translate this into a “task breakdown + file skeleton + pseudocode” that a coding agent can implement directly.
