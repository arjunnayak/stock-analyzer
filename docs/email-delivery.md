# Email Delivery System

## Overview

The email delivery system sends Material Changes alerts to users via SMTP, with support for multiple providers, HTML/plain-text templates, delivery logging, and open tracking for validation metrics.

## Features

✅ **Multi-provider SMTP support** - SendGrid, Postmark, AWS SES, Mailgun, etc.
✅ **HTML + Plain Text** - Dual-format emails for compatibility
✅ **Beautiful templates** - Color-coded alerts with responsive design
✅ **Open tracking** - Track when users open emails (validation metrics)
✅ **Delivery logging** - PostgreSQL logging for analytics
✅ **Error handling** - Graceful failures with detailed error messages
✅ **Test utilities** - Send test emails to verify configuration
✅ **Integration** - Seamlessly integrated with signal pipeline

---

## Quick Start

### 1. Configure SMTP Credentials

Set environment variables:

```bash
# For SendGrid (recommended for MVP)
export SMTP_HOST=smtp.sendgrid.net
export SMTP_PORT=587
export SMTP_USER=apikey
export SMTP_PASSWORD=SG.your_sendgrid_api_key_here
export FROM_EMAIL=alerts@materialchanges.app
export FROM_NAME="Material Changes"
```

### 2. Test Configuration

```bash
# Send a simple test email
python scripts/test_send_email.py --simple you@example.com

# Send a full alert test email
python scripts/test_send_email.py you@example.com
```

### 3. Run Unit Tests

```bash
# Test templates and sending logic (mocked)
python tests/test_email_delivery.py
```

### 4. Enable in Pipeline

Email delivery is automatically enabled in the daily evaluation pipeline if SMTP credentials are configured.

---

## Architecture

### Components

```
src/email/
├── sender.py       # SMTP client and delivery logic
├── templates.py    # HTML/plain-text email generators
├── delivery.py     # Orchestration + logging
└── __init__.py     # Public API
```

### Data Flow

```
Signal Pipeline
    │
    ├──> Alert Generated
    │        │
    │        ├──> EmailTemplates.format_plain_text()
    │        ├──> EmailTemplates.format_html()
    │        │
    │        └──> EmailSender.send_alert()
    │                  │
    │                  ├──> SMTP Server
    │                  │
    │                  └──> EmailDeliveryService.log_delivery()
    │                            │
    │                            └──> PostgreSQL (email_deliveries table)
```

---

## SMTP Provider Setup

### SendGrid (Recommended for MVP)

**Free tier:** 100 emails/day

1. Sign up at https://sendgrid.com
2. Create API key: Settings → API Keys → Create API Key
3. Select "Full Access" permissions
4. Copy key to `SMTP_PASSWORD`

```bash
export SMTP_HOST=smtp.sendgrid.net
export SMTP_PORT=587
export SMTP_USER=apikey
export SMTP_PASSWORD=SG.xxxxxxxxxxxx
export FROM_EMAIL=alerts@yourdomain.com
```

**Important:** Verify sender email in SendGrid → Settings → Sender Authentication

### Postmark

**Free tier:** 100 emails/month

```bash
export SMTP_HOST=smtp.postmarkapp.com
export SMTP_PORT=587
export SMTP_USER=your_postmark_server_token
export SMTP_PASSWORD=your_postmark_server_token
export FROM_EMAIL=alerts@yourdomain.com
```

### AWS SES

**Free tier:** 62,000 emails/month (if sent from EC2)

```bash
export SMTP_HOST=email-smtp.us-east-1.amazonaws.com
export SMTP_PORT=587
export SMTP_USER=your_smtp_username
export SMTP_PASSWORD=your_smtp_password
export FROM_EMAIL=alerts@yourdomain.com
```

### Mailgun

**Free tier:** 100 emails/day

