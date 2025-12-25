# MVP Technical Architecture (Validation Phase)

## 1. Goals & Constraints

**Primary goal:**
Validate the product idea cheaply while supporting real daily batch computation and low‑latency reads.

**Constraints:**

* Optimize for **low cost / free tiers**
* Prefer **serverless / minimal ops**
* Accept some operational rough edges (cron, retries) during validation
* Architecture should be **easy to evolve** into a more robust system if traction appears

---

## 2. High‑Level Architecture

The system is intentionally split into **two planes**:

1. **Read / API Plane (latency‑sensitive, I/O‑heavy)**
2. **Batch / Compute Plane (throughput‑oriented, long‑running allowed)**

### Summary

* **API & orchestration:** Cloudflare Workers
* **Time‑series storage:** Cloudflare R2
* **Metadata & user data:** Supabase (Postgres)
* **Batch processing:** GitHub Actions (cron‑based)
* **Derived outputs:** Written back to R2 (and selectively to Supabase)

This keeps the API extremely cheap while pushing all expensive compute into a once‑daily job that runs on free or near‑free infrastructure.

---

## 3. Data Model & Storage

### 3.1 Cloudflare R2 (Primary Data Store)

**Used for:**

* Raw time‑series data
* Derived daily aggregates / signals

**Why R2:**

* Zero egress fees (critical for Workers)
* Cheap object storage
* Simple read model

**Recommended layout:**

```
r2://timeseries/
  └── {entity_id}/
      ├── raw/
      │   ├── 2025-01.json.gz
      │   ├── 2025-02.json.gz
      ├── derived/
      │   ├── daily_signals.json
      │   ├── rolling_metrics.json
```

**Notes:**

* Partition by **entity + time window** to keep reads small
* Use **gzipped JSON** for MVP simplicity
* Avoid large multi‑year single files

---

### 3.2 Supabase (Postgres)

**Used for:**

* User accounts & auth
* Watchlists / tracked entities
* Static metadata (entity info, configs)
* Optional: small, queryable summary tables

**Not used for:**

* Large time‑series scans
* Heavy analytical joins

**Example tables:**

* `users`
* `entities`
* `watchlists`
* `user_entity_settings`

---

## 4. API Layer (Cloudflare Workers)

### 4.1 Responsibilities

Workers are **read‑optimized** and intentionally thin.

They:

* Authenticate users (Supabase JWT)
* Fetch metadata from Supabase
* Fetch time‑series or derived outputs from R2
* Perform **light transformations only**
* Cache common responses aggressively

They **do not**:

* Run heavy computations
* Scan large time ranges
* Perform batch jobs

---

### 4.2 Example Endpoints

* `GET /entities` → metadata from Supabase
* `GET /entities/{id}/summary` → derived data from R2
* `GET /entities/{id}/timeseries?window=30d`
* `GET /watchlist`

**Typical request flow:**

1. Validate auth token
2. Fetch small metadata row from Supabase
3. Fetch pre‑computed JSON from R2
4. Slice / shape response
5. Return within milliseconds

---

### 4.3 Caching Strategy

* Use Cloudflare cache for public or semi‑public data
* Cache derived entity summaries aggressively
* Bypass cache for user‑specific endpoints

---

## 5. Batch Processing Plane (GitHub Actions)

### 5.1 Why GitHub Actions for MVP

* Free or extremely cheap at low volume
* Built‑in cron scheduling
* No always‑on infrastructure
* Easy iteration during validation

This is **not** a forever solution, but ideal for MVP validation.

---

### 5.2 Batch Job Responsibilities

Runs once per day (or a few times per day):

1. Enumerate active entities
2. Pull required raw time‑series from R2
3. Pull metadata/config from Supabase
4. Compute derived outputs:

   * aggregates
   * rolling windows
   * signals / indicators
5. Write results back to R2
6. Optionally write small summary rows to Supabase

---

### 5.3 Batch Job Structure

```
batch/
  ├── main.py
  ├── loaders/
  │   ├── r2_loader.py
  │   ├── supabase_loader.py
  ├── compute/
  │   ├── indicators.py
  │   ├── aggregations.py
  ├── writers/
  │   ├── r2_writer.py
  │   ├── supabase_writer.py
```

**Important rules:**

* Batch jobs may take minutes
* Failures should be logged, not crash the entire pipeline
* Partial results are acceptable during validation

---

### 5.4 Scheduling

* GitHub Actions cron trigger (e.g. once nightly)
* Manual trigger supported for debugging

---

## 6. Security & Secrets

* Supabase keys stored as GitHub Actions secrets
* R2 credentials stored as secrets
* Workers access R2 via Cloudflare bindings
* No secrets committed to repo

---

## 7. Failure Modes & Tradeoffs (Accepted for MVP)

Explicitly accepted during validation:

* No strong guarantees on batch completion time
* Limited retries
* No exactly‑once processing
* Basic logging only

The goal is **signal > perfection**.

---

## 8. Evolution Path (Post‑Validation)

If validation succeeds, migrate batch plane to:

* Option A: Fly.io / Render / Railway worker service
* Option B: Cloudflare Cron + Queues for partitioned workloads

No changes required to:

* R2 layout
* API endpoints
* Client applications

---

## 9. Key Architectural Principles (For Coding Agent)

* **Workers must stay fast and thin**
* **All heavy compute lives in batch**
* **R2 is the source of truth for time‑series**
* **Supabase is metadata, not analytics**
* Prefer simplicity over premature robustness

---

## 10. Open Questions (Deferred)

* Real‑time updates vs daily batch
* Fine‑grained alerting
* User‑defined indicators
* Streaming ingestion

These are intentionally **out of scope** for MVP.
