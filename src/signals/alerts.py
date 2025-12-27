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
        metric_type: str = "ev_revenue",
        previous_percentile: Optional[float] = None,
        previous_metric_value: Optional[float] = None,
    ) -> Alert:
        """
        Generate alert for valuation regime change (Alert Type 1).

        Follows MVP plan specifications:
        - Explicit EV/Revenue or EV/EBITDA labeling
        - Percentile-based regime classification
        - Clear entry/exit messaging
        - Conservative, educational tone

        Args:
            ticker: Stock ticker
            change: StateChange object
            current_percentile: Current percentile (0-100)
            current_metric_value: Current valuation metric value
            metric_type: 'ev_revenue' or 'ev_ebitda'
            previous_percentile: Previous percentile (optional)
            previous_metric_value: Previous metric value (optional)

        Returns:
            Structured Alert object
        """
        old_regime = change.old_value
        new_regime = change.new_value

        # Map metric type to display label
        metric_label = {
            "ev_revenue": "EV/Revenue",
            "ev_ebitda": "EV/EBITDA",
        }.get(metric_type, "Valuation")

        # Generate headline per MVP plan
        if new_regime == "cheap":
            headline = "Valuation entered historically cheap zone"
        elif new_regime == "expensive":
            headline = "Valuation entered historically rich zone"
        elif old_regime == "cheap":
            headline = "Valuation exited historically cheap zone"
        elif old_regime == "expensive":
            headline = "Valuation exited historically rich zone"
        else:
            headline = "Valuation regime changed"

        # What changed section
        what_changed_items = [
            f"{metric_label} moved from {previous_percentile:.0f}th percentile → {current_percentile:.0f}th percentile"
            if previous_percentile is not None
            else f"{metric_label} now at {current_percentile:.0f}th percentile of historical range"
        ]
        what_changed = "\n".join(f"• {item}" for item in what_changed_items)

        # Why it matters section (per MVP plan specifications)
        if new_regime == "cheap":
            why_it_matters_items = [
                "Stock is trading at the lower end of its own historical valuation range, which can increase margin of safety."
            ]
        elif new_regime == "expensive":
            why_it_matters_items = [
                "Stock is trading at the higher end of its historical valuation range; future returns may rely on continued strong execution."
            ]
        elif old_regime == "cheap":
            why_it_matters_items = [
                "Valuation is no longer in a historically discounted range, reducing margin of safety."
            ]
        elif old_regime == "expensive":
            why_it_matters_items = [
                "Valuation is no longer in a historically premium range."
            ]
        else:
            why_it_matters_items = [
                "Valuation has moved to a different historical zone.",
                "Re-evaluate your investment thesis with this change."
            ]
        why_it_matters = "\n".join(f"• {item}" for item in why_it_matters_items)

        # Before vs now section
        before_vs_now_items = [
            f"Multiple: {previous_metric_value:.2f}x → {current_metric_value:.2f}x"
            if previous_metric_value is not None
            else f"Multiple: {current_metric_value:.2f}x",
            f"Percentile: {previous_percentile:.0f} → {current_percentile:.0f}"
            if previous_percentile is not None
            else f"Percentile: {current_percentile:.0f}"
        ]
        before_vs_now = "\n".join(f"• {item}" for item in before_vs_now_items)

        # What didn't change section
        what_didnt_change_items = [
            f"Metric used: {metric_label}",
            "This is a relative valuation signal based on the company's own history",
            "Underlying business fundamentals may have changed separately"
        ]
        what_didnt_change = "\n".join(f"• {item}" for item in what_didnt_change_items)

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
                "previous_percentile": previous_percentile,
                "current_metric_value": current_metric_value,
                "previous_metric_value": previous_metric_value,
                "metric_type": metric_type,
                "metric_label": metric_label,
                "old_regime": old_regime,
                "new_regime": new_regime,
            },
        )


class AlertRepository:
    """Store and retrieve alerts from database."""

    def __init__(self):
        """Initialize repository with Supabase client."""
        self.client = config.get_supabase_client()

    def close(self):
        """Close connections (no-op for Supabase client)."""
        pass

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
        response = (
            self.client.table("alert_history")
            .insert(
                {
                    "user_id": user_id,
                    "entity_id": entity_id,
                    "alert_type": alert.alert_type,
                    "headline": alert.headline,
                    "what_changed": alert.what_changed,
                    "why_it_matters": alert.why_it_matters,
                    "before_vs_now": alert.before_vs_now,
                    "what_didnt_change": alert.what_didnt_change,
                    "data_snapshot": alert.data_snapshot,
                    "sent_at": alert.timestamp.isoformat(),
                }
            )
            .execute()
        )

        return response.data[0]["id"]

    def get_recent_alerts(self, user_id: str, limit: int = 10) -> list[dict]:
        """
        Get recent alerts for a user.

        Args:
            user_id: User UUID
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        response = (
            self.client.table("alert_history")
            .select("id, alert_type, headline, what_changed, why_it_matters, before_vs_now, what_didnt_change, sent_at, opened_at, entity_id, entities(ticker)")
            .eq("user_id", user_id)
            .order("sent_at", desc=True)
            .limit(limit)
            .execute()
        )

        # Flatten the entities relationship into ticker field
        results = []
        for row in response.data:
            alert_dict = {
                "id": row["id"],
                "alert_type": row["alert_type"],
                "headline": row["headline"],
                "what_changed": row["what_changed"],
                "why_it_matters": row["why_it_matters"],
                "before_vs_now": row["before_vs_now"],
                "what_didnt_change": row["what_didnt_change"],
                "sent_at": row["sent_at"],
                "opened_at": row["opened_at"],
                "ticker": row["entities"]["ticker"] if row.get("entities") else None,
            }
            results.append(alert_dict)

        return results


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
