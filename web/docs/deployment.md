# Deployment Guide - Material Changes Web UI

## Architecture Overview

```
┌─────────────────┐
│   Next.js App   │
│  (Cloudflare    │
│     Pages)      │
└────────┬────────┘
         │
         ├──► Supabase (Auth + Database)
         │
         └──► Cloudflare Python Worker (API)
                     │
                     ├──► Supabase (PostgreSQL)
                     └──► R2 Storage
```

## Prerequisites

- [ ] Cloudflare account
- [ ] Supabase account (or self-hosted)
- [ ] GitHub repository
- [ ] Domain name (optional)

## Step 1: Deploy Supabase

### Option A: Supabase Cloud

1. Go to [supabase.com](https://supabase.com)
2. Create new project
3. Wait for database to provision
4. Run migrations:

```bash
# Install Supabase CLI
npm install -g supabase

# Link to project
supabase link --project-ref your-project-ref

# Push migrations
cd stock-analyzer
supabase db push
```

5. Get credentials:
   - Project URL: `https://xxx.supabase.co`
   - Anon key: From Settings → API
   - Service role key: From Settings → API (keep secret!)

### Option B: Self-Hosted

See [Supabase self-hosting docs](https://supabase.com/docs/guides/self-hosting)

## Step 2: Deploy Cloudflare Python Worker

The Python Worker will use the existing backend logic in `src/`.

### Create Worker

1. Go to Cloudflare Dashboard → Workers & Pages
2. Click "Create Application" → "Create Worker"
3. Name it (e.g., `material-changes-api`)

### Deploy Worker

```bash
# Install Wrangler CLI
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Deploy worker
cd stock-analyzer
# TODO: Create wrangler.toml and worker code
wrangler deploy
```

### Configure Environment Variables

In Cloudflare Dashboard → Workers → Settings → Environment Variables:

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx
R2_BUCKET_NAME=market-data
```

### Bind R2 Storage

In Cloudflare Dashboard → Workers → Settings → Bindings:
- Add R2 bucket binding
- Variable name: `BUCKET`
- R2 bucket: `market-data`

## Step 3: Deploy Next.js to Cloudflare Pages

### Connect GitHub

1. Go to Cloudflare Dashboard → Pages
2. Click "Create a project"
3. Connect to GitHub
4. Select your repository
5. Configure build settings:

```
Framework preset: Next.js
Build command: npm run build
Build output directory: .next
Root directory: web
Branch: main
```

### Set Environment Variables

In Cloudflare Pages → Settings → Environment Variables:

**Production:**
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
NEXT_PUBLIC_SITE_URL=https://materialchanges.com
NEXT_PUBLIC_API_URL=https://material-changes-api.your-subdomain.workers.dev
```

**Preview (optional):**
Same values but with preview URLs

### Deploy

1. Push to main branch
2. Cloudflare Pages auto-builds and deploys
3. Check build logs for errors
4. Visit your site: `https://xxx.pages.dev`

### Custom Domain

1. Go to Pages → Custom domains
2. Click "Set up a custom domain"
3. Add your domain (e.g., `materialchanges.com`)
4. Update DNS records as instructed
5. Wait for SSL certificate (a few minutes)

## Step 4: Configure Supabase Auth

### Update Auth Settings

In Supabase Dashboard → Authentication → URL Configuration:

**Site URL:**
```
https://materialchanges.com
```

**Redirect URLs:**
```
https://materialchanges.com/auth/callback
https://materialchanges.com/**
```

### Email Templates

Customize magic link email in Authentication → Email Templates:

**Subject:** Sign in to Material Changes

**Body:**
```html
<h2>Welcome to Material Changes</h2>
<p>Click the link below to sign in:</p>
<p><a href="{{ .ConfirmationURL }}">Sign in</a></p>
<p>This link expires in 24 hours.</p>
```

## Step 5: Set up R2 Storage

### Create R2 Bucket

1. Go to Cloudflare Dashboard → R2
2. Click "Create bucket"
3. Name: `market-data`
4. Region: Automatic

### Configure CORS (if needed)

```bash
# Using Wrangler
wrangler r2 bucket cors set market-data --config cors.json
```

`cors.json`:
```json
{
  "AllowedOrigins": ["https://materialchanges.com"],
  "AllowedMethods": ["GET"],
  "AllowedHeaders": ["*"]
}
```

## Step 6: Verify Deployment

### Checklist

- [ ] Landing page loads (https://materialchanges.com)
- [ ] Can click "Get Started"
- [ ] Email signup sends magic link
- [ ] Magic link redirects to onboarding
- [ ] Can complete onboarding (2 steps)
- [ ] Dashboard loads after onboarding
- [ ] Can add/remove stocks from watchlist
- [ ] Settings page works
- [ ] Can sign out and sign back in

### Test Auth Flow

1. Go to https://materialchanges.com
2. Click "Get Started"
3. Enter test email
4. Check email for magic link
5. Click link → should redirect to onboarding
6. Complete onboarding
7. Should land on dashboard

### Check Logs

**Cloudflare Pages:**
- Dashboard → Pages → Deployments → View logs

**Cloudflare Worker:**
- Dashboard → Workers → Logs → Live tail

**Supabase:**
- Dashboard → Database → Logs

## Step 7: Monitoring & Analytics

### Cloudflare Analytics

- Pages → Analytics
- Workers → Analytics
- Monitor requests, errors, bandwidth

### Supabase Logs

- Dashboard → Database → Logs
- Monitor auth events, database queries

### Error Tracking (Optional)

Add Sentry for error tracking:

```bash
npm install @sentry/nextjs
```

## Environment-Specific Settings

### Development

```bash
# .env.local
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=local_key
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8787
```

### Staging

```bash
NEXT_PUBLIC_SUPABASE_URL=https://staging-xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=staging_key
NEXT_PUBLIC_SITE_URL=https://staging.materialchanges.com
NEXT_PUBLIC_API_URL=https://staging-api.workers.dev
```

### Production

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=production_key
NEXT_PUBLIC_SITE_URL=https://materialchanges.com
NEXT_PUBLIC_API_URL=https://api.materialchanges.com
```

## Security Checklist

- [ ] HTTPS enabled (Cloudflare Pages auto-enables)
- [ ] Environment variables set (not in code)
- [ ] Row Level Security (RLS) enabled on all tables
- [ ] Supabase service role key kept secret
- [ ] CORS configured properly
- [ ] Rate limiting enabled (Cloudflare)
- [ ] Redirect URLs whitelisted in Supabase

## Costs (Free Tier)

- **Cloudflare Pages:** Free (500 builds/month)
- **Cloudflare Workers:** Free (100k requests/day)
- **Cloudflare R2:** Free (10GB storage, 1M Class A, 10M Class B)
- **Supabase:** Free (500MB database, 1GB file storage, 2GB bandwidth)

## Rollback Procedure

If deployment fails:

### Cloudflare Pages

1. Go to Dashboard → Pages → Deployments
2. Find last working deployment
3. Click "..." → "Rollback to this deployment"

### Cloudflare Worker

1. Go to Dashboard → Workers → Deployments
2. Click "Rollback" on previous version

### Database

```bash
supabase db reset  # Caution: destructive
# Or manually rollback specific migration
```

## Troubleshooting

### Build Fails

- Check build logs in Cloudflare Pages
- Verify all dependencies in package.json
- Ensure Next.js config is correct

### Auth Not Working

- Verify Supabase URL and keys
- Check redirect URLs in Supabase settings
- Test magic link email delivery

### API Errors

- Check Worker logs
- Verify environment variables
- Test Worker endpoints directly

### Database Connection Failed

- Check Supabase credentials
- Verify RLS policies
- Check database logs

## Next Steps

1. Set up monitoring and alerts
2. Configure custom domain
3. Add analytics (Google Analytics, Plausible, etc.)
4. Set up automated backups
5. Create staging environment
6. Document runbook for incidents

---

**Support:** For issues, check Cloudflare docs or Supabase docs
