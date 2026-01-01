"""
DoltHub Backfiller

Fetches historical stock data from DoltHub public datasets and uploads to R2.

Uses:
- post-no-preference/stocks (for price data)
- post-no-preference/earnings (for fundamentals)
"""

import os
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class DoltBackfiller:
    """Backfill historical data from DoltHub"""

    # DoltHub SQL API endpoint
    DOLTHUB_API = "https://www.dolthub.com/api/v1alpha1"

    # Datasets
    STOCKS_DB = "post-no-preference/stocks"
    EARNINGS_DB = "post-no-preference/earnings"

    def __init__(self, db_client, r2_client):
        """
        Initialize DoltBackfiller

        Args:
            db_client: Supabase client
            r2_client: R2/S3 client
        """
        self.db = db_client
        self.r2 = r2_client

    def backfill_ticker(self, ticker: str) -> None:
        """
        Backfill all historical data for a ticker

        Args:
            ticker: Stock ticker symbol

        Raises:
            Exception: If backfill fails
        """
        logger.info(f"Starting backfill for {ticker}")

        # 1. Fetch price data from DoltHub
        prices_df = self._fetch_prices_from_dolt(ticker)

        if prices_df is not None and not prices_df.empty:
            # Upload to R2
            self._upload_prices_to_r2(ticker, prices_df)
            logger.info(f"Uploaded {len(prices_df)} price records for {ticker}")
        else:
            logger.warning(f"No price data found for {ticker}")

        # 2. Fetch fundamental data from DoltHub
        fundamentals_df = self._fetch_fundamentals_from_dolt(ticker)

        if fundamentals_df is not None and not fundamentals_df.empty:
            # Upload to R2
            self._upload_fundamentals_to_r2(ticker, fundamentals_df)
            logger.info(f"Uploaded {len(fundamentals_df)} fundamental records for {ticker}")

            # Update fundamentals_latest table with TTM values
            self._update_fundamentals_latest(ticker, fundamentals_df)
        else:
            logger.warning(f"No fundamental data found for {ticker}")

        # 3. Update entity metadata
        self._update_entity_metadata(ticker, prices_df, fundamentals_df)

        logger.info(f"Completed backfill for {ticker}")

    def _fetch_prices_from_dolt(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Fetch price data from DoltHub stocks database

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, adj_close
        """
        try:
            # Query DoltHub SQL API
            query = f"""
                SELECT date, open, high, low, close, volume, adj_close
                FROM prices
                WHERE ticker = '{ticker}'
                ORDER BY date DESC
                LIMIT 10000
            """

            response = requests.post(
                f"{self.DOLTHUB_API}/{self.STOCKS_DB}",
                json={"query": query}
            )

            if response.status_code != 200:
                logger.error(f"DoltHub API error: {response.text}")
                return None

            data = response.json()
            rows = data.get('rows', [])

            if not rows:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(rows)
            df['date'] = pd.to_datetime(df['date'])

            return df

        except Exception as e:
            logger.error(f"Error fetching prices from DoltHub for {ticker}: {e}")
            return None

    def _fetch_fundamentals_from_dolt(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Fetch fundamental data from DoltHub earnings database.

        Joins income_statement, balance_sheet_assets, balance_sheet_liabilities,
        and balance_sheet_equity to get all fields needed for EV/EBITDA calculation.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with quarterly fundamentals including balance sheet data
        """
        try:
            # Query DoltHub SQL API with proper table joins
            # Note: DoltHub uses 'act_symbol' as the ticker column
            query = f"""
                SELECT
                    inc.date as period_end,
                    inc.period,
                    inc.sales as revenue,
                    inc.gross_profit,
                    inc.income_after_depreciation as operating_income,
                    inc.net_income,
                    inc.diluted_net_eps,
                    inc.average_shares,
                    inc.pretax_income,
                    inc.income_taxes,
                    inc.interest_expense,
                    inc.depreciation_and_amortization,
                    -- Balance sheet assets
                    assets.cash_and_equivalents,
                    -- Balance sheet liabilities
                    liab.long_term_debt,
                    liab.current_portion_long_term_debt,
                    liab.total_liabilities,
                    -- Balance sheet equity
                    equity.shares_outstanding,
                    equity.total_equity
                FROM income_statement inc
                LEFT JOIN balance_sheet_assets assets
                    ON inc.act_symbol = assets.act_symbol
                    AND inc.date = assets.date
                    AND inc.period = assets.period
                LEFT JOIN balance_sheet_liabilities liab
                    ON inc.act_symbol = liab.act_symbol
                    AND inc.date = liab.date
                    AND inc.period = liab.period
                LEFT JOIN balance_sheet_equity equity
                    ON inc.act_symbol = equity.act_symbol
                    AND inc.date = equity.date
                    AND inc.period = equity.period
                WHERE inc.act_symbol = '{ticker}'
                ORDER BY inc.date DESC
                LIMIT 200
            """

            response = requests.post(
                f"{self.DOLTHUB_API}/{self.EARNINGS_DB}",
                json={"query": query}
            )

            if response.status_code != 200:
                logger.error(f"DoltHub API error: {response.text}")
                return None

            data = response.json()
            rows = data.get('rows', [])

            if not rows:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(rows)
            df['period_end'] = pd.to_datetime(df['period_end'])

            # Compute EBITDA from components if not present
            if 'depreciation_and_amortization' in df.columns:
                if 'operating_income' in df.columns:
                    df['ebitda'] = (
                        df['operating_income'].fillna(0) +
                        df['depreciation_and_amortization'].fillna(0)
                    )
                elif all(col in df.columns for col in ['net_income', 'interest_expense', 'income_taxes']):
                    df['ebitda'] = (
                        df['net_income'].fillna(0) +
                        df['interest_expense'].fillna(0) +
                        df['income_taxes'].fillna(0) +
                        df['depreciation_and_amortization'].fillna(0)
                    )

            # Compute total_debt = long_term_debt + current_portion_long_term_debt
            if 'long_term_debt' in df.columns:
                df['total_debt'] = df['long_term_debt'].fillna(0)
                if 'current_portion_long_term_debt' in df.columns:
                    df['total_debt'] = df['total_debt'] + df['current_portion_long_term_debt'].fillna(0)

            return df

        except Exception as e:
            logger.error(f"Error fetching fundamentals from DoltHub for {ticker}: {e}")
            return None

    def _upload_prices_to_r2(self, ticker: str, df: pd.DataFrame) -> None:
        """Upload price data to R2 in monthly partitions"""
        # Group by year/month and upload each partition
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month

        for (year, month), group in df.groupby(['year', 'month']):
            # Create S3 key
            key = f"prices/v1/{ticker}/{year}/{month:02d}/data.parquet"

            # Convert to parquet
            parquet_data = group.to_parquet(index=False)

            # Upload to R2
            self.r2.put_object(
                Bucket=os.getenv('R2_BUCKET_NAME', 'market-data'),
                Key=key,
                Body=parquet_data
            )

            logger.debug(f"Uploaded {key}")

    def _upload_fundamentals_to_r2(self, ticker: str, df: pd.DataFrame) -> None:
        """Upload fundamental data to R2 in monthly partitions"""
        # Determine the date column
        date_col = 'period_end' if 'period_end' in df.columns else 'date'

        # Group by year/month and upload each partition
        df['year'] = df[date_col].dt.year
        df['month'] = df[date_col].dt.month

        for (year, month), group in df.groupby(['year', 'month']):
            # Create S3 key
            key = f"fundamentals/v1/{ticker}/{year}/{month:02d}/data.parquet"

            # Remove temporary columns before upload
            upload_df = group.drop(columns=['year', 'month'], errors='ignore')

            # Convert to parquet
            parquet_data = upload_df.to_parquet(index=False)

            # Upload to R2
            self.r2.put_object(
                Bucket=os.getenv('R2_BUCKET_NAME', 'market-data'),
                Key=key,
                Body=parquet_data
            )

            logger.debug(f"Uploaded {key}")

    def _update_entity_metadata(
        self,
        ticker: str,
        prices_df: Optional[pd.DataFrame],
        fundamentals_df: Optional[pd.DataFrame]
    ) -> None:
        """Update entity metadata after successful backfill"""
        update_data = {}

        if prices_df is not None and not prices_df.empty:
            update_data['has_price_data'] = True
            update_data['price_data_min_date'] = prices_df['date'].min().isoformat()
            update_data['price_data_max_date'] = prices_df['date'].max().isoformat()

        if fundamentals_df is not None and not fundamentals_df.empty:
            update_data['has_fundamental_data'] = True
            # Handle both 'date' and 'period_end' column names
            date_col = 'period_end' if 'period_end' in fundamentals_df.columns else 'date'
            update_data['fundamental_data_min_date'] = fundamentals_df[date_col].min().isoformat()
            update_data['fundamental_data_max_date'] = fundamentals_df[date_col].max().isoformat()

        if update_data:
            update_data['last_data_update'] = datetime.utcnow().isoformat()

            self.db.table('entities').update(
                update_data
            ).eq('ticker', ticker).execute()

            logger.info(f"Updated entity metadata for {ticker}")

    def _update_fundamentals_latest(
        self,
        ticker: str,
        fundamentals_df: pd.DataFrame
    ) -> None:
        """
        Compute TTM values and update fundamentals_latest table.

        Args:
            ticker: Stock ticker
            fundamentals_df: DataFrame with quarterly fundamentals
        """
        if fundamentals_df.empty:
            return

        # Filter to quarterly data only (exclude annual "Year" rows)
        df = fundamentals_df.copy()
        if 'period' in df.columns:
            df = df[df['period'].str.contains('Quarter', case=False, na=False)]
            if df.empty:
                logger.warning(f"No quarterly data found after filtering for {ticker}")
                return

        # Determine date column
        date_col = 'period_end' if 'period_end' in df.columns else 'date'

        # Sort by date desc to get most recent quarters
        df = df.sort_values(date_col, ascending=False)

        # Get the 4 most recent quarters for TTM calculation
        recent_4q = df.head(4)

        if len(recent_4q) < 4:
            logger.warning(f"Not enough quarters for TTM calculation for {ticker}")
            return

        # Compute TTM values (sum of last 4 quarters)
        ebitda_ttm = None
        if 'ebitda' in df.columns:
            ebitda_ttm = float(recent_4q['ebitda'].sum())
        elif 'depreciation_and_amortization' in df.columns and 'operating_income' in df.columns:
            ebitda_4q = (
                recent_4q['operating_income'].fillna(0) +
                recent_4q['depreciation_and_amortization'].fillna(0)
            )
            ebitda_ttm = float(ebitda_4q.sum())

        revenue_ttm = None
        if 'revenue' in df.columns:
            revenue_ttm = float(recent_4q['revenue'].fillna(0).sum())

        # Get latest balance sheet values (most recent quarter only)
        latest = df.iloc[0]

        total_debt = None
        if 'total_debt' in df.columns:
            total_debt = float(latest['total_debt']) if pd.notna(latest.get('total_debt')) else None
        elif 'long_term_debt' in df.columns:
            total_debt = float(latest['long_term_debt']) if pd.notna(latest.get('long_term_debt')) else 0
            if 'current_portion_long_term_debt' in df.columns and pd.notna(
                latest.get('current_portion_long_term_debt')
            ):
                total_debt += float(latest['current_portion_long_term_debt'])

        cash_and_equivalents = None
        if 'cash_and_equivalents' in df.columns and pd.notna(latest.get('cash_and_equivalents')):
            cash_and_equivalents = float(latest['cash_and_equivalents'])

        shares_outstanding = None
        if 'shares_outstanding' in df.columns and pd.notna(latest.get('shares_outstanding')):
            shares_outstanding = float(latest['shares_outstanding'])
        elif 'average_shares' in df.columns and pd.notna(latest.get('average_shares')):
            shares_outstanding = float(latest['average_shares'])

        # Compute net_debt
        net_debt = None
        if total_debt is not None:
            net_debt = total_debt - (cash_and_equivalents or 0)

        # Build row for upsert
        asof_date = latest[date_col]
        if hasattr(asof_date, 'date'):
            asof_date = asof_date.date()

        row = {
            'ticker': ticker,
            'asof_date': asof_date.isoformat() if hasattr(asof_date, 'isoformat') else str(asof_date),
            'ebitda_ttm': ebitda_ttm,
            'revenue_ttm': revenue_ttm,
            'net_debt': net_debt,
            'shares_outstanding': shares_outstanding,
            'total_debt': total_debt,
            'cash_and_equivalents': cash_and_equivalents,
        }

        # Upsert to Supabase via fundamentals_latest table
        try:
            from src.storage.supabase_db import SupabaseDB
            db = SupabaseDB()
            db.upsert_fundamentals_latest([row])
            logger.info(f"Updated fundamentals_latest for {ticker}")
        except Exception as e:
            logger.error(f"Failed to update fundamentals_latest for {ticker}: {e}")
