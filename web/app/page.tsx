'use client'

import { useState } from 'react'

export default function Home() {
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (isPaid = false) => {
    if (!email) {
      setError('Please enter your email')
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      const response = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          planInterest: isPaid ? 'paid' : 'free',
          source: 'landing_page'
        })
      })

      const data = await response.json()

      if (response.ok) {
        setSuccess(true)
        setEmail('')
      } else {
        setError(data.error || 'Something went wrong. Please try again.')
      }
    } catch (err) {
      setError('Something went wrong. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-white">
      {/* Hero Section */}
      <section className="max-w-5xl mx-auto px-6 pt-32 pb-24">
        <div className="max-w-3xl">
          <h1 className="text-6xl font-semibold tracking-tight text-black leading-tight mb-6">
            Stop Re-Analyzing Your Stocks
          </h1>
          <p className="text-2xl text-gray-600 leading-relaxed mb-4">
            Get notified only when something actually matters.
          </p>
          <p className="text-lg text-gray-500 leading-relaxed mb-12">
            Smart alerts for long-term investors holding 10–30 stocks — so you don't miss important changes or waste time watching noise.
          </p>

          {/* CTA Buttons */}
          {success ? (
            <div className="p-6 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-green-800 text-lg font-medium">
                ✓ You're on the list! Check your email for next steps.
              </p>
            </div>
          ) : (
            <>
              <div className="flex flex-col sm:flex-row gap-4 mb-2">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    setError('')
                  }}
                  placeholder="Enter your email"
                  className="px-5 py-4 border border-gray-300 rounded-lg text-base w-full sm:w-96 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  disabled={isSubmitting}
                />
                <button
                  onClick={() => handleSubmit()}
                  disabled={isSubmitting}
                  className="px-6 py-4 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-all whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? 'Joining...' : 'Join Early Access'}
                </button>
              </div>
              {error && (
                <p className="text-red-600 text-sm mb-4">{error}</p>
              )}
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span>or</span>
                <button
                  onClick={() => handleSubmit(true)}
                  disabled={isSubmitting}
                  className="underline hover:text-black transition-colors disabled:opacity-50"
                >
                  Reserve Your Spot — $10/month (fully refundable)
                </button>
              </div>
            </>
          )}
        </div>
      </section>

      {/* Social Proof */}
      <section className="max-w-5xl mx-auto px-6 py-16 border-t border-gray-200">
        <div className="max-w-3xl">
          <p className="text-lg text-gray-600 leading-relaxed">
            Built for busy professionals who invest long-term and want clarity — not dashboards.
          </p>
          <p className="text-lg text-gray-500 mt-4">
            No newsletters. No hype. Just actionable signals.
          </p>
        </div>
      </section>

      {/* The Problem */}
      <section className="max-w-5xl mx-auto px-6 py-24">
        <div className="max-w-3xl">
          <h2 className="text-4xl font-semibold text-black mb-8">
            If you invest long-term, you've felt this:
          </h2>
          <ul className="space-y-4 text-lg text-gray-600">
            <li className="flex items-start gap-3">
              <span className="text-gray-400 mt-1">•</span>
              <span>You own great companies… but don't know <em>when</em> to add, trim, or re-evaluate</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-gray-400 mt-1">•</span>
              <span>You re-analyze stocks manually after earnings, price drops, or headlines</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-gray-400 mt-1">•</span>
              <span>You follow too many metrics — most of which don't actually change decisions</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-gray-400 mt-1">•</span>
              <span>You miss important shifts because you weren't looking that day</span>
            </li>
          </ul>
          <div className="mt-12 p-8 bg-gray-50 rounded-lg border border-gray-200">
            <p className="text-xl text-black font-medium">
              Most stock apps give you more data.
            </p>
            <p className="text-xl text-gray-600 mt-2">
              This gives you fewer — better — alerts.
            </p>
          </div>
        </div>
      </section>

      {/* The Promise */}
      <section className="max-w-5xl mx-auto px-6 py-24 border-t border-gray-200">
        <div className="max-w-3xl">
          <h2 className="text-4xl font-semibold text-black mb-8">
            I'll tell you when one of your stocks actually needs attention.
          </h2>
          <p className="text-lg text-gray-600 mb-10">You'll get notified when:</p>
          <div className="space-y-6">
            <div className="flex items-start gap-4">
              <span className="text-2xl">📉</span>
              <div>
                <h3 className="text-lg font-medium text-black mb-1">Valuation</h3>
                <p className="text-gray-600">becomes meaningfully cheap or expensive vs its own history</p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <span className="text-2xl">📊</span>
              <div>
                <h3 className="text-lg font-medium text-black mb-1">Fundamentals</h3>
                <p className="text-gray-600">deteriorate or inflect (growth, margins, cash flow)</p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <span className="text-2xl">📈</span>
              <div>
                <h3 className="text-lg font-medium text-black mb-1">Long-term trends</h3>
                <p className="text-gray-600">confirm or break (not day-trading noise)</p>
              </div>
            </div>
          </div>
          <div className="mt-12 space-y-2 text-lg text-gray-600">
            <p>No constant pings.</p>
            <p>No watching charts every day.</p>
            <p className="font-medium text-black">Just alerts that justify taking action.</p>
          </div>
        </div>
      </section>

      {/* Who This Is For */}
      <section className="max-w-5xl mx-auto px-6 py-24 border-t border-gray-200">
        <div className="max-w-3xl">
          <h2 className="text-4xl font-semibold text-black mb-12">
            Who this is for
          </h2>

          <div className="mb-12">
            <h3 className="text-xl font-medium text-black mb-6">This is for you if:</h3>
            <ul className="space-y-3 text-lg text-gray-600">
              <li className="flex items-start gap-3">
                <span className="text-green-600">✓</span>
                <span>You hold <strong>10–30 long-term positions</strong></span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-green-600">✓</span>
                <span>You think in <strong>months / years</strong>, not minutes</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-green-600">✓</span>
                <span>You want to <strong>add on weakness</strong> and <strong>trim on excess</strong></span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-green-600">✓</span>
                <span>You're tired of re-researching the same stocks</span>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-xl font-medium text-black mb-6">This is <em>not</em> for:</h3>
            <ul className="space-y-3 text-lg text-gray-600">
              <li className="flex items-start gap-3">
                <span className="text-gray-400">×</span>
                <span>Day traders</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-gray-400">×</span>
                <span>Meme stock chasers</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-gray-400">×</span>
                <span>People who want "top stock picks"</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="max-w-5xl mx-auto px-6 py-24 border-t border-gray-200">
        <div className="max-w-3xl">
          <h2 className="text-4xl font-semibold text-black mb-4">
            Simple by design
          </h2>
          <div className="space-y-8 mt-12">
            <div className="flex items-start gap-6">
              <span className="text-5xl font-bold text-gray-200">1</span>
              <div className="pt-2">
                <p className="text-lg text-gray-600">You add your stock list</p>
              </div>
            </div>
            <div className="flex items-start gap-6">
              <span className="text-5xl font-bold text-gray-200">2</span>
              <div className="pt-2">
                <p className="text-lg text-gray-600">I monitor valuation, fundamentals, and trend shifts</p>
              </div>
            </div>
            <div className="flex items-start gap-6">
              <span className="text-5xl font-bold text-gray-200">3</span>
              <div className="pt-2">
                <p className="text-lg text-gray-600">You get notified <strong className="text-black">only</strong> when something crosses a meaningful threshold</p>
              </div>
            </div>
          </div>
          <p className="text-lg text-gray-500 mt-12">That's it.</p>
        </div>
      </section>

      {/* Why Different */}
      <section className="max-w-5xl mx-auto px-6 py-24 border-t border-gray-200">
        <div className="max-w-3xl">
          <h2 className="text-4xl font-semibold text-black mb-12">
            Why this is different
          </h2>
          <div className="space-y-8">
            <div>
              <p className="text-lg text-gray-600 mb-3">Most tools ask:</p>
              <blockquote className="text-2xl text-gray-400 italic pl-6 border-l-4 border-gray-200">
                "What's happening in the market?"
              </blockquote>
            </div>
            <div>
              <p className="text-lg text-gray-600 mb-3">This asks:</p>
              <blockquote className="text-2xl text-black font-medium pl-6 border-l-4 border-black">
                "Does this change what I should do with <em>my</em> stocks?"
              </blockquote>
            </div>
            <div className="pt-6">
              <p className="text-lg text-gray-600">Different question.</p>
              <p className="text-lg text-black font-medium">Much better answers.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Early Access CTA */}
      <section className="max-w-5xl mx-auto px-6 py-24 border-t border-gray-200">
        <div className="max-w-3xl">
          <h2 className="text-4xl font-semibold text-black mb-8">
            Get Early Access
          </h2>
          <p className="text-lg text-gray-600 mb-6">
            I'm opening this to a small group first to:
          </p>
          <ul className="space-y-3 text-lg text-gray-600 mb-12">
            <li className="flex items-start gap-3">
              <span className="text-gray-400">•</span>
              <span>Validate which alerts matter most</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-gray-400">•</span>
              <span>Tune thresholds with real investors</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-gray-400">•</span>
              <span>Build this <em>with</em> users, not in isolation</span>
            </li>
          </ul>

