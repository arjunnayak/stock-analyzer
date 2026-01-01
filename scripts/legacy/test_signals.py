#!/usr/bin/env python3
"""
Test script for signal computation and alert generation.

This script demonstrates:
1. Computing technical signals from price data
2. Detecting state changes
3. Generating structured alerts
4. Running the full daily evaluation pipeline

Prerequisites:
- Docker services running (make start)
- Price data ingested (make ingest or make test-pipeline)
"""

import sys
from datetime import date, timedelta

from src.reader import TimeSeriesReader
from src.signals.alerts import AlertGenerator, AlertRepository
from src.signals.pipeline import SignalPipeline
from src.signals.state_tracker import StateChange, StateTracker
from src.signals.technical import TechnicalSignals


def test_technical_signals():
    """Test computing technical signals from real data."""
    print("=" * 70)
    print("1. TESTING TECHNICAL SIGNAL COMPUTATION")
    print("=" * 70)

    reader = TimeSeriesReader()

    # Get available tickers
    tickers = reader.list_available_tickers()

    if not tickers:
        print("❌ ERROR: No price data in storage!")
        print("   Run: make ingest")
        return False

    ticker = tickers[0]
    print(f"Using ticker: {ticker}")

    # Fetch recent data
    df = reader.get_latest_prices(ticker, days=365)

    if df.empty:
        print(f"❌ ERROR: No data for {ticker}")
        return False

    print(f"✓ Loaded {len(df)} days of price data")

    # Compute signals
    df_with_signals = TechnicalSignals.compute_all_technical_signals(df)

    print("\nSignals computed:")
    print(df_with_signals[["date", "close", "sma_20", "sma_50", "sma_200", "trend_position"]].tail(10))

    # Get latest
    latest = TechnicalSignals.get_latest_signals(df_with_signals)
    print(f"\nLatest signals for {ticker}:")
    print(f"  Date: {latest.get('date')}")
    print(f"  Close: ${latest.get('close'):.2f}")
    print(f"  SMA-200: ${latest.get('sma_200'):.2f}" if latest.get("sma_200") else "  SMA-200: Not available")
    print(f"  Trend: {latest.get('trend_position')}")

    # Check for crossovers
    crossovers = df_with_signals[df_with_signals["crossover"].notna()]
    print(f"\nCrossovers detected: {len(crossovers)}")

    if not crossovers.empty:
        print("\nRecent crossovers:")
        print(crossovers[["date", "close", "sma_200", "crossover"]].tail(5))

    print("\n✅ Technical signals OK")
    return True


def test_state_tracking():
    """Test state tracking and change detection."""
    print("\n" + "=" * 70)
    print("2. TESTING STATE TRACKING")
    print("=" * 70)

    with StateTracker() as tracker:
        # Get test user and entity using Supabase client
        from src.config import config

        client = config.get_supabase_client()

        # Get first user
        user_response = client.table("users").select("id, email").limit(1).execute()
        user = user_response.data[0] if user_response.data else None

        # Get first entity
        entity_response = client.table("entities").select("id, ticker").limit(1).execute()
        entity = entity_response.data[0] if entity_response.data else None

        if not user or not entity:
            print("❌ ERROR: No test data in database")
            return False

        print(f"Testing with user: {user['email']}, ticker: {entity['ticker']}")

        # Get current state
        state = tracker.get_state(user["id"], entity["id"], entity["ticker"])

        print(f"\nCurrent state:")
        print(f"  Trend position: {state.last_trend_position}")
        print(f"  Price: ${state.last_price_close}" if state.last_price_close else "  Price: Not set")
        print(f"  Last evaluated: {state.last_evaluated_at}")

        # Simulate a state change
        print("\nSimulating trend change (below → above)...")

        change = tracker.detect_trend_change(
            previous_state=state, current_trend_position="above_sma", current_price=150.0
        )

        if change:
            print(f"✓ Change detected!")
            print(f"  Type: {change.change_type}")
            print(f"  {change.old_value} → {change.new_value}")
            print(f"  Should alert: {change.should_alert}")
        else:
            print("No change detected (this is expected if state unchanged)")

        print("\n✅ State tracking OK")
        return True


def test_alert_generation():
    """Test generating structured alerts."""
    print("\n" + "=" * 70)
    print("3. TESTING ALERT GENERATION")
    print("=" * 70)

    from datetime import datetime

    # Create sample state change
    change = StateChange(
        ticker="AAPL",
        change_type="trend_position",
        old_value="below_sma",
        new_value="above_sma",
        timestamp=datetime.now(),
        should_alert=True,
        alert_type="trend_break",
    )

    # Generate alert
    alert = AlertGenerator.generate_trend_break_alert(
        ticker="AAPL", change=change, current_price=185.50, sma_200=175.00, previous_price=172.00
    )

    print("Generated Alert:")
    print("-" * 70)
    print(alert.format_email())

    print("✅ Alert generation OK")
    return True


def test_full_pipeline():
    """Test the full signal evaluation pipeline."""
    print("\n" + "=" * 70)
    print("4. TESTING FULL SIGNAL PIPELINE")
    print("=" * 70)

    with SignalPipeline() as pipeline:
        # Get watchlists
        watchlists = pipeline.get_active_watchlists()

        if not watchlists:
            print("⚠️  No active watchlists found")
            print("   This is OK - the pipeline works but has no data to process")
            return True

        print(f"Found {len(watchlists)} active watchlist items")

        # Run evaluation for first item
        item = watchlists[0]
        print(f"\nEvaluating {item['ticker']} for {item['email']}...")

        alerts = pipeline.evaluate_ticker_for_user(
            user_id=item["user_id"], entity_id=item["entity_id"], ticker=item["ticker"]
        )

        print(f"\nGenerated {len(alerts)} alert(s)")

        if alerts:
            print("\nAlert details:")
            for alert in alerts:
                print("-" * 70)
                print(alert.format_email())

        print("\n✅ Full pipeline OK")
        return True


def test_daily_evaluation():
    """Test running the full daily evaluation."""
    print("\n" + "=" * 70)
    print("5. TESTING DAILY EVALUATION (FULL BATCH)")
    print("=" * 70)

    with SignalPipeline() as pipeline:
        summary = pipeline.run_daily_evaluation()

        # Show results
        if summary["total_alerts"] > 0:
            print("\n" + "=" * 70)
            print("GENERATED ALERTS")
            print("=" * 70)

            with AlertRepository() as repo:
                # Get first user from results
                for result in summary["results"]:
                    if result["alerts_generated"] > 0:
                        # This would show the alerts, but we need user_id
                        # For now, just show the summary
                        print(f"\n{result['ticker']}: {result['alerts_generated']} alert(s)")

        print("\n✅ Daily evaluation OK")
        return True


def main():
    """Run all signal tests."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "SIGNAL PIPELINE TEST" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝")

    tests = [
        ("Technical Signals", test_technical_signals),
        ("State Tracking", test_state_tracking),
        ("Alert Generation", test_alert_generation),
        ("Full Pipeline", test_full_pipeline),
        ("Daily Evaluation", test_daily_evaluation),
    ]

    results = {}

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ UNEXPECTED ERROR in {name}: {e}")
            import traceback

            traceback.print_exc()
            results[name] = False

        # Continue even on failure to see all results

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for name, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"{icon} {name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nThe signal computation and alert system is working!")
        print("\nNext steps:")
        print("  - Set up email delivery")
        print("  - Create frontend UI")
        print("  - Schedule daily batch job")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nPlease review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
