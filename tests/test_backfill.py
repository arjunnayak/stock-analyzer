"""
Tests for backfill functionality.

Tests the fundamentals backfill with balance sheet data
and fundamentals_latest table updates.
"""

import pandas as pd
import pytest
from datetime import date
from unittest.mock import MagicMock, patch


class TestBackfillFundamentals:
    """Test fundamentals backfill with balance sheet data."""

    def create_mock_fundamentals_df(self):
        """Create a mock fundamentals DataFrame with balance sheet data."""
        return pd.DataFrame({
            "period_end": pd.to_datetime([
                "2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31",
                "2023-09-30", "2023-06-30"
            ]),
            "period": ["Q3", "Q2", "Q1", "Q4", "Q3", "Q2"],
            "revenue": [100000, 95000, 90000, 88000, 85000, 82000],
            "operating_income": [25000, 24000, 22000, 21000, 20000, 19000],
            "net_income": [20000, 19000, 17000, 16000, 15000, 14000],
            "depreciation_and_amortization": [5000, 4800, 4600, 4500, 4400, 4300],
            # Balance sheet data
            "cash_and_equivalents": [50000, 48000, 45000, 42000, 40000, 38000],
            "long_term_debt": [30000, 31000, 32000, 33000, 34000, 35000],
            "current_portion_long_term_debt": [5000, 5000, 5000, 5000, 5000, 5000],
            "shares_outstanding": [1000, 1000, 1000, 1000, 1000, 1000],
        })

    def test_ebitda_calculation(self):
        """Test that EBITDA is correctly computed from components."""
        from scripts.backfill_from_dolt import DoltClient

        # Create mock connection
        mock_conn = MagicMock()

        client = DoltClient()
        client.earnings_conn = mock_conn

        df = self.create_mock_fundamentals_df()

        # Simulate EBITDA calculation from get_fundamentals
        if "depreciation_and_amortization" in df.columns and "operating_income" in df.columns:
            df["ebitda"] = (
                df["operating_income"].fillna(0)
                + df["depreciation_and_amortization"].fillna(0)
            )

        # Verify EBITDA is correctly calculated
        assert "ebitda" in df.columns
        # Q3 2024: operating_income=25000 + D&A=5000 = 30000
        assert df.iloc[0]["ebitda"] == 30000
        # Q2 2024: operating_income=24000 + D&A=4800 = 28800
        assert df.iloc[1]["ebitda"] == 28800

    def test_total_debt_calculation(self):
        """Test that total_debt is correctly computed."""
        df = self.create_mock_fundamentals_df()

        # Simulate total_debt calculation
        if "long_term_debt" in df.columns:
            df["total_debt"] = df["long_term_debt"].fillna(0)
            if "current_portion_long_term_debt" in df.columns:
                df["total_debt"] = df["total_debt"] + df["current_portion_long_term_debt"].fillna(0)

        # Verify total_debt is correctly calculated
        assert "total_debt" in df.columns
        # Q3 2024: long_term=30000 + current=5000 = 35000
        assert df.iloc[0]["total_debt"] == 35000

    def test_ttm_calculation(self):
        """Test that TTM values are correctly computed from 4 quarters."""
        df = self.create_mock_fundamentals_df()

        # Add EBITDA column
        df["ebitda"] = df["operating_income"] + df["depreciation_and_amortization"]

        # Sort by period_end desc to get most recent quarters
        df = df.sort_values("period_end", ascending=False)

        # Get the 4 most recent quarters
        recent_4q = df.head(4)

        # Calculate TTM values
        ebitda_ttm = float(recent_4q["ebitda"].sum())
        revenue_ttm = float(recent_4q["revenue"].sum())

        # Expected TTM EBITDA: 30000 + 28800 + 26600 + 25500 = 110900
        assert ebitda_ttm == 110900

        # Expected TTM Revenue: 100000 + 95000 + 90000 + 88000 = 373000
        assert revenue_ttm == 373000

    def test_net_debt_calculation(self):
        """Test that net_debt is correctly computed."""
        df = self.create_mock_fundamentals_df()

        # Add total_debt
        df["total_debt"] = df["long_term_debt"] + df["current_portion_long_term_debt"]

        latest = df.iloc[0]
        total_debt = float(latest["total_debt"])
        cash_and_equivalents = float(latest["cash_and_equivalents"])

        net_debt = total_debt - cash_and_equivalents

        # Q3 2024: total_debt=35000 - cash=50000 = -15000 (net cash position)
        assert net_debt == -15000

    def test_fundamentals_latest_row_structure(self):
        """Test that fundamentals_latest row has correct structure."""
        df = self.create_mock_fundamentals_df()
        df["ebitda"] = df["operating_income"] + df["depreciation_and_amortization"]
        df["total_debt"] = df["long_term_debt"] + df["current_portion_long_term_debt"]

        df = df.sort_values("period_end", ascending=False)
        recent_4q = df.head(4)
        latest = df.iloc[0]

        row = {
            "ticker": "AAPL",
            "asof_date": latest["period_end"].date().isoformat(),
            "ebitda_ttm": float(recent_4q["ebitda"].sum()),
            "revenue_ttm": float(recent_4q["revenue"].sum()),
            "net_debt": float(latest["total_debt"]) - float(latest["cash_and_equivalents"]),
            "shares_outstanding": float(latest["shares_outstanding"]),
            "total_debt": float(latest["total_debt"]),
            "cash_and_equivalents": float(latest["cash_and_equivalents"]),
        }

        # Verify row structure
        assert row["ticker"] == "AAPL"
        assert row["asof_date"] == "2024-09-30"
        assert row["ebitda_ttm"] == 110900
        assert row["revenue_ttm"] == 373000
        assert row["net_debt"] == -15000
        assert row["shares_outstanding"] == 1000
        assert row["total_debt"] == 35000
        assert row["cash_and_equivalents"] == 50000


