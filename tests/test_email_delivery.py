#!/usr/bin/env python3
"""
Tests for email delivery system.

Note: Most tests mock SMTP to avoid actual email sends during testing.
Use scripts/test_send_email.py for real integration testing.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.email.sender import EmailConfig, EmailSender
from src.email.templates import EmailTemplates
from src.signals.alerts import Alert


class TestEmailTemplates:
    """Test email template generation."""

    def test_plain_text_format(self):
        """Test plain text email formatting."""
        print("\n" + "=" * 70)
        print("TEST: Plain Text Email Format")
        print("=" * 70)

        alert = Alert(
            ticker="AAPL",
            alert_type="valuation_regime_change",
            headline="Valuation entered historically cheap zone",
            what_changed="• EV/EBITDA moved from 42nd percentile → 19th percentile",
            why_it_matters="• Stock is trading at lower end of historical range",
            before_vs_now="• Multiple: 28.5x → 22.3x\n• Percentile: 42 → 19",
            what_didnt_change="• Metric used: EV/EBITDA\n• Relative signal",
            timestamp=datetime.now(),
            data_snapshot={"test": "data"},
        )

        plain = EmailTemplates.format_plain_text(alert)

        assert "[AAPL]" in plain
        assert "Valuation entered historically cheap zone" in plain
        assert "What changed:" in plain
        assert "Why it matters:" in plain
        assert "Before vs now:" in plain
        assert "What didn't change:" in plain
        assert "Material Changes" in plain

        print("✓ Plain text contains all required sections")
        print("\nSample output (first 300 chars):")
        print(plain[:300] + "...")

        return True

    def test_html_format(self):
        """Test HTML email formatting."""
        print("\n" + "=" * 70)
        print("TEST: HTML Email Format")
        print("=" * 70)

        alert = Alert(
            ticker="MSFT",
            alert_type="trend_break",
            headline="Bullish trend break",
            what_changed="• Price crossed above 200-day MA",
            why_it_matters="• Major trend shift",
            before_vs_now="• Then: Below MA\n• Now: Above MA",
            what_didnt_change="• Business unchanged",
            timestamp=datetime.now(),
            data_snapshot={},
        )

        html = EmailTemplates.format_html(alert, tracking_pixel=False)

        assert "<!DOCTYPE html>" in html
        assert "<title>MSFT" in html
        assert "Bullish trend break" in html
        assert "What Changed" in html
        assert "View MSFT Details" in html
        assert "Material Changes" in html

        # Should NOT have tracking pixel
        assert '<img src="https://materialchanges.app/track/open/' not in html

        print("✓ HTML contains all required elements")
        print("✓ Tracking pixel disabled as requested")

        return True

    def test_html_with_tracking_pixel(self):
        """Test HTML with open tracking pixel."""
        print("\n" + "=" * 70)
        print("TEST: HTML with Tracking Pixel")
        print("=" * 70)

        alert = Alert(
            ticker="TSLA",
            alert_type="valuation_regime_change",
            headline="Exited cheap zone",
            what_changed="• Percentile increased",
            why_it_matters="• Margin of safety reduced",
            before_vs_now="• Then: Cheap\n• Now: Normal",
            what_didnt_change="• Metric: EV/Revenue",
            timestamp=datetime.now(),
            data_snapshot={"alert_id": "test-123"},
        )

        html = EmailTemplates.format_html(alert, tracking_pixel=True)

        assert '<img src="https://materialchanges.app/track/open/test-123"' in html
        assert 'width="1" height="1"' in html

        print("✓ Tracking pixel included")
        print("✓ Pixel dimensions correct (1x1)")

        return True

    def test_no_changes_email(self):
        """Test 'no changes' email generation."""
        print("\n" + "=" * 70)
        print("TEST: No Changes Email")
        print("=" * 70)

        plain, html = EmailTemplates.format_no_changes_email(
            user_name="John",
            ticker_count=15
        )

        assert "Hi John" in plain
        assert "no material changes" in plain.lower()
        assert "15 monitored stocks" in plain
        assert "<!DOCTYPE html>" in html
        assert "All Quiet" in html

        print("✓ No changes email generated correctly")
        print(f"✓ Personalized for user 'John'")
        print(f"✓ Shows 15 stocks monitored")

        return True

    def test_welcome_email(self):
        """Test welcome email with magic link."""
        print("\n" + "=" * 70)
        print("TEST: Welcome Email")
        print("=" * 70)

        plain, html = EmailTemplates.format_welcome_email(
            user_email="test@example.com",
            magic_link="https://materialchanges.app/auth/verify?token=abc123"
        )

        assert "Welcome to Material Changes" in plain
        assert "token=abc123" in plain
        assert "24 hours" in plain
        assert "<a href=" in html
        assert "Complete Setup" in html

        print("✓ Welcome email contains magic link")
        print("✓ Expiration notice included")

        return True


class TestEmailSender:
    """Test email sending (mocked)."""

    @patch('smtplib.SMTP')
    def test_send_alert_success(self, mock_smtp):
        """Test successful alert email send."""
        print("\n" + "=" * 70)
        print("TEST: Send Alert Email (Mocked)")
        print("=" * 70)

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Configure sender
        config = EmailConfig(
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_user="testuser",
            smtp_password="testpass",
            from_email="test@test.com"
        )

        sender = EmailSender(config)

        # Send email
        result = sender.send_alert(
            to_email="recipient@test.com",
            ticker="AAPL",
            headline="Test alert",
            plain_body="Plain text body",
            html_body="<html>HTML body</html>",
            alert_id="alert-123"
        )

        # Verify
        assert result["status"] == "sent"
        assert result["to"] == "recipient@test.com"
        assert result["error"] is None
        assert "AAPL" in result["subject"]

        # Verify SMTP was called
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("testuser", "testpass")
        mock_server.send_message.assert_called_once()

        print("✓ Email sent successfully")
        print(f"✓ Subject: {result['subject']}")
        print("✓ SMTP connection established")

        return True

    @patch('smtplib.SMTP')
    def test_send_alert_failure(self, mock_smtp):
        """Test failed alert email send."""
        print("\n" + "=" * 70)
        print("TEST: Send Alert Email Failure (Mocked)")
        print("=" * 70)

        # Mock SMTP to raise exception
        mock_smtp.return_value.__enter__.side_effect = Exception("SMTP connection failed")

        config = EmailConfig(
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_user="testuser",
            smtp_password="testpass",
            from_email="test@test.com"
        )

        sender = EmailSender(config)

        result = sender.send_alert(
            to_email="recipient@test.com",
            ticker="MSFT",
            headline="Test alert",
            plain_body="Plain",
            html_body="<html>HTML</html>",
        )

        assert result["status"] == "failed"
        assert result["error"] is not None
        assert "SMTP connection failed" in result["error"]

        print("✓ Failure handled gracefully")
        print(f"✓ Error message: {result['error']}")

        return True

    def test_email_config_validation(self):
        """Test email configuration validation."""
        print("\n" + "=" * 70)
        print("TEST: Email Config Validation")
        print("=" * 70)

        # Missing password should fail
        try:
            config = EmailConfig(
                smtp_host="smtp.test.com",
                smtp_port=587,
                smtp_user="testuser",
                smtp_password="",  # Empty!
                from_email="test@test.com"
            )
            sender = EmailSender(config)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "SMTP_PASSWORD" in str(e)
            print("✓ Missing password detected")

        # Missing from_email should fail
        try:
            config = EmailConfig(
                smtp_host="smtp.test.com",
                smtp_port=587,
                smtp_user="testuser",
                smtp_password="testpass",
                from_email=""  # Empty!
            )
            sender = EmailSender(config)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "FROM_EMAIL" in str(e)
            print("✓ Missing from_email detected")

        return True


def run_all_tests():
    """Run all email delivery tests."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "EMAIL DELIVERY TESTS" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝")
    print("\nNote: These tests use mocked SMTP. For real integration testing,")
    print("use: python scripts/test_send_email.py")

    template_tests = TestEmailTemplates()
    sender_tests = TestEmailSender()

    test_methods = [
        ('Plain Text Format', template_tests.test_plain_text_format),
        ('HTML Format', template_tests.test_html_format),
        ('HTML with Tracking Pixel', template_tests.test_html_with_tracking_pixel),
        ('No Changes Email', template_tests.test_no_changes_email),
        ('Welcome Email', template_tests.test_welcome_email),
        ('Send Alert Success', sender_tests.test_send_alert_success),
        ('Send Alert Failure', sender_tests.test_send_alert_failure),
        ('Config Validation', sender_tests.test_email_config_validation),
    ]

    results = []

    for name, test_func in test_methods:
        try:
            test_func()
            results.append((name, 'PASS', None))
        except AssertionError as e:
            results.append((name, 'FAIL', str(e)))
        except Exception as e:
            results.append((name, 'ERROR', str(e)))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, status, _ in results if status == 'PASS')
    failed = sum(1 for _, status, _ in results if status == 'FAIL')
    errors = sum(1 for _, status, _ in results if status == 'ERROR')

    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "=" * 70)
    print(f"Total: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print("=" * 70)

    if failed == 0 and errors == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
