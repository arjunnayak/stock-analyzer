"""
Tests for the 10 hardcoded templates in Step 3 evaluation.

Tests cover:
- Each template's trigger conditions
- Edge cases (missing data, boundary conditions)
- Trigger strength calculations
- Template registry functions
"""

import json
import pandas as pd
import numpy as np
import pytest

from src.features.templates import (
    ALL_TEMPLATES,
    BASIC_TEMPLATES,
    STATS_TEMPLATES,
    CrossAbove200EMA,
    CrossBelow200EMA,
    PullbackInUptrend,
    ExtendedAboveTrend,
    CheapAbsoluteWithTrend,
    ExpensiveWithExtension,
    CheapVsHistory,
    ExpensiveVsHistory,
    ValueAtMedian,
    TrendUpValueCheap,
    evaluate_all_templates,
    get_template_by_id,
)


class TestT1CrossAbove200EMA:
    """Test T1: Cross above 200 EMA."""

    def test_triggers_on_crossover(self):
        """Test that template triggers when price crosses above EMA."""
        df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "close": [105, 200],
            "ema_200": [100, 195],
            "prev_close": [98, 200],  # AAPL was below, MSFT was above
            "prev_ema_200": [100, 195],
        })

        template = CrossAbove200EMA()
        results = template.evaluate(df)

        # Only AAPL should trigger (was below, now above)
        assert len(results) == 1
        assert results.iloc[0]["ticker"] == "AAPL"
        assert results.iloc[0]["template_id"] == "T1"

    def test_no_trigger_if_already_above(self):
        """Test no trigger if price was already above EMA."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [110],
            "ema_200": [100],
            "prev_close": [105],  # Was already above
            "prev_ema_200": [100],
        })

        template = CrossAbove200EMA()
        results = template.evaluate(df)

        assert len(results) == 0

    def test_strength_calculation(self):
        """Test trigger strength is proportional to crossover distance."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [110],
            "ema_200": [100],
            "prev_close": [99],
            "prev_ema_200": [100],
        })

        template = CrossAbove200EMA()
        results = template.evaluate(df)

        # Strength = (110 - 100) / 100 = 0.10
        assert abs(results.iloc[0]["trigger_strength"] - 0.10) < 0.001


class TestT2CrossBelow200EMA:
    """Test T2: Cross below 200 EMA."""

    def test_triggers_on_crossover_below(self):
        """Test that template triggers when price crosses below EMA."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [95],
            "ema_200": [100],
            "prev_close": [102],  # Was above
            "prev_ema_200": [100],
        })

        template = CrossBelow200EMA()
        results = template.evaluate(df)

        assert len(results) == 1
        assert results.iloc[0]["ticker"] == "AAPL"

    def test_no_trigger_if_already_below(self):
        """Test no trigger if price was already below EMA."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [90],
            "ema_200": [100],
            "prev_close": [95],  # Was already below
            "prev_ema_200": [100],
        })

        template = CrossBelow200EMA()
        results = template.evaluate(df)

        assert len(results) == 0


class TestT3PullbackInUptrend:
    """Test T3: Pullback in uptrend."""

    def test_triggers_on_pullback(self):
        """Test trigger when price pulls back in uptrend zone."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [105],  # Between ema_50 (110) and ema_200 (100)
            "ema_50": [110],
            "ema_200": [100],
        })

        template = PullbackInUptrend()
        results = template.evaluate(df)

        assert len(results) == 1
        assert results.iloc[0]["ticker"] == "AAPL"

    def test_no_trigger_in_downtrend(self):
        """Test no trigger when ema_50 < ema_200."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [105],
            "ema_50": [95],  # Downtrend
            "ema_200": [100],
        })

        template = PullbackInUptrend()
        results = template.evaluate(df)

        assert len(results) == 0

    def test_no_trigger_if_above_ema50(self):
        """Test no trigger if price is above ema_50."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [115],  # Above ema_50
            "ema_50": [110],
            "ema_200": [100],
        })

        template = PullbackInUptrend()
        results = template.evaluate(df)

        assert len(results) == 0

    def test_pullback_depth_strength(self):
        """Test that strength reflects pullback depth."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [105],  # 50% between ema_50 and ema_200
            "ema_50": [110],
            "ema_200": [100],
        })

        template = PullbackInUptrend()
        results = template.evaluate(df)

        # Strength = (110 - 105) / (110 - 100) = 0.5
        assert abs(results.iloc[0]["trigger_strength"] - 0.5) < 0.001


