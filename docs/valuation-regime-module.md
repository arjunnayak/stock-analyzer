# Valuation Regime Module

## Overview

The **Valuation Regime Module** provides automated, trustworthy valuation monitoring for US equities using a percentile-based approach. It tracks whether stocks are trading in historically cheap, normal, or rich zones relative to their own multi-year history, and generates alerts only on meaningful regime transitions.

## Key Features

✅ **One Metric Per Stock** - Automatically selects EV/EBITDA (for profitable companies) or EV/Revenue (for unprofitable/growth companies)
✅ **Historical Percentile Analysis** - Compares current valuation to 3-10 years of the company's own history
✅ **Robust Outlier Detection** - Uses IQR-based cleaning to prevent extreme data points from skewing results
✅ **Transition-Only Alerts** - Only alerts on regime changes (enter/exit cheap/rich zones), not continuous conditions
✅ **Human-Readable Explanations** - Generates structured alerts with clear "what changed" and "why it matters" sections
✅ **Conservative Approach** - No "fair value" estimates or buy/sell recommendations

## Non-Goals (MVP)

This module intentionally does NOT provide:
- P/E or PEG ratio analysis
- Sector-relative comparisons
- Fair value estimation
- Buy/sell recommendations
- Charting or visualization
- Custom user-defined metrics
- Intraday data (daily EOD only)

## Core Concepts

### 1. Metric Selection Logic

The system deterministically chooses **ONE** valuation metric per stock:

```python
if latest_ttm_ebitda > 0 AND
   sufficient_positive_ebitda_history (≥18 of last 24 months):
    metric = EV/EBITDA
else:
    metric = EV/Revenue
```

**Examples:**
- Apple (AAPL): Consistently profitable → **EV/EBITDA**
- Cloudflare (NET): Unprofitable → **EV/Revenue**

### 2. Regime Classification

Valuation regimes are based on historical percentiles:

| Percentile Range | Regime | Meaning |
|------------------|--------|---------|
| ≤ 20th percentile | **CHEAP** | Trading at lower end of historical range |
| 21st - 79th percentile | **NEUTRAL** | Trading within normal historical range |
| ≥ 80th percentile | **RICH** | Trading at upper end of historical range |

**Lower percentile = cheaper valuation = better margin of safety**

### 3. Transition-Based Alerting

Alerts are triggered ONLY on regime transitions:

- ✅ **NEUTRAL → CHEAP** (enter cheap zone)
- ✅ **CHEAP → NEUTRAL** (exit cheap zone)
- ✅ **NEUTRAL → RICH** (enter rich zone)
- ✅ **RICH → NEUTRAL** (exit rich zone)

**No alerts** if regime stays the same day-to-day.

## Data Requirements

### Input Data

The module expects the following data to be pre-computed and stored in R2:

**signals_valuation dataset** (daily time series per ticker):
- `date`: Date of observation
- `ev_revenue`: EV/Revenue multiple
- `ev_ebitda`: EV/EBITDA multiple
- `ttm_revenue`: Trailing twelve month revenue
- `ttm_ebitda`: Trailing twelve month EBITDA
- `enterprise_value`: Enterprise value
- `market_cap`: Market capitalization
- `shares_outstanding`: Shares outstanding

### Minimum History Requirements

- **Preferred**: 10 years of daily data
- **Minimum**: 3 years of data
- **Required valid points**: At least 36 monthly observations after cleaning

If insufficient history exists, the module returns `regime: UNKNOWN` and does not generate alerts.

## Data Pipeline

### 1. TTM Computation

TTM (Trailing Twelve Month) metrics are computed from quarterly fundamental data:

```python
# Example: TTM Revenue
quarterly_sales = [250M, 250M, 250M, 250M]  # Last 4 quarters
ttm_revenue = sum(quarterly_sales)  # = $1B
```

### 2. Enterprise Value Calculation

```
EV = Market Cap + Total Debt - Cash
```

where:
- **Market Cap** = Price × Shares Outstanding
- **Total Debt** = Long-term Debt + Current Portion of Long-term Debt
- **Cash** = Cash and Equivalents

### 3. Multiple Calculation

```
EV/Revenue = Enterprise Value / TTM Revenue
EV/EBITDA = Enterprise Value / TTM EBITDA
```

Multiples are set to `None` if the denominator is zero or negative.

### 4. Historical Cleaning

The module applies robust outlier detection:

1. **Remove invalid values**: NaN, inf, zero, negative
2. **IQR outlier removal**: Keep values within `[Q1 - 3×IQR, Q3 + 3×IQR]`
3. **Minimum data check**: Require at least 36 valid points

### 5. Percentile Calculation

Uses `scipy.stats.percentileofscore` with `kind='rank'`:

```python
current_value = 18.5x
historical_values = [10x, 12x, ..., 25x]  # Cleaned history

percentile = percentileofscore(historical_values, current_value)
# Returns: 65.2 (meaning current value is higher than 65.2% of history)
```

