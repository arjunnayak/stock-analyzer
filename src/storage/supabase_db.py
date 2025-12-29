"""
Supabase database helpers for daily feature pipeline.

Provides typed access to:
- indicator_state (rolling EMA values)
- valuation_stats (historical percentiles)
- fundamentals_latest (latest fundamental data)
- Active ticker queries
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from src.config import get_supabase_client


@dataclass
class IndicatorState:
    """Represents a row in the indicator_state table."""

    ticker: str
    last_price_date: date
    last_close: Optional[float] = None

    # Previous day values (for crossover detection)
    prev_close: Optional[float] = None
    prev_ema_200: Optional[float] = None
    prev_ema_50: Optional[float] = None

    # Current EMA values
    ema_200: Optional[float] = None
    ema_50: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "IndicatorState":
        """Create from database row."""
        return cls(
            ticker=data["ticker"],
            last_price_date=date.fromisoformat(data["last_price_date"])
            if data.get("last_price_date")
            else None,
            last_close=data.get("last_close"),
            prev_close=data.get("prev_close"),
            prev_ema_200=data.get("prev_ema_200"),
            prev_ema_50=data.get("prev_ema_50"),
            ema_200=data.get("ema_200"),
            ema_50=data.get("ema_50"),
        )


@dataclass
class FundamentalsLatest:
    """Represents a row in the fundamentals_latest table."""

    ticker: str
    asof_date: date
    ebitda_ttm: Optional[float] = None
    revenue_ttm: Optional[float] = None
    net_debt: Optional[float] = None
    shares_outstanding: Optional[float] = None
    total_debt: Optional[float] = None
    cash_and_equivalents: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "FundamentalsLatest":
        """Create from database row."""
        return cls(
            ticker=data["ticker"],
            asof_date=date.fromisoformat(data["asof_date"])
            if data.get("asof_date")
            else None,
            ebitda_ttm=data.get("ebitda_ttm"),
            revenue_ttm=data.get("revenue_ttm"),
            net_debt=data.get("net_debt"),
            shares_outstanding=data.get("shares_outstanding"),
            total_debt=data.get("total_debt"),
            cash_and_equivalents=data.get("cash_and_equivalents"),
        )


class SupabaseDB:
    """Database access layer for feature pipeline."""

    def __init__(self, client=None):
        """
        Initialize with optional Supabase client.

        Args:
            client: Supabase client (creates new if not provided)
        """
        self._client = client

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def close(self):
        """Close connection (no-op for Supabase, but maintains interface)."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # =========================================================================
    # Active Tickers
    # =========================================================================

    def get_active_tickers(self) -> list[str]:
        """
        Get all active tickers from watchlist members.

        Returns:
            List of unique ticker symbols
        """
        response = (
            self.client.table("watchlists")
            .select("entity_id, entities(ticker)")
            .eq("alerts_enabled", True)
            .execute()
        )

        tickers = set()
        for row in response.data:
            entity = row.get("entities")
            if entity and entity.get("ticker"):
                tickers.add(entity["ticker"])

        return sorted(list(tickers))

    def get_tickers_with_entity_ids(self) -> dict[str, str]:
        """
        Get mapping of ticker -> entity_id.

        Returns:
            Dict mapping ticker to entity UUID
        """
        response = self.client.table("entities").select("id, ticker").execute()

        return {row["ticker"]: row["id"] for row in response.data}

    # =========================================================================
    # Indicator State
    # =========================================================================

    def fetch_indicator_state(self, tickers: list[str]) -> dict[str, IndicatorState]:
        """
        Fetch indicator state for a list of tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> IndicatorState
        """
        if not tickers:
            return {}

        response = (
            self.client.table("indicator_state")
            .select("*")
            .in_("ticker", tickers)
            .execute()
        )

        return {row["ticker"]: IndicatorState.from_dict(row) for row in response.data}

    def upsert_indicator_state(self, rows: list[dict], batch_size: int = 500) -> int:
        """
        Upsert indicator state rows in batches.

        Args:
            rows: List of dicts with indicator state data
            batch_size: Number of rows per batch

        Returns:
            Total rows upserted
        """
        if not rows:
            return 0

        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            self.client.table("indicator_state").upsert(
                batch, on_conflict="ticker"
            ).execute()
            total += len(batch)

        return total

    # =========================================================================
    # Fundamentals Latest
    # =========================================================================

    def fetch_fundamentals_latest(
        self, tickers: list[str]
    ) -> dict[str, FundamentalsLatest]:
        """
        Fetch latest fundamentals for a list of tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> FundamentalsLatest
        """
        if not tickers:
            return {}

        response = (
            self.client.table("fundamentals_latest")
            .select("*")
            .in_("ticker", tickers)
            .execute()
        )

        return {
            row["ticker"]: FundamentalsLatest.from_dict(row) for row in response.data
        }

    def upsert_fundamentals_latest(
        self, rows: list[dict], batch_size: int = 500
    ) -> int:
        """
        Upsert fundamentals_latest rows in batches.

        Args:
            rows: List of dicts with fundamentals data
            batch_size: Number of rows per batch

        Returns:
            Total rows upserted
        """
        if not rows:
            return 0

        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            self.client.table("fundamentals_latest").upsert(
                batch, on_conflict="ticker"
            ).execute()
            total += len(batch)

        return total

    # =========================================================================
    # Valuation Stats
    # =========================================================================

    def fetch_valuation_stats(
        self, tickers: list[str], metric: str = "ev_ebitda", window_days: int = 1260
    ) -> pd.DataFrame:
        """
        Fetch valuation stats for a list of tickers.

        Args:
            tickers: List of ticker symbols
            metric: Valuation metric (default: 'ev_ebitda')
            window_days: Lookback window (default: 1260 = ~5 years)

        Returns:
            DataFrame with columns: ticker, metric, window_days, p10, p20, p50, p80, p90, etc.
        """
        if not tickers:
            return pd.DataFrame()

        response = (
            self.client.table("valuation_stats")
            .select("*")
            .in_("ticker", tickers)
            .eq("metric", metric)
            .eq("window_days", window_days)
            .execute()
        )

        if not response.data:
            return pd.DataFrame()

        return pd.DataFrame(response.data)

    def upsert_valuation_stats(self, rows: list[dict], batch_size: int = 500) -> int:
        """
        Upsert valuation stats rows in batches.

        Args:
            rows: List of dicts with valuation stats
                  Must include: ticker, metric, window_days, asof_date, count
            batch_size: Number of rows per batch

        Returns:
            Total rows upserted
        """
        if not rows:
            return 0

        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            self.client.table("valuation_stats").upsert(
                batch, on_conflict="ticker,metric,window_days"
            ).execute()
            total += len(batch)

        return total

    # =========================================================================
    # Entity/Ticker Metadata
    # =========================================================================

    def get_entity_metadata(self, tickers: list[str]) -> pd.DataFrame:
        """
        Get entity metadata (sector, industry) for tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            DataFrame with columns: ticker, sector, name
        """
        if not tickers:
            return pd.DataFrame()

        response = (
            self.client.table("entities")
            .select("ticker, name, sector")
            .in_("ticker", tickers)
            .execute()
        )

        if not response.data:
            return pd.DataFrame()

        return pd.DataFrame(response.data)


# Convenience function for quick access
def get_db() -> SupabaseDB:
    """Get a SupabaseDB instance."""
    return SupabaseDB()


if __name__ == "__main__":
    # Test database access
    print("Testing SupabaseDB")
    print("=" * 60)

    db = SupabaseDB()

    # Test active tickers
    print("\n1. Active tickers:")
    tickers = db.get_active_tickers()
    print(f"   Found {len(tickers)} active tickers")
    if tickers:
        print(f"   Sample: {tickers[:5]}")

    # Test indicator state
    if tickers:
        print("\n2. Indicator state:")
        states = db.fetch_indicator_state(tickers[:3])
        print(f"   Found {len(states)} state records")

        # Test upsert
        print("\n3. Testing indicator state upsert:")
        test_rows = [
            {
                "ticker": tickers[0],
                "last_price_date": "2024-12-01",
                "last_close": 100.0,
                "ema_200": 95.0,
                "ema_50": 98.0,
            }
        ]
        count = db.upsert_indicator_state(test_rows)
        print(f"   Upserted {count} rows")

    print("\n✓ All tests completed!")
