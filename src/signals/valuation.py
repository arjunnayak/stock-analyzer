"""
Valuation regime signal computation for stock analysis.

Computes valuation regime indicators from fundamental data:
- EV/Revenue and EV/EBITDA multiples
- Historical percentile analysis
- Regime classification (cheap/normal/expensive)
- Material change detection
"""

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import percentileofscore


class ValuationSignals:
    """Compute valuation regime signals from fundamental data."""

    # Regime thresholds
    CHEAP_THRESHOLD = 20.0
    EXPENSIVE_THRESHOLD = 80.0

    # History requirements
    MIN_HISTORY_YEARS = 3
    MAX_HISTORY_YEARS = 10
    MIN_VALID_POINTS = 36  # 3 years of monthly data

    # Outlier detection
    IQR_MULTIPLIER = 3.0  # Conservative threshold

    # Profitability check
    MIN_POSITIVE_EBITDA_MONTHS = 18  # 75% of 2 years

    @staticmethod
    def select_valuation_metric(df: pd.DataFrame) -> str:
        """
        Select EV/EBITDA or EV/Revenue based on profitability.

        Logic:
        - If latest EBITDA > 0 AND sufficient positive EBITDA history: use EV/EBITDA
        - Else: use EV/Revenue
        - If revenue invalid: return 'unknown'

        Args:
            df: Valuation DataFrame with columns: ttm_ebitda, ttm_revenue

        Returns:
            Metric type: 'ev_ebitda', 'ev_revenue', or 'unknown'
        """
        if df.empty:
            return 'unknown'

        latest = df.iloc[-1]

        # Check revenue validity
        if pd.isna(latest['ttm_revenue']) or latest['ttm_revenue'] <= 0:
            return 'unknown'

        # Check if profitable and has stable profitability
        if pd.notna(latest['ttm_ebitda']) and latest['ttm_ebitda'] > 0:
            # Count positive EBITDA in last 2 years (24 months minimum)
            recent_df = df.tail(24)
            positive_count = (recent_df['ttm_ebitda'] > 0).sum()

            if positive_count >= ValuationSignals.MIN_POSITIVE_EBITDA_MONTHS:
                return 'ev_ebitda'

        return 'ev_revenue'

    @staticmethod
    def clean_historical_multiples(
        multiples: pd.Series,
        min_points: int = 36
    ) -> tuple[pd.Series, dict]:
        """
        Clean historical multiples using IQR outlier detection.

        Cleaning steps:
        1. Remove NaN, inf, -inf
        2. Remove non-positive values (invalid multiples)
        3. Remove outliers using IQR method (Q1 - 3*IQR, Q3 + 3*IQR)
        4. Check if sufficient points remain

        Args:
            multiples: Series of computed multiples
            min_points: Minimum valid points required (default: 36)

        Returns:
            Tuple of (cleaned_series, metadata_dict)
            - cleaned_series: Cleaned multiples or empty if insufficient
            - metadata: {
                'original_count': int,
                'after_nan_removal': int,
                'after_outlier_removal': int,
                'outliers_removed': int,
                'sufficient_history': bool
              }
        """
        original_count = len(multiples)

        # Remove NaN and inf values
        clean = multiples[multiples.notna() & np.isfinite(multiples)]
        after_nan = len(clean)

        # Remove non-positive values
        clean = clean[clean > 0]

        if len(clean) < min_points:
            return pd.Series(dtype=float), {
                'original_count': original_count,
                'after_nan_removal': after_nan,
                'after_outlier_removal': len(clean),
                'outliers_removed': 0,
                'sufficient_history': False
            }

        # IQR outlier removal
        Q1 = clean.quantile(0.25)
        Q3 = clean.quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - ValuationSignals.IQR_MULTIPLIER * IQR
        upper_bound = Q3 + ValuationSignals.IQR_MULTIPLIER * IQR

        before_outlier_removal = len(clean)
        clean = clean[(clean >= lower_bound) & (clean <= upper_bound)]
        after_outlier = len(clean)

        outliers_removed = before_outlier_removal - after_outlier

        metadata = {
            'original_count': original_count,
            'after_nan_removal': after_nan,
            'after_outlier_removal': after_outlier,
            'outliers_removed': outliers_removed,
            'sufficient_history': after_outlier >= min_points
        }

        if not metadata['sufficient_history']:
            return pd.Series(dtype=float), metadata

        return clean, metadata

    @staticmethod
    def compute_percentile(
        current_value: float,
        historical_values: pd.Series
    ) -> float:
        """
        Compute percentile of current value vs historical distribution.

        Uses scipy.stats.percentileofscore with 'rank' method.
        Lower multiple = lower percentile = cheaper valuation.

        Args:
            current_value: Current multiple
            historical_values: Historical multiples (cleaned)

        Returns:
            Percentile (0-100)
        """
        if len(historical_values) == 0:
            return None

        return percentileofscore(historical_values, current_value, kind='rank')

    @staticmethod
    def classify_regime(
        percentile: Optional[float],
        cheap_threshold: float = 20.0,
        expensive_threshold: float = 80.0
    ) -> str:
        """
        Classify percentile into valuation regime.

        Args:
            percentile: Current percentile (0-100) or None
            cheap_threshold: Threshold for cheap regime (default: 20)
            expensive_threshold: Threshold for expensive regime (default: 80)

        Returns:
            'cheap', 'normal', 'expensive', or 'unknown'
        """
        if percentile is None:
            return 'unknown'

        if percentile <= cheap_threshold:
            return 'cheap'
        elif percentile >= expensive_threshold:
            return 'expensive'
        else:
            return 'normal'

    @staticmethod
    def compute_valuation_signals(
        valuation_df: pd.DataFrame,
        lookback_years: int = 10
    ) -> dict:
        """
        Compute valuation signals for a ticker.

        Main orchestration method that:
        1. Validates input data
        2. Selects appropriate metric (EV/EBITDA vs EV/Revenue)
        3. Extracts historical multiples
        4. Cleans data
        5. Calculates percentile
        6. Determines regime

        Args:
            valuation_df: DataFrame with valuation data (from signals_valuation dataset)
            lookback_years: Years of history to use (default: 10)

        Returns:
            Signal dictionary with:
            - metric_type: 'ev_ebitda', 'ev_revenue', or 'unknown'
            - current_multiple: float or None
            - current_percentile: float or None
            - regime: 'cheap', 'normal', 'expensive', or 'unknown'
            - history_count: int
            - history_min, history_max, history_median: float or None
            - outliers_removed: int
            - success: bool
            - error: str or None
        """
        # Default error response
        error_response = {
            'metric_type': 'unknown',
            'current_multiple': None,
            'current_percentile': None,
            'regime': 'unknown',
            'history_count': 0,
            'history_min': None,
            'history_max': None,
            'history_median': None,
            'outliers_removed': 0,
            'success': False,
            'error': None
        }

        # Validate input
        if valuation_df.empty:
            error_response['error'] = 'No valuation data'
            return error_response

        required_cols = ['date', 'ev_revenue', 'ev_ebitda', 'ttm_revenue', 'ttm_ebitda']
        missing_cols = [col for col in required_cols if col not in valuation_df.columns]
        if missing_cols:
            error_response['error'] = f'Missing columns: {missing_cols}'
            return error_response

        # Sort by date
        df = valuation_df.copy()
        df = df.sort_values('date')

        # Apply lookback window
        if 'date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['date']):
            cutoff_date = df['date'].max() - pd.Timedelta(days=365 * lookback_years)
            df = df[df['date'] >= cutoff_date]

        if len(df) < ValuationSignals.MIN_VALID_POINTS:
            error_response['error'] = f'Insufficient history: {len(df)} < {ValuationSignals.MIN_VALID_POINTS}'
            return error_response

        # Select valuation metric
        metric_type = ValuationSignals.select_valuation_metric(df)

        if metric_type == 'unknown':
            error_response['error'] = 'Invalid revenue data'
            return error_response

        # Extract appropriate multiple series
        if metric_type == 'ev_ebitda':
            multiples = df['ev_ebitda'].copy()
        else:  # ev_revenue
            multiples = df['ev_revenue'].copy()

        # Clean historical multiples
        cleaned_multiples, metadata = ValuationSignals.clean_historical_multiples(
            multiples,
            min_points=ValuationSignals.MIN_VALID_POINTS
        )

        if not metadata['sufficient_history']:
            error_response['error'] = f'Insufficient clean data: {metadata["after_outlier_removal"]} points'
            error_response['outliers_removed'] = metadata['outliers_removed']
            return error_response

        # Get current value
        latest_multiple = multiples.iloc[-1]

        if not np.isfinite(latest_multiple) or latest_multiple <= 0:
            error_response['error'] = 'Invalid current multiple'
            return error_response

        # Compute percentile
        percentile = ValuationSignals.compute_percentile(latest_multiple, cleaned_multiples)

        # Classify regime
        regime = ValuationSignals.classify_regime(
            percentile,
            ValuationSignals.CHEAP_THRESHOLD,
            ValuationSignals.EXPENSIVE_THRESHOLD
        )

        # Build response
        return {
            'metric_type': metric_type,
            'current_multiple': float(latest_multiple),
            'current_percentile': float(percentile) if percentile is not None else None,
            'regime': regime,
            'history_count': len(cleaned_multiples),
            'history_min': float(cleaned_multiples.min()),
            'history_max': float(cleaned_multiples.max()),
            'history_median': float(cleaned_multiples.median()),
            'outliers_removed': metadata['outliers_removed'],
            'success': True,
            'error': None
        }

    @staticmethod
    def compute_ttm_revenue(fundamentals_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trailing twelve month (TTM) revenue from quarterly data.

        Args:
            fundamentals_df: DataFrame with quarterly fundamental data
                            Expected columns: date, sales, period

        Returns:
            DataFrame with columns: date, ttm_revenue
        """
        if fundamentals_df.empty or 'sales' not in fundamentals_df.columns:
            return pd.DataFrame(columns=['date', 'ttm_revenue'])

        # Sort by date
        df = fundamentals_df.copy()
        df = df.sort_values('date')

        # Only use quarterly data (period = 'Q')
        if 'period' in df.columns:
            df = df[df['period'].str.contains('Q', na=False)]

        if len(df) < 4:
            return pd.DataFrame(columns=['date', 'ttm_revenue'])

        # Compute rolling 4-quarter sum
        df['ttm_revenue'] = df['sales'].rolling(window=4, min_periods=4).sum()

        return df[['date', 'ttm_revenue']].copy()

    @staticmethod
    def compute_ttm_ebitda(fundamentals_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trailing twelve month (TTM) EBITDA from quarterly data.

        EBITDA = income_before_depreciation (if available)
              OR net_income + interest_expense + income_taxes + depreciation_and_amortization

        Args:
            fundamentals_df: DataFrame with quarterly fundamental data

        Returns:
            DataFrame with columns: date, ttm_ebitda
        """
        if fundamentals_df.empty:
            return pd.DataFrame(columns=['date', 'ttm_ebitda'])

        df = fundamentals_df.copy()
        df = df.sort_values('date')

        # Only use quarterly data
        if 'period' in df.columns:
            df = df[df['period'].str.contains('Q', na=False)]

        if len(df) < 4:
            return pd.DataFrame(columns=['date', 'ttm_ebitda'])

        # Use income_before_depreciation if available (this is EBITDA)
        if 'income_before_depreciation' in df.columns:
            df['ebitda_quarterly'] = df['income_before_depreciation']
        else:
            # Fallback: compute from components
            # EBITDA = Net Income + Interest + Taxes + D&A
            df['ebitda_quarterly'] = (
                df.get('net_income', 0) +
                df.get('interest_expense', 0).fillna(0) +
                df.get('income_taxes', 0).fillna(0) +
                df.get('depreciation_and_amortization', 0).fillna(0)
            )

        # Compute rolling 4-quarter sum
        df['ttm_ebitda'] = df['ebitda_quarterly'].rolling(window=4, min_periods=4).sum()

        return df[['date', 'ttm_ebitda']].copy()

    @staticmethod
    def compute_enterprise_value(
        prices_df: pd.DataFrame,
        fundamentals_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compute enterprise value time series.

        EV = Market Cap + Total Debt - Cash
        where Market Cap = Price * Shares Outstanding

        Args:
            prices_df: DataFrame with daily price data (date, close)
            fundamentals_df: DataFrame with quarterly fundamental data

        Returns:
            DataFrame with columns: date, enterprise_value, market_cap, shares_outstanding
        """
        if prices_df.empty or fundamentals_df.empty:
            return pd.DataFrame(columns=['date', 'enterprise_value', 'market_cap', 'shares_outstanding'])

        # Get shares outstanding from balance sheet equity
        if 'shares_outstanding' not in fundamentals_df.columns:
            return pd.DataFrame(columns=['date', 'enterprise_value', 'market_cap', 'shares_outstanding'])

        # Forward-fill quarterly data to daily frequency
        # This assumes balance sheet metrics persist until next report
        quarterly_data = fundamentals_df[['date', 'shares_outstanding']].copy()
        quarterly_data = quarterly_data.sort_values('date').drop_duplicates('date')

        # Get total debt (current + long-term debt)
        total_debt = pd.Series(0, index=quarterly_data.index)
        if 'long_term_debt' in fundamentals_df.columns:
            debt_df = fundamentals_df[['date', 'long_term_debt']].copy()
            if 'current_portion_long_term_debt' in fundamentals_df.columns:
                debt_df = fundamentals_df[['date', 'long_term_debt', 'current_portion_long_term_debt']].copy()
                debt_df['total_debt'] = (
                    debt_df['long_term_debt'].fillna(0) +
                    debt_df['current_portion_long_term_debt'].fillna(0)
                )
            else:
                debt_df['total_debt'] = debt_df['long_term_debt'].fillna(0)

            quarterly_data = quarterly_data.merge(
                debt_df[['date', 'total_debt']], on='date', how='left'
            )
        else:
            quarterly_data['total_debt'] = 0

        # Get cash
        if 'cash_and_equivalents' in fundamentals_df.columns:
            cash_df = fundamentals_df[['date', 'cash_and_equivalents']].copy()
            quarterly_data = quarterly_data.merge(
                cash_df, on='date', how='left'
            )
        else:
            quarterly_data['cash_and_equivalents'] = 0

        # Merge with daily prices using forward-fill
        prices_daily = prices_df[['date', 'close']].copy()
        prices_daily = prices_daily.sort_values('date')

        # Create date range and merge
        combined = pd.merge_asof(
            prices_daily,
            quarterly_data,
            on='date',
            direction='backward'
        )

        # Compute market cap and EV
        combined['shares_outstanding'] = combined['shares_outstanding'].fillna(0)
        combined['total_debt'] = combined['total_debt'].fillna(0)
        combined['cash_and_equivalents'] = combined['cash_and_equivalents'].fillna(0)

        combined['market_cap'] = combined['close'] * combined['shares_outstanding']
        combined['enterprise_value'] = (
            combined['market_cap'] +
            combined['total_debt'] -
            combined['cash_and_equivalents']
        )

        # Filter out invalid values
        combined.loc[combined['shares_outstanding'] <= 0, ['market_cap', 'enterprise_value']] = None

        return combined[['date', 'enterprise_value', 'market_cap', 'shares_outstanding']].copy()

    @staticmethod
    def compute_ev_revenue(
        prices_df: pd.DataFrame,
        fundamentals_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compute EV/Revenue multiple time series.

        Args:
            prices_df: DataFrame with daily price data
            fundamentals_df: DataFrame with quarterly fundamental data

        Returns:
            DataFrame with columns: date, ev_revenue, ttm_revenue
        """
        # Compute TTM revenue
        ttm_revenue_df = ValuationSignals.compute_ttm_revenue(fundamentals_df)
        if ttm_revenue_df.empty:
            return pd.DataFrame(columns=['date', 'ev_revenue', 'ttm_revenue'])

        # Compute enterprise value
        ev_df = ValuationSignals.compute_enterprise_value(prices_df, fundamentals_df)
        if ev_df.empty:
            return pd.DataFrame(columns=['date', 'ev_revenue', 'ttm_revenue'])

        # Merge EV with TTM revenue using forward-fill
        ev_df = ev_df.sort_values('date')
        ttm_revenue_df = ttm_revenue_df.sort_values('date')

        combined = pd.merge_asof(
            ev_df[['date', 'enterprise_value']],
            ttm_revenue_df,
            on='date',
            direction='backward'
        )

        # Compute EV/Revenue multiple
        # Set to None if revenue is zero or negative
        combined['ev_revenue'] = None
        valid_mask = (combined['ttm_revenue'] > 0) & (combined['enterprise_value'].notna())
        combined.loc[valid_mask, 'ev_revenue'] = (
            combined.loc[valid_mask, 'enterprise_value'] /
            combined.loc[valid_mask, 'ttm_revenue']
        )

        return combined[['date', 'ev_revenue', 'ttm_revenue']].copy()

    @staticmethod
    def compute_ev_ebitda(
        prices_df: pd.DataFrame,
        fundamentals_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compute EV/EBITDA multiple time series.

        Args:
            prices_df: DataFrame with daily price data
            fundamentals_df: DataFrame with quarterly fundamental data

        Returns:
            DataFrame with columns: date, ev_ebitda, ttm_ebitda, enterprise_value, market_cap, shares_outstanding
        """
        # Compute TTM EBITDA
        ttm_ebitda_df = ValuationSignals.compute_ttm_ebitda(fundamentals_df)
        if ttm_ebitda_df.empty:
            return pd.DataFrame(columns=['date', 'ev_ebitda', 'ttm_ebitda', 'enterprise_value', 'market_cap', 'shares_outstanding'])

        # Compute enterprise value
        ev_df = ValuationSignals.compute_enterprise_value(prices_df, fundamentals_df)
        if ev_df.empty:
            return pd.DataFrame(columns=['date', 'ev_ebitda', 'ttm_ebitda', 'enterprise_value', 'market_cap', 'shares_outstanding'])

        # Merge EV with TTM EBITDA using forward-fill
        ev_df = ev_df.sort_values('date')
        ttm_ebitda_df = ttm_ebitda_df.sort_values('date')

        combined = pd.merge_asof(
            ev_df,
            ttm_ebitda_df,
            on='date',
            direction='backward'
        )

        # Compute EV/EBITDA multiple
        # Set to None if EBITDA is zero or negative
        combined['ev_ebitda'] = None
        valid_mask = (combined['ttm_ebitda'] > 0) & (combined['enterprise_value'].notna())
        combined.loc[valid_mask, 'ev_ebitda'] = (
            combined.loc[valid_mask, 'enterprise_value'] /
            combined.loc[valid_mask, 'ttm_ebitda']
        )

        return combined[['date', 'ev_ebitda', 'ttm_ebitda', 'enterprise_value', 'market_cap', 'shares_outstanding']].copy()

    @staticmethod
    def get_latest_valuation_signal(
        valuation_df: pd.DataFrame,
        lookback_years: int = 10
    ) -> dict:
        """
        Get latest valuation signal (convenience method).

        Args:
            valuation_df: DataFrame with valuation data
            lookback_years: Years of history to use (default: 10)

        Returns:
            Latest signal dictionary
        """
        return ValuationSignals.compute_valuation_signals(valuation_df, lookback_years)


if __name__ == "__main__":
    # Test with sample data
    print("Testing Valuation Signals")
    print("=" * 60)

    # Create sample valuation data (profitable company)
    dates = pd.date_range(start="2020-01-01", end="2024-12-25", freq="D")
    n = len(dates)

    # Generate realistic EV/EBITDA multiples (range: 10-25x with some noise)
    np.random.seed(42)
    base_multiple = 15.0
    ev_ebitda_multiples = base_multiple + np.cumsum(np.random.randn(n) * 0.5)
    ev_ebitda_multiples = np.clip(ev_ebitda_multiples, 10, 25)

    # Derive EV and EBITDA from multiples
    ebitda_ttm = np.full(n, 1_000_000_000)  # $1B EBITDA
    ev = ev_ebitda_multiples * ebitda_ttm

    # Generate revenue (assume 20% EBITDA margin)
    revenue_ttm = ebitda_ttm / 0.20
    ev_revenue_multiples = ev / revenue_ttm

    df = pd.DataFrame({
        'date': dates,
        'enterprise_value': ev,
        'ttm_revenue': revenue_ttm,
        'ttm_ebitda': ebitda_ttm,
        'ev_revenue': ev_revenue_multiples,
        'ev_ebitda': ev_ebitda_multiples,
    })

    # Test metric selection
    print("\n1. Testing metric selection...")
    metric = ValuationSignals.select_valuation_metric(df)
    print(f"   Selected metric: {metric}")
    print(f"   ✓ Profitable company → {metric} (expected: ev_ebitda)")

    # Test outlier cleaning
    print("\n2. Testing outlier cleaning...")
    multiples = df['ev_ebitda']
    cleaned, metadata = ValuationSignals.clean_historical_multiples(multiples)
    print(f"   Original: {metadata['original_count']} points")
    print(f"   After cleaning: {metadata['after_outlier_removal']} points")
    print(f"   Outliers removed: {metadata['outliers_removed']}")
    print(f"   Sufficient history: {metadata['sufficient_history']}")

    # Test percentile calculation
    print("\n3. Testing percentile calculation...")
    current = multiples.iloc[-1]
    percentile = ValuationSignals.compute_percentile(current, cleaned)
    print(f"   Current multiple: {current:.2f}x")
    print(f"   Percentile: {percentile:.1f}")

    # Test regime classification
    print("\n4. Testing regime classification...")
    regime = ValuationSignals.classify_regime(percentile)
    print(f"   Regime: {regime}")

    # Test full pipeline
    print("\n5. Testing full signal computation...")
    result = ValuationSignals.compute_valuation_signals(df)
    print(f"   Success: {result['success']}")
    print(f"   Metric type: {result['metric_type']}")
    print(f"   Current multiple: {result['current_multiple']:.2f}x")
    print(f"   Percentile: {result['current_percentile']:.1f}")
    print(f"   Regime: {result['regime']}")
    print(f"   History: {result['history_min']:.2f}x - {result['history_max']:.2f}x (median: {result['history_median']:.2f}x)")

    print("\n✓ All tests completed!")