## Output Format

### Main Function: `compute_valuation_signals()`

```python
result = ValuationSignals.compute_valuation_signals(valuation_df, lookback_years=10)

# Returns:
{
    'metric_type': 'ev_ebitda',         # or 'ev_revenue' or 'unknown'
    'current_multiple': 18.5,            # Current valuation multiple
    'current_percentile': 65.2,          # Percentile rank (0-100)
    'regime': 'normal',                  # 'cheap', 'normal', 'expensive', 'unknown'
    'history_count': 1821,               # Number of valid historical points
    'history_min': 10.2,                 # Min multiple in history
    'history_max': 25.8,                 # Max multiple in history
    'history_median': 16.5,              # Median multiple
    'outliers_removed': 12,              # Count of outliers filtered out
    'success': True,                     # Whether computation succeeded
    'error': None                        # Error message if failed
}
```

### Alert Format

When a regime transition occurs, the system generates a structured alert:

```python
alert = AlertGenerator.generate_valuation_regime_alert(
    ticker="AAPL",
    change=state_change,
    current_percentile=18.5,
    current_metric_value=22.3,
    metric_type="ev_ebitda",
    previous_percentile=45.2
)

# Alert structure:
alert.headline = "Valuation entered historically cheap zone"
alert.what_changed = "• EV/EBITDA moved from 45th percentile → 19th percentile"
alert.why_it_matters = "• Stock is trading at the lower end of its own historical..."
alert.before_vs_now = "• Multiple: 28.5x → 22.3x\n• Percentile: 45 → 19"
alert.what_didnt_change = "• Metric used: EV/EBITDA\n• This is a relative signal..."
```

## Usage Examples

### Example 1: Evaluate a Profitable Company (AAPL)

```python
from src.signals.valuation import ValuationSignals
from src.reader import TimeSeriesReader

# Read valuation data from R2
reader = TimeSeriesReader()
valuation_df = reader.r2.get_timeseries(
    "signals_valuation",
    "AAPL",
    start_date=date(2015, 1, 1),
    end_date=date(2025, 1, 1)
)

# Compute valuation signals
result = ValuationSignals.compute_valuation_signals(valuation_df, lookback_years=10)

print(f"Metric: {result['metric_type']}")           # ev_ebitda (profitable)
print(f"Current: {result['current_multiple']:.2f}x")
print(f"Percentile: {result['current_percentile']:.1f}")
print(f"Regime: {result['regime']}")                # cheap/normal/expensive
```

### Example 2: Evaluate an Unprofitable Company (NET)

```python
# Same as above, but for Cloudflare (NET)
result = ValuationSignals.compute_valuation_signals(net_valuation_df, lookback_years=10)

print(f"Metric: {result['metric_type']}")           # ev_revenue (unprofitable)
print(f"Current: {result['current_multiple']:.2f}x")
print(f"Regime: {result['regime']}")
```

### Example 3: Detect Regime Transitions

```python
from src.signals.state_tracker import StateTracker

tracker = StateTracker()

# Get previous state
previous_state = tracker.get_state(user_id, entity_id, "AAPL")

# Detect change
change = tracker.detect_valuation_regime_change(
    previous_state,
    current_percentile=18.5,
    cheap_threshold=20.0,
    expensive_threshold=80.0
)

if change and change.should_alert:
    print(f"Regime transition: {change.old_value} → {change.new_value}")
    # Generate alert...
```

## Edge Cases & Error Handling

### 1. Missing or Invalid Data

```python
result = ValuationSignals.compute_valuation_signals(empty_df)

# Returns:
{
    'success': False,
    'error': 'No valuation data',
    'regime': 'unknown',
    'current_multiple': None,
    # ... all other fields None or default values
}
```

### 2. Insufficient History

```python
# Only 2 years of data (need minimum 3)
result = ValuationSignals.compute_valuation_signals(short_df)

# Returns:
{
    'success': False,
    'error': 'Insufficient history: 24 < 36',
    'regime': 'unknown'
}
```

### 3. Company Transitions to Profitability

When a company becomes profitable, the metric may switch from EV/Revenue to EV/EBITDA. The module:
- Requires **18 consecutive months** of positive EBITDA before switching
- Prevents flip-flopping between metrics
- Returns `metric_type` in output for transparency

### 4. Zero or Negative Revenue

```python
# Invalid data (revenue <= 0)
result = ValuationSignals.compute_valuation_signals(invalid_df)

# Returns:
{
    'success': False,
    'error': 'Invalid revenue data',
    'metric_type': 'unknown'
}
```

## State Persistence

The module persists state in the `user_entity_settings` PostgreSQL table:

```sql
CREATE TABLE user_entity_settings (
    user_id UUID,
    entity_id UUID,
    last_valuation_regime TEXT,           -- 'cheap', 'normal', 'expensive'
    last_valuation_percentile FLOAT,      -- Last computed percentile
    last_evaluated_at TIMESTAMP,
    ...
);
```

