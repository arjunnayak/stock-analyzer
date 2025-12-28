'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth/AuthProvider'
import Link from 'next/link'

export default function DashboardPage() {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold">Material Changes</h1>
            <div className="flex items-center gap-6">
              <Link
                href="/dashboard"
                className="text-sm font-medium text-black"
              >
                Dashboard
              </Link>
              <Link
                href="/watchlist"
                className="text-sm font-medium text-gray-600 hover:text-black"
              >
                Watchlist
              </Link>
              <Link
                href="/settings"
                className="text-sm font-medium text-gray-600 hover:text-black"
              >
                Settings
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="space-y-12">
          {/* Welcome */}
          <div className="space-y-4">
            <h2 className="text-3xl font-bold">Welcome back!</h2>
            <p className="text-gray-600">
              Here's what's happening with your watchlist.
            </p>
          </div>

          {/* Status */}
          <div className="bg-gray-50 rounded-lg p-8 text-center space-y-4">
            <div className="text-6xl">✓</div>
            <div className="space-y-2">
              <h3 className="text-xl font-semibold">No material changes today</h3>
              <p className="text-gray-600">Your stocks are stable.</p>
            </div>
            <Link
              href="/watchlist"
              className="inline-block mt-4 px-6 py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
            >
              View Watchlist →
            </Link>
          </div>

          {/* What to expect */}
          <div className="space-y-6">
            <h3 className="text-2xl font-bold">What to expect</h3>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="text-green-600 text-xl">✓</div>
                <div>
                  <h4 className="font-semibold">We monitor your stocks daily</h4>
                  <p className="text-sm text-gray-600">
                    Every evening, we analyze valuation, trends, and fundamentals for each stock in your watchlist
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="text-green-600 text-xl">✓</div>
                <div>
                  <h4 className="font-semibold">You'll get an email when something material changes</h4>
                  <p className="text-sm text-gray-600">
                    No daily summaries, no noise — only alerts when there's a meaningful shift
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="text-green-600 text-xl">✓</div>
                <div>
                  <h4 className="font-semibold">No noise - only what matters</h4>
                  <p className="text-sm text-gray-600">
                    We track changes, not persistence. You'll only hear from us when something actually changed
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Material changes we track */}
          <div className="space-y-6">
            <h3 className="text-2xl font-bold">Material changes we track</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="border border-gray-200 rounded-lg p-6 space-y-2">
                <h4 className="font-semibold">Valuation Regime Shifts</h4>
                <p className="text-sm text-gray-600">
                  Entry or exit from historically cheap/expensive zones
                </p>
              </div>
              <div className="border border-gray-200 rounded-lg p-6 space-y-2">
                <h4 className="font-semibold">Trend Breaks</h4>
                <p className="text-sm text-gray-600">
                  Crosses above or below 200-day moving average
                </p>
              </div>
              <div className="border border-gray-200 rounded-lg p-6 space-y-2">
                <h4 className="font-semibold">Fundamental Inflections</h4>
                <p className="text-sm text-gray-600">
                  EPS estimate direction changes (positive → negative, etc.)
                </p>
              </div>
            </div>
          </div>

          {/* Recent alerts (placeholder) */}
          <div className="space-y-4">
            <h3 className="text-2xl font-bold">Recent alerts</h3>
            <div className="text-center py-12 text-gray-500">
              No alerts yet. We'll notify you when something material changes.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
