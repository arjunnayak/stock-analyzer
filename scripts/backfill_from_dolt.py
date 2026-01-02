#!/usr/bin/env python3
"""
Backfill CLI for loading historical price and fundamental data from Dolt database.

Dolt is a SQL database with Git-like versioning, perfect for storing historical market data.

Usage:
    # Backfill specific tickers
    python scripts/backfill_from_dolt.py --tickers AAPL MSFT GOOGL

    # Backfill from file
    python scripts/backfill_from_dolt.py --ticker-file tickers.txt

    # Backfill with date range
    python scripts/backfill_from_dolt.py --tickers AAPL --start-date 2020-01-01 --end-date 2024-12-31

    # Backfill fundamentals only
    python scripts/backfill_from_dolt.py --tickers AAPL --fundamentals-only

    # Dry run (no writes)
    python scripts/backfill_from_dolt.py --tickers AAPL --dry-run

Dolt Database Schema Expected:
    - Table: prices (ticker, date, open, high, low, close, adj_close, volume)
    - Table: fundamentals (ticker, period_end, revenue, earnings, etc.)
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    print("⚠️  mysql-connector-python not installed. Install with:")
    print("   uv add mysql-connector-python")
    print("   or: pip install mysql-connector-python")
    sys.exit(1)

from src.config import config
from src.storage.r2_client import R2Client


class DoltClient:
    """Client for reading data from local Dolt database."""

    def __init__(
        self,
        host: str = "localhost",
        stocks_port: int = 3306,
        earnings_port: int = 3307,
        user: str = "root",
        password: str = "",
    ):
        """
        Initialize Dolt database connection.

        Args:
            host: Database host (default: localhost)
            stocks_port: Stocks database port (default: 3306)
            earnings_port: Earnings database port (default: 3307)
            user: Database user (default: root)
            password: Database password (default: empty)
        """
        self.host = host
        self.user = user
        self.password = password
        self.stocks_port = stocks_port
        self.earnings_port = earnings_port
        self.stocks_conn = None
        self.earnings_conn = None

    def connect(self):
        """Establish database connections."""
        try:
            self.stocks_conn = mysql.connector.connect(
                host=self.host,
                port=self.stocks_port,
                database="stocks",
                user=self.user,
                password=self.password,
            )
            print(f"✓ Connected to Dolt stocks database (port {self.stocks_port})")
        except MySQLError as e:
            print(f"✗ Failed to connect to stocks DB: {e}")
            return False

        try:
            self.earnings_conn = mysql.connector.connect(
                host=self.host,
                port=self.earnings_port,
                database="earnings",
                user=self.user,
                password=self.password,
            )
            print(f"✓ Connected to Dolt earnings database (port {self.earnings_port})")
            return True
        except MySQLError as e:
            print(f"✗ Failed to connect to earnings DB: {e}")
            if self.stocks_conn and self.stocks_conn.is_connected():
                self.stocks_conn.close()
            return False

    def disconnect(self):
        """Close database connections."""
        if self.stocks_conn and self.stocks_conn.is_connected():
            self.stocks_conn.close()
        if self.earnings_conn and self.earnings_conn.is_connected():
            self.earnings_conn.close()
        print("✓ Disconnected from Dolt databases")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def get_prices(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Fetch price data from Dolt stocks database (ohlcv table).

        Args:
            ticker: Stock ticker (act_symbol)
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            DataFrame with price data (date, open, high, low, close, volume)
        """
        query = """
            SELECT date, open, high, low, close, volume
            FROM ohlcv
            WHERE act_symbol = %s
        """
        params = [ticker]

        if start_date:
            query += " AND date >= %s"
            params.append(start_date)

        if end_date:
            query += " AND date <= %s"
            params.append(end_date)

        query += " ORDER BY date ASC"

        try:
            df = pd.read_sql(query, self.stocks_conn, params=params)
            df["date"] = pd.to_datetime(df["date"])
            return df
        except Exception as e:
            print(f"✗ Error fetching prices for {ticker}: {e}")
            return pd.DataFrame()

    def get_fundamentals(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Fetch fundamental data from Dolt earnings database.

        Joins income_statement, balance_sheet_assets, balance_sheet_liabilities,
        and balance_sheet_equity to get all fields needed for EV/EBITDA calculation.

        Args:
            ticker: Stock ticker (act_symbol)
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            DataFrame with fundamental data including balance sheet items
        """
        # Join all relevant tables on date and period
        query = """
            SELECT
                inc.date as period_end,
                inc.period,
                inc.sales as revenue,
                inc.gross_profit,
                inc.income_after_depreciation_and_amortization as operating_income,
                inc.non_operating_income,
                inc.net_income,
                inc.diluted_net_eps,
                inc.average_shares,
                inc.pretax_income,
                inc.income_taxes,
                inc.interest_expense,
                inc.depreciation_and_amortization,
                inc.cost_of_goods,
                inc.selling_administrative_depreciation_amortization_expenses,
                inc.income_from_continuing_operations,
                inc.income_before_depreciation_and_amortization,
                -- Balance sheet assets
                assets.cash_and_equivalents,
                -- Balance sheet liabilities
                liab.long_term_debt,
                liab.current_portion_long_term_debt,
                liab.total_liabilities,
                -- Balance sheet equity
                equity.shares_outstanding,
                equity.total_equity,
                equity.book_value_per_share
            FROM income_statement inc
            LEFT JOIN balance_sheet_assets assets
                ON inc.act_symbol = assets.act_symbol
                AND inc.date = assets.date
                AND inc.period = assets.period
            LEFT JOIN balance_sheet_liabilities liab
                ON inc.act_symbol = liab.act_symbol
                AND inc.date = liab.date
                AND inc.period = liab.period
            LEFT JOIN balance_sheet_equity equity
                ON inc.act_symbol = equity.act_symbol
                AND inc.date = equity.date
                AND inc.period = equity.period
            WHERE inc.act_symbol = %s
        """
        params = [ticker]

        if start_date:
            query += " AND inc.date >= %s"
            params.append(start_date)

        if end_date:
            query += " AND inc.date <= %s"
            params.append(end_date)

        query += " ORDER BY inc.date ASC"

        try:
            df = pd.read_sql(query, self.earnings_conn, params=params)
            df["period_end"] = pd.to_datetime(df["period_end"])

            # Compute EBITDA if we have the components
            # EBITDA = Operating Income + Depreciation & Amortization
            # Or: EBITDA = Net Income + Interest + Taxes + D&A
            if "depreciation_and_amortization" in df.columns:
                if "operating_income" in df.columns:
                    df["ebitda"] = (
                        df["operating_income"].fillna(0)
                        + df["depreciation_and_amortization"].fillna(0)
                    )
                elif all(col in df.columns for col in ["net_income", "interest_expense", "income_taxes"]):
                    df["ebitda"] = (
                        df["net_income"].fillna(0)
                        + df["interest_expense"].fillna(0)
                        + df["income_taxes"].fillna(0)
                        + df["depreciation_and_amortization"].fillna(0)
                    )

            # Compute total_debt = long_term_debt + current_portion_long_term_debt
            if "long_term_debt" in df.columns:
                df["total_debt"] = df["long_term_debt"].fillna(0)
                if "current_portion_long_term_debt" in df.columns:
                    df["total_debt"] = df["total_debt"] + df["current_portion_long_term_debt"].fillna(0)

            return df
        except Exception as e:
            print(f"✗ Error fetching fundamentals for {ticker}: {e}")
            return pd.DataFrame()

    def get_available_tickers(self) -> list[str]:
        """
        Get list of all available tickers in stocks database.

        Returns:
            List of ticker symbols
        """
        query = "SELECT DISTINCT act_symbol FROM ohlcv ORDER BY act_symbol"

        try:
            df = pd.read_sql(query, self.stocks_conn)
            return df["act_symbol"].tolist()
        except Exception as e:
            print(f"✗ Error fetching tickers: {e}")
            return []


class BackfillPipeline:
    """Pipeline for backfilling data from Dolt to R2."""

    def __init__(self, dolt_client: DoltClient, r2_client: R2Client, dry_run: bool = False):
        """
        Initialize backfill pipeline.

        Args:
            dolt_client: Dolt database client
            r2_client: R2 storage client
            dry_run: If True, don't write to R2
        """
        self.dolt = dolt_client
        self.r2 = r2_client
        self.dry_run = dry_run

    def backfill_prices(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        Backfill price data for a ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            Summary statistics
        """
        print(f"\nBackfilling prices for {ticker}...")

        # Fetch from Dolt
        df = self.dolt.get_prices(ticker, start_date, end_date)

        if df.empty:
            print(f"  ⚠️  No price data found")
            return {"ticker": ticker, "dataset": "prices", "rows": 0, "files": 0, "status": "no_data"}

        print(f"  ✓ Fetched {len(df)} rows from Dolt")

        if self.dry_run:
            print(f"  🏃 DRY RUN - Would write {len(df)} rows")
            return {"ticker": ticker, "dataset": "prices", "rows": len(df), "files": 0, "status": "dry_run"}

        # Partition by month and write to R2
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month

        groups = df.groupby(["year", "month"])
        files_written = 0

        for (year, month), group_df in groups:
            data_df = group_df.drop(columns=["year", "month"])

            key = self.r2.build_key(dataset="prices", ticker=ticker, year=year, month=month)

            self.r2.merge_and_put(key, data_df, dedupe_column="date")
            files_written += 1

        print(f"  ✓ Wrote {files_written} monthly files to R2")

        return {
            "ticker": ticker,
            "dataset": "prices",
            "rows": len(df),
            "files": files_written,
            "status": "success",
        }

    def backfill_fundamentals(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        fundamentals_df: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        Backfill fundamental data for a ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date (optional)
            end_date: End date (optional)
            fundamentals_df: Pre-fetched fundamentals data (optional, avoids refetch)

        Returns:
            Summary statistics
        """
        print(f"\nBackfilling fundamentals for {ticker}...")

        # Use pre-fetched data or fetch from Dolt
        if fundamentals_df is not None:
            df = fundamentals_df
        else:
            df = self.dolt.get_fundamentals(ticker, start_date, end_date)

        if df.empty:
            print(f"  ⚠️  No fundamental data found")
            return {"ticker": ticker, "dataset": "fundamentals", "rows": 0, "files": 0, "status": "no_data"}

        print(f"  ✓ Fetched {len(df)} rows from Dolt")

        if self.dry_run:
            print(f"  🏃 DRY RUN - Would write {len(df)} rows")
            return {
                "ticker": ticker,
                "dataset": "fundamentals",
                "rows": len(df),
                "files": 0,
                "status": "dry_run",
            }

        # For fundamentals, partition by year of period_end
        df["year"] = df["period_end"].dt.year
        df["month"] = df["period_end"].dt.month

        groups = df.groupby(["year", "month"])
        files_written = 0

        for (year, month), group_df in groups:
            data_df = group_df.drop(columns=["year", "month"])

            key = self.r2.build_key(dataset="fundamentals", ticker=ticker, year=year, month=month)

            self.r2.merge_and_put(key, data_df, dedupe_column="period_end")
            files_written += 1

        print(f"  ✓ Wrote {files_written} monthly files to R2")

        return {
            "ticker": ticker,
            "dataset": "fundamentals",
            "rows": len(df),
            "files": files_written,
            "status": "success",
        }

    def update_fundamentals_latest(
        self,
        ticker: str,
        fundamentals_df: pd.DataFrame,
    ) -> bool:
        """
        Compute TTM values and update fundamentals_latest table.

        Args:
            ticker: Stock ticker
            fundamentals_df: Fundamentals dataframe with quarterly data

        Returns:
            True if successful
        """
        if fundamentals_df.empty:
            return False

        # Filter to quarterly data only (exclude annual "Year" rows)
        df = fundamentals_df.copy()
        if "period" in df.columns:
            df = df[df["period"].str.contains("Quarter", case=False, na=False)]
            if df.empty:
                print(f"  ⚠️  No quarterly data found after filtering")
                return False

        # Sort by period_end desc to get most recent quarters
        df = df.sort_values("period_end", ascending=False)

        # Get the 4 most recent quarters for TTM calculation
        recent_4q = df.head(4)

        if len(recent_4q) < 4:
            print(f"  ⚠️  Not enough quarters for TTM ({len(recent_4q)}/4)")
            return False

        # Compute TTM values (sum of last 4 quarters)
        ebitda_ttm = None
        if "ebitda" in df.columns:
            ebitda_ttm = float(recent_4q["ebitda"].sum())
        elif "depreciation_and_amortization" in df.columns and "operating_income" in df.columns:
            ebitda_4q = (
                recent_4q["operating_income"].fillna(0)
                + recent_4q["depreciation_and_amortization"].fillna(0)
            )
            ebitda_ttm = float(ebitda_4q.sum())

        # Compute operating income TTM (EBIT)
        operating_income_ttm = None
        if "operating_income" in df.columns:
            op_income_values = recent_4q["operating_income"].dropna()
            if len(op_income_values) >= 4:
                operating_income_ttm = float(op_income_values.sum())

        revenue_ttm = None
        if "revenue" in df.columns:
            revenue_ttm = float(recent_4q["revenue"].fillna(0).sum())

        # Get latest balance sheet values (most recent quarter only)
        latest = df.iloc[0]

        total_debt = None
        if "total_debt" in df.columns:
            total_debt = float(latest["total_debt"]) if pd.notna(latest["total_debt"]) else None
        elif "long_term_debt" in df.columns:
            total_debt = float(latest["long_term_debt"]) if pd.notna(latest["long_term_debt"]) else 0
            if "current_portion_long_term_debt" in df.columns and pd.notna(
                latest["current_portion_long_term_debt"]
            ):
                total_debt += float(latest["current_portion_long_term_debt"])

        cash_and_equivalents = None
        if "cash_and_equivalents" in df.columns and pd.notna(latest["cash_and_equivalents"]):
            cash_and_equivalents = float(latest["cash_and_equivalents"])

        shares_outstanding = None
        if "shares_outstanding" in df.columns and pd.notna(latest["shares_outstanding"]):
            shares_outstanding = float(latest["shares_outstanding"])
        elif "average_shares" in df.columns and pd.notna(latest["average_shares"]):
            shares_outstanding = float(latest["average_shares"])

        # Compute net_debt
        net_debt = None
        if total_debt is not None:
            net_debt = total_debt - (cash_and_equivalents or 0)

        # Build the row for upsert
        asof_date = latest["period_end"]
        if hasattr(asof_date, "date"):
            asof_date = asof_date.date()
        elif isinstance(asof_date, str):
            asof_date = datetime.strptime(asof_date, "%Y-%m-%d").date()

        row = {
            "ticker": ticker,
            "asof_date": asof_date.isoformat(),
            "ebitda_ttm": ebitda_ttm,
            "operating_income_ttm": operating_income_ttm,
            "revenue_ttm": revenue_ttm,
            "net_debt": net_debt,
            "shares_outstanding": shares_outstanding,
            "total_debt": total_debt,
            "cash_and_equivalents": cash_and_equivalents,
        }

        if self.dry_run:
            print(f"  🏃 [DRY RUN] Would upsert fundamentals_latest: ebitda_ttm={ebitda_ttm}, operating_income_ttm={operating_income_ttm}, shares={shares_outstanding}")
            return True

        # Upsert to Supabase
        try:
            from src.storage.supabase_db import SupabaseDB

            db = SupabaseDB()
            db.upsert_fundamentals_latest([row])
            print(f"  ✓ Updated fundamentals_latest: ebitda_ttm={ebitda_ttm:.0f}" if ebitda_ttm else "  ✓ Updated fundamentals_latest")
            return True
        except Exception as e:
            print(f"  ⚠️  Failed to update fundamentals_latest: {e}")
            return False


def load_tickers_from_file(file_path: str) -> list[str]:
    """Load ticker list from file (one per line)."""
    with open(file_path) as f:
        return [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Backfill historical data from Dolt database to R2 storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Ticker selection
    ticker_group = parser.add_mutually_exclusive_group(required=True)
    ticker_group.add_argument("--tickers", nargs="+", help="List of ticker symbols")
    ticker_group.add_argument("--ticker-file", help="File containing ticker symbols (one per line)")
    ticker_group.add_argument("--all", action="store_true", help="Backfill all tickers in Dolt database")

    # Date range
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")

    # Dataset selection
    parser.add_argument("--prices-only", action="store_true", help="Only backfill price data")
    parser.add_argument("--fundamentals-only", action="store_true", help="Only backfill fundamental data")

    # Dolt connection
    parser.add_argument("--dolt-host", default="localhost", help="Dolt host (default: localhost)")
    parser.add_argument("--stocks-port", type=int, default=3306, help="Stocks DB port (default: 3306)")
    parser.add_argument("--earnings-port", type=int, default=3307, help="Earnings DB port (default: 3307)")
    parser.add_argument("--dolt-user", default="root", help="Dolt user (default: root)")
    parser.add_argument("--dolt-password", default="", help="Dolt password (default: empty)")

    # Options
    parser.add_argument("--dry-run", action="store_true", help="Don't write to R2, just show what would happen")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    return parser.parse_args()


def main():
    """Run backfill CLI."""
    args = parse_args()

    print("=" * 70)
    print("DOLT → R2 BACKFILL")
    print("=" * 70)

    # Parse dates
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date() if args.start_date else None
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else None

    if start_date and end_date and start_date > end_date:
        print("❌ ERROR: start-date must be before end-date")
        return 1

    # Get ticker list
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    elif args.ticker_file:
        tickers = load_tickers_from_file(args.ticker_file)
        print(f"Loaded {len(tickers)} tickers from {args.ticker_file}")
    else:  # --all
        # Connect to get ticker list
        with DoltClient(
            host=args.dolt_host,
            stocks_port=args.stocks_port,
            earnings_port=args.earnings_port,
            user=args.dolt_user,
            password=args.dolt_password,
        ) as dolt:
            tickers = dolt.get_available_tickers()
            print(f"Found {len(tickers)} tickers in Dolt database")

    if not tickers:
        print("❌ ERROR: No tickers to process")
        return 1

    # Connect to Dolt and R2
    dolt_client = DoltClient(
        host=args.dolt_host,
        stocks_port=args.stocks_port,
        earnings_port=args.earnings_port,
        user=args.dolt_user,
        password=args.dolt_password,
    )

    if not dolt_client.connect():
        return 1

    r2_client = R2Client()
    pipeline = BackfillPipeline(dolt_client, r2_client, dry_run=args.dry_run)

    # Run backfill
    print(f"\nProcessing {len(tickers)} ticker(s)")
    if start_date or end_date:
        print(f"Date range: {start_date or 'beginning'} to {end_date or 'latest'}")
    if args.dry_run:
        print("🏃 DRY RUN MODE - No data will be written")

    results = []

    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] {ticker}")
        print("-" * 70)

        # Backfill prices
        if not args.fundamentals_only:
            result = pipeline.backfill_prices(ticker, start_date, end_date)
            results.append(result)

        # Backfill fundamentals
        if not args.prices_only:
            # Get fundamentals data
            fundamentals_df = dolt_client.get_fundamentals(ticker, start_date, end_date)

            # Backfill to R2 (pass pre-fetched data to avoid double fetch)
            result = pipeline.backfill_fundamentals(
                ticker, start_date, end_date, fundamentals_df=fundamentals_df
            )
            results.append(result)

            # Update fundamentals_latest table with TTM values
            if result["status"] == "success" and not fundamentals_df.empty:
                pipeline.update_fundamentals_latest(ticker, fundamentals_df)

    dolt_client.disconnect()

    # Summary
    print("\n" + "=" * 70)
    print("BACKFILL SUMMARY")
    print("=" * 70)

    total_rows = sum(r["rows"] for r in results)
    total_files = sum(r["files"] for r in results)
    successful = sum(1 for r in results if r["status"] == "success")
    no_data = sum(1 for r in results if r["status"] == "no_data")

    print(f"Total tickers processed: {len(tickers)}")
    print(f"Successful: {successful}")
    print(f"No data: {no_data}")
    print(f"Total rows: {total_rows:,}")
    print(f"Total files: {total_files}")

    if args.dry_run:
        print("\n🏃 DRY RUN - No data was written to R2")

    return 0


if __name__ == "__main__":
    sys.exit(main())