```bash
export SMTP_HOST=smtp.mailgun.org
export SMTP_PORT=587
export SMTP_USER=postmaster@yourdomain.mailgun.org
export SMTP_PASSWORD=your_mailgun_password
export FROM_EMAIL=alerts@yourdomain.com
```

---

## Email Templates

### Alert Email Structure

All alert emails follow the MVP-defined 4-section format:

```
[TICKER] — [Headline]

What changed:
• Concrete metric movement

Why it matters:
• Plain-English investor relevance

Before vs now:
• Then → Now

What didn't change:
• Stabilizing facts
```

### Template Types

**1. Alert Email** (`EmailTemplates.format_plain_text()`, `format_html()`)
- Individual material change alerts
- Color-coded by alert type (valuation/trend)
- Includes "View Details" button
- Optional open tracking pixel

**2. Daily Digest** (Future)
- Multiple alerts in one email
- Summary view with expandable details

**3. No Changes Email** (`format_no_changes_email()`)
- Optional "all quiet" notification
- Currently disabled (only send on actual changes)

**4. Welcome Email** (`format_welcome_email()`)
- Onboarding with magic link authentication
- 24-hour expiration notice

---

## Usage Examples

### Send Alert from Pipeline

Automatically handled by `SignalPipeline`:

```python
# In pipeline.py (already integrated)
if self.enable_email and self.email_service:
    user_email = self._get_user_email(user_id)
    if user_email:
        self.email_service.send_alert_email(
            user_id=user_id,
            entity_id=entity_id,
            user_email=user_email,
            alert=alert,
            alert_id=alert_id,
        )
```

### Manual Email Send

```python
from src.email.sender import EmailSender
from src.email.templates import EmailTemplates
from src.signals.alerts import Alert

# Create alert
alert = Alert(
    ticker="AAPL",
    alert_type="valuation_regime_change",
    headline="Valuation entered historically cheap zone",
    what_changed="• EV/EBITDA moved to 18th percentile",
    why_it_matters="• Increased margin of safety",
    before_vs_now="• Multiple: 28x → 22x",
    what_didnt_change="• Metric: EV/EBITDA",
    timestamp=datetime.now(),
    data_snapshot={},
)

# Generate email bodies
plain = EmailTemplates.format_plain_text(alert)
html = EmailTemplates.format_html(alert, tracking_pixel=True)

# Send
sender = EmailSender()
result = sender.send_alert(
    to_email="user@example.com",
    ticker=alert.ticker,
    headline=alert.headline,
    plain_body=plain,
    html_body=html,
    alert_id="alert-123",
)

if result["status"] == "sent":
    print(f"✓ Email sent: {result['message_id']}")
else:
    print(f"✗ Failed: {result['error']}")
```

### Check Delivery Stats

```python
from src.email.delivery import EmailDeliveryService

with EmailDeliveryService() as service:
    stats = service.get_user_delivery_stats(user_id, days=30)

    print(f"Sent: {stats['sent_count']}")
    print(f"Opened: {stats['opened_count']}")
    print(f"Open rate: {stats['open_rate']:.1f}%")
```

---

## Database Schema

The `email_deliveries` table logs all email delivery attempts:

```sql
CREATE TABLE email_deliveries (
    id UUID PRIMARY KEY,
    alert_id UUID NOT NULL,          -- References alert_history.id
    user_id UUID NOT NULL,
    entity_id UUID,                  -- NULL for digests
    to_email TEXT NOT NULL,
    status TEXT NOT NULL,            -- 'sent', 'failed', 'skipped'
    message_id TEXT,                 -- Email Message-ID
    sent_at TIMESTAMP,
    opened_at TIMESTAMP,             -- Tracked via pixel
    error TEXT,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Create table:**

```python
from src.email.delivery import create_email_deliveries_table
create_email_deliveries_table()
```

Or run directly:

```bash
python -c "from src.email.delivery import create_email_deliveries_table; create_email_deliveries_table()"
```

---

## Open Tracking

### How It Works

1. Email includes 1x1 pixel: `<img src="https://materialchanges.app/track/open/alert-123" />`
2. When user opens email, browser loads pixel
3. Server logs open: `EmailDeliveryService.track_email_open(alert_id)`
4. `opened_at` timestamp recorded

### Implementation (Future - API Required)

```python
# In API endpoint (Cloudflare Worker)
@app.get('/track/open/:alert_id')
async def track_open(alert_id: str):
    service = EmailDeliveryService()
    service.track_email_open(alert_id)

    # Return 1x1 transparent GIF
    return Response(
        TRACKING_PIXEL_GIF,
        headers={'Content-Type': 'image/gif'}
    )
