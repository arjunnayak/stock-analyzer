"""
Alert notification service for template triggers.

Converts template evaluation results to email alerts and sends to users.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import pandas as pd

from src.email.alerts import Alert
from src.email.delivery import EmailDeliveryService
from src.storage.r2_client import R2Client
from src.storage.supabase_db import SupabaseDB


class TemplateAlertAdapter:
    """Convert template triggers to Alert-compatible format for emails."""

    # Template metadata for formatting
    TEMPLATE_METADATA = {
        "T1": {
            "headline": "Bullish trend entry — crossed above 200-day MA",
            "why_matters": """• Major trend shifts can signal the start of new price momentum
• This is the first cross in recent periods, suggesting a potential regime change
• Historically, sustained moves above the 200-day MA indicate bullish trends""",
            "what_didnt_change": """• This is a technical signal, not a fundamental business change
• Company financials and operations remain the same
• Consider this alongside your investment thesis and risk tolerance""",
        },
        "T2": {
            "headline": "Bearish trend risk — crossed below 200-day MA",
            "why_matters": """• Price broke below long-term support, indicating potential downtrend
• This crossover often precedes extended weakness
• May be time to reassess position sizing and risk management""",
            "what_didnt_change": """• This is a technical signal reflecting price action
• Underlying business fundamentals may still be strong
• Consider whether this aligns with your investment timeframe""",
        },
        "T3": {
            "headline": "Pullback to support — potential add opportunity",
            "why_matters": """• Price pullbacks in uptrends can offer lower-risk entry points
• Stock remains above long-term trend (200-day MA)
• Historical pullbacks to 50-day MA often resolve upward in bull trends""",
            "what_didnt_change": """• Overall uptrend remains intact
• This is a tactical observation, not a fundamental shift
• Consider your average cost and position sizing""",
        },
        "T4": {
            "headline": "Extended above trend — potential trim consideration",
            "why_matters": """• Price significantly above moving average suggests short-term overextension
• Historically, such extensions often lead to consolidation or pullbacks
• May be an opportunity to rebalance or take partial profits""",
            "what_didnt_change": """• Uptrend remains valid
• This is about position management, not a sell signal
• Strong momentum can persist longer than expected""",
        },
        "T5": {
            "headline": "Value + Momentum combo — cheap with bullish trend",
            "why_matters": """• Combining low valuation with positive trend offers asymmetric risk/reward
• Stock trading at attractive multiple while price momentum is positive
• This combination historically outperforms single-factor approaches""",
            "what_didnt_change": """• Valuation is just one lens on the business
• Cheap stocks can stay cheap if fundamentals deteriorate
• Consider the quality of the business and competitive position""",
        },
        "T6": {
            "headline": "Expensive + Extended — potential risk zone",
            "why_matters": """• High valuation combined with price extension suggests elevated risk
• Market pricing in optimistic assumptions
• Historical patterns show this combo precedes corrections""",
            "what_didnt_change": """• Strong businesses can maintain premium valuations
• This is a risk signal, not a mandatory sell
• Consider your conviction in the business case""",
        },
        "T7": {
            "headline": "Historically cheap — valuation in bottom 20%",
            "why_matters": """• EV/EBIT in lowest quintile of 5-year range
• Market pricing in below-average expectations
• Historical mean reversion suggests upside potential""",
            "what_didnt_change": """• Low valuation doesn't guarantee recovery
• Check if there are structural reasons for the discount""",
        },
        "T8": {
            "headline": "Historically expensive — valuation in top 20%",
            "why_matters": """• EV/EBIT in highest quintile of 5-year range
• Market pricing in above-average expectations
• Leaves less room for disappointment""",
            "what_didnt_change": """• Great companies can justify premium valuations
• Consider if growth narrative is still intact""",
        },
        "T9": {
            "headline": "Fair value — trading at historical median",
            "why_matters": """• Valuation near 5-year median suggests balanced pricing
• Neither obvious bargain nor expensive
• Good baseline for monitoring future changes""",
            "what_didnt_change": """• This is informational, not actionable
• Fair value is a starting point, not a recommendation
• Focus on business trajectory and competitive dynamics""",
        },
        "T10": {
            "headline": "Uptrend + Cheap — bullish technical + attractive valuation",
            "why_matters": """• Strong combination: price momentum with valuation support
• Uptrend confirms market recognition while valuation offers margin of safety
• This dual confirmation can indicate sustainable moves""",
            "what_didnt_change": """• Both factors can reverse independently