class TestT4ExtendedAboveTrend:
    """Test T4: Extended above trend."""

    def test_triggers_on_extension(self):
        """Test trigger when price is 20%+ above EMA."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [125],  # 25% above ema_200
            "ema_200": [100],
        })

        template = ExtendedAboveTrend()
        results = template.evaluate(df)

        assert len(results) == 1
        # Strength = 0.25
        assert abs(results.iloc[0]["trigger_strength"] - 0.25) < 0.001

    def test_no_trigger_below_threshold(self):
        """Test no trigger when extension < 20%."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [115],  # Only 15% above
            "ema_200": [100],
        })

        template = ExtendedAboveTrend()
        results = template.evaluate(df)

        assert len(results) == 0


class TestT5CheapAbsoluteWithTrend:
    """Test T5: Value + momentum (cheap EV/EBIT with trend)."""

    def test_triggers_on_cheap_with_trend(self):
        """Test trigger when EV/EBIT <= 12 and price > ema_200."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [10.0],
            "close": [110],
            "ema_200": [100],
        })

        template = CheapAbsoluteWithTrend()
        results = template.evaluate(df)

        assert len(results) == 1
        # Strength = (12 - 10) / 12 = 0.167
        assert abs(results.iloc[0]["trigger_strength"] - 0.167) < 0.01

    def test_no_trigger_expensive(self):
        """Test no trigger when EV/EBIT > 12."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [18.0],
            "close": [110],
            "ema_200": [100],
        })

        template = CheapAbsoluteWithTrend()
        results = template.evaluate(df)

        assert len(results) == 0

    def test_no_trigger_below_ema(self):
        """Test no trigger when price below EMA."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [10.0],
            "close": [95],
            "ema_200": [100],
        })

        template = CheapAbsoluteWithTrend()
        results = template.evaluate(df)

        assert len(results) == 0


class TestT6ExpensiveWithExtension:
    """Test T6: Expensive + extended."""

    def test_triggers_on_expensive_extended(self):
        """Test trigger when expensive and extended."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [35.0],  # >= 30
            "close": [120],  # 20% above ema_200 (>= 15%)
            "ema_200": [100],
        })

        template = ExpensiveWithExtension()
        results = template.evaluate(df)

        assert len(results) == 1

    def test_no_trigger_cheap(self):
        """Test no trigger when cheap."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [12.0],  # < 30
            "close": [120],
            "ema_200": [100],
        })

        template = ExpensiveWithExtension()
        results = template.evaluate(df)

        assert len(results) == 0


class TestT7CheapVsHistory:
    """Test T7: Cheap vs history (below p20)."""

    def test_triggers_below_p20(self):
        """Test trigger when EV/EBIT below p20."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [10.0],
            "ev_ebit_p20": [12.0],
        })

        template = CheapVsHistory()
        results = template.evaluate(df)

        assert len(results) == 1
        # Strength = (12 - 10) / 12 = 0.167
        assert abs(results.iloc[0]["trigger_strength"] - 0.167) < 0.01

    def test_no_trigger_above_p20(self):
        """Test no trigger when above p20."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [15.0],
            "ev_ebit_p20": [12.0],
        })

        template = CheapVsHistory()
        results = template.evaluate(df)

        assert len(results) == 0

    def test_missing_stats_column(self):
        """Test graceful handling of missing stats column."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [10.0],
            # Missing ev_ebit_p20
        })

        template = CheapVsHistory()
        results = template.evaluate(df)

        assert len(results) == 0