```

---

## Validation Metrics

### Key Metrics to Track

**Email Delivery:**
- Total emails sent
- Delivery failures (SMTP errors)
- Bounce rate

**User Engagement:**
- Open rate (% of sent emails opened)
- Time to first open
- Repeat opens

**Alert Quality:**
- Alerts per user per week
- Which alert types are opened most
- Correlation between opens and stock removals

### Query Examples

```sql
-- Overall delivery stats (last 30 days)
SELECT
    COUNT(*) FILTER (WHERE status = 'sent') as sent,
    COUNT(*) FILTER (WHERE status = 'failed') as failed,
    COUNT(*) FILTER (WHERE opened_at IS NOT NULL) as opened,
    ROUND(100.0 * COUNT(*) FILTER (WHERE opened_at IS NOT NULL) /
          NULLIF(COUNT(*) FILTER (WHERE status = 'sent'), 0), 1) as open_rate_pct
FROM email_deliveries
WHERE created_at >= NOW() - INTERVAL '30 days';

-- Per-user engagement
SELECT
    user_id,
    COUNT(*) as emails_sent,
    COUNT(*) FILTER (WHERE opened_at IS NOT NULL) as emails_opened,
    ROUND(100.0 * COUNT(*) FILTER (WHERE opened_at IS NOT NULL) /
          COUNT(*), 1) as open_rate_pct
FROM email_deliveries
WHERE status = 'sent'
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY user_id
ORDER BY emails_sent DESC;

-- Alert type performance
SELECT
    a.alert_type,
    COUNT(DISTINCT ed.id) as emails_sent,
    COUNT(DISTINCT ed.id) FILTER (WHERE ed.opened_at IS NOT NULL) as emails_opened,
    ROUND(100.0 * COUNT(DISTINCT ed.id) FILTER (WHERE ed.opened_at IS NOT NULL) /
          COUNT(DISTINCT ed.id), 1) as open_rate_pct
FROM email_deliveries ed
JOIN alert_history a ON ed.alert_id = a.id
WHERE ed.status = 'sent'
  AND ed.created_at >= NOW() - INTERVAL '30 days'
GROUP BY a.alert_type
ORDER BY emails_sent DESC;
```

---

## Error Handling

### Common Errors

**1. SMTP Authentication Failed**

```
Error: SMTP error: (535, b'Authentication failed')
```

**Fix:** Check `SMTP_PASSWORD` is correct. For SendGrid, ensure API key has "Full Access" permissions.

**2. Sender Not Verified**

```
Error: SMTP error: (550, b'Sender not verified')
```

**Fix:** Verify sender email in provider dashboard (SendGrid → Sender Authentication).

**3. Connection Timeout**

```
Error: Unexpected error: timed out
```

**Fix:** Check firewall rules. GitHub Actions may need VPN/proxy for some SMTP providers.

**4. Missing Configuration**

```
Error: SMTP_PASSWORD environment variable is required
```

**Fix:** Set all required environment variables (see Quick Start).

---

## Testing

### Unit Tests (Mocked SMTP)

```bash
python tests/test_email_delivery.py
```

Tests:
- Plain text formatting
- HTML formatting
- Tracking pixel injection
- SMTP send (mocked)
- Error handling
- Configuration validation

### Integration Tests (Real SMTP)

```bash
# Simple test (plain email)
python scripts/test_send_email.py --simple your@email.com

