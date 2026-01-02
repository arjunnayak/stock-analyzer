"""
Hardcoded template definitions for Step 3 evaluation.

Each template:
- Has an id, name, and description
- Defines required feature columns and optional stats columns
- Implements vectorized evaluation over a features DataFrame
- Returns triggered rows with metadata (ticker, strength, reasons)
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class TemplateResult:
    """Result of a single template trigger."""

    ticker: str
    template_id: str
    template_name: str
    trigger_strength: Optional[float] = None
    reasons_json: str = "{}"


class Template(ABC):
    """Base class for all templates."""

    id: str
    name: str
    description: str
    required_features: list[str]
    required_stats: list[str] = []

    @abstractmethod
    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluate the template on a features DataFrame.

        Args:
            df: Features DataFrame with required columns

        Returns:
            DataFrame of triggered rows with columns:
            - ticker
            - template_id
            - template_name
            - trigger_strength
            - reasons_json
        """
        pass

    def check_requirements(self, df: pd.DataFrame) -> bool:
        """Check if required columns are present."""
        missing = [col for col in self.required_features if col not in df.columns]
        if missing:
            print(f"  [{self.id}] Missing required columns: {missing}")
            return False
        return True

    def _build_result_df(
        self,
        triggered_df: pd.DataFrame,
        strength_col: Optional[str] = None,
        reasons_fn=None,
    ) -> pd.DataFrame:
        """Build result DataFrame from triggered rows."""
        if triggered_df.empty:
            return pd.DataFrame(
                columns=["ticker", "template_id", "template_name", "trigger_strength", "reasons_json"]
            )

        results = []
        for _, row in triggered_df.iterrows():
            strength = row[strength_col] if strength_col and strength_col in row else None
            reasons = reasons_fn(row) if reasons_fn else {}

            results.append(
                {
                    "ticker": row["ticker"],
                    "template_id": self.id,
                    "template_name": self.name,
                    "trigger_strength": strength,
                    "reasons_json": json.dumps(reasons),
                }
            )

        return pd.DataFrame(results)


