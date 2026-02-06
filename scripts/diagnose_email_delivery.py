#!/usr/bin/env python3
"""
Diagnose email delivery issues.

Checks:
1. SMTP configuration validity
2. Watchlist email addresses
3. Recent email delivery attempts
4. Common misconfigurations
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.email.sender import EmailSender
from src.storage.supabase_db import SupabaseDB


def check_smtp_config():
    """Check SMTP configuration."""
    print("\n" + "=" * 70)
    print("SMTP CONFIGURATION CHECK")
    print("=" * 70)

    try:
        sender = EmailSender()
        print("✓ Email sender initialized")
        print(f"  SMTP Host: {sender.config.smtp_host}")
        print(f"  SMTP Port: {sender.config.smtp_port}")
        print(f"  SMTP User: {sender.config.smtp_user}")
        print(f"  From Email: {sender.config.from_email}")
        print(f"  From Name: {sender.config.from_name}")

        # Check if credentials look valid
        if not sender.config.smtp_password or len(sender.config.smtp_password) < 10:
            print("  ⚠️  SMTP password looks suspicious (too short)")

        return sender
    except Exception as e:
        print(f"❌ Failed to initialize email sender: {e}")
        return None


def check_watchlist_emails():
    """Check what email addresses are in watchlists."""
    print("\n" + "=" * 70)
    print("WATCHLIST EMAIL ADDRESSES")
    print("=" * 70)

    db = SupabaseDB()

    try:
        # Get watchlists with email addresses
        response = (
            db.client.table("watchlists")
            .select("user_id, entity_id, users(email), entities(ticker), alerts_enabled")
            .execute()
        )

        if not response.data:
            print("❌ No watchlist entries found!")
            return False

        print(f"Found {len(response.data)} watchlist entries\n")

        # Group by alerts_enabled status
        enabled = []
        disabled = []

        for row in response.data:
            user = row.get("users")
            entity = row.get("entities")

            if not user or not entity:
                continue

            email = user.get("email")
            ticker = entity.get("ticker")
            alerts = row.get("alerts_enabled", False)

            if alerts:
                enabled.append((email, ticker))
            else:
                disabled.append((email, ticker))

        print(f"Alerts ENABLED ({len(enabled)} entries):")
        for email, ticker in enabled[:10]:  # Show first 10
            masked_email = email[:3] + "***" + email.split("@")[1] if "@" in email else email
            print(f"  {masked_email} → {ticker}")
        if len(enabled) > 10:
            print(f"  ... and {len(enabled) - 10} more")

        if disabled:
            print(f"\nAlerts DISABLED ({len(disabled)} entries):")
            for email, ticker in disabled[:5]:
                masked_email = email[:3] + "***" + email.split("@")[1] if "@" in email else email
                print(f"  {masked_email} → {ticker}")

        if not enabled:
            print("\n❌ NO WATCHLISTS HAVE ALERTS ENABLED!")
            print("   This is why no emails are being sent.")
            print("   Check the 'alerts_enabled' column in the watchlists table.")
            return False

        return True

    except Exception as e:
        print(f"❌ Error checking watchlists: {e}")
        return False


def check_recent_email_deliveries():
    """Check recent email delivery attempts."""
    print("\n" + "=" * 70)
    print("RECENT EMAIL DELIVERY ATTEMPTS")
    print("=" * 70)

    db = SupabaseDB()

    try:
        # Check if email_deliveries table exists
        response = (
            db.client.table("email_deliveries")
            .select("*")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        if not response.data:
            print("⚠️  No email delivery records found")
            print("   This could mean:")
            print("   1. No emails have been sent yet")
            print("   2. Table doesn't exist or is empty")
            return False

        print(f"Found {len(response.data)} recent delivery attempts:\n")

        for delivery in response.data:
            status = delivery.get("status")
            to_email = delivery.get("to_email", "unknown")
            masked_email = to_email[:3] + "***" + to_email.split("@")[1] if "@" in to_email else to_email
            sent_at = delivery.get("sent_at", "unknown")
            error = delivery.get("error")

            icon = "✓" if status == "sent" else "✗"
            print(f"{icon} {status.upper()}: {masked_email}")
            print(f"   Sent at: {sent_at}")
            if error:
                print(f"   Error: {error}")
            print()

        # Count by status
        sent_count = sum(1 for d in response.data if d.get("status") == "sent")
        failed_count = sum(1 for d in response.data if d.get("status") == "failed")

        print(f"Summary: {sent_count} sent, {failed_count} failed")

        return True

    except Exception as e:
        print(f"⚠️  Could not check email_deliveries table: {e}")
        print("   Table may not exist yet")
        return False


def test_email_sending(sender):
    """Test if emails can actually be sent."""
    print("\n" + "=" * 70)
    print("EMAIL SENDING TEST")
    print("=" * 70)

    # Get a test email from environment or prompt
    import os
    test_email = os.getenv("TEST_EMAIL")

    if not test_email:
        print("⚠️  No TEST_EMAIL environment variable set")
        print("   To test email delivery, set TEST_EMAIL and run again:")
        print("   export TEST_EMAIL=your@email.com")
        print("   uv run python scripts/diagnose_email_delivery.py")
        return False

    print(f"Attempting to send test email to {test_email}...")

    try:
        result = sender.send_test_email(test_email)

        if result["status"] == "sent":
            print("✓ Test email sent successfully!")
            print("  Check your inbox (and spam folder)")
            return True
        else:
            print(f"✗ Test email failed: {result['error']}")
            return False

    except Exception as e:
        print(f"✗ Exception during test: {e}")
        return False


def main():
    """Run all diagnostic checks."""
    print("\n" + "=" * 70)
    print("EMAIL DELIVERY DIAGNOSTICS")
    print("=" * 70)

    results = {}

    # 1. Check SMTP config
    sender = check_smtp_config()
    results["smtp_config"] = sender is not None

    # 2. Check watchlist emails
    results["watchlist_emails"] = check_watchlist_emails()

    # 3. Check recent deliveries
    results["recent_deliveries"] = check_recent_email_deliveries()

    # 4. Test sending (optional)
    if sender:
        results["test_send"] = test_email_sending(sender)

    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSIS SUMMARY")
    print("=" * 70)

    for check, passed in results.items():
        icon = "✓" if passed else "❌"
        print(f"{icon} {check.replace('_', ' ').title()}")

    print("\n" + "=" * 70)
    print("COMMON ISSUES & FIXES")
    print("=" * 70)

    print("""
1. **Emails report 'sent' but not received:**
   - Check spam folder first!
   - SMTP provider might be dropping emails (invalid API key)
   - FROM_EMAIL domain not verified with provider
   - User email addresses in watchlist are incorrect

2. **No watchlist entries with alerts_enabled=true:**
   - SQL: UPDATE watchlists SET alerts_enabled = true;
   - Check database for correct user/entity associations

3. **SMTP credentials invalid:**
   - Verify SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
   - For SendGrid: SMTP_USER should be "apikey"
   - Test with: TEST_EMAIL=your@email.com uv run python scripts/diagnose_email_delivery.py

4. **email_deliveries table empty:**
   - Pipeline might not be logging deliveries
   - Table might not exist (run migrations)

5. **FROM_EMAIL domain issues:**
   - Many providers require domain verification
   - Check provider dashboard for domain status
   - Use verified domain or provider's default sending domain
""")

    # Exit code
    if all(results.values()):
        print("✅ All checks passed!")
        return 0
    else:
        print("⚠️  Some issues detected - see details above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
