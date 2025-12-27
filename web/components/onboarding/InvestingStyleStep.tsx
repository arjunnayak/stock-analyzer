'use client'

interface InvestingStyleStepProps {
  onSelect: (style: 'value' | 'growth' | 'blend' | null) => void
  onBack: () => void
}

export default function InvestingStyleStep({ onSelect, onBack }: InvestingStyleStepProps) {
  return (
    <div className="space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold">Choose your investing style</h1>
        <p className="text-gray-600">
          This helps us customize alerts for you (you can change this later)
        </p>
      </div>

      <div className="space-y-4">
        <button
          onClick={() => onSelect('value')}
          className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-black transition-colors text-left group"
        >
          <h3 className="text-xl font-semibold mb-2 group-hover:text-black">Value</h3>
          <p className="text-gray-600 text-sm">
            Focus on undervalued companies with strong fundamentals trading below intrinsic value
          </p>
        </button>

        <button
          onClick={() => onSelect('growth')}
          className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-black transition-colors text-left group"
        >
          <h3 className="text-xl font-semibold mb-2 group-hover:text-black">Growth</h3>
          <p className="text-gray-600 text-sm">
            Prioritize companies with high revenue/earnings growth potential
          </p>
        </button>

        <button
          onClick={() => onSelect('blend')}
          className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-black transition-colors text-left group"
        >
          <h3 className="text-xl font-semibold mb-2 group-hover:text-black">Blend</h3>
          <p className="text-gray-600 text-sm">
            Mix of both value and growth considerations
          </p>
        </button>
      </div>

      <div className="text-center pt-4">
        <button
          onClick={() => onSelect(null)}
          className="text-sm text-gray-500 hover:text-black"
        >
          Skip for now →
        </button>
      </div>
    </div>
  )
}
