"""
Alert generation for material changes.

Creates structured alerts following the MVP format:
- [TICKER] — [Short headline]
- What changed
- Why it matters
- Before vs now
- What didn't change
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import Json

from src.config import config
from src.signals.state_tracker import StateChange


@dataclass
class Alert:
    """Structured alert following MVP format."""

    ticker: str
    alert_type: str  # 'valuation_regime_change', 'fundamental_inflection', 'trend_break'
    headline: str

    # Required sections per MVP plan
    what_changed: str
    why_it_matters: str
    before_vs_now: str
    what_didnt_change: str

    # Metadata
    timestamp: datetime
    data_snapshot: dict

    def to_dict(self) -> dict:
        """Convert alert to dictionary."""
        return {
            "ticker": self.ticker,
            "alert_type": self.alert_type,
            "headline": self.headline,
            "what_changed": self.what_changed,
            "why_it_matters": self.why_it_matters,
            "before_vs_now": self.before_vs_now,
            "what_didnt_change": self.what_didnt_change,
            "timestamp": self.timestamp.isoformat(),
            "data_snapshot": self.data_snapshot,
        }

    def format_email(self) -> str:
        """Format alert for email delivery."""
        return f"""[{self.ticker}] — {self.headline}

What changed:
{self.what_changed}

Why it matters:
{self.why_it_matters}

Before vs now:
{self.before_vs_now}

What didn't change:
{self.what_didnt_change}