This enables:
- **Transition detection**: Compare current regime vs. previous regime
- **Alert suppression**: Don't re-alert if regime hasn't changed
- **Audit trail**: Track when valuation was last evaluated

## Testing

### Run Unit Tests

```bash
# Run comprehensive test suite
python tests/test_valuation_regime.py

# Expected output:
# ✓ Metric Selection (Profitable): PASS
# ✓ Metric Selection (Unprofitable): PASS
# ✓ Outlier Cleaning: PASS
# ✓ Percentile Calculation: PASS
# ✓ Regime Classification: PASS
# ✓ Missing Data Handling: PASS
# ✓ TTM Computation: PASS
# ✓ Full Pipeline (Profitable): PASS
# ✓ Full Pipeline (Unprofitable): PASS
#
# 🎉 ALL TESTS PASSED!
```

### Test Coverage

The test suite validates:
1. ✅ Profitable companies use EV/EBITDA
2. ✅ Unprofitable companies use EV/Revenue
3. ✅ Regime transitions fire exactly once (not repeatedly)
4. ✅ Missing data yields UNKNOWN regime
5. ✅ Outlier handling prevents extreme percentiles
6. ✅ TTM computation is accurate
7. ✅ Percentile calculation is directionally correct
8. ✅ Boundary conditions (20th/80th percentile) work correctly

## Integration with Signal Pipeline

The valuation regime module integrates seamlessly with the existing signal evaluation pipeline:

```python
# In SignalPipeline.evaluate_ticker_for_user()

# 1. Fetch valuation data
valuation_df = self.reader.r2.get_timeseries("signals_valuation", ticker, ...)

# 2. Compute signals
result = ValuationSignals.compute_valuation_signals(valuation_df)

# 3. Detect transitions
change = self.state_tracker.detect_valuation_regime_change(
    previous_state,
    current_percentile
)

# 4. Generate alert if changed
if change and change.should_alert:
    alert = AlertGenerator.generate_valuation_regime_alert(...)
    self.alert_repo.save_alert(user_id, entity_id, alert)

# 5. Update state
self.state_tracker.update_state(
    user_id, entity_id,
    valuation_regime=result['regime'],
    valuation_percentile=result['current_percentile']
)
```

## Alert Examples

### Example 1: Entering Cheap Zone

```
[AAPL] — Valuation entered historically cheap zone

What changed:
• EV/EBITDA moved from 42nd percentile → 18th percentile

Why it matters:
• Stock is trading at the lower end of its own historical valuation range, which can increase margin of safety.

Before vs now:
• Multiple: 28.5x → 22.3x
• Percentile: 42 → 18

What didn't change:
• Metric used: EV/EBITDA
• This is a relative valuation signal based on the company's own history
• Underlying business fundamentals may have changed separately
```

### Example 2: Exiting Rich Zone

```
[NET] — Valuation exited historically rich zone

What changed:
• EV/Revenue moved from 85th percentile → 72nd percentile

Why it matters:
• Valuation is no longer in a historically premium range.

Before vs now:
• Multiple: 15.2x → 12.8x
• Percentile: 85 → 72

What didn't change:
• Metric used: EV/Revenue
• This is a relative valuation signal based on the company's own history
• Underlying business fundamentals may have changed separately
```

## Quality Guarantees

1. **Deterministic Behavior** - Same input always produces same output
2. **Graceful Degradation** - Returns `UNKNOWN` regime when data is insufficient (never crashes)
3. **Rare, Meaningful Alerts** - Only triggers on regime transitions (not daily noise)
4. **Explainable Output** - All alerts include human-readable explanations
5. **Conservative Approach** - No speculative recommendations, only relative observations

## Future Enhancements (Out of MVP Scope)

Potential future additions:
- Sector-relative comparisons (e.g., "cheap vs. other SaaS companies")
- Multiple concurrent metrics (P/E, PEG, etc.)
- Forward-looking estimates (using analyst consensus)
- Custom user-defined thresholds
- Intraday valuation updates
- Charting and visualization

## References

- **System Architecture**: `/docs/system-architecture.md`
- **Database Schema**: `/supabase/migrations/001_initial_schema.sql`
- **Valuation Signals Code**: `/src/signals/valuation.py`
- **State Tracker**: `/src/signals/state_tracker.py`
- **Alert Generator**: `/src/signals/alerts.py`
- **Pipeline Integration**: `/src/signals/pipeline.py`
- **Unit Tests**: `/tests/test_valuation_regime.py`

## Support

For issues or questions:
1. Check test failures: `python tests/test_valuation_regime.py`
2. Review error messages in `result['error']` field
3. Verify data availability in R2 storage
4. Check state persistence in PostgreSQL

---

**Built with**: Python 3.10+, pandas, numpy, scipy, PostgreSQL, R2/S3 storage
**License**: Internal use only
**Last Updated**: 2025-12-26
