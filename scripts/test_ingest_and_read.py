#!/usr/bin/env python3
"""
Test script to verify the complete ingest and read pipeline.

This script demonstrates:
1. Connecting to local MinIO (R2)
2. Fetching data from EODHD API
3. Storing data in Parquet format
4. Reading data back from storage

Prerequisites:
- Docker services running (make start)
- Dependencies installed (uv sync)
- EODHD API key configured in .env.local
"""

import sys
from datetime import date, timedelta

from src.config import config
from src.ingest.eodhd_client import EODHDClient
from src.ingest.ingest_prices import PriceIngester
from src.reader import TimeSeriesReader
from src.storage.r2_client import R2Client


def test_config():
    """Test configuration loading."""
    print("=" * 70)
    print("1. TESTING CONFIGURATION")
    print("=" * 70)

    print(f"Environment: {config.env}")
    print(f"Is Local: {config.is_local}")
    print(f"\nR2 Storage:")
    print(f"  Endpoint: {config.r2_endpoint}")
    print(f"  Bucket: {config.r2_bucket}")
    print(f"\nEODHD API:")
    print(f"  API Key: {'✓ configured' if config.eodhd_api_key else '✗ missing'}")

    if not config.eodhd_api_key:
        print("\n❌ ERROR: EODHD API key not configured!")
        return False

    print("\n✅ Configuration OK")
    return True


def test_r2_connection():
    """Test R2/MinIO connection."""
    print("\n" + "=" * 70)
    print("2. TESTING R2/MINIO CONNECTION")
    print("=" * 70)

    try:
        client = R2Client()
        response = client.s3.list_buckets()

        buckets = [b["Name"] for b in response["Buckets"]]
        print(f"✓ Connected to R2/MinIO")
        print(f"  Available buckets: {', '.join(buckets)}")

        if config.r2_bucket not in buckets:
            print(f"\n⚠️  WARNING: Bucket '{config.r2_bucket}' not found!")
            print("  The bucket should be auto-created by docker-compose")
            return False

        print(f"  Using bucket: {config.r2_bucket}")
        print("\n✅ R2 connection OK")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: Failed to connect to R2: {e}")
        print("\nMake sure Docker services are running:")
        print("  make start")
        return False


def test_eodhd_api():
    """Test EODHD API connection."""
    print("\n" + "=" * 70)
    print("3. TESTING EODHD API CONNECTION")
    print("=" * 70)

    try:
        client = EODHDClient()

        # Fetch a small sample
        end_date = date.today()
        start_date = end_date - timedelta(days=5)

        df = client.get_prices("AAPL", start_date=start_date, end_date=end_date)

        if df.empty:
            print("❌ ERROR: No data returned from EODHD")
            return False

        print(f"✓ Fetched {len(df)} price records for AAPL")
        print("\nSample data:")
        print(df.head())
        print("\n✅ EODHD API OK")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: Failed to fetch from EODHD: {e}")
        return False


def test_ingest():
    """Test data ingestion."""
    print("\n" + "=" * 70)
    print("4. TESTING DATA INGESTION")
    print("=" * 70)

    try:
        ingester = PriceIngester()

        # Ingest recent data for a few tickers
        tickers = ["AAPL", "MSFT"]
        end_date = date.today()
        start_date = date(2024, 12, 1)  # Last ~month

        print(f"Ingesting {', '.join(tickers)} from {start_date} to {end_date}")

        summary = ingester.ingest_batch(tickers, start_date, end_date)

        print(f"\nIngestion Summary:")
        print(f"  Total Tickers: {summary['total_tickers']}")
        print(f"  Successful: {summary['successful']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Total Rows: {summary['total_rows']:,}")
        print(f"  Total Files: {summary['total_files']}")

        if summary["failed"] > 0:
            print("\n⚠️  Some ingestions failed")
            return False

        print("\n✅ Data ingestion OK")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_read():
    """Test data reading."""
    print("\n" + "=" * 70)
    print("5. TESTING DATA READING")
    print("=" * 70)

    try:
        reader = TimeSeriesReader()

        # List available tickers
        tickers = reader.list_available_tickers()
        print(f"✓ Found {len(tickers)} tickers in storage: {', '.join(tickers)}")

        if not tickers:
            print("❌ ERROR: No data in storage")
            return False

        # Read data for first ticker
        ticker = tickers[0]
        df = reader.get_latest_prices(ticker, days=30)

        print(f"\n✓ Read {len(df)} rows for {ticker}")
        print("\nSample data:")
        print(df.head())

        # Test multi-ticker read
        if len(tickers) >= 2:
            closes = reader.get_closing_prices(tickers[:2], start_date=date(2024, 12, 1))
            print(f"\n✓ Read closing prices for {len(tickers[:2])} tickers")
            print(f"  Date range: {len(closes)} trading days")

        print("\n✅ Data reading OK")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: Read failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "INGEST & READ PIPELINE TEST" + " " * 26 + "║")
    print("╚" + "=" * 68 + "╝")

    # Run tests in sequence
    tests = [
        ("Configuration", test_config),
        ("R2 Connection", test_r2_connection),
        ("EODHD API", test_eodhd_api),
        ("Data Ingestion", test_ingest),
        ("Data Reading", test_read),
    ]

    results = {}

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ UNEXPECTED ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

        # Stop on first failure
        if not results[name]:
            break

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for name, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"{icon} {name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nYou're ready to build the signal computation pipeline!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nPlease fix the issues above before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
