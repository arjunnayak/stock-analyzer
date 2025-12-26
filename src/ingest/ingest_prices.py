"""
Ingest historical price data from EODHD to R2 storage.

This script:
1. Fetches price data from EODHD API
2. Partitions by month
3. Stores in R2 as Parquet files following the architecture pattern
"""

from datetime import date, datetime
from typing import Optional

import pandas as pd

from src.config import config
from src.ingest.eodhd_client import EODHDClient
from src.storage.r2_client import R2Client


class PriceIngester:
    """Handles ingestion of price data to R2 storage."""

    def __init__(self):
        """Initialize ingester with EODHD and R2 clients."""
        self.eodhd = EODHDClient()
        self.r2 = R2Client()

    def ingest_ticker(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        exchange: str = "US",
    ) -> dict:
        """
        Ingest price data for a single ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date (defaults to 5 years ago)
            end_date: End date (defaults to today)
            exchange: Exchange code

        Returns:
            Summary statistics
        """
        print(f"\n{'=' * 60}")
        print(f"Ingesting {ticker}")
        print(f"{'=' * 60}")

        # Fetch data from EODHD
        df = self.eodhd.get_prices(ticker, start_date, end_date, exchange)

        if df.empty:
            return {"ticker": ticker, "status": "failed", "rows": 0, "files": 0}

        # Partition by month and write to R2
        stats = self._partition_and_write(ticker, df)

        return stats

    def _partition_and_write(self, ticker: str, df: pd.DataFrame) -> dict:
        """
        Partition DataFrame by month and write to R2.

        Args:
            ticker: Stock ticker
            df: Price DataFrame with 'date' column

        Returns:
            Summary statistics
        """
        # Ensure date is datetime
        df["date"] = pd.to_datetime(df["date"])

        # Extract year and month
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month

        # Group by year/month
        groups = df.groupby(["year", "month"])

        files_written = 0
        total_rows = 0

        for (year, month), group_df in groups:
            # Drop the year/month helper columns
            data_df = group_df.drop(columns=["year", "month"])

            # Build storage key
            key = self.r2.build_key(
                dataset="prices",
                ticker=ticker,
                year=year,
                month=month,
            )

            # Merge with existing data and write
            self.r2.merge_and_put(key, data_df, dedupe_column="date")

            files_written += 1
            total_rows += len(data_df)

        return {
            "ticker": ticker,
            "status": "success",
            "rows": total_rows,
            "files": files_written,
        }

    def ingest_batch(
        self,
        tickers: list[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        exchange: str = "US",
    ) -> dict:
        """
        Ingest price data for multiple tickers.

        Args:
            tickers: List of stock tickers
            start_date: Start date
            end_date: End date
            exchange: Exchange code

        Returns:
            Summary statistics for all tickers
        """
        results = []

        for ticker in tickers:
            result = self.ingest_ticker(ticker, start_date, end_date, exchange)
            results.append(result)

        # Aggregate summary
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        total_rows = sum(r["rows"] for r in results)
        total_files = sum(r["files"] for r in results)

        summary = {
            "total_tickers": len(tickers),
            "successful": successful,
            "failed": failed,
            "total_rows": total_rows,
            "total_files": total_files,
            "results": results,
        }

        return summary


def main():
    """Run ingestion for test tickers."""
    print("Price Data Ingestion")
    print("=" * 60)

    ingester = PriceIngester()

    # Test tickers (from our DB seed data)
    tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]

    # Ingest last 6 months of data for testing
    end_date = date.today()
    start_date = date(2024, 7, 1)  # ~6 months

    print(f"Ingesting data from {start_date} to {end_date}")
    print(f"Tickers: {', '.join(tickers)}")

    summary = ingester.ingest_batch(tickers, start_date, end_date)

    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Total Tickers: {summary['total_tickers']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Total Rows: {summary['total_rows']:,}")
    print(f"Total Files: {summary['total_files']}")
    print()

    for result in summary["results"]:
        status_icon = "✓" if result["status"] == "success" else "✗"
        print(f"{status_icon} {result['ticker']}: {result['rows']:,} rows, {result['files']} files")


if __name__ == "__main__":
    main()
