# Cloudflare Pages Deployment Guide

This guide explains how to deploy the Material Changes web app to Cloudflare Pages.

## Overview

The app is configured as a static Next.js export that deploys to Cloudflare Pages. The architecture is:

```
Cloudflare Pages (Frontend) → Cloudflare Worker (API) → Supabase (Database)
```

## Prerequisites

- Cloudflare account with Pages enabled
- Wrangler CLI installed: `npm install -g wrangler`
- Node.js 18+ and npm installed
- Access to your Supabase project credentials

## Configuration

### 1. Environment Variables

The app requires the following environment variables to be set in Cloudflare Pages:

#### Production Environment Variables

Set these in the Cloudflare Pages dashboard under **Settings → Environment variables**:

```bash
# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key

# API Configuration
NEXT_PUBLIC_API_URL=https://api.yourdomain.com

# Site Configuration
NEXT_PUBLIC_SITE_URL=https://yourdomain.com

# Dev Auth (DISABLE IN PRODUCTION)
NEXT_PUBLIC_ENABLE_DEV_AUTH=false
```

#### Local Development

Copy `.env.example` to `.env.local` and configure:

```bash
cp .env.example .env.local
```

Edit `.env.local` with your local development values.

## Deployment Methods

### Method 1: Deploy via Cloudflare Dashboard (Recommended)

1. **Connect GitHub Repository**
   - Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
   - Navigate to **Pages** → **Create a project**
   - Connect your GitHub account
   - Select the `stock-analyzer` repository

2. **Configure Build Settings**
   - **Production branch**: `main` or `master`
   - **Build command**: `npm run pages:build`
   - **Build output directory**: `out`
   - **Root directory**: `web`

3. **Set Environment Variables**
   - Add all production environment variables listed above
   - Click **Save and Deploy**

4. **Deploy**
   - Click **Save and Deploy**
   - Cloudflare will build and deploy your app
   - Your app will be available at `https://your-project.pages.dev`

### Method 2: Deploy via Wrangler CLI

1. **Login to Cloudflare**
   ```bash
   wrangler login
   ```

2. **Build the Application**
   ```bash
   cd web
   npm run pages:build
   ```

3. **Deploy to Cloudflare Pages**
   ```bash
   npm run pages:deploy
   ```

   Or manually:
   ```bash
   wrangler pages deploy out --project-name=material-changes-web
   ```

4. **Set Environment Variables**
   ```bash
   # Set production variables
   wrangler pages secret put NEXT_PUBLIC_SUPABASE_URL
   wrangler pages secret put NEXT_PUBLIC_SUPABASE_ANON_KEY
   wrangler pages secret put NEXT_PUBLIC_API_URL
   wrangler pages secret put NEXT_PUBLIC_SITE_URL
   ```

## Local Development

### Start Development Server

```bash
cd web
npm run dev
```

The app will be available at `http://localhost:3000`

### Preview Production Build Locally

```bash
# Build the static export
npm run pages:build

# Preview with Wrangler
npm run pages:preview
```

## Custom Domain Setup

### 1. Add Custom Domain in Cloudflare

1. Go to your Pages project in Cloudflare Dashboard
2. Navigate to **Custom domains**
3. Click **Set up a custom domain**
4. Enter your domain (e.g., `app.materialchanges.com`)
5. Follow the DNS configuration instructions

### 2. Update Environment Variables

Update `NEXT_PUBLIC_SITE_URL` to match your custom domain:

```bash
NEXT_PUBLIC_SITE_URL=https://app.materialchanges.com
```

## Connecting to Worker API

The frontend communicates with the Cloudflare Worker API. Make sure:

1. **Worker is deployed** (see `/worker/README.md`)
2. **API URL is configured** in environment variables
3. **CORS is enabled** on the Worker for your domain

Update the Worker's CORS configuration in `worker/src/index.py`:

```python
CORS_HEADERS = {
    'Access-Control-Allow-Origin': 'https://yourdomain.com',
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}
```

## Connecting to Supabase

### Local Development

Uses local Supabase instance (via Docker):
- URL: `http://localhost:54321`
- Anon Key: (from `../.env.local`)

### Production

1. Create a Supabase project at https://supabase.com
2. Get your project URL and anon key from **Settings → API**
3. Add them to Cloudflare Pages environment variables

## Build Configuration

### next.config.ts

The app is configured for static export with these settings:

```typescript
{
  output: "export",        // Static export for Cloudflare Pages
  images: {
    unoptimized: true,    // Disable image optimization
  },
  trailingSlash: true,    // Add trailing slashes to URLs
}
```

### package.json Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production (static export)
- `npm run pages:build` - Build for Cloudflare Pages (alias for build)
- `npm run pages:deploy` - Build and deploy to Cloudflare Pages
- `npm run pages:preview` - Preview production build locally

## Troubleshooting

### Build Fails

1. **Check Node.js version**: Ensure Node.js 18+ is installed
2. **Clear cache**: Delete `.next` and `out` folders, then rebuild
3. **Check environment variables**: Ensure all required variables are set
4. **Review build logs**: Check Cloudflare Pages build logs for errors

### App Loads but API Calls Fail

1. **Check API URL**: Verify `NEXT_PUBLIC_API_URL` is correct
2. **Check CORS**: Ensure Worker allows requests from your domain
3. **Check Worker deployment**: Verify Worker is deployed and accessible
4. **Check browser console**: Look for network errors

### Supabase Connection Issues

1. **Check credentials**: Verify Supabase URL and anon key are correct
2. **Check RLS policies**: Ensure Row Level Security policies allow access
3. **Check network**: Verify Supabase is accessible from Cloudflare

### Images Don't Load

Images are configured as `unoptimized` for static export. Ensure:
1. Images are in the `public/` directory
2. Image paths are absolute (e.g., `/logo.png`)
3. No dynamic image imports

## Continuous Deployment

### Automatic Deployments

When connected via GitHub:
- **Production**: Pushes to `main` branch auto-deploy to production
- **Preview**: Pull requests create preview deployments
- **Rollback**: Previous deployments can be activated from the dashboard

### Manual Deployments

Use Wrangler CLI for manual deployments:

```bash
npm run pages:deploy
```

## Performance Optimization

### Recommended Settings

1. **Enable caching** in Cloudflare Pages settings
2. **Enable auto-minify** for JS, CSS, and HTML
3. **Enable Brotli compression**
4. **Configure cache rules** for static assets

### Analytics

Enable Web Analytics in Cloudflare Pages:
1. Go to **Analytics** in your Pages project
2. Enable **Web Analytics**
3. View traffic, performance, and Core Web Vitals

## Security

### Environment Variables

- **Never commit** `.env.local` or `.env` files
- Use Cloudflare Pages secrets for sensitive values
- Rotate keys regularly

### HTTPS

- Cloudflare Pages automatically provides SSL/TLS
- All traffic is encrypted by default
- Use HSTS headers for additional security

## Support

For issues specific to:
- **Cloudflare Pages**: https://developers.cloudflare.com/pages/
- **Next.js**: https://nextjs.org/docs
- **Supabase**: https://supabase.com/docs

## Next Steps

1. ✅ Configure environment variables in Cloudflare Pages
2. ✅ Deploy the Worker API (see `/worker/README.md`)
3. ✅ Deploy the web app
4. ⚠️ Set up custom domain
5. ⚠️ Enable Web Analytics
6. ⚠️ Configure monitoring and alerts
