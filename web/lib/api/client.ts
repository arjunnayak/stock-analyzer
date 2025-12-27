/**
 * API Client for Material Changes
 *
 * This client calls Cloudflare Python Worker endpoints that use
 * the existing backend logic in src/
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8787'

interface ApiResponse<T> {
  data?: T
  error?: string
}

/**
 * Generic API call helper
 */
async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.text()
      return { error: error || 'API request failed' }
    }

    const data = await response.json()
    return { data }
  } catch (error) {
    return { error: error instanceof Error ? error.message : 'Unknown error' }
  }
}

/**
 * Watchlist API
 */
export const watchlistApi = {
  /**
   * Get user's watchlist with latest states
   */
  async getWatchlist(userId: string) {
    return apiCall<{
      stocks: Array<{
        ticker: string
        name: string
        valuation_state: 'up' | 'down' | 'neutral'
        trend_state: 'up' | 'down' | 'neutral'
        last_alert_date: string | null
      }>
    }>(`/api/watchlist/${userId}`)
  },

  /**
   * Add stock to watchlist
   */
  async addStock(userId: string, ticker: string) {
    return apiCall(`/api/watchlist/${userId}`, {
      method: 'POST',
      body: JSON.stringify({ ticker }),
    })
  },

  /**
   * Remove stock from watchlist
   */
  async removeStock(userId: string, ticker: string) {
    return apiCall(`/api/watchlist/${userId}/${ticker}`, {
      method: 'DELETE',
    })
  },
}

/**
 * User Settings API
 */
export const userApi = {
  /**
   * Get user settings
   */
  async getSettings(userId: string) {
    return apiCall<{
      investing_style: 'value' | 'growth' | 'blend' | null
      alerts_enabled: boolean
    }>(`/api/user/${userId}/settings`)
  },

  /**
   * Update user settings
   */
  async updateSettings(
    userId: string,
    settings: {
      investing_style?: 'value' | 'growth' | 'blend'
      alerts_enabled?: boolean
    }
  ) {
    return apiCall(`/api/user/${userId}/settings`, {
      method: 'PATCH',
      body: JSON.stringify(settings),
    })
  },

  /**
   * Complete onboarding
   */
  async completeOnboarding(
    userId: string,
    data: {
      investing_style: 'value' | 'growth' | 'blend' | null
      tickers: string[]
    }
  ) {
    return apiCall(`/api/user/${userId}/onboarding`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
}

/**
 * Alerts API
 */
export const alertsApi = {
  /**
   * Get user's alert history
   */
  async getAlerts(userId: string, limit = 20) {
    return apiCall<{
      alerts: Array<{
        id: string
        ticker: string
        alert_type: string
        headline: string
        sent_at: string
        opened_at: string | null
      }>
    }>(`/api/alerts/${userId}?limit=${limit}`)
  },

  /**
   * Mark alert as opened
   */
  async markOpened(alertId: string) {
    return apiCall(`/api/alerts/${alertId}/opened`, {
      method: 'POST',
    })
  },
}

/**
 * Entities API (stocks metadata)
 */
export const entitiesApi = {
  /**
   * Search stocks by ticker or name
   */
  async search(query: string, limit = 10) {
    return apiCall<{
      results: Array<{
        ticker: string
        name: string
        sector: string | null
      }>
    }>(`/api/entities/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  },

  /**
   * Get stock details
   */
  async getStock(ticker: string) {
    return apiCall<{
      ticker: string
      name: string
      sector: string | null
      has_price_data: boolean
      has_fundamental_data: boolean
    }>(`/api/entities/${ticker}`)
  },
}