# Full alert test (actual alert format)
python scripts/test_send_email.py your@email.com
```

**Expected result:** Email arrives in inbox within seconds.

### Manual Testing Checklist

- [ ] Email arrives in inbox (not spam)
- [ ] HTML version renders correctly
- [ ] Plain text version is readable
- [ ] Links work (View Stock, Manage Watchlist, Pause Alerts)
- [ ] Subject line is clear: `[Material Change] AAPL — headline`
- [ ] From name shows "Material Changes"
- [ ] Reply-to works (if configured)

---

## Cost Optimization

### Free Tier Recommendations

| Provider | Free Tier | Best For |
|----------|-----------|----------|
| SendGrid | 100/day | MVP (3,000/month) |
| AWS SES | 62,000/month | Production (requires EC2) |
| Postmark | 100/month | Testing only |
| Mailgun | 100/day | Backup option |

### Cost at Scale

**Assumptions:**
- 50 users
- 10 stocks per user
- 1 alert/stock/week = 500 alerts/month

**SendGrid:** Free (under 3,000/month)
**AWS SES:** Free (under 62,000/month)
**Cost:** $0

**At 1,000 users (10,000 alerts/month):**
- SendGrid: $20/month (40,000 emails/month plan)
- AWS SES: $1/month (10,000 emails = $1)

---

## Production Checklist

Before launching email delivery:

- [ ] Sender email verified with SMTP provider
- [ ] SPF/DKIM records configured (reduce spam score)
- [ ] Unsubscribe link functional (future requirement)
- [ ] GitHub Actions secrets configured
- [ ] Test email sent successfully
- [ ] Database migration run (`email_deliveries` table created)
- [ ] Open tracking endpoint deployed (optional for MVP)
- [ ] Error monitoring set up (Sentry/etc.)
- [ ] Delivery logs reviewed for failures

---

## Troubleshooting

### Emails Going to Spam

**Causes:**
- Missing SPF/DKIM records
- New sender domain (no reputation)
- Generic/marketing-style subject lines

**Fixes:**
1. Configure SPF/DKIM in DNS (provider-specific)
2. Warm up sender reputation (start with small volumes)
3. Use personal subject lines: `[Material Change] AAPL — Cheap zone`
4. Avoid spam trigger words ("FREE", "BUY NOW", etc.)

### Slow Delivery

**Causes:**
- SMTP server latency
- Rate limiting
- Network issues

**Fixes:**
1. Use provider with low latency (SendGrid, Postmark)
2. Implement retry logic for rate limits
3. Monitor `sent_at` timestamps

### Failed Deliveries

Check `email_deliveries` table:

```sql
SELECT to_email, error, created_at
FROM email_deliveries
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 10;
```

Common patterns:
- Invalid email addresses → Validate on signup
- Bounces → Remove from list
- SMTP timeouts → Retry logic

---

## Future Enhancements

**MVP Scope (Out):**
- ❌ Digest emails (multiple alerts in one)
- ❌ Unsubscribe links (manually handled for MVP)
- ❌ Email preferences (HTML vs plain text)
- ❌ Send time optimization
- ❌ A/B testing subject lines

**Post-MVP (If Traction):**
- ✅ Daily digest batching
- ✅ Unsubscribe management
- ✅ Email preferences UI
- ✅ Personalization (user name, investing style)
- ✅ Multi-language support

---

## References

- **Sender module:** `/src/email/sender.py`
- **Templates:** `/src/email/templates.py`
- **Delivery service:** `/src/email/delivery.py`
- **Tests:** `/tests/test_email_delivery.py`
- **Test script:** `/scripts/test_send_email.py`
- **Pipeline integration:** `/src/signals/pipeline.py`

---

**Built with:** Python 3.10+, smtplib (stdlib), PostgreSQL
**SMTP Providers:** SendGrid, Postmark, AWS SES, Mailgun
**Last Updated:** 2025-12-26
