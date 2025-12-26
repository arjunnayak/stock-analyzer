"""
Read time-series data from R2 storage.

Provides high-level utilities for reading stored market data.
"""

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from src.storage.r2_client import R2Client


class TimeSeriesReader:
    """High-level reader for time-series data from R2."""

    def __init__(self):
        """Initialize reader with R2 client."""
        self.r2 = R2Client()

    def get_prices(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Get price data for a ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date (defaults to 1 year ago)
            end_date: End date (defaults to today)

        Returns:
            DataFrame with price data
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        return self.r2.get_timeseries("prices", ticker, start_date, end_date)

    def get_latest_prices(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """
        Get most recent price data for a ticker.

        Args:
            ticker: Stock ticker
            days: Number of days to look back (default: 30)

        Returns:
            DataFrame with recent price data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        return self.get_prices(ticker, start_date, end_date)

    def get_multi_ticker_prices(
        self,
        tickers: list[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Get price data for multiple tickers.

        Args:
            tickers: List of stock tickers
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping ticker -> DataFrame
        """
        results = {}

        for ticker in tickers:
            df = self.get_prices(ticker, start_date, end_date)
            if not df.empty:
                results[ticker] = df

        return results

    def get_closing_prices(
        self,
        tickers: list[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Get closing prices for multiple tickers in wide format.

        Args:
            tickers: List of stock tickers
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with date index and ticker columns containing close prices
        """
        prices_dict = self.get_multi_ticker_prices(tickers, start_date, end_date)

        if not prices_dict:
            return pd.DataFrame()

        # Extract close prices and combine
        close_prices = {}
        for ticker, df in prices_dict.items():
            if not df.empty and "close" in df.columns:
                close_prices[ticker] = df.set_index("date")["close"]

        if not close_prices:
            return pd.DataFrame()

        # Combine into wide format
        result = pd.DataFrame(close_prices)
        result.index.name = "date"

        return result

    def get_fundamentals(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Get fundamental data for a ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date (defaults to 5 years ago)
            end_date: End date (defaults to today)

        Returns:
            DataFrame with fundamental data
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=5 * 365)

        return self.r2.get_timeseries("fundamentals", ticker, start_date, end_date)

    def list_available_tickers(self, dataset: str = "prices") -> list[str]:
        """
        List all tickers that have data in storage.

        Args:
            dataset: Dataset type (default: prices)

        Returns:
            List of ticker symbols
        """
        keys = self.r2.list_keys(prefix=f"{dataset}/v1/")

        # Extract unique tickers from keys
        # Pattern: {dataset}/v1/{ticker}/{year}/{month}/data.parquet
        tickers = set()
        for key in keys:
            parts = key.split("/")
            if len(parts) >= 3:
                tickers.add(parts[2])  # ticker is the 3rd part

        return sorted(list(tickers))


def main():
    """Demonstrate reading data."""
    print("Time-Series Data Reader")
    print("=" * 60)

    reader = TimeSeriesReader()

    # List available tickers
    print("\nAvailable tickers in storage:")
    tickers = reader.list_available_tickers()
    print(f"  {', '.join(tickers) if tickers else 'None yet'}")

    if not tickers:
        print("\n⚠️  No data in storage yet. Run ingest_prices.py first!")
        return

    # Read prices for first ticker
    ticker = tickers[0]
    print(f"\n{'=' * 60}")
    print(f"Reading last 30 days of {ticker}")
    print(f"{'=' * 60}")

    df = reader.get_latest_prices(ticker, days=30)

    if not df.empty:
        print(f"\nRetrieved {len(df)} rows")
        print("\nFirst 5 rows:")
        print(df.head())
        print("\nLast 5 rows:")
        print(df.tail())
        print("\nBasic statistics:")
        print(df[["open", "high", "low", "close", "volume"]].describe())

    # Multi-ticker example
    if len(tickers) >= 3:
        test_tickers = tickers[:3]
        print(f"\n{'=' * 60}")
        print(f"Reading closing prices for: {', '.join(test_tickers)}")
        print(f"{'=' * 60}")

        closes = reader.get_closing_prices(test_tickers, start_date=date(2024, 12, 1))

        if not closes.empty:
            print(f"\nRetrieved {len(closes)} dates")
            print("\nClosing prices (first 10 rows):")
            print(closes.head(10))


if __name__ == "__main__":
    main()
