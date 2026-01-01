"""
Alert dataclass for email delivery system.

This is the only component preserved from the legacy signals system.
All signal computation has moved to src/features/.
"""

from dataclasses import dataclass
from datetime import datetime


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
