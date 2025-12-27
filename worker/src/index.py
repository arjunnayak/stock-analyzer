"""
Cloudflare Worker - Material Changes API

Thin HTTP handlers that route requests to business logic services in src/services/
"""

from js import Response, Headers, fetch
import json
import sys
import os

# Add parent directory to path to import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.services import UserService, WatchlistService, EntitiesService, AlertsService
from src.config import get_supabase_client


# CORS headers for frontend
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',  # TODO: Restrict to frontend domain in production
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}


def json_response(data, status=200):
    """Create JSON response with CORS headers"""
    headers = Headers.new(CORS_HEADERS)
    headers.set('Content-Type', 'application/json')

    return Response.new(
        json.dumps(data),
        status=status,
        headers=headers
    )


def error_response(message, status=400):
    """Create error response"""
    return json_response({
        'error': {
            'message': message,
            'status': status
        }
    }, status=status)


def handle_request(request):
    """
    Main request handler

    Routes requests to appropriate handlers based on URL path
    """
    url = request.url
    method = request.method

    # Handle CORS preflight
    if method == 'OPTIONS':
        return Response.new('', status=204, headers=Headers.new(CORS_HEADERS))

    try:
        # Parse URL path
        path = url.pathname
        parts = path.strip('/').split('/')

        # Initialize database client
        db = get_supabase_client()

        # Route to appropriate handler
        if parts[0] == 'api':
            if parts[1] == 'user':
                return handle_user(request, parts[2:], db)
            elif parts[1] == 'watchlist':
                return handle_watchlist(request, parts[2:], db)
            elif parts[1] == 'entities':
                return handle_entities(request, parts[2:], db)
            elif parts[1] == 'alerts':
                return handle_alerts(request, parts[2:], db)
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

def handle_user(request, parts, db):
    """
    Handle /api/user/* routes

    POST   /api/user/:userId/onboarding
    GET    /api/user/:userId/settings
    PATCH  /api/user/:userId/settings
    """
    service = UserService(db)
    method = request.method
    user_id = parts[0] if parts else None

    if not user_id:
        return error_response('User ID required', 400)

    # POST /api/user/:userId/onboarding
    if len(parts) >= 2 and parts[1] == 'onboarding' and method == 'POST':
        data = await request.json()
        result = service.complete_onboarding(
            user_id,
            investing_style=data.get('investing_style'),
            tickers=data.get('tickers', [])
        )
        return json_response(result)

    # GET /api/user/:userId/settings
    elif len(parts) >= 2 and parts[1] == 'settings' and method == 'GET':
        result = service.get_settings(user_id)
        return json_response(result)

    # PATCH /api/user/:userId/settings
    elif len(parts) >= 2 and parts[1] == 'settings' and method == 'PATCH':
        data = await request.json()
        result = service.update_settings(user_id, data)
        return json_response(result)

    return error_response('Endpoint not found', 404)


# ============================================================================
# WATCHLIST ROUTES
# ============================================================================

def handle_watchlist(request, parts, db):
    """
    Handle /api/watchlist/* routes

    GET    /api/watchlist/:userId
    POST   /api/watchlist/:userId
    DELETE /api/watchlist/:userId/:ticker
    """
    service = WatchlistService(db)
    method = request.method
    user_id = parts[0] if parts else None

    if not user_id:
        return error_response('User ID required', 400)

    # GET /api/watchlist/:userId
    if len(parts) == 1 and method == 'GET':
        result = service.get_watchlist(user_id)
        return json_response(result)

    # POST /api/watchlist/:userId
    elif len(parts) == 1 and method == 'POST':
        data = await request.json()
        ticker = data.get('ticker')
        if not ticker:
            return error_response('Ticker required', 400)

        result = service.add_stock(user_id, ticker)
        return json_response(result)

    # DELETE /api/watchlist/:userId/:ticker
    elif len(parts) == 2 and method == 'DELETE':
        ticker = parts[1]
        result = service.remove_stock(user_id, ticker)
        return json_response(result)

    return error_response('Endpoint not found', 404)


# ============================================================================
# ENTITIES ROUTES
# ============================================================================

def handle_entities(request, parts, db):
    """
    Handle /api/entities/* routes

    GET /api/entities/search?q=query&limit=10
    GET /api/entities/:ticker
    GET /api/entities/popular
    """
    service = EntitiesService(db)
    method = request.method

    if method != 'GET':
        return error_response('Method not allowed', 405)

    # GET /api/entities/search
    if parts[0] == 'search':
        url = request.url
        query = url.searchParams.get('q', '')
        limit = int(url.searchParams.get('limit', '10'))

        result = service.search(query, limit)
        return json_response(result)

    # GET /api/entities/popular
    elif parts[0] == 'popular':
        url = request.url
        limit = int(url.searchParams.get('limit', '20'))

        result = service.get_popular_stocks(limit)
        return json_response(result)

    # GET /api/entities/:ticker
    else:
        ticker = parts[0]
        result = service.get_stock(ticker)
        return json_response(result)


# ============================================================================
# ALERTS ROUTES
# ============================================================================

def handle_alerts(request, parts, db):
    """
    Handle /api/alerts/* routes

    GET  /api/alerts/:userId?limit=20&offset=0&type=valuation_regime_change
    POST /api/alerts/:alertId/opened
    GET  /api/alerts/:userId/stats
    """
    service = AlertsService(db)
    method = request.method

    if not parts:
        return error_response('User ID or Alert ID required', 400)

    # POST /api/alerts/:alertId/opened
    if len(parts) == 2 and parts[1] == 'opened' and method == 'POST':
        alert_id = parts[0]
        result = service.mark_opened(alert_id)
        return json_response(result)

    # GET /api/alerts/:userId/stats
    elif len(parts) == 2 and parts[1] == 'stats' and method == 'GET':
        user_id = parts[0]
        result = service.get_alert_stats(user_id)
        return json_response(result)

    # GET /api/alerts/:userId
    elif len(parts) == 1 and method == 'GET':
        user_id = parts[0]
        url = request.url
        limit = int(url.searchParams.get('limit', '20'))
        offset = int(url.searchParams.get('offset', '0'))
        alert_type = url.searchParams.get('type')

        result = service.get_alerts(user_id, limit, offset, alert_type)
        return json_response(result)

    return error_response('Endpoint not found', 404)


# ============================================================================
# Worker Entry Point
# ============================================================================

def on_fetch(request):
    """Cloudflare Worker fetch event handler"""
    return handle_request(request)