# =============================================================================
# T1: Cross above 200 EMA (trend entry)
# =============================================================================
class CrossAbove200EMA(Template):
    id = "T1"
    name = "Cross above 200 EMA"
    description = "Price crossed above the 200-day EMA (bullish trend entry)"
    required_features = ["close", "ema_200", "prev_close", "prev_ema_200"]

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        # Trigger: prev_close <= prev_ema_200 AND close > ema_200
        mask = (
            (df["prev_close"] <= df["prev_ema_200"])
            & (df["close"] > df["ema_200"])
            & df["prev_close"].notna()
            & df["prev_ema_200"].notna()
        )

        triggered = df[mask].copy()
        triggered["strength"] = (triggered["close"] - triggered["ema_200"]) / triggered["ema_200"]

        def reasons(row):
            return {
                "prev_close": round(row["prev_close"], 2),
                "prev_ema_200": round(row["prev_ema_200"], 2),
                "close": round(row["close"], 2),
                "ema_200": round(row["ema_200"], 2),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T2: Cross below 200 EMA (trend risk)
# =============================================================================
class CrossBelow200EMA(Template):
    id = "T2"
    name = "Cross below 200 EMA"
    description = "Price crossed below the 200-day EMA (bearish trend risk)"
    required_features = ["close", "ema_200", "prev_close", "prev_ema_200"]

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        # Trigger: prev_close >= prev_ema_200 AND close < ema_200
        mask = (
            (df["prev_close"] >= df["prev_ema_200"])
            & (df["close"] < df["ema_200"])
            & df["prev_close"].notna()
            & df["prev_ema_200"].notna()
        )

        triggered = df[mask].copy()
        triggered["strength"] = (triggered["ema_200"] - triggered["close"]) / triggered["ema_200"]

        def reasons(row):
            return {
                "prev_close": round(row["prev_close"], 2),
                "prev_ema_200": round(row["prev_ema_200"], 2),
                "close": round(row["close"], 2),
                "ema_200": round(row["ema_200"], 2),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T3: Pullback in uptrend ("add" heuristic)
# =============================================================================
class PullbackInUptrend(Template):
    id = "T3"
    name = "Pullback in uptrend"
    description = "Price pulled back to support in an uptrend (EMA50 > EMA200, close between them)"
    required_features = ["close", "ema_50", "ema_200"]

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        # Trigger: ema_50 > ema_200 AND close < ema_50 AND close > ema_200
        mask = (
            (df["ema_50"] > df["ema_200"])
            & (df["close"] < df["ema_50"])
            & (df["close"] > df["ema_200"])
            & df["ema_50"].notna()
            & df["ema_200"].notna()
        )

        triggered = df[mask].copy()
        # Strength: how far into the pullback zone (0 = at ema_50, 1 = at ema_200)
        triggered["strength"] = (triggered["ema_50"] - triggered["close"]) / (
            triggered["ema_50"] - triggered["ema_200"]
        )

        def reasons(row):
            return {
                "close": round(row["close"], 2),
                "ema_50": round(row["ema_50"], 2),
                "ema_200": round(row["ema_200"], 2),
                "pullback_depth_pct": round(row["strength"] * 100, 1),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T4: Extended above trend ("trim risk")
# =============================================================================
class ExtendedAboveTrend(Template):
    id = "T4"
    name = "Extended above trend"
    description = "Price is extended 20%+ above 200 EMA (potential trim candidate)"
    required_features = ["close", "ema_200"]

    EXTENSION_THRESHOLD = 0.20  # 20%

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        # Trigger: (close - ema_200) / ema_200 >= 0.20
        df = df.copy()
        df["extension"] = (df["close"] - df["ema_200"]) / df["ema_200"]

        mask = (df["extension"] >= self.EXTENSION_THRESHOLD) & df["ema_200"].notna()

        triggered = df[mask].copy()
        triggered["strength"] = triggered["extension"]

        def reasons(row):
            return {
                "close": round(row["close"], 2),
                "ema_200": round(row["ema_200"], 2),
                "extension_pct": round(row["extension"] * 100, 1),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T5: EV/EBIT cheap absolute + trend filter
# =============================================================================
class CheapAbsoluteWithTrend(Template):
    id = "T5"
    name = "Value + momentum"
    description = "Cheap EV/EBIT (<=12x) with price above 200 EMA"
    required_features = ["ev_ebit", "close", "ema_200"]

    EV_EBIT_THRESHOLD = 12.0  # EV/EBIT typically slightly higher than EV/EBITDA

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        # Trigger: ev_ebit <= 12 AND close > ema_200
        mask = (
            (df["ev_ebit"] <= self.EV_EBIT_THRESHOLD)
            & (df["close"] > df["ema_200"])
            & df["ev_ebit"].notna()
            & df["ema_200"].notna()
        )

        triggered = df[mask].copy()
        # Lower EV/EBIT = stronger signal
        triggered["strength"] = (self.EV_EBIT_THRESHOLD - triggered["ev_ebit"]) / self.EV_EBIT_THRESHOLD

        def reasons(row):
            return {
                "ev_ebit": round(row["ev_ebit"], 1),
                "close": round(row["close"], 2),
                "ema_200": round(row["ema_200"], 2),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T6: EV/EBIT expensive absolute + extension
# =============================================================================
class ExpensiveWithExtension(Template):
    id = "T6"
    name = "Expensive + extended"
    description = "Expensive EV/EBIT (>=30x) and extended 15%+ above 200 EMA"
    required_features = ["ev_ebit", "close", "ema_200"]

    EV_EBIT_THRESHOLD = 30.0  # EV/EBIT typically slightly higher than EV/EBITDA
    EXTENSION_THRESHOLD = 0.15

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        df = df.copy()
        df["extension"] = (df["close"] - df["ema_200"]) / df["ema_200"]

        # Trigger: ev_ebit >= 30 AND extension >= 0.15
        mask = (
            (df["ev_ebit"] >= self.EV_EBIT_THRESHOLD)
            & (df["extension"] >= self.EXTENSION_THRESHOLD)
            & df["ev_ebit"].notna()
            & df["ema_200"].notna()
        )

        triggered = df[mask].copy()
        triggered["strength"] = triggered["extension"]

        def reasons(row):
            return {
                "ev_ebit": round(row["ev_ebit"], 1),
                "close": round(row["close"], 2),
                "ema_200": round(row["ema_200"], 2),
                "extension_pct": round(row["extension"] * 100, 1),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T7: EV/EBIT cheap vs 5-year history (percentile)
# =============================================================================
class CheapVsHistory(Template):
    id = "T7"
    name = "Cheap vs history"
    description = "EV/EBIT is below 20th percentile of its own 5-year history"
    required_features = ["ev_ebit"]
    required_stats = ["ev_ebit_p20"]

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        if "ev_ebit_p20" not in df.columns:
            print(f"  [{self.id}] Missing stats column: ev_ebit_p20")
            return pd.DataFrame()

        # Trigger: ev_ebit <= p20
        mask = (
            (df["ev_ebit"] <= df["ev_ebit_p20"])
            & df["ev_ebit"].notna()
            & df["ev_ebit_p20"].notna()
        )

        triggered = df[mask].copy()
        # Strength: how far below p20
        triggered["strength"] = (triggered["ev_ebit_p20"] - triggered["ev_ebit"]) / triggered["ev_ebit_p20"]

        def reasons(row):
            return {
                "ev_ebit": round(row["ev_ebit"], 1),
                "p20": round(row["ev_ebit_p20"], 1),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T8: EV/EBIT expensive vs 5-year history (percentile)
# =============================================================================
class ExpensiveVsHistory(Template):
    id = "T8"
    name = "Expensive vs history"
    description = "EV/EBIT is above 80th percentile of its own 5-year history"
    required_features = ["ev_ebit"]
    required_stats = ["ev_ebit_p80"]

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        if "ev_ebit_p80" not in df.columns:
            print(f"  [{self.id}] Missing stats column: ev_ebit_p80")
            return pd.DataFrame()

        # Trigger: ev_ebit >= p80
        mask = (
            (df["ev_ebit"] >= df["ev_ebit_p80"])
            & df["ev_ebit"].notna()
            & df["ev_ebit_p80"].notna()
        )

        triggered = df[mask].copy()
        # Strength: how far above p80
        triggered["strength"] = (triggered["ev_ebit"] - triggered["ev_ebit_p80"]) / triggered["ev_ebit_p80"]

        def reasons(row):
            return {
                "ev_ebit": round(row["ev_ebit"], 1),
                "p80": round(row["ev_ebit_p80"], 1),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T9: Value improving (at/below median)
# =============================================================================
class ValueAtMedian(Template):
    id = "T9"
    name = "Fair value"
    description = "EV/EBIT is at or below median of its 5-year history"
    required_features = ["ev_ebit"]
    required_stats = ["ev_ebit_p50"]

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        if "ev_ebit_p50" not in df.columns:
            print(f"  [{self.id}] Missing stats column: ev_ebit_p50")
            return pd.DataFrame()

        # Trigger: ev_ebit <= p50 (simple version without prev comparison)
        mask = (
            (df["ev_ebit"] <= df["ev_ebit_p50"])
            & df["ev_ebit"].notna()
            & df["ev_ebit_p50"].notna()
        )

        triggered = df[mask].copy()
        # Strength: how far below median (negative = above)
        triggered["strength"] = (triggered["ev_ebit_p50"] - triggered["ev_ebit"]) / triggered["ev_ebit_p50"]

        def reasons(row):
            return {
                "ev_ebit": round(row["ev_ebit"], 1),
                "p50_median": round(row["ev_ebit_p50"], 1),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# T10: Trend up + value cheap (combo)
# =============================================================================
class TrendUpValueCheap(Template):
    id = "T10"
    name = "Uptrend + cheap"
    description = "Uptrend (EMA50 > EMA200) with EV/EBIT below 20th percentile"
    required_features = ["ema_50", "ema_200", "ev_ebit"]
    required_stats = ["ev_ebit_p20"]

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.check_requirements(df):
            return pd.DataFrame()

        if "ev_ebit_p20" not in df.columns:
            print(f"  [{self.id}] Missing stats column: ev_ebit_p20")
            return pd.DataFrame()

        # Trigger: ema_50 > ema_200 AND ev_ebit <= p20
        mask = (
            (df["ema_50"] > df["ema_200"])
            & (df["ev_ebit"] <= df["ev_ebit_p20"])
            & df["ema_50"].notna()
            & df["ema_200"].notna()
            & df["ev_ebit"].notna()
            & df["ev_ebit_p20"].notna()
        )

        triggered = df[mask].copy()
        # Strength: trend strength * value discount
        triggered["trend_strength"] = (triggered["ema_50"] - triggered["ema_200"]) / triggered["ema_200"]
        triggered["value_strength"] = (triggered["ev_ebit_p20"] - triggered["ev_ebit"]) / triggered["ev_ebit_p20"]
        triggered["strength"] = triggered["trend_strength"] + triggered["value_strength"]

        def reasons(row):
            return {
                "ema_50": round(row["ema_50"], 2),
                "ema_200": round(row["ema_200"], 2),
                "ev_ebit": round(row["ev_ebit"], 1),
                "p20": round(row["ev_ebit_p20"], 1),
            }

        return self._build_result_df(triggered, "strength", reasons)


# =============================================================================
# Template Registry
# =============================================================================

# All templates in order
ALL_TEMPLATES: list[Template] = [
    CrossAbove200EMA(),
    CrossBelow200EMA(),
    PullbackInUptrend(),
    ExtendedAboveTrend(),
    CheapAbsoluteWithTrend(),
    ExpensiveWithExtension(),
    CheapVsHistory(),
    ExpensiveVsHistory(),
    ValueAtMedian(),
    TrendUpValueCheap(),
]

# Templates that don't require stats (can run without weekly job)
BASIC_TEMPLATES: list[Template] = [
    CrossAbove200EMA(),
    CrossBelow200EMA(),
    PullbackInUptrend(),
    ExtendedAboveTrend(),
    CheapAbsoluteWithTrend(),
    ExpensiveWithExtension(),
]

# Templates that require valuation stats
STATS_TEMPLATES: list[Template] = [
    CheapVsHistory(),
    ExpensiveVsHistory(),
    ValueAtMedian(),
    TrendUpValueCheap(),
]


def get_template_by_id(template_id: str) -> Optional[Template]:
    """Get a template by its ID."""
    for template in ALL_TEMPLATES:
        if template.id == template_id:
            return template
    return None


def evaluate_all_templates(
    features_df: pd.DataFrame,
    templates: Optional[list[Template]] = None,
) -> pd.DataFrame:
    """
    Evaluate all templates on a features DataFrame.

    Args:
        features_df: Features DataFrame with required columns
        templates: List of templates to evaluate (defaults to ALL_TEMPLATES)

    Returns:
        DataFrame of all triggered rows across all templates
    """
    if templates is None:
        templates = ALL_TEMPLATES

    all_results = []

    for template in templates:
        print(f"Evaluating [{template.id}] {template.name}...")
        try:
            results = template.evaluate(features_df)
            if not results.empty:
                print(f"  → {len(results)} triggers")
                all_results.append(results)
            else:
                print(f"  → No triggers")
        except Exception as e:
            print(f"  → Error: {e}")

    if not all_results:
        return pd.DataFrame(
            columns=["ticker", "template_id", "template_name", "trigger_strength", "reasons_json"]
        )

    return pd.concat(all_results, ignore_index=True)


if __name__ == "__main__":
    # Test templates with sample data
    print("Testing Templates")
    print("=" * 60)

    # Create sample features data
    sample_data = pd.DataFrame(
        [
            # T1: Cross above 200 EMA
            {
                "ticker": "AAPL",
                "close": 105,
                "ema_200": 100,
                "ema_50": 102,
                "prev_close": 99,
                "prev_ema_200": 100,
                "prev_ema_50": 101,
                "ev_ebit": 18,
            },
            # T2: Cross below 200 EMA
            {
                "ticker": "MSFT",
                "close": 95,
                "ema_200": 100,
                "ema_50": 98,
                "prev_close": 101,
                "prev_ema_200": 100,
                "prev_ema_50": 99,
                "ev_ebit": 24,
            },
            # T3: Pullback in uptrend
            {
                "ticker": "GOOGL",
                "close": 115,
                "ema_200": 100,
                "ema_50": 120,
                "prev_close": 118,
                "prev_ema_200": 99,
                "prev_ema_50": 119,
                "ev_ebit": 14,
            },
            # T4: Extended above trend
            {
                "ticker": "NVDA",
                "close": 130,
                "ema_200": 100,
                "ema_50": 115,
                "prev_close": 128,
                "prev_ema_200": 99,
                "prev_ema_50": 114,
                "ev_ebit": 35,
            },
            # T5: Cheap absolute with trend
            {
                "ticker": "META",
                "close": 110,
                "ema_200": 100,
                "ema_50": 105,
                "prev_close": 108,
                "prev_ema_200": 99,
                "prev_ema_50": 104,
                "ev_ebit": 10,
            },
            # No triggers
            {
                "ticker": "AMZN",
                "close": 100,
                "ema_200": 100,
                "ema_50": 100,
                "prev_close": 100,
                "prev_ema_200": 100,
                "prev_ema_50": 100,
                "ev_ebit": 18,
            },
        ]
    )

    # Add valuation stats columns for templates that need them
    sample_data["ev_ebit_p20"] = 12
    sample_data["ev_ebit_p50"] = 18
    sample_data["ev_ebit_p80"] = 30

    print("\nSample data:")
    print(sample_data[["ticker", "close", "ema_200", "ema_50", "ev_ebit"]].to_string(index=False))

    print("\n" + "=" * 60)
    print("Evaluating all templates...")
    print("=" * 60)

    results = evaluate_all_templates(sample_data)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    if not results.empty:
        print(results.to_string(index=False))
    else:
        print("No triggers")

    print(f"\nTotal triggers: {len(results)}")
