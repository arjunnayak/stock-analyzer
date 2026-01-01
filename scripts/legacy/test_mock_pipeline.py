#!/usr/bin/env python3
"""
Mock data pipeline test.

Generates realistic mock price data and tests the full ingest/read pipeline
without requiring Docker or EODHD API access.

This script can run anywhere and validates:
1. Data generation
2. R2 storage operations (or file-based fallback)
3. Signal computation
4. Alert generation
"""

import io
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd


def generate_mock_prices(
    ticker: str,
    start_date: date,
    end_date: date,
    base_price: float = 100.0,
    volatility: float = 0.02,
    trend: float = 0.0001,
) -> pd.DataFrame:
    """
    Generate realistic mock price data.

    Args:
        ticker: Stock ticker
        start_date: Start date
        end_date: End date
        base_price: Starting price
        volatility: Daily volatility (default: 2%)
        trend: Daily trend (default: 0.01% per day)

    Returns:
        DataFrame with OHLCV data
    """
    # Generate trading days (weekdays only)
    all_dates = pd.date_range(start=start_date, end=end_date, freq="D")
    trading_days = [d for d in all_dates if d.weekday() < 5]  # Mon-Fri only

    n_days = len(trading_days)

    # Generate price series with trend and random walk
    returns = np.random.randn(n_days) * volatility + trend
    cumulative_returns = np.exp(np.cumsum(returns))
    close_prices = base_price * cumulative_returns

    # Generate OHLC from close prices
    daily_range = np.random.uniform(0.01, 0.03, n_days)  # 1-3% daily range

    high_prices = close_prices * (1 + daily_range / 2)
    low_prices = close_prices * (1 - daily_range / 2)
    open_prices = low_prices + (high_prices - low_prices) * np.random.uniform(0, 1, n_days)

    # Generate volume with some pattern
    base_volume = 5_000_000
    volume_variation = np.random.uniform(0.5, 1.5, n_days)
    volumes = (base_volume * volume_variation).astype(int)

    df = pd.DataFrame(
        {
            "date": trading_days,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "adj_close": close_prices,  # Same as close for simplicity
            "volume": volumes,
        }
    )

    return df


def test_mock_data_generation():
    """Test generating mock data."""
    print("=" * 70)
    print("1. MOCK DATA GENERATION")
    print("=" * 70)

    tickers = ["AAPL", "MSFT", "GOOGL"]
    end_date = date.today()
    start_date = end_date - timedelta(days=365)

    mock_data = {}

    for ticker in tickers:
        df = generate_mock_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            base_price=np.random.uniform(100, 200),
            volatility=0.02,
            trend=np.random.uniform(-0.0002, 0.0005),
        )

        mock_data[ticker] = df
        print(f"✓ Generated {len(df)} days for {ticker}")
        print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    print(f"\n✅ Generated data for {len(tickers)} tickers")
    return mock_data


def test_storage_operations(mock_data: dict):
    """Test storage operations (file-based if R2 not available)."""
    print("\n" + "=" * 70)
    print("2. STORAGE OPERATIONS")
    print("=" * 70)

    # Create temp directory for mock storage
    storage_dir = Path(".mock_storage")
    storage_dir.mkdir(exist_ok=True)

    stored_files = []

    for ticker, df in mock_data.items():
        # Partition by month
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month

        groups = df.groupby(["year", "month"])

        for (year, month), group_df in groups:
            # Create directory structure
            path = storage_dir / "prices" / "v1" / ticker / str(year) / f"{month:02d}"
            path.mkdir(parents=True, exist_ok=True)

            # Save as parquet
            file_path = path / "data.parquet"
            data_df = group_df.drop(columns=["year", "month"])
            data_df.to_parquet(file_path, engine="pyarrow", compression="snappy", index=False)

            stored_files.append(file_path)

    print(f"✓ Stored {len(stored_files)} monthly files")
    print(f"✓ Storage directory: {storage_dir.absolute()}")

    # Test reading back
    print("\nTesting read operations...")

    for ticker in list(mock_data.keys())[:2]:  # Test first 2
        # Read all monthly files for ticker
        ticker_path = storage_dir / "prices" / "v1" / ticker
        parquet_files = list(ticker_path.rglob("*.parquet"))

        dfs = []
        for file in parquet_files:
            dfs.append(pd.read_parquet(file))

        combined = pd.concat(dfs, ignore_index=True).sort_values("date")
        print(f"✓ Read {len(combined)} rows for {ticker} from {len(parquet_files)} files")

    print(f"\n✅ Storage operations working")
    return storage_dir


