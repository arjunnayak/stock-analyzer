# Cloudflare Python Worker Implementation Plan

## Overview

Build a Cloudflare Worker (Python) that exposes REST API endpoints for the Next.js frontend. The worker will:
- Use existing backend logic from `src/`
- Connect to Supabase (PostgreSQL)
- Connect to R2 storage
- Follow modular service-oriented architecture

## Architecture

```
┌─────────────────────────────────────────────┐
│         Next.js Frontend                    │
│         (Cloudflare Pages)                  │
└─────────────────┬───────────────────────────┘
                  │
                  │ HTTP/JSON
                  ▼
┌─────────────────────────────────────────────┐
│    Cloudflare Python Worker                 │
│                                              │
│  ┌──────────────────────────────────┐      │
│  │  API Routes (FastAPI/Hono)       │      │
│  │  - /api/user/*                   │      │
│  │  - /api/watchlist/*              │      │
│  │  - /api/entities/*               │      │
│  │  - /api/alerts/*                 │      │
│  └─────────────┬────────────────────┘      │
│                │                             │
│  ┌─────────────▼────────────────────┐      │
│  │  Service Layer                   │      │
│  │  - UserService                   │      │
│  │  - WatchlistService              │      │
│  │  - EntitiesService               │      │
│  │  - AlertsService                 │      │
│  └─────────────┬────────────────────┘      │
│                │                             │
│  ┌─────────────▼────────────────────┐      │
│  │  Existing Business Logic         │      │
│  │  (from src/)                     │      │
│  │  - config.py (DB connections)    │      │
│  │  - reader.py (R2 data reading)   │      │
│  │  - signals/ (alert logic)        │      │
│  └──────────────────────────────────┘      │
│                                              │
└────────┬──────────────────────┬─────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│   Supabase      │    │   R2 Storage    │
│   (PostgreSQL)  │    │   (Time-series) │
└─────────────────┘    └─────────────────┘
```

## Project Structure

```
worker/
├── src/
│   ├── index.py              # Main worker entry point
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── user.py          # User endpoints
│   │   ├── watchlist.py     # Watchlist endpoints
│   │   ├── entities.py      # Entities endpoints
│   │   └── alerts.py        # Alerts endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py      # User business logic
│   │   ├── watchlist_service.py # Watchlist CRUD
│   │   ├── entities_service.py  # Stock metadata
│   │   └── alerts_service.py    # Alert retrieval
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py          # JWT verification
│   │   ├── cors.py          # CORS handling
│   │   └── errors.py        # Error handling
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── db.py            # Database helpers
│   │   ├── validation.py    # Request validation
│   │   └── response.py      # Response formatting
│   └── models/
│       ├── __init__.py
│       └── schemas.py       # Pydantic models
├── tests/
│   ├── test_user.py
│   ├── test_watchlist.py
│   ├── test_entities.py
│   └── test_alerts.py
├── wrangler.toml            # Cloudflare Worker config
├── requirements.txt         # Python dependencies
└── README.md
```

## Reusing Existing Code

### 1. Database Configuration (src/config.py)
**Reuse:**
- `DatabaseConfig` class
- `get_supabase_client()` function
- Connection pooling logic

**Adapt:**
- Add Cloudflare Worker environment variable loading
- Use Worker secrets instead of .env files

### 2. R2 Data Reading (src/reader.py)
**Reuse:**
- `TimeSeriesReader` class
- `read_price_data()`, `read_fundamental_data()`
- Parquet reading logic

**Adapt:**
- Use Cloudflare R2 bindings instead of boto3
- Cache frequently accessed data

### 3. Signal Computation (src/signals/)
**Reuse:**
- `compute.py` - Signal calculation logic
- `valuation.py` - Valuation regime detection
- `technical.py` - Technical analysis
- `state_tracker.py` - State change detection

**Use for:**
- Reading latest signal states from R2
- Computing delta indicators for watchlist

### 4. Email Templates (src/email/templates.py)
**Future use:**
- Alert email formatting
- Not needed for initial MVP API

## API Endpoints to Implement

### User Endpoints

```python
# POST /api/user/:userId/onboarding
# Complete user onboarding
{
  "investing_style": "value" | "growth" | "blend" | null,
  "tickers": ["AAPL", "MSFT", ...]
}

# GET /api/user/:userId/settings
# Get user settings
Response: {
  "investing_style": "value",
  "alerts_enabled": true
}

# PATCH /api/user/:userId/settings
# Update user settings
{
  "investing_style": "growth",
  "alerts_enabled": false
}
```

### Watchlist Endpoints

