#!/usr/bin/env python3
"""
Check the health of GitHub automation and data pipelines.

Verifies:
- Latest price data dates
- Latest fundamentals dates
- Latest features computed
- Data freshness and gaps
- Potential issues
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.r2_client import R2Client
from src.storage.supabase_db import SupabaseDB
from src.reader import TimeSeriesReader


def check_price_data_health():
    """Check health of price data."""
    print("\n" + "=" * 70)
    print("PRICE DATA HEALTH CHECK")
    print("=" * 70)

    r2 = R2Client()
    db = SupabaseDB()
    reader = TimeSeriesReader()

    # Get active tickers
    tickers = db.get_active_tickers()
    print(f"Active tickers: {len(tickers)}")

    if not tickers:
        print("❌ No active tickers found!")
        return False

    # Check latest price snapshot
    latest_snapshot_date = r2.get_latest_price_snapshot_date(lookback_days=7)
    if latest_snapshot_date:
        days_old = (date.today() - latest_snapshot_date).days
        status = "✓" if days_old <= 1 else "⚠️"
        print(f"{status} Latest price snapshot: {latest_snapshot_date} ({days_old} days old)")
    else:
        print("❌ No price snapshot found in last 7 days")

    # Check latest ingestion data
    latest_price_date = reader.get_latest_price_date(tickers[:5], lookback_days=7)
    if latest_price_date:
        days_old = (date.today() - latest_price_date).days
        status = "✓" if days_old <= 1 else "⚠️"
        print(f"{status} Latest price ingestion: {latest_price_date} ({days_old} days old)")
    else:
        print("❌ No price ingestion data found in last 7 days")

    # Check a sample ticker in detail
    sample_ticker = tickers[0]
    print(f"\nSample ticker: {sample_ticker}")

    # Check December 2025 and January 2026
    for year_month in ["2025/12", "2026/01"]:
        key = f"prices/v1/{sample_ticker}/{year_month}/data.parquet"
        try:
            df = r2.read_parquet(key)
            if df is not None and not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                latest = df['date'].max().date()
                print(f"  ✓ {year_month}: {len(df)} rows, latest = {latest}")
            else:
                print(f"  ✗ {year_month}: No data")
        except Exception as e:
            print(f"  ✗ {year_month}: Error - {e}")

    return latest_price_date is not None


def check_features_health():
    """Check health of computed features."""
    print("\n" + "=" * 70)
    print("FEATURES DATA HEALTH CHECK")
    print("=" * 70)

    r2 = R2Client()

    # Check latest features
    try:
        df = r2.read_parquet("features/v1/latest.parquet")
        if df is not None and not df.empty:
            latest_date = df['date'].max()
            days_old = (date.today() - pd.Timestamp(latest_date).date()).days
            status = "✓" if days_old <= 1 else "⚠️"
            print(f"{status} Latest features computed: {latest_date} ({days_old} days old)")
            print(f"  Tickers: {len(df)}")
            print(f"  Columns: {list(df.columns)}")

            # Check for null values in critical columns
            critical_cols = ['close', 'ema_200', 'ema_50', 'ev_ebitda']
            for col in critical_cols:
                if col in df.columns:
                    null_count = df[col].isna().sum()
                    total = len(df)
                    status = "✓" if null_count == 0 else "⚠️"
                    print(f"  {status} {col}: {total - null_count}/{total} non-null")

            return True
        else:
            print("❌ No features data found")
            return False
    except Exception as e:
        print(f"❌ Error reading features: {e}")
        return False


def check_fundamentals_health():
    """Check health of fundamentals data."""
    print("\n" + "=" * 70)
    print("FUNDAMENTALS DATA HEALTH CHECK")
    print("=" * 70)

    db = SupabaseDB()

    tickers = db.get_active_tickers()
    if not tickers:
        print("❌ No active tickers found")
        return False

    latest_date = db.get_fundamentals_latest_date(tickers)

    if latest_date:
        days_old = (date.today() - latest_date).days
        status = "✓" if days_old <= 120 else "⚠️"
        print(f"{status} Latest fundamentals: {latest_date} ({days_old} days old)")

        if days_old > 120:
            print("  ⚠️  Fundamentals are stale (> 4 months)")
            print("  Action: Run fundamentals backfill")

        return days_old <= 120
    else:
        print("❌ No fundamentals data found")
        return False


def check_indicator_state():
    """Check indicator state health."""
    print("\n" + "=" * 70)
    print("INDICATOR STATE HEALTH CHECK")
    print("=" * 70)

    db = SupabaseDB()

    try:
        result = db.client.table("indicator_state").select("*").limit(5).execute()

        if result.data:
            print(f"✓ Indicator state table has {len(result.data)} rows (sample)")

            # Check dates
            for row in result.data[:3]:
                ticker = row['ticker']
                indicator = row['indicator_name']
                prev_date = row.get('prev_date')
                if prev_date:
                    days_old = (date.today() - date.fromisoformat(prev_date)).days
                    status = "✓" if days_old <= 2 else "⚠️"
                    print(f"  {status} {ticker} {indicator}: {prev_date} ({days_old} days old)")

            return True
        else:
            print("⚠️  Indicator state table is empty")
            print("  This is normal for first run")
            return True
    except Exception as e:
        print(f"❌ Error checking indicator state: {e}")
        return False


def check_alert_history():
    """Check alert history and recent deliveries."""
    print("\n" + "=" * 70)
    print("ALERT HISTORY CHECK")
    print("=" * 70)

    db = SupabaseDB()

    try:
        # Check last 7 days of alerts
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

        result = db.client.table("alert_history")\
            .select("*")\
            .gte("sent_at", seven_days_ago)\
            .order("sent_at", desc=True)\
            .limit(10)\
            .execute()

        if result.data:
            print(f"✓ Found {len(result.data)} alerts in last 7 days")

            for alert in result.data[:5]:
                sent_at = alert.get('sent_at', 'unknown')[:10]
                ticker = alert.get('ticker', 'unknown')
                alert_type = alert.get('alert_type', 'unknown')
                opened = "opened" if alert.get('opened_at') else "not opened"
                print(f"  - {sent_at}: {ticker} ({alert_type}) - {opened}")

            return True
        else:
            print("⚠️  No alerts sent in last 7 days")
            print("  This could mean:")
            print("  - No template triggers fired (normal if no material changes)")
            print("  - Pipeline not running")
            print("  - Alert delivery failing")
            return False
    except Exception as e:
        print(f"❌ Error checking alert history: {e}")
        return False


def check_workflow_health():
    """Check if workflows should be running."""
    print("\n" + "=" * 70)
    print("WORKFLOW SCHEDULE CHECK")
    print("=" * 70)

    now = datetime.now()

    print(f"Current time: {now} UTC")
    print(f"Current day: {now.strftime('%A')}")
    print()

    # Daily pipeline
    daily_pipeline_time = now.replace(hour=23, minute=0, second=0, microsecond=0)
    time_until_daily = daily_pipeline_time - now
    if time_until_daily.total_seconds() < 0:
        time_until_daily += timedelta(days=1)

    print(f"Daily Pipeline (11 PM UTC / 6 PM ET):")
    print(f"  Next run: {daily_pipeline_time + (timedelta(days=1) if time_until_daily.total_seconds() < 0 else timedelta(0))}")
    print(f"  Time until: {time_until_daily}")
    print()

    # Weekly stats
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour < 7:
        next_sunday = now
    else:
        next_sunday = now + timedelta(days=days_until_sunday if days_until_sunday > 0 else 7)

    next_sunday = next_sunday.replace(hour=7, minute=0, second=0, microsecond=0)

    print(f"Weekly Stats (Sunday 2 AM ET / 7 AM UTC):")
    print(f"  Next run: {next_sunday}")
    print(f"  Time until: {next_sunday - now}")


def main():
    """Run all health checks."""
    print("\n" + "=" * 70)
    print("AUTOMATION HEALTH CHECK")
    print("=" * 70)
    print(f"Run time: {datetime.now()}")

    results = {}

    try:
        results['prices'] = check_price_data_health()
    except Exception as e:
        print(f"❌ Price health check failed: {e}")
        results['prices'] = False

    try:
        results['features'] = check_features_health()
    except Exception as e:
        print(f"❌ Features health check failed: {e}")
        results['features'] = False

    try:
        results['fundamentals'] = check_fundamentals_health()
    except Exception as e:
        print(f"❌ Fundamentals health check failed: {e}")
        results['fundamentals'] = False

    try:
        results['indicators'] = check_indicator_state()
    except Exception as e:
        print(f"❌ Indicator state check failed: {e}")
        results['indicators'] = False

    try:
        results['alerts'] = check_alert_history()
    except Exception as e:
        print(f"❌ Alert history check failed: {e}")
        results['alerts'] = False

    try:
        check_workflow_health()
    except Exception as e:
        print(f"❌ Workflow health check failed: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_healthy = all(results.values())

    for check, status in results.items():
        icon = "✓" if status else "❌"
        print(f"{icon} {check.capitalize()}: {'Healthy' if status else 'Issues detected'}")

    print()

    if all_healthy:
        print("✅ All systems healthy!")
        return 0
    else:
        print("⚠️  Some issues detected - review details above")
        print()
        print("Common fixes:")
        print("- If prices are stale: Check if daily pipeline is running on main branch")
        print("- If features are stale: Run pipeline manually to catch up")
        print("- If no alerts: Check if templates are firing (may be normal)")
        return 1


if __name__ == "__main__":
    import pandas as pd
    sys.exit(main())