• Technical + value doesn't guarantee success
• Consider fundamentals and business quality as well""",
        },
    }

    @classmethod
    def to_alert(cls, trigger_row: dict) -> Alert:
        """
        Convert a template trigger row to an Alert object.

        Args:
            trigger_row: Dict with keys: ticker, template_id, template_name,
                        trigger_strength, reasons_json

        Returns:
            Alert object compatible with EmailTemplates
        """
        ticker = trigger_row["ticker"]
        template_id = trigger_row["template_id"]
        template_name = trigger_row["template_name"]
        reasons = json.loads(trigger_row["reasons_json"])
        strength = trigger_row.get("trigger_strength", 0.0)

        # Get template metadata
        metadata = cls.TEMPLATE_METADATA.get(template_id, {})

        # Build alert sections
        headline = metadata.get("headline", template_name)
        what_changed = cls._format_what_changed(template_id, reasons)
        why_it_matters = metadata.get(
            "why_matters", "This pattern has triggered."
        )
        before_vs_now = cls._format_before_vs_now(template_id, reasons)
        what_didnt_change = metadata.get(
            "what_didnt_change", "This is a technical signal."
        )

        return Alert(
            ticker=ticker,
            alert_type="template_trigger",
            headline=headline,
            what_changed=what_changed,
            why_it_matters=why_it_matters,
            before_vs_now=before_vs_now,
            what_didnt_change=what_didnt_change,
            timestamp=datetime.now(),
            data_snapshot={
                "template_id": template_id,
                "template_name": template_name,
                "strength": strength,
                **reasons,
            },
        )

    @staticmethod
    def _format_what_changed(template_id: str, reasons: dict) -> str:
        """Format 'what changed' section based on template."""
        if template_id == "T1":  # Cross above 200 EMA
            return f"""• Price crossed above the 200-day moving average
• Previous close: ${reasons.get('prev_close', 0):.2f} (below MA: ${reasons.get('prev_ema_200', 0):.2f})
• Current close: ${reasons.get('close', 0):.2f} (above MA: ${reasons.get('ema_200', 0):.2f})"""

        elif template_id == "T2":  # Cross below 200 EMA
            return f"""• Price crossed below the 200-day moving average
• Previous close: ${reasons.get('prev_close', 0):.2f} (above MA: ${reasons.get('prev_ema_200', 0):.2f})
• Current close: ${reasons.get('close', 0):.2f} (below MA: ${reasons.get('ema_200', 0):.2f})"""

        elif template_id == "T3":  # Pullback in uptrend
            pullback_pct = reasons.get("pullback_depth_pct", 0)
            return f"""• Price pulled back to support in an uptrend
• Current price: ${reasons.get('close', 0):.2f}
• Between EMA 50 (${reasons.get('ema_50', 0):.2f}) and EMA 200 (${reasons.get('ema_200', 0):.2f})
• Pullback depth: {pullback_pct:.1f}% into support zone"""

        elif template_id == "T4":  # Extended above trend
            extension_pct = reasons.get("extension_pct", 0)
            return f"""• Price significantly extended above moving average
• Current price: ${reasons.get('close', 0):.2f}
• EMA 200: ${reasons.get('ema_200', 0):.2f}
• Extension: {extension_pct:.1f}% above long-term trend"""

        elif template_id == "T5":  # Value + momentum
            return f"""• Stock combines cheap valuation with bullish trend
• EV/EBIT: {reasons.get('ev_ebit', 0):.1f}x (threshold: ≤12x)
• Price: ${reasons.get('close', 0):.2f} (above 200 EMA: ${reasons.get('ema_200', 0):.2f})
• Dual confirmation: technical + fundamental"""

        elif template_id == "T6":  # Expensive + extended
            extension_pct = reasons.get("extension_pct", 0)
            return f"""• High valuation combined with price extension
• EV/EBIT: {reasons.get('ev_ebit', 0):.1f}x (threshold: ≥30x)
• Price: ${reasons.get('close', 0):.2f}
• Extension above 200 EMA: {extension_pct:.1f}%"""

        elif template_id == "T7":  # Cheap vs history
            return f"""EV/EBIT: {reasons.get('ev_ebit', 0):.1f}x (below 20th percentile: {reasons.get('p20', 0):.1f}x)
Price: ${reasons.get('close', 0):.2f}"""

        elif template_id == "T8":  # Expensive vs history
            return f"""EV/EBIT: {reasons.get('ev_ebit', 0):.1f}x (above 80th percentile: {reasons.get('p80', 0):.1f}x)
Price: ${reasons.get('close', 0):.2f}"""

        elif template_id == "T9":  # Fair value
            return f"""EV/EBIT: {reasons.get('ev_ebit', 0):.1f}x (median: {reasons.get('p50_median', 0):.1f}x)
Price: ${reasons.get('close', 0):.2f}"""

        elif template_id == "T10":  # Uptrend + cheap
            return f"""EV/EBIT: {reasons.get('ev_ebit', 0):.1f}x (below p20: {reasons.get('p20', 0):.1f}x)
