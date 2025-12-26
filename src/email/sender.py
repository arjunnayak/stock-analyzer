"""
Email delivery system for Material Changes alerts.

Supports multiple SMTP providers (SendGrid, Postmark, AWS SES, etc.)
with retry logic, tracking, and HTML/plain-text templates.
"""

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.config import config


@dataclass
class EmailConfig:
    """Email delivery configuration."""

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    from_name: str = "Material Changes"

    @classmethod
    def from_env(cls) -> "EmailConfig":
        """Load email config from environment variables."""
        return cls(
            smtp_host=os.getenv("SMTP_HOST", "smtp.sendgrid.net"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", "apikey"),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            from_email=os.getenv("FROM_EMAIL", "alerts@materialchanges.app"),
            from_name=os.getenv("FROM_NAME", "Material Changes"),
        )


class EmailSender:
    """Send email alerts via SMTP."""

    def __init__(self, config: Optional[EmailConfig] = None):
        """
        Initialize email sender.

        Args:
            config: Email configuration (loads from env if not provided)
        """
        self.config = config or EmailConfig.from_env()
        self._validate_config()

    def _validate_config(self):
        """Validate email configuration."""
        if not self.config.smtp_password:
            raise ValueError("SMTP_PASSWORD environment variable is required")

        if not self.config.from_email:
            raise ValueError("FROM_EMAIL environment variable is required")

    def send_alert(
        self,
        to_email: str,
        ticker: str,
        headline: str,
        plain_body: str,
        html_body: str,
        alert_id: Optional[str] = None,
    ) -> dict:
        """
        Send a material change alert email.

        Args:
            to_email: Recipient email address
            ticker: Stock ticker (e.g., "AAPL")
            headline: Alert headline
            plain_body: Plain text email body
            html_body: HTML email body
            alert_id: Optional alert ID for tracking

        Returns:
            Result dict with status, message_id, error
        """
        subject = f"[Material Change] {ticker} — {headline}"

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
        msg["To"] = to_email
        msg["Message-ID"] = self._generate_message_id(alert_id)
        msg["X-Alert-ID"] = alert_id or "unknown"

        # Attach both plain text and HTML versions
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send via SMTP
        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            return {
                "status": "sent",
                "message_id": msg["Message-ID"],
                "to": to_email,
                "subject": subject,
                "sent_at": datetime.now().isoformat(),
                "error": None,
            }

        except smtplib.SMTPException as e:
            return {
                "status": "failed",
                "message_id": None,
                "to": to_email,
                "subject": subject,
                "sent_at": None,
                "error": f"SMTP error: {str(e)}",
            }

        except Exception as e:
            return {
                "status": "failed",
                "message_id": None,
                "to": to_email,
                "subject": subject,
                "sent_at": None,
                "error": f"Unexpected error: {str(e)}",
            }

    def send_daily_digest(
        self,
        to_email: str,
        alerts: list[dict],
        user_name: Optional[str] = None,
    ) -> dict:
        """
        Send a daily digest email with multiple alerts.

        Args:
            to_email: Recipient email address
            alerts: List of alert dicts (ticker, headline, body)
            user_name: Optional user name for personalization

        Returns:
            Result dict with status, message_id, error
        """
        if not alerts:
            return {
                "status": "skipped",
                "message_id": None,
                "to": to_email,
                "subject": None,
                "sent_at": None,
                "error": "No alerts to send",
            }

        count = len(alerts)
        tickers = ", ".join(set(a["ticker"] for a in alerts[:3]))
        if count > 3:
            tickers += f" +{count - 3} more"

        subject = f"[Material Changes] {count} alert{'s' if count > 1 else ''} — {tickers}"

        # Build digest body
        greeting = f"Hi {user_name}" if user_name else "Hi"

        plain_parts = [
            greeting,
            "",
            f"You have {count} material change alert{'s' if count > 1 else ''} today:",
            "",
            "=" * 70,
        ]

        for i, alert in enumerate(alerts, 1):
            plain_parts.append(f"\n{i}. {alert['ticker']} — {alert['headline']}\n")
            plain_parts.append(alert["plain_body"])
            plain_parts.append("\n" + "=" * 70)

        plain_parts.extend([
            "",
            "---",
            "Material Changes - Monitor stocks without re-researching",
            "Manage your watchlist: https://materialchanges.app/watchlist",
            "Pause alerts: https://materialchanges.app/settings",
        ])

        plain_body = "\n".join(plain_parts)

        # Simple HTML version (can be enhanced later)
        html_body = plain_body.replace("\n", "<br>")

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
        msg["To"] = to_email

        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send
        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            return {
                "status": "sent",
                "message_id": msg.get("Message-ID"),
                "to": to_email,
                "subject": subject,
                "sent_at": datetime.now().isoformat(),
                "alert_count": count,
                "error": None,
            }

        except Exception as e:
            return {
                "status": "failed",
                "message_id": None,
                "to": to_email,
                "subject": subject,
                "sent_at": None,
                "alert_count": count,
                "error": str(e),
            }

    def send_test_email(self, to_email: str) -> dict:
        """
        Send a test email to verify configuration.

        Args:
            to_email: Recipient email address

        Returns:
            Result dict with status and error
        """
        subject = "[Material Changes] Test Email"

        plain_body = """
This is a test email from Material Changes.

If you received this, your email delivery is configured correctly!

---
Material Changes
Monitor stocks without re-researching
"""

        html_body = """
<html>
<body>
<p>This is a test email from <strong>Material Changes</strong>.</p>
<p>If you received this, your email delivery is configured correctly!</p>
<hr>
<p><small>Material Changes - Monitor stocks without re-researching</small></p>
</body>
</html>
"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
        msg["To"] = to_email

        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            print(f"✓ Test email sent successfully to {to_email}")
            return {
                "status": "sent",
                "to": to_email,
                "error": None,
            }

        except Exception as e:
            print(f"✗ Failed to send test email: {e}")
            return {
                "status": "failed",
                "to": to_email,
                "error": str(e),
            }

    def _generate_message_id(self, alert_id: Optional[str] = None) -> str:
        """Generate a unique Message-ID for email tracking."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        domain = self.config.from_email.split("@")[1]

        if alert_id:
            return f"<alert-{alert_id}-{timestamp}@{domain}>"
        else:
            return f"<{timestamp}@{domain}>"


def main():
    """Test email delivery."""
    print("Email Delivery System Test")
    print("=" * 70)

    # Check if config is available
    try:
        sender = EmailSender()
        print("✓ Email configuration loaded")
        print(f"  SMTP: {sender.config.smtp_host}:{sender.config.smtp_port}")
        print(f"  From: {sender.config.from_email}")
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nRequired environment variables:")
        print("  - SMTP_HOST (default: smtp.sendgrid.net)")
        print("  - SMTP_PORT (default: 587)")
        print("  - SMTP_USER (default: apikey)")
        print("  - SMTP_PASSWORD (required)")
        print("  - FROM_EMAIL (default: alerts@materialchanges.app)")
        return 1

    # Send test email
    test_email = os.getenv("TEST_EMAIL")
    if not test_email:
        print("\n⚠️  Set TEST_EMAIL environment variable to send a test email")
        return 0

    print(f"\nSending test email to {test_email}...")
    result = sender.send_test_email(test_email)

    if result["status"] == "sent":
        print("✓ Test email sent successfully!")
        return 0
    else:
        print(f"✗ Failed to send: {result['error']}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
