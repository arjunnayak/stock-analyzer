# Material Changes Stock Analyzer - Architecture Documentation

## 1. System Overview

**Product Vision**: Automated stock analysis system that detects material changes in stock valuations and trends, delivering actionable email alerts to investors.

**Core Capabilities**:
- Daily price and fundamental data ingestion
- Incremental technical indicator computation (EMA 200, EMA 50)
- Valuation metric calculation (EV/EBITDA with point-in-time fundamentals)
- Template-based signal evaluation (10 hardcoded templates)
- Email alert delivery via SMTP
- Historical valuation percentile tracking

**User Flow**:
1. User adds stocks to watchlist (via Cloudflare Worker API or database)
2. Daily pipeline ingests prices and computes features
3. Templates evaluate features against predefined conditions
4. Triggers generate email alerts for material changes
5. Users receive structured emails with actionable insights

---

## 1.1 Python Execution Convention

**⚠️ CRITICAL: Always use `uv run python` for Python execution**

This project uses [uv](https://github.com/astral-sh/uv) for dependency management and virtual environment handling.

**DO:**
```bash
uv run python scripts/ingest_prices.py
uv run python -m src.features.pipeline_daily
uv run python tests/test_templates.py
```

**DON'T:**
```bash
python scripts/ingest_prices.py  # ❌ Wrong - won't use correct dependencies
python -m src.features.pipeline_daily  # ❌ Wrong - may use wrong environment
pytest tests/  # ❌ Wrong - use uv run python instead
```

**Why?**
- `uv run` ensures correct virtual environment and dependencies
- Avoids "module not found" errors
- Consistent behavior across local and CI environments
- Automatic dependency installation if needed

**Exception:** GitHub Actions workflows already run in the correct environment, so they use `uv run python` directly in workflow YAML files.

---

## 2. Architecture Diagrams

### 2.1 Data Flow Architecture

```
┌─────────────────┐
│  EODHD API      │ (Price & Fundamental Data; large historical date ranges use dolt db for cost efficiency)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions - Daily Pipeline (11 PM UTC)             │
│  .github/workflows/daily-pipeline.yml                    │
├─────────────────────────────────────────────────────────┤
│  Step 1: Ingest Prices                                   │
│    scripts/ingest_prices.py                              │
│    → writes to: prices_ingestion/v1/{date}/{ticker}.parquet
│                                                           │
│  Step 2: Compute Features                                │
│    src/features/pipeline_daily.py                        │
│    → reads: prices_ingestion, fundamentals_quarterly     │
│    → computes: EMA 200, EMA 50, EV/EBITDA               │
│    → writes to: features_daily/v1/{date}/data.parquet   │
│    → updates: indicator_state table (Supabase)          │
│                                                           │
│  Step 3: Evaluate Templates                              │
│    src/features/templates.py                             │
│    → reads: features_daily, valuation_stats             │
│    → evaluates: 10 templates (T1-T10)                   │
│    → writes to: triggers/v1/{date}/data.parquet         │
│                                                           │
│  Step 4: Send Alerts                                     │
│    src/features/alert_notifications.py                   │
│    → reads: triggers, user watchlists                   │
│    → generates: Alert objects (src/email/alerts.py)     │
│    → sends: emails via SMTP                             │
│    → logs: alert_history table (Supabase)               │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Storage Layer                                          │
│                                                         │
│  R2 (Cloudflare)              Supabase (PostgreSQL)     │
│  ├─ prices/                    ├─ users                 │
│  ├─ prices_snapshots/          ├─ entities              │
│  ├─ features/                  ├─ watchlists            │
│  ├─ triggers/                  ├─ indicator_state       │
│  ├─ fundamentals/              ├─ valuation_stats       │
│                                ├─ backfill_queue        │
│                                └─ alert_history         │
└─────────────────────────────────────────────────────────┘
```

**Template Data Dependencies** (Minimal Requirements):

```
TEMPLATES (10 total)
    │
    ├── T1-T4 (Pure Technical)
    │     └─→ features_daily → prices (200 days)
    │         - close, ema_200, ema_50, prev_close, prev_ema_200
    │         - NO fundamentals required
    │
    ├── T5-T6 (Technical + Valuation)
    │     └─→ features_daily → prices (200 days) + fundamentals (4 qtrs)
    │         - close, ema_200, ema_50, ev_ebitda
    │         - Fundamentals: shares_outstanding, total_debt, cash, ebitda_ttm
    │
    └── T7-T10 (Historical Stats)
          └─→ valuation_stats → features history (5 years)
              - ev_ebitda, ev_ebitda_p20, ev_ebitda_p50, ev_ebitda_p80
              - Requires weekly stats pipeline to have run
```

**Key Insight**: Templates have cascading data requirements:
- **Basic Testing**: 200 days + 4 quarters = T1-T6 work (6/10 templates)
- **Full Testing**: 5 years data + weekly stats = T1-T10 work (all templates)

### 2.2 Storage Architecture

**R2 Bucket Organization** (Parquet files):
- `prices/v1/{ticker}/{YYYY}/{MM}/data.parquet` - Raw EODHD daily prices
- `prices_snapshot/v1/date={YYYY-MM-DD}/close.parquet` - Cross-sectional price snapshot
- `features/v1/date={YYYY-MM-DD}/part-XXX.parquet` - Wide-row features (all tickers, all features)
- `alerts_eval/v1/date=YYYY-MM-DD/triggers.parquet` - Template evaluation results
- `fundamentals/v1/{ticker}/{YYYY}/{MM}/data.parquet` - Quarterly & annual financial statements

**Supabase Tables** (PostgreSQL):
- `users` - User accounts, email preferences, onboarding status
- `entities` - Stock metadata (ticker, name, exchange, type)
- `watchlists` - User-stock associations
- `indicator_state` - Incremental EMA computation state (prev_value, prev_date)
- `valuation_stats` - Historical percentiles for EV/EBITDA (p10, p20, p50, p80, p90)
- `backfill_queue` - Asynchronous fundamental data backfill tasks
- `alert_history` - Delivered alerts with engagement tracking (sent_at, opened_at)

---

## 3. Active Pipelines

### 3.1 Daily Pipeline (11 PM UTC / 6 PM ET)

**Workflow file**: `.github/workflows/daily-pipeline.yml`

**Trigger**: Cron schedule `0 23 * * *` (daily at 11 PM UTC)

**Steps**:

1. **Ingest Latest Prices** (`scripts/ingest_prices.py`)
   - Fetches EOD prices from EODHD API for all watchlist tickers
   - Writes to `prices/v1/{ticker}/{YYYY}/{MM}/data.parquet`
   - Default: last 7 days to handle missing data

2. **Compute Daily Features** (`src/features/pipeline_daily.py`)
   - **Input**: Prices ingestion, fundamentals quarterly, indicator_state
   - **Processing**:
     - Creates cross-sectional price snapshot
     - Computes EMA 200 incrementally (using stored state)
     - Computes EMA 50 incrementally (using stored state)
     - Joins point-in-time fundamentals for valuation
     - Computes EV/EBITDA = (market_cap + total_debt - cash) / ebitda_ttm
   - **Output**: `features/v1/date={YYYY-MM-DD}/part-XXX.parquet` (wide-row format)
   - **State Update**: Upserts `indicator_state` table with latest EMA values

3. **Evaluate Templates** (`src/features/templates.py`)
   - **Input**: Latest features, valuation_stats table
   - **Processing**: Evaluates 10 hardcoded templates (T1-T10)
   - **Output**: `alerts_eval/v1/date=YYYY-MM-DD/triggers.parquet`
   - **Columns**: date, ticker, template_id, template_name, trigger_strength, reasons_json

4. **Send Alert Notifications** (`src/features/alert_notifications.py`)
   - **Input**: Triggers parquet, user watchlists
   - **Processing**:
     - Converts triggers to Alert objects (src/email/alerts.py)
     - Renders email HTML/text (src/email/templates.py)
     - Sends via SMTP (src/email/sender.py)
     - Logs to alert_history table
   - **Output**: Email delivery + database log

**Manual Trigger Options**:
- `tickers`: Specific tickers (space-separated)
- `skip_ingestion`: Use existing price data
- `skip_features`: Skip feature computation
- `skip_templates`: Skip template evaluation
- `run_date`: Override run date (YYYY-MM-DD)

### 3.2 Weekly Pipeline (Sunday 2 AM ET)

**Workflow file**: `.github/workflows/weekly-stats.yml`

**Trigger**: Cron schedule `0 7 * * 0` (Sunday at 2 AM ET)

**Steps**:

1. **Compute Valuation Percentiles** (`src/features/pipeline_weekly_stats.py`)
   - **Input**: Historical features_daily parquet files (5 years)
   - **Processing**:
     - Aggregates EV/EBITDA for each ticker over 1260 days (~5 years)
     - Computes percentiles: p10, p20, p50, p80, p90
     - Identifies historical cheap/expensive zones
   - **Output**: Upserts `valuation_stats` table in Supabase
   - **Usage**: Required by templates T7-T10 for historical context

### 3.3 Backfill Pipeline (On-Demand)

**Workflow file**: `.github/workflows/daily-backfill.yml`

**Trigger**: Manual dispatch or cron

**Steps**:

1. **Process Backfill Queue** (`scripts/process_backfill_queue.py`)
   - **Input**: `backfill_queue` table (pending tasks)
   - **Processing**: Fetches fundamental data for queued tickers
   - **Output**: Writes to `fundamentals_quarterly`, updates queue status

---

## 4. Code Organization

### 4.1 Active Modules (Production)

**src/features/** - Feature computation and template evaluation (ACTIVE)
- `pipeline_daily.py` - Daily pipeline orchestrator (DailyPipeline class)
- `features_compute.py` - EMA and valuation computation (FeaturesComputer class)
- `templates.py` - 10 hardcoded signal templates (T1-T10)
- `alert_notifications.py` - Alert delivery orchestration (AlertNotifier class)
- `pipeline_weekly_stats.py` - Weekly percentile computation

**src/email/** - Alert delivery system
- `alerts.py` - Alert dataclass with email formatting
- `delivery.py` - Email delivery with logging (EmailDeliveryService class)
- `templates.py` - HTML/text email rendering (EmailTemplates class)
- `sender.py` - SMTP sending (EmailSender class)

**src/storage/** - Data persistence clients
- `r2_client.py` - Cloudflare R2 object storage (R2Client class)
- `supabase_db.py` - PostgreSQL database client (SupabaseDB class)

**src/ingest/** - Data ingestion
- `prices.py` - EODHD price ingestion (PriceIngestion class)
- `fundamentals.py` - Financial statement ingestion (FundamentalsIngestion class)
- `eodhd_client.py` - EODHD API wrapper

**scripts/** - CLI tools and automation
- `ingest_prices.py` - Price ingestion CLI (used by daily-pipeline.yml)
- `process_backfill_queue.py` - Backfill queue processor
- `verify_data_availability.py` - Data completeness checker

**src/config.py** - Environment configuration (ENV=LOCAL vs ENV=REMOTE)

### 4.2 Worker (Cloudflare Python Worker)

**worker/src/** - HTTP API for frontend
- `index.py` - Request routing with direct Supabase queries
- `supabase_client.py` - Async Supabase client for Workers

**Endpoints**:
- `GET /api/user/:userId/settings` - User settings
- `PATCH /api/user/:userId/settings` - Update settings
- `GET /api/watchlist/:userId` - User's watchlist
- `POST /api/watchlist/:userId` - Add stock to watchlist
- `DELETE /api/watchlist/:userId/:ticker` - Remove stock
- `GET /api/entities/search?q=query` - Stock search
- `GET /api/entities/:ticker` - Stock details
- `GET /api/entities/popular` - Popular stocks
- `GET /api/alerts/:userId` - Alert history
- `POST /api/alerts/:alertId/opened` - Mark alert as opened
- `GET /api/alerts/:userId/stats` - Alert statistics
- `GET /api/health` - Health check

**Note**: Worker uses inline database queries, not a service layer. All business logic is in the request handlers.

### 4.3 Shared Utilities

**src/reader.py** - TimeSeriesReader for efficient R2 data access

---

## 5. Data Models

### 5.1 R2 Parquet Schemas

**features_daily/v1/{date}/data.parquet** (Wide-row format):
```
ticker: str
date: date
close: float
market_cap: float
ema_200: float
ema_50: float
ev_ebitda: float
```

**triggers/v1/{date}/data.parquet**:
```
date: date
ticker: str
template_id: str  # T1-T10
template_name: str
trigger_strength: float  # 0.0-1.0
reasons_json: str  # JSON array of reasons
```

### 5.2 Supabase Table Schemas

**indicator_state** (Incremental EMA computation):
```sql
CREATE TABLE indicator_state (
  ticker TEXT,
  indicator_name TEXT,  -- 'ema_200', 'ema_50'
  prev_value NUMERIC,
  prev_date DATE,
  last_updated TIMESTAMPTZ,
  PRIMARY KEY (ticker, indicator_name)
);
```

**valuation_stats** (Historical percentiles):
```sql
CREATE TABLE valuation_stats (
  ticker TEXT PRIMARY KEY,
  metric TEXT,  -- 'ev_ebitda'
  window_days INTEGER,  -- 1260 (~5 years)
  p10 NUMERIC,
  p20 NUMERIC,
  p50 NUMERIC,
  p80 NUMERIC,
  p90 NUMERIC,
  computed_at TIMESTAMPTZ
);
```

**alert_history** (Delivered alerts):
```sql
CREATE TABLE alert_history (
  id UUID PRIMARY KEY,
  user_id UUID,
  entity_id UUID,
  ticker TEXT,
  alert_type TEXT,  -- 'valuation_regime_change', 'trend_break'
  headline TEXT,
  what_changed TEXT,
  why_it_matters TEXT,
  before_vs_now TEXT,
  what_didnt_change TEXT,
  data_snapshot JSONB,
  sent_at TIMESTAMPTZ,
  opened_at TIMESTAMPTZ  -- NULL until user opens
);
```

### 5.3 Table Purpose Quick Reference

**TL;DR**: Only `valuation_stats` is truly required (for T7-T10). Everything else is performance optimization.

#### Required vs Optional Tables

| Table | Status | Purpose | Can Skip? |
|-------|--------|---------|-----------|
| **valuation_stats** | Required for T7-T10 | 5-year EV/EBITDA percentiles | ✅ Yes (T7-T10 won't work) |
| **indicator_state** | Performance cache | Stores last EMA values | ✅ Yes (slower, computes from scratch) |
| **fundamentals_latest** | Performance cache | Cached TTM fundamentals | ⚠️ Maybe (need to read from R2 instead) |
| **users** | User management | User accounts | ✅ Yes (for testing) |
| **entities** | Stock metadata | Ticker info | ⚠️ Needed for watchlist |
| **watchlists** | User management | User stocks | ✅ Yes (for testing) |
| **alert_history** | Logging | Sent alerts log | ✅ Yes (for testing) |

#### What Happens Without Each Table

**Without `valuation_stats`**:
- Templates T7-T10 will be skipped (missing required stats)
- Templates T1-T6 work normally
- Daily pipeline runs fine

**Without `indicator_state`**:
- EMA computed from scratch each time (200 days of calculations)
- Daily pipeline ~2-3x slower
- Results identical, just takes longer

**Without `fundamentals_latest`**:
- Must read quarterly data from R2 parquet each time
- Must compute TTM from 4 quarters each time
- Daily pipeline ~1.5x slower
- Requires code change to fallback to R2 (currently expects this table)

**Mental Model**: Think of Supabase tables as caches. The "source of truth" is R2 parquet files.

---

## 6. Features Computation Details

### 6.1 Technical Indicators

**EMA 200 (Exponential Moving Average)**:
- **Formula**: `EMA_t = α * Price_t + (1 - α) * EMA_(t-1)` where `α = 2/(200+1)`
- **Implementation**: Incremental using `indicator_state` table (src/features/features_compute.py:120-180)
- **State Storage**: `(ticker, 'ema_200', prev_value, prev_date)` in indicator_state table
- **Cold Start**: Uses simple moving average for first 200 days

**EMA 50 (Exponential Moving Average)**:
- **Formula**: `EMA_t = α * Price_t + (1 - α) * EMA_(t-1)` where `α = 2/(50+1)`
- **Implementation**: Incremental using `indicator_state` table
- **State Storage**: `(ticker, 'ema_50', prev_value, prev_date)` in indicator_state table

### 6.2 Valuation Metrics

**EV/EBITDA** (Enterprise Value to EBITDA):
- **Formula**:
  ```
  enterprise_value = market_cap + total_debt - cash_and_equivalents
  ev_ebitda = enterprise_value / ebitda_ttm
  ```
- **Implementation**: src/features/features_compute.py:_compute_valuation_series()
- **Point-in-Time Join**: Uses quarterly fundamentals with proper time alignment
- **TTM Calculation**: Rolling 4-quarter sum of EBITDA (filters out annual 'Year' rows)
- **Balance Sheet Data**: Fetches latest balance sheet for total_debt and cash

**Data Sources**:
- `market_cap`: From daily price data (close * shares_outstanding)
- `total_debt`: From balance sheet (fundamentals_quarterly)
- `cash_and_equivalents`: From balance sheet
- `ebitda_ttm`: Trailing twelve months from income statement (fundamentals_quarterly)

### 6.3 State Management

**Incremental EMA Computation**:
1. Read previous EMA value and date from `indicator_state` table
2. Fetch new prices since prev_date
3. Compute EMA incrementally for each new day
4. Upsert final EMA value back to indicator_state
5. **Benefit**: Avoids reprocessing entire price history daily

**Missing Data Handling**:
- If price data gaps exist, EMA computation skips those days
- State date advances only for days with valid prices
- Invalid/null prices are filtered out before computation

---

## 7. Template System

### 7.1 Template Types

**Basic Templates** (T1-T6): Only require features_daily data
- T1: Bullish 200 MA Cross
- T2: Bearish 200 MA Cross
- T3: Pullback to 50 MA (in uptrend)
- T4: Extended above trend
- T5: Value + Momentum combo
- T6: Expensive + Extended

**Stats Templates** (T7-T10): Require valuation_stats table
- T7: Historically cheap (EV/EBITDA < p20)
- T8: Historically expensive (EV/EBITDA > p80)
- T9: Fair value (near p50)
- T10: Regime change (crossing percentile thresholds)

### 7.2 Template Evaluation Logic

**File**: `src/features/templates.py`

**Function**: `evaluate_all_templates(features_df, templates)`

**Process**:
1. For each template, call template['evaluate_fn'](features_df)
2. Function returns DataFrame with columns: ticker, trigger_strength, reasons_json
3. Filter out rows with trigger_strength = 0.0 (no trigger)
4. Aggregate all triggers into single DataFrame
5. Write to `triggers/v1/{date}/data.parquet`

**Example Template (T1 - Bullish 200 MA Cross)**:
```python
def evaluate_T1_bullish_cross(df):
    # Price crossed above EMA 200
    mask = (df['close'] > df['ema_200']) & (df['ema_50'] > df['ema_200'])
    triggers = df[mask].copy()
    triggers['template_id'] = 'T1'
    triggers['template_name'] = 'Bullish 200 MA Cross'
    triggers['trigger_strength'] = 1.0
    triggers['reasons_json'] = json.dumps([
        "Price crossed above 200-day MA",
        "50-day MA also above 200-day MA (uptrend confirmation)"
    ])
    return triggers[['ticker', 'trigger_strength', 'reasons_json']]
```

### 7.3 Trigger Strength Calculation

**Scale**: 0.0 (no trigger) to 1.0 (strongest trigger)

**Interpretation**:
- `0.0`: Condition not met
- `0.1-0.3`: Weak signal (informational)
- `0.4-0.6`: Moderate signal (watchlist)
- `0.7-0.9`: Strong signal (actionable)
- `1.0`: Critical signal (high conviction)

**Current Implementation**: Most templates use binary triggering (0.0 or 1.0)
**Future**: Could add weighted scoring based on multiple conditions

---

## 8. Email Delivery Flow

### 8.1 Alert Generation Pipeline

**File**: `src/features/alert_notifications.py`

**Steps**:

1. **Load Triggers**: Read latest triggers parquet from R2
2. **Filter by Watchlist**: Join triggers with user watchlists
3. **Convert to Alerts**: Use TemplateAlertAdapter to convert triggers to Alert objects
4. **Render Email**: EmailTemplates.render_html() and render_text()
5. **Send via SMTP**: EmailSender.send_email()
6. **Log Delivery**: Write to alert_history table

**Class**: `AlertNotifier.send_alerts_for_triggers(run_date)`

### 8.2 Alert Dataclass Structure

**File**: `src/email/alerts.py`

```python
@dataclass
class Alert:
    ticker: str
    alert_type: str  # 'valuation_regime_change', 'trend_break', etc.
    headline: str
    what_changed: str  # Factual description
    why_it_matters: str  # Investment implication
    before_vs_now: str  # Quantitative comparison
    what_didnt_change: str  # Context and caveats
    timestamp: datetime
    data_snapshot: dict  # Raw data for reference
```

**Methods**:
- `to_dict()`: Serialize for database storage
- `format_email()`: Plain text email formatting

### 8.3 Template-to-Alert Adapter Pattern

**File**: `src/features/alert_notifications.py`

**Class**: `TemplateAlertAdapter`

**Purpose**: Convert template triggers (structured tabular data) into Alert objects (rich narrative format)

**Metadata Mapping**:
```python
TEMPLATE_METADATA = {
    "T1": {
        "headline": "Bullish trend entry — crossed above 200-day MA",
        "why_matters": "Major trend shifts can signal momentum...",
        "what_didnt_change": "This is technical, not fundamental..."
    },
    # ... T2-T10
}
```

**Process**:
1. Read trigger row (ticker, template_id, trigger_strength, reasons_json)
2. Lookup template metadata
3. Parse reasons_json for what_changed
4. Fetch current features for before_vs_now comparison
5. Construct Alert object
6. Return Alert

---

## 9. Development Workflow

### 9.1 Local Setup

**Environment Variables**:
```bash
ENV=LOCAL  # or ENV=REMOTE for production

# Local (Docker Compose)
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=<local-key>
R2_ENDPOINT_URL=http://127.0.0.1:9000  # MinIO
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin

# Remote (Production)
SUPABASE_URL=<production-url>
SUPABASE_SERVICE_ROLE_KEY=<secret>
R2_ENDPOINT_URL=<cloudflare-r2-url>
AWS_ACCESS_KEY_ID=<r2-key>
AWS_SECRET_ACCESS_KEY=<r2-secret>
```

**Docker Compose Services**:
- Supabase (PostgreSQL, Auth, Storage)
- MinIO (S3-compatible local R2)

**Start Local Stack**:
```bash
docker-compose up -d
ENV=LOCAL uv run python scripts/ingest_prices.py --tickers AAPL MSFT --days 7
ENV=LOCAL uv run python -m src.features.pipeline_daily --run-date 2025-12-30
```

### 9.2 Testing

**Unit Tests**:
```bash
uv run python tests/test_valuation_regime.py  # Valuation computation
uv run python tests/test_templates.py  # Template evaluation
uv run python tests/test_features_backfill.py  # Feature backfill
uv run python tests/test_email_delivery.py  # Email sending
```

**Integration Tests** (with mock data):
```bash
ENV=LOCAL uv run python -m src.features.pipeline_daily --dry-run
```

**Manual Testing**:
```bash
# Test alert generation
uv run python src/email/alerts.py  # Runs __main__ block with sample alerts
```

### 9.3 Deployment

**GitHub Actions**:
- Workflows trigger on schedule or manual dispatch
- Secrets managed in GitHub repository settings
- Logs uploaded as artifacts

**Cloudflare Worker**:
```bash
cd worker
npx wrangler deploy
```

**Secrets**:
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_BUCKET_NAME`
- `EODHD_API_KEY`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `ALERT_EMAIL`

### 9.4 Minimal Testing Setup

**TL;DR**: You only need 200 days of price data + 4 quarters fundamentals to test most templates.

#### Quick Start: Test One Ticker (5 minutes)

**Goal**: Get templates T1-T6 working with minimal data

**Step 1: Ingest 200 days of prices**
```bash
uv run python scripts/ingest_prices.py --ticker AAPL --days 400  # Extra buffer
```

**Step 2: Ingest 5 quarters of fundamentals (for safety)**
```bash
uv run python scripts/backfill_fundamentals.py --ticker AAPL --quarters 5
```

**Step 3: Run daily pipeline (will auto-populate tables)**
```bash
uv run python -m src.features.pipeline_daily \
  --run-date 2025-12-30 \
  --tickers AAPL \
  --skip-templates  # Compute features only
```

**Step 4: Evaluate templates**
```bash
uv run python -m src.features.pipeline_daily \
  --run-date 2025-12-30 \
  --skip-features  # Evaluate templates only
```

**What just happened**:
- Features computation auto-populated `indicator_state` table
- Features computation auto-populated `fundamentals_latest` from R2
- Templates T1-T6 will work (no stats needed)
- Templates T7-T10 will be skipped (need valuation_stats)

#### Two-Tier Testing Approach

**Tier 1: Basic Templates (T1-T6) - Fast**
- **Data needed**: 200 days prices + 4 quarters fundamentals
- **Time to set up**: ~5 minutes
- **Templates that work**: T1 (Bullish 200 MA), T2 (Bearish 200 MA), T3 (Pullback), T4 (Extended), T5 (Value+Momentum), T6 (Expensive+Extended)
- **Templates that skip**: T7-T10 (need historical stats)

**Tier 2: All Templates (T1-T10) - Comprehensive**
- **Data needed**: 5 years prices + 5 years fundamentals
- **Time to set up**: ~30 minutes
- **Additional step**: Run weekly stats once
  ```bash
  uv run python -m src.features.pipeline_weekly_stats
  ```
- **Templates that work**: All T1-T10

#### Data Completeness Verification

Check what data you have:

```bash
# Check price data
uv run python scripts/verify_data_availability.py --ticker AAPL

# Check fundamentals in R2
AWS_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY \
  aws s3 ls s3://$R2_BUCKET_NAME/fundamentals_quarterly/v1/AAPL/ --endpoint-url $R2_ENDPOINT_URL

# Check Supabase tables
psql $DATABASE_URL -c "SELECT * FROM indicator_state WHERE ticker = 'AAPL'"
psql $DATABASE_URL -c "SELECT * FROM valuation_stats WHERE ticker = 'AAPL'"
psql $DATABASE_URL -c "SELECT * FROM fundamentals_latest WHERE ticker = 'AAPL'"
```

#### Minimal Data Requirements by Template

| Template | Price Data | Fundamentals | indicator_state | valuation_stats | fundamentals_latest |
|----------|-----------|--------------|-----------------|-----------------|---------------------|
| T1-T4 (Technical) | 200 days | Not needed | Optional* | Not needed | Not needed |
| T5-T6 (Tech+Val) | 200 days | 4 quarters | Optional* | Not needed | Auto-populated** |
| T7-T10 (Historical) | 5 years | 5 years | Optional* | **Required** | Auto-populated** |

\* Optional = Performance optimization (faster if present, works without)
\*\* Auto-populated = Computed automatically during features pipeline

---

## 10. Migration History

### 10.1 Legacy Architecture (Deprecated - Removed Jan 2026)

**src/signals/** (Removed):
- **Old Approach**: Batch computation of technical and valuation signals
- **Architecture**: OOP classes (TechnicalSignals, ValuationSignals, MetricsComputer)
- **Storage**: Separate datasets (signals_technical, signals_valuation)
- **Partitioning**: By ticker/year/month
- **Problem**:
  - No state management (recomputed entire history)
  - Narrow data format (one metric per file)
  - Not used by daily pipeline

**src/services/** (Removed):
- **Purpose**: Business logic services for Cloudflare Worker API
- **Files**: UserService, WatchlistService, EntitiesService, AlertsService
- **Problem**: Never integrated with worker, zero imports found
- **Worker Reality**: Uses inline Supabase queries instead

**scripts/legacy/** (Archived):
- `backfill_uber.py` - Legacy backfill script
- `compute_metrics.py` - CLI tool for old signals system
- `test_signals.py` - Test scripts for deprecated code
- `test_mock_pipeline.py` - Mock pipeline tests

### 10.2 Current Architecture (Active - Jan 2026)

**src/features/** (Active):
- **New Approach**: Incremental daily computation with wide-row snapshots
- **Architecture**: Functional/procedural with FeaturesComputer class
- **Storage**: Unified dataset (features_daily) with all features per row
- **Partitioning**: By date (cross-sectional)
- **State**: indicator_state table for incremental EMA computation
- **Advantages**:
  - Efficient incremental updates
  - Wide-row format for easy template evaluation
  - Clean separation of concerns (compute → evaluate → alert)

**Template System**:
- **Old**: Code-based in pipeline.py with hardcoded logic
- **New**: Declarative templates.py with metadata-driven alert generation
- **Benefits**: Easier to add/modify templates, better testing

---

## 11. Naming Conventions

### 11.1 Datasets (R2)

**Pattern**: `{dataset_name}/{version}/{partition}/data.parquet`

**Examples**:
- `prices_ingestion/v1/2025-12-30/AAPL.parquet` (daily, partitioned by ticker)
- `features_daily/v1/2025-12-30/data.parquet` (daily, cross-sectional)
- `fundamentals_quarterly/v1/AAPL/data.parquet` (ticker-level, all quarters)

**Versioning**: Use `/v1/`, `/v2/` for schema changes

### 11.2 Tables (Supabase)

**Pattern**: `snake_case`

**Examples**: `users`, `watchlists`, `indicator_state`, `valuation_stats`, `alert_history`

### 11.3 Templates

**Pattern**: `T{number}` with descriptive name

**Examples**:
- `T1` - "Bullish 200 MA Cross"
- `T7` - "Historically Cheap (EV/EBITDA < p20)"

### 11.4 Code

**Classes**: `PascalCase` (e.g., `FeaturesComputer`, `EmailDeliveryService`)
**Functions**: `snake_case` (e.g., `compute_daily_features`, `evaluate_all_templates`)
**Constants**: `UPPER_SNAKE_CASE` (e.g., `TEMPLATE_METADATA`, `PRIMARY_COLOR`)

---

## 12. Common Patterns

### 12.1 Point-in-Time Fundamentals

**Problem**: Quarterly fundamentals released with lag, need to avoid look-ahead bias

**Pattern**:
```python
# Join price data (date: 2025-12-30) with fundamentals
# Use "asof" merge to get latest available quarterly data as of that date
features_df = pd.merge_asof(
    prices_df.sort_values('date'),
    fundamentals_df.sort_values('filing_date'),
    left_on='date',
    right_on='filing_date',
    by='ticker',
    direction='backward'  # Latest data *before* price date
)
```

**File**: `src/features/features_compute.py:_compute_ticker_features()`

### 12.2 TTM Calculation from Quarterly Reports

**Problem**: Compute trailing twelve months (TTM) from quarterly data, avoid double-counting annuals

**Pattern**:
```python
# Filter out annual 'Year' rows (period_type == 'Year')
quarterly_only = df[df['period_type'] != 'Year'].copy()

# Sort by date and take last 4 quarters
quarterly_only = quarterly_only.sort_values('filing_date')
last_4q = quarterly_only.tail(4)

# Sum EBITDA across 4 quarters
ebitda_ttm = last_4q['ebitda'].sum()
```

**File**: `src/features/features_compute.py:_compute_valuation_series()`

**Critical**: Filter out annual rows BEFORE computing TTM to avoid overcounting

### 12.3 Incremental EMA Computation

**Problem**: Computing 200-day EMA requires 200+ days of price history, slow to recompute daily

**Pattern**:
```python
# Step 1: Load previous EMA state from database
prev_ema, prev_date = db.get_indicator_state(ticker, 'ema_200')

# Step 2: Fetch only new prices since prev_date
new_prices = prices_df[prices_df['date'] > prev_date]

# Step 3: Compute EMA incrementally
alpha = 2 / (200 + 1)
for price in new_prices:
    ema = alpha * price + (1 - alpha) * prev_ema
    prev_ema = ema

# Step 4: Save final EMA state back to database
db.upsert_indicator_state(ticker, 'ema_200', ema, latest_date)
```

**File**: `src/features/features_compute.py:_compute_ema_series()`

### 12.4 R2 Data Access Patterns

**Reading Latest Features** (src/storage/r2_client.py:get_features_latest()):
```python
# List all dates in features_daily/v1/
dates = r2.list_objects(prefix='features_daily/v1/')

# Get most recent date
latest_date = max(dates)

# Read parquet file
key = f'features_daily/v1/{latest_date}/data.parquet'
df = r2.read_parquet(key)
```

**Writing Partitioned Data**:
```python
# Write daily features (cross-sectional, partitioned by date)
key = f'features_daily/v1/{run_date}/data.parquet'
r2.put_parquet(key, features_df)

# Write ticker-specific data (all history in one file)
key = f'fundamentals_quarterly/v1/{ticker}/data.parquet'
r2.put_parquet(key, fundamentals_df)
```

---

## 13. Troubleshooting

### 13.1 Common Issues

**Issue**: Daily pipeline fails with "No price data available"
- **Cause**: EODHD API rate limit or missing ticker
- **Fix**: Check `prices_ingestion/v1/{date}/` for missing files, verify EODHD_API_KEY
- **Verify**: `uv run python scripts/verify_data_availability.py --date 2025-12-30`

**Issue**: EMA computation returns NaN
- **Cause**: Insufficient price history (<200 days for EMA 200)
- **Fix**: Run backfill: `uv run python scripts/ingest_prices.py --ticker AAPL --days 400`
- **Verify**: Check indicator_state table for prev_value

**Issue**: Templates not triggering (getting empty results)

**Diagnosis - Check which templates are being evaluated**:
- T1-T6 (Basic): Only need features_daily data
- T7-T10 (Stats): Need valuation_stats table

**Step 1: Verify data completeness for basic templates (T1-T6)**
```bash
# Check if features_daily has required columns
uv run python -c "
from src.storage.r2_client import R2Client
r2 = R2Client()
df = r2.get_features_latest()
print('Required columns:', ['close', 'ema_200', 'ema_50', 'ev_ebitda'])
print('Available columns:', df.columns.tolist())
print('\nSample data:')
print(df[['ticker', 'close', 'ema_200', 'ev_ebitda']].head())
"
```

**Common Fixes**:
- Missing `ema_200` or `ema_50`: Run features pipeline, check indicator_state table
  ```bash
  psql $DATABASE_URL -c "SELECT * FROM indicator_state WHERE ticker = 'AAPL'"
  ```
- Missing `ev_ebitda`: Check fundamentals_latest table has TTM data
  ```bash
  psql $DATABASE_URL -c "SELECT ticker, ebitda_ttm, asof_date FROM fundamentals_latest WHERE ticker = 'AAPL'"
  ```

**Step 2: Verify data for stats templates (T7-T10)**
```bash
# Check if valuation_stats exists
psql $DATABASE_URL -c "SELECT ticker, p20, p50, p80 FROM valuation_stats WHERE ticker = 'AAPL'"
```

**Fix**: Run weekly stats pipeline once
```bash
uv run python -m src.features.pipeline_weekly_stats
```

**Step 3: Check template evaluation logs**
```bash
# Run pipeline with verbose logging
uv run python -m src.features.pipeline_daily \
  --run-date 2025-12-30 \
  --tickers AAPL \
  --skip-features  # Only evaluate templates
```

Look for output like:
- "Evaluating template T1 for 100 tickers" → Working
- "Skipping template T7: missing required stats" → Need valuation_stats

**Issue**: Emails not sending
- **Cause**: Invalid SMTP credentials or firewall
- **Fix**: Test SMTP: `uv run python src/email/sender.py` (manual test mode)
- **Verify**: Check GitHub Actions logs for SMTP errors

### 13.2 Data Availability Verification

**Script**: `scripts/verify_data_availability.py`

**Usage**:
```bash
# Check all watchlist tickers for specific date
uv run python scripts/verify_data_availability.py --date 2025-12-30

# Check specific ticker
uv run python scripts/verify_data_availability.py --ticker AAPL
```

**Checks**:
- Price data exists in R2
- Fundamentals data exists in R2
- Indicator state exists in Supabase
- Valuation stats exist in Supabase

### 13.3 Pipeline Failure Recovery

**Scenario**: Daily pipeline fails mid-execution

**Recovery Steps**:
1. Identify failed step from GitHub Actions logs
2. Re-run specific step with manual trigger:
   ```bash
   # Skip steps that succeeded
   gh workflow run daily-pipeline.yml \
     --field skip_ingestion=true \
     --field skip_features=false \
     --field run_date=2025-12-30
   ```
3. Verify output:
   ```bash
   aws s3 ls s3://bucket/features_daily/v1/2025-12-30/ \
     --endpoint-url $R2_ENDPOINT_URL
   ```
4. Resume from next step

**Rollback**:
- R2 data is append-only, safe to re-run
- Supabase updates are upserts, idempotent
- Email sending is logged in alert_history, check sent_at to avoid duplicates

---

## 14. Performance Optimization

### 14.1 Query Optimization

**Supabase Indexes**: Ensure indexes on frequently queried columns
```sql
CREATE INDEX idx_watchlists_user_id ON watchlists(user_id);
CREATE INDEX idx_indicator_state_ticker ON indicator_state(ticker, indicator_name);
CREATE INDEX idx_alert_history_user_sent ON alert_history(user_id, sent_at DESC);
```

### 14.2 Batch Processing

**Features Computation**: Process all tickers in single pipeline run
```python
# Good: Batch processing
tickers = db.get_active_tickers()  # 100 tickers
features_df = computer.compute_daily_features(run_date, tickers)

# Bad: One ticker at a time
for ticker in tickers:
    features_df = computer.compute_daily_features(run_date, [ticker])
```

### 14.3 Caching

**TimeSeriesReader**: Caches fundamentals data for repeated access
```python
reader = TimeSeriesReader(r2_client)
# First call: reads from R2
fundamentals = reader.get_fundamentals('AAPL')
# Subsequent calls: uses cache
fundamentals = reader.get_fundamentals('AAPL')
```

---

## 15. Security & Compliance

### 15.1 API Key Management

**Never commit secrets to Git**:
- Use GitHub Secrets for workflows
- Use Cloudflare Workers environment variables
- Use .env files locally (add to .gitignore)

**Key Rotation**:
- Rotate EODHD_API_KEY annually
- Rotate Supabase service role key quarterly
- Rotate R2 access keys quarterly

### 15.2 Data Privacy

**User Data**:
- Email addresses stored in Supabase `users` table
- SMTP credentials in GitHub Secrets
- Alert history includes user_id but no PII in parquet files

**Compliance**:
- GDPR: Provide user data export via API
- CAN-SPAM: Include unsubscribe link in emails
- Data Retention: Purge alert_history older than 2 years

---

## 16. Future Enhancements

### 16.1 Planned Features

**Custom Templates**:
- Allow users to create custom templates via web UI
- Store template definitions in Supabase
- Evaluate custom templates alongside hardcoded ones

**Real-Time Alerts**:
- Intraday price monitoring
- WebSocket notifications for immediate delivery

**Machine Learning Integration**:
- Predict template trigger likelihood
- Optimize trigger_strength scoring

### 16.2 Technical Debt

**Refactoring**:
- Extract common patterns into shared utilities
- Add comprehensive error handling
- Improve logging with structured logs

**Testing**:
- Increase test coverage to 80%+
- Add end-to-end integration tests
- Property-based testing for template evaluation

**Documentation**:
- API documentation with OpenAPI spec
- Template evaluation decision trees
- Runbook for on-call engineers

---

## Quick Reference

### Python Execution

**⚠️ Always use:** `uv run python <script>` (see section 1.1 for details)

**Examples:**
```bash
uv run python scripts/ingest_prices.py --tickers AAPL --days 7
uv run python -m src.features.pipeline_daily --run-date 2025-12-30
uv run python tests/test_templates.py
```

### File Paths

**Pipelines**:
- Daily: `.github/workflows/daily-pipeline.yml`
- Weekly: `.github/workflows/weekly-stats.yml`
- Backfill: `.github/workflows/daily-backfill.yml`

**Core Code**:
- Features: `src/features/pipeline_daily.py:66`
- Templates: `src/features/templates.py:145`
- Email: `src/email/delivery.py:49`
- Alert: `src/email/alerts.py:12`

**Scripts**:
- Ingest: `scripts/ingest_prices.py`
- Backfill: `scripts/process_backfill_queue.py`

**Worker**:
- Routes: `worker/src/index.py:45`

---

Last Updated: 2026-01-01
Architecture Version: 2.0 (Post-cleanup)
