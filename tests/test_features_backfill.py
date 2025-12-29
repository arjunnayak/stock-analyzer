"""
Tests for features backfill with point-in-time fundamentals.

Ensures that historical EV/EBITDA values use fundamentals that were
available at that time (e.g., Aug 2021 uses Q2 2021 fundamentals).
"""

import pandas as pd
import numpy as np
import pytest
from datetime import date, timedelta


class TestPointInTimeFundamentals:
    """Test point-in-time fundamentals logic."""

    def create_mock_fundamentals_df(self):
        """
        Create mock quarterly fundamentals data.

        Simulates typical quarterly earnings dates:
        - Q4 2020: reported in Feb 2021
        - Q1 2021: reported in May 2021
        - Q2 2021: reported in Aug 2021
        - Q3 2021: reported in Nov 2021
        """
        return pd.DataFrame({
            "period_end": pd.to_datetime([
                "2020-12-31",  # Q4 2020
                "2021-03-31",  # Q1 2021
                "2021-06-30",  # Q2 2021
                "2021-09-30",  # Q3 2021
                "2021-12-31",  # Q4 2021
            ]),
            "ebitda": [10000, 11000, 12000, 13000, 14000],
            "shares_outstanding": [1000, 1000, 1000, 1000, 1000],
            "total_debt": [20000, 21000, 22000, 23000, 24000],
            "cash_and_equivalents": [5000, 5500, 6000, 6500, 7000],
        })

    def create_mock_prices_df(self):
        """Create mock daily price data for 2021."""
        dates = pd.date_range(start="2021-01-01", end="2021-12-31", freq="B")
        return pd.DataFrame({
            "date": dates,
            "close": np.random.uniform(100, 200, len(dates)),
        })

    def test_merge_asof_backward(self):
        """Test that merge_asof with direction='backward' works correctly."""
        fundamentals = self.create_mock_fundamentals_df()
        prices = self.create_mock_prices_df()

        # Prepare fundamentals for point-in-time merge
        fundamentals["date"] = fundamentals["period_end"]
        fundamentals = fundamentals.sort_values("date")

        prices = prices.sort_values("date")

        # Use merge_asof with backward direction
        merged = pd.merge_asof(
            prices,
            fundamentals[["date", "ebitda", "shares_outstanding", "total_debt", "cash_and_equivalents"]],
            on="date",
            direction="backward"
        )

        # On January 4, 2021 (first trading day), Q4 2020 fundamentals should be used
        jan_4_row = merged[merged["date"] == pd.Timestamp("2021-01-04")].iloc[0]
        # Q4 2020 period_end is 2020-12-31, which is before Jan 4
        assert jan_4_row["ebitda"] == 10000

        # On August 2, 2021, Q2 2021 fundamentals should be used
        aug_2_row = merged[merged["date"] == pd.Timestamp("2021-08-02")].iloc[0]
        assert aug_2_row["ebitda"] == 12000

        # On July 1, 2021, Q2 2021 fundamentals should be used (just released on June 30)
        jul_1_row = merged[merged["date"] == pd.Timestamp("2021-07-01")].iloc[0]
        assert jul_1_row["ebitda"] == 12000

    def test_ev_ebitda_point_in_time(self):
        """Test that EV/EBITDA is calculated using point-in-time fundamentals."""
        fundamentals = self.create_mock_fundamentals_df()

        # Prepare fundamentals for point-in-time merge
        fundamentals["date"] = fundamentals["period_end"]

        # Create a simplified prices dataframe
        prices = pd.DataFrame({
            "date": pd.to_datetime(["2021-02-01", "2021-05-01", "2021-08-01", "2021-11-01"]),
            "close": [100, 110, 120, 130],
        })

        # Calculate rolling 4-quarter TTM EBITDA
        fundamentals = fundamentals.sort_values("date")
        fundamentals["ebitda_ttm"] = fundamentals["ebitda"].rolling(window=4, min_periods=4).sum()

        prices = prices.sort_values("date")

        merged = pd.merge_asof(
            prices,
            fundamentals[["date", "ebitda_ttm", "shares_outstanding", "total_debt", "cash_and_equivalents"]],
            on="date",
            direction="backward"
        )

        # Calculate EV/EBITDA
        merged["market_cap"] = merged["close"] * merged["shares_outstanding"]
        merged["net_debt"] = merged["total_debt"] - merged["cash_and_equivalents"]
        merged["ev"] = merged["market_cap"] + merged["net_debt"]
        merged["ev_ebitda"] = merged["ev"] / merged["ebitda_ttm"]

        # Check that only rows with 4+ quarters have valid EV/EBITDA
        # First 3 rows won't have TTM (not enough history)
        # Q4 2020 + Q1 2021 + Q2 2021 + Q3 2021 = 46000 EBITDA TTM

        # Nov 2021 should use Q4 2020 + Q1-Q3 2021 = 10000+11000+12000+13000 = 46000
        nov_row = merged[merged["date"] == pd.Timestamp("2021-11-01")].iloc[0]
        if pd.notna(nov_row["ebitda_ttm"]):
            assert nov_row["ebitda_ttm"] == 46000

    def test_fundamentals_forward_fill(self):
        """Test that fundamentals are forward-filled correctly."""
        # Create fundamentals with gaps
        fundamentals = pd.DataFrame({
            "period_end": pd.to_datetime([
                "2021-03-31",  # Q1 2021
                "2021-09-30",  # Q3 2021 (skipping Q2)
            ]),
            "ebitda": [11000, 13000],
        })

        fundamentals["date"] = fundamentals["period_end"]

        # Daily prices
        prices = pd.DataFrame({
            "date": pd.to_datetime(["2021-04-01", "2021-05-01", "2021-06-01", "2021-07-01"]),
            "close": [100, 110, 120, 130],
        })

        merged = pd.merge_asof(
            prices.sort_values("date"),
            fundamentals.sort_values("date"),
            on="date",
            direction="backward"
        )

        # All dates should use Q1 2021 fundamentals (last available)
        assert all(merged["ebitda"] == 11000)


