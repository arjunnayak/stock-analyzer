'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth/AuthProvider'
import { signOut } from '@/lib/supabase/auth'
import Link from 'next/link'

export default function SettingsPage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [investingStyle, setInvestingStyle] = useState<'value' | 'growth' | 'blend'>('blend')
  const [alertsEnabled, setAlertsEnabled] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  const handleSave = async () => {
    setSaving(true)
    setMessage('')

    // TODO: Call API to update settings

    setTimeout(() => {
      setSaving(false)
      setMessage('Settings saved successfully')
      setTimeout(() => setMessage(''), 3000)
    }, 1000)
  }

  const handleSignOut = async () => {
    await signOut()
    router.push('/')
  }

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
                className="text-sm font-medium text-gray-600 hover:text-black"
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
                className="text-sm font-medium text-black"
              >
                Settings
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <div className="max-w-2xl mx-auto px-4 py-12">
        <div className="space-y-8">
          <div>
            <h2 className="text-3xl font-bold">Settings</h2>
          </div>

          {/* Account */}
          <div className="space-y-4">
            <h3 className="text-xl font-semibold">Account</h3>
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="text-sm text-gray-600">Email</div>
              <div className="font-medium">{user.email}</div>
            </div>
          </div>

          {/* Preferences */}
          <div className="space-y-4">
            <h3 className="text-xl font-semibold">Preferences</h3>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                Investing Style
              </label>
              <select
                value={investingStyle}
                onChange={(e) => setInvestingStyle(e.target.value as any)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
              >
                <option value="value">Value</option>
                <option value="growth">Growth</option>
                <option value="blend">Blend</option>
              </select>
              <p className="text-sm text-gray-600">
                This helps us customize alerts for your investment approach
              </p>
            </div>

            <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
              <div>
                <div className="font-medium">Email Alerts</div>
                <div className="text-sm text-gray-600">
                  Receive email notifications for material changes
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={alertsEnabled}
                  onChange={(e) => setAlertsEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-black/10 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-black"></div>
              </label>
            </div>

            {message && (
              <div className="text-sm text-green-600 bg-green-50 p-3 rounded-lg">
                {message}
              </div>
            )}

            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full px-6 py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>

          {/* Sign out */}
          <div className="pt-8 border-t border-gray-200">
            <button
              onClick={handleSignOut}
              className="text-sm text-red-600 hover:text-red-800"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
