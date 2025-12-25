Got it. Here’s a **simplified spec** with the flat-module layout you want and the new constraints:

* **Only fetch “the last day”** (latest available daily bar, using a small date range like `asof-7…asof` but only **ingest 1 day**)
* Bulk historical ingest is out-of-scope (different service)
* R2 key format: `prices/v1/{ticker}/{YYYY}/{MM}/data.parquet`
* Keep code minimal: `ingest.py eod_client.py r2.py db.py cli.py pipeline.py`

Below is a tight system spec + module responsibilities + minimal interfaces.

---

## Overview

### Daily job behavior (GitHub Actions)

1. Ask `db.py` for the list of tickers to ingest **in priority order**.
2. Enforce a **daily budget** of 20 API calls.
3. For each ticker (up to budget):

   * Fetch latest available daily bar (one row)
   * Write it to R2 Parquet file for that month:

     * `prices/v1/{ticker}/{YYYY}/{MM}/data.parquet`
   * Record ingestion status back to metadata (optional hook)

### Key simplification

Because the R2 path is **monthly file**, appending is not native in object storage. For simplicity, in MVP we do:

* **Read existing month parquet** (if present)
* **Upsert** the day’s row (by `date`)
* **Write back** the full month parquet

This is fine for MVP because:

* It’s at most ~31 rows per ticker per month
* With 20 tickers/day, you rewrite at most 20 small objects/day

---

## Data contract (normalized bar)

**Parquet schema (monthly file rows):**

* `date` (date32)
* `open` (float64)
* `high` (float64)
* `low` (float64)
* `close` (float64)
* `adj_close` (float64, nullable)
* `volume` (int64, nullable)
* `source` (string) = `"eodhd"`
* `ingested_at` (timestamp)

Ticker is implied by path; you can include `ticker` column if you prefer, but not required.

---

## R2 key structure

```
prices/v1/{ticker}/{YYYY}/{MM}/data.parquet
```

Examples:

* `prices/v1/AAPL.US/2025/12/data.parquet`
* `prices/v1/7203.T/2025/12/data.parquet`

Rules:

* `YYYY` is 4-digit year
* `MM` is zero-padded 2-digit month

Idempotency:

* Re-running same day should produce identical month file content (row replaced).

---

## EODHD usage pattern (1 request per ticker)

To reliably get the “latest trading day” without knowing if yesterday was a holiday/weekend:

* Request a small range: `from=asof-7d` to `to=asof` and take the max(date) row.
* Ingest **only that one row**.

This stays **1 API call per ticker**, which is what you need with 20/day.

---

## Minimal module layout

### `eod_client.py`

**Responsibility:** EODHD HTTP calls + retry/backoff + parse into normalized row.

Public API:

```python
class EODHDClient:
    def __init__(self, api_token: str, base_url: str = "https://eodhd.com/api", timeout_s: float = 20.0): ...

    def fetch_latest_daily_bar(self, ticker: str, asof_date: date) -> dict | None:
        """
        Returns a normalized dict with keys: date, open, high, low, close, adj_close, volume
        or None if no data in range.
        """
```

Retry behavior (simple):

* Retry on network errors, 429, 5xx up to `max_retries=3`
* Exponential backoff + jitter
* Respect `Retry-After` if present

### `r2.py`

**Responsibility:** read/write parquet in R2, and monthly upsert.

Public API:

```python
class R2Store:
    def __init__(self, endpoint_url, access_key_id, secret_access_key, bucket, prefix="prices/v1"): ...

    def month_key(self, ticker: str, year: int, month: int) -> str: ...

    def read_month(self, ticker: str, year: int, month: int) -> "pa.Table | None": ...

    def upsert_day_into_month(self, ticker: str, bar: dict, ingested_at: datetime, source="eodhd") -> str:
        """
        Reads existing month parquet (if any), upserts row by date, writes back.
        Returns object key written.
        """
```

Implementation notes:

* Use `pyarrow` + `s3fs`
* Keep table sorted by `date` ascending
* Deduplicate by `date` (last write wins)

### `db.py`

**Responsibility:** *thin* wrapper around your other metadata package. Keep this tiny.

Public API (what pipeline needs):

```python
def list_priority_tickers() -> list[str]:
    """Returns tickers in priority order (alerts/watchlists first)."""

def record_ingest_result(ticker: str, bar_date: date | None, r2_key: str | None, status: str, error: str | None = None) -> None:
    """Optional; can be no-op in MVP."""
```

You said DB will live elsewhere — so here it can just call into that package.

### `pipeline.py`

**Responsibility:** orchestration: budget, iterate tickers, fetch, write, record.

Public API:

```python
def run_daily_ingest(
    run_date: date,
    max_requests: int,
    client: EODHDClient,
    store: R2Store,
) -> dict:
    """
    Returns summary dict: attempted, ingested, skipped_budget, no_data, failures, calls_used
    """
```

Budget logic:

* Calls used increments **when a request is made**
* Stop once `calls_used == max_requests`

Failure handling:

* Continue on per-ticker errors
* If auth error or token invalid (401/403), fail fast (optional)

### `ingest.py`

**Responsibility:** “main entry” function called by CLI; wires config + dependencies.

Public API:

```python
def main(run_date: date | None = None, dry_run: bool = False) -> int:
    """Return process exit code."""
```

### `cli.py`

**Responsibility:** parse args/env, call `ingest.main`.

CLI:

* `python cli.py run [--date YYYY-MM-DD] [--dry-run]`

---

## Daily ingest algorithm (exact)

For each ticker (up to 20):

1. `bar = client.fetch_latest_daily_bar(ticker, asof_date=run_date)`
2. If `bar is None`: record `no_data`, continue
3. If `bar["date"] > run_date`: allow it? (Usually shouldn’t happen; treat as suspicious and skip or accept — pick one. I’d accept if within +1 day due to timezone; otherwise skip.)
4. Write to R2 monthly parquet:

   * key = `store.upsert_day_into_month(ticker, bar, ingested_at=now_utc)`
5. record success with `bar_date` + `key`

---

## Config (simple env vars)

Required:

* `EODHD_API_TOKEN`
* `R2_ENDPOINT_URL`
* `R2_ACCESS_KEY_ID`
* `R2_SECRET_ACCESS_KEY`
* `R2_BUCKET`

Optional:

* `R2_PREFIX` default `prices/v1`
* `MAX_DAILY_REQUESTS` default `20`
* `RUN_TZ` default `UTC` (or `America/New_York`—but simplest is UTC + range query)
* `LOG_LEVEL`

---

## GitHub Actions run (simple)

* Schedule daily (choose time after most markets closed; if you want “global”, run ~06:00 UTC so Asia/Europe/US all have prior day close)
* Step runs:

  * `python cli.py run`

---

## What I would implement for “pull last day”

Because “last day” depends on market calendar, the safest “simple” strategy is:

* call EODHD with `from=run_date-7` and `to=run_date`
* take the max date row and ingest it
  This guarantees you’ll ingest the latest actual trading day with **one call**.

---

If you want, I can now rewrite this as a **single Clause prompt** that generates the actual code files with this simplified structure (and minimal dependencies), tailored to your exact ticker format (e.g. `AAPL.US` vs `AAPL` + exchange).
