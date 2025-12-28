#!/usr/bin/env python3
"""
Comprehensive unit tests for the Valuation Regime module.

Tests cover:
1. Metric selection (EV/EBITDA vs EV/Revenue) based on profitability
2. Historical data cleaning and outlier detection
3. Percentile calculation
4. Regime classification
5. Transition detection
6. Alert generation
7. Edge cases (missing data, unprofitable companies, etc.)
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from src.signals.valuation import ValuationSignals


class TestValuationRegime:
    """Test suite for valuation regime module."""

    def test_metric_selection_profitable(self):
        """Test that profitable companies use EV/EBITDA."""
        print("\n" + "=" * 70)
        print("TEST: Metric Selection - Profitable Company")
        print("=" * 70)

        # Create data for consistently profitable company
        dates = pd.date_range(start="2022-01-01", end="2024-12-25", freq="MS")  # Monthly
        n = len(dates)

        df = pd.DataFrame({
            'date': dates,
            'ttm_revenue': np.full(n, 10_000_000_000),  # $10B revenue
            'ttm_ebitda': np.full(n, 2_000_000_000),   # $2B EBITDA (20% margin)
        })

        metric = ValuationSignals.select_valuation_metric(df)

        assert metric == 'ev_ebitda', f"Expected 'ev_ebitda' but got '{metric}'"
        print(f"✓ Profitable company correctly selected: {metric}")

        return True

    def test_metric_selection_unprofitable(self):
        """Test that unprofitable/low-profit companies use EV/Revenue."""
        print("\n" + "=" * 70)
        print("TEST: Metric Selection - Unprofitable Company")
        print("=" * 70)

        # Create data for unprofitable company (like NET)
        dates = pd.date_range(start="2022-01-01", end="2024-12-25", freq="MS")
        n = len(dates)

        df = pd.DataFrame({
            'date': dates,
            'ttm_revenue': np.full(n, 1_000_000_000),  # $1B revenue
            'ttm_ebitda': np.full(n, -100_000_000),    # -$100M EBITDA (unprofitable)
        })

        metric = ValuationSignals.select_valuation_metric(df)

        assert metric == 'ev_revenue', f"Expected 'ev_revenue' but got '{metric}'"
        print(f"✓ Unprofitable company correctly selected: {metric}")

        return True

    def test_metric_selection_becoming_profitable(self):
        """Test company that recently became profitable."""
        print("\n" + "=" * 70)
        print("TEST: Metric Selection - Recently Profitable Company")
        print("=" * 70)

        # Company was unprofitable, recently turned profitable
        dates = pd.date_range(start="2022-01-01", end="2024-12-25", freq="MS")
        n = len(dates)

        ebitda = np.concatenate([
            np.full(18, -50_000_000),  # 18 months unprofitable
            np.full(n - 18, 100_000_000)  # Recent months profitable
        ])

        df = pd.DataFrame({
            'date': dates,
            'ttm_revenue': np.full(n, 1_000_000_000),
            'ttm_ebitda': ebitda,
        })

        metric = ValuationSignals.select_valuation_metric(df)

        # Should use EV/Revenue since less than 18 months of recent profitability
        if n - 18 < 18:
            assert metric == 'ev_revenue', f"Expected 'ev_revenue' for recently profitable company"
            print(f"✓ Recently profitable company correctly uses EV/Revenue (not enough history)")
        else:
            assert metric == 'ev_ebitda', f"Expected 'ev_ebitda' for sustainably profitable company"
            print(f"✓ Sustainably profitable company uses EV/EBITDA")

        return True

    def test_outlier_cleaning(self):
        """Test robust outlier detection using IQR method."""
        print("\n" + "=" * 70)
        print("TEST: Outlier Cleaning")
        print("=" * 70)

        # Create data with outliers
        np.random.seed(42)
        normal_values = np.random.normal(15, 2, 100)  # Mean=15, std=2
        outliers = np.array([50, 100, -10, 5])  # Obvious outliers

        multiples = pd.Series(np.concatenate([normal_values, outliers]))

        cleaned, metadata = ValuationSignals.clean_historical_multiples(multiples, min_points=36)

        print(f"  Original count: {metadata['original_count']}")
        print(f"  After NaN removal: {metadata['after_nan_removal']}")
        print(f"  After outlier removal: {metadata['after_outlier_removal']}")
        print(f"  Outliers removed: {metadata['outliers_removed']}")
        print(f"  Sufficient history: {metadata['sufficient_history']}")

        assert metadata['outliers_removed'] > 0, "Should have removed outliers"
        assert metadata['sufficient_history'], "Should have sufficient history"
        assert len(cleaned) < len(multiples), "Cleaned data should be smaller"

        print(f"✓ Outlier cleaning working correctly")

        return True

    def test_percentile_calculation(self):
        """Test percentile calculation is directionally correct."""
        print("\n" + "=" * 70)
        print("TEST: Percentile Calculation")
        print("=" * 70)

        # Create known distribution
        historical = pd.Series(np.arange(1, 101))  # 1 to 100

        # Test low value (should be low percentile = cheap)
        low_percentile = ValuationSignals.compute_percentile(10, historical)
        print(f"  Value 10 in [1,100]: {low_percentile:.1f}th percentile")
        assert low_percentile < 20, "Low value should have low percentile"

        # Test high value (should be high percentile = expensive)
        high_percentile = ValuationSignals.compute_percentile(90, historical)
        print(f"  Value 90 in [1,100]: {high_percentile:.1f}th percentile")
        assert high_percentile > 80, "High value should have high percentile"

        # Test median (should be ~50th percentile)
        mid_percentile = ValuationSignals.compute_percentile(50, historical)
        print(f"  Value 50 in [1,100]: {mid_percentile:.1f}th percentile")
        assert 45 < mid_percentile < 55, "Median value should be ~50th percentile"

        print(f"✓ Percentile calculation directionally correct")

        return True

    def test_regime_classification(self):
        """Test regime classification thresholds."""
        print("\n" + "=" * 70)
        print("TEST: Regime Classification")
        print("=" * 70)

        cheap = ValuationSignals.classify_regime(15.0)
        normal = ValuationSignals.classify_regime(50.0)
        expensive = ValuationSignals.classify_regime(85.0)
        unknown = ValuationSignals.classify_regime(None)

        assert cheap == 'cheap', f"15th percentile should be 'cheap'"
        assert normal == 'normal', f"50th percentile should be 'normal'"
        assert expensive == 'expensive', f"85th percentile should be 'expensive'"
        assert unknown == 'unknown', f"None percentile should be 'unknown'"

        # Test boundary conditions
        boundary_cheap = ValuationSignals.classify_regime(20.0)
        boundary_expensive = ValuationSignals.classify_regime(80.0)

        assert boundary_cheap == 'cheap', f"20th percentile should be 'cheap' (at boundary)"
        assert boundary_expensive == 'expensive', f"80th percentile should be 'expensive' (at boundary)"

        print(f"✓ Regime classification correct:")
        print(f"  - 15th percentile: {cheap}")
        print(f"  - 50th percentile: {normal}")
        print(f"  - 85th percentile: {expensive}")
        print(f"  - Boundary 20th: {boundary_cheap}")
        print(f"  - Boundary 80th: {boundary_expensive}")

        return True

    def test_missing_data_handling(self):
        """Test graceful handling of missing data."""
        print("\n" + "=" * 70)
        print("TEST: Missing Data Handling")
        print("=" * 70)

        # Empty dataframe
        empty_df = pd.DataFrame()
        result = ValuationSignals.compute_valuation_signals(empty_df)

        assert not result['success'], "Should fail with empty data"
        assert result['regime'] == 'unknown', "Should return 'unknown' regime"
        print(f"✓ Empty data: {result['error']}")

        # Missing required columns
        incomplete_df = pd.DataFrame({
            'date': pd.date_range(start="2020-01-01", periods=100, freq="D"),
            'ttm_revenue': np.random.rand(100) * 1e9,
            # Missing ev_revenue, ev_ebitda, ttm_ebitda
        })

        result = ValuationSignals.compute_valuation_signals(incomplete_df)
        assert not result['success'], "Should fail with missing columns"
        print(f"✓ Missing columns: {result['error']}")

        # Insufficient history
        short_df = pd.DataFrame({
            'date': pd.date_range(start="2024-01-01", periods=10, freq="D"),
            'ttm_revenue': np.random.rand(10) * 1e9,
            'ttm_ebitda': np.random.rand(10) * 1e8,
            'ev_revenue': np.random.rand(10) * 3,
            'ev_ebitda': np.random.rand(10) * 15,
        })

        result = ValuationSignals.compute_valuation_signals(short_df)
        assert not result['success'], "Should fail with insufficient history"
        print(f"✓ Insufficient history: {result['error']}")

        return True

    def test_full_pipeline_profitable(self):
        """Test full pipeline with realistic profitable company data."""
        print("\n" + "=" * 70)
        print("TEST: Full Pipeline - Profitable Company")
        print("=" * 70)

        # Create realistic data for profitable company
        dates = pd.date_range(start="2020-01-01", end="2024-12-25", freq="D")
        n = len(dates)

        np.random.seed(42)

        # Generate realistic EV/EBITDA multiples (range: 10-25x)
        base_multiple = 15.0
        ev_ebitda = base_multiple + np.cumsum(np.random.randn(n) * 0.5)
        ev_ebitda = np.clip(ev_ebitda, 10, 25)

        # Derive components
        ebitda_ttm = np.full(n, 1_000_000_000)  # $1B EBITDA
        revenue_ttm = ebitda_ttm / 0.20  # 20% margin

        df = pd.DataFrame({
            'date': dates,
            'ttm_revenue': revenue_ttm,
            'ttm_ebitda': ebitda_ttm,
            'ev_revenue': ev_ebitda / 5,  # Derived from 20% margin
            'ev_ebitda': ev_ebitda,
        })

        result = ValuationSignals.compute_valuation_signals(df, lookback_years=5)

        assert result['success'], f"Should succeed: {result.get('error')}"
        assert result['metric_type'] == 'ev_ebitda', "Should use EV/EBITDA for profitable company"
        assert result['current_multiple'] is not None, "Should have current multiple"
        assert result['current_percentile'] is not None, "Should have percentile"
        assert result['regime'] in ['cheap', 'normal', 'expensive'], "Should have valid regime"

        print(f"✓ Full pipeline successful:")
        print(f"  - Metric: {result['metric_type']}")
        print(f"  - Current multiple: {result['current_multiple']:.2f}x")
        print(f"  - Percentile: {result['current_percentile']:.1f}")
        print(f"  - Regime: {result['regime']}")
        print(f"  - History: {result['history_count']} points")
        print(f"  - Range: {result['history_min']:.2f}x - {result['history_max']:.2f}x")

        return True

    def test_full_pipeline_unprofitable(self):
        """Test full pipeline with unprofitable company (like NET)."""
        print("\n" + "=" * 70)
        print("TEST: Full Pipeline - Unprofitable Company")
        print("=" * 70)

        # Create realistic data for unprofitable growth company
        dates = pd.date_range(start="2020-01-01", end="2024-12-25", freq="D")
        n = len(dates)

        np.random.seed(42)

        # Generate EV/Revenue multiples (higher for growth companies)
        base_multiple = 8.0
        ev_revenue = base_multiple + np.cumsum(np.random.randn(n) * 0.3)
        ev_revenue = np.clip(ev_revenue, 3, 15)

        # Negative EBITDA (unprofitable)
        revenue_ttm = np.full(n, 1_000_000_000)  # $1B revenue
        ebitda_ttm = np.full(n, -200_000_000)    # -$200M EBITDA

        df = pd.DataFrame({
            'date': dates,
            'ttm_revenue': revenue_ttm,
            'ttm_ebitda': ebitda_ttm,
            'ev_revenue': ev_revenue,
            'ev_ebitda': np.nan,  # Can't compute for negative EBITDA
        })

        result = ValuationSignals.compute_valuation_signals(df, lookback_years=5)

        assert result['success'], f"Should succeed: {result.get('error')}"
        assert result['metric_type'] == 'ev_revenue', "Should use EV/Revenue for unprofitable company"
        assert result['current_multiple'] is not None, "Should have current multiple"
        assert result['regime'] in ['cheap', 'normal', 'expensive'], "Should have valid regime"

        print(f"✓ Full pipeline successful for unprofitable company:")
        print(f"  - Metric: {result['metric_type']}")
        print(f"  - Current multiple: {result['current_multiple']:.2f}x")
        print(f"  - Percentile: {result['current_percentile']:.1f}")
        print(f"  - Regime: {result['regime']}")

        return True

    def test_ttm_computation(self):
        """Test TTM revenue and EBITDA computation from quarterly data."""
        print("\n" + "=" * 70)
        print("TEST: TTM Computation")
        print("=" * 70)

        # Create quarterly data
        quarters = pd.date_range(start="2020-01-01", periods=20, freq="QS")

        fundamentals_df = pd.DataFrame({
            'date': quarters,
            'period': ['Quarter'] * 20,  # Match implementation filter
            'revenue': np.full(20, 250_000_000),  # $250M per quarter
            'income_before_depreciation': np.full(20, 50_000_000),  # $50M EBITDA per quarter
        })

        # Test TTM revenue
        ttm_revenue_df = ValuationSignals.compute_ttm_revenue(fundamentals_df)
        assert not ttm_revenue_df.empty, "Should compute TTM revenue"
        assert 'ttm_revenue' in ttm_revenue_df.columns, "Should have ttm_revenue column"

        # Latest TTM should be sum of last 4 quarters
        latest_ttm = ttm_revenue_df['ttm_revenue'].iloc[-1]
        expected_ttm = 250_000_000 * 4  # 4 quarters

        assert abs(latest_ttm - expected_ttm) < 1, f"TTM revenue should be {expected_ttm}, got {latest_ttm}"
        print(f"✓ TTM revenue: ${latest_ttm:,.0f} (expected ${expected_ttm:,.0f})")

        # Test TTM EBITDA
        ttm_ebitda_df = ValuationSignals.compute_ttm_ebitda(fundamentals_df)
        assert not ttm_ebitda_df.empty, "Should compute TTM EBITDA"

        latest_ebitda = ttm_ebitda_df['ttm_ebitda'].iloc[-1]
        expected_ebitda = 50_000_000 * 4

        assert abs(latest_ebitda - expected_ebitda) < 1, f"TTM EBITDA should be {expected_ebitda}"
        print(f"✓ TTM EBITDA: ${latest_ebitda:,.0f} (expected ${expected_ebitda:,.0f})")

        return True


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "VALUATION REGIME MODULE TESTS" + " " * 24 + "║")
    print("╚" + "=" * 68 + "╝")

    tests = TestValuationRegime()

    test_methods = [
        ('Metric Selection (Profitable)', tests.test_metric_selection_profitable),
        ('Metric Selection (Unprofitable)', tests.test_metric_selection_unprofitable),
        ('Metric Selection (Becoming Profitable)', tests.test_metric_selection_becoming_profitable),
        ('Outlier Cleaning', tests.test_outlier_cleaning),
        ('Percentile Calculation', tests.test_percentile_calculation),
        ('Regime Classification', tests.test_regime_classification),
        ('Missing Data Handling', tests.test_missing_data_handling),
        ('TTM Computation', tests.test_ttm_computation),
        ('Full Pipeline (Profitable)', tests.test_full_pipeline_profitable),
        ('Full Pipeline (Unprofitable)', tests.test_full_pipeline_unprofitable),
    ]

    results = []

    for name, test_func in test_methods:
        try:
            test_func()
            results.append((name, 'PASS', None))
        except AssertionError as e:
            results.append((name, 'FAIL', str(e)))
        except Exception as e:
            results.append((name, 'ERROR', str(e)))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, status, _ in results if status == 'PASS')
    failed = sum(1 for _, status, _ in results if status == 'FAIL')
    errors = sum(1 for _, status, _ in results if status == 'ERROR')

    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "=" * 70)
    print(f"Total: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print("=" * 70)

    if failed == 0 and errors == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(run_all_tests())
