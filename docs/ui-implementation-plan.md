# UI Implementation Plan - Stock Analyzer MVP

## Overview

Building a Next.js web application for the Stock Analyzer MVP with focus on:
- **Zero friction onboarding** - Email → Verify → Add stocks (< 2 minutes)
- **Clean, minimal design** - Inspired by Mercury's aesthetic
- **Fast, simple watchlist** - Autocomplete search, clear delta indicators
- **Auth-ready** - Supabase Auth with email magic links, prep for Google OAuth

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Auth**: Supabase Auth (email magic links, prep for Google)
- **Database**: PostgreSQL (Supabase)
- **Deployment**: Vercel (or Cloudflare Pages)

## Project Structure

```
web/                           # Next.js app root
├── src/
│   ├── app/                   # App router pages
│   │   ├── (auth)/           # Auth layout group
│   │   │   ├── login/
│   │   │   └── signup/
│   │   ├── (dashboard)/      # Dashboard layout group
│   │   │   ├── dashboard/
│   │   │   ├── watchlist/
│   │   │   └── settings/
│   │   ├── onboarding/       # Onboarding flow
│   │   ├── api/              # API routes
│   │   │   ├── watchlist/
│   │   │   └── user/
│   │   ├── layout.tsx
│   │   └── page.tsx          # Landing page
│   ├── components/
│   │   ├── auth/
│   │   │   ├── AuthProvider.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── onboarding/
│   │   │   ├── EmailStep.tsx
│   │   │   ├── InvestingStyleStep.tsx
│   │   │   └── StockPickerStep.tsx
│   │   ├── watchlist/
│   │   │   ├── StockSearch.tsx
│   │   │   ├── WatchlistTable.tsx
│   │   │   └── StockCard.tsx
│   │   ├── landing/
│   │   │   ├── Hero.tsx
│   │   │   ├── Features.tsx
│   │   │   └── CTA.tsx
│   │   └── ui/               # Reusable UI components
│   ├── lib/
│   │   ├── supabase/
│   │   │   ├── client.ts     # Browser client
│   │   │   ├── server.ts     # Server client
│   │   │   └── middleware.ts
│   │   ├── api/              # API client functions
│   │   └── utils/
│   ├── data/
│   │   └── us-tickers.ts     # US stock tickers for autocomplete
│   └── types/
│       └── database.ts        # Database types
├── public/
├── .env.local
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

## Database Integration

### Migration: Integrate Supabase Auth with Existing Schema

Create migration: `002_integrate_supabase_auth.sql`

```sql
-- Link existing users table to Supabase auth
ALTER TABLE users
  ADD COLUMN auth_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Add unique constraint
ALTER TABLE users
  ADD CONSTRAINT unique_auth_id UNIQUE(auth_id);

-- Create function to sync auth.users with users table
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (auth_id, email, created_at, updated_at)
  VALUES (NEW.id, NEW.email, NOW(), NOW())
  ON CONFLICT (auth_id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to auto-create user record on signup
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Create function to sync email updates
CREATE OR REPLACE FUNCTION handle_user_email_update()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE public.users
  SET email = NEW.email, updated_at = NOW()
  WHERE auth_id = NEW.id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to sync email updates
CREATE TRIGGER on_auth_user_email_updated
  AFTER UPDATE OF email ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_user_email_update();
```

### Row Level Security (RLS) Policies

```sql
-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_entity_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_history ENABLE ROW LEVEL SECURITY;

-- Users: Can only see/update their own data
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = auth_id);

CREATE POLICY "Users can update own data" ON users
  FOR UPDATE USING (auth.uid() = auth_id);