Price: ${reasons.get('close', 0):.2f} (above EMA 200: ${reasons.get('ema_200', 0):.2f})"""

        else:
            # Generic fallback
            return "• " + ", ".join(f"{k}: {v}" for k, v in reasons.items())

    @staticmethod
    def _format_before_vs_now(template_id: str, reasons: dict) -> str:
        """Format 'before vs now' section."""
        if template_id in ["T1", "T2"]:  # MA crossovers
            prev_close = reasons.get("prev_close", 0)
            close = reasons.get("close", 0)
            pct_change = (
                ((close - prev_close) / prev_close * 100) if prev_close else 0
            )

            return f"""• Previous: ${prev_close:.2f}
• Current: ${close:.2f}
• Change: {pct_change:+.1f}%"""

        elif template_id in ["T7", "T8", "T9", "T10"]:  # Valuation templates - no before/after needed
            # Skip redundant info - already shown in "what changed"
            return ""

        elif template_id in ["T3", "T4"]:  # Pullback or extension
            return f"""• Current price: ${reasons.get('close', 0):.2f}
• EMA 50: ${reasons.get('ema_50', 0):.2f}
• EMA 200: ${reasons.get('ema_200', 0):.2f}"""

        else:
            # Generic
            close = reasons.get("close", 0)
            ev_ebit = reasons.get("ev_ebit")
            parts = [f"• Current price: ${close:.2f}"]
            if ev_ebit:
                parts.append(f"• EV/EBIT: {ev_ebit:.1f}x")
            return "\n".join(parts)


class AlertNotifier:
    """Send email alerts for template triggers."""

    def __init__(
        self,
        r2_client: Optional[R2Client] = None,
        db: Optional[SupabaseDB] = None,
        email_service: Optional[EmailDeliveryService] = None,
    ):
        """Initialize alert notifier."""
        self.r2 = r2_client or R2Client()
        self.db = db or SupabaseDB()
        self.email_service = email_service or EmailDeliveryService()

    def send_alerts_for_triggers(
        self,
        run_date: date,
        dry_run: bool = False,
    ) -> dict:
        """
        Send ONE digest email per user with all their alerts for today.

        Args:
            run_date: Date of trigger evaluation
            dry_run: If True, don't send emails or update state

        Returns:
            Summary dict with counts
        """
        print(f"\nProcessing alerts for {run_date}...")

        # 1. Load triggers from R2
        triggers_df = self.r2.get_triggers(run_date)

        if triggers_df is None or triggers_df.empty:
            print("No triggers found. Skipping alert notifications.")
            return {
                "status": "no_triggers",
                "triggers_processed": 0,
                "emails_sent": 0,
                "emails_skipped": 0,
            }

        print(f"Loaded {len(triggers_df)} triggers")

        # 2. Get user watchlists (who's watching what)
        watchlist_map = self._get_user_watchlist_map()
        total_pairs = sum(len(users) for users in watchlist_map.values())
        print(f"Loaded watchlists for {total_pairs} user-ticker pairs")

        # 3. Group alerts by user (for digest emails)
        # user_alerts: {user_id: {"email": str, "alerts": [(alert_id, Alert, entity_id, template_id)]}}
        user_alerts: dict[str, dict] = {}
        alerts_skipped = 0

        for _, trigger_row in triggers_df.iterrows():
            ticker = trigger_row["ticker"]
            template_id = trigger_row["template_id"]

            # Find users watching this ticker
            users = watchlist_map.get(ticker, [])

            if not users:
                continue  # No one watching this ticker

            for user_info in users:
                user_id = user_info["user_id"]
                entity_id = user_info["entity_id"]
                user_email = user_info["email"]

                # Check deduplication (skip if already alerted for this template recently)
                if not self._should_send_alert(user_id, entity_id, template_id, run_date):
                    alerts_skipped += 1
                    continue

                # Convert trigger to Alert
                alert = TemplateAlertAdapter.to_alert(trigger_row.to_dict())
                alert_id = str(uuid.uuid4())

                # Group by user
                if user_id not in user_alerts:
                    user_alerts[user_id] = {
                        "email": user_email,
                        "alerts": [],
                    }
                user_alerts[user_id]["alerts"].append((alert_id, alert, entity_id, template_id))

        # 4. Send ONE digest email per user
        emails_sent = 0
        errors = []
        total_alerts_in_digests = sum(len(u["alerts"]) for u in user_alerts.values())

        print(f"\nSending {len(user_alerts)} digest email(s) with {total_alerts_in_digests} total alerts...")

        for user_id, user_data in user_alerts.items():
            user_email = user_data["email"]
            alerts_list = user_data["alerts"]

            if not alerts_list:
                continue

            if dry_run:
                alert_summaries = [f"{a[1].ticker} {a[3]}" for a in alerts_list]
                print(f"  [DRY RUN] Would send digest to {user_email}: {', '.join(alert_summaries)}")
                emails_sent += 1
                continue

            try:
                # Send digest email
                result = self.email_service.send_daily_digest(
                    user_id=user_id,
                    user_email=user_email,
                    user_name=None,  # Could fetch from users table if needed
                    alerts=[(aid, alert) for aid, alert, _, _ in alerts_list],
                )

                if result.status == "sent":
                    emails_sent += 1
                    # Update alert state for all alerts in this digest
                    for _, alert, entity_id, template_id in alerts_list:
                        self._update_alert_state(user_id, entity_id, template_id, run_date)
                    print(f"  ✓ Digest sent to {user_email} ({len(alerts_list)} alerts)")
                else:
                    errors.append({
                        "user_email": user_email,
                        "error": result.error,
                        "alert_count": len(alerts_list),
                    })
                    print(f"  ✗ Failed digest to {user_email}: {result.error}")

            except Exception as e:
                errors.append({
                    "user_email": user_email,
                    "error": str(e),
                    "alert_count": len(alerts_list),
                })
                print(f"  ✗ Error sending digest to {user_email}: {e}")

        return {
            "status": "success",
            "triggers_processed": len(triggers_df),
            "emails_sent": emails_sent,
            "alerts_in_digests": total_alerts_in_digests,
            "alerts_skipped": alerts_skipped,
            "errors_count": len(errors),
            "errors": errors[:10],
        }

    def _get_user_watchlist_map(self) -> dict[str, list[dict]]:
        """
        Get mapping of ticker → [user_info dicts].

        Returns:
            Dict like: {"AAPL": [{"user_id": "...", "entity_id": "...", "email": "..."}]}
        """
        response = (
            self.db.client.table("watchlists")
            .select("user_id, entity_id, users(email), entities(ticker)")
            .eq("alerts_enabled", True)
            .execute()
        )

        watchlist_map = {}
        for row in response.data:
            entity = row.get("entities")
            user = row.get("users")

            if not entity or not user:
                continue  # Skip malformed rows

            ticker = entity.get("ticker")
            email = user.get("email")

            if not ticker or not email:
                continue

            user_info = {
                "user_id": row["user_id"],
                "entity_id": row["entity_id"],
                "email": email,
            }

            watchlist_map.setdefault(ticker, []).append(user_info)

        return watchlist_map

    def _should_send_alert(
        self,
        user_id: str,
        entity_id: str,
        template_id: str,
        run_date: date,
    ) -> bool:
        """
        Check if we should send this alert (deduplication).

        Only send if:
        - User hasn't been alerted for this template on this ticker in last 7 days

        Args:
            user_id: User UUID
            entity_id: Entity UUID
            template_id: Template ID (e.g., "T1")
            run_date: Current run date

        Returns:
            True if should send, False if should skip
        """
        response = (
            self.db.client.table("user_entity_settings")
            .select("last_alerted_templates")
            .eq("user_id", user_id)
            .eq("entity_id", entity_id)
            .execute()
        )

        if not response.data:
            return True  # No state = first alert

        last_alerted = response.data[0].get("last_alerted_templates", {})

        if template_id not in last_alerted:
            return True  # Never alerted for this template

        # Check if enough time has passed
        try:
            last_date = date.fromisoformat(last_alerted[template_id])
            days_since = (run_date - last_date).days

            # Only re-alert if 7+ days have passed
            return days_since >= 7

        except (ValueError, TypeError):
            # Invalid date format, reset and allow alert
            return True

    def _update_alert_state(
        self,
        user_id: str,
        entity_id: str,
        template_id: str,
        run_date: date,
    ):
        """
        Update user's alert state to prevent duplicates.

        Adds/updates template_id → date mapping in last_alerted_templates.
        """
        # Get current state
        response = (
            self.db.client.table("user_entity_settings")
            .select("last_alerted_templates")
            .eq("user_id", user_id)
            .eq("entity_id", entity_id)
            .execute()
        )

        if response.data:
            last_alerted = response.data[0].get("last_alerted_templates") or {}
        else:
            last_alerted = {}

        # Update template alert date
        last_alerted[template_id] = run_date.isoformat()

        # Upsert state (use on_conflict to handle existing rows)
        self.db.client.table("user_entity_settings").upsert(
            {
                "user_id": user_id,
                "entity_id": entity_id,
                "last_alerted_templates": last_alerted,
            },
            on_conflict="user_id,entity_id",
        ).execute()
