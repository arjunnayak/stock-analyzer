"""
Alerts Service

Handles alert operations:
- Get user's alert history
- Mark alerts as opened (for tracking)
- Alert statistics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AlertsService:
    """Service for alert management"""

    def __init__(self, db_client):
        """
        Initialize AlertsService

        Args:
            db_client: Database client (Supabase client or similar)
        """
        self.db = db_client

    def get_alerts(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        alert_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get user's alert history

        Args:
            user_id: User UUID
            limit: Maximum number of alerts to return
            offset: Pagination offset
            alert_type: Filter by alert type (optional)

        Returns:
            dict: {
                'alerts': [
                    {
                        'id': 'uuid',
                        'ticker': 'AAPL',
                        'alert_type': 'valuation_regime_change',
                        'headline': 'AAPL entered cheap zone',
                        'what_changed': '...',
                        'why_it_matters': '...',
                        'before_vs_now': '...',
                        'what_didnt_change': '...',
                        'sent_at': '2025-01-15T10:00:00Z',
                        'opened_at': '2025-01-15T11:30:00Z' or None
                    }
                ],
                'total': 42,
                'has_more': True/False
            }
        """
        try:
            # Build query
            query = self.db.from_('alert_history').select(
                'id, alert_type, headline, what_changed, why_it_matters, '
                'before_vs_now, what_didnt_change, sent_at, opened_at, '
                'entities!inner(ticker, name)'
            ).eq('user_id', user_id)

            # Filter by alert_type if provided
            if alert_type:
                query = query.eq('alert_type', alert_type)

            # Order by sent_at descending (newest first)
            query = query.order('sent_at', desc=True)

            # Apply pagination
            query = query.range(offset, offset + limit - 1)

            # Execute query
            result = query.execute()

            # Get total count
            count_result = self.db.from_('alert_history').select(
                'id', count='exact'
            ).eq('user_id', user_id).execute()

            total = count_result.count if count_result.count else 0

            # Format alerts
            alerts = []
            for row in result.data or []:
                alerts.append({
                    'id': row['id'],
                    'ticker': row['entities']['ticker'],
                    'name': row['entities'].get('name'),
                    'alert_type': row['alert_type'],
                    'headline': row['headline'],
                    'what_changed': row.get('what_changed'),
                    'why_it_matters': row.get('why_it_matters'),
                    'before_vs_now': row.get('before_vs_now'),
                    'what_didnt_change': row.get('what_didnt_change'),
                    'sent_at': row['sent_at'],
                    'opened_at': row.get('opened_at')
                })

            logger.info(f"Fetched {len(alerts)} alerts for user {user_id}")

            return {
                'alerts': alerts,
                'total': total,
                'has_more': offset + len(alerts) < total
            }

        except Exception as e:
            logger.error(f"Error fetching alerts for user {user_id}: {e}")
            raise

    def mark_opened(self, alert_id: str) -> Dict[str, Any]:
        """
        Mark alert as opened

        Used for tracking user engagement with alerts

        Args:
            alert_id: Alert UUID

        Returns:
            dict: Success status

        Raises:
            ValueError: If alert not found
        """
        try:
            # Update opened_at timestamp if not already set
            result = self.db.from_('alert_history').update({
                'opened_at': datetime.utcnow().isoformat()
            }).eq('id', alert_id).is_('opened_at', None).execute()

            if not result.data:
                # Either alert not found or already marked as opened
                # Check if alert exists
                check = self.db.from_('alert_history').select(
                    'id, opened_at'
                ).eq('id', alert_id).execute()

                if not check.data:
                    raise ValueError(f"Alert {alert_id} not found")

                # Already opened, that's fine
                logger.debug(f"Alert {alert_id} was already marked as opened")
            else:
                logger.info(f"Marked alert {alert_id} as opened")

            return {
                'success': True,
                'message': 'Alert marked as opened'
            }

        except ValueError as e:
            raise
        except Exception as e:
            logger.error(f"Error marking alert {alert_id} as opened: {e}")
            raise

    def get_alert_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get alert statistics for user

        Useful for dashboard display

        Args:
            user_id: User UUID

        Returns:
            dict: Alert statistics (counts by type, open rate, etc.)
        """
        try:
            # Get counts by alert type
            query = """
                SELECT
                    alert_type,
                    COUNT(*) as count,
                    COUNT(opened_at) as opened_count
                FROM alert_history
                WHERE user_id = $1
                GROUP BY alert_type
            """

            result = self.db.rpc('exec_sql', {
                'query': query,
                'params': [user_id]
            }).execute()

            stats_by_type = {}
            total_alerts = 0
            total_opened = 0

            for row in result.data or []:
                alert_type = row['alert_type']
                count = row['count']
                opened_count = row['opened_count']

                stats_by_type[alert_type] = {
                    'count': count,
                    'opened_count': opened_count,
                    'open_rate': opened_count / count if count > 0 else 0
                }

                total_alerts += count
                total_opened += opened_count

            logger.info(f"Fetched alert stats for user {user_id}")

            return {
                'total_alerts': total_alerts,
                'total_opened': total_opened,
                'overall_open_rate': total_opened / total_alerts if total_alerts > 0 else 0,
                'by_type': stats_by_type
            }

        except Exception as e:
            logger.error(f"Error fetching alert stats for user {user_id}: {e}")
            raise

    def get_recent_alerts_count(
        self,
        user_id: str,
        days: int = 7
    ) -> int:
        """
        Get count of recent alerts

        Args:
            user_id: User UUID
            days: Number of days to look back

        Returns:
            int: Number of alerts in the last N days
        """
        try:
            from datetime import timedelta

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            result = self.db.from_('alert_history').select(
                'id', count='exact'
            ).eq('user_id', user_id).gte(
                'sent_at', cutoff_date.isoformat()
            ).execute()

            count = result.count if result.count else 0

            logger.info(f"User {user_id} has {count} alerts in last {days} days")

            return count

        except Exception as e:
            logger.error(f"Error fetching recent alerts count for user {user_id}: {e}")
            return 0
