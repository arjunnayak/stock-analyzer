#!/usr/bin/env python3
"""
Backfill historical daily features.

This script runs the daily features computation for historical dates to build up
feature history. This is needed before the weekly stats pipeline can run.

Usage:
    # Backfill last 120 trading days (~6 months)
    ENV=REMOTE python scripts/backfill_features_historical.py --days 120

    # Backfill specific date range
    ENV=REMOTE python scripts/backfill_features_historical.py --start-date 2024-01-01 --end-date 2024-12-31

    # Dry run to see what would be processed
    ENV=REMOTE python scripts/backfill_features_historical.py --days 30 --dry-run
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.features.pipeline_daily import DailyPipeline
from src.reader import TimeSeriesReader
from src.storage.r2_client import R2Client
from src.storage.supabase_db import SupabaseDB


def get_trading_dates(start_date: date, end_date: date, tickers: list[str]) -> list[date]:
    """
    Get list of dates that have price data (trading days).

    Args:
        start_date: Start date
        end_date: End date
        tickers: List of tickers to sample

    Returns:
        List of trading dates (dates with price data)
    """
    print(f"\nDiscovering trading dates from {start_date} to {end_date}...")
    reader = TimeSeriesReader()

    # Sample a few tickers to find trading dates
    sample_ticker = tickers[0] if tickers else None
    if not sample_ticker:
        print("No tickers available")
        return []

    try:
        df = reader.get_prices(sample_ticker, start_date, end_date)
        if df.empty:
            print(f"No price data for {sample_ticker} in date range")
            return []

        # Extract dates
        dates = df["date"].tolist()
        dates = [d.date() if hasattr(d, "date") else date.fromisoformat(str(d)) for d in dates]
        dates = sorted(set(dates))

        print(f"Found {len(dates)} trading dates")
        return dates

    except Exception as e:
        print(f"Error discovering trading dates: {e}")
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill historical daily features for valuation stats"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of calendar days to backfill (e.g., 120 for ~6 months)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        help="Specific tickers to process (default: all active)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually running",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force regenerate features even if they already exist",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.days and not (args.start_date and args.end_date):
        print("Error: Must specify either --days or both --start-date and --end-date")
        sys.exit(1)

    # Determine date range
    if args.days:
        end_date = date.today() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=args.days)
    else:
        start_date = date.fromisoformat(args.start_date)
        end_date = date.fromisoformat(args.end_date)

    print("\n" + "=" * 70)
    print("BACKFILL HISTORICAL FEATURES")
    print("=" * 70)
    print(f"Date range: {start_date} to {end_date}")

    # Get active tickers
    db = SupabaseDB()
    tickers = args.tickers or db.get_active_tickers()
    if not tickers:
        print("No active tickers found")
        sys.exit(1)

    print(f"Tickers: {len(tickers)}")

    # Discover trading dates
    trading_dates = get_trading_dates(start_date, end_date, tickers)
    if not trading_dates:
        print("No trading dates found in range")
        sys.exit(1)

    # Filter to dates in range
    trading_dates = [d for d in trading_dates if start_date <= d <= end_date]

    # Check which dates already have features
    if not args.force:
        print("\nChecking for existing features...")
        r2 = R2Client()
        existing_dates = r2.list_feature_dates(limit=5000)
        existing_set = set(existing_dates)

        dates_to_process = [d for d in trading_dates if d not in existing_set]
        dates_skipped = len(trading_dates) - len(dates_to_process)

        print(f"  Existing: {dates_skipped} dates")
        print(f"  To process: {len(dates_to_process)} dates")

        trading_dates = dates_to_process
    else:
        dates_to_process = trading_dates
        print(f"\n[FORCE] Will regenerate all {len(dates_to_process)} dates")

    if not dates_to_process:
        print("\n✓ All dates already have features!")
        sys.exit(0)

    print(f"\nWill process {len(dates_to_process)} dates")

    if args.dry_run:
        print("\n[DRY RUN] Dates to process:")
        for d in dates_to_process[:10]:
            print(f"  {d}")
        if len(dates_to_process) > 10:
            print(f"  ... and {len(dates_to_process) - 10} more")
        sys.exit(0)

    # Process each date
    print("\n" + "=" * 70)
    print("PROCESSING")
    print("=" * 70)

    success_count = 0
    error_count = 0

    with DailyPipeline() as pipeline:
        for i, run_date in enumerate(dates_to_process, 1):
            print(f"\n[{i}/{len(dates_to_process)}] Processing {run_date}...")

            try:
                result = pipeline.run(
                    run_date=run_date,
                    tickers=args.tickers,
                    skip_alerts=True,  # Don't send alerts for historical data
                    skip_snapshot=False,  # Create snapshots
                    skip_templates=True,  # Don't evaluate templates
                    dry_run=False,
                )

                if result["status"] == "success":
                    success_count += 1
                    print(f"  ✓ Success ({result.get('tickers_processed', 0)} tickers)")
                else:
                    error_count += 1
                    print(f"  ✗ Failed: {result.get('status')}")

            except Exception as e:
                error_count += 1
                print(f"  ✗ Error: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)
    print(f"Total dates: {len(dates_to_process)}")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")

    if success_count > 0:
        print("\n✓ You can now run the weekly stats pipeline:")
        print("  ENV=REMOTE python -m src.features.pipeline_weekly_stats --dry-run")

    sys.exit(0 if error_count == 0 else 1)


if __name__ == "__main__":
    main()
