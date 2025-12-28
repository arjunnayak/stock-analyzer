# API Client for Material Changes

## Overview

This directory contains the API client that connects the Next.js frontend to the Cloudflare Python Worker backend.

## Architecture

```
┌─────────────────┐
│   Next.js App   │
│  (Cloudflare    │
│     Pages)      │
└────────┬────────┘
         │
         │ HTTP Requests
         ▼
┌─────────────────┐
│   Cloudflare    │
│  Python Worker  │
│                 │
│  Uses existing  │
│  src/ logic     │
└────────┬────────┘
         │
         ├──► Supabase (PostgreSQL)
         └──► R2 Storage
```

## Usage

### Import the API client

```typescript
import { watchlistApi, userApi, alertsApi, entitiesApi } from '@/lib/api/client'
```

### Examples

#### Get user's watchlist

```typescript
const { data, error } = await watchlistApi.getWatchlist(userId)
if (error) {
  console.error('Failed to fetch watchlist:', error)
} else {
  console.log('Watchlist:', data.stocks)
}
```

#### Add stock to watchlist

```typescript
const { error } = await watchlistApi.addStock(userId, 'AAPL')
if (error) {
  console.error('Failed to add stock:', error)
} else {
  console.log('Stock added successfully')
}
```

#### Update user settings

```typescript
const { error } = await userApi.updateSettings(userId, {
  investing_style: 'value',
  alerts_enabled: true,
})
```

#### Complete onboarding

```typescript
const { error } = await userApi.completeOnboarding(userId, {
  investing_style: 'blend',
  tickers: ['AAPL', 'MSFT', 'GOOGL'],
})
```

## Environment Variables

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8787  # Development
NEXT_PUBLIC_API_URL=https://api.materialchanges.com  # Production
```

## Error Handling

All API functions return a consistent response format:

```typescript
{
  data?: T,      // Response data if successful
  error?: string // Error message if failed
}
```

Always check for errors:

```typescript
const { data, error } = await watchlistApi.getWatchlist(userId)
if (error) {
  // Handle error
  return
}
// Use data
```

## Authentication

The API client doesn't handle authentication directly. Use Supabase Auth to get the user ID:

```typescript
import { useAuth } from '@/components/auth/AuthProvider'

const { user } = useAuth()
if (user) {
  const userId = user.id
  const { data } = await watchlistApi.getWatchlist(userId)
}
```

## API Endpoints

See the Python Worker backend for full API documentation. Key endpoints:

### Watchlist
- `GET /api/watchlist/:userId` - Get user's watchlist
- `POST /api/watchlist/:userId` - Add stock to watchlist
- `DELETE /api/watchlist/:userId/:ticker` - Remove stock

### User Settings
- `GET /api/user/:userId/settings` - Get user settings
- `PATCH /api/user/:userId/settings` - Update settings
- `POST /api/user/:userId/onboarding` - Complete onboarding

### Alerts
- `GET /api/alerts/:userId` - Get alert history
- `POST /api/alerts/:alertId/opened` - Mark alert as opened

### Entities
- `GET /api/entities/search?q=query` - Search stocks
- `GET /api/entities/:ticker` - Get stock details

## Development

The API client is designed to work with both:
1. Local development (Python Worker running locally)
2. Production (deployed Cloudflare Worker)

Set `NEXT_PUBLIC_API_URL` accordingly in your `.env.local` file.

## Next Steps

1. Implement the Cloudflare Python Worker endpoints
2. Wire up the API calls in the frontend components
3. Add proper error handling and loading states
4. Test end-to-end flow
