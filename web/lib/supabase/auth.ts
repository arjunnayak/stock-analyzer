import { createClient } from './client'

export interface AuthError {
  message: string
}

export interface AuthResponse {
  error: AuthError | null
}

/**
 * Sign up or sign in with email magic link
 */
export async function signInWithEmail(email: string): Promise<AuthResponse> {
  const supabase = createClient()

  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
    },
  })

  if (error) {
    return { error }
  }

  return { error: null }
}

/**
 * Sign out the current user
 */
export async function signOut(): Promise<AuthResponse> {
  const supabase = createClient()
  const { error } = await supabase.auth.signOut()

  if (error) {
    return { error }
  }

  return { error: null }
}

/**
 * Get the current user
 */
export async function getCurrentUser() {
  const supabase = createClient()
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser()

  if (error) {
    return { user: null, error }
  }

  return { user, error: null }
}

/**
 * Sign in with Google OAuth
 */
export async function signInWithGoogle(): Promise<AuthResponse> {
  const supabase = createClient()

  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
    },
  })

  if (error) {
    return { error }
  }

  return { error: null }
}

/**
 * Check if dev auth bypass is enabled
 * Only returns true when NODE_ENV=development AND NEXT_PUBLIC_ENABLE_DEV_AUTH=true
 */
export function isDevAuthEnabled(): boolean {
  return (
    process.env.NODE_ENV === 'development' &&
    process.env.NEXT_PUBLIC_ENABLE_DEV_AUTH === 'true'
  )
}

/**
 * DEV ONLY: Bypass auth with test credentials
 * Only works when NODE_ENV=development AND NEXT_PUBLIC_ENABLE_DEV_AUTH=true
 */
export async function devBypassSignIn(): Promise<AuthResponse> {
  // Double-check environment
  if (!isDevAuthEnabled()) {
    return { error: { message: 'Dev bypass not available in this environment' } }
  }

  const email = process.env.NEXT_PUBLIC_DEV_EMAIL
  const password = process.env.NEXT_PUBLIC_DEV_PASSWORD

  if (!email || !password) {
    return { error: { message: 'Dev credentials not configured. Set NEXT_PUBLIC_DEV_EMAIL and NEXT_PUBLIC_DEV_PASSWORD in .env.local' } }
  }

  const supabase = createClient()

  const { error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })

  if (error) {
    return { error }
  }

  return { error: null }
}
