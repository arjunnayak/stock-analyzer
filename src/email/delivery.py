"""
Email delivery orchestration with logging and tracking.

Integrates with alert pipeline to send emails and log delivery metrics
for validation analysis.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.config import config
from src.email.alerts import Alert
from src.email.sender import EmailSender
from src.email.templates import EmailTemplates


@dataclass
class DeliveryResult:
    """Result of an email delivery attempt."""

    alert_id: str
    user_id: str
    entity_id: str
    ticker: str
    to_email: str
    status: str  # 'sent', 'failed', 'skipped'
    message_id: Optional[str]
    sent_at: Optional[datetime]
    error: Optional[str]


class EmailDeliveryService:
    """Orchestrate email delivery with logging."""

    def __init__(self, email_sender: Optional[EmailSender] = None):
        """
        Initialize delivery service.

        Args:
            email_sender: Email sender instance (creates new if not provided)
        """
        self.sender = email_sender or EmailSender()
        self.client = config.get_supabase_client()

    def close(self):
        """Close connections (no-op for Supabase client)."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def send_alert_email(
        self,
        user_id: str,
        entity_id: str,
        user_email: str,
        alert: Alert,
        alert_id: str,
    ) -> DeliveryResult:
        """
        Send an alert email and log the delivery.

        Args:
            user_id: User UUID
            entity_id: Entity UUID
            user_email: Recipient email address
            alert: Alert object
            alert_id: Alert UUID (from alert_history table)

        Returns:
            DeliveryResult object
        """
        # Generate email bodies
        plain_body = EmailTemplates.format_plain_text(alert)
        html_body = EmailTemplates.format_html(alert, tracking_pixel=True)

        # Send email
        result = self.sender.send_alert(
            to_email=user_email,
            ticker=alert.ticker,
            headline=alert.headline,
            plain_body=plain_body,
            html_body=html_body,
            alert_id=alert_id,
        )

        # Log delivery
        delivery_result = DeliveryResult(
            alert_id=alert_id,
            user_id=user_id,
            entity_id=entity_id,
            ticker=alert.ticker,
            to_email=user_email,
            status=result["status"],
            message_id=result.get("message_id"),
            sent_at=datetime.fromisoformat(result["sent_at"]) if result.get("sent_at") else None,
            error=result.get("error"),
        )

        self._log_delivery(delivery_result)

        return delivery_result

    def send_daily_digest(
        self,
        user_id: str,
        user_email: str,
        user_name: Optional[str],
        alerts: list[tuple[str, Alert]],  # List of (alert_id, Alert)
    ) -> DeliveryResult:
        """
        Send a daily digest email with multiple alerts.

        Args:
            user_id: User UUID
            user_email: Recipient email address
            user_name: User's name (for personalization)
            alerts: List of (alert_id, Alert) tuples

        Returns:
            DeliveryResult object
        """
        # Generate a UUID for the digest
        digest_id = str(uuid.uuid4())

        if not alerts:
            return DeliveryResult(
                alert_id=digest_id,
                user_id=user_id,
                entity_id="",
                ticker="",
                to_email=user_email,
                status="skipped",
                message_id=None,
                sent_at=None,
                error="No alerts to send",
            )

        # Format alerts for digest
        digest_alerts = []
        for alert_id, alert in alerts:
            digest_alerts.append({
                "ticker": alert.ticker,
                "headline": alert.headline,
                "plain_body": EmailTemplates.format_plain_text(alert),
            })

        # Send digest
        result = self.sender.send_daily_digest(
            to_email=user_email,
            alerts=digest_alerts,
            user_name=user_name,
        )

        # Log delivery
        delivery_result = DeliveryResult(
            alert_id=digest_id,
            user_id=user_id,
            entity_id="",
            ticker=f"{len(alerts)} stocks",
            to_email=user_email,
            status=result["status"],
            message_id=result.get("message_id"),
            sent_at=datetime.fromisoformat(result["sent_at"]) if result.get("sent_at") else None,
            error=result.get("error"),
        )

        self._log_digest_delivery(delivery_result, [aid for aid, _ in alerts])

        return delivery_result

    def send_no_changes_notification(
        self,
        user_id: str,
        user_email: str,
        user_name: Optional[str],
        ticker_count: int,
    ) -> Optional[DeliveryResult]:
        """
        Send "no material changes" email (optional).

        Args:
            user_id: User UUID
            user_email: Recipient email address
            user_name: User's name
            ticker_count: Number of monitored stocks

        Returns:
            DeliveryResult or None if disabled
        """
        # Check user preference (if they want "no changes" emails)
        # For MVP, we'll skip this by default
        # Users should only get emails when something actually happens

        return None

    def _log_delivery(self, result: DeliveryResult):
        """Log email delivery to database for validation metrics."""
        self.client.table("email_deliveries").insert(
            {
                "id": str(uuid.uuid4()),
                "alert_id": result.alert_id,
                "user_id": result.user_id,
                "entity_id": result.entity_id,
                "to_email": result.to_email,
                "status": result.status,
                "message_id": result.message_id,
                "sent_at": result.sent_at.isoformat() if result.sent_at else None,
                "error": result.error,
            }
        ).execute()

        # Print log for batch job visibility
        if result.status == "sent":
            print(f"  ✓ Email sent to {result.to_email} for {result.ticker}")
        else:
            print(f"  ✗ Email failed for {result.to_email}: {result.error}")

    def _log_digest_delivery(self, result: DeliveryResult, alert_ids: list[str]):
        """Log digest email delivery."""
        self.client.table("email_deliveries").insert(
            {
                "id": str(uuid.uuid4()),
                "alert_id": result.alert_id,
                "user_id": result.user_id,
                "entity_id": result.entity_id if result.entity_id else None,  # NULL for digest
                "to_email": result.to_email,
                "status": result.status,
                "message_id": result.message_id,
                "sent_at": result.sent_at.isoformat() if result.sent_at else None,
                "error": result.error,
                "metadata": {"alert_ids": alert_ids, "type": "digest"},
            }
        ).execute()

        if result.status == "sent":
            print(f"  ✓ Digest sent to {result.to_email} ({len(alert_ids)} alerts)")
        else:
            print(f"  ✗ Digest failed for {result.to_email}: {result.error}")

    def get_user_delivery_stats(self, user_id: str, days: int = 30) -> dict:
        """
        Get email delivery statistics for a user.

        Args:
            user_id: User UUID
            days: Number of days to look back

        Returns:
            Stats dict with sent, failed, opened counts
        """
        from datetime import timedelta

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        response = (
            self.client.table("email_deliveries")
            .select("status, opened_at")
            .eq("user_id", user_id)
            .gte("created_at", cutoff_date)
            .execute()
        )

        # Compute stats in Python
        sent_count = sum(1 for row in response.data if row["status"] == "sent")
        failed_count = sum(1 for row in response.data if row["status"] == "failed")
        opened_count = sum(1 for row in response.data if row.get("opened_at") is not None)

        return {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "opened_count": opened_count,
            "open_rate": (opened_count / sent_count * 100) if sent_count > 0 else 0,
        }

    def track_email_open(self, alert_id: str):
        """
        Track when a user opens an email (via tracking pixel).

        Args:
            alert_id: Alert UUID
        """
        # Update only if opened_at is null (first open only)
        self.client.table("email_deliveries").update({"opened_at": datetime.now().isoformat()}).eq(
            "alert_id", alert_id
        ).is_("opened_at", "null").execute()


