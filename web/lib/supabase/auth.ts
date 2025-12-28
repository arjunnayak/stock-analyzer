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
 * Sign in with Google OAuth (prepared for future use)
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
