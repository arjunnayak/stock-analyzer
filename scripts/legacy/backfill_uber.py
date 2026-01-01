#!/usr/bin/env python3
"""
Backfill complete data for UBER (end-to-end test).

This script will:
1. Ingest historical price data from EODHD or Dolt
2. Ingest fundamental data (if available)
3. Compute technical signals (SMA 200)
4. Compute valuation signals (EV/Revenue, EV/EBITDA)
5. Verify all data in R2
6. Test signal evaluation

Usage:
    # Using EODHD (requires API key, limited requests):
    python scripts/backfill_uber.py [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]

    # Using Dolt (free, requires Dolt running locally):
    python scripts/backfill_uber.py --use-dolt [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.config import config
from src.ingest.ingest_prices import PriceIngester
from src.reader import TimeSeriesReader
from src.signals.compute import MetricsComputer
from src.signals.technical import TechnicalSignals
from src.signals.valuation import ValuationSignals
from src.storage.r2_client import R2Client

# Dolt imports (optional)
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    DOLT_AVAILABLE = True
except ImportError:
    DOLT_AVAILABLE = False


class DoltClient:
    """Lightweight Dolt client for reading price and fundamental data."""

    def __init__(self, host: str = "localhost", stocks_port: int = 3306, earnings_port: int = 3307):
        self.host = host
        self.stocks_port = stocks_port
        self.earnings_port = earnings_port
        self.stocks_conn = None
        self.earnings_conn = None

    def connect(self):
        """Connect to Dolt databases."""
        try:
            self.stocks_conn = mysql.connector.connect(
                host=self.host, port=self.stocks_port, database="stocks", user="root", password=""
            )
            print(f"✓ Connected to Dolt stocks DB (port {self.stocks_port})")
        except MySQLError as e:
            print(f"✗ Failed to connect to stocks DB: {e}")
            return False

        try:
            self.earnings_conn = mysql.connector.connect(
                host=self.host, port=self.earnings_port, database="earnings", user="root", password=""
            )
            print(f"✓ Connected to Dolt earnings DB (port {self.earnings_port})")
            return True
        except MySQLError as e:
            print(f"⚠️  Failed to connect to earnings DB: {e}")
            # Continue without earnings
            return True  # Stocks DB is enough for prices

    def disconnect(self):
        """Disconnect from Dolt databases."""
        if self.stocks_conn and self.stocks_conn.is_connected():
            self.stocks_conn.close()
        if self.earnings_conn and self.earnings_conn.is_connected():
            self.earnings_conn.close()

    def get_prices(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Fetch price data from Dolt ohlcv table."""
        query = """
            SELECT date, open, high, low, close, volume
            FROM ohlcv
            WHERE act_symbol = %s AND date >= %s AND date <= %s
            ORDER BY date ASC
        """
        df = pd.read_sql(query, self.stocks_conn, params=[ticker, start_date, end_date])
        df["date"] = pd.to_datetime(df["date"])
        # Add adj_close (assume same as close if not available)
        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]
        return df

    def get_fundamentals(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Fetch fundamental data from Dolt income_statement table."""
        if not self.earnings_conn or not self.earnings_conn.is_connected():
            return pd.DataFrame()

        query = """
            SELECT
                date as period_end,
                period,
                sales as revenue,
                gross_profit,
                income_after_depreciation_and_amortization as operating_income,
                net_income,
                diluted_net_eps,
                average_shares,
                pretax_income,
                income_taxes,
                depreciation_and_amortization,
                cost_of_goods,
                selling_administrative_depreciation_amortization_expenses,
                income_from_continuing_operations
            FROM income_statement
            WHERE act_symbol = %s AND date >= %s AND date <= %s
            ORDER BY date ASC
        """
        df = pd.read_sql(query, self.earnings_conn, params=[ticker, start_date, end_date])
        df["period_end"] = pd.to_datetime(df["period_end"])
        return df


def step_1_ingest_prices_from_dolt(ticker: str, start_date: date, end_date: date, dolt: DoltClient):
    """Step 1: Ingest price data from Dolt."""
    print("\n" + "=" * 70)
    print("STEP 1: Ingest Price Data (from Dolt)")
    print("=" * 70)

    r2 = R2Client()

    print(f"Fetching {ticker} price data from Dolt...")
    print(f"Date range: {start_date} to {end_date}")

    df = dolt.get_prices(ticker, start_date, end_date)

    if df.empty:
        print(f"\n✗ FAILED - No price data found in Dolt for {ticker}")
        return False

    print(f"✓ Fetched {len(df)} rows from Dolt")

    # Partition by month and write to R2
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    groups = df.groupby(["year", "month"])
    files_written = 0

    for (year, month), group_df in groups:
        data_df = group_df.drop(columns=["year", "month"])
        key = r2.build_key(dataset="prices", ticker=ticker, year=year, month=month)
        r2.merge_and_put(key, data_df, dedupe_column="date")
        files_written += 1

    print(f"\n✓ SUCCESS")
    print(f"  Rows ingested: {len(df)}")
    print(f"  Files written: {files_written}")
    print(f"  Storage: R2 prices/v1/{ticker}/YYYY/MM/data.parquet")
    return True


def step_1_5_ingest_fundamentals_from_dolt(ticker: str, start_date: date, end_date: date, dolt: DoltClient):
    """Step 1.5: Ingest fundamental data from Dolt."""
    print("\n" + "=" * 70)
    print("STEP 1.5: Ingest Fundamental Data (from Dolt)")
    print("=" * 70)

    r2 = R2Client()

    print(f"Fetching {ticker} fundamental data from Dolt...")

    df = dolt.get_fundamentals(ticker, start_date, end_date)

    if df.empty:
        print(f"\n⚠️  No fundamental data found in Dolt for {ticker}")
        print(f"  Skipping - will continue with price data only")
        return False

    print(f"✓ Fetched {len(df)} rows from Dolt")

    # Partition by year/month of period_end
    df["year"] = df["period_end"].dt.year
    df["month"] = df["period_end"].dt.month
    groups = df.groupby(["year", "month"])
    files_written = 0

    for (year, month), group_df in groups:
        data_df = group_df.drop(columns=["year", "month"])
        key = r2.build_key(dataset="fundamentals", ticker=ticker, year=year, month=month)
        r2.merge_and_put(key, data_df, dedupe_column="period_end")
        files_written += 1

    print(f"\n✓ SUCCESS")
    print(f"  Rows ingested: {len(df)}")
    print(f"  Files written: {files_written}")
    print(f"  Storage: R2 fundamentals/v1/{ticker}/YYYY/MM/data.parquet")
    return True


def step_1_ingest_prices(ticker: str, start_date: date, end_date: date):
    """Step 1: Ingest price data from EODHD."""
    print("\n" + "=" * 70)
    print("STEP 1: Ingest Price Data")
    print("=" * 70)

    ingester = PriceIngester()

    print(f"Fetching {ticker} price data from EODHD...")
    print(f"Date range: {start_date} to {end_date}")

    result = ingester.ingest_ticker(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        exchange="US"
    )

    if result["status"] == "success":
        print(f"\n✓ SUCCESS")
        print(f"  Rows ingested: {result['rows']}")
        print(f"  Files written: {result['files']}")
        print(f"  Storage: R2 prices/v1/{ticker}/YYYY/MM/data.parquet")
        return True
    else:
        print(f"\n✗ FAILED")
        print(f"  No data returned from EODHD for {ticker}")
        print(f"  Check: EODHD_API_KEY is set correctly")
        print(f"  Check: {ticker} is a valid US ticker")
        return False


def step_2_verify_prices(ticker: str):
    """Step 2: Verify price data is readable from R2."""
    print("\n" + "=" * 70)
    print("STEP 2: Verify Price Data in R2")
    print("=" * 70)

    reader = TimeSeriesReader()

    # Try to read recent data
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    df = reader.get_prices(ticker, start_date, end_date)

    if not df.empty:
        print(f"\n✓ SUCCESS - Price data readable")
        print(f"  Rows: {len(df)}")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"  Latest close: ${df['close'].iloc[-1]:.2f}")
        print(f"\nSample data (last 5 days):")
        print(df[['date', 'open', 'high', 'low', 'close', 'volume']].tail())
        return True
    else:
        print(f"\n✗ FAILED - No price data found in R2")
        return False


def step_3_compute_technical_signals(ticker: str):
    """Step 3: Compute technical signals."""
    print("\n" + "=" * 70)
    print("STEP 3: Compute Technical Signals")
    print("=" * 70)

    computer = MetricsComputer()

    print(f"Computing SMA 200 for {ticker}...")

    result = computer.compute_technical_metrics(
        ticker=ticker,
        force=True  # Recompute everything
    )

    if result["status"] == "success":
        print(f"\n✓ SUCCESS")
        print(f"  Rows computed: {result['rows']}")
        print(f"  Files written: {result['files']}")
        print(f"  Storage: R2 signals_technical/v1/{ticker}/YYYY/MM/data.parquet")
        return True
    else:
        print(f"\n✗ FAILED: {result['status']}")
        return False


def step_4_verify_technical_signals(ticker: str):
    """Step 4: Verify technical signals."""
    print("\n" + "=" * 70)
    print("STEP 4: Verify Technical Signals")
    print("=" * 70)

    reader = TimeSeriesReader()

    # Read technical signals
    end_date = date.today()
    start_date = end_date - timedelta(days=365)

    df = reader.r2.get_timeseries("signals_technical", ticker, start_date, end_date)

    if not df.empty:
        # Get latest signals
        latest = df.iloc[-1]

        print(f"\n✓ SUCCESS - Technical signals computed")
        print(f"  Rows: {len(df)}")
        print(f"  Latest date: {latest['date']}")
        print(f"  Latest close: ${latest['close']:.2f}")

        if pd.notna(latest['sma_200']):
            print(f"  SMA-200: ${latest['sma_200']:.2f}")
            print(f"  Position: {latest.get('trend_position', 'N/A')}")
        else:
            print(f"  SMA-200: Not yet available (need 200 days)")

        return True
    else:
        print(f"\n✗ FAILED - No technical signals found")
        return False


def step_5_check_fundamentals(ticker: str):
    """Step 5: Check if fundamental data exists."""
    print("\n" + "=" * 70)
    print("STEP 5: Check Fundamental Data Availability")
    print("=" * 70)

    reader = TimeSeriesReader()

    end_date = date.today()
    start_date = end_date - timedelta(days=5 * 365)  # 5 years

    df = reader.get_fundamentals(ticker, start_date, end_date)

    if not df.empty:
        print(f"\n✓ Fundamental data available")
        print(f"  Rows: {len(df)}")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"  Columns: {list(df.columns)}")
        return True
    else:
        print(f"\n⚠️  No fundamental data in R2 yet")
        print(f"  Note: Fundamentals must be ingested separately")
        print(f"  For MVP, you can:")
        print(f"    1. Backfill from Dolt (if running locally)")
        print(f"    2. Manually ingest from EODHD Fundamentals API")
        print(f"    3. Skip valuation signals for now (use technical only)")
        return False


def step_6_compute_valuation_signals(ticker: str):
    """Step 6: Compute valuation signals (if fundamentals available)."""
    print("\n" + "=" * 70)
    print("STEP 6: Compute Valuation Signals")
    print("=" * 70)

    computer = MetricsComputer()

    print(f"Computing EV/Revenue and EV/EBITDA for {ticker}...")

    result = computer.compute_valuation_metrics(
        ticker=ticker,
        force=True
    )

    if result["status"] == "success":
        print(f"\n✓ SUCCESS")
        print(f"  Rows computed: {result['rows']}")
        print(f"  Files written: {result['files']}")
        return True
    elif result["status"] == "no_fundamental_data":
        print(f"\n⚠️  SKIPPED - No fundamental data available")
        print(f"  Valuation signals require quarterly fundamental data")
        return False
    else:
        print(f"\n✗ FAILED: {result['status']}")
        return False


def step_7_test_valuation_regime(ticker: str):
    """Step 7: Test valuation regime detection."""
    print("\n" + "=" * 70)
    print("STEP 7: Test Valuation Regime Detection")
    print("=" * 70)

    reader = TimeSeriesReader()

    end_date = date.today()
    start_date = end_date - timedelta(days=10 * 365)  # 10 years for percentile

    df = reader.r2.get_timeseries("signals_valuation", ticker, start_date, end_date)

    if df.empty:
        print(f"\n⚠️  SKIPPED - No valuation data available")
        return False

    # Compute valuation signals
    result = ValuationSignals.compute_valuation_signals(df, lookback_years=10)

    if result['success']:
        print(f"\n✓ SUCCESS - Valuation regime detected")
        print(f"  Metric: {result['metric_type']}")
        print(f"  Current multiple: {result['current_multiple']:.2f}x")
        print(f"  Percentile: {result['current_percentile']:.1f}")
        print(f"  Regime: {result['regime'].upper()}")
        print(f"  History range: {result['history_min']:.2f}x - {result['history_max']:.2f}x")
        print(f"  Median: {result['history_median']:.2f}x")
        print(f"  Data points: {result['history_count']}")
        return True
    else:
        print(f"\n✗ FAILED: {result['error']}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backfill UBER data end-to-end")
    parser.add_argument(
        "--start-date",
        type=str,
        default=(date.today() - timedelta(days=5 * 365)).isoformat(),
        help="Start date (YYYY-MM-DD), default: 5 years ago"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=date.today().isoformat(),
        help="End date (YYYY-MM-DD), default: today"
    )
    parser.add_argument(
        "--use-dolt",
        action="store_true",
        help="Use Dolt database instead of EODHD API (saves API requests)"
    )
    parser.add_argument(
        "--dolt-host",
        type=str,
        default="localhost",
        help="Dolt host (default: localhost)"
    )
    parser.add_argument(
        "--stocks-port",
        type=int,
        default=3306,
        help="Dolt stocks DB port (default: 3306)"
    )
    parser.add_argument(
        "--earnings-port",
        type=int,
        default=3307,
        help="Dolt earnings DB port (default: 3307)"
    )

    args = parser.parse_args()

    ticker = "UBER"
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)

    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "UBER DATA BACKFILL" + " " * 29 + "║")
    print("╚" + "=" * 68 + "╝")
    print(f"\nTicker: {ticker}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Duration: {(end_date - start_date).days} days")
    print(f"Data Source: {'Dolt Database' if args.use_dolt else 'EODHD API'}")

    # Check configuration
    print("\n" + "=" * 70)
    print("Checking Configuration")
    print("=" * 70)

    dolt_client = None

    if args.use_dolt:
        # Check Dolt availability
        if not DOLT_AVAILABLE:
            print("✗ mysql-connector-python not installed")
            print("  Install with: pip install mysql-connector-python")
            return 1

        # Connect to Dolt
        dolt_client = DoltClient(
            host=args.dolt_host,
            stocks_port=args.stocks_port,
            earnings_port=args.earnings_port
        )
        if not dolt_client.connect():
            print("\n✗ Failed to connect to Dolt databases")
            print("\nTo start Dolt services:")
            print("  docker-compose up -d dolt-stocks dolt-earnings")
            print("  OR see docs/quick-start-uber-backfill.md")
            return 1
        print("✓ Dolt client configured")
    else:
        # Check EODHD
        try:
            from src.ingest.eodhd_client import EODHDClient
            client = EODHDClient()
            print("✓ EODHD API client configured")
        except Exception as e:
            print(f"✗ EODHD configuration error: {e}")
            print("\nRequired: Set EODHD_API_KEY environment variable")
            print("OR use --use-dolt flag to use local Dolt database")
            return 1

    try:
        from src.storage.r2_client import R2Client
        r2 = R2Client()
        print("✓ R2 storage client configured")
    except Exception as e:
        print(f"✗ R2 configuration error: {e}")
        print("\nRequired: Set R2 credentials (AWS_ACCESS_KEY_ID, etc.)")
        return 1

    # Run pipeline
    if args.use_dolt:
        steps = [
            ("Ingest Prices", lambda: step_1_ingest_prices_from_dolt(ticker, start_date, end_date, dolt_client)),
            ("Ingest Fundamentals", lambda: step_1_5_ingest_fundamentals_from_dolt(ticker, start_date, end_date, dolt_client)),
            ("Verify Prices", lambda: step_2_verify_prices(ticker)),
            ("Compute Technical", lambda: step_3_compute_technical_signals(ticker)),
            ("Verify Technical", lambda: step_4_verify_technical_signals(ticker)),
            ("Check Fundamentals", lambda: step_5_check_fundamentals(ticker)),
            ("Compute Valuation", lambda: step_6_compute_valuation_signals(ticker)),
            ("Test Valuation Regime", lambda: step_7_test_valuation_regime(ticker)),
        ]
    else:
        steps = [
            ("Ingest Prices", lambda: step_1_ingest_prices(ticker, start_date, end_date)),
            ("Verify Prices", lambda: step_2_verify_prices(ticker)),
            ("Compute Technical", lambda: step_3_compute_technical_signals(ticker)),
            ("Verify Technical", lambda: step_4_verify_technical_signals(ticker)),
            ("Check Fundamentals", lambda: step_5_check_fundamentals(ticker)),
            ("Compute Valuation", lambda: step_6_compute_valuation_signals(ticker)),
            ("Test Valuation Regime", lambda: step_7_test_valuation_regime(ticker)),
        ]

    results = []
    for step_name, step_func in steps:
        try:
            success = step_func()
            results.append((step_name, success))
        except Exception as e:
            print(f"\n✗ ERROR in {step_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((step_name, False))

    # Cleanup
    if dolt_client:
        dolt_client.disconnect()
        print("\n✓ Disconnected from Dolt")

    # Summary
    print("\n" + "=" * 70)
    print("BACKFILL SUMMARY")
    print("=" * 70)

    for step_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status:8} {step_name}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print("\n" + "=" * 70)
    print(f"Completed: {passed}/{total} steps successful")

    if passed >= 4:  # At least prices + technical working
        print("\n✅ UBER data backfill successful!")
        print(f"\nYou can now:")
        print(f"  - View price data: TimeSeriesReader().get_prices('UBER', ...)")
        print(f"  - View signals: TimeSeriesReader().r2.get_timeseries('signals_technical', 'UBER', ...)")
        print(f"  - Run pipeline: SignalPipeline().evaluate_ticker_for_user(...)")
        return 0
    else:
        print("\n⚠️  Backfill incomplete - check errors above")
        return 1


if __name__ == "__main__":
    import pandas as pd  # Import here for step functions
    sys.exit(main())
