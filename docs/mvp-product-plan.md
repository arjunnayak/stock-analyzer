Below is a **clear, execution-ready MVP product plan** written **specifically to hand to a coding agent**.
It is opinionated, scoped, and optimized for **speed + validation**, not elegance.

---

# PRODUCT PLAN — MVP: Stateful Stock Monitoring & Alerts

## 0. Product Definition (do not skip)

**Product name (working):** Material Changes
**Core promise:**

> Monitor stocks I care about and notify me *only* when something materially changes — so I don’t re-research.

**Explicit non-goals (MVP):**

* No charts
* No AI buy/sell recommendations
* No screeners
* No social features
* No broker integrations
* No mobile app (web + email only)

---

## 1. Target User (single persona)

* Self-directed investor
* Owns / watches 5–30 US stocks
* Checks markets weekly or more
* Already uses tools like TradingView / SA / Yahoo
* Pain: re-checking the same stocks repeatedly

---

## 2. MVP Success Criteria (engineering-aligned)

The MVP is successful if, within 14 days:

* Users keep alerts enabled
* Users read alerts
* ≥10–15% are willing to pay $10/month

This means:

> **Alert quality > feature completeness**

---

## 3. Core User Flow (MVP)

### 3.1 Onboarding Flow

1. User enters email
2. User adds 5–10 stock tickers (US equities only)
3. User selects investing style:

   * Value
   * Growth
   * Blend
4. User submits

No auth complexity beyond magic link or simple login.

---

### 3.2 Daily System Flow (background job)

Runs **once per day (EOD)**:

For each user
→ for each stock
→ evaluate material change signals
→ if triggered, create alert
→ send email

If **no alerts triggered**, optionally send:

> “No material changes today”

---

## 4. Data Scope (strictly limited)

### 4.1 Assets

* US-listed equities only
* No ETFs
* No crypto
* No international

### 4.2 Required Data Fields

You need only:

**Price data**

* Daily close
* 200-day moving average

**Fundamental data**

* EV/EBITDA (or ONE valuation metric — pick one)
* Forward 12m EPS estimate (or revenue growth if EPS unavailable)
* Historical valuation time series (5–10 years)

**Metadata**

* Ticker
* Company name
* Sector (optional, not required)

If a stock lacks sufficient data → skip alerts silently.

---

## 5. Alert Types (HARD-CODED, NO USER CONFIG)

### Alert Type 1 — Valuation Regime Change

**Goal:** Detect entry or exit from historically cheap/expensive zones.

**Logic (example):**

* Compute percentile of current valuation vs its own 10-year history
* Trigger alert if:

  * Enters bottom 20% OR
  * Exits bottom 20%

**Stateful requirement:**

* Alert only on **change of regime**, not persistence

---

### Alert Type 2 — Fundamental Inflection

**Goal:** Catch deterioration or improvement early.

**Logic (pick ONE):**

* Forward EPS revisions:

  * Positive → negative
  * Negative → positive

OR

* Revenue growth decelerates beyond threshold (YoY delta)

**Stateful requirement:**

* Alert only on **directional change**

---

### Alert Type 3 — Trend Break

**Goal:** Identify major trend shifts without noise.

**Logic:**

* Price crosses above or below 200DMA
* Only trigger if:

  * First cross in ≥6 months

---

## 6. Alert Explanation (NON-NEGOTIABLE)

Every alert **must include 4 sections**:

```
[TICKER] — [Short headline]

What changed:
• Concrete metric movement

Why it matters:
• Plain-English investor relevance

Before vs now:
• Then → Now

What didn’t change:
• 1–2 stabilizing facts
```

If an alert cannot be explained this clearly → **do not send it**.

---

## 7. Stock Detail View (Minimal UI)

For each stock, show **delta-only summary**:

* Valuation: ↑ ↓ →
* Fundamentals: ↑ ↓ →
* Trend: ↑ ↓ →
* Last alert date

No charts. No tables. No raw numbers unless necessary.

---

## 8. Alert Delivery

### Channels

* Email only (MVP)

### Frequency

* Instant for material alerts
* Optional daily digest if multiple alerts

### Subject line format

```
[Material Change] TICKER — short reason
```

---

## 9. User Controls (Minimal)

User can:

* Pause all alerts
* Remove stock
* Change investing style

User cannot:

* Write custom alert logic
* Change thresholds
* Add indicators

(These come later if MVP succeeds.)

---

## 10. Architecture (Simple & Fast)

### 10.1 Backend

* Daily cron job
* Stateless workers evaluating signals
* Persistent store for:

  * User stocks
  * Previous signal states
  * Alert history

### 10.2 Frontend

* Simple web UI
* Onboarding form
* Watchlist page
* Stock detail page
* Settings page

### 10.3 State Tracking (IMPORTANT)

You must store **previous state** per stock per user:

* Previous valuation regime
* Previous EPS direction
* Previous trend position

This is the core differentiation.

---

## 11. What NOT to Build (explicitly)

* AI stock picks
* Scores / grades
* Screeners
* Backtesting
* News aggregation
* Push notifications
* Mobile app
* Sharing / social

If it doesn’t support **“notify me so I don’t re-research”**, cut it.

---

## 12. Validation Hooks (required)

Log these events:

* Alert sent
* Alert opened
* Stock removed
* Alerts paused
* Conversion attempt

This data decides go/no-go.

---

## 13. MVP Timeline (realistic)

**Week 1**

* Data ingestion
* Signal logic
* Alert templating

**Week 2**

* Onboarding UI
* Email delivery
* Logging + metrics
* Run validation experiment

---

## 14. Kill Criteria (write this into README)

If after 14 days:

* <5% convert to paid
* Users ignore alerts
* Feedback centers on “needs more features”

→ **STOP** or **PIVOT**

This is not failure — it’s success at learning fast.

---

## 15. One-Sentence Build North Star (pin this)

> “Every line of code must reduce how often the user feels the need to re-check a stock manually.”

---

If you want next, I can:

* Translate this into **task tickets** (Jira-style)
* Define **exact numeric thresholds**
* Or rewrite this as a **Cursor / Claude coding prompt** optimized for agent execution
