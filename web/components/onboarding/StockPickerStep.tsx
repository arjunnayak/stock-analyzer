'use client'

import { useState } from 'react'
import StockSearch from '@/components/watchlist/StockSearch'

interface StockPickerStepProps {
  selectedStocks: string[]
  onStocksChange: (stocks: string[]) => void
  onBack: () => void
  onComplete: () => void
}

export default function StockPickerStep({
  selectedStocks,
  onStocksChange,
  onBack,
  onComplete,
}: StockPickerStepProps) {
  const [error, setError] = useState('')

  const handleAddStock = (ticker: string) => {
    if (selectedStocks.includes(ticker)) {
      setError('Stock already added')
      return
    }
    onStocksChange([...selectedStocks, ticker])
    setError('')
  }

  const handleRemoveStock = (ticker: string) => {
    onStocksChange(selectedStocks.filter((t) => t !== ticker))
  }

  const handleComplete = () => {
    if (selectedStocks.length === 0) {
      setError('Please add at least one stock to monitor')
      return
    }
    onComplete()
  }

  // Popular stocks to get started
  const popularStocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX']

  return (
    <div className="space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold">Add stocks to monitor</h1>
        <p className="text-gray-600">
          Choose 5-10 stocks you want to track for material changes
        </p>
      </div>

      {/* Stock search */}
      <div>
        <StockSearch onSelect={handleAddStock} />
        {error && (
          <p className="text-sm text-red-600 mt-2">{error}</p>
        )}
      </div>

      {/* Selected stocks */}
      {selectedStocks.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-700">
            Your watchlist ({selectedStocks.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {selectedStocks.map((ticker) => (
              <div
                key={ticker}
                className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg"
              >
                <span className="font-semibold">{ticker}</span>
                <button
                  onClick={() => handleRemoveStock(ticker)}
                  className="text-gray-500 hover:text-black"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Popular stocks */}
      {selectedStocks.length === 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-700">Popular stocks</h3>
          <div className="flex flex-wrap gap-2">
            {popularStocks.map((ticker) => (
              <button
                key={ticker}
                onClick={() => handleAddStock(ticker)}
                className="px-3 py-2 border border-gray-300 rounded-lg hover:border-black hover:bg-gray-50 transition-colors text-sm font-medium"
              >
                {ticker}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-6">
        <button
          onClick={onBack}
          className="text-sm text-gray-600 hover:text-black"
        >
          ← Back
        </button>
        <button
          onClick={handleComplete}
          disabled={selectedStocks.length === 0}
          className="px-6 py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Start monitoring →
        </button>
      </div>
    </div>
  )
}
