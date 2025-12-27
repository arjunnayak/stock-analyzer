"""
Watchlist Service

Handles watchlist operations:
- Get user's watchlist with computed states
- Add stocks to watchlist
- Remove stocks from watchlist
- Queue stocks for backfill if needed
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Mapping from database states to frontend indicators
VALUATION_STATE_MAP = {
    'cheap': 'down',      # ↓ Good buying opportunity
    'normal': 'neutral',  # → Normal valuation
    'expensive': 'up',    # ↑ Overvalued
    'rich': 'up',         # ↑ Overvalued (alternative naming)
    None: 'neutral'       # No data yet
}

TREND_STATE_MAP = {
    'below_200dma': 'down',   # ↓ Bearish
    'above_200dma': 'up',     # ↑ Bullish
    None: 'neutral'           # No data yet
}


class WatchlistService:
    """Service for watchlist management"""

    def __init__(self, db_client):
        """
        Initialize WatchlistService

        Args:
            db_client: Database client (Supabase client or similar)
        """
        self.db = db_client

    async def get_watchlist(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's watchlist with latest computed states

        Fetches:
        - Stock metadata (ticker, name)
        - Latest valuation regime (from user_entity_settings)
        - Latest trend position (from user_entity_settings)
        - Last alert date (from alert_history)

        Args:
            user_id: User UUID

        Returns:
            dict: {
                'stocks': [
                    {
                        'ticker': 'AAPL',
                        'name': 'Apple Inc.',
                        'valuation_state': 'up' | 'down' | 'neutral',
                        'trend_state': 'up' | 'down' | 'neutral',
                        'last_alert_date': '2025-01-15' or None,
                        'last_evaluated_at': '2025-01-20T06:00:00Z' or None
                    }
                ]
            }
        """
        try:
            # Query watchlist with joined data
            # Note: Using raw SQL for complex join with aggregation
            query = """
                SELECT
                    e.ticker,
                    e.name,
                    e.sector,
                    w.added_at,
                    w.alerts_enabled,
                    ues.last_valuation_regime,
                    ues.last_trend_position,
                    ues.last_evaluated_at,
                    (
                        SELECT MAX(sent_at)
                        FROM alert_history
                        WHERE user_id = w.user_id
                          AND entity_id = w.entity_id
                    ) as last_alert_date
                FROM watchlists w
                JOIN entities e ON w.entity_id = e.id
                LEFT JOIN user_entity_settings ues ON
                    w.user_id = ues.user_id AND w.entity_id = ues.entity_id
                WHERE w.user_id = $1
                ORDER BY w.added_at DESC
            """

            result = await self.db.rpc('exec_sql', {
                'query': query,
                'params': [user_id]
            }).execute()

            stocks = []
            for row in result.data or []:
                stocks.append({
                    'ticker': row['ticker'],
                    'name': row['name'],
                    'sector': row.get('sector'),
                    'valuation_state': self._map_valuation_state(row.get('last_valuation_regime')),
                    'trend_state': self._map_trend_state(row.get('last_trend_position')),
                    'last_alert_date': row.get('last_alert_date'),
                    'last_evaluated_at': row.get('last_evaluated_at'),
                    'added_at': row.get('added_at'),
                    'alerts_enabled': row.get('alerts_enabled', True)
                })

            logger.info(f"Fetched watchlist for user {user_id}: {len(stocks)} stocks")

            return {'stocks': stocks}

        except Exception as e:
            logger.error(f"Error fetching watchlist for user {user_id}: {e}")
            raise

    async def add_stock(self, user_id: str, ticker: str) -> Dict[str, Any]:
        """
        Add stock to user's watchlist

        Steps:
        1. Verify entity exists (or create it)
        2. Add to watchlist table
        3. Initialize user_entity_settings
        4. Queue for backfill if stock doesn't have data

        Args:
            user_id: User UUID
            ticker: Stock ticker symbol (will be uppercased)

        Returns:
            dict: Success status and message

        Raises:
            ValueError: If ticker is invalid or already in watchlist
        """
        try:
            ticker = ticker.upper()

            # 1. Get or create entity
            entity = await self._get_or_create_entity(ticker)
            entity_id = entity['id']

            # 2. Check if already in watchlist
            existing = await self.db.from_('watchlists').select('id').eq(
                'user_id', user_id
            ).eq('entity_id', entity_id).execute()

            if existing.data:
                raise ValueError(f"Stock {ticker} is already in your watchlist")

            # 3. Add to watchlist
            await self.db.from_('watchlists').insert({
                'user_id': user_id,
                'entity_id': entity_id,
                'alerts_enabled': True
            }).execute()

            # 4. Initialize user_entity_settings (will be populated by pipeline)
            await self.db.from_('user_entity_settings').insert({
                'user_id': user_id,
                'entity_id': entity_id
            }).execute()

            # 5. Queue for backfill if entity doesn't have data
            if not entity.get('has_price_data') or not entity.get('has_fundamental_data'):
                await self._queue_for_backfill(ticker, user_id)

            logger.info(f"Added {ticker} to watchlist for user {user_id}")

            return {
                'success': True,
                'message': f'Added {ticker} to your watchlist',
                'ticker': ticker
            }

        except ValueError as e:
            raise
        except Exception as e:
            logger.error(f"Error adding {ticker} to watchlist for user {user_id}: {e}")
            raise

    async def remove_stock(self, user_id: str, ticker: str) -> Dict[str, Any]:
        """
        Remove stock from user's watchlist

        Note: Keeps user_entity_settings for historical tracking

        Args:
            user_id: User UUID
            ticker: Stock ticker symbol

        Returns:
            dict: Success status and message

        Raises:
            ValueError: If stock not in watchlist
        """
        try:
            ticker = ticker.upper()

            # Get entity_id
            entity = await self.db.from_('entities').select('id').eq(
                'ticker', ticker
            ).single().execute()

            if not entity.data:
                raise ValueError(f"Stock {ticker} not found")

            entity_id = entity.data['id']

            # Delete from watchlist
            result = await self.db.from_('watchlists').delete().eq(
                'user_id', user_id
            ).eq('entity_id', entity_id).execute()

            if not result.data:
                raise ValueError(f"Stock {ticker} is not in your watchlist")

            logger.info(f"Removed {ticker} from watchlist for user {user_id}")

            return {
                'success': True,
                'message': f'Removed {ticker} from your watchlist',
                'ticker': ticker
            }

        except ValueError as e:
            raise
        except Exception as e:
            logger.error(f"Error removing {ticker} from watchlist for user {user_id}: {e}")
            raise

    async def _get_or_create_entity(self, ticker: str) -> Dict[str, Any]:
        """
        Get entity by ticker, or create if doesn't exist

        Args:
            ticker: Stock ticker symbol (already uppercased)

        Returns:
            dict: Entity data

        Raises:
            ValueError: If ticker is invalid
        """
        # Try to get existing entity
        result = await self.db.from_('entities').select('*').eq(
            'ticker', ticker
        ).execute()

        if result.data:
            return result.data[0]

        # Create new entity (name will be filled by backfill process)
        new_entity = await self.db.from_('entities').insert({
            'ticker': ticker,
            'name': ticker,  # Placeholder, will be updated by backfill
            'has_price_data': False,
            'has_fundamental_data': False
        }).execute()

        if not new_entity.data:
            raise ValueError(f"Failed to create entity for {ticker}")

        logger.info(f"Created new entity for ticker {ticker}")

        return new_entity.data[0]

    async def _queue_for_backfill(self, ticker: str, user_id: str) -> None:
        """
        Add stock to backfill queue

        Args:
            ticker: Stock ticker symbol
            user_id: User who requested (for priority tracking)
        """
        try:
            # Insert into queue (will auto-increment priority if already exists)
            await self.db.from_('backfill_queue').insert({
                'ticker': ticker,
                'requested_by': user_id,
                'status': 'pending',
                'priority': 0
            }).execute()

            logger.info(f"Queued {ticker} for backfill (requested by {user_id})")

        except Exception as e:
            # Ignore errors (likely duplicate, which is fine)
            logger.debug(f"Could not queue {ticker} for backfill: {e}")

    def _map_valuation_state(self, regime: Optional[str]) -> str:
        """Map database valuation regime to frontend state"""
        return VALUATION_STATE_MAP.get(regime, 'neutral')

    def _map_trend_state(self, position: Optional[str]) -> str:
        """Map database trend position to frontend state"""
        return TREND_STATE_MAP.get(position, 'neutral')