---
Detected: {self.timestamp.strftime('%Y-%m-%d %H:%M')}
"""


class AlertGenerator:
    """Generate structured alerts from state changes."""

    @staticmethod
    def generate_trend_break_alert(
        ticker: str,
        change: StateChange,
        current_price: float,
        sma_200: float,
        previous_price: Optional[float] = None,
    ) -> Alert:
        """
        Generate alert for 200-day MA crossover (Alert Type 3).

        Args:
            ticker: Stock ticker
            change: StateChange object
            current_price: Current closing price
            sma_200: 200-day moving average
            previous_price: Previous closing price

        Returns:
            Structured Alert object
        """
        direction = "above" if change.new_value == "above_sma" else "below"
        sentiment = "Bullish" if direction == "above" else "Bearish"

        headline = f"{sentiment} trend break"

        what_changed = f"• Price crossed {direction} the 200-day moving average (${sma_200:.2f})"

        why_it_matters = (
            "• Major trend shifts can signal the start of new price momentum\n"
            f"• This is the first cross in recent months, suggesting a potential regime change"
        )

        old_direction = "below" if direction == "above" else "above"
        before_vs_now = (
            f"• Then: Trading {old_direction} 200-day MA\n" f"• Now: Trading {direction} 200-day MA at ${current_price:.2f}"
        )

        # What didn't change - add context
        what_didnt_change = (
            f"• Long-term moving average remains at ${sma_200:.2f}\n"
            "• Fundamental business metrics unchanged\n"
            "• This is a technical signal, not a fundamental change"
        )

        return Alert(
            ticker=ticker,
            alert_type="trend_break",
            headline=headline,
            what_changed=what_changed,
            why_it_matters=why_it_matters,
            before_vs_now=before_vs_now,
            what_didnt_change=what_didnt_change,
            timestamp=datetime.now(),
            data_snapshot={
                "current_price": current_price,
                "sma_200": sma_200,
                "previous_price": previous_price,
                "direction": direction,
            },
        )

    @staticmethod
    def generate_valuation_regime_alert(
        ticker: str,
        change: StateChange,
        current_percentile: float,
        current_metric_value: float,
        metric_name: str = "P/E",
    ) -> Alert:
        """
        Generate alert for valuation regime change (Alert Type 1).

        Args:
            ticker: Stock ticker
            change: StateChange object
            current_percentile: Current percentile (0-100)
            current_metric_value: Current valuation metric value
            metric_name: Name of valuation metric (e.g., "P/E", "EV/EBITDA")

        Returns:
            Structured Alert object
        """
        old_regime = change.old_value
        new_regime = change.new_value

        # Generate headline
        if new_regime == "cheap":
            headline = "Entered historically cheap zone"
        elif new_regime == "expensive":
            headline = "Entered historically expensive zone"
        elif old_regime == "cheap":
            headline = "Exited historically cheap zone"
        elif old_regime == "expensive":
            headline = "Exited historically expensive zone"
        else:
            headline = "Valuation regime changed"

        what_changed = (
            f"• {metric_name} moved to {current_percentile:.0f}th percentile of 10-year range\n"
            f"• Current {metric_name}: {current_metric_value:.2f}"
        )

        if new_regime == "cheap":
            why_it_matters = (
                "• Stock is trading at valuations seen only 20% of the time historically\n"
                "• May represent an attractive entry point for value investors\n"
                "• Consider whether business fundamentals justify the discount"
            )
        elif new_regime == "expensive":
            why_it_matters = (
                "• Stock is trading at valuations seen only 20% of the time historically\n"
                "• May indicate elevated expectations or frothy sentiment\n"
                "• Consider whether growth prospects justify the premium"
            )
        else:  # Exiting cheap/expensive
            why_it_matters = (
                f"• Stock has moved out of the {old_regime} zone\n"
                "• Valuation has normalized relative to historical range\n"
                "• Re-evaluate your investment thesis with this new regime"
            )

        before_vs_now = f"• Then: {old_regime.capitalize()} zone\n" f"• Now: {new_regime.capitalize()} zone ({current_percentile:.0f}th percentile)"

        what_didnt_change = (
            "• Underlying business operations continue\n"
            "• This is a relative valuation signal, not absolute quality assessment\n"
            "• Historical ranges are backward-looking"
        )

        return Alert(
            ticker=ticker,
            alert_type="valuation_regime_change",
            headline=headline,
            what_changed=what_changed,
            why_it_matters=why_it_matters,
            before_vs_now=before_vs_now,
            what_didnt_change=what_didnt_change,
            timestamp=datetime.now(),
            data_snapshot={
                "current_percentile": current_percentile,
                "metric_value": current_metric_value,
                "metric_name": metric_name,
                "old_regime": old_regime,
                "new_regime": new_regime,
            },
        )


class AlertRepository:
    """Store and retrieve alerts from database."""

    def __init__(self):
        """Initialize repository with database connection."""
        self.conn = psycopg2.connect(config.database_url)

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def save_alert(self, user_id: str, entity_id: str, alert: Alert) -> str:
        """
        Save alert to database.

        Args:
            user_id: User UUID
            entity_id: Entity UUID
            alert: Alert object

        Returns:
            Alert UUID
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alert_history (
                    user_id, entity_id, alert_type,
                    headline, what_changed, why_it_matters,
                    before_vs_now, what_didnt_change,
                    data_snapshot, sent_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    entity_id,
                    alert.alert_type,
                    alert.headline,
                    alert.what_changed,
                    alert.why_it_matters,
                    alert.before_vs_now,
                    alert.what_didnt_change,
                    Json(alert.data_snapshot),
                    alert.timestamp,
                ),
            )

            alert_id = cur.fetchone()[0]

        self.conn.commit()
        return alert_id

    def get_recent_alerts(self, user_id: str, limit: int = 10) -> list[dict]:
        """
        Get recent alerts for a user.

        Args:
            user_id: User UUID
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    ah.id, ah.alert_type, ah.headline,
                    ah.what_changed, ah.why_it_matters,
                    ah.before_vs_now, ah.what_didnt_change,
                    ah.sent_at, ah.opened_at,
                    e.ticker
                FROM alert_history ah
                JOIN entities e ON ah.entity_id = e.id
                WHERE ah.user_id = %s
                ORDER BY ah.sent_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )

            return [dict(row) for row in cur.fetchall()]


if __name__ == "__main__":
    # Test alert generation
    print("Testing Alert Generation")
    print("=" * 60)

    from src.signals.state_tracker import StateChange

    # Test trend break alert
    change = StateChange(
        ticker="AAPL",
        change_type="trend_position",
        old_value="below_sma",
        new_value="above_sma",
        timestamp=datetime.now(),
        should_alert=True,
        alert_type="trend_break",
    )

    alert = AlertGenerator.generate_trend_break_alert(
        ticker="AAPL", change=change, current_price=185.50, sma_200=175.00, previous_price=172.00
    )

    print("\nGenerated Alert:")
    print("=" * 60)
    print(alert.format_email())

    # Test valuation regime alert
    change2 = StateChange(
        ticker="MSFT",
        change_type="valuation_regime",
        old_value="normal",
        new_value="cheap",
        timestamp=datetime.now(),
        should_alert=True,
        alert_type="valuation_regime_change",
    )

    alert2 = AlertGenerator.generate_valuation_regime_alert(
        ticker="MSFT", change=change2, current_percentile=15.0, current_metric_value=22.5, metric_name="P/E"
    )

    print("\n" + "=" * 60)
    print("\nGenerated Alert:")
    print("=" * 60)
    print(alert2.format_email())