{success ? (
            <div className="p-6 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-green-800 text-lg font-medium">
                ✓ You're on the list! Check your email for next steps.
              </p>
            </div>
          ) : (
            <>
              <div className="flex flex-col sm:flex-row gap-4 mb-2">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    setError('')
                  }}
                  placeholder="Enter your email"
                  className="px-5 py-4 border border-gray-300 rounded-lg text-base w-full sm:w-96 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  disabled={isSubmitting}
                />
                <button
                  onClick={() => handleSubmit()}
                  disabled={isSubmitting}
                  className="px-6 py-4 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-all whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? 'Joining...' : 'Join Early Access'}
                </button>
              </div>
              {error && (
                <p className="text-red-600 text-sm mb-4">{error}</p>
              )}
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
                <span>or</span>
                <button
                  onClick={() => handleSubmit(true)}
                  disabled={isSubmitting}
                  className="underline hover:text-black transition-colors disabled:opacity-50"
                >
                  Reserve Your Spot — $10/month (fully refundable)
                </button>
              </div>
              <p className="text-sm text-gray-500 italic">
                Early users help shape the product.
              </p>
            </>
          )}
        </div>
      </section>

      {/* Lead Magnet */}
      <section className="max-w-5xl mx-auto px-6 py-24 border-t border-gray-200 bg-gray-50">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-semibold text-black mb-6">
            Free: The 7 Alerts Long-Term Investors Actually Need
          </h2>
          <p className="text-lg text-gray-600 mb-6">
            A short guide breaking down:
          </p>
          <ul className="space-y-2 text-gray-600 mb-8">
            <li className="flex items-start gap-3">
              <span className="text-gray-400">•</span>
              <span>Which signals are worth paying attention to</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-gray-400">•</span>
              <span>Which alerts to ignore</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-gray-400">•</span>
              <span>How to think about add vs trim decisions</span>
            </li>
          </ul>
          <p className="text-gray-600">
            📥 Get the free guide when you join.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="max-w-5xl mx-auto px-6 py-16 border-t border-gray-200">
        <div className="max-w-3xl">
          <p className="text-gray-600 mb-3">
            Built by an investor who wanted fewer alerts — not more.
          </p>
          <p className="text-gray-500">
            Questions? Reply to the welcome email. I read every one.
          </p>
        </div>
      </footer>
    </main>
  )
}