```python
# GET /api/watchlist/:userId
# Get user's watchlist with latest states
Response: {
  "stocks": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "valuation_state": "up" | "down" | "neutral",
      "trend_state": "up" | "down" | "neutral",
      "last_alert_date": "2025-01-15" | null
    }
  ]
}

# POST /api/watchlist/:userId
# Add stock to watchlist
{
  "ticker": "AAPL"
}

# DELETE /api/watchlist/:userId/:ticker
# Remove stock from watchlist
```

### Entities Endpoints

```python
# GET /api/entities/search?q=aapl&limit=10
# Search stocks by ticker or name
Response: {
  "results": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "sector": "Technology"
    }
  ]
}

# GET /api/entities/:ticker
# Get stock details
Response: {
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "sector": "Technology",
  "has_price_data": true,
  "has_fundamental_data": true
}
```

### Alerts Endpoints

```python
# GET /api/alerts/:userId?limit=20
# Get user's alert history
Response: {
  "alerts": [
    {
      "id": "uuid",
      "ticker": "AAPL",
      "alert_type": "valuation_regime_change",
      "headline": "AAPL entered cheap zone",
      "sent_at": "2025-01-15T10:00:00Z",
      "opened_at": "2025-01-15T11:30:00Z" | null
    }
  ]
}

# POST /api/alerts/:alertId/opened
# Mark alert as opened (for tracking)
```

## Service Layer Design

### UserService

```python
class UserService:
    def __init__(self, db_client, r2_bucket):
        self.db = db_client
        self.r2 = r2_bucket

    async def complete_onboarding(self, user_id: str, data: OnboardingData):
        """
        1. Update user investing_style
        2. Create watchlist entries for all tickers
        3. Initialize user_entity_settings for each stock
        """
        pass

    async def get_settings(self, user_id: str):
        """Get user settings from database"""
        pass

    async def update_settings(self, user_id: str, settings: dict):
        """Update user settings"""
        pass
```

### WatchlistService

```python
class WatchlistService:
    def __init__(self, db_client, reader: TimeSeriesReader):
        self.db = db_client
        self.reader = reader  # Reuse from src/reader.py

    async def get_watchlist(self, user_id: str):
        """
        1. Fetch user's watchlist from database
        2. For each stock, read latest signal states from R2
        3. Compute delta indicators (up/down/neutral)
        4. Get last alert date from alert_history
        5. Return enriched watchlist
        """
        pass

    async def add_stock(self, user_id: str, ticker: str):
        """
        1. Verify ticker exists in entities table
        2. Create watchlist entry
        3. Initialize user_entity_settings
        """
        pass

    async def remove_stock(self, user_id: str, ticker: str):
        """
        1. Delete from watchlist
        2. Keep user_entity_settings for history
        """
        pass
```

### EntitiesService

```python
class EntitiesService:
    def __init__(self, db_client):
        self.db = db_client

    async def search(self, query: str, limit: int = 10):
        """
        Search entities by ticker or name
        Use PostgreSQL ILIKE for fuzzy matching
        """
        pass

    async def get_stock(self, ticker: str):
        """Get stock metadata from entities table"""
        pass
```

### AlertsService

```python
class AlertsService:
    def __init__(self, db_client):
        self.db = db_client

    async def get_alerts(self, user_id: str, limit: int = 20):
        """
        Fetch alert_history for user
        Order by sent_at DESC
        Include ticker, alert_type, headline, timestamps
        """
        pass

    async def mark_opened(self, alert_id: str):
        """Update opened_at timestamp"""
        pass
```

## Middleware

### Authentication Middleware

```python
# Verify Supabase JWT token
# Extract user_id from token
# Attach to request context
```

### CORS Middleware

```python
# Allow requests from Next.js frontend
# Handle preflight OPTIONS requests
```

### Error Handling

```python
# Catch all exceptions
# Return consistent error format
# Log errors for debugging
```

## Environment Variables (Worker Secrets)

```toml
[vars]
ENVIRONMENT = "production"

# Database (via secrets)
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "xxx"

# R2 Bucket (via binding)
# R2_BUCKET = "market-data"  # Configured as binding

# Frontend URL (for CORS)
FRONTEND_URL = "https://materialchanges.com"
```

## Database Queries

### Get Watchlist with States

```sql
-- Get watchlist with latest signal states and alerts
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
    SELECT sent_at
    FROM alert_history
    WHERE user_id = w.user_id
      AND entity_id = w.entity_id
    ORDER BY sent_at DESC
    LIMIT 1
  ) as last_alert_date
FROM watchlists w
JOIN entities e ON w.entity_id = e.id
LEFT JOIN user_entity_settings ues ON
  w.user_id = ues.user_id AND w.entity_id = ues.entity_id
WHERE w.user_id = $1
ORDER BY w.added_at DESC;
```

