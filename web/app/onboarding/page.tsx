'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/auth/AuthProvider'
import InvestingStyleStep from '@/components/onboarding/InvestingStyleStep'
import StockPickerStep from '@/components/onboarding/StockPickerStep'

export default function OnboardingPage() {
  const [step, setStep] = useState(1)
  const [investingStyle, setInvestingStyle] = useState<'value' | 'growth' | 'blend' | null>(null)
  const [selectedStocks, setSelectedStocks] = useState<string[]>([])
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.push('/signup')
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

  const handleStyleSelect = (style: 'value' | 'growth' | 'blend' | null) => {
    setInvestingStyle(style)
    setStep(2)
  }

  const handleStocksSelect = (stocks: string[]) => {
    setSelectedStocks(stocks)
  }

  const handleComplete = async () => {
    // TODO: Call API to save investing style and watchlist
    router.push('/dashboard')
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-2xl mx-auto px-4 py-12">
        {/* Progress indicator */}
        <div className="mb-12">
          <div className="flex items-center justify-center space-x-2">
            <div className={`h-2 w-2 rounded-full ${step >= 1 ? 'bg-black' : 'bg-gray-300'}`} />
            <div className={`h-2 w-16 ${step >= 2 ? 'bg-black' : 'bg-gray-300'}`} />
            <div className={`h-2 w-2 rounded-full ${step >= 2 ? 'bg-black' : 'bg-gray-300'}`} />
          </div>
          <p className="text-center text-sm text-gray-500 mt-2">
            Step {step} of 2
          </p>
        </div>

        {/* Steps */}
        {step === 1 && (
          <InvestingStyleStep
            onSelect={handleStyleSelect}
            onBack={() => router.push('/signup')}
          />
        )}

        {step === 2 && (
          <StockPickerStep
            selectedStocks={selectedStocks}
            onStocksChange={handleStocksSelect}
            onBack={() => setStep(1)}
            onComplete={handleComplete}
          />
        )}
      </div>
    </div>
  )
}