class TestT8ExpensiveVsHistory:
    """Test T8: Expensive vs history (above p80)."""

    def test_triggers_above_p80(self):
        """Test trigger when EV/EBIT above p80."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [32.0],
            "ev_ebit_p80": [28.0],
        })

        template = ExpensiveVsHistory()
        results = template.evaluate(df)

        assert len(results) == 1


class TestT9ValueAtMedian:
    """Test T9: Fair value (at/below median)."""

    def test_triggers_at_median(self):
        """Test trigger when at median."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [18.0],
            "ev_ebit_p50": [18.0],
        })

        template = ValueAtMedian()
        results = template.evaluate(df)

        assert len(results) == 1

    def test_triggers_below_median(self):
        """Test trigger when below median."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ev_ebit": [14.0],
            "ev_ebit_p50": [18.0],
        })

        template = ValueAtMedian()
        results = template.evaluate(df)

        assert len(results) == 1


class TestT10TrendUpValueCheap:
    """Test T10: Uptrend + cheap combo."""

    def test_triggers_on_combo(self):
        """Test trigger when uptrend and cheap."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ema_50": [110],
            "ema_200": [100],  # Uptrend
            "ev_ebit": [10.0],
            "ev_ebit_p20": [12.0],
        })

        template = TrendUpValueCheap()
        results = template.evaluate(df)

        assert len(results) == 1

    def test_no_trigger_downtrend(self):
        """Test no trigger in downtrend."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "ema_50": [95],
            "ema_200": [100],  # Downtrend
            "ev_ebit": [10.0],
            "ev_ebit_p20": [12.0],
        })

        template = TrendUpValueCheap()
        results = template.evaluate(df)

        assert len(results) == 0


class TestTemplateRegistry:
    """Test template registry functions."""

    def test_all_templates_count(self):
        """Test that we have exactly 10 templates."""
        assert len(ALL_TEMPLATES) == 10

    def test_basic_templates_count(self):
        """Test basic templates (no stats required)."""
        assert len(BASIC_TEMPLATES) == 6

    def test_stats_templates_count(self):
        """Test templates requiring stats."""
        assert len(STATS_TEMPLATES) == 4

    def test_get_template_by_id(self):
        """Test getting template by ID."""
        t1 = get_template_by_id("T1")
        assert t1 is not None
        assert t1.name == "Cross above 200 EMA"

        t5 = get_template_by_id("T5")
        assert t5 is not None
        assert t5.name == "Value + momentum"

        unknown = get_template_by_id("T99")
        assert unknown is None


class TestEvaluateAllTemplates:
    """Test bulk template evaluation."""

    def test_evaluate_basic_templates(self):
        """Test evaluating basic templates."""
        df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "close": [105, 130],
            "ema_200": [100, 100],
            "ema_50": [110, 105],
            "prev_close": [98, 95],
            "prev_ema_200": [100, 100],
            "ev_ebit": [10.0, 35.0],
        })

        results = evaluate_all_templates(df, templates=BASIC_TEMPLATES)

        # Should have multiple triggers across templates
        assert len(results) > 0
        assert "template_id" in results.columns
        assert "ticker" in results.columns

    def test_evaluate_with_missing_columns(self):
        """Test that templates with missing columns return empty."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [105],
            # Missing ema_200, etc.
        })

        results = evaluate_all_templates(df, templates=[CrossAbove200EMA()])

        assert len(results) == 0


class TestTemplateReasons:
    """Test that reasons JSON contains correct data."""

    def test_reasons_json_format(self):
        """Test that reasons_json is valid JSON."""
        df = pd.DataFrame({
            "ticker": ["AAPL"],
            "close": [105],
            "ema_200": [100],
            "prev_close": [98],
            "prev_ema_200": [100],
        })

        template = CrossAbove200EMA()
        results = template.evaluate(df)

        reasons = json.loads(results.iloc[0]["reasons_json"])
        assert "prev_close" in reasons
        assert "close" in reasons
        assert "ema_200" in reasons


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
