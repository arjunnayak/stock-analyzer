#!/usr/bin/env python3
"""
Check what recent price data exists in R2 storage.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.r2_client import R2Client


def check_price_files():
    """Check what price files exist for recent dates."""
    r2 = R2Client()

    # Check December 2025 and January 2026
    test_tickers = ["AAPL", "MSFT", "GOOGL", "TSLA"]

    print("=" * 70)
    print("CHECKING R2 PRICE DATA FILES")
    print("=" * 70)
    print()

    for ticker in test_tickers:
        print(f"\n{ticker}:")
        print("-" * 70)

        # Check December 2025
        dec_key = f"prices/v1/{ticker}/2025/12/data.parquet"
        dec_df = r2.get_parquet(dec_key)
        if dec_df is not None and not dec_df.empty:
            dec_df['date'] = pd.to_datetime(dec_df['date'])
            latest_dec = dec_df['date'].max()
            print(f"  ✓ 2025/12: {len(dec_df)} rows, latest = {latest_dec.date()}")
        else:
            print(f"  ✗ 2025/12: No data")

        # Check January 2026
        jan_key = f"prices/v1/{ticker}/2026/01/data.parquet"
        jan_df = r2.get_parquet(jan_key)
        if jan_df is not None and not jan_df.empty:
            jan_df['date'] = pd.to_datetime(jan_df['date'])
            earliest_jan = jan_df['date'].min()
            latest_jan = jan_df['date'].max()
            print(f"  ✓ 2026/01: {len(jan_df)} rows, {earliest_jan.date()} to {latest_jan.date()}")
        else:
            print(f"  ✗ 2026/01: No data")

    print("\n" + "=" * 70)
    print("CHECKING PRICE SNAPSHOTS")
    print("=" * 70)
    print()

    # Check snapshots for recent dates
    today = date.today()
    for days_ago in range(10):
        check_date = today - timedelta(days=days_ago)
        key = f"prices_snapshots/v1/date={check_date}/close.parquet"
        df = r2.get_parquet(key)
        if df is not None and not df.empty:
            print(f"  ✓ {check_date}: Snapshot exists with {len(df)} tickers")
        else:
            print(f"  ✗ {check_date}: No snapshot")


if __name__ == "__main__":
    import pandas as pd
    check_price_files()
