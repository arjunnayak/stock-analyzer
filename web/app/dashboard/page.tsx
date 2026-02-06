'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth/AuthProvider'
import Link from 'next/link'
import { dashboardApi } from '@/lib/api/client'
import { PriceChart, ValuationChart } from '@/components/dashboard/Charts'

interface Ticker {
  ticker: string
  sector: string | null
  close: number | null
  ema_200: number | null
  ema_50: number | null
  ev_ebit: number | null
  triggers: Array<{
    id: string
    name: string
    strength: number
  }>
}

interface OverviewData {
  updated_at: string
  tickers: Ticker[]
}

interface HistoryData {
  ticker: string
  updated_at: string
  history: Array<{
    date: string
    close: number | null
    ema_200: number | null
    ema_50: number | null
    ev_ebit: number | null
  }>
}

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const [overviewData, setOverviewData] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)
  const [historyData, setHistoryData] = useState<HistoryData | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  useEffect(() => {
    if (!user) return

    async function fetchOverview() {
      setLoading(true)
      setError(null)

      const result = await dashboardApi.getOverview()

      if (result.error) {
        setError(result.error)
      } else if (result.data) {
        setOverviewData(result.data)
      }

      setLoading(false)
    }

    fetchOverview()
  }, [user])

  useEffect(() => {
    if (!selectedTicker) {
      setHistoryData(null)
      return
    }

    async function fetchHistory() {
      setHistoryLoading(true)

      const result = await dashboardApi.getTickerHistory(selectedTicker!)

      if (result.data) {
        setHistoryData(result.data)
      }

      setHistoryLoading(false)
    }

    fetchHistory()
  }, [selectedTicker])

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  // Sort tickers: those with triggers first, then alphabetically
  const sortedTickers = overviewData?.tickers.slice().sort((a, b) => {
    const aHasTriggers = a.triggers.length > 0
    const bHasTriggers = b.triggers.length > 0

    if (aHasTriggers && !bHasTriggers) return -1
    if (!aHasTriggers && bHasTriggers) return 1

    return a.ticker.localeCompare(b.ticker)
  }) || []

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
      <div className="max-w-6xl mx-auto px-4 py-8">
        {error && (
          <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
            Error loading dashboard: {error}
          </div>
        )}

        {!selectedTicker && (
          <>
            {/* Overview Header */}
            <div className="mb-8">
              <h2 className="text-3xl font-bold mb-2">Dashboard</h2>
              {overviewData && (
                <p className="text-gray-600">
                  Updated: {new Date(overviewData.updated_at).toLocaleDateString()}
                </p>
              )}
            </div>

            {/* Ticker Cards Grid */}
            {sortedTickers.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                No data available. Add stocks to your watchlist to see them here.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {sortedTickers.map((ticker) => (
                  <TickerCard
                    key={ticker.ticker}
                    ticker={ticker}
                    onClick={() => setSelectedTicker(ticker.ticker)}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {selectedTicker && (
          <>
            {/* Detail View */}
            <div className="mb-8">
              <button
                onClick={() => setSelectedTicker(null)}
                className="text-blue-600 hover:text-blue-800 mb-4 flex items-center gap-2"
              >
                <span>←</span> Back to overview
              </button>

              <h2 className="text-3xl font-bold">{selectedTicker}</h2>
              {historyData && (
                <p className="text-gray-600 mt-1">
                  Updated: {new Date(historyData.updated_at).toLocaleDateString()}
                </p>
              )}
            </div>

            {historyLoading ? (
              <div className="text-center py-12 text-gray-600">
                Loading chart data...
              </div>
            ) : historyData ? (
              <>
                {/* Current Values Summary */}
                <CurrentValuesSummary
                  ticker={sortedTickers.find(t => t.ticker === selectedTicker)!}
                />

                {/* Charts */}
                <div className="space-y-8 mt-8">
                  {/* Price Chart */}
                  <div>
                    <h3 className="text-xl font-semibold mb-4">Price & Moving Averages</h3>
                    <div className="border border-gray-200 rounded-lg p-4">
                      <PriceChart
                        data={historyData.history.slice(-252)} // Last year (252 trading days)
                        height={400}
                      />
                    </div>
                  </div>

                  {/* Valuation Chart */}
                  {historyData.history.some(d => d.ev_ebit != null) && (
                    <div>
                      <h3 className="text-xl font-semibold mb-4">Valuation (EV/EBIT)</h3>
                      <div className="border border-gray-200 rounded-lg p-4">
                        <ValuationChart
                          data={historyData.history}
                          height={300}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-gray-500">
                No historical data available.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function TickerCard({ ticker, onClick }: { ticker: Ticker; onClick: () => void }) {
  const hasTriggers = ticker.triggers.length > 0
  const borderClass = hasTriggers ? 'border-blue-500' : 'border-gray-200'

  return (
    <div
      onClick={onClick}
      className={`border-2 ${borderClass} rounded-lg p-4 cursor-pointer hover:shadow-lg transition-shadow`}
    >
      <div className="space-y-3">
        {/* Ticker & Sector */}
        <div>
          <h3 className="text-2xl font-bold">{ticker.ticker}</h3>
          {ticker.sector && (
            <p className="text-sm text-gray-500">{ticker.sector}</p>
          )}
        </div>

        {/* Metrics */}
        <div className="space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Close:</span>
            <span className="font-medium">
              {ticker.close != null ? `$${ticker.close.toFixed(2)}` : 'N/A'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">EMA 200:</span>
            <span className="font-medium">
              {ticker.ema_200 != null ? `$${ticker.ema_200.toFixed(2)}` : 'N/A'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">EMA 50:</span>
            <span className="font-medium">
              {ticker.ema_50 != null ? `$${ticker.ema_50.toFixed(2)}` : 'N/A'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">EV/EBIT:</span>
            <span className="font-medium">
              {ticker.ev_ebit != null ? ticker.ev_ebit.toFixed(1) : 'N/A'}
            </span>
          </div>
        </div>

        {/* Triggers */}
        {hasTriggers && (
          <div className="pt-2 border-t border-gray-200">
            <div className="flex flex-wrap gap-2">
              {ticker.triggers.map((trigger) => (
                <span
                  key={trigger.id}
                  className="inline-block px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded"
                >
                  {trigger.name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function CurrentValuesSummary({ ticker }: { ticker: Ticker }) {
  return (
    <div className="bg-gray-50 rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">Current Values</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <p className="text-sm text-gray-600">Close Price</p>
          <p className="text-xl font-bold">
            {ticker.close != null ? `$${ticker.close.toFixed(2)}` : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-sm text-gray-600">EMA 200</p>
          <p className="text-xl font-bold">
            {ticker.ema_200 != null ? `$${ticker.ema_200.toFixed(2)}` : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-sm text-gray-600">EMA 50</p>
          <p className="text-xl font-bold">
            {ticker.ema_50 != null ? `$${ticker.ema_50.toFixed(2)}` : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-sm text-gray-600">EV/EBIT</p>
          <p className="text-xl font-bold">
            {ticker.ev_ebit != null ? ticker.ev_ebit.toFixed(1) : 'N/A'}
          </p>
        </div>
      </div>
    </div>
  )
}
