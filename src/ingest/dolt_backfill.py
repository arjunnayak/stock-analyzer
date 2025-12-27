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
        Fetch fundamental data from DoltHub earnings database

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with quarterly fundamentals
        """
        try:
            # Query DoltHub SQL API
            query = f"""
                SELECT date, revenue, ebitda, net_income, eps, shares_outstanding
                FROM quarterly_financials
                WHERE ticker = '{ticker}'
                ORDER BY date DESC
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
            df['date'] = pd.to_datetime(df['date'])

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
        # Group by year/month and upload each partition
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month

        for (year, month), group in df.groupby(['year', 'month']):
            # Create S3 key
            key = f"fundamentals/v1/{ticker}/{year}/{month:02d}/data.parquet"

            # Convert to parquet
            parquet_data = group.to_parquet(index=False)

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
            update_data['fundamental_data_min_date'] = fundamentals_df['date'].min().isoformat()
            update_data['fundamental_data_max_date'] = fundamentals_df['date'].max().isoformat()

        if update_data:
            update_data['last_data_update'] = datetime.utcnow().isoformat()

            self.db.table('entities').update(
                update_data
            ).eq('ticker', ticker).execute()

            logger.info(f"Updated entity metadata for {ticker}")