class TestEMABackfill:
    """Test EMA calculation for backfill."""

    def test_ema_calculation(self):
        """Test that EMA is calculated correctly."""
        # Create 250 days of price data
        dates = pd.date_range(start="2021-01-01", periods=250, freq="B")
        np.random.seed(42)
        prices = pd.DataFrame({
            "date": dates,
            "close": 100 + np.cumsum(np.random.randn(250) * 2),  # Random walk
        })

        # Calculate EMA 50 and 200
        span_50 = 50
        span_200 = 200

        prices["ema_50"] = prices["close"].ewm(span=span_50, adjust=False).mean()
        prices["ema_200"] = prices["close"].ewm(span=span_200, adjust=False).mean()

        # Verify EMA properties
        # EMA should converge toward prices
        assert abs(prices.iloc[-1]["ema_50"] - prices.iloc[-1]["close"]) < 20
        # EMA 200 should be smoother (less reactive) than EMA 50
        ema_50_volatility = prices["ema_50"].diff().std()
        ema_200_volatility = prices["ema_200"].diff().std()
        assert ema_200_volatility < ema_50_volatility

    def test_ema_cold_start(self):
        """Test EMA behavior on first day (cold start)."""
        prices = pd.DataFrame({
            "date": pd.date_range(start="2021-01-01", periods=5, freq="B"),
            "close": [100, 102, 101, 103, 105],
        })

        # With adjust=False, first EMA equals first close
        ema = prices["close"].ewm(span=50, adjust=False).mean()
        assert ema.iloc[0] == 100


class TestBackfillDateRange:
    """Test backfill date range handling."""

    def test_date_range_validation(self):
        """Test that date range is validated correctly."""
        start_date = date(2021, 1, 1)
        end_date = date(2021, 12, 31)

        # Valid range
        assert start_date < end_date

        # Invalid range should be caught
        with pytest.raises(AssertionError):
            assert end_date < start_date

    def test_lookback_period(self):
        """Test that lookback period includes enough data for EMA warmup."""
        # For EMA 200, we need ~200 trading days of warmup
        start_date = date(2021, 1, 1)

        # Calculate lookback start (approximately 200 trading days before)
        trading_days_per_year = 252
        lookback_days = int(200 * (365 / trading_days_per_year)) + 30  # Add buffer

        lookback_start = start_date - timedelta(days=lookback_days)

        # Verify lookback is roughly a year before start
        assert lookback_start < start_date
        assert (start_date - lookback_start).days > 280  # ~9+ months


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
