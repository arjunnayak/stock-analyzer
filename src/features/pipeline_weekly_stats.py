"""
Weekly valuation stats computation.

Recomputes historical valuation percentiles for all active tickers:
- Reads EV/EBITDA from historical features
- Computes percentiles (p10, p20, p50, p80, p90)
- Stores in Supabase valuation_stats table

Scheduled to run weekly (e.g., Sundays 2am ET).
"""

import argparse
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.storage.r2_client import R2Client
from src.storage.supabase_db import SupabaseDB


# Default lookback window in trading days (~5 years)
DEFAULT_WINDOW_DAYS = 1260

# Minimum data points required for valid stats
MIN_DATA_POINTS = 100


class WeeklyStatsPipeline:
    """Computes weekly valuation statistics for all active tickers."""

    def __init__(
        self,
        r2_client: Optional[R2Client] = None,
        db: Optional[SupabaseDB] = None,
    ):
        """
        Initialize pipeline components.

        Args:
            r2_client: R2 storage client
            db: Supabase database client
        """
        self.r2 = r2_client or R2Client()
        self.db = db or SupabaseDB()

    def close(self):
        """Close all connections."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def run(
        self,
        tickers: Optional[list[str]] = None,
        window_days: int = DEFAULT_WINDOW_DAYS,
        min_data_points: int = MIN_DATA_POINTS,
        dry_run: bool = False,
    ) -> dict:
        """
        Compute valuation stats for all active tickers.

        Args:
            tickers: Optional list of tickers (defaults to all active)
            window_days: Lookback window in trading days (default: 1260)
            min_data_points: Minimum data points required (default: 100)
            dry_run: Don't write to Supabase

        Returns:
            Summary dict with statistics
        """
        print("\n" + "=" * 70)
        print("WEEKLY VALUATION STATS COMPUTATION")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # =====================================================================
        # Step 0: Data Availability Validation
        # =====================================================================
        print("\n" + "=" * 70)
        print("STEP 0: DATA AVAILABILITY VALIDATION")
        print("=" * 70)

        # Get active tickers
        if tickers is None:
            tickers = self.db.get_active_tickers()

        if not tickers:
            print("✗ No active tickers found")
            return {
                "status": "failed_validation",
                "error": "no_active_tickers",
                "tickers_processed": 0,
            }

        print(f"✓ Active tickers: {len(tickers)}")

        # Check if we have any historical features
        print("\nChecking for historical features in R2...")
        # Use a high limit to ensure we get all available dates, not just old ones
        available_dates = self.r2.list_feature_dates(limit=5000)

        if not available_dates:
            print("✗ No historical features found in R2")
            print("\n  The weekly stats pipeline requires historical features.")
            print("  You need to build up feature history first by running the daily pipeline.")
            print("\n  To backfill historical features, run:")
            print("    # For the last 6 months (~120 trading days)")
            print("    ENV=REMOTE python scripts/backfill_features_historical.py --days 120")
            print("\n  Or manually run daily pipeline for each historical date:")
            print("    ENV=REMOTE python -m src.features.pipeline_daily --run-date YYYY-MM-DD")
            return {
                "status": "failed_validation",
                "error": "no_historical_features",
                "tickers_processed": 0,
            }

        # Check if we have enough history
        num_available = len(available_dates)
        oldest_date = min(available_dates)
        newest_date = max(available_dates)
        days_of_history = (newest_date - oldest_date).days

        print(f"✓ Found {num_available} dates of feature history")
        print(f"  Date range: {oldest_date} to {newest_date} ({days_of_history} calendar days)")

        if num_available < min_data_points:
            print(f"\n⚠️  Warning: Only {num_available} feature dates available")
            print(f"  Recommended: {min_data_points}+ dates for reliable stats")
            print(f"  Some tickers may have insufficient data and will be skipped")

        # Recommend window adjustment if needed
        if num_available < window_days:
            recommended_window = num_available - 10
            print(f"\n⚠️  Warning: Requested window ({window_days} days) exceeds available data ({num_available} days)")
            print(f"  Recommendation: Use --window-days {recommended_window}")

        print("\n" + "=" * 70)
        print(f"Window: {window_days} trading days (~{window_days // 252} years)")
        print(f"Min data points: {min_data_points}")
        print("=" * 70)

        # Compute valuation data directly from prices and fundamentals
        # This is more reliable than using pre-computed features which may have missing data
        print("\nComputing valuation metrics from prices and fundamentals...")

        # Calculate date range based on window
        end_date = date.today()
        # Approximate calendar days for trading days (252 trading days per year)
        calendar_days = int(window_days * 365 / 252) + 30  # Add buffer
        start_date = end_date - timedelta(days=calendar_days)

        features_df = self._compute_valuation_from_fundamentals(tickers, start_date, end_date)

        if features_df.empty:
            print("No valuation data could be computed. Exiting.")
            return {
                "status": "no_features",
                "tickers_processed": 0,
            }

        print(f"Computed {len(features_df)} valuation rows")
        print(f"Date range: {features_df['date'].min()} to {features_df['date'].max()}")
        print(f"Unique tickers in data: {features_df['ticker'].nunique()}")

        # Compute stats per ticker
        print("\nComputing valuation stats per ticker...")
        stats_rows = []
        tickers_with_ev_ebit = 0
        tickers_with_ev_ebitda = 0
        tickers_insufficient = 0

        for ticker in tickers:
            ticker_df = features_df[features_df["ticker"] == ticker]

            if len(ticker_df) < min_data_points:
                tickers_insufficient += 1
                continue

            asof_date = ticker_df["date"].max()
            # Convert date to string for Supabase
            if hasattr(asof_date, "isoformat"):
                asof_date_str = asof_date.isoformat()
            elif hasattr(asof_date, "strftime"):
                asof_date_str = asof_date.strftime("%Y-%m-%d")
            else:
                asof_date_str = str(asof_date)

            # Get EV/EBIT values (preferred - quarterly granularity)
            if "ev_ebit" in ticker_df.columns:
                ev_ebit = ticker_df["ev_ebit"].dropna()
                ev_ebit = ev_ebit[ev_ebit > 0]

                if len(ev_ebit) >= min_data_points:
                    stats = self._compute_stats(ev_ebit)
                    stats["ticker"] = ticker
                    stats["metric"] = "ev_ebit"
                    stats["window_days"] = window_days
                    stats["asof_date"] = asof_date_str
                    stats_rows.append(stats)
                    tickers_with_ev_ebit += 1

            # Get EV/EBITDA values (fallback - yearly D&A only)
            if "ev_ebitda" in ticker_df.columns:
                ev_ebitda = ticker_df["ev_ebitda"].dropna()
                ev_ebitda = ev_ebitda[ev_ebitda > 0]

                if len(ev_ebitda) >= min_data_points:
                    stats = self._compute_stats(ev_ebitda)
                    stats["ticker"] = ticker
                    stats["metric"] = "ev_ebitda"
                    stats["window_days"] = window_days
                    stats["asof_date"] = asof_date_str
                    stats_rows.append(stats)
                    tickers_with_ev_ebitda += 1

            # Count as insufficient only if neither metric has enough data
            if ticker not in [s["ticker"] for s in stats_rows]:
                tickers_insufficient += 1

        print(f"\nStats computed:")
        print(f"  - EV/EBIT: {tickers_with_ev_ebit} tickers")
        print(f"  - EV/EBITDA: {tickers_with_ev_ebitda} tickers")
        print(f"  - Insufficient data: {tickers_insufficient} tickers")

        if not stats_rows:
            print("No stats to write. Exiting.")
            return {
                "status": "no_stats",
                "tickers_processed": 0,
            }

        # Write to Supabase
        if not dry_run:
            print("\nWriting to Supabase valuation_stats...")
            count = self.db.upsert_valuation_stats(stats_rows)
            print(f"Upserted {count} rows")
        else:
            print("\n[DRY RUN] Skipping write to Supabase")

        # Summary
        result = {
            "status": "success" if not dry_run else "dry_run",
            "tickers_with_ev_ebit": tickers_with_ev_ebit,
            "tickers_with_ev_ebitda": tickers_with_ev_ebitda,
            "tickers_insufficient": tickers_insufficient,
            "total_feature_rows": len(features_df),
        }

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        for key, value in result.items():
            print(f"  {key}: {value}")

        return result

    def _load_historical_features(self, window_days: int) -> pd.DataFrame:
        """
        Load historical features from R2.

        Reads date-partitioned feature files for the lookback window.

        Args:
            window_days: Number of trading days to look back

        Returns:
            DataFrame with historical features
        """
        # Get list of available feature dates (use high limit to get recent dates)
        available_dates = self.r2.list_feature_dates(limit=5000)

        if not available_dates:
            return pd.DataFrame()

        # Take up to window_days most recent dates
        dates_to_load = available_dates[:window_days]
        print(f"Loading features from {len(dates_to_load)} dates...")

        dfs = []
        for i, d in enumerate(dates_to_load):
            df = self.r2.get_features(d)
            if df is not None and not df.empty:
                dfs.append(df)

            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"  Loaded {i + 1}/{len(dates_to_load)} dates...")

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)

        # Ensure date column is proper datetime
        if "date" in combined.columns:
            combined["date"] = pd.to_datetime(combined["date"])

        return combined

    def _compute_valuation_from_fundamentals(
        self, tickers: list[str], start_date: date, end_date: date
    ) -> pd.DataFrame:
        """
        Compute EV/EBIT time series directly from prices and fundamentals.

        This is used when pre-computed features don't have valuation data.

        Args:
            tickers: List of ticker symbols
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with columns: date, ticker, ev_ebit, ev_ebitda
        """
        print("Computing valuation metrics from raw data...")
        all_rows = []

        for ticker in tickers:
            # Load price history
            prices_df = self.r2.get_timeseries("prices", ticker, start_date, end_date)
            if prices_df.empty:
                continue

            # Load fundamentals history
            funds_df = self.r2.get_timeseries("fundamentals", ticker, start_date, end_date)
            if funds_df.empty:
                continue

            # Filter to quarterly fundamentals for TTM calculation
            # Handle different period value formats (Quarter, QUARTER, quarter)
            q_df = funds_df[funds_df["period"].str.lower() == "quarter"].copy()
            if len(q_df) < 4:
                print(f"  {ticker}: Only {len(q_df)} quarters, need 4 for TTM")
                continue

            # Sort by period_end
            q_df = q_df.sort_values("period_end")
            q_df["period_end"] = pd.to_datetime(q_df["period_end"])

            # Compute TTM operating income (rolling 4 quarters)
            if "operating_income" in q_df.columns:
                q_df["operating_income_ttm"] = q_df["operating_income"].rolling(4, min_periods=4).sum()
            else:
                continue

            # For each price date, find the most recent TTM operating income
            prices_df = prices_df.copy()
            prices_df["date"] = pd.to_datetime(prices_df["date"])
            prices_df = prices_df.sort_values("date")

            for _, price_row in prices_df.iterrows():
                price_date = price_row["date"]
                close = price_row["close"]

                # Find most recent fundamentals as of this date
                valid_funds = q_df[q_df["period_end"] <= price_date]
                if valid_funds.empty:
                    continue

                latest_fund = valid_funds.iloc[-1]
                op_income_ttm = latest_fund.get("operating_income_ttm")

                if pd.isna(op_income_ttm) or op_income_ttm <= 0:
                    continue

                # Get shares outstanding (use most recent)
                shares = latest_fund.get("average_shares")
                if pd.isna(shares) or shares <= 0:
                    continue

                # Compute market cap and EV
                market_cap = close * shares

                # Use net debt from balance sheet if available, else skip
                # For simplicity, we'll estimate EV = market_cap (no debt adjustment)
                # TODO: Add proper net debt calculation from balance sheet
                enterprise_value = market_cap

                ev_ebit = enterprise_value / op_income_ttm if op_income_ttm > 0 else None

                all_rows.append({
                    "date": price_date,
                    "ticker": ticker,
                    "ev_ebit": ev_ebit,
                    "close": close,
                })

        if not all_rows:
            return pd.DataFrame()

        return pd.DataFrame(all_rows)

    def _compute_stats(self, values: pd.Series) -> dict:
        """
        Compute distribution statistics for a series of values.

        Args:
            values: Pandas Series of numeric values

        Returns:
            Dict with count, mean, std, min, max, and percentiles
        """
        return {
            "count": len(values),
            "mean": float(values.mean()),
            "std": float(values.std()),
            "min": float(values.min()),
            "max": float(values.max()),
            "p10": float(np.percentile(values, 10)),
            "p20": float(np.percentile(values, 20)),
            "p50": float(np.percentile(values, 50)),
            "p80": float(np.percentile(values, 80)),
            "p90": float(np.percentile(values, 90)),
        }

def main():
    """Main entry point for weekly stats computation."""
    parser = argparse.ArgumentParser(
        description="Compute weekly valuation stats for historical percentile templates"
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        help="Specific tickers to process (default: all active)",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help=f"Lookback window in trading days (default: {DEFAULT_WINDOW_DAYS})",
    )
    parser.add_argument(
        "--min-data-points",
        type=int,
        default=MIN_DATA_POINTS,
        help=f"Minimum data points required (default: {MIN_DATA_POINTS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write to Supabase",
    )

    args = parser.parse_args()

    with WeeklyStatsPipeline() as pipeline:
        result = pipeline.run(
            tickers=args.tickers,
            window_days=args.window_days,
            min_data_points=args.min_data_points,
            dry_run=args.dry_run,
        )

        if result["status"] not in ("success", "dry_run"):
            exit(1)


if __name__ == "__main__":
    main()
