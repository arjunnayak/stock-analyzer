"""
Daily feature computation for Step 2 of the pipeline.

Computes wide-row features for all active tickers:
- Technical indicators (EMA 200, EMA 50)
- Valuation metrics (EV/EBITDA)
- Stores to R2 as date-partitioned parquet + latest.parquet
- Upserts indicator_state for incremental computation

For backfill operations, uses point-in-time fundamentals (merge_asof)
to ensure historical EV/EBITDA reflects the fundamentals available at that time.
"""

from datetime import date, timedelta
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

    # =========================================================================
    # Backfill Methods - Use Point-in-Time Fundamentals
    # =========================================================================

    def backfill_features(
        self,
        start_date: date,
        end_date: date,
        tickers: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Backfill historical features with point-in-time fundamentals.

        Unlike daily incremental computation, backfill:
        - Uses merge_asof to get fundamentals valid at each price date
        - Computes EMA sequentially from start_date
        - Writes features for each date in the range

        Args:
            start_date: Start date for backfill
            end_date: End date for backfill
            tickers: Optional list of tickers (defaults to active tickers)
            dry_run: If True, don't write to R2

        Returns:
            Summary dict with statistics
        """
        print(f"\n{'=' * 70}")
        print(f"FEATURE BACKFILL - {start_date} to {end_date}")
        print(f"{'=' * 70}\n")

        # Get tickers
        if tickers is None:
            tickers = self.db.get_active_tickers()

        if not tickers:
            print("No tickers to process. Exiting.")
            return {"status": "no_tickers", "tickers_processed": 0}

        print(f"Tickers to backfill: {len(tickers)}")

        # Load entity metadata
        metadata_df = self.db.get_entity_metadata(tickers)

        # Process each ticker
        all_features = []
        tickers_processed = 0
        tickers_failed = 0

        for ticker in tickers:
            print(f"\nProcessing {ticker}...")

            try:
                ticker_features = self._backfill_ticker(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    metadata_df=metadata_df,
                )

                if ticker_features is not None and not ticker_features.empty:
                    all_features.append(ticker_features)
                    tickers_processed += 1
                    print(f"  {len(ticker_features)} feature rows computed")
                else:
                    tickers_failed += 1
                    print(f"  No features computed")

            except Exception as e:
                print(f"  Error: {e}")
                tickers_failed += 1

        if not all_features:
            print("\nNo features computed. Exiting.")
            return {
                "status": "no_features",
                "tickers_processed": 0,
                "tickers_failed": tickers_failed,
            }

        # Combine all features
        combined_df = pd.concat(all_features, ignore_index=True)

        # Group by date and write
        print(f"\nWriting {len(combined_df)} total feature rows...")

        if not dry_run:
            dates_written = self._write_features_by_date(combined_df)
            print(f"Wrote features for {dates_written} dates")

            # Update indicator_state with final state for each ticker
            self._update_indicator_state_from_backfill(combined_df)
        else:
            print("[DRY RUN] Skipping writes")

        return {
            "status": "success" if not dry_run else "dry_run",
            "tickers_processed": tickers_processed,
            "tickers_failed": tickers_failed,
            "total_rows": len(combined_df),
            "date_range": f"{start_date} to {end_date}",
        }

    def _backfill_ticker(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        metadata_df: pd.DataFrame,
    ) -> Optional[pd.DataFrame]:
        """
        Backfill features for a single ticker with point-in-time fundamentals.

        Args:
            ticker: Ticker symbol
            start_date: Start date
            end_date: End date
            metadata_df: Entity metadata

        Returns:
            DataFrame with features for all dates, or None if failed
        """
        # Load prices - need extra lookback for EMA warmup
        warmup_start = start_date - timedelta(days=300)  # ~200 trading days
        prices_df = self.reader.get_prices(ticker, warmup_start, end_date)

        if prices_df.empty:
            print(f"  No price data found")
            return None

        # Ensure date column is datetime
        prices_df["date"] = pd.to_datetime(prices_df["date"])
        prices_df = prices_df.sort_values("date").reset_index(drop=True)

        # Load fundamentals - need extra lookback to cover first price dates
        fund_start = warmup_start - timedelta(days=180)  # Extra buffer for quarterly data
        fundamentals_df = self.reader.get_fundamentals(ticker, fund_start, end_date)

        # Prepare fundamentals for point-in-time join
        fund_pit = self._prepare_fundamentals_for_pit(fundamentals_df)

        # Join fundamentals to prices using point-in-time logic
        if fund_pit is not None and not fund_pit.empty:
            prices_with_fund = pd.merge_asof(
                prices_df.sort_values("date"),
                fund_pit.sort_values("date"),
                on="date",
                direction="backward",  # Use most recent fundamental data before each price date
            )
        else:
            print(f"  No fundamental data, EV/EBITDA will be null")
            prices_with_fund = prices_df.copy()
            for col in ["shares_outstanding", "total_debt", "cash_and_equivalents", "ebitda_ttm"]:
                prices_with_fund[col] = None

        # Compute EMAs incrementally
        features = self._compute_ema_series(prices_with_fund)

        # Compute EV/EBITDA for each row
        features = self._compute_valuation_series(features)

        # Add metadata
        sector = None
        if not metadata_df.empty:
            ticker_meta = metadata_df[metadata_df["ticker"] == ticker]
            if not ticker_meta.empty:
                sector = ticker_meta.iloc[0].get("sector")

        features["ticker"] = ticker
        features["sector"] = sector

        # Filter to requested date range (exclude warmup period)
        features = features[features["date"].dt.date >= start_date]
        features = features[features["date"].dt.date <= end_date]

        # Add prev values
        features["prev_close"] = features["close"].shift(1)
        features["prev_ema_200"] = features["ema_200"].shift(1)
        features["prev_ema_50"] = features["ema_50"].shift(1)

        # Convert date back to date type
        features["date"] = features["date"].dt.date

        # Select and order columns
        columns = [
            "date", "ticker", "close", "volume",
            "ema_200", "ema_50", "prev_close", "prev_ema_200", "prev_ema_50",
            "ev_ebitda", "market_cap", "enterprise_value", "ebitda_ttm", "sector"
        ]

        return features[[c for c in columns if c in features.columns]]

    def _prepare_fundamentals_for_pit(
        self, fundamentals_df: pd.DataFrame
    ) -> Optional[pd.DataFrame]:
        """
        Prepare fundamentals DataFrame for point-in-time merge.

        Computes TTM values and extracts balance sheet items.

        Args:
            fundamentals_df: Raw quarterly fundamentals

        Returns:
            DataFrame with date, shares_outstanding, total_debt, cash, ebitda_ttm
        """
        if fundamentals_df.empty:
            return None

        df = fundamentals_df.copy()

        # Normalize date column
        if "period_end" in df.columns:
            df = df.rename(columns={"period_end": "date"})

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        # Filter to quarterly data if period column exists
        if "period" in df.columns:
            df = df[df["period"].str.contains("Quarter", na=False)]

        if df.empty:
            return None

        # Map average_shares to shares_outstanding if needed
        if "shares_outstanding" not in df.columns and "average_shares" in df.columns:
            df["shares_outstanding"] = df["average_shares"]

        # Get EBITDA (use income_before_depreciation if available)
        if "income_before_depreciation" in df.columns:
            df["ebitda_q"] = df["income_before_depreciation"]
        else:
            # Fallback: compute from components
            df["ebitda_q"] = df.get("net_income", 0)
            if "interest_expense" in df.columns:
                df["ebitda_q"] = df["ebitda_q"] + df["interest_expense"].fillna(0)
            if "income_taxes" in df.columns:
                df["ebitda_q"] = df["ebitda_q"] + df["income_taxes"].fillna(0)
            if "depreciation_and_amortization" in df.columns:
                df["ebitda_q"] = df["ebitda_q"] + df["depreciation_and_amortization"].fillna(0)

        # Compute TTM EBITDA (trailing 4 quarters)
        df["ebitda_ttm"] = df["ebitda_q"].rolling(window=4, min_periods=4).sum()

        # Get balance sheet items
        total_debt = pd.Series(0, index=df.index)
        if "long_term_debt" in df.columns:
            total_debt = df["long_term_debt"].fillna(0)
        if "current_portion_long_term_debt" in df.columns:
            total_debt = total_debt + df["current_portion_long_term_debt"].fillna(0)
        df["total_debt"] = total_debt

        if "cash_and_equivalents" not in df.columns:
            df["cash_and_equivalents"] = 0

        # Select relevant columns
        result_cols = ["date", "shares_outstanding", "total_debt", "cash_and_equivalents", "ebitda_ttm"]
        result = df[[c for c in result_cols if c in df.columns]].copy()

        return result

    def _compute_ema_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute EMA series incrementally.

        Args:
            df: DataFrame with close prices, sorted by date

        Returns:
            DataFrame with ema_200 and ema_50 columns added
        """
        df = df.copy()

        # Use pandas ewm for efficient EMA computation
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()

        return df

    def _compute_valuation_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute EV/EBITDA for each row using point-in-time fundamentals.

        Args:
            df: DataFrame with close, shares_outstanding, total_debt, cash, ebitda_ttm

        Returns:
            DataFrame with ev_ebitda, market_cap, enterprise_value added
        """
        df = df.copy()

        # Market cap
        if "shares_outstanding" in df.columns:
            df["market_cap"] = df["close"] * df["shares_outstanding"].fillna(0)
        else:
            df["market_cap"] = None

        # Enterprise value = market_cap + total_debt - cash
        df["enterprise_value"] = None
        if "market_cap" in df.columns and "total_debt" in df.columns:
            df["enterprise_value"] = (
                df["market_cap"]
                + df["total_debt"].fillna(0)
                - df.get("cash_and_equivalents", pd.Series(0, index=df.index)).fillna(0)
            )

        # EV/EBITDA
        df["ev_ebitda"] = None
        if "enterprise_value" in df.columns and "ebitda_ttm" in df.columns:
            valid_mask = (df["ebitda_ttm"] > 0) & df["enterprise_value"].notna()
            df.loc[valid_mask, "ev_ebitda"] = (
                df.loc[valid_mask, "enterprise_value"] / df.loc[valid_mask, "ebitda_ttm"]
            )

        return df

    def _write_features_by_date(self, features_df: pd.DataFrame) -> int:
        """
        Write features grouped by date.

        Args:
            features_df: Combined features DataFrame

        Returns:
            Number of dates written
        """
        # Group by date
        features_df["date"] = pd.to_datetime(features_df["date"])
        grouped = features_df.groupby(features_df["date"].dt.date)

        dates_written = 0
        for run_date, group_df in grouped:
            # Convert date column back to just date
            group_df = group_df.copy()
            group_df["date"] = run_date

            self.r2.put_features(run_date, group_df)
            dates_written += 1

        # Also update latest.parquet with most recent date
        latest_date = features_df["date"].max().date()
        latest_df = features_df[features_df["date"].dt.date == latest_date].copy()
        latest_df["date"] = latest_date
        self.r2.put_features_latest(latest_df)

        return dates_written

    def _update_indicator_state_from_backfill(self, features_df: pd.DataFrame) -> None:
        """
        Update indicator_state with final values from backfill.

        Args:
            features_df: Features DataFrame from backfill
        """
        # Get final state for each ticker
        features_df["date"] = pd.to_datetime(features_df["date"])
        latest = features_df.loc[features_df.groupby("ticker")["date"].idxmax()]

        updates = []
        for _, row in latest.iterrows():
            updates.append({
                "ticker": row["ticker"],
                "last_price_date": row["date"].date().isoformat() if hasattr(row["date"], "date") else str(row["date"]),
                "last_close": row["close"],
                "prev_close": row.get("prev_close"),
                "prev_ema_200": row.get("prev_ema_200"),
                "prev_ema_50": row.get("prev_ema_50"),
                "ema_200": row["ema_200"],
                "ema_50": row["ema_50"],
            })

        if updates:
            count = self.db.upsert_indicator_state(updates)
            print(f"Updated indicator_state for {count} tickers")


if __name__ == "__main__":
    import argparse

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
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run backfill mode with point-in-time fundamentals",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for backfill (YYYY-MM-DD). Required with --backfill.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for backfill (YYYY-MM-DD). Defaults to today.",
    )

    args = parser.parse_args()

    # Parse dates
    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start_date = date.fromisoformat(args.start_date) if args.start_date else None

    with FeaturesComputer() as computer:
        if args.backfill:
            # Backfill mode with point-in-time fundamentals
            if not start_date:
                print("Error: --start-date is required for backfill mode")
                exit(1)

            result = computer.backfill_features(
                start_date=start_date,
                end_date=end_date,
                tickers=args.tickers,
                dry_run=args.dry_run,
            )
        elif args.create_snapshot:
            # Just create the price snapshot
            tickers = args.tickers
            if not tickers:
                tickers = computer.db.get_active_tickers()
            computer.create_price_snapshot_from_ingestion(run_date, tickers)
            result = {"status": "snapshot_created"}
        else:
            # Daily incremental feature computation
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
