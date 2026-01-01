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

        # Get active tickers
        if tickers is None:
            tickers = self.db.get_active_tickers()

        if not tickers:
            print("No active tickers found. Exiting.")
            return {
                "status": "no_tickers",
                "tickers_processed": 0,
            }

        print(f"\nActive tickers: {len(tickers)}")
        print(f"Window: {window_days} trading days (~{window_days // 252} years)")
        print(f"Min data points: {min_data_points}")

        # Load historical features
        print("\nLoading historical features from R2...")
        features_df = self._load_historical_features(window_days)

        if features_df.empty:
            print("No historical features available. Exiting.")
            return {
                "status": "no_features",
                "tickers_processed": 0,
            }

        print(f"Loaded {len(features_df)} feature rows")
        print(f"Date range: {features_df['date'].min()} to {features_df['date'].max()}")
        print(f"Unique tickers in data: {features_df['ticker'].nunique()}")

        # Filter to active tickers
        features_df = features_df[features_df["ticker"].isin(tickers)]
        print(f"After filtering to active tickers: {len(features_df)} rows")

        # Compute stats per ticker
        print("\nComputing valuation stats per ticker...")
        stats_rows = []
        tickers_with_stats = 0
        tickers_insufficient = 0

        for ticker in tickers:
            ticker_df = features_df[features_df["ticker"] == ticker]

            if len(ticker_df) < min_data_points:
                tickers_insufficient += 1
                continue

            # Get EV/EBITDA values
            ev_ebitda = ticker_df["ev_ebitda"].dropna()

            if len(ev_ebitda) < min_data_points:
                tickers_insufficient += 1
                continue

            # Filter to positive values only
            ev_ebitda = ev_ebitda[ev_ebitda > 0]

            if len(ev_ebitda) < min_data_points:
                tickers_insufficient += 1
                continue

            # Compute stats
            stats = self._compute_stats(ev_ebitda)
            stats["ticker"] = ticker
            stats["metric"] = "ev_ebitda"
            stats["window_days"] = window_days
            stats["asof_date"] = ticker_df["date"].max()

            # Convert date to string for Supabase
            if hasattr(stats["asof_date"], "isoformat"):
                stats["asof_date"] = stats["asof_date"].isoformat()
            elif hasattr(stats["asof_date"], "strftime"):
                stats["asof_date"] = stats["asof_date"].strftime("%Y-%m-%d")

            stats_rows.append(stats)
            tickers_with_stats += 1

        print(f"\nStats computed for {tickers_with_stats} tickers")
        print(f"Insufficient data for {tickers_insufficient} tickers")

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
            "tickers_processed": tickers_with_stats,
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
        # Get list of available feature dates
        available_dates = self.r2.list_feature_dates(limit=window_days + 100)

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

    def backfill_from_signals_valuation(
        self,
        tickers: Optional[list[str]] = None,
        years: int = 5,
        dry_run: bool = False,
    ) -> dict:
        """
        Backfill valuation stats from the existing signals_valuation dataset.

        This is useful for initial setup before the daily features dataset has
        enough history.

        Args:
            tickers: Optional list of tickers
            years: Number of years of history
            dry_run: Don't write to Supabase

        Returns:
            Summary dict
        """
        print("\n" + "=" * 70)
        print("BACKFILL VALUATION STATS FROM SIGNALS_VALUATION")
        print("=" * 70)

        if tickers is None:
            tickers = self.db.get_active_tickers()

        if not tickers:
            print("No active tickers. Exiting.")
            return {"status": "no_tickers", "tickers_processed": 0}

        print(f"Processing {len(tickers)} tickers...")

        from src.reader import TimeSeriesReader

        reader = TimeSeriesReader()
        end_date = date.today()
        start_date = end_date - timedelta(days=years * 365)

        stats_rows = []
        tickers_processed = 0
        tickers_failed = 0

        for ticker in tickers:
            try:
                # Read from signals_valuation
                df = reader.r2.get_timeseries(
                    dataset="signals_valuation",
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                )

                if df.empty or "ev_ebitda" not in df.columns:
                    tickers_failed += 1
                    continue

                # Get valid EV/EBITDA values
                ev_ebitda = df["ev_ebitda"].dropna()
                ev_ebitda = ev_ebitda[ev_ebitda > 0]

                if len(ev_ebitda) < MIN_DATA_POINTS:
                    tickers_failed += 1
                    continue

                # Compute stats
                stats = self._compute_stats(ev_ebitda)
                stats["ticker"] = ticker
                stats["metric"] = "ev_ebitda"
                stats["window_days"] = years * 252  # Approximate trading days
                stats["asof_date"] = df["date"].max()

                if hasattr(stats["asof_date"], "isoformat"):
                    stats["asof_date"] = stats["asof_date"].isoformat()
                elif hasattr(stats["asof_date"], "strftime"):
                    stats["asof_date"] = stats["asof_date"].strftime("%Y-%m-%d")

                stats_rows.append(stats)
                tickers_processed += 1

                print(f"  {ticker}: {len(ev_ebitda)} points, p20={stats['p20']:.1f}, p50={stats['p50']:.1f}, p80={stats['p80']:.1f}")

            except Exception as e:
                print(f"  {ticker}: Error - {e}")
                tickers_failed += 1

        if not stats_rows:
            print("No stats computed.")
            return {"status": "no_stats", "tickers_processed": 0}

        if not dry_run:
            print(f"\nWriting {len(stats_rows)} stats rows to Supabase...")
            count = self.db.upsert_valuation_stats(stats_rows)
            print(f"Upserted {count} rows")
        else:
            print("\n[DRY RUN] Skipping write")

        return {
            "status": "success" if not dry_run else "dry_run",
            "tickers_processed": tickers_processed,
            "tickers_failed": tickers_failed,
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
        "--backfill",
        action="store_true",
        help="Backfill from signals_valuation instead of features",
    )
    parser.add_argument(
        "--backfill-years",
        type=int,
        default=5,
        help="Years of history for backfill (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write to Supabase",
    )

    args = parser.parse_args()

    with WeeklyStatsPipeline() as pipeline:
        if args.backfill:
            result = pipeline.backfill_from_signals_valuation(
                tickers=args.tickers,
                years=args.backfill_years,
                dry_run=args.dry_run,
            )
        else:
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
