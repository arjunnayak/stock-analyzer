#!/usr/bin/env python3
"""
Batch Metrics Computation CLI

Computes valuation and technical metrics from stored price and fundamental data.

Usage:
    # Single ticker (for testing)
    python scripts/compute_metrics.py --ticker UBER

    # Multiple tickers
    python scripts/compute_metrics.py --tickers AAPL MSFT GOOGL

    # From file
    python scripts/compute_metrics.py --ticker-file tickers.txt

    # All tickers
    python scripts/compute_metrics.py --all

    # Date range
    python scripts/compute_metrics.py --ticker UBER --start-date 2020-01-01

    # Only technical or valuation
    python scripts/compute_metrics.py --ticker UBER --technical-only
    python scripts/compute_metrics.py --ticker UBER --valuation-only

    # Force recompute (ignore existing data)
    python scripts/compute_metrics.py --ticker UBER --force

    # Dry run
    python scripts/compute_metrics.py --ticker UBER --dry-run
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reader import TimeSeriesReader
from src.signals.compute import MetricsComputer


def load_tickers_from_file(file_path: str) -> list[str]:
    """Load ticker list from file (one per line)."""
    with open(file_path) as f:
        return [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Batch metrics computation from stored data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Ticker selection (mutually exclusive)
    ticker_group = parser.add_mutually_exclusive_group(required=True)
    ticker_group.add_argument("--ticker", help="Single ticker (for testing)")
    ticker_group.add_argument("--tickers", nargs="+", help="List of ticker symbols")
    ticker_group.add_argument("--ticker-file", help="File containing ticker symbols (one per line)")
    ticker_group.add_argument("--all", action="store_true", help="All tickers in storage")

    # Date range
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")

    # Metric selection
    parser.add_argument("--technical-only", action="store_true", help="Only compute technical metrics")
    parser.add_argument("--valuation-only", action="store_true", help="Only compute valuation metrics")

    # Options
    parser.add_argument(
        "--force", action="store_true", help="Recompute all dates (ignore existing data)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    return parser.parse_args()


def main():
    """Run batch metrics computation."""
    args = parse_args()

    start_time = time.time()

    print("=" * 70)
    print("BATCH METRICS COMPUTATION")
    print("=" * 70)

    # Parse dates
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date() if args.start_date else None
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else None

    if start_date and end_date and start_date > end_date:
        print("❌ ERROR: start-date must be before end-date")
        return 1

    # Determine mode
    mode = "Force recompute all" if args.force else "Incremental (compute missing dates)"
    metrics_mode = (
        "Technical only"
        if args.technical_only
        else "Valuation only" if args.valuation_only else "Technical + Valuation"
    )

    print(f"Mode: {mode}")
    print(f"Metrics: {metrics_mode}")

    if start_date or end_date:
        print(f"Date range: {start_date or 'beginning'} to {end_date or 'latest'}")

    if args.dry_run:
        print("\n🏃 DRY RUN MODE - No data will be written")

    # Get ticker list
    reader = TimeSeriesReader()

    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
    elif args.ticker_file:
        tickers = load_tickers_from_file(args.ticker_file)
        print(f"Loaded {len(tickers)} tickers from {args.ticker_file}")
    else:  # --all
        tickers = reader.list_available_tickers(dataset="prices")
        print(f"Found {len(tickers)} tickers in storage")

    if not tickers:
        print("❌ ERROR: No tickers to process")
        return 1

    print(f"\nProcessing {len(tickers)} ticker(s)")
    print()

    # Initialize computer
    computer = MetricsComputer()

    # Run computation for each ticker
    results = []

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker}")
        print("-" * 70)

        if args.dry_run:
            # Dry run: just check what data exists
            prices = reader.get_prices(ticker, start_date, end_date)
            fundamentals = reader.get_fundamentals(ticker)

            print(f"  Price rows available: {len(prices)}")
            print(f"  Fundamental rows available: {len(fundamentals)}")
            print(f"  🏃 DRY RUN - Would compute metrics for this ticker")

            results.append({"ticker": ticker, "status": "dry_run", "total_rows": 0, "total_files": 0})
        else:
            # Actual computation
            try:
                result = computer.compute_all_metrics(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    technical_only=args.technical_only,
                    valuation_only=args.valuation_only,
                    force=args.force,
                )
                results.append(result)
            except Exception as e:
                print(f"  ✗ Error processing {ticker}: {e}")
                if args.verbose:
                    import traceback

                    traceback.print_exc()

                results.append({
                    "ticker": ticker,
                    "status": "error",
                    "total_rows": 0,
                    "total_files": 0,
                    "error": str(e),
                })

    # Summary
    elapsed_time = time.time() - start_time

    print("\n" + "=" * 70)
    print("COMPUTATION SUMMARY")
    print("=" * 70)

    total_rows = sum(r.get("total_rows", 0) for r in results)
    total_files = sum(r.get("total_files", 0) for r in results)

    success = sum(1 for r in results if r.get("status") == "success")
    partial = sum(1 for r in results if r.get("status") == "partial_success")
    failed = sum(1 for r in results if r.get("status") in ["failed", "error"])
    no_data = sum(
        1
        for r in results
        if r.get("status") in ["no_price_data", "no_fundamental_data", "up_to_date"]
    )

    print(f"Total tickers processed: {len(tickers)}")
    print(f"Successful: {success}")
    if partial > 0:
        print(f"Partial success: {partial}")
    if failed > 0:
        print(f"Failed: {failed}")
    if no_data > 0:
        print(f"No data / Up to date: {no_data}")

    if not args.dry_run:
        print(f"Total signal rows computed: {total_rows:,}")
        print(f"Total files written: {total_files}")

    print(f"Elapsed time: {elapsed_time:.1f} seconds")

    if args.dry_run:
        print("\n🏃 DRY RUN - No data was written")

    # Show errors if any
    errors = [r for r in results if r.get("status") in ["error", "failed"]]
    if errors and not args.verbose:
        print("\nErrors occurred. Use --verbose for details.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