### Add Stock to Watchlist

```sql
-- 1. Get entity_id
SELECT id FROM entities WHERE ticker = $1;

-- 2. Insert into watchlist
INSERT INTO watchlists (user_id, entity_id, alerts_enabled)
VALUES ($1, $2, true)
ON CONFLICT (user_id, entity_id) DO NOTHING
RETURNING id;

-- 3. Initialize user_entity_settings
INSERT INTO user_entity_settings (user_id, entity_id)
VALUES ($1, $2)
ON CONFLICT (user_id, entity_id) DO NOTHING;
```

## Computing Delta Indicators

```python
def compute_state_indicator(current_regime, previous_regime):
    """
    Compare current vs previous state to determine indicator

    Returns: "up" | "down" | "neutral"
    """
    if current_regime == previous_regime:
        return "neutral"

    # Valuation: cheap -> normal/expensive = "up" (bad for value)
    # Trend: below_200dma -> above_200dma = "up" (bullish)

    # This logic depends on alert type
    # Reuse from src/signals/state_tracker.py
```

## Error Handling

```python
# Standard error response format
{
  "error": {
    "message": "Stock not found",
    "code": "STOCK_NOT_FOUND",
    "status": 404
  }
}

# Error codes:
# - INVALID_REQUEST (400)
# - UNAUTHORIZED (401)
# - FORBIDDEN (403)
# - NOT_FOUND (404)
# - INTERNAL_ERROR (500)
```

## Testing Strategy

### Unit Tests
- Test each service method independently
- Mock database and R2 calls
- Test error cases

### Integration Tests
- Test API endpoints end-to-end
- Use test database
- Verify response formats

### Load Tests (Future)
- Test Worker performance
- Monitor R2 read latency
- Check database connection pooling

## Performance Considerations

### Caching
- Cache entity metadata (rarely changes)
- Cache signal data with TTL (updated daily)
- Use Cloudflare KV for frequently accessed data

### Database Optimization
- Use connection pooling
- Index on user_id, entity_id, ticker
- Batch queries where possible

### R2 Optimization
- Read signal data once per watchlist request
- Consider pre-aggregating daily states
- Use streaming for large datasets

## Deployment Steps

1. **Create Worker**
   ```bash
   wrangler init worker
   ```

2. **Configure Secrets**
   ```bash
   wrangler secret put SUPABASE_URL
   wrangler secret put SUPABASE_SERVICE_ROLE_KEY
   ```

3. **Bind R2 Bucket**
   ```toml
   [[r2_buckets]]
   binding = "BUCKET"
   bucket_name = "market-data"
   ```

4. **Deploy**
   ```bash
   wrangler deploy
   ```

5. **Test**
   ```bash
   curl https://worker.your-subdomain.workers.dev/api/health
   ```

## Migration Path

### Phase 1: Core API (Week 1)
- ✅ User service (onboarding, settings)
- ✅ Watchlist service (CRUD)
- ✅ Entities service (search, get)
- ✅ Basic error handling

### Phase 2: Alerts (Week 2)
- ✅ Alerts service (history, mark opened)
- ✅ Integration with signal computation
- ✅ Delta indicators from R2 data

### Phase 3: Optimization (Week 3)
- ✅ Caching layer
- ✅ Performance monitoring
- ✅ Load testing
- ✅ Security hardening

## Success Criteria

- ✅ All API endpoints implemented
- ✅ Frontend can complete full user flow
- ✅ Response time < 200ms (p95)
- ✅ 99.9% uptime
- ✅ Proper error handling
- ✅ Comprehensive tests

## Questions to Resolve

1. **Auth Strategy**: Verify Supabase JWT in Worker or trust frontend?
   - **Recommendation**: Verify JWT for security

2. **Caching**: Use Cloudflare KV or in-memory cache?
   - **Recommendation**: KV for cross-request caching

3. **R2 Access**: Direct binding or via S3 API?
   - **Recommendation**: R2 binding (faster, native)

4. **Signal Computation**: Read from R2 or pre-compute daily?
   - **Recommendation**: Read from R2 (simpler, less storage)

---

## Next Steps

1. Review and approve this plan
2. Create Worker project structure
3. Implement services one by one
4. Test with frontend
5. Deploy to Cloudflare

**Estimated Time**: 2-3 days for core API, 1 week for full implementation

---

Does this plan look good? Any changes you'd like before I start implementing?
