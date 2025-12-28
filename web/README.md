# Material Changes - Web UI

> Simple, fast, and frictionless stock monitoring interface

## Overview

This is the Next.js frontend for Material Changes, designed for deployment on Cloudflare Pages. It provides a clean, Mercury-inspired interface for users to monitor their stock watchlists and receive alerts when material changes occur.

## Features

- ✅ **Email Magic Link Authentication** - Passwordless sign up and login via Supabase Auth
- ✅ **Frictionless Onboarding** - 2-step onboarding: investing style + add stocks (< 2 minutes)
- ✅ **Smart Watchlist** - Autocomplete stock search with real-time state indicators
- ✅ **Material Changes Dashboard** - Clear overview of what's happening with your stocks
- ✅ **Clean, Minimal Design** - Mercury-inspired aesthetics with generous whitespace
- 🔜 **Google OAuth** - Prepared but not enabled (see `docs/google-auth-setup.md`)

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Authentication**: Supabase Auth (email magic links)
- **Database**: PostgreSQL via Supabase
- **Deployment**: Cloudflare Pages
- **Backend**: Cloudflare Python Worker (using existing `src/` logic)

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Copy `.env.local.example` to `.env.local` and update:

```bash
cp .env.local.example .env.local
```

Update the values:

```bash
# Get these from Supabase dashboard or local Supabase instance
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key_here

# Your site URL
NEXT_PUBLIC_SITE_URL=http://localhost:3000

# Cloudflare Python Worker endpoint
NEXT_PUBLIC_API_URL=http://localhost:8787
```

### 3. Run Development Server

```bash
npm run dev
```

Visit http://localhost:3000

## Project Structure

```
web/
├── app/                          # Next.js App Router
│   ├── (auth)/
│   │   ├── login/               # Login page
│   │   └── signup/              # Signup page
│   ├── auth/
│   │   └── callback/            # OAuth callback handler
│   ├── onboarding/              # 2-step onboarding flow
│   ├── dashboard/               # Main dashboard
│   ├── watchlist/               # Watchlist management
│   ├── settings/                # User settings
│   ├── layout.tsx               # Root layout with AuthProvider
│   ├── page.tsx                 # Landing page
│   └── globals.css              # Global styles
├── components/
│   ├── auth/
│   │   └── AuthProvider.tsx    # Auth context provider
│   ├── onboarding/
│   │   ├── InvestingStyleStep.tsx
│   │   └── StockPickerStep.tsx
│   └── watchlist/
│       ├── StockSearch.tsx      # Autocomplete search
│       └── WatchlistTable.tsx   # Watchlist display
├── lib/
│   ├── supabase/
│   │   ├── client.ts            # Browser Supabase client
│   │   ├── server.ts            # Server Supabase client
│   │   ├── middleware.ts        # Auth middleware
│   │   └── auth.ts              # Auth helper functions
│   └── api/
│       ├── client.ts            # API client for Python Worker
│       └── README.md            # API documentation
├── data/
│   └── us-tickers.ts            # US stock tickers for autocomplete
├── types/
│   └── database.ts              # Database TypeScript types
├── docs/
│   └── google-auth-setup.md     # Google OAuth setup guide
├── middleware.ts                # Next.js middleware for auth
├── .env.local                   # Local environment variables
└── package.json
```

## Development Workflow

### 1. Start Services

Make sure you have the backend services running:

```bash
# In the root directory
cd ..
make setup  # Start Supabase, MinIO, etc.
```

### 2. Develop

```bash
npm run dev
```

The app will be available at http://localhost:3000

### 3. Test Auth Flow

1. Go to http://localhost:3000
2. Click "Get Started" or "Sign up"
3. Enter your email
4. Check email for magic link (or check Supabase logs)
5. Click magic link → redirected to onboarding
6. Complete onboarding → redirected to dashboard

### 4. View Database

Open Supabase Studio at http://localhost:54323 to view:
- Auth users
- User records
- Watchlists
- Alert history

## Deployment

### Cloudflare Pages

1. **Connect your GitHub repo**
   - Go to Cloudflare Dashboard → Pages
   - Click "Create a project"
   - Connect to GitHub and select your repo
   - Set build directory: `web`

2. **Configure build settings**
   ```
   Build command: npm run build
   Build output directory: .next
   Root directory: web
   Framework preset: Next.js
   ```

3. **Set environment variables**
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
   NEXT_PUBLIC_SITE_URL=https://yourdomain.com
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```

4. **Deploy**
   - Push to main branch
   - Cloudflare Pages auto-deploys

### Vercel (Alternative)

```bash
npm install -g vercel
vercel
```

Follow the prompts and set environment variables in Vercel dashboard.

## Authentication

### Supabase Auth Flow

1. **Sign Up**
   - User enters email
   - Supabase sends magic link
   - User clicks link
   - Session created, user record auto-created via trigger

2. **Login**
   - Same flow as sign up
   - Existing users get logged in

3. **Protected Routes**
   - Middleware checks auth state
   - Redirects to /login if not authenticated
   - Redirects to /dashboard if already authenticated

### Database Integration

User records are automatically created via database trigger (see `supabase/migrations/002_integrate_supabase_auth.sql`):

```sql
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

## API Integration

The frontend calls Cloudflare Python Worker endpoints that use the existing backend logic in `src/`.

See `/lib/api/README.md` for full API documentation.

Example:

```typescript
import { watchlistApi } from '@/lib/api/client'

const { data, error } = await watchlistApi.getWatchlist(userId)
if (error) {
  console.error('Failed to fetch watchlist:', error)
} else {
  console.log('Watchlist:', data.stocks)
}
```

## Design Principles

### Mercury-Inspired Aesthetics

- **Colors**: Clean blacks (#000), whites (#FFF), subtle grays (#F5F5F5)
- **Typography**: System fonts (Apple System, SF, Roboto)
- **Spacing**: Generous whitespace, clean layouts
- **Borders**: Subtle 1px borders, minimal shadows
- **Interactions**: Fast, responsive, no unnecessary animations

### User Experience

- **Speed**: < 30 seconds to sign up, < 2 minutes to onboard
- **Clarity**: Zero questions about what the app does
- **Simplicity**: Only essential features, no clutter
- **Accessibility**: Keyboard navigation, semantic HTML

## Scripts

```bash
npm run dev      # Start development server
npm run build    # Build for production
npm run start    # Start production server
npm run lint     # Run ESLint
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key | `eyJxxx...` |
| `NEXT_PUBLIC_SITE_URL` | Your site URL | `https://materialchanges.com` |
| `NEXT_PUBLIC_API_URL` | Python Worker API URL | `https://api.materialchanges.com` |

## Next Steps

1. ✅ Frontend UI complete
2. ⚠️ Wire up API calls to Python Worker
3. ⚠️ Implement Cloudflare Python Worker endpoints
4. ⚠️ Test end-to-end flow
5. ⚠️ Deploy to Cloudflare Pages

## Troubleshooting

### "Invalid auth credentials"

- Check that `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are correct
- Verify Supabase is running (http://localhost:54323)

### "Redirect URI mismatch"

- Check `NEXT_PUBLIC_SITE_URL` matches your actual URL
- Update Supabase auth settings if needed

### "API request failed"

- Verify Python Worker is running
- Check `NEXT_PUBLIC_API_URL` is correct
- Check browser console for CORS errors

## Contributing

This is an MVP validation project. Focus on:
- Speed over perfection
- User experience over features
- Learning over building

## License

TBD

---

**North Star**: Every line of code must reduce how often the user feels the need to re-check a stock manually.
