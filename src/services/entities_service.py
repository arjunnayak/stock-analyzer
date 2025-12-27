"""
Entities Service

Handles stock/entity operations:
- Search stocks by ticker or name
- Get stock metadata
- Stock availability checking
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class EntitiesService:
    """Service for entity/stock metadata operations"""

    def __init__(self, db_client):
        """
        Initialize EntitiesService

        Args:
            db_client: Database client (Supabase client or similar)
        """
        self.db = db_client

    async def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Search stocks by ticker or company name

        Uses case-insensitive LIKE matching on both ticker and name

        Args:
            query: Search query (ticker symbol or company name)
            limit: Maximum number of results (default 10)

        Returns:
            dict: {
                'results': [
                    {
                        'ticker': 'AAPL',
                        'name': 'Apple Inc.',
                        'sector': 'Technology'
                    }
                ]
            }
        """
        try:
            if not query:
                return {'results': []}

            query = query.upper()

            # Search by ticker (starts with) OR name (contains)
            # Prioritize ticker matches
            results = await self.db.from_('entities').select(
                'ticker, name, sector'
            ).or_(
                f'ticker.ilike.{query}%,name.ilike.%{query}%'
            ).order(
                'ticker'  # Ticker matches appear first
            ).limit(limit).execute()

            stocks = []
            for row in results.data or []:
                stocks.append({
                    'ticker': row['ticker'],
                    'name': row.get('name', row['ticker']),
                    'sector': row.get('sector')
                })

            logger.info(f"Search for '{query}' returned {len(stocks)} results")

            return {'results': stocks}

        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            raise

    async def get_stock(self, ticker: str) -> Dict[str, Any]:
        """
        Get stock details by ticker

        Args:
            ticker: Stock ticker symbol

        Returns:
            dict: Stock metadata including data availability

        Raises:
            ValueError: If stock not found
        """
        try:
            ticker = ticker.upper()

            result = await self.db.from_('entities').select(
                'ticker, name, sector, has_price_data, has_fundamental_data, '
                'price_data_min_date, price_data_max_date, '
                'fundamental_data_min_date, fundamental_data_max_date, '
                'last_data_update'
            ).eq('ticker', ticker).single().execute()

            if not result.data:
                raise ValueError(f"Stock {ticker} not found")

            stock = result.data
            logger.info(f"Fetched stock details for {ticker}")

            return {
                'ticker': stock['ticker'],
                'name': stock.get('name', stock['ticker']),
                'sector': stock.get('sector'),
                'has_price_data': stock.get('has_price_data', False),
                'has_fundamental_data': stock.get('has_fundamental_data', False),
                'price_data_range': {
                    'min_date': stock.get('price_data_min_date'),
                    'max_date': stock.get('price_data_max_date')
                } if stock.get('has_price_data') else None,
                'fundamental_data_range': {
                    'min_date': stock.get('fundamental_data_min_date'),
                    'max_date': stock.get('fundamental_data_max_date')
                } if stock.get('has_fundamental_data') else None,
                'last_data_update': stock.get('last_data_update')
            }

        except ValueError as e:
            raise
        except Exception as e:
            logger.error(f"Error fetching stock {ticker}: {e}")
            raise

    async def get_popular_stocks(self, limit: int = 20) -> Dict[str, Any]:
        """
        Get popular stocks (most watched)

        Useful for onboarding suggestions

        Args:
            limit: Number of stocks to return

        Returns:
            dict: {
                'results': [list of popular stocks]
            }
        """
        try:
            # Query entities that appear most frequently in watchlists
            query = """
                SELECT
                    e.ticker,
                    e.name,
                    e.sector,
                    COUNT(w.id) as watch_count
                FROM entities e
                LEFT JOIN watchlists w ON e.id = w.entity_id
                GROUP BY e.ticker, e.name, e.sector
                ORDER BY watch_count DESC, e.ticker ASC
                LIMIT $1
            """

            result = await self.db.rpc('exec_sql', {
                'query': query,
                'params': [limit]
            }).execute()

            stocks = []
            for row in result.data or []:
                stocks.append({
                    'ticker': row['ticker'],
                    'name': row.get('name', row['ticker']),
                    'sector': row.get('sector'),
                    'watch_count': row.get('watch_count', 0)
                })

            logger.info(f"Fetched {len(stocks)} popular stocks")

            return {'results': stocks}

        except Exception as e:
            logger.error(f"Error fetching popular stocks: {e}")
            raise

    async def check_stock_exists(self, ticker: str) -> bool:
        """
        Check if stock exists in database

        Args:
            ticker: Stock ticker symbol

        Returns:
            bool: True if stock exists
        """
        try:
            ticker = ticker.upper()

            result = await self.db.from_('entities').select(
                'id'
            ).eq('ticker', ticker).execute()

            return bool(result.data)

        except Exception as e:
            logger.error(f"Error checking if stock {ticker} exists: {e}")
            return False