class TestUpdateFundamentalsLatest:
    """Test the update_fundamentals_latest method."""

    @patch("src.storage.supabase_db.SupabaseDB")
    def test_update_fundamentals_latest_success(self, mock_supabase_class):
        """Test that update_fundamentals_latest correctly computes and upserts."""
        from scripts.backfill_from_dolt import BackfillPipeline, DoltClient
        from src.storage.r2_client import R2Client

        # Create mock objects
        mock_dolt = MagicMock(spec=DoltClient)
        mock_r2 = MagicMock(spec=R2Client)
        mock_supabase = MagicMock()
        mock_supabase_class.return_value = mock_supabase

        pipeline = BackfillPipeline(mock_dolt, mock_r2, dry_run=False)

        # Create test data
        df = pd.DataFrame({
            "period_end": pd.to_datetime([
                "2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31"
            ]),
            "period": ["Q3", "Q2", "Q1", "Q4"],
            "revenue": [100000, 95000, 90000, 88000],
            "operating_income": [25000, 24000, 22000, 21000],
            "depreciation_and_amortization": [5000, 4800, 4600, 4500],
            "ebitda": [30000, 28800, 26600, 25500],
            "cash_and_equivalents": [50000, 48000, 45000, 42000],
            "total_debt": [35000, 36000, 37000, 38000],
            "shares_outstanding": [1000, 1000, 1000, 1000],
        })

        # Call the method
        result = pipeline.update_fundamentals_latest("AAPL", df)

        # Verify it was called
        assert result == True
        mock_supabase.upsert_fundamentals_latest.assert_called_once()

        # Check the row that was upserted
        call_args = mock_supabase.upsert_fundamentals_latest.call_args[0][0]
        row = call_args[0]

        assert row["ticker"] == "AAPL"
        assert row["ebitda_ttm"] == 110900  # Sum of 4 quarters
        assert row["revenue_ttm"] == 373000

    def test_update_fundamentals_latest_not_enough_quarters(self):
        """Test that update returns False when not enough quarters."""
        from scripts.backfill_from_dolt import BackfillPipeline, DoltClient
        from src.storage.r2_client import R2Client

        mock_dolt = MagicMock(spec=DoltClient)
        mock_r2 = MagicMock(spec=R2Client)

        pipeline = BackfillPipeline(mock_dolt, mock_r2, dry_run=False)

        # Only 3 quarters of data
        df = pd.DataFrame({
            "period_end": pd.to_datetime(["2024-09-30", "2024-06-30", "2024-03-31"]),
            "period": ["Q3", "Q2", "Q1"],
            "revenue": [100000, 95000, 90000],
            "ebitda": [30000, 28800, 26600],
        })

        result = pipeline.update_fundamentals_latest("AAPL", df)
        assert result == False

    def test_update_fundamentals_latest_dry_run(self):
        """Test that dry run doesn't actually upsert."""
        from scripts.backfill_from_dolt import BackfillPipeline, DoltClient
        from src.storage.r2_client import R2Client

        mock_dolt = MagicMock(spec=DoltClient)
        mock_r2 = MagicMock(spec=R2Client)

        pipeline = BackfillPipeline(mock_dolt, mock_r2, dry_run=True)

        df = pd.DataFrame({
            "period_end": pd.to_datetime([
                "2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31"
            ]),
            "period": ["Q3", "Q2", "Q1", "Q4"],
            "revenue": [100000, 95000, 90000, 88000],
            "ebitda": [30000, 28800, 26600, 25500],
            "total_debt": [35000, 36000, 37000, 38000],
            "cash_and_equivalents": [50000, 48000, 45000, 42000],
            "shares_outstanding": [1000, 1000, 1000, 1000],
        })

        with patch("src.storage.supabase_db.SupabaseDB") as mock_supabase_class:
            result = pipeline.update_fundamentals_latest("AAPL", df)

            # Should return True but not call upsert
            assert result == True
            mock_supabase_class.return_value.upsert_fundamentals_latest.assert_not_called()


