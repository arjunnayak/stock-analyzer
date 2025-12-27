'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth/AuthProvider'
import Link from 'next/link'
import StockSearch from '@/components/watchlist/StockSearch'

interface WatchlistStock {
  ticker: string
  name: string
  valuationState: 'up' | 'down' | 'neutral'
  trendState: 'up' | 'down' | 'neutral'
  lastAlertDate: string | null
}

export default function WatchlistPage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [stocks, setStocks] = useState<WatchlistStock[]>([])
  const [showAddStock, setShowAddStock] = useState(false)

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  // TODO: Fetch watchlist from API
  useEffect(() => {
    if (user) {
      // Placeholder data for now
      setStocks([])
    }
  }, [user])

  const handleAddStock = (ticker: string) => {
    // TODO: Call API to add stock
    console.log('Adding stock:', ticker)
    setShowAddStock(false)
  }

  const handleRemoveStock = (ticker: string) => {
    // TODO: Call API to remove stock
    setStocks(stocks.filter(s => s.ticker !== ticker))
  }

  const getStateIcon = (state: 'up' | 'down' | 'neutral') => {
    if (state === 'up') return <span className="text-green-600">↑</span>
    if (state === 'down') return <span className="text-red-600">↓</span>
    return <span className="text-gray-400">→</span>
  }

  const formatLastAlert = (date: string | null) => {
    if (!date) return 'Never'
    // TODO: Proper date formatting
    return date
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
                className="text-sm font-medium text-black"
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
      <div className="max-w-6xl mx-auto px-4 py-12">
        <div className="space-y-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-3xl font-bold">Your Watchlist</h2>
              <p className="text-gray-600 mt-1">
                {stocks.length} {stocks.length === 1 ? 'stock' : 'stocks'} monitored
              </p>
            </div>
            <button
              onClick={() => setShowAddStock(!showAddStock)}
              className="px-6 py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
            >
              + Add Stock
            </button>
          </div>

          {/* Add stock search */}
          {showAddStock && (
            <div className="bg-gray-50 rounded-lg p-6 space-y-4">
              <h3 className="font-semibold">Add a stock to your watchlist</h3>
              <StockSearch onSelect={handleAddStock} />
              <button
                onClick={() => setShowAddStock(false)}
                className="text-sm text-gray-600 hover:text-black"
              >
                Cancel
              </button>
            </div>
          )}

          {/* Watchlist table */}
          {stocks.length === 0 ? (
            <div className="text-center py-20 space-y-4">
              <p className="text-gray-600">Your watchlist is empty</p>
              <button
                onClick={() => setShowAddStock(true)}
                className="inline-block px-6 py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
              >
                Add your first stock
              </button>
            </div>
          ) : (
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">
                      Stock
                    </th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-gray-700">
                      Valuation
                    </th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-gray-700">
                      Trend
                    </th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-gray-700">
                      Last Alert
                    </th>
                    <th className="px-6 py-4 text-right text-sm font-semibold text-gray-700">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {stocks.map((stock) => (
                    <tr key={stock.ticker} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div>
                          <div className="font-semibold">{stock.ticker}</div>
                          <div className="text-sm text-gray-600">{stock.name}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center text-2xl">
                        {getStateIcon(stock.valuationState)}
                      </td>
                      <td className="px-6 py-4 text-center text-2xl">
                        {getStateIcon(stock.trendState)}
                      </td>
                      <td className="px-6 py-4 text-center text-sm text-gray-600">
                        {formatLastAlert(stock.lastAlertDate)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleRemoveStock(stock.ticker)}
                          className="text-sm text-red-600 hover:text-red-800"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
