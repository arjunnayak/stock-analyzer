# MVP Progress Tracker

Last updated: 2025-12-26

## Overview

Building **Material Changes** - a stateful stock monitoring system that alerts investors only when something materially changes.

**Core promise:** _"Monitor stocks I care about and notify me only when something materially changes — so I don't re-research."_

---

## 🎯 Success Metrics (14-day validation)

- [ ] Users keep alerts enabled
- [ ] Users read alerts (track open rate)
- [ ] ≥10–15% willing to pay $10/month

---

## 📊 Implementation Status

### ✅ COMPLETED (Week 1)

#### Data Infrastructure
- [x] **PostgreSQL schema** (Supabase) - users, entities, watchlists, state tracking
- [x] **R2 storage architecture** - time-series data in monthly partitions
- [x] **Data ingestion pipeline** - EODHD API → R2 storage
- [x] **Time-series reader** - high-level API for reading from R2
- [x] **Dolt integration** - backfill from MySQL databases

#### Signal Computation
- [x] **Technical signals** - SMA (20/50/200), trend detection, crossovers
- [x] **Valuation signals** - EV/Revenue, EV/EBITDA computation
- [x] **TTM computation** - Revenue and EBITDA from quarterly data
- [x] **Enterprise value** - Market cap + debt - cash calculation
- [x] **Historical analysis** - Percentile calculation, outlier detection (IQR)
- [x] **Regime classification** - Cheap (≤20%), Normal, Rich (≥80%)

#### Alert Types (3 of 3)
- [x] **Alert Type 1: Valuation Regime Change** ✨ (Just completed!)
  - Entry/exit of cheap/rich zones
  - Percentile-based vs own history
  - EV/EBITDA for profitable, EV/Revenue for unprofitable
  - Transition-only alerts (stateful)

- [x] **Alert Type 3: Trend Break**
  - 200-day MA crossovers
  - First cross in ≥6 months
  - Bullish/bearish signals

- [ ] **Alert Type 2: Fundamental Inflection** (⚠️ NEXT PRIORITY)
  - EPS direction changes
  - Revenue growth deceleration
  - Forward estimate revisions

#### State Management
- [x] **State tracking** - Previous regime, trend, EPS per user/stock
- [x] **Transition detection** - Only alert on material changes
- [x] **Alert repository** - PostgreSQL storage with full context
- [x] **Alert format** - What changed, why it matters, before/now, what didn't

#### Testing & Quality
- [x] **Unit tests** - 10 comprehensive tests for valuation module (100% passing)
- [x] **Mock data pipeline** - End-to-end testing without external dependencies
- [x] **Documentation** - Complete technical docs for valuation regime

#### CI/CD & Automation
- [x] **GitHub Actions workflows** ✨ (Just created!)
  - Daily signal evaluation (6 PM ET cron)
  - Weekly metrics computation (Sunday 2 AM)
  - CI/CD for tests and linting
  - Manual backfill workflow

---

### 🚧 IN PROGRESS (Week 2)

#### Alert Type 2: Fundamental Inflection
- [ ] EPS estimate data integration
- [ ] Direction change detection (positive → negative, etc.)
- [ ] Alert generation for EPS inflections
- [ ] Tests for fundamental inflection logic

#### Email Delivery System
- [ ] SMTP integration (via SendGrid/Postmark/SES)
- [ ] Email template design (plain text + HTML)
- [ ] Alert batching (instant vs daily digest)
- [ ] Unsubscribe handling
- [ ] Delivery logging

#### Validation & Metrics
- [ ] Alert sent logging
- [ ] Alert opened tracking (pixel/link tracking)
- [ ] Stock removed tracking
- [ ] Alerts paused tracking
- [ ] Conversion attempt logging
- [ ] Dashboard for validation metrics

---

### 📋 TODO (Week 2 cont.)

#### Frontend UI (Minimal)
- [ ] **Onboarding flow**
  - Email entry
  - Add 5-10 tickers
  - Select investing style (Value/Growth/Blend)
  - Magic link auth

- [ ] **Watchlist page**
  - Delta-only summary (↑ ↓ →)
  - Last alert date
  - Pause/remove controls

- [ ] **Stock detail page**
  - Valuation: ↑ ↓ →
  - Fundamentals: ↑ ↓ →
  - Trend: ↑ ↓ →
  - Alert history

- [ ] **Settings page**
  - Pause all alerts
  - Change investing style
  - Account management

#### Deployment
- [ ] Cloudflare Workers API setup
- [ ] R2 bucket configuration
- [ ] Supabase production setup
- [ ] Environment variable management
- [ ] Domain setup + SSL

#### Polish & Launch Prep
- [ ] Alert quality review (test with real stocks)
- [ ] Email deliverability testing
- [ ] Performance optimization
- [ ] Error handling & monitoring
- [ ] Privacy policy & terms
- [ ] Launch checklist

---

## 🏗️ Technical Architecture

### Data Flow

