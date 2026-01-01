"""
Cloudflare Worker - Material Changes API

Thin HTTP handlers with direct Supabase queries for watchlist, alerts, and user management.
"""

from workers import Response, WorkerEntrypoint
import json
import os

# Import the lightweight Supabase client for Workers
from supabase_client import get_supabase_client


# CORS headers for frontend
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',  # TODO: Restrict to frontend domain in production
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}


def json_response(data, status=200):
    """Create JSON response with CORS headers"""
    return Response(
        json.dumps(data),
        status=status,
        headers={
            **CORS_HEADERS,
            'Content-Type': 'application/json'
        }
    )


def error_response(message, status=400):
    """Create error response"""
    return json_response({
        'error': {
            'message': message,
            'status': status
        }
    }, status=status)


class Default(WorkerEntrypoint):
    """Main Worker entrypoint for Material Changes API"""

    async def fetch(self, request):
        """
        Main request handler - routes requests to appropriate handlers based on URL path

        Args:
            request: The incoming HTTP request

        Returns:
            Response: HTTP response
        """
        method = request.method

        # Handle CORS preflight
        if method == 'OPTIONS':
            return Response('', status=204, headers=CORS_HEADERS)

        try:
            # Parse URL path (remove query string first)
            url = request.url
            # Split off query string
            url_without_query = url.split('?')[0]
            path = url_without_query.split('/', 3)[-1] if '/' in url_without_query else ''
            parts = path.strip('/').split('/')

            # Initialize async database client
            db = await get_supabase_client(self.env)

            # Route to appropriate handler
            if parts[0] == 'api':
                if len(parts) < 2:
                    return error_response('Invalid API endpoint', 404)

                if parts[1] == 'user':
                    return await self.handle_user(request, parts[2:], db)
                elif parts[1] == 'watchlist':
                    return await self.handle_watchlist(request, parts[2:], db)
                elif parts[1] == 'entities':
                    return await self.handle_entities(request, parts[2:], db)
                elif parts[1] == 'alerts':
                    return await self.handle_alerts(request, parts[2:], db)
                elif parts[1] == 'health':
                    return json_response({'status': 'ok', 'service': 'material-changes-api'})

            # 404 Not Found
            return error_response('Endpoint not found', 404)

        except ValueError as e:
            return error_response(str(e), 400)
        except Exception as e:
            print(f"Error handling request: {e}")
            return error_response('Internal server error', 500)

    # ============================================================================
    # USER ROUTES
    # ============================================================================

    async def handle_user(self, request, parts, db):
        """
        Handle /api/user/* routes

        GET    /api/user/:userId/settings
        PATCH  /api/user/:userId/settings
        """
        method = request.method
        user_id = parts[0] if parts else None

        if not user_id:
            return error_response('User ID required', 400)

        # GET /api/user/:userId/settings
        if len(parts) >= 2 and parts[1] == 'settings' and method == 'GET':
            result = await db.table('users').select('*').eq('id', user_id).execute()
            if not result['data']:
                return error_response('User not found', 404)
            return json_response(result['data'][0])

        # PATCH /api/user/:userId/settings
        elif len(parts) >= 2 and parts[1] == 'settings' and method == 'PATCH':
            data = await request.json()
            result = await db.table('users').eq('id', user_id).update(data)
            if not result['data']:
                return error_response('User not found', 404)
            return json_response(result['data'][0])

        return error_response('Endpoint not found', 404)

    # ============================================================================
    # WATCHLIST ROUTES
    # ============================================================================

    async def handle_watchlist(self, request, parts, db):
        """
        Handle /api/watchlist/* routes

        GET    /api/watchlist/:userId
        POST   /api/watchlist/:userId
        DELETE /api/watchlist/:userId/:ticker
        """
        method = request.method
        user_id = parts[0] if parts else None

        if not user_id:
            return error_response('User ID required', 400)

        # GET /api/watchlist/:userId
        if len(parts) == 1 and method == 'GET':
            result = await db.table('watchlists').select('*').eq('user_id', user_id).execute()
            return json_response(result['data'])

        # POST /api/watchlist/:userId
        elif len(parts) == 1 and method == 'POST':
            data = await request.json()
            ticker = data.get('ticker')
            if not ticker:
                return error_response('Ticker required', 400)

            # First get entity_id for this ticker
            entity_result = await db.table('entities').select('id').eq('ticker', ticker).execute()
            if not entity_result['data']:
                return error_response('Stock not found', 404)

            entity_id = entity_result['data'][0]['id']

            # Add to watchlist
            watchlist_data = {
                'user_id': user_id,
                'entity_id': entity_id,
            }
            result = await db.table('watchlists').insert(watchlist_data)
            return json_response(result['data'][0])

        # DELETE /api/watchlist/:userId/:ticker
        elif len(parts) == 2 and method == 'DELETE':
            ticker = parts[1]

            # Get entity_id for this ticker
            entity_result = await db.table('entities').select('id').eq('ticker', ticker).execute()
            if not entity_result['data']:
                return error_response('Stock not found', 404)

            entity_id = entity_result['data'][0]['id']

            # Remove from watchlist
            await db.table('watchlists').eq('user_id', user_id).eq('entity_id', entity_id).delete()
            return json_response({'success': True})

        return error_response('Endpoint not found', 404)

    # ============================================================================
    # ENTITIES ROUTES
    # ============================================================================

    async def handle_entities(self, request, parts, db):
        """
        Handle /api/entities/* routes

        GET /api/entities/search?q=query&limit=10
        GET /api/entities/:ticker
        GET /api/entities/popular
        """
        method = request.method

        if method != 'GET':
            return error_response('Method not allowed', 405)

        if not parts:
            return error_response('Invalid entities endpoint', 404)

        # Parse query parameters from URL
        url_parts = request.url.split('?')
        query_params = {}
        if len(url_parts) > 1:
            for param in url_parts[1].split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    query_params[key] = value

        # GET /api/entities/search
        if parts[0] == 'search':
            query = query_params.get('q', '')
            limit = int(query_params.get('limit', '10'))

            # Search by ticker or name
            result = await db.table('entities').select('*').ilike('ticker', f'%{query}%').limit(limit).execute()
            return json_response(result['data'])

        # GET /api/entities/popular
        elif parts[0] == 'popular':
            limit = int(query_params.get('limit', '20'))

            # Get most popular stocks (you can define popularity however you want)
            # For now, just return first N entities
            result = await db.table('entities').select('*').limit(limit).execute()
            return json_response(result['data'])

        # GET /api/entities/:ticker
        else:
            ticker = parts[0]
            result = await db.table('entities').select('*').eq('ticker', ticker).execute()
            if not result['data']:
                return error_response('Stock not found', 404)
            return json_response(result['data'][0])

    # ============================================================================
    # ALERTS ROUTES
    # ============================================================================

    async def handle_alerts(self, request, parts, db):
        """
        Handle /api/alerts/* routes

        GET  /api/alerts/:userId?limit=20&offset=0&type=valuation_regime_change
        POST /api/alerts/:alertId/opened
        GET  /api/alerts/:userId/stats
        """
        method = request.method

        if not parts:
            return error_response('User ID or Alert ID required', 400)

        # POST /api/alerts/:alertId/opened
        if len(parts) == 2 and parts[1] == 'opened' and method == 'POST':
            alert_id = parts[0]
            from datetime import datetime
            result = await db.table('alert_history').eq('id', alert_id).update({'opened_at': datetime.now().isoformat()})
            return json_response({'success': True})

        # GET /api/alerts/:userId/stats
        elif len(parts) == 2 and parts[1] == 'stats' and method == 'GET':
            user_id = parts[0]
            # Get alert statistics for this user
            result = await db.table('alert_history').select('*').eq('user_id', user_id).execute()
            total = len(result['data'])
            opened = sum(1 for alert in result['data'] if alert.get('opened_at'))
            return json_response({
                'total_alerts': total,
                'opened_alerts': opened,
                'unread_alerts': total - opened
            })

        # GET /api/alerts/:userId
        elif len(parts) == 1 and method == 'GET':
            user_id = parts[0]

            # Parse query parameters from URL
            url_parts = request.url.split('?')
            query_params = {}
            if len(url_parts) > 1:
                for param in url_parts[1].split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        query_params[key] = value

            limit = int(query_params.get('limit', '20'))
            offset = int(query_params.get('offset', '0'))
            alert_type = query_params.get('type')

            # Build query
            query = db.table('alert_history').select('*').eq('user_id', user_id)

            if alert_type:
                query = query.eq('alert_type', alert_type)

            query = query.limit(limit).offset(offset)

            result = await query.execute()
            return json_response(result['data'])

        return error_response('Endpoint not found', 404)
