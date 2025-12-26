"""
EODHD API client for fetching market data.

Fetches price and fundamental data from EODHD API.
"""

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from eodhd import APIClient

from src.config import config


class EODHDClient:
    """Client for fetching data from EODHD API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize EODHD client.

        Args:
            api_key: EODHD API key (defaults to config)
        """
        self.api_key = api_key or config.eodhd_api_key
        if not self.api_key:
            raise ValueError("EODHD API key not configured")

        self.client = APIClient(self.api_key)

    def get_prices(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        exchange: str = "US",
    ) -> pd.DataFrame:
        """
        Fetch historical price data for a ticker.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (defaults to 5 years ago)
            end_date: End date (defaults to today)
            exchange: Exchange code (default: US)

        Returns:
            DataFrame with columns: date, open, high, low, close, adj_close, volume
        """
        # Default date range: last 5 years
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=5 * 365)

        print(f"Fetching prices for {ticker}.{exchange} from {start_date} to {end_date}...")

        try:
            # EODHD API call
            symbol = f"{ticker}.{exchange}"
            data = self.client.get_eod_historical_stock_market_data(
                symbol=symbol,
                from_date=start_date.strftime("%Y-%m-%d"),
                to_date=end_date.strftime("%Y-%m-%d"),
            )

            if not data:
                print(f"✗ No data returned for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Standardize column names to match our schema
            column_mapping = {
                "date": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "adjusted_close": "adj_close",
                "volume": "volume",
            }

            # Select and rename columns
            df = df.rename(columns=column_mapping)

            # Ensure we have the expected columns
            expected_cols = ["date", "open", "high", "low", "close", "adj_close", "volume"]
            df = df[expected_cols]

            # Convert date to datetime
            df["date"] = pd.to_datetime(df["date"])

            # Sort by date
            df = df.sort_values("date").reset_index(drop=True)

            print(f"✓ Fetched {len(df)} price records for {ticker}")
            return df

        except Exception as e:
            print(f"✗ Error fetching prices for {ticker}: {e}")
            return pd.DataFrame()

    def get_fundamentals(
        self, ticker: str, exchange: str = "US"
    ) -> Optional[dict]:
        """
        Fetch fundamental data for a ticker.

        Args:
            ticker: Stock ticker symbol
            exchange: Exchange code (default: US)

        Returns:
            Dictionary with fundamental data or None
        """
        print(f"Fetching fundamentals for {ticker}.{exchange}...")

        try:
            symbol = f"{ticker}.{exchange}"
            data = self.client.get_fundamental_equity(symbol=symbol)

            if not data:
                print(f"✗ No fundamental data returned for {symbol}")
                return None

            print(f"✓ Fetched fundamentals for {ticker}")
            return data

        except Exception as e:
            print(f"✗ Error fetching fundamentals for {ticker}: {e}")
            return None

    def get_bulk_prices(
        self,
        tickers: list[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        exchange: str = "US",
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch prices for multiple tickers.

        Args:
            tickers: List of ticker symbols
            start_date: Start date
            end_date: End date
            exchange: Exchange code

        Returns:
            Dictionary mapping ticker -> DataFrame
        """
        results = {}

        for ticker in tickers:
            df = self.get_prices(ticker, start_date, end_date, exchange)
            if not df.empty:
                results[ticker] = df

        return results


if __name__ == "__main__":
    # Test EODHD client
    print("Testing EODHD Client")
    print("=" * 50)

    client = EODHDClient()

    # Test fetching prices for AAPL
    df = client.get_prices("AAPL", start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

    if not df.empty:
        print(f"\nSample data (first 5 rows):")
        print(df.head())
        print(f"\nData types:")
        print(df.dtypes)