```
┌─────────────────┐
│  EODHD API      │  ← Daily price/fundamental data
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GitHub Actions │  ← Daily batch job (6 PM ET)
│  (Compute)      │
└────────┬────────┘
         │
         ├──► R2 Storage (Time-series)
         │    └── prices, fundamentals, signals
         │
         └──► PostgreSQL (Metadata + State)
              └── users, watchlists, alerts, state

┌─────────────────┐
│  Daily Pipeline │
└────────┬────────┘
         │
         ├──► Read R2 signals
         ├──► Detect state changes
         ├──► Generate alerts
         ├──► Send emails
         └──► Update state
```

### Storage Breakdown

**R2 (Time-series):**
- `prices/v1/{ticker}/{year}/{month}/data.parquet`
- `fundamentals/v1/{ticker}/{year}/{month}/data.parquet`
- `signals_technical/v1/{ticker}/{year}/{month}/data.parquet`
- `signals_valuation/v1/{ticker}/{year}/{month}/data.parquet`

**PostgreSQL (Metadata + State):**
- `users` - Email, auth, preferences
- `entities` - Ticker metadata
- `watchlists` - User → ticker mapping
- `user_entity_settings` - Previous state (regime, trend, EPS)
- `alert_history` - Audit log with full context

---

## 📈 Data Requirements (Per Stock)

### Minimum Required
- [x] Daily close prices (5-10 years)
- [x] 200-day moving average
- [x] EV/EBITDA or EV/Revenue (quarterly → daily)
- [ ] Forward 12m EPS estimates
- [x] Revenue (quarterly, for TTM)
- [x] EBITDA (quarterly, for TTM)

### Nice to Have
- [ ] Sector classification
- [ ] Market cap tier (small/mid/large)
- [ ] Analyst rating changes

---

## 🎨 Alert Format (Implemented)

```
[AAPL] — Valuation entered historically cheap zone

What changed:
• EV/EBITDA moved from 42nd percentile → 19th percentile

Why it matters:
• Stock is trading at the lower end of its own historical valuation range,
  which can increase margin of safety.

Before vs now:
• Multiple: 28.5x → 22.3x
• Percentile: 42 → 19

What didn't change:
• Metric used: EV/EBITDA
• This is a relative valuation signal based on the company's own history
• Underlying business fundamentals may have changed separately
```

---

## 🚫 Explicitly Out of Scope (MVP)

- ❌ Charts/graphs
- ❌ AI buy/sell recommendations
- ❌ Screeners
- ❌ Social features
- ❌ Broker integrations
- ❌ Mobile app
- ❌ Custom alert logic
- ❌ User-defined thresholds
- ❌ News aggregation
- ❌ Push notifications

---

## 📅 Timeline

### Week 1 (COMPLETED) ✅
- Data ingestion pipeline
- Signal computation (3 alert types)
- State tracking & transitions
- Alert generation framework
- GitHub Actions setup

### Week 2 (IN PROGRESS)
- [ ] Complete Alert Type 2 (Fundamental Inflection)
- [ ] Email delivery system
- [ ] Validation metrics & logging
- [ ] Frontend UI (minimal)
- [ ] Deploy to production
- [ ] Launch validation experiment

### Week 3 (Validation)
- Monitor metrics
- Gather feedback
- Iterate on alert quality
- Evaluate go/no-go decision

---

## 🎯 Next Immediate Steps

1. **Implement Alert Type 2** (Fundamental Inflection)
   - Add EPS estimate data to fundamentals pipeline
   - Build direction change detector
   - Generate alerts for EPS inflections
   - Write tests

2. **Set up email delivery**
   - Choose provider (SendGrid recommended for MVP)
   - Create templates
   - Integrate with alert pipeline
   - Test deliverability

3. **Deploy GitHub Actions**
   - Set up repository secrets
   - Test daily evaluation workflow manually
   - Verify logs and artifacts
   - Monitor first automated run

4. **Build minimal frontend**
   - Onboarding form
   - Watchlist page
   - Deploy to Cloudflare Pages/Workers

---

## 🔍 Validation Hooks (Required Logging)

```python
# Track these events for go/no-go decision
events_to_log = [
    "alert_sent",          # Every alert delivery
    "alert_opened",        # Email open tracking
    "stock_removed",       # User removes from watchlist
    "alerts_paused",       # User disables alerts
    "conversion_attempt",  # User tries to upgrade
]
```

---

## 💀 Kill Criteria (14 days)

Stop or pivot if:
- <5% convert to paid
- Users ignore alerts (low open rate)
- Feedback centers on "needs more features"

**This is success at learning fast, not failure.**

---

## 🌟 One-Sentence North Star

> "Every line of code must reduce how often the user feels the need to re-check a stock manually."

---

## 📝 Notes

- **Cost optimization:** Using GitHub Actions free tier (2,000 min/month), Cloudflare Workers free tier, Supabase free tier
- **Data provider:** EODHD (backup: Alpha Vantage, Financial Modeling Prep)
- **Tech stack:** Python 3.10, pandas, PostgreSQL, R2, Cloudflare Workers
- **Target users:** 10-50 users for validation phase
- **Geographic focus:** US equities only (MVP)

---

For detailed implementation docs, see:
- `/docs/system-architecture.md` - Overall architecture
- `/docs/mvp-product-plan.md` - Product requirements
- `/docs/valuation-regime-module.md` - Valuation signals implementation
- `/.github/workflows/README.md` - GitHub Actions setup
