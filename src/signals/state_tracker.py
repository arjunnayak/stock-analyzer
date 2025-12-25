"""
State tracking for material change detection.

Tracks previous signal states and detects meaningful changes
to trigger alerts (not continuous conditions).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from src.config import config


@dataclass
class TickerState:
    """Current state of a ticker for a user."""

    user_id: str
    entity_id: str
    ticker: str

    # Valuation state
    last_valuation_regime: Optional[str] = None  # 'cheap', 'expensive', 'normal'
    last_valuation_percentile: Optional[float] = None

    # Fundamental state
    last_eps_direction: Optional[str] = None  # 'positive', 'negative', 'neutral'
    last_eps_value: Optional[float] = None

    # Technical state
    last_trend_position: Optional[str] = None  # 'above_200dma', 'below_200dma'
    last_price_close: Optional[float] = None

    # Tracking
    last_evaluated_at: Optional[datetime] = None


@dataclass
class StateChange:
    """Represents a detected state change."""

    ticker: str
    change_type: str  # 'valuation_regime', 'eps_direction', 'trend_position'
    old_value: Optional[str]
    new_value: str
    timestamp: datetime
    should_alert: bool = False
    alert_type: Optional[str] = None  # Maps to alert types in MVP plan


class StateTracker:
    """Tracks and detects state changes for tickers."""

    def __init__(self):
        """Initialize state tracker with database connection."""
        self.conn = psycopg2.connect(config.database_url)

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_state(self, user_id: str, entity_id: str, ticker: str) -> TickerState:
        """
        Get current state for a user/ticker pair.

        Args:
            user_id: User UUID
            entity_id: Entity UUID
            ticker: Stock ticker

        Returns:
            TickerState object (may be empty if no previous state)
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    user_id, entity_id,
                    last_valuation_regime, last_valuation_percentile,
                    last_eps_direction, last_eps_value,
                    last_trend_position, last_price_close,
                    last_evaluated_at
                FROM user_entity_settings
                WHERE user_id = %s AND entity_id = %s
                """,
                (user_id, entity_id),
            )

            row = cur.fetchone()

            if row:
                return TickerState(
                    user_id=row["user_id"],
                    entity_id=row["entity_id"],
                    ticker=ticker,
                    last_valuation_regime=row["last_valuation_regime"],
                    last_valuation_percentile=row["last_valuation_percentile"],
                    last_eps_direction=row["last_eps_direction"],
                    last_eps_value=row["last_eps_value"],
                    last_trend_position=row["last_trend_position"],
                    last_price_close=row["last_price_close"],
                    last_evaluated_at=row["last_evaluated_at"],
                )
            else:
                # No previous state - create empty state
                return TickerState(user_id=user_id, entity_id=entity_id, ticker=ticker)

    def update_state(
        self,
        user_id: str,
        entity_id: str,
        valuation_regime: Optional[str] = None,
        valuation_percentile: Optional[float] = None,
        eps_direction: Optional[str] = None,
        eps_value: Optional[float] = None,
        trend_position: Optional[str] = None,
        price_close: Optional[float] = None,
    ) -> None:
        """
        Update state for a user/ticker pair.

        Creates record if doesn't exist, updates if it does.

        Args:
            user_id: User UUID
            entity_id: Entity UUID
            valuation_regime: Current valuation regime
            valuation_percentile: Current valuation percentile
            eps_direction: Current EPS direction
            eps_value: Current EPS value
            trend_position: Current trend position
            price_close: Current closing price
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_entity_settings (
                    user_id, entity_id,
                    last_valuation_regime, last_valuation_percentile,
                    last_eps_direction, last_eps_value,
                    last_trend_position, last_price_close,
                    last_evaluated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, entity_id)
                DO UPDATE SET
                    last_valuation_regime = COALESCE(EXCLUDED.last_valuation_regime, user_entity_settings.last_valuation_regime),
                    last_valuation_percentile = COALESCE(EXCLUDED.last_valuation_percentile, user_entity_settings.last_valuation_percentile),
                    last_eps_direction = COALESCE(EXCLUDED.last_eps_direction, user_entity_settings.last_eps_direction),
                    last_eps_value = COALESCE(EXCLUDED.last_eps_value, user_entity_settings.last_eps_value),
                    last_trend_position = COALESCE(EXCLUDED.last_trend_position, user_entity_settings.last_trend_position),
                    last_price_close = COALESCE(EXCLUDED.last_price_close, user_entity_settings.last_price_close),
                    last_evaluated_at = NOW(),
                    updated_at = NOW()
                """,
                (
                    user_id,
                    entity_id,
                    valuation_regime,
                    valuation_percentile,
                    eps_direction,
                    eps_value,
                    trend_position,
                    price_close,
                ),
            )

        self.conn.commit()

    def detect_trend_change(
        self, previous_state: TickerState, current_trend_position: str, current_price: float
    ) -> Optional[StateChange]:
        """
        Detect if trend position has changed (200-day MA crossover).

        According to MVP plan:
        - Alert Type 3 — Trend Break
        - Price crosses above or below 200DMA
        - Only trigger if first cross in ≥6 months

        Args:
            previous_state: Previous ticker state
            current_trend_position: Current trend position ('above_sma', 'below_sma')
            current_price: Current closing price

        Returns:
            StateChange if material change detected, None otherwise
        """
        # No previous state = first time, don't alert
        if previous_state.last_trend_position is None:
            return None

        # No change = no alert
        if previous_state.last_trend_position == current_trend_position:
            return None

        # Change detected!
        change = StateChange(
            ticker=previous_state.ticker,
            change_type="trend_position",
            old_value=previous_state.last_trend_position,
            new_value=current_trend_position,
            timestamp=datetime.now(),
            should_alert=True,
            alert_type="trend_break",
        )

        return change

    def detect_valuation_regime_change(
        self,
        previous_state: TickerState,
        current_percentile: float,
        cheap_threshold: float = 20.0,
        expensive_threshold: float = 80.0,
    ) -> Optional[StateChange]:
        """
        Detect if valuation regime has changed.

        According to MVP plan:
        - Alert Type 1 — Valuation Regime Change
        - Enters or exits bottom 20% (cheap) or top 20% (expensive)
        - Alert only on regime change, not persistence

        Args:
            previous_state: Previous ticker state
            current_percentile: Current valuation percentile (0-100)
            cheap_threshold: Percentile threshold for "cheap" (default: 20)
            expensive_threshold: Percentile threshold for "expensive" (default: 80)

        Returns:
            StateChange if material change detected, None otherwise
        """

        def classify_regime(percentile: Optional[float]) -> str:
            """Classify percentile into regime."""
            if percentile is None:
                return "unknown"
            if percentile <= cheap_threshold:
                return "cheap"
            elif percentile >= expensive_threshold:
                return "expensive"
            else:
                return "normal"

        current_regime = classify_regime(current_percentile)
        previous_regime = classify_regime(previous_state.last_valuation_percentile)

        # No change = no alert
        if current_regime == previous_regime:
            return None

        # Change detected!
        change = StateChange(
            ticker=previous_state.ticker,
            change_type="valuation_regime",
            old_value=previous_regime,
            new_value=current_regime,
            timestamp=datetime.now(),
            should_alert=True,
            alert_type="valuation_regime_change",
        )

        return change


if __name__ == "__main__":
    # Test state tracker
    print("Testing State Tracker")
    print("=" * 60)

    with StateTracker() as tracker:
        # Get test user and entity from database
        with tracker.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, email FROM users LIMIT 1")
            user = cur.fetchone()

            cur.execute("SELECT id, ticker FROM entities LIMIT 1")
            entity = cur.fetchone()

        if user and entity:
            print(f"Testing with user: {user['email']}, ticker: {entity['ticker']}")

            # Get current state
            state = tracker.get_state(user["id"], entity["id"], entity["ticker"])
            print(f"\nCurrent state:")
            print(f"  Trend position: {state.last_trend_position}")
            print(f"  Last price: {state.last_price_close}")
            print(f"  Last evaluated: {state.last_evaluated_at}")

            # Simulate trend change
            print("\n" + "=" * 60)
            print("Simulating trend change...")

            change = tracker.detect_trend_change(state, "above_sma", 150.0)

            if change:
                print(f"✓ Change detected!")
                print(f"  Type: {change.change_type}")
                print(f"  Old: {change.old_value} → New: {change.new_value}")
                print(f"  Alert type: {change.alert_type}")

                # Update state
                tracker.update_state(
                    user["id"],
                    entity["id"],
                    trend_position="above_sma",
                    price_close=150.0,
                )
                print("✓ State updated")
            else:
                print("No change detected (or no previous state)")

        else:
            print("⚠️  No test data in database. Run migrations first.")
