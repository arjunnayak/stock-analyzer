export interface Database {
  public: {
    Tables: {
      users: {
        Row: {
          id: string
          auth_id: string | null
          email: string
          created_at: string
          updated_at: string
          investing_style: 'value' | 'growth' | 'blend' | null
          alerts_enabled: boolean
        }
        Insert: {
          id?: string
          auth_id?: string | null
          email: string
          created_at?: string
          updated_at?: string
          investing_style?: 'value' | 'growth' | 'blend' | null
          alerts_enabled?: boolean
        }
        Update: {
          id?: string
          auth_id?: string | null
          email?: string
          created_at?: string
          updated_at?: string
          investing_style?: 'value' | 'growth' | 'blend' | null
          alerts_enabled?: boolean
        }
      }
      entities: {
        Row: {
          id: string
          ticker: string
          name: string | null
          sector: string | null
          has_price_data: boolean
          has_fundamental_data: boolean
          price_data_min_date: string | null
          price_data_max_date: string | null
          fundamental_data_min_date: string | null
          fundamental_data_max_date: string | null
          created_at: string
          updated_at: string
          last_data_update: string | null
        }
      }
      watchlists: {
        Row: {
          id: string
          user_id: string
          entity_id: string
          added_at: string
          alerts_enabled: boolean
        }
        Insert: {
          id?: string
          user_id: string
          entity_id: string
          added_at?: string
          alerts_enabled?: boolean
        }
        Update: {
          id?: string
          user_id?: string
          entity_id?: string
          added_at?: string
          alerts_enabled?: boolean
        }
      }
      user_entity_settings: {
        Row: {
          id: string
          user_id: string
          entity_id: string
          last_valuation_regime: string | null
          last_valuation_percentile: number | null
          last_eps_direction: string | null
          last_eps_value: number | null
          last_trend_position: string | null
          last_price_close: number | null
          last_evaluated_at: string | null
          created_at: string
          updated_at: string
        }
      }
      alert_history: {
        Row: {
          id: string
          user_id: string
          entity_id: string
          alert_type: 'valuation_regime_change' | 'fundamental_inflection' | 'trend_break'
          headline: string
          what_changed: string | null
          why_it_matters: string | null
          before_vs_now: string | null
          what_didnt_change: string | null
          sent_at: string
          opened_at: string | null
          data_snapshot: any
        }
      }
    }
  }
}
