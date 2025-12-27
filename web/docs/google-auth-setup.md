# Google OAuth Setup Guide

## Overview

This guide explains how to enable Google OAuth authentication for the Material Changes app. The UI is already prepared for Google Auth, but it's disabled until we're ready to activate it.

## Steps to Enable Google Auth

### 1. Set up Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Configure OAuth consent screen:
   - Application name: "Material Changes"
   - User support email: your email
   - Developer contact: your email
   - Scopes: email, profile
6. Create OAuth 2.0 Client ID:
   - Application type: Web application
   - Authorized JavaScript origins:
     - `http://localhost:3000` (development)
     - `https://yourdomain.com` (production)
   - Authorized redirect URIs:
     - `http://localhost:3000/auth/callback` (development)
     - `https://yourdomain.com/auth/callback` (production)

### 2. Configure Supabase

1. Go to your Supabase project dashboard
2. Navigate to Authentication → Providers
3. Enable Google provider
4. Add your Google OAuth credentials:
   - Client ID: from Google Cloud Console
   - Client Secret: from Google Cloud Console
5. Save changes

### 3. Update Environment Variables

Add to `.env.local`:

```bash
# These are already configured through Supabase
# NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY handle OAuth
```

### 4. Enable Google Sign-In Button (when ready)

The Google auth function is already implemented in `/lib/supabase/auth.ts`:

```typescript
export async function signInWithGoogle(): Promise<AuthResponse> {
  const supabase = createClient()
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
    },
  })
  return { error: error || null }
}
```

To add the button to the UI, update `/app/login/page.tsx` and `/app/signup/page.tsx`:

```typescript
import { signInWithGoogle } from '@/lib/supabase/auth'

// Add this button to the form:
<button
  onClick={async () => {
    const { error } = await signInWithGoogle()
    if (error) {
      setError(error.message)
    }
  }}
  className="w-full px-6 py-3 border border-gray-300 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
>
  <svg className="w-5 h-5" viewBox="0 0 24 24">
    {/* Google icon SVG */}
  </svg>
  Continue with Google
</button>
```

## Testing

1. Start the dev server: `npm run dev`
2. Click "Continue with Google"
3. Complete Google OAuth flow
4. Should redirect to `/auth/callback` then to `/onboarding` or `/dashboard`

## Security Considerations

- Keep Google OAuth credentials secret
- Use environment variables (never commit to git)
- Configure authorized domains carefully
- Enable HTTPS in production
- Review OAuth scopes (only request what you need)

## Troubleshooting

**Error: "redirect_uri_mismatch"**
- Check that your redirect URI in Google Cloud Console matches exactly
- Include both http://localhost:3000 (dev) and https://yourdomain.com (prod)

**Error: "access_denied"**
- User cancelled the OAuth flow
- OAuth consent screen not configured properly

**Error: "invalid_client"**
- Client ID or Secret is incorrect in Supabase
- Double-check credentials in Google Cloud Console

## Cost Considerations

- Google OAuth is free for most use cases
- Check Google Cloud Console quotas
- Monitor OAuth requests in Supabase dashboard

---

**Note:** Google Auth is prepared but NOT enabled by default. Only enable after:
1. MVP validation succeeds
2. User demand for social login
3. Proper security review completed