class TestDoltBackfillerFundamentals:
    """Test the DoltHub API backfiller fundamentals fetch."""

    def test_ebitda_computation_from_components(self):
        """Test that EBITDA is computed from operating income + D&A."""
        # Simulate the logic from _fetch_fundamentals_from_dolt
        df = pd.DataFrame({
            "period_end": pd.to_datetime(["2024-09-30"]),
            "operating_income": [25000],
            "depreciation_and_amortization": [5000],
            "net_income": [20000],
            "interest_expense": [1000],
            "income_taxes": [4000],
        })

        # Test method 1: Operating income + D&A
        if "depreciation_and_amortization" in df.columns:
            if "operating_income" in df.columns:
                df["ebitda"] = (
                    df["operating_income"].fillna(0) +
                    df["depreciation_and_amortization"].fillna(0)
                )

        assert df.iloc[0]["ebitda"] == 30000

    def test_ebitda_computation_fallback(self):
        """Test EBITDA fallback: net_income + interest + taxes + D&A."""
        df = pd.DataFrame({
            "period_end": pd.to_datetime(["2024-09-30"]),
            # No operating_income
            "net_income": [20000],
            "interest_expense": [1000],
            "income_taxes": [4000],
            "depreciation_and_amortization": [5000],
        })

        # Test method 2: Net income + interest + taxes + D&A
        if "depreciation_and_amortization" in df.columns:
            if "operating_income" not in df.columns:
                if all(col in df.columns for col in ["net_income", "interest_expense", "income_taxes"]):
                    df["ebitda"] = (
                        df["net_income"].fillna(0) +
                        df["interest_expense"].fillna(0) +
                        df["income_taxes"].fillna(0) +
                        df["depreciation_and_amortization"].fillna(0)
                    )

        # 20000 + 1000 + 4000 + 5000 = 30000
        assert df.iloc[0]["ebitda"] == 30000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
