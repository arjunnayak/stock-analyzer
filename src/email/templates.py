"""
Email templates for Material Changes alerts.

Generates HTML and plain-text versions of alert emails.
"""

from typing import Optional

from src.signals.alerts import Alert


class EmailTemplates:
    """Generate email bodies from Alert objects."""

    # Brand colors (can be customized)
    PRIMARY_COLOR = "#2563eb"  # Blue
    SUCCESS_COLOR = "#10b981"  # Green
    WARNING_COLOR = "#f59e0b"  # Amber
    DANGER_COLOR = "#ef4444"   # Red
    NEUTRAL_COLOR = "#6b7280"  # Gray

    @staticmethod
    def format_plain_text(alert: Alert) -> str:
        """
        Generate plain-text email body from alert.

        Args:
            alert: Alert object

        Returns:
            Plain text email body
        """
        lines = [
            f"[{alert.ticker}] — {alert.headline}",
            "",
            "What changed:",
            alert.what_changed,
            "",
            "Why it matters:",
            alert.why_it_matters,
            "",
            "Before vs now:",
            alert.before_vs_now,
            "",
            "What didn't change:",
            alert.what_didnt_change,
            "",
            "---",
            f"Detected: {alert.timestamp.strftime('%Y-%m-%d at %I:%M %p ET')}",
            "",
            "---",
            "Material Changes - Monitor stocks without re-researching",
            f"View {alert.ticker}: https://materialchanges.app/stock/{alert.ticker}",
            "Manage watchlist: https://materialchanges.app/watchlist",
            "Pause alerts: https://materialchanges.app/settings",
        ]

        return "\n".join(lines)

    @staticmethod
    def format_html(alert: Alert, tracking_pixel: bool = False) -> str:
        """
        Generate HTML email body from alert.

        Args:
            alert: Alert object
            tracking_pixel: Whether to include open tracking pixel

        Returns:
            HTML email body
        """
        # Choose color based on alert type
        if "cheap" in alert.headline.lower() or "entered" in alert.headline.lower():
            accent_color = EmailTemplates.SUCCESS_COLOR
        elif "rich" in alert.headline.lower() or "expensive" in alert.headline.lower():
            accent_color = EmailTemplates.WARNING_COLOR
        elif "break" in alert.headline.lower():
            accent_color = EmailTemplates.PRIMARY_COLOR
        else:
            accent_color = EmailTemplates.NEUTRAL_COLOR

        # Build tracking pixel if enabled
        tracking_html = ""
        if tracking_pixel and alert.data_snapshot.get("alert_id"):
            alert_id = alert.data_snapshot["alert_id"]
            tracking_html = f'<img src="https://materialchanges.app/track/open/{alert_id}" width="1" height="1" alt="" />'

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{alert.ticker} — {alert.headline}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background-color: #f9fafb;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: {accent_color};
            color: white;
            padding: 24px;
            text-align: center;
        }}
        .ticker {{
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .headline {{
            font-size: 20px;
            font-weight: 700;
            margin: 0;
        }}
        .content {{
            padding: 32px 24px;
        }}
        .section {{
            margin-bottom: 24px;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 600;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        .section-body {{
            font-size: 15px;
            color: #374151;
            white-space: pre-line;
        }}
        .timestamp {{
            text-align: center;
            color: #9ca3af;
            font-size: 13px;
            padding: 16px 24px;
            border-top: 1px solid #e5e7eb;
        }}
        .footer {{
            background: #f9fafb;
            padding: 24px;
            text-align: center;
            font-size: 13px;
            color: #6b7280;
        }}
        .footer a {{
            color: {accent_color};
            text-decoration: none;
        }}
        .footer a:hover {{
            text-decoration: underline;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background: {accent_color};
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin-top: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="ticker">{alert.ticker}</div>
            <h1 class="headline">{alert.headline}</h1>
        </div>

        <div class="content">
            <div class="section">
                <div class="section-title">What Changed</div>
                <div class="section-body">{alert.what_changed}</div>
            </div>

            <div class="section">
                <div class="section-title">Why It Matters</div>
                <div class="section-body">{alert.why_it_matters}</div>
            </div>

            <div class="section">
                <div class="section-title">Before vs Now</div>
                <div class="section-body">{alert.before_vs_now}</div>
            </div>

            <div class="section">
                <div class="section-title">What Didn't Change</div>
                <div class="section-body">{alert.what_didnt_change}</div>
            </div>

            <div style="text-align: center;">
                <a href="https://materialchanges.app/stock/{alert.ticker}" class="button">View {alert.ticker} Details</a>
            </div>
        </div>

        <div class="timestamp">
            Detected on {alert.timestamp.strftime('%B %d, %Y at %I:%M %p ET')}
        </div>

        <div class="footer">
            <strong>Material Changes</strong><br>
            Monitor stocks without re-researching
            <br><br>
            <a href="https://materialchanges.app/watchlist">Manage Watchlist</a> •
            <a href="https://materialchanges.app/settings">Pause Alerts</a>
        </div>
    </div>
    {tracking_html}
</body>
</html>
"""
        return html

    @staticmethod
    def format_no_changes_email(
        user_name: Optional[str] = None,
        ticker_count: int = 0,
    ) -> tuple[str, str]:
        """
        Generate "no material changes" email.

        Args:
            user_name: Optional user name
            ticker_count: Number of stocks being monitored

        Returns:
            Tuple of (plain_text, html)
        """
        greeting = f"Hi {user_name}" if user_name else "Hi"

        plain_text = f"""
{greeting},

Good news — no material changes detected in your {ticker_count} monitored stocks today.

We're still watching for:
• Valuation regime changes (entry/exit of cheap or rich zones)
• Trend breaks (200-day moving average crossovers)
• Fundamental inflections (EPS estimate reversals)

You'll hear from us when something material happens.

---
Material Changes - Monitor stocks without re-researching
Manage watchlist: https://materialchanges.app/watchlist
Pause alerts: https://materialchanges.app/settings
"""

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>No Material Changes Today</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background-color: #f9fafb;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: white;
            border-radius: 8px;
            padding: 32px;
            text-align: center;
        }}
        h1 {{
            color: #10b981;
            font-size: 24px;
            margin-bottom: 16px;
        }}
        p {{
            color: #374151;
            font-size: 15px;
        }}
        .footer {{
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid #e5e7eb;
            font-size: 13px;
            color: #6b7280;
        }}
        .footer a {{
            color: #2563eb;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✓ All Quiet Today</h1>
        <p>{greeting},</p>
        <p>Good news — no material changes detected in your <strong>{ticker_count} monitored stocks</strong> today.</p>
        <p>We're still watching for valuation regime changes, trend breaks, and fundamental inflections.</p>
        <p>You'll hear from us when something material happens.</p>

        <div class="footer">
            <strong>Material Changes</strong><br>
            Monitor stocks without re-researching
            <br><br>
            <a href="https://materialchanges.app/watchlist">Manage Watchlist</a> •
            <a href="https://materialchanges.app/settings">Pause Alerts</a>
        </div>
    </div>
</body>
</html>
"""

        return plain_text, html

    @staticmethod
    def format_welcome_email(user_email: str, magic_link: str) -> tuple[str, str]:
        """
        Generate welcome/onboarding email with magic link.

        Args:
            user_email: User's email address
            magic_link: Authentication link

        Returns:
            Tuple of (plain_text, html)
        """
        plain_text = f"""
Welcome to Material Changes!

Click the link below to complete your account setup:

{magic_link}

This link will expire in 24 hours.

Once you're logged in, you can:
• Add stocks to your watchlist
• Choose your investing style (Value, Growth, or Blend)
• Enable material change alerts

We'll notify you only when something meaningful happens — so you never need to re-check manually.

---
Material Changes - Monitor stocks without re-researching
Questions? Reply to this email.
"""

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Material Changes</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background-color: #f9fafb;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: white;
            border-radius: 8px;
            padding: 40px;
        }}
        h1 {{
            color: #2563eb;
            font-size: 28px;
            margin-bottom: 16px;
        }}
        .button {{
            display: inline-block;
            padding: 16px 32px;
            background: #2563eb;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin: 24px 0;
        }}
        .footer {{
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid #e5e7eb;
            font-size: 13px;
            color: #6b7280;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Welcome to Material Changes!</h1>
        <p>Click the button below to complete your account setup:</p>

        <div style="text-align: center;">
            <a href="{magic_link}" class="button">Complete Setup</a>
        </div>

        <p style="font-size: 13px; color: #6b7280;">This link will expire in 24 hours.</p>

        <p>Once you're logged in, you can:</p>
        <ul>
            <li>Add stocks to your watchlist</li>
            <li>Choose your investing style (Value, Growth, or Blend)</li>
            <li>Enable material change alerts</li>
        </ul>

        <p>We'll notify you <strong>only when something meaningful happens</strong> — so you never need to re-check manually.</p>

        <div class="footer">
            <strong>Material Changes</strong><br>
            Monitor stocks without re-researching
            <br><br>
            Questions? Reply to this email.
        </div>
    </div>
</body>
</html>
"""

        return plain_text, html
