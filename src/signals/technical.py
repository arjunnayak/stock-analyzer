"""
Technical signal computation for stock analysis.

Computes technical indicators from price data:
- Moving averages (SMA, EMA)
- Trend detection
- Price momentum
"""

from datetime import date, timedelta
from typing import Optional

import pandas as pd


class TechnicalSignals:
    """Compute technical indicators from price data."""

    @staticmethod
    def add_sma(df: pd.DataFrame, periods: list[int] = [20, 50, 200]) -> pd.DataFrame:
        """
        Add Simple Moving Averages to price DataFrame.

        Args:
            df: Price DataFrame with 'close' column
            periods: List of periods to compute (default: 20, 50, 200)

        Returns:
            DataFrame with added SMA columns (sma_20, sma_50, sma_200)
        """
        df = df.copy()

        for period in periods:
            df[f"sma_{period}"] = df["close"].rolling(window=period).mean()

        return df

    @staticmethod
    def add_ema(df: pd.DataFrame, periods: list[int] = [12, 26]) -> pd.DataFrame:
        """
        Add Exponential Moving Averages to price DataFrame.

        Args:
            df: Price DataFrame with 'close' column
            periods: List of periods to compute (default: 12, 26)

        Returns:
            DataFrame with added EMA columns (ema_12, ema_26)
        """
        df = df.copy()

        for period in periods:
            df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()

        return df

    @staticmethod
    def detect_trend_position(df: pd.DataFrame, ma_period: int = 200) -> pd.DataFrame:
        """
        Detect if price is above or below moving average.

        Args:
            df: Price DataFrame with 'close' column and SMA columns
            ma_period: Moving average period to use (default: 200)

        Returns:
            DataFrame with added 'trend_position' column
        """
        df = df.copy()
        ma_col = f"sma_{ma_period}"

        if ma_col not in df.columns:
            df = TechnicalSignals.add_sma(df, [ma_period])

        df["trend_position"] = df.apply(
            lambda row: (
                "above_sma" if pd.notna(row["close"]) and pd.notna(row[ma_col]) and row["close"] > row[ma_col]
                else "below_sma" if pd.notna(row["close"]) and pd.notna(row[ma_col])
                else None
            ),
            axis=1,
        )

        return df

    @staticmethod
    def detect_ma_crossover(df: pd.DataFrame, ma_period: int = 200) -> pd.DataFrame:
        """
        Detect when price crosses moving average.

        Args:
            df: Price DataFrame with 'close' and trend_position columns
            ma_period: Moving average period (default: 200)

        Returns:
            DataFrame with 'crossover' column indicating direction
        """
        df = df.copy()

        if "trend_position" not in df.columns:
            df = TechnicalSignals.detect_trend_position(df, ma_period)

        # Detect changes in trend position
        df["crossover"] = None
        df.loc[
            (df["trend_position"] == "above_sma") & (df["trend_position"].shift(1) == "below_sma"),
            "crossover",
        ] = "bullish"  # Crossed above

        df.loc[
            (df["trend_position"] == "below_sma") & (df["trend_position"].shift(1) == "above_sma"),
            "crossover",
        ] = "bearish"  # Crossed below

        return df

    @staticmethod
    def compute_all_technical_signals(df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all technical signals for a price DataFrame.

        Args:
            df: Price DataFrame with OHLCV data

        Returns:
            DataFrame with all technical signals added
        """
        df = df.copy()

        # Add moving averages
        df = TechnicalSignals.add_sma(df, [20, 50, 200])
        df = TechnicalSignals.add_ema(df, [12, 26])

        # Add trend detection
        df = TechnicalSignals.detect_trend_position(df, ma_period=200)
        df = TechnicalSignals.detect_ma_crossover(df, ma_period=200)

        return df

    @staticmethod
    def get_latest_signals(df: pd.DataFrame) -> dict:
        """
        Get the most recent signal values.

        Args:
            df: Price DataFrame with signals computed

        Returns:
            Dictionary with latest signal values
        """
        if df.empty:
            return {}

        latest = df.iloc[-1]

        return {
            "date": latest["date"].strftime("%Y-%m-%d") if pd.notna(latest["date"]) else None,
            "close": float(latest["close"]) if pd.notna(latest["close"]) else None,
            "sma_20": float(latest.get("sma_20")) if pd.notna(latest.get("sma_20")) else None,
            "sma_50": float(latest.get("sma_50")) if pd.notna(latest.get("sma_50")) else None,
            "sma_200": float(latest.get("sma_200")) if pd.notna(latest.get("sma_200")) else None,
            "trend_position": latest.get("trend_position"),
            "crossover": latest.get("crossover"),
        }


if __name__ == "__main__":
    # Test with sample data
    import numpy as np

    print("Testing Technical Signals")
    print("=" * 60)

    # Create sample price data
    dates = pd.date_range(start="2023-01-01", end="2024-12-25", freq="D")
    prices = 100 + np.cumsum(np.random.randn(len(dates)) * 2)

    df = pd.DataFrame(
        {
            "date": dates,
            "close": prices,
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "volume": np.random.randint(1000000, 10000000, len(dates)),
        }
    )

    # Compute signals
    df_with_signals = TechnicalSignals.compute_all_technical_signals(df)

    print("\nSample data with signals (last 10 rows):")
    print(df_with_signals[["date", "close", "sma_20", "sma_50", "sma_200", "trend_position"]].tail(10))

    # Get latest signals
    latest = TechnicalSignals.get_latest_signals(df_with_signals)
    print("\nLatest signals:")
    for key, value in latest.items():
        print(f"  {key}: {value}")

    # Check for crossovers
    crossovers = df_with_signals[df_with_signals["crossover"].notna()]
    print(f"\nCrossovers detected: {len(crossovers)}")
    if not crossovers.empty:
        print(crossovers[["date", "close", "sma_200", "crossover"]].tail())
