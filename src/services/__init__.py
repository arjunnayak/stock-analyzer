"""
Services package for Material Changes

Business logic layer that can be used by:
- Cloudflare Workers (API endpoints)
- GitHub Actions (batch processing)
- CLI tools

Each service encapsulates domain logic and database operations.
"""

from .user_service import UserService
from .watchlist_service import WatchlistService
from .entities_service import EntitiesService
from .alerts_service import AlertsService

__all__ = [
    'UserService',
    'WatchlistService',
    'EntitiesService',
    'AlertsService',
]
