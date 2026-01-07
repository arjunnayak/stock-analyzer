#!/usr/bin/env python3
"""
Debug script to diagnose date issue in daily pipeline.
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.ingest.eodhd_client import EODHDClient
from src.storage.r2_client import R2Client


def check_system_date():
    """Check what date the system thinks it is."""
    print("=" * 70)
    print("SYSTEM DATE CHECK")
    print("=" * 70)
    print(f"date.today(): {date.today()}")
    print(f"datetime.now(): {datetime.now()}")
    print(f"datetime.utcnow(): {datetime.utcnow()}")
    print()


def check_latest_r2_data():
    """Check what the latest data in R2 is."""
    print("=" * 70)
    print("LATEST R2 DATA CHECK")
    print("=" * 70)

    r2 = R2Client()

    # Check a few tickers
    test_tickers = ["AAPL", "MSFT", "GOOGL"]

    for ticker in test_tickers:
        try:
            # List files for December 2025 and January 2026
            for year_month in ["2025/12", "2026/01"]:
                key = f"prices/v1/{ticker}/{year_month}/data.parquet"
                try:
                    df = r2.read_parquet(key)
                    if not df.empty:
                        latest_date = df['date'].max()
                        print(f"✓ {ticker} {year_month}: Latest date = {latest_date}")
                    else:
                        print(f"  {ticker} {year_month}: Empty file")
                except Exception as e:
                    print(f"  {ticker} {year_month}: File not found")
        except Exception as e:
            print(f"✗ Error checking {ticker}: {e}")
    print()


def check_eodhd_api():
    """Check if EODHD API returns data for recent dates."""
    print("=" * 70)
    print("EODHD API CHECK")
    print("=" * 70)

    client = EODHDClient()

    # Test fetching data for last 10 days
    end_date = date.today()
    start_date = end_date - timedelta(days=10)

    print(f"Requesting data from {start_date} to {end_date}")
    print()

    df = client.get_prices("AAPL", start_date=start_date, end_date=end_date)

    if not df.empty:
        print(f"✓ Received {len(df)} rows from EODHD API")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        print()
        print("Last 5 rows:")
        print(df[['date', 'close']].tail())
    else:
        print("✗ No data received from EODHD API")
    print()


def main():
    """Run all diagnostic checks."""
    print("\n" + "=" * 70)
    print("DATE ISSUE DIAGNOSTIC")
    print("=" * 70)
    print()

    check_system_date()
    check_latest_r2_data()
    check_eodhd_api()

    print("=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
