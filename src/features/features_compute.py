"""
Daily feature computation for Step 2 of the pipeline.

Computes wide-row features for all active tickers:
- Technical indicators (EMA 200, EMA 50)
- Valuation metrics (EV/EBITDA)
- Stores to R2 as date-partitioned parquet + latest.parquet
- Upserts indicator_state for incremental computation
"""

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.reader import TimeSeriesReader
from src.storage.r2_client import R2Client
from src.storage.supabase_db import IndicatorState, SupabaseDB


# EMA smoothing factors
ALPHA_200 = 2 / (200 + 1)
ALPHA_50 = 2 / (50 + 1)


class FeaturesComputer:
    """Computes daily features snapshot for all active tickers."""

    def __init__(
        self,
        r2_client: Optional[R2Client] = None,
        db: Optional[SupabaseDB] = None,
        reader: Optional[TimeSeriesReader] = None,
    ):
        """
        Initialize features computer.

        Args:
            r2_client: R2 storage client
            db: Supabase database client
            reader: Time series reader for price data
        """
        self.r2 = r2_client or R2Client()
        self.db = db or SupabaseDB()
        self.reader = reader or TimeSeriesReader()

    def close(self):
        """Close all connections."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def compute_daily_features(
        self,
        run_date: date,
        tickers: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Compute and store daily features for all active tickers.

        Args:
            run_date: Date of the feature snapshot
            tickers: Optional list of tickers (defaults to active tickers)
            dry_run: If True, don't write to R2 or Supabase

        Returns:
            Summary dict with statistics
        """
        print(f"\n{'=' * 70}")
        print(f"DAILY FEATURE COMPUTATION - {run_date}")
        print(f"{'=' * 70}\n")

        # Step 1: Get active tickers
        if tickers is None:
            tickers = self.db.get_active_tickers()

        if not tickers:
            print("No active tickers found. Exiting.")
            return {
                "run_date": run_date.isoformat(),
                "status": "no_tickers",
                "tickers_processed": 0,
            }

        print(f"Active tickers: {len(tickers)}")

        # Step 2: Try to load price snapshot for run_date
        prices_df = self._load_prices_for_date(run_date, tickers)

        if prices_df.empty:
            print(f"No price data for {run_date}. Exiting.")
            return {
                "run_date": run_date.isoformat(),
                "status": "no_price_data",
                "tickers_processed": 0,
            }

        print(f"Loaded prices for {len(prices_df)} tickers")

        # Step 3: Load indicator state
        indicator_states = self.db.fetch_indicator_state(tickers)
        print(f"Loaded indicator state for {len(indicator_states)} tickers")

        # Step 4: Load fundamentals
        fundamentals = self.db.fetch_fundamentals_latest(tickers)
        print(f"Loaded fundamentals for {len(fundamentals)} tickers")

        # Step 5: Load entity metadata
        metadata_df = self.db.get_entity_metadata(tickers)

        # Step 6: Compute features for each ticker
        feature_rows = []
        indicator_updates = []
        cold_starts = 0

        for _, row in prices_df.iterrows():
            ticker = row["ticker"]
            close = row["close"]
            volume = row.get("volume")

            # Get previous state
            prev_state = indicator_states.get(ticker)

            # Compute incremental EMAs
            features, new_state = self._compute_ticker_features(
                ticker=ticker,
                close=close,
                volume=volume,
                run_date=run_date,
                prev_state=prev_state,
                fundamentals=fundamentals.get(ticker),
                metadata_df=metadata_df,
            )

            if prev_state is None:
                cold_starts += 1

            feature_rows.append(features)
            indicator_updates.append(new_state)

        # Build features DataFrame
        features_df = pd.DataFrame(feature_rows)

        print(f"\nFeature computation complete:")
        print(f"  - Tickers processed: {len(features_df)}")
        print(f"  - Cold starts: {cold_starts}")
        print(f"  - EMA 200 valid: {features_df['ema_200'].notna().sum()}")
        print(f"  - EV/EBITDA valid: {features_df['ev_ebitda'].notna().sum()}")

        if dry_run:
            print("\n[DRY RUN] Skipping writes to R2 and Supabase")
            return {
                "run_date": run_date.isoformat(),
                "status": "dry_run",
                "tickers_processed": len(features_df),
                "cold_starts": cold_starts,
            }

        # Step 7: Write features to R2
        print("\nWriting features to R2...")
        self.r2.put_features(run_date, features_df)
        self.r2.put_features_latest(features_df)

        # Step 8: Upsert indicator state
        print("Updating indicator state in Supabase...")
        count = self.db.upsert_indicator_state(indicator_updates)
        print(f"  - Updated {count} indicator state rows")

        return {
            "run_date": run_date.isoformat(),
            "status": "success",
            "tickers_processed": len(features_df),
            "cold_starts": cold_starts,
            "ema_200_valid": int(features_df["ema_200"].notna().sum()),
            "ev_ebitda_valid": int(features_df["ev_ebitda"].notna().sum()),
        }

    def _load_prices_for_date(
        self, run_date: date, tickers: list[str]
    ) -> pd.DataFrame:
        """
        Load prices for a specific date.

        Tries price snapshot first, falls back to reading individual ticker files.

        Args:
            run_date: Date to load prices for
            tickers: List of tickers to include

        Returns:
            DataFrame with columns: ticker, close, volume
        """
        # Try snapshot first
        snapshot = self.r2.get_price_snapshot(run_date)
        if snapshot is not None and not snapshot.empty:
            # Filter to active tickers
            snapshot = snapshot[snapshot["ticker"].isin(tickers)]
            if not snapshot.empty:
                print(f"Using price snapshot for {run_date}")
                return snapshot

        # Fallback: Read from individual ticker files
        print(f"Building price snapshot from individual ticker files...")
        rows = []

        for ticker in tickers:
            try:
                df = self.reader.get_prices(ticker, run_date, run_date)
                if not df.empty:
                    latest = df.iloc[-1]
                    rows.append(
                        {
                            "date": run_date,
                            "ticker": ticker,
                            "close": latest["close"],
                            "volume": latest.get("volume"),
                        }
                    )
            except Exception as e:
                print(f"  Warning: Could not load prices for {ticker}: {e}")

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    def _compute_ticker_features(
        self,
        ticker: str,
        close: float,
        volume: Optional[float],
        run_date: date,
        prev_state: Optional[IndicatorState],
        fundamentals: Optional[object],
        metadata_df: pd.DataFrame,
    ) -> tuple[dict, dict]:
        """
        Compute features for a single ticker.

        Args:
            ticker: Ticker symbol
            close: Current close price
            volume: Current volume
            run_date: Date of computation
            prev_state: Previous indicator state (None for cold start)
            fundamentals: Fundamentals data (if available)
            metadata_df: Entity metadata DataFrame

        Returns:
            Tuple of (feature_dict, indicator_state_update_dict)
        """
        # Initialize with cold start values
        if prev_state is None:
            # Cold start: set EMA = close
            ema_200 = close
            ema_50 = close
            prev_close = None
            prev_ema_200 = None
            prev_ema_50 = None
        else:
            # Shift prev values
            prev_close = prev_state.last_close
            prev_ema_200 = prev_state.ema_200
            prev_ema_50 = prev_state.ema_50

            # Compute new EMAs
            if prev_state.ema_200 is not None:
                ema_200 = ALPHA_200 * close + (1 - ALPHA_200) * prev_state.ema_200
            else:
                ema_200 = close

            if prev_state.ema_50 is not None:
                ema_50 = ALPHA_50 * close + (1 - ALPHA_50) * prev_state.ema_50
            else:
                ema_50 = close

        # Compute EV/EBITDA
        ev_ebitda = None
        market_cap = None
        enterprise_value = None
        ebitda_ttm = None
        sector = None

        if fundamentals is not None:
            shares = fundamentals.shares_outstanding
            if shares and shares > 0:
                market_cap = close * shares

                # Net debt = total_debt - cash
                net_debt = (fundamentals.net_debt or 0) if fundamentals.net_debt else (
                    (fundamentals.total_debt or 0) - (fundamentals.cash_and_equivalents or 0)
                )
                enterprise_value = market_cap + net_debt

                ebitda = fundamentals.ebitda_ttm
                if ebitda and ebitda > 0:
                    ebitda_ttm = ebitda
                    ev_ebitda = enterprise_value / ebitda

        # Get sector from metadata
        if not metadata_df.empty:
            ticker_meta = metadata_df[metadata_df["ticker"] == ticker]
            if not ticker_meta.empty:
                sector = ticker_meta.iloc[0].get("sector")

        # Build feature row
        features = {
            "date": run_date,
            "ticker": ticker,
            "close": close,
            "volume": volume,
            "ema_200": ema_200,
            "ema_50": ema_50,
            "prev_close": prev_close,
            "prev_ema_200": prev_ema_200,
            "prev_ema_50": prev_ema_50,
            "ev_ebitda": ev_ebitda,
            "market_cap": market_cap,
            "enterprise_value": enterprise_value,
            "ebitda_ttm": ebitda_ttm,
            "sector": sector,
        }

        # Build indicator state update
        state_update = {
            "ticker": ticker,
            "last_price_date": run_date.isoformat(),
            "last_close": close,
            "prev_close": prev_close,
            "prev_ema_200": prev_ema_200,
            "prev_ema_50": prev_ema_50,
            "ema_200": ema_200,
            "ema_50": ema_50,
        }

        return features, state_update

    def create_price_snapshot_from_ingestion(
        self, run_date: date, tickers: list[str]
    ) -> Optional[str]:
        """
        Create a price snapshot from individual ticker files after ingestion.

        This should be called after price ingestion to create the cross-sectional
        snapshot that Step 2 needs.

        Args:
            run_date: Date of the snapshot
            tickers: List of tickers to include

        Returns:
            R2 key of the written snapshot, or None if no data
        """
        print(f"\nCreating price snapshot for {run_date}...")

        rows = []
        for ticker in tickers:
            try:
                df = self.reader.get_prices(ticker, run_date, run_date)
                if not df.empty:
                    # Get the row for run_date
                    df["date"] = pd.to_datetime(df["date"]).dt.date
                    day_df = df[df["date"] == run_date]
                    if not day_df.empty:
                        latest = day_df.iloc[-1]
                        rows.append(
                            {
                                "date": run_date,
                                "ticker": ticker,
                                "close": latest["close"],
                                "volume": latest.get("volume"),
                            }
                        )
            except Exception as e:
                print(f"  Warning: Could not load prices for {ticker}: {e}")

        if not rows:
            print("  No price data found for any ticker")
            return None

        snapshot_df = pd.DataFrame(rows)
        key = self.r2.put_price_snapshot(run_date, snapshot_df)
        print(f"  Created snapshot with {len(snapshot_df)} tickers: {key}")
        return key


if __name__ == "__main__":
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser(description="Compute daily features")
    parser.add_argument(
        "--run-date",
        type=str,
        help="Date to compute features for (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        help="Specific tickers to process (default: all active)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write to R2 or Supabase",
    )
    parser.add_argument(
        "--create-snapshot",
        action="store_true",
        help="Create price snapshot from individual ticker files",
    )

    args = parser.parse_args()

    # Parse run date
    if args.run_date:
        run_date = date.fromisoformat(args.run_date)
    else:
        run_date = date.today()

    with FeaturesComputer() as computer:
        if args.create_snapshot:
            # Just create the price snapshot
            tickers = args.tickers
            if not tickers:
                tickers = computer.db.get_active_tickers()
            computer.create_price_snapshot_from_ingestion(run_date, tickers)
        else:
            # Full feature computation
            result = computer.compute_daily_features(
                run_date=run_date,
                tickers=args.tickers,
                dry_run=args.dry_run,
            )

            print(f"\n{'=' * 70}")
            print("SUMMARY")
            print(f"{'=' * 70}")
            for key, value in result.items():
                print(f"  {key}: {value}")
