'use client'

import { useState, useRef, useEffect } from 'react'
import { searchTickers, type Ticker } from '@/data/us-tickers'

interface StockSearchProps {
  onSelect: (ticker: string) => void
  placeholder?: string
}

export default function StockSearch({ onSelect, placeholder = "Search stocks..." }: StockSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Ticker[]>([])
  const [showResults, setShowResults] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (query.length > 0) {
      const searchResults = searchTickers(query, 8)
      setResults(searchResults)
      setShowResults(searchResults.length > 0)
      setSelectedIndex(0)
    } else {
      setResults([])
      setShowResults(false)
    }
  }, [query])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        resultsRef.current &&
        !resultsRef.current.contains(event.target as Node) &&
        !inputRef.current?.contains(event.target as Node)
      ) {
        setShowResults(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (ticker: string) => {
    onSelect(ticker)
    setQuery('')
    setShowResults(false)
    inputRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showResults) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter' && results.length > 0) {
      e.preventDefault()
      handleSelect(results[selectedIndex].symbol)
    } else if (e.key === 'Escape') {
      setShowResults(false)
    }
  }

  return (
    <div className="relative">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => query && setShowResults(true)}
        placeholder={placeholder}
        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
      />

      {showResults && results.length > 0 && (
        <div
          ref={resultsRef}
          className="absolute z-10 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg max-h-80 overflow-y-auto"
        >
          {results.map((ticker, index) => (
            <button
              key={ticker.symbol}
              onClick={() => handleSelect(ticker.symbol)}
              className={`w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-100 last:border-b-0 transition-colors ${
                index === selectedIndex ? 'bg-gray-50' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-black">{ticker.symbol}</div>
                  <div className="text-sm text-gray-600">{ticker.name}</div>
                </div>
                <div className="text-xs text-gray-400">{ticker.exchange}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {query && results.length === 0 && (
        <div className="absolute z-10 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-4">
          <p className="text-sm text-gray-600">No stocks found for "{query}"</p>
        </div>
      )}
    </div>
  )
}
