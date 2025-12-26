#!/usr/bin/env python3
"""
Send a test email to verify email delivery configuration.

Usage:
    python scripts/test_send_email.py your@email.com

Environment variables required:
    SMTP_HOST       - SMTP server (default: smtp.sendgrid.net)
    SMTP_PORT       - SMTP port (default: 587)
    SMTP_USER       - SMTP username (default: apikey for SendGrid)
    SMTP_PASSWORD   - SMTP password (required)
    FROM_EMAIL      - From email address (default: alerts@materialchanges.app)
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.email.sender import EmailSender
from src.email.templates import EmailTemplates
from src.signals.alerts import Alert


def send_test_alert_email(to_email: str):
    """Send a complete test alert email."""
    print("=" * 70)
    print("SENDING TEST ALERT EMAIL")
    print("=" * 70)
    print(f"To: {to_email}")
    print()

    # Create a sample alert
    alert = Alert(
        ticker="AAPL",
        alert_type="valuation_regime_change",
        headline="Valuation entered historically cheap zone",
        what_changed="• EV/EBITDA moved from 45th percentile → 18th percentile",
        why_it_matters=(
            "• Stock is trading at the lower end of its own historical valuation range, "
            "which can increase margin of safety."
        ),
        before_vs_now="• Multiple: 28.5x → 22.3x\n• Percentile: 45 → 18",
        what_didnt_change=(
            "• Metric used: EV/EBITDA\n"
            "• This is a relative valuation signal based on the company's own history\n"
            "• Underlying business fundamentals may have changed separately"
        ),
        timestamp=datetime.now(),
        data_snapshot={"alert_id": "test-12345"},
    )

    # Generate email bodies
    plain_body = EmailTemplates.format_plain_text(alert)
    html_body = EmailTemplates.format_html(alert, tracking_pixel=False)

    # Send email
    sender = EmailSender()
    result = sender.send_alert(
        to_email=to_email,
        ticker=alert.ticker,
        headline=alert.headline,
        plain_body=plain_body,
        html_body=html_body,
        alert_id="test-12345",
    )

    # Print result
    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)

    if result["status"] == "sent":
        print("✓ Email sent successfully!")
        print(f"  Subject: {result['subject']}")
        print(f"  Sent at: {result['sent_at']}")
        print(f"\n  Check {to_email} for the test email.")
        print("\n  The email will look like a real Material Changes alert.")
        return 0
    else:
        print("✗ Email failed to send")
        print(f"  Error: {result['error']}")
        print("\n  Troubleshooting:")
        print("  1. Check SMTP_PASSWORD is set correctly")
        print("  2. Verify SMTP_HOST and SMTP_PORT are correct")
        print("  3. Check FROM_EMAIL is verified with your provider")
        return 1


def send_simple_test_email(to_email: str):
    """Send a simple test email."""
    print("=" * 70)
    print("SENDING SIMPLE TEST EMAIL")
    print("=" * 70)
    print(f"To: {to_email}")
    print()

    sender = EmailSender()
    result = sender.send_test_email(to_email)

    return 0 if result["status"] == "sent" else 1


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_send_email.py <email>")
        print("\nOptions:")
        print("  --simple    Send a simple test email (no alert)")
        print("  --alert     Send a full alert email (default)")
        print("\nExamples:")
        print("  python scripts/test_send_email.py you@example.com")
        print("  python scripts/test_send_email.py --simple you@example.com")
        return 1

    # Parse arguments
    args = sys.argv[1:]
    mode = "alert"
    email = None

    for arg in args:
        if arg == "--simple":
            mode = "simple"
        elif arg == "--alert":
            mode = "alert"
        elif not arg.startswith("--"):
            email = arg

    if not email:
        print("Error: Email address required")
        return 1

    # Check configuration
    try:
        sender = EmailSender()
        print("✓ Email configuration loaded")
        print(f"  SMTP: {sender.config.smtp_host}:{sender.config.smtp_port}")
        print(f"  From: {sender.config.from_email}")
        print()
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nRequired environment variables:")
        print("  SMTP_HOST (default: smtp.sendgrid.net)")
        print("  SMTP_PORT (default: 587)")
        print("  SMTP_USER (default: apikey)")
        print("  SMTP_PASSWORD (required)")
        print("  FROM_EMAIL (default: alerts@materialchanges.app)")
        return 1

    # Send test email
    if mode == "simple":
        return send_simple_test_email(email)
    else:
        return send_test_alert_email(email)


if __name__ == "__main__":
    sys.exit(main())
