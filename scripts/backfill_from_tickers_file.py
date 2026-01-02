#!/usr/bin/env python3
"""
Backfill features for tickers from tickers.txt file.

This script:
1. Reads tickers from tickers.txt (skips comments and blank lines)
2. Runs backfill_features() for the specified date range
3. Writes features to R2 and updates indicator_state in Supabase

Usage:
    # Backfill with default date range (2 years)
    ENV=REMOTE python scripts/backfill_from_tickers_file.py

    # Backfill with custom date range
    ENV=REMOTE python scripts/backfill_from_tickers_file.py --start-date 2023-01-01 --end-date 2025-12-31

    # Dry run (preview without writing)
    ENV=REMOTE python scripts/backfill_from_tickers_file.py --dry-run
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.features.features_compute import FeaturesComputer


def read_tickers_from_file(file_path: str) -> list[str]:
    """
    Read tickers from a file.

    Args:
        file_path: Path to tickers file

    Returns:
        List of ticker symbols
    """
    tickers = []

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()

            # Skip comments and blank lines
            if not line or line.startswith("#"):
                continue

            tickers.append(line.upper())

    return tickers


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill features for tickers from tickers.txt"
    )
    parser.add_argument(
        "--tickers-file",
        type=str,
        default="tickers.txt",
        help="Path to tickers file (default: tickers.txt)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Defaults to 2 years ago.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing to R2 or Supabase",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of tickers to process in parallel (default: 5)",
    )

    args = parser.parse_args()

    # Parse dates
    if args.end_date:
        end_date = date.fromisoformat(args.end_date)
    else:
        end_date = date.today()

    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
    else:
        # Default to 2 years ago
        start_date = end_date - timedelta(days=2 * 365)

    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 18 + "FEATURES BACKFILL" + " " * 33 + "║")
    print("╚" + "=" * 68 + "╝")

    print(f"\nDate range: {start_date} to {end_date}")
    print(f"Tickers file: {args.tickers_file}")

    # Read tickers
    try:
        tickers = read_tickers_from_file(args.tickers_file)
    except FileNotFoundError:
        print(f"\n✗ Error: File not found: {args.tickers_file}")
        print(f"  Please create {args.tickers_file} with one ticker per line")
        sys.exit(1)

    if not tickers:
        print(f"\n✗ Error: No tickers found in {args.tickers_file}")
        sys.exit(1)

    print(f"Tickers to backfill: {len(tickers)}")
    print(f"  {', '.join(tickers)}")

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No data will be written")

    # Confirm
    if not args.dry_run:
        print("\n" + "⚠️ " * 35)
        print("This will write features to R2 and update Supabase!")
        print("⚠️ " * 35)
        confirmation = input("\nType 'BACKFILL' to confirm: ")
        if confirmation != "BACKFILL":
            print("Aborted.")
            sys.exit(0)

    # Run backfill
    print("\nStarting backfill...")

    with FeaturesComputer() as computer:
        result = computer.backfill_features(
            start_date=start_date,
            end_date=end_date,
            tickers=tickers,
            dry_run=args.dry_run,
        )

    # Summary
    print("\n" + "=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)
    print(f"Status: {result['status']}")
    print(f"Tickers processed: {result['tickers_processed']}")
    print(f"Tickers failed: {result.get('tickers_failed', 0)}")
    print(f"Total rows: {result.get('total_rows', 0)}")
    print(f"Date range: {result.get('date_range', 'N/A')}")

    if result["status"] in ("success", "dry_run"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
