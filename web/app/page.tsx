'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

export default function Home() {
  const [email, setEmail] = useState('')
  const router = useRouter()

  const handleGetStarted = () => {
    if (email) {
      router.push(`/signup?email=${encodeURIComponent(email)}`)
    } else {
      router.push('/signup')
    }
  }

  return (
    <main className="min-h-screen bg-white">
      <div className="max-w-4xl mx-auto px-4 py-20">
        <div className="text-center space-y-8">
          {/* Hero */}
          <div className="space-y-4">
            <h1 className="text-5xl font-bold tracking-tight text-black">
              Stop Re-Checking the Same Stocks
            </h1>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Get notified only when something materially changes.
            </p>
          </div>

          {/* CTA */}
          <div className="flex justify-center items-center gap-4 pt-4">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              className="px-4 py-3 border border-gray-300 rounded-lg text-base w-80 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
              onKeyDown={(e) => e.key === 'Enter' && handleGetStarted()}
            />
            <button
              onClick={handleGetStarted}
              className="px-6 py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
            >
              Get Started →
            </button>
          </div>

          {/* Features */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-16">
            <div className="space-y-2">
              <h3 className="font-semibold text-lg">Valuation Alerts</h3>
              <p className="text-gray-600 text-sm">
                Know when stocks enter historically cheap or expensive zones
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold text-lg">Trend Breaks</h3>
              <p className="text-gray-600 text-sm">
                Catch major trend shifts without the noise
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold text-lg">Fundamental Changes</h3>
              <p className="text-gray-600 text-sm">
                Early warning on business deterioration or improvement
              </p>
            </div>
          </div>

          {/* How it works */}
          <div className="pt-16 space-y-6">
            <h2 className="text-3xl font-bold">How It Works</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="space-y-2">
                <div className="text-4xl font-bold text-gray-300">1</div>
                <h4 className="font-semibold">Add Your Stocks</h4>
                <p className="text-sm text-gray-600">
                  Choose 5-10 stocks you care about
                </p>
              </div>
              <div className="space-y-2">
                <div className="text-4xl font-bold text-gray-300">2</div>
                <h4 className="font-semibold">We Monitor 24/7</h4>
                <p className="text-sm text-gray-600">
                  Daily analysis of valuation, trends, and fundamentals
                </p>
              </div>
              <div className="space-y-2">
                <div className="text-4xl font-bold text-gray-300">3</div>
                <h4 className="font-semibold">Get Smart Alerts</h4>
                <p className="text-sm text-gray-600">
                  Only when something material changes
                </p>
              </div>
            </div>
          </div>

          {/* Final CTA */}
          <div className="pt-16">
            <Link href="/signup">
              <button className="px-8 py-4 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors text-lg">
                Start monitoring your stocks
              </button>
            </Link>
            <p className="text-sm text-gray-500 mt-2">No credit card required</p>
          </div>
        </div>
      </div>
    </main>
  );
}