def create_email_deliveries_table():
    """
    Create email_deliveries table for logging (migration).

    NOTE: This function is deprecated. Use Supabase migrations instead.
    For development/testing, the table should be created via:
    - supabase/migrations/*.sql files
    - Applied with: supabase db push

    This function is kept for backward compatibility but may not work
    with Supabase client (which doesn't support raw SQL DDL).
    """
    print("⚠️  create_email_deliveries_table() is deprecated")
    print("   Use Supabase migrations instead:")
    print("   1. Add table definition to supabase/migrations/")
    print("   2. Run: supabase db push")
    print()
    print("   Table schema:")
    print("   - id UUID PRIMARY KEY")
    print("   - alert_id UUID NOT NULL")
    print("   - user_id UUID NOT NULL REFERENCES users(id)")
    print("   - entity_id UUID REFERENCES entities(id)")
    print("   - to_email TEXT NOT NULL")
    print("   - status TEXT NOT NULL")
    print("   - message_id TEXT")
    print("   - sent_at TIMESTAMP")
    print("   - opened_at TIMESTAMP")
    print("   - error TEXT")
    print("   - metadata JSONB")
    print("   - created_at TIMESTAMP NOT NULL DEFAULT NOW()")


if __name__ == "__main__":
    # Create table if needed
    print("Setting up email delivery infrastructure...")
    create_email_deliveries_table()
