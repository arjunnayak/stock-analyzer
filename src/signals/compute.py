"""
Metrics computation orchestration.

Coordinates technical and valuation metrics computation,
manages incremental updates, and handles R2 storage.
"""

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from src.reader import TimeSeriesReader
from src.signals.technical import TechnicalSignals
from src.signals.valuation import ValuationSignals
from src.storage.r2_client import R2Client


# Recomputation window for data revisions
RECOMPUTE_WINDOW_DAYS = 30


class MetricsComputer:
    """Orchestrates computation of technical and valuation metrics."""

    def __init__(self, r2_client: Optional[R2Client] = None):
        """
        Initialize metrics computer.

        Args:
            r2_client: R2 storage client (creates new if not provided)
        """
        self.r2 = r2_client or R2Client()
        self.reader = TimeSeriesReader()

    def detect_available_date_range(self, ticker: str) -> tuple[Optional[date], Optional[date]]:
        """
        Detect the available date range for a ticker by listing R2 keys.

        Args:
            ticker: Stock ticker

        Returns:
            Tuple of (min_date, max_date) or (None, None) if no data
        """
        # List all price files for this ticker
        prefix = f"prices/v1/{ticker.upper()}/"
        keys = self.r2.list_keys(prefix=prefix, max_keys=10000)

        if not keys:
            return None, None

        # Parse dates from keys (format: prices/v1/TICKER/YYYY/MM/data.parquet)
        dates = []
        for key in keys:
            parts = key.split("/")
            if len(parts) >= 5:
                try:
                    year = int(parts[3])
                    month = int(parts[4])
                    # Use first day of month as representative date
                    dates.append(date(year, month, 1))
                except (ValueError, IndexError):
                    continue

        if not dates:
            return None, None

        return min(dates), max(dates)

    def compute_technical_metrics(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force: bool = False,
    ) -> dict:
        """
        Compute technical metrics (SMA 200) for a ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date (optional, defaults to all available)
            end_date: End date (optional, defaults to today)
            force: If True, recompute all dates (ignore existing)

        Returns:
            Summary dict with status, rows, files
        """
        print(f"\nComputing Technical Metrics for {ticker}...")

        # Load price data
        prices_df = self.reader.get_prices(ticker, start_date, end_date)

        if prices_df.empty:
            print("  ✗ No price data found")
            return {
                "ticker": ticker,
                "dataset": "technical",
                "status": "no_price_data",
                "rows": 0,
                "files": 0,
            }

        print(f"  ✓ Fetched {len(prices_df)} price rows from R2")

        # Determine which dates need computation
        if not force:
            dates_to_compute = self.get_missing_dates(
                "signals_technical", ticker, list(prices_df["date"].dt.date)
            )

            if not dates_to_compute:
                print("  → All dates up to date (use --force to recompute)")
                return {
                    "ticker": ticker,
                    "dataset": "technical",
                    "status": "up_to_date",
                    "rows": 0,
                    "files": 0,
                }

            print(f"  → Computing for {len(dates_to_compute)} dates (missing + recent)")

            # Filter prices to dates we need to compute
            prices_df = prices_df[prices_df["date"].dt.date.isin(dates_to_compute)]
        else:
            print(f"  → Force mode: computing for all {len(prices_df)} dates")

        # Compute SMA 200
        signals_df = TechnicalSignals.compute_sma_200_only(prices_df)

        # Count valid SMA values
        valid_sma = signals_df["sma_200"].notna().sum()
        null_sma = len(signals_df) - valid_sma

        print(f"  ✓ Computed SMA 200 for {len(signals_df)} dates ({null_sma} NaN due to lookback)")

        # Partition and write to R2
        files_written = self._partition_and_write("signals_technical", ticker, signals_df)

        return {
            "ticker": ticker,
            "dataset": "technical",
            "status": "success",
            "rows": len(signals_df),
            "files": files_written,
        }

    def compute_valuation_metrics(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force: bool = False,
    ) -> dict:
        """
        Compute valuation metrics (EV/Revenue, EV/EBITDA) for a ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date (optional)
            end_date: End date (optional)
            force: If True, recompute all dates

        Returns:
            Summary dict with status, rows, files
        """
        print(f"\nComputing Valuation Metrics for {ticker}...")

        # Load price data
        prices_df = self.reader.get_prices(ticker, start_date, end_date)

        if prices_df.empty:
            print("  ✗ No price data found")
            return {
                "ticker": ticker,
                "dataset": "valuation",
                "status": "no_price_data",
                "rows": 0,
                "files": 0,
            }

        print(f"  ✓ Fetched {len(prices_df)} price rows from R2")

        # Load fundamental data (need longer history for TTM computation)
        # Start from 2 years before price data to ensure we have enough quarters
        fundamental_start = (start_date or prices_df["date"].min().date()) - timedelta(days=730)
        fundamental_end = end_date or prices_df["date"].max().date()

        fundamentals_df = self.reader.get_fundamentals(ticker, fundamental_start, fundamental_end)

        if fundamentals_df.empty:
            print("  ⚠️  No fundamental data found")
            return {
                "ticker": ticker,
                "dataset": "valuation",
                "status": "no_fundamental_data",
                "rows": 0,
                "files": 0,
            }

        print(f"  ✓ Fetched {len(fundamentals_df)} quarterly fundamental rows from R2")

        # Compute EV/Revenue
        print("  → Computing EV/Revenue...")
        ev_revenue_df = ValuationSignals.compute_ev_revenue(prices_df, fundamentals_df)

        if ev_revenue_df.empty:
            print("  ✗ Failed to compute EV/Revenue")
            return {
                "ticker": ticker,
                "dataset": "valuation",
                "status": "computation_failed",
                "rows": 0,
                "files": 0,
            }

        # Compute EV/EBITDA
        print("  → Computing EV/EBITDA...")
        ev_ebitda_df = ValuationSignals.compute_ev_ebitda(prices_df, fundamentals_df)

        if ev_ebitda_df.empty:
            print("  ✗ Failed to compute EV/EBITDA")
            return {
                "ticker": ticker,
                "dataset": "valuation",
                "status": "computation_failed",
                "rows": 0,
                "files": 0,
            }

        # Merge both metrics
        valuation_df = pd.merge(
            ev_revenue_df[["date", "ev_revenue", "ttm_revenue"]],
            ev_ebitda_df[["date", "ev_ebitda", "ttm_ebitda", "enterprise_value", "market_cap", "shares_outstanding"]],
            on="date",
            how="inner",
        )

        # Count valid values
        valid_ev_revenue = valuation_df["ev_revenue"].notna().sum()
        valid_ev_ebitda = valuation_df["ev_ebitda"].notna().sum()

        print(f"  ✓ Computed EV/Revenue for {valid_ev_revenue}/{len(valuation_df)} dates")
        print(f"  ✓ Computed EV/EBITDA for {valid_ev_ebitda}/{len(valuation_df)} dates")

        if valid_ev_revenue < len(valuation_df):
            null_count = len(valuation_df) - valid_ev_revenue
            print(f"  ⚠️  {null_count} dates with null EV/Revenue (zero/negative revenue)")

        if valid_ev_ebitda < len(valuation_df):
            null_count = len(valuation_df) - valid_ev_ebitda
            print(f"  ⚠️  {null_count} dates with null EV/EBITDA (zero/negative EBITDA)")

        # Partition and write to R2
        files_written = self._partition_and_write("signals_valuation", ticker, valuation_df)

        return {
            "ticker": ticker,
            "dataset": "valuation",
            "status": "success",
            "rows": len(valuation_df),
            "files": files_written,
        }

    def compute_all_metrics(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        technical_only: bool = False,
        valuation_only: bool = False,
        force: bool = False,
    ) -> dict:
        """
        Compute both technical and valuation metrics for a ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date (optional, auto-detects from available prices if None)
            end_date: End date (optional, defaults to today if None)
            technical_only: Only compute technical metrics
            valuation_only: Only compute valuation metrics
            force: Recompute all dates

        Returns:
            Combined summary dict
        """
        # Auto-detect date range from available price data if not provided
        if start_date is None or end_date is None:
            # Detect available date range by listing R2 keys (efficient)
            detected_start, detected_end = self.detect_available_date_range(ticker)

            if detected_start and detected_end:
                if start_date is None:
                    start_date = detected_start
                    print(f"  ℹ️  Auto-detected start date: {start_date} (earliest available)")

                if end_date is None:
                    end_date = date.today()
                    print(f"  ℹ️  Using today as end date: {end_date}")
            else:
                # No price data available
                print(f"  ⚠️  No price data found in R2 for {ticker}")
                if end_date is None:
                    end_date = date.today()
                if start_date is None:
                    start_date = end_date

        results = []

        # Technical metrics
        if not valuation_only:
            result = self.compute_technical_metrics(ticker, start_date, end_date, force)
            results.append(result)

        # Valuation metrics
        if not technical_only:
            result = self.compute_valuation_metrics(ticker, start_date, end_date, force)
            results.append(result)

        # Combine results
        total_rows = sum(r["rows"] for r in results)
        total_files = sum(r["files"] for r in results)
        statuses = [r["status"] for r in results]

        # Overall status
        if all(s == "success" for s in statuses):
            status = "success"
        elif any(s == "success" for s in statuses):
            status = "partial_success"
        else:
            status = "failed"

        return {
            "ticker": ticker,
            "status": status,
            "results": results,
            "total_rows": total_rows,
            "total_files": total_files,
        }

    def get_missing_dates(
        self, dataset: str, ticker: str, available_price_dates: list[date]
    ) -> list[date]:
        """
        Determine which dates are missing in R2 for incremental computation.

        Strategy:
        1. Get all dates from price data (source of truth)
        2. Get existing dates from signals dataset in R2
        3. Compute diff: dates in prices but not in signals
        4. Add buffer: recompute last N days (for data revisions)

        Args:
            dataset: Dataset name (e.g., 'signals_technical', 'signals_valuation')
            ticker: Stock ticker
            available_price_dates: List of dates we have price data for

        Returns:
            List of dates that need computation
        """
        if not available_price_dates:
            return []

        # Get existing signal dates from R2
        try:
            existing_signals = self.r2.get_timeseries(
                dataset=dataset,
                ticker=ticker,
                start_date=min(available_price_dates),
                end_date=max(available_price_dates),
            )
        except Exception:
            # If no existing data, compute for all dates
            return available_price_dates

        if existing_signals.empty:
            # No existing data, compute for all dates
            return available_price_dates

        # Convert to sets for diff
        existing_dates = set(existing_signals["date"].dt.date)
        available_dates = set(available_price_dates)

        # Dates we're missing
        missing_dates = available_dates - existing_dates

        # Add last N days for recomputation (data revision buffer)
        today = date.today()
        recent_cutoff = today - timedelta(days=RECOMPUTE_WINDOW_DAYS)
        recent_dates = {d for d in available_dates if d >= recent_cutoff}

        # Union of missing and recent
        dates_to_compute = missing_dates.union(recent_dates)

        return sorted(list(dates_to_compute))

    def _partition_and_write(self, dataset: str, ticker: str, df: pd.DataFrame) -> int:
        """
        Partition DataFrame by month and write to R2.

        Args:
            dataset: Dataset name (e.g., 'signals_technical')
            ticker: Stock ticker
            df: Signals DataFrame with 'date' column

        Returns:
            Number of files written
        """
        if df.empty:
            return 0

        # Add year/month columns for partitioning
        df = df.copy()
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month

        # Group by month
        groups = df.groupby(["year", "month"])
        files_written = 0

        for (year, month), group_df in groups:
            # Remove partitioning columns
            data_df = group_df.drop(columns=["year", "month"])

            # Build key
            key = self.r2.build_key(dataset=dataset, ticker=ticker, year=year, month=month)

            # Merge with existing data and write
            self.r2.merge_and_put(key, data_df, dedupe_column="date")
            files_written += 1

        print(f"  ✓ Wrote {files_written} monthly files to {dataset}/v1/{ticker}/...")

        return files_written


if __name__ == "__main__":
    # Test with mock data
    print("Testing MetricsComputer")
    print("=" * 60)

    # This would require actual R2 data to test
    # See scripts/compute_metrics.py for CLI usage
    print("Use scripts/compute_metrics.py to run actual computations")
    print("Example: python scripts/compute_metrics.py --ticker UBER")
