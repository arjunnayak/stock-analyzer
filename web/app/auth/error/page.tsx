'use client'

import Link from 'next/link'

export default function AuthErrorPage() {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="text-6xl">!</div>
        <div className="space-y-2">
          <h1 className="text-3xl font-bold">Authentication Error</h1>
          <p className="text-gray-600">
            There was a problem signing you in. This could be due to:
          </p>
          <ul className="text-sm text-gray-600 text-left list-disc list-inside space-y-1 mt-4">
            <li>Expired or invalid authentication link</li>
            <li>Authorization was cancelled</li>
            <li>Network connection issue</li>
          </ul>
        </div>
        <Link
          href="/login"
          className="inline-block px-6 py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
        >
          Try Again
        </Link>
      </div>
    </div>
  )
}
