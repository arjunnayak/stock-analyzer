'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { signInWithEmail } from '@/lib/supabase/auth'
import { GoogleSignInButton } from '@/components/auth/GoogleSignInButton'
import Link from 'next/link'

export default function SignupPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    const { error } = await signInWithEmail(email)

    if (error) {
      setError(error.message)
      setLoading(false)
    } else {
      setSent(true)
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center space-y-6">
          <div className="space-y-2">
            <h1 className="text-3xl font-bold">Check your email</h1>
            <p className="text-gray-600">
              We sent a magic link to <span className="font-semibold">{email}</span>
            </p>
            <p className="text-sm text-gray-500">
              Click the link in the email to complete your sign up and get started.
            </p>
          </div>

          <div className="pt-4 border-t">
            <button
              onClick={() => {
                setSent(false)
                setEmail('')
              }}
              className="text-sm text-gray-600 hover:text-black"
            >
              Use a different email
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold">Get started</h1>
          <p className="text-gray-600">
            Create your account and start monitoring your stocks
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
              Email address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
              placeholder="you@example.com"
            />
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full px-6 py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Sending link...' : 'Continue with email'}
          </button>
        </form>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">Or continue with</span>
          </div>
        </div>

        <GoogleSignInButton disabled={loading} />

        <div className="text-center">
          <p className="text-sm text-gray-600">
            Already have an account?{' '}
            <Link href="/login" className="font-semibold text-black hover:underline">
              Sign in
            </Link>
          </p>
        </div>

        <div className="text-center pt-4">
          <Link href="/" className="text-sm text-gray-500 hover:text-black">
            ← Back to home
          </Link>
        </div>

        <p className="text-xs text-gray-500 text-center">
          By signing up, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  )
}