-- Watchlists: Users can manage their own watchlists
CREATE POLICY "Users can view own watchlists" ON watchlists
  FOR SELECT USING (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

CREATE POLICY "Users can insert own watchlists" ON watchlists
  FOR INSERT WITH CHECK (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

CREATE POLICY "Users can delete own watchlists" ON watchlists
  FOR DELETE USING (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

-- Similar policies for user_entity_settings and alert_history
```

## Authentication Flow

### 1. Email Magic Link (Primary)

**Signup Flow:**
1. User enters email on landing page
2. Supabase sends magic link
3. User clicks link → auto-authenticated
4. Redirect to onboarding flow

**Login Flow:**
1. User enters email on login page
2. Supabase sends magic link
3. User clicks link → authenticated
4. Redirect to dashboard

### 2. Google OAuth (Prepared, not implemented)

Setup in Supabase dashboard, add button in UI, but don't activate until MVP validation succeeds.

```typescript
// lib/supabase/auth.ts
export async function signInWithGoogle() {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`
    }
  })
  return { data, error }
}
```

## Onboarding Flow (3 Steps)

### Step 1: Email Input
- Clean form with single email field
- "Get Started" CTA
- Sends magic link
- Shows "Check your email" confirmation

### Step 2: Investing Style
- Choose one: Value / Growth / Blend
- Brief explanation of each (1 sentence)
- Skip option (defaults to Blend)

### Step 3: Add Stocks
- Autocomplete search bar
- Show popular stocks (AAPL, MSFT, GOOGL, etc.)
- Minimum 1 stock, recommended 5-10
- "Start Monitoring" CTA

**Design Principles:**
- Each step on separate screen
- Progress indicator (1/3, 2/3, 3/3)
- Can go back to previous step
- Auto-save as they progress
- < 2 minutes total time

## Landing Page Design (Mercury-inspired)

### Hero Section
```
┌─────────────────────────────────────────┐
│                                         │
│   Stop Re-Checking the Same Stocks     │
│                                         │
│   Get notified only when something     │
│   materially changes.                  │
│                                         │
│   [Enter email]  [Get Started →]       │
│                                         │
└─────────────────────────────────────────┘
```

### Features Section (3 columns)
1. **Valuation Alerts** - Know when stocks enter cheap/expensive zones
2. **Trend Breaks** - Catch major shifts without noise
3. **Fundamental Changes** - Early warning on deterioration

### How It Works
1. Add stocks you care about
2. We monitor 24/7
3. Get alerts only when something material changes

### CTA
- "Start monitoring your stocks" button
- "No credit card required"

**Design Tokens (Mercury-inspired):**
- Colors: Clean blacks (#000), whites (#FFF), subtle grays (#F5F5F5)
- Typography: Inter or similar sans-serif
- Spacing: Generous whitespace
- Borders: Subtle 1px borders
- Minimal shadows
- Clean, crisp aesthetics

## Watchlist Page

### Layout
```
┌─────────────────────────────────────────┐
│  [Search stocks...]              [+ Add]│
├─────────────────────────────────────────┤
│  Ticker  |  Valuation  |  Trend  | Last │
│  ─────────────────────────────────────  │
│  AAPL    |     ↑       |    →    | 2d   │
│  MSFT    |     →       |    ↑    | 5d   │
│  GOOGL   |     ↓       |    ↓    | 1w   │
└─────────────────────────────────────────┘
```

### Stock Autocomplete
- Instant search through US tickers
- Shows: Ticker + Company Name
- Filter as you type
- Select to add to watchlist

### Delta Indicators
- **↑** Green - Positive change
- **↓** Red - Negative change
- **→** Gray - No material change

### Actions
- Click row to see stock detail (future)
- Remove from watchlist
- Pause alerts for stock

## Dashboard Home

### Welcome Message
```
Welcome back! Here's what's happening with your watchlist.

No material changes today.
Your stocks are stable.

[View Watchlist →]
```

### Recent Alerts (if any)
```
Material Changes (Last 7 days)

[AAPL] Valuation entered cheap zone
  2 days ago

[TSLA] Trend break: Below 200-day MA
  5 days ago
```

### Explanation Section
```
What to expect:

✓ We monitor your stocks daily
✓ You'll get an email when something material changes
✓ No noise - only what matters

Material changes we track:
• Valuation regime shifts
• Trend breaks (200-day MA)
• Fundamental inflections
```

## US Tickers Data

Create a static file with ~3000 most traded US stocks:

```typescript
// src/data/us-tickers.ts
export interface Ticker {
  symbol: string
  name: string
  exchange: string
}

export const US_TICKERS: Ticker[] = [
  { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" },
  { symbol: "MSFT", name: "Microsoft Corporation", exchange: "NASDAQ" },
  // ... ~3000 more
]

// Helper function for search
export function searchTickers(query: string, limit = 10): Ticker[] {
  const q = query.toUpperCase()
  return US_TICKERS
    .filter(t =>
      t.symbol.startsWith(q) ||
      t.name.toUpperCase().includes(q)
    )
    .slice(0, limit)
}
```

Source for tickers: Can scrape from NASDAQ/NYSE lists or use a public dataset.

## API Routes

### POST /api/watchlist/add
```typescript
// Add stock to user's watchlist
{
  ticker: string
}
```

### DELETE /api/watchlist/:ticker
```typescript
// Remove stock from watchlist
```

### GET /api/watchlist
```typescript
// Get user's watchlist with latest states
Response: {
  stocks: [{
    ticker: string
    name: string
    valuation_state: "up" | "down" | "neutral"
    trend_state: "up" | "down" | "neutral"
    last_alert_date: string | null
  }]
}
```

### PATCH /api/user/settings
```typescript
// Update user settings
{
  investing_style?: "value" | "growth" | "blend"
  alerts_enabled?: boolean
}
```

## Environment Variables

```bash
# .env.local
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

## Implementation Steps

### Phase 1: Foundation (Day 1)
1. ✅ Initialize Next.js app with TypeScript + Tailwind
2. ✅ Set up Supabase client configuration
3. ✅ Create auth migration
4. ✅ Build basic auth provider
5. ✅ Set up protected routes

### Phase 2: Landing & Auth (Day 1-2)
1. Build landing page with Mercury-inspired design
2. Create email magic link signup flow
3. Add login page
4. Test auth flow end-to-end

### Phase 3: Onboarding (Day 2)
1. Create 3-step onboarding flow
2. Build stock picker with autocomplete
3. Add US tickers data
4. Test onboarding flow

### Phase 4: Dashboard (Day 2-3)
1. Build dashboard home with explanations
2. Create watchlist page
3. Implement stock search and add
4. Add delta indicators
5. Connect to API

### Phase 5: Polish (Day 3)
1. Add loading states
2. Error handling
3. Responsive design
4. Accessibility
5. Final testing

## Testing Checklist

- [ ] Can sign up with email
- [ ] Receive magic link email
- [ ] Auth state persists across refreshes
- [ ] Onboarding flow completes successfully
- [ ] Can add stocks to watchlist
- [ ] Autocomplete search works
- [ ] Watchlist displays correctly
- [ ] Can remove stocks
- [ ] Settings update works
- [ ] Protected routes redirect correctly

## Deployment

1. **Vercel** (recommended)
   - Connect GitHub repo
   - Auto-deploy on push
   - Add environment variables

2. **Cloudflare Pages** (alternative)
   - Build command: `npm run build`
   - Output directory: `.next`

## Next Steps After MVP

Once UI is live and users can onboard:
1. Connect to backend signal computation
2. Implement email alert delivery
3. Add tracking for validation metrics
4. Run 14-day validation experiment

## Design References

**Mercury-inspired elements:**
- Clean, minimal interface
- Generous whitespace
- Subtle borders and shadows
- Black text on white background
- Simple, functional typography
- Focus on content, not decoration
- Fast, responsive interactions

**Examples:**
- https://mercury.com - Overall aesthetic
- https://linear.app - Clean dashboard design
- https://stripe.com - Simple forms and CTAs

---

## Success Criteria

The UI is successful if:
- ✅ User can sign up in < 30 seconds
- ✅ Onboarding completes in < 2 minutes
- ✅ Watchlist is instantly understandable
- ✅ Zero questions about what the app does
- ✅ Fast, responsive, bug-free

**Remember:** Speed and clarity over features.
