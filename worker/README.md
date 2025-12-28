# Material Changes - Cloudflare Worker API

Lightweight Python Worker that provides REST API endpoints for the Material Changes frontend.

## Architecture

```
Frontend (Next.js) → Worker (Python) → Services (src/services/) → Database
```

**Key Principle:** Worker contains **thin HTTP handlers only**. All business logic lives in `src/services/` which can be reused by Workers, GitHub Actions, and CLI tools.

## API Endpoints

### User Endpoints

```
POST   /api/user/:userId/onboarding
GET    /api/user/:userId/settings
PATCH  /api/user/:userId/settings
```

### Watchlist Endpoints

```
GET    /api/watchlist/:userId
POST   /api/watchlist/:userId
DELETE /api/watchlist/:userId/:ticker
```

### Entities Endpoints

```
GET /api/entities/search?q=query&limit=10
GET /api/entities/:ticker
GET /api/entities/popular
```

### Alerts Endpoints

```
GET  /api/alerts/:userId?limit=20&offset=0
POST /api/alerts/:alertId/opened
GET  /api/alerts/:userId/stats
```

### Health Check

```
GET /api/health
```

## Local Development

### Prerequisites

- Node.js 18+ (for Wrangler)
- Python 3.11+
- Supabase running locally

### Setup

1. **Install Wrangler CLI**

```bash
npm install -g wrangler
```

2. **Login to Cloudflare**

```bash
wrangler login
```

3. **Set up local environment**

```bash
# Copy environment file
cp .dev.vars.example .dev.vars

# Edit .dev.vars with your local Supabase credentials
```

4. **Run locally**

```bash
wrangler dev
```

The Worker will be available at http://localhost:8787

### Testing Endpoints

```bash
# Health check
curl http://localhost:8787/api/health

# Get watchlist (replace USER_ID)
curl http://localhost:8787/api/watchlist/USER_ID

# Add stock to watchlist
curl -X POST http://localhost:8787/api/watchlist/USER_ID \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
```

## Deployment

### Set Secrets

```bash
# Supabase credentials
wrangler secret put SUPABASE_URL
wrangler secret put SUPABASE_SERVICE_ROLE_KEY

# Frontend URL for CORS
wrangler secret put FRONTEND_URL
```

### Create R2 Bucket

```bash
wrangler r2 bucket create market-data
```

### Deploy to Production

```bash
# Deploy to production
wrangler deploy

# Deploy to staging
wrangler deploy --env staging

# Deploy to development
wrangler deploy --env development
```

### Configure Custom Domain

1. Go to Cloudflare Dashboard → Workers & Pages
2. Select your worker
3. Settings → Triggers → Custom Domains
4. Add domain: `api.materialchanges.com`

## Environment Variables

Set via `wrangler secret put`:

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (admin access) | Yes |
| `FRONTEND_URL` | Frontend URL for CORS | Yes |

## Project Structure

```
worker/
├── src/
│   └── index.py              # HTTP handlers (routes to services)
├── wrangler.toml             # Worker configuration
├── requirements.txt          # Python dependencies
├── .dev.vars.example         # Example local env vars
└── README.md                 # This file
```

**Business Logic:** Lives in `../src/services/` (shared with GitHub Actions)

## CORS Configuration

The Worker allows cross-origin requests from the frontend. Update `CORS_HEADERS` in `src/index.py` to restrict to your domain in production:

```python
CORS_HEADERS = {
    'Access-Control-Allow-Origin': 'https://materialchanges.com',
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}
```

## Error Handling

All errors return consistent JSON format:

```json
{
  "error": {
    "message": "Stock not found",
    "status": 404
  }
}
```

Status codes:
- `200` - Success
- `400` - Bad Request (invalid input)
- `404` - Not Found
- `405` - Method Not Allowed
- `500` - Internal Server Error

## Authentication

Currently, the Worker trusts the user_id from the request path. In production, you should:

1. Verify Supabase JWT token from Authorization header
2. Extract user_id from verified token
3. Use that user_id for all operations

Example:

```python
async def verify_auth(request):
    """Verify Supabase JWT token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise ValueError('Missing authorization')

    token = auth_header.replace('Bearer ', '')
    # Verify JWT with Supabase
    # Extract user_id from token
    return user_id
```

## Performance

- **Cold start**: ~50-100ms
- **Warm requests**: ~10-30ms
- **Database queries**: ~20-50ms (Supabase)

**Optimization tips:**
- Database connection pooling (handled by Supabase client)
- Cache frequently accessed data in KV store (future)
- Minimize database round-trips

## Monitoring

### View Logs

```bash
# Live tail logs
wrangler tail

# Filter by status code
wrangler tail --status error

# Filter by method
wrangler tail --method POST
```

### Metrics

View in Cloudflare Dashboard:
- Workers & Pages → Your Worker → Metrics
- Request count, error rate, CPU time, etc.

## Troubleshooting

### "Module not found" errors

Cloudflare Workers Python has limited package support. Use built-in modules or HTTP fetch for external services.

### CORS errors

Check that `FRONTEND_URL` matches your frontend domain and includes protocol (https://).

### Database connection errors

Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set correctly:

```bash
wrangler secret list
```

### 500 errors

Check logs:

```bash
wrangler tail --status error
```

## Next Steps

1. ✅ Deploy Worker to Cloudflare
2. ⚠️ Test all API endpoints
3. ⚠️ Add JWT authentication
4. ⚠️ Configure custom domain
5. ⚠️ Set up monitoring and alerts

## Resources

- [Cloudflare Workers Python Docs](https://developers.cloudflare.com/workers/languages/python/)
- [Wrangler CLI Docs](https://developers.cloudflare.com/workers/wrangler/)
- [Supabase REST API](https://supabase.com/docs/guides/api)
