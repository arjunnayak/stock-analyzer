#!/usr/bin/env python3
"""
Verify data availability in R2 storage.

Checks for presence of:
- Price data (prices_daily, prices_intraday)
- Fundamentals data (fundamentals_income, fundamentals_balance, fundamentals_cash)
- Technical signals (signals_technical)
- Valuation signals (signals_valuation)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_r2_client, get_supabase_client


# Data types to check
DATA_TYPES = {
    'prices': ['prices_daily', 'prices_intraday'],
    'fundamentals': ['fundamentals_income', 'fundamentals_balance', 'fundamentals_cash'],
    'signals': ['signals_technical', 'signals_valuation'],
}


def get_watchlist_tickers() -> list[str]:
    """Get all unique tickers from active watchlists."""
    try:
        client = get_supabase_client()
        response = (
            client.table("watchlists")
            .select("entity_id, entities(ticker)")
            .eq("alerts_enabled", True)
            .execute()
        )

        tickers = set()
        for row in response.data:
            entity = row.get("entities")
            if entity and entity.get("ticker"):
                tickers.add(entity["ticker"])

        return sorted(list(tickers))
    except Exception as e:
        print(f"Error fetching watchlist tickers: {e}", file=sys.stderr)
        return []


def check_r2_data_availability(r2_client, ticker: str, data_type: str) -> dict:
    """
    Check if data exists in R2 for a given ticker and data type.

    Args:
        r2_client: R2 client instance
        ticker: Stock ticker symbol
        data_type: Type of data (e.g., 'prices_daily', 'fundamentals_income')

    Returns:
        Dict with 'exists', 'file_count', 'latest_file', 'size_bytes'
    """
    prefix = f"{data_type}/{ticker}/"

    try:
        files = r2_client.list_objects(prefix=prefix)

        if not files:
            return {
                'exists': False,
                'file_count': 0,
                'latest_file': None,
                'size_bytes': 0
            }

        # Get latest file by modification time
        latest_file = max(files, key=lambda x: x.get('LastModified', datetime.min))
        total_size = sum(f.get('Size', 0) for f in files)

        return {
            'exists': True,
            'file_count': len(files),
            'latest_file': latest_file.get('Key', '').split('/')[-1],
            'latest_modified': latest_file.get('LastModified'),
            'size_bytes': total_size
        }
    except Exception as e:
        return {
            'exists': False,
            'error': str(e),
            'file_count': 0,
            'latest_file': None,
            'size_bytes': 0
        }


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def verify_ticker_data(r2_client, ticker: str, verbose: bool = False) -> dict:
    """
    Verify all data types for a single ticker.

    Args:
        r2_client: R2 client instance
        ticker: Stock ticker symbol
        verbose: Print detailed info

    Returns:
        Dict with verification results
    """
    results = {
        'ticker': ticker,
        'timestamp': datetime.now().isoformat(),
        'data_types': {}
    }

    if verbose:
        print(f"\n{'='*70}")
        print(f"Checking: {ticker}")
        print('='*70)

    for category, data_types in DATA_TYPES.items():
        category_results = {}

        for data_type in data_types:
            check_result = check_r2_data_availability(r2_client, ticker, data_type)
            category_results[data_type] = check_result

            if verbose:
                status = "✓" if check_result['exists'] else "✗"
                print(f"  [{status}] {data_type:25s}", end="")

                if check_result['exists']:
                    print(f" {check_result['file_count']:3d} files, "
                          f"{format_size(check_result['size_bytes']):>10s}, "
                          f"latest: {check_result['latest_file']}")
                else:
                    error = check_result.get('error', 'No data')
                    print(f" {error}")

        results['data_types'][category] = category_results

    return results


def generate_summary(all_results: list[dict]) -> dict:
    """Generate summary statistics from all verification results."""
    summary = {
        'total_tickers': len(all_results),
        'by_data_type': {},
        'missing_data': []
    }

    # Flatten data types
    all_data_types = []
    for category_types in DATA_TYPES.values():
        all_data_types.extend(category_types)

    # Count availability for each data type
    for data_type in all_data_types:
        available = 0
        missing = 0

        for result in all_results:
            # Find this data type in the result
            found = False
            for category_data in result['data_types'].values():
                if data_type in category_data:
                    if category_data[data_type]['exists']:
                        available += 1
                    else:
                        missing += 1
                        summary['missing_data'].append({
                            'ticker': result['ticker'],
                            'data_type': data_type
                        })
                    found = True
                    break

        summary['by_data_type'][data_type] = {
            'available': available,
            'missing': missing,
            'coverage_pct': (available / len(all_results) * 100) if all_results else 0
        }

    return summary


def print_summary(summary: dict):
    """Print summary in a readable format."""
    print("\n" + "="*70)
    print("DATA AVAILABILITY SUMMARY")
    print("="*70)
    print(f"Total Tickers Checked: {summary['total_tickers']}\n")

    # Print by category
    for category, data_types in DATA_TYPES.items():
        print(f"\n{category.upper()}:")
        print("-" * 70)

        for data_type in data_types:
            stats = summary['by_data_type'][data_type]
            coverage = stats['coverage_pct']
            bar_length = 40
            filled = int(bar_length * coverage / 100)
            bar = "█" * filled + "░" * (bar_length - filled)

            print(f"  {data_type:25s} [{bar}] {coverage:5.1f}%  "
                  f"({stats['available']}/{summary['total_tickers']})")

    # Missing data
    if summary['missing_data']:
        print(f"\n\nMISSING DATA DETAILS ({len(summary['missing_data'])} items):")
        print("-" * 70)

        # Group by ticker
        by_ticker = {}
        for item in summary['missing_data']:
            ticker = item['ticker']
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(item['data_type'])

        for ticker, missing_types in sorted(by_ticker.items()):
            print(f"  {ticker:10s} missing: {', '.join(missing_types)}")


def main():
    """Run data availability verification."""
    parser = argparse.ArgumentParser(
        description="Verify data availability in R2 storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check specific tickers
  python scripts/verify_data_availability.py --tickers AAPL MSFT GOOGL

  # Check all watchlist tickers
  python scripts/verify_data_availability.py --watchlist

  # Check with verbose output
  python scripts/verify_data_availability.py --tickers AAPL --verbose
        """
    )

    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Specific tickers to check (space-separated)'
    )

    parser.add_argument(
        '--watchlist',
        action='store_true',
        help='Check all tickers from active watchlists'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed per-ticker information'
    )

    args = parser.parse_args()

    # Determine tickers to check
    if args.tickers:
        tickers = args.tickers
    elif args.watchlist:
        print("Fetching watchlist tickers...")
        tickers = get_watchlist_tickers()
        if not tickers:
            print("❌ No tickers found in active watchlists")
            return 1
        print(f"Found {len(tickers)} tickers in watchlist\n")
    else:
        print("❌ ERROR: Must specify --tickers or --watchlist")
        parser.print_help()
        return 1

    # Initialize R2 client
    print("Connecting to R2 storage...")
    try:
        r2_client = get_r2_client()
    except Exception as e:
        print(f"❌ ERROR: Failed to connect to R2: {e}")
        return 1

    print(f"Checking data availability for {len(tickers)} ticker(s)...\n")

    # Verify each ticker
    all_results = []
    for i, ticker in enumerate(tickers, 1):
        if not args.verbose:
            print(f"[{i}/{len(tickers)}] {ticker}...", end='\r')

        result = verify_ticker_data(r2_client, ticker, verbose=args.verbose)
        all_results.append(result)

    if not args.verbose:
        print()  # Clear progress line

    # Generate and print summary
    summary = generate_summary(all_results)
    print_summary(summary)

    # Exit with error if any data is missing
    if summary['missing_data']:
        print(f"\n⚠️  Some data is missing for {len(set(m['ticker'] for m in summary['missing_data']))} ticker(s)")
        return 0  # Don't fail, just warn
    else:
        print("\n✅ All data types available for all tickers!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