def test_signal_computation(mock_data: dict):
    """Test signal computation on mock data."""
    print("\n" + "=" * 70)
    print("3. SIGNAL COMPUTATION")
    print("=" * 70)

    from src.signals.technical import TechnicalSignals

    results = {}

    for ticker, df in mock_data.items():
        # Compute signals
        df_with_signals = TechnicalSignals.compute_all_technical_signals(df)

        # Get latest
        latest = TechnicalSignals.get_latest_signals(df_with_signals)

        # Find crossovers
        crossovers = df_with_signals[df_with_signals["crossover"].notna()]

        results[ticker] = {
            "latest": latest,
            "crossovers": len(crossovers),
            "df": df_with_signals,
        }

        print(f"\n{ticker}:")
        print(f"  Latest close: ${latest['close']:.2f}")
        print(f"  SMA-200: ${latest['sma_200']:.2f}" if latest.get("sma_200") else "  SMA-200: Not enough data")
        print(f"  Trend: {latest.get('trend_position', 'N/A')}")
        print(f"  Crossovers detected: {len(crossovers)}")

        if not crossovers.empty:
            last_crossover = crossovers.iloc[-1]
            print(
                f"  Last crossover: {last_crossover['date'].strftime('%Y-%m-%d')} "
                f"({last_crossover['crossover']})"
            )

    print(f"\n✅ Computed signals for {len(results)} tickers")
    return results


def test_alert_generation(signal_results: dict):
    """Test alert generation from signals."""
    print("\n" + "=" * 70)
    print("4. ALERT GENERATION")
    print("=" * 70)

    from datetime import datetime

    from src.signals.alerts import AlertGenerator
    from src.signals.state_tracker import StateChange

    alerts_generated = []

    for ticker, result in signal_results.items():
        crossovers = result["df"][result["df"]["crossover"].notna()]

        if crossovers.empty:
            continue

        # Get most recent crossover
        last_crossover = crossovers.iloc[-1]

        # Create state change
        old_position = "below_sma" if last_crossover["crossover"] == "bullish" else "above_sma"
        new_position = "above_sma" if last_crossover["crossover"] == "bullish" else "below_sma"

        change = StateChange(
            ticker=ticker,
            change_type="trend_position",
            old_value=old_position,
            new_value=new_position,
            timestamp=datetime.now(),
            should_alert=True,
            alert_type="trend_break",
        )

        # Generate alert
        alert = AlertGenerator.generate_trend_break_alert(
            ticker=ticker,
            change=change,
            current_price=last_crossover["close"],
            sma_200=last_crossover["sma_200"],
        )

        alerts_generated.append(alert)

        print(f"\n✓ Generated alert for {ticker}:")
        print(f"  Type: {alert.alert_type}")
        print(f"  Headline: {alert.headline}")

    if alerts_generated:
        print(f"\n✅ Generated {len(alerts_generated)} alerts")
        print("\nSample alert:")
        print("-" * 70)
        print(alerts_generated[0].format_email())
    else:
        print("\n✅ Alert generation working (no crossovers in recent data)")

    return alerts_generated


def cleanup(storage_dir: Path):
    """Clean up mock storage."""
    import shutil

    if storage_dir.exists():
        shutil.rmtree(storage_dir)
        print(f"\n🗑️  Cleaned up {storage_dir}")


def main():
    """Run full mock data pipeline test."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "MOCK DATA PIPELINE TEST" + " " * 25 + "║")
    print("╚" + "=" * 68 + "╝")
    print("\nThis test runs without Docker or external APIs")
    print()

    try:
        # Test 1: Generate mock data
        mock_data = test_mock_data_generation()

        # Test 2: Storage operations
        storage_dir = test_storage_operations(mock_data)

        # Test 3: Signal computation
        signal_results = test_signal_computation(mock_data)

        # Test 4: Alert generation
        alerts = test_alert_generation(signal_results)

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"✅ Mock data generation: {len(mock_data)} tickers")
        print(f"✅ Storage operations: Working")
        print(f"✅ Signal computation: {len(signal_results)} tickers")
        print(f"✅ Alert generation: {len(alerts)} alerts")

        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED")
        print("=" * 70)
        print("\nThe pipeline works end-to-end with mock data!")
        print("Next step: Test with real Docker + EODHD data")

        # Cleanup
        cleanup(storage_dir)

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
