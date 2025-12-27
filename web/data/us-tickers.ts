export interface Ticker {
  symbol: string
  name: string
  exchange: string
}

// Top ~100 US stocks by market cap for MVP
// This can be expanded to full list later
export const US_TICKERS: Ticker[] = [
  { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" },
  { symbol: "MSFT", name: "Microsoft Corporation", exchange: "NASDAQ" },
  { symbol: "GOOGL", name: "Alphabet Inc. Class A", exchange: "NASDAQ" },
  { symbol: "GOOG", name: "Alphabet Inc. Class C", exchange: "NASDAQ" },
  { symbol: "AMZN", name: "Amazon.com Inc.", exchange: "NASDAQ" },
  { symbol: "NVDA", name: "NVIDIA Corporation", exchange: "NASDAQ" },
  { symbol: "META", name: "Meta Platforms Inc.", exchange: "NASDAQ" },
  { symbol: "TSLA", name: "Tesla, Inc.", exchange: "NASDAQ" },
  { symbol: "BRK.B", name: "Berkshire Hathaway Inc. Class B", exchange: "NYSE" },
  { symbol: "TSM", name: "Taiwan Semiconductor Manufacturing", exchange: "NYSE" },
  { symbol: "V", name: "Visa Inc.", exchange: "NYSE" },
  { symbol: "JPM", name: "JPMorgan Chase & Co.", exchange: "NYSE" },
  { symbol: "UNH", name: "UnitedHealth Group Incorporated", exchange: "NYSE" },
  { symbol: "MA", name: "Mastercard Incorporated", exchange: "NYSE" },
  { symbol: "JNJ", name: "Johnson & Johnson", exchange: "NYSE" },
  { symbol: "WMT", name: "Walmart Inc.", exchange: "NYSE" },
  { symbol: "XOM", name: "Exxon Mobil Corporation", exchange: "NYSE" },
  { symbol: "PG", name: "Procter & Gamble Company", exchange: "NYSE" },
  { symbol: "HD", name: "Home Depot Inc.", exchange: "NYSE" },
  { symbol: "CVX", name: "Chevron Corporation", exchange: "NYSE" },
  { symbol: "ABBV", name: "AbbVie Inc.", exchange: "NYSE" },
  { symbol: "BAC", name: "Bank of America Corporation", exchange: "NYSE" },
  { symbol: "MRK", name: "Merck & Co., Inc.", exchange: "NYSE" },
  { symbol: "KO", name: "Coca-Cola Company", exchange: "NYSE" },
  { symbol: "COST", name: "Costco Wholesale Corporation", exchange: "NASDAQ" },
  { symbol: "PEP", name: "PepsiCo, Inc.", exchange: "NASDAQ" },
  { symbol: "AVGO", name: "Broadcom Inc.", exchange: "NASDAQ" },
  { symbol: "TMO", name: "Thermo Fisher Scientific Inc.", exchange: "NYSE" },
  { symbol: "MCD", name: "McDonald's Corporation", exchange: "NYSE" },
  { symbol: "CSCO", name: "Cisco Systems, Inc.", exchange: "NASDAQ" },
  { symbol: "ABT", name: "Abbott Laboratories", exchange: "NYSE" },
  { symbol: "CRM", name: "Salesforce, Inc.", exchange: "NYSE" },
  { symbol: "ACN", name: "Accenture plc", exchange: "NYSE" },
  { symbol: "LIN", name: "Linde plc", exchange: "NYSE" },
  { symbol: "NFLX", name: "Netflix, Inc.", exchange: "NASDAQ" },
  { symbol: "ADBE", name: "Adobe Inc.", exchange: "NASDAQ" },
  { symbol: "DHR", name: "Danaher Corporation", exchange: "NYSE" },
  { symbol: "VZ", name: "Verizon Communications Inc.", exchange: "NYSE" },
  { symbol: "NKE", name: "NIKE, Inc.", exchange: "NYSE" },
  { symbol: "TXN", name: "Texas Instruments Incorporated", exchange: "NASDAQ" },
  { symbol: "ORCL", name: "Oracle Corporation", exchange: "NYSE" },
  { symbol: "WFC", name: "Wells Fargo & Company", exchange: "NYSE" },
  { symbol: "INTC", name: "Intel Corporation", exchange: "NASDAQ" },
  { symbol: "BMY", name: "Bristol-Myers Squibb Company", exchange: "NYSE" },
  { symbol: "UPS", name: "United Parcel Service, Inc.", exchange: "NYSE" },
  { symbol: "PM", name: "Philip Morris International Inc.", exchange: "NYSE" },
  { symbol: "RTX", name: "Raytheon Technologies Corporation", exchange: "NYSE" },
  { symbol: "HON", name: "Honeywell International Inc.", exchange: "NASDAQ" },
  { symbol: "QCOM", name: "QUALCOMM Incorporated", exchange: "NASDAQ" },
  { symbol: "IBM", name: "International Business Machines", exchange: "NYSE" },
  { symbol: "UNP", name: "Union Pacific Corporation", exchange: "NYSE" },
  { symbol: "AMD", name: "Advanced Micro Devices, Inc.", exchange: "NASDAQ" },
  { symbol: "GE", name: "General Electric Company", exchange: "NYSE" },
  { symbol: "MS", name: "Morgan Stanley", exchange: "NYSE" },
  { symbol: "CAT", name: "Caterpillar Inc.", exchange: "NYSE" },
  { symbol: "CVS", name: "CVS Health Corporation", exchange: "NYSE" },
  { symbol: "AMGN", name: "Amgen Inc.", exchange: "NASDAQ" },
  { symbol: "BA", name: "Boeing Company", exchange: "NYSE" },
  { symbol: "GS", name: "Goldman Sachs Group, Inc.", exchange: "NYSE" },
  { symbol: "SBUX", name: "Starbucks Corporation", exchange: "NASDAQ" },
  { symbol: "MDT", name: "Medtronic plc", exchange: "NYSE" },
  { symbol: "AXP", name: "American Express Company", exchange: "NYSE" },
  { symbol: "BLK", name: "BlackRock, Inc.", exchange: "NYSE" },
  { symbol: "T", name: "AT&T Inc.", exchange: "NYSE" },
  { symbol: "ISRG", name: "Intuitive Surgical, Inc.", exchange: "NASDAQ" },
  { symbol: "LOW", name: "Lowe's Companies, Inc.", exchange: "NYSE" },
  { symbol: "DE", name: "Deere & Company", exchange: "NYSE" },
  { symbol: "GILD", name: "Gilead Sciences, Inc.", exchange: "NASDAQ" },
  { symbol: "LMT", name: "Lockheed Martin Corporation", exchange: "NYSE" },
  { symbol: "AMAT", name: "Applied Materials, Inc.", exchange: "NASDAQ" },
  { symbol: "SPGI", name: "S&P Global Inc.", exchange: "NYSE" },
  { symbol: "TJX", name: "TJX Companies, Inc.", exchange: "NYSE" },
  { symbol: "SYK", name: "Stryker Corporation", exchange: "NYSE" },
  { symbol: "BKNG", name: "Booking Holdings Inc.", exchange: "NASDAQ" },
  { symbol: "MMC", name: "Marsh & McLennan Companies", exchange: "NYSE" },
  { symbol: "SCHW", name: "Charles Schwab Corporation", exchange: "NYSE" },
  { symbol: "PLD", name: "Prologis, Inc.", exchange: "NYSE" },
  { symbol: "ZTS", name: "Zoetis Inc.", exchange: "NYSE" },
  { symbol: "TMUS", name: "T-Mobile US, Inc.", exchange: "NASDAQ" },
  { symbol: "CI", name: "Cigna Corporation", exchange: "NYSE" },
  { symbol: "MO", name: "Altria Group, Inc.", exchange: "NYSE" },
  { symbol: "INTU", name: "Intuit Inc.", exchange: "NASDAQ" },
  { symbol: "DUK", name: "Duke Energy Corporation", exchange: "NYSE" },
  { symbol: "SO", name: "Southern Company", exchange: "NYSE" },
  { symbol: "C", name: "Citigroup Inc.", exchange: "NYSE" },
  { symbol: "NOW", name: "ServiceNow, Inc.", exchange: "NYSE" },
  { symbol: "BDX", name: "Becton, Dickinson and Company", exchange: "NYSE" },
  { symbol: "PNC", name: "PNC Financial Services Group", exchange: "NYSE" },
  { symbol: "USB", name: "U.S. Bancorp", exchange: "NYSE" },
  { symbol: "COP", name: "ConocoPhillips", exchange: "NYSE" },
  { symbol: "AMT", name: "American Tower Corporation", exchange: "NYSE" },
  { symbol: "MDLZ", name: "Mondelez International, Inc.", exchange: "NASDAQ" },
  { symbol: "REGN", name: "Regeneron Pharmaceuticals", exchange: "NASDAQ" },
  { symbol: "CB", name: "Chubb Limited", exchange: "NYSE" },
  { symbol: "SLB", name: "Schlumberger Limited", exchange: "NYSE" },
  { symbol: "BSX", name: "Boston Scientific Corporation", exchange: "NYSE" },
  { symbol: "ADP", name: "Automatic Data Processing", exchange: "NASDAQ" },
  { symbol: "VRTX", name: "Vertex Pharmaceuticals", exchange: "NASDAQ" },
]

/**
 * Search tickers by symbol or name
 */
export function searchTickers(query: string, limit = 10): Ticker[] {
  if (!query) return []

  const q = query.toUpperCase()
  return US_TICKERS
    .filter(t =>
      t.symbol.startsWith(q) ||
      t.name.toUpperCase().includes(q)
    )
    .slice(0, limit)
}

/**
 * Get ticker by symbol
 */
export function getTickerBySymbol(symbol: string): Ticker | undefined {
  return US_TICKERS.find(t => t.symbol === symbol.toUpperCase())
}
