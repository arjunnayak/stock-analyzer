"""
User Service

Handles user-related operations:
- Onboarding
- Settings management
- User preferences
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management operations"""

    def __init__(self, db_client):
        """
        Initialize UserService

        Args:
            db_client: Database client (Supabase client or similar)
        """
        self.db = db_client

    def complete_onboarding(
        self,
        user_id: str,
        investing_style: Optional[str] = None,
        tickers: list[str] = None
    ) -> Dict[str, Any]:
        """
        Complete user onboarding

        1. Update user's investing_style
        2. Add stocks to watchlist (via WatchlistService)

        Args:
            user_id: User UUID
            investing_style: "value", "growth", "blend", or None
            tickers: List of stock tickers to add to watchlist

        Returns:
            dict: Success status and message

        Raises:
            ValueError: If user not found or invalid data
        """
        try:
            # Update user settings
            if investing_style:
                self.update_settings(user_id, {
                    'investing_style': investing_style
                })

            # Add stocks to watchlist
            if tickers:
                from .watchlist_service import WatchlistService
                watchlist_service = WatchlistService(self.db)

                for ticker in tickers:
                    await watchlist_service.add_stock(user_id, ticker.upper())

            logger.info(f"User {user_id} completed onboarding with {len(tickers or [])} stocks")

            return {
                'success': True,
                'message': 'Onboarding completed successfully'
            }

        except Exception as e:
            logger.error(f"Error completing onboarding for user {user_id}: {e}")
            raise

    def get_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get user settings

        Args:
            user_id: User UUID

        Returns:
            dict: User settings (investing_style, alerts_enabled)

        Raises:
            ValueError: If user not found
        """
        try:
            # Query user from database
            result = self.db.from_('users').select(
                'investing_style, alerts_enabled'
            ).eq('id', user_id).single().execute()

            if not result.data:
                raise ValueError(f"User {user_id} not found")

            return {
                'investing_style': result.data.get('investing_style'),
                'alerts_enabled': result.data.get('alerts_enabled', True)
            }

        except Exception as e:
            logger.error(f"Error fetching settings for user {user_id}: {e}")
            raise

    def update_settings(
        self,
        user_id: str,
        settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update user settings

        Args:
            user_id: User UUID
            settings: Dict with keys like 'investing_style', 'alerts_enabled'

        Returns:
            dict: Updated settings

        Raises:
            ValueError: If user not found or invalid settings
        """
        try:
            # Validate settings
            allowed_fields = {'investing_style', 'alerts_enabled'}
            update_data = {k: v for k, v in settings.items() if k in allowed_fields}

            if not update_data:
                raise ValueError("No valid settings provided")

            # Validate investing_style if provided
            if 'investing_style' in update_data:
                style = update_data['investing_style']
                if style not in ['value', 'growth', 'blend', None]:
                    raise ValueError(f"Invalid investing_style: {style}")

            # Update database
            result = self.db.from_('users').update(
                update_data
            ).eq('id', user_id).execute()

            if not result.data:
                raise ValueError(f"User {user_id} not found")

            logger.info(f"Updated settings for user {user_id}: {update_data}")

            return self.get_settings(user_id)

        except Exception as e:
            logger.error(f"Error updating settings for user {user_id}: {e}")
            raise

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID

        Args:
            user_id: User UUID

        Returns:
            dict: User data or None if not found
        """
        try:
            result = self.db.from_('users').select(
                'id, email, investing_style, alerts_enabled, created_at'
            ).eq('id', user_id).single().execute()

            return result.data if result.data else None

        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            return None
