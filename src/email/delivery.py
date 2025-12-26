"""
Email delivery orchestration with logging and tracking.

Integrates with alert pipeline to send emails and log delivery metrics
for validation analysis.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from src.config import config
from src.email.sender import EmailSender
from src.email.templates import EmailTemplates
from src.signals.alerts import Alert


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
        self.db_conn = psycopg2.connect(config.database_url)

    def close(self):
        """Close database connection."""
        if self.db_conn:
            self.db_conn.close()

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
        if not alerts:
            return DeliveryResult(
                alert_id="digest",
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
            alert_id="digest",
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
        with self.db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_deliveries (
                    id, alert_id, user_id, entity_id,
                    to_email, status, message_id, sent_at, error, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    result.alert_id,
                    result.user_id,
                    result.entity_id,
                    result.to_email,
                    result.status,
                    result.message_id,
                    result.sent_at,
                    result.error,
                ),
            )

        self.db_conn.commit()

        # Print log for batch job visibility
        if result.status == "sent":
            print(f"  ✓ Email sent to {result.to_email} for {result.ticker}")
        else:
            print(f"  ✗ Email failed for {result.to_email}: {result.error}")

    def _log_digest_delivery(self, result: DeliveryResult, alert_ids: list[str]):
        """Log digest email delivery."""
        with self.db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_deliveries (
                    id, alert_id, user_id, entity_id,
                    to_email, status, message_id, sent_at, error,
                    metadata, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    result.alert_id,
                    result.user_id,
                    result.entity_id,
                    result.to_email,
                    result.status,
                    result.message_id,
                    result.sent_at,
                    result.error,
                    Json({"alert_ids": alert_ids, "type": "digest"}),
                ),
            )

        self.db_conn.commit()

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
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'sent') as sent_count,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                    COUNT(*) FILTER (WHERE opened_at IS NOT NULL) as opened_count
                FROM email_deliveries
                WHERE user_id = %s
                  AND created_at >= NOW() - INTERVAL '%s days'
                """,
                (user_id, days),
            )

            row = cur.fetchone()

            return {
                "sent_count": row["sent_count"] or 0,
                "failed_count": row["failed_count"] or 0,
                "opened_count": row["opened_count"] or 0,
                "open_rate": (row["opened_count"] / row["sent_count"] * 100) if row["sent_count"] > 0 else 0,
            }

    def track_email_open(self, alert_id: str):
        """
        Track when a user opens an email (via tracking pixel).

        Args:
            alert_id: Alert UUID
        """
        with self.db_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE email_deliveries
                SET opened_at = NOW()
                WHERE alert_id = %s
                  AND opened_at IS NULL
                """,
                (alert_id,),
            )

        self.db_conn.commit()


def create_email_deliveries_table():
    """Create email_deliveries table for logging (migration)."""
    sql = """
    CREATE TABLE IF NOT EXISTS email_deliveries (
        id UUID PRIMARY KEY,
        alert_id UUID NOT NULL,  -- References alert_history.id or 'digest'
        user_id UUID NOT NULL REFERENCES users(id),
        entity_id UUID REFERENCES entities(id),  -- NULL for digests
        to_email TEXT NOT NULL,
        status TEXT NOT NULL,  -- 'sent', 'failed', 'skipped'
        message_id TEXT,  -- Email Message-ID for tracking
        sent_at TIMESTAMP,
        opened_at TIMESTAMP,  -- Tracked via pixel
        error TEXT,
        metadata JSONB,  -- Additional data (e.g., digest alert IDs)
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_email_deliveries_user_created
        ON email_deliveries(user_id, created_at DESC);

    CREATE INDEX IF NOT EXISTS idx_email_deliveries_alert
        ON email_deliveries(alert_id);

    CREATE INDEX IF NOT EXISTS idx_email_deliveries_status
        ON email_deliveries(status);
    """

    conn = psycopg2.connect(config.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("✓ email_deliveries table created")
    finally:
        conn.close()


if __name__ == "__main__":
    # Create table if needed
    print("Setting up email delivery infrastructure...")
    create_email_deliveries_table()
    print("✓ Setup complete")
