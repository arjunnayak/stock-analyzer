#!/usr/bin/env python3
"""
CLI script to ingest price data from EODHD API to R2 storage.

This script fetches the latest price data for tickers in the watchlist
and updates R2 storage. Designed to run daily before metric computation.
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.ingest.ingest_prices import PriceIngester


def get_watchlist_tickers() -> list[str]:
    """
    Get all unique tickers from active watchlists.

    Returns:
        List of unique ticker symbols
    """
    client = config.get_supabase_client()

    # Get all entities that are in active watchlists
    response = (
        client.table("watchlists")
        .select("entity_id, entities(ticker)")
        .eq("alerts_enabled", True)
        .execute()
    )

    # Extract unique tickers
    tickers = set()
    for row in response.data:
        entity = row.get("entities")
        if entity and entity.get("ticker"):
            tickers.add(entity["ticker"])

    return sorted(list(tickers))


def parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD date string."""
    return date.fromisoformat(date_str)


def main():
    """Run price data ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest price data from EODHD API to R2 storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest all watchlist tickers (default: last 7 days)
  python scripts/ingest_prices.py

  # Ingest specific tickers
  python scripts/ingest_prices.py --tickers AAPL MSFT GOOGL

  # Ingest with custom date range
  python scripts/ingest_prices.py --start-date 2024-01-01 --end-date 2024-12-31

  # Ingest from ticker file
  python scripts/ingest_prices.py --ticker-file tickers.txt

  # Incremental update (last N days)
  python scripts/ingest_prices.py --days 30
        """,
    )

    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Specific tickers to ingest (space-separated)",
    )

    parser.add_argument(
        "--ticker-file",
        help="File containing tickers (one per line)",
    )

    parser.add_argument(
        "--start-date",
        type=parse_date,
        help="Start date (YYYY-MM-DD). If not provided, defaults to --days ago",
    )

    parser.add_argument(
        "--end-date",
        type=parse_date,
        help="End date (YYYY-MM-DD). If not provided, defaults to today",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7). Ignored if --start-date is provided",
    )

    parser.add_argument(
        "--exchange",
        default="US",
        help="Exchange code (default: US)",
    )

    parser.add_argument(
        "--watchlist",
        action="store_true",
        help="Ingest all tickers from active watchlists (default if no tickers specified)",
    )

    args = parser.parse_args()

    # Determine tickers to ingest
    tickers: Optional[list[str]] = None

    if args.tickers:
        tickers = args.tickers
    elif args.ticker_file:
        with open(args.ticker_file) as f:
            tickers = [line.strip() for line in f if line.strip()]
    elif args.watchlist or (not args.tickers and not args.ticker_file):
        # Default: fetch from watchlist
        print("Fetching tickers from active watchlists...")
        tickers = get_watchlist_tickers()

        if not tickers:
            print("⚠️  No tickers found in active watchlists")
            return 1

        print(f"Found {len(tickers)} unique tickers in watchlists")

    if not tickers:
        print("❌ ERROR: No tickers specified")
        return 1

    # Determine date range
    end_date = args.end_date or date.today()

    if args.start_date:
        start_date = args.start_date
    else:
        start_date = end_date - timedelta(days=args.days)

    # Run ingestion
    print("\n" + "=" * 70)
    print("PRICE DATA INGESTION")
    print("=" * 70)
    print(f"Environment: {config.env}")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Tickers: {len(tickers)}")
    print(f"Exchange: {args.exchange}")
    print()

    ingester = PriceIngester()
    summary = ingester.ingest_batch(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        exchange=args.exchange,
    )

    # Print summary
    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"Total Tickers: {summary['total_tickers']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Rows Fetched from API: {summary['rows_fetched']:,}")
    print(f"Rows Stored in R2: {summary['rows_stored']:,}")
    print(f"Net New Rows: {summary['rows_stored'] - summary.get('rows_existing', 0):+,}")
    print(f"Total Files: {summary['total_files']}")
    print()

    for result in summary["results"]:
        status_icon = "✓" if result["status"] == "success" else "✗"
        fetched = result.get('rows_fetched', result.get('rows', 0))
        stored = result.get('rows_stored', result.get('rows', 0))
        print(f"{status_icon} {result['ticker']}: {fetched} fetched → {stored} stored, {result['files']} files")

    # Exit with error if any failed
    if summary["failed"] > 0:
        print(f"\n⚠️  {summary['failed']} ticker(s) failed")
        return 1

    print("\n✅ Ingestion completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
