# Email Deliverability Fixes - Getting Out of Spam

## Problem
Stock alert emails are being sent successfully but landing in spam folders.

## Root Causes

Email providers (Gmail, Outlook, etc.) filter emails to spam based on:
1. **Sender reputation** (domain/IP not trusted)
2. **Missing authentication** (SPF, DKIM, DMARC not configured)
3. **Content triggers** (spammy words, formatting)
4. **Engagement signals** (low open rates, no user interaction)
5. **FROM address issues** (domain not verified)

---

## Immediate Fixes (Priority 1)

### 1. Verify Your Sending Domain

**For SendGrid:**
```bash
# Go to SendGrid Dashboard → Settings → Sender Authentication
# Click "Authenticate Your Domain"
# Follow DNS setup instructions
```

**What this does:**
- Proves you own the sending domain
- Adds SPF, DKIM, DMARC records automatically
- Dramatically improves deliverability

**Before verification:**
```
From: Material Changes <alerts@materialchanges.app>
Status: ⚠️ Unverified domain → SPAM
```

**After verification:**
```
From: Material Changes <alerts@materialchanges.app>
Status: ✓ Verified domain → INBOX
```

---

### 2. Use a Reputable SMTP Provider

**Recommended providers (all have free tiers):**
- **SendGrid** - 100 emails/day free
- **Postmark** - Transactional email specialist
- **AWS SES** - $0.10 per 1,000 emails
- **Resend** - Modern, developer-friendly

**Current setup check:**
```bash
echo $SMTP_HOST
# Should be: smtp.sendgrid.net, smtp.postmarkapp.com, etc.
```

**⚠️ Avoid:**
- Generic SMTP servers (smtp.gmail.com for mass mail)
- Free email services for transactional emails
- Shared IPs with poor reputation

---

### 3. Configure Email Authentication (SPF/DKIM/DMARC)

**These DNS records tell email providers you're legitimate:**

#### SPF (Sender Policy Framework)
```dns
TXT @ "v=spf1 include:sendgrid.net ~all"
```
This says "SendGrid is allowed to send email from my domain"

#### DKIM (DomainKeys Identified Mail)
```dns
TXT k1._domainkey "v=DKIM1; k=rsa; p=MIGfMA0GCSq..."
```
This cryptographically signs your emails

#### DMARC (Domain-based Message Authentication)
```dns
TXT _dmarc "v=DMARC1; p=quarantine; rua=mailto:dmarc@materialchanges.app"
```
This tells providers what to do with failed checks

**How to set up:**
1. Log into your domain provider (Cloudflare, GoDaddy, etc.)
2. Go to DNS settings
3. Add TXT records provided by SendGrid/your SMTP provider
4. Wait 24-48 hours for propagation

**Verify setup:**
```bash
# Check SPF
dig TXT materialchanges.app

# Check DKIM
dig TXT k1._domainkey.materialchanges.app

# Check DMARC
dig TXT _dmarc.materialchanges.app
```

---

## Medium-Term Fixes (Priority 2)

### 4. Improve Email Content

**Current issues that trigger spam filters:**

```python
# ❌ BAD - Spam triggers
subject = "🔥 URGENT: Buy Now! 🚀"
body = "Limited time offer! Act fast! Click here!"
```

```python
# ✓ GOOD - Professional
subject = "[Material Change] AAPL — Bullish trend entry"
body = "Price crossed above 200-day moving average..."
```

**Best practices:**
- ✅ Clear, descriptive subject lines
- ✅ Proper HTML structure (your code already does this!)
- ✅ Plain text alternative (you have this!)
- ✅ Balanced text-to-image ratio
- ❌ Avoid: ALL CAPS, excessive punctuation!!!, $ signs
- ❌ Avoid: Shortened URLs (use full URLs)
- ❌ Avoid: Attachments in alert emails

---

### 5. Add Unsubscribe Link

**Required by CAN-SPAM Act, also improves deliverability:**

Update `src/email/sender.py` to add unsubscribe header:

```python
# In send_daily_digest() method, add:
msg["List-Unsubscribe"] = f"<https://materialchanges.app/unsubscribe?user_id={user_id}>"
msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
```

And in the email body (already have this in footer):
```html
<a href="https://materialchanges.app/settings">Pause Alerts</a>
```

---

### 6. Warm Up Your Sending Domain

**New domains have no reputation - you need to build it gradually:**

**Week 1:** Send to 10-20 engaged users
**Week 2:** Send to 50-100 users
**Week 3:** Send to 500 users
**Week 4+:** Scale to full audience

**Why this matters:**
- Sending 1,000 emails from a brand new domain = spam
- Gradually increasing volume = legitimate sender

---

### 7. Monitor Engagement Metrics

**Email providers track:**
- **Open rate** - Are people opening your emails?
- **Click rate** - Are they clicking links?
- **Reply rate** - Are they replying?
- **Complaint rate** - Are they marking as spam?

**Your tracking pixel (already implemented):**
```python
# In src/email/templates.py - already have this!
tracking_pixel = f'<img src="https://api.materialchanges.app/email/open/{alert_id}" width="1" height="1" />'
```

**Check these metrics weekly in SendGrid dashboard**

---

## Long-Term Improvements (Priority 3)

### 8. Use a Dedicated IP (Advanced)

**For high-volume senders (>100k emails/month):**
- Get a dedicated IP address from your SMTP provider
- Build reputation on your own IP
- More control over deliverability

**Cost:** ~$30-50/month (SendGrid/AWS SES)

---

### 9. Implement Email Preference Center

Let users control what they receive:
- Daily digest vs individual alerts
- Which templates trigger alerts (T1-T10)
- Frequency controls (real-time, daily, weekly)

This reduces spam complaints = better reputation

---

### 10. Monitor Blacklists

**Check if your domain/IP is blacklisted:**
```bash
# Check reputation
https://www.senderscore.org/
https://mxtoolbox.com/blacklists.aspx
```

If blacklisted, request removal + fix root cause

---

## Quick Wins for Your Specific Setup

### Check 1: Is your FROM_EMAIL domain verified?

```bash
# Current FROM_EMAIL
echo $FROM_EMAIL
# Should be: alerts@materialchanges.app or similar

# If using SendGrid, check verification status:
# SendGrid Dashboard → Settings → Sender Authentication
```

**If not verified:**
1. Go to SendGrid Dashboard
2. Settings → Sender Authentication
3. Click "Authenticate Your Domain"
4. Add DNS records to your domain (Cloudflare)
5. Wait 24-48 hours

**Impact:** This alone can move you from spam → inbox!

---

### Check 2: Are you using a verified sender identity?

Some providers require both:
- Domain verification (materialchanges.app)
- Sender verification (alerts@materialchanges.app)

**SendGrid:**
- Go to Settings → Sender Identity
- Verify the specific email address

---

### Check 3: Check your email content

Run your email through spam checkers:
```bash
# Use online tools
https://www.mail-tester.com/
https://www.isnotspam.com/

# Send test email to these services
# They'll give you a spam score + fixes
```

---

## Testing Your Fixes

### 1. Send Test Email

```bash
export TEST_EMAIL=your@email.com
uv run python scripts/diagnose_email_delivery.py
```

Check:
- ✓ Lands in inbox (not spam)
- ✓ Shows "via materialchanges.app" or verified domain
- ✓ No security warnings
- ✓ Images load (if using tracking pixel)

---

### 2. Check Email Headers

Forward a received email to yourself, view full headers:

**Good signs:**
```
Authentication-Results: spf=pass; dkim=pass; dmarc=pass
X-Spam-Score: 0.1
```

**Bad signs:**
```
Authentication-Results: spf=fail; dkim=none
X-Spam-Score: 8.5
```

---

### 3. Test With Multiple Providers

Send test emails to:
- Gmail (strictest spam filters)
- Outlook/Hotmail
- Yahoo
- ProtonMail
- Corporate email (often strictest)

If you pass Gmail's filters, you'll pass most others.

---

## Recommended Action Plan

### Today (15 minutes)
1. ✅ Check if FROM_EMAIL domain is verified in SendGrid
2. ✅ If not, start domain verification process
3. ✅ Send test email to yourself: `TEST_EMAIL=you@gmail.com uv run python scripts/diagnose_email_delivery.py`

### This Week (1 hour)
1. ✅ Add SPF/DKIM/DMARC DNS records
2. ✅ Add unsubscribe headers to emails
3. ✅ Review email content for spam triggers
4. ✅ Test deliverability with mail-tester.com

### This Month
1. ✅ Monitor open rates and spam complaints in SendGrid
2. ✅ Gradually increase sending volume (warm up)
3. ✅ Add email preference center
4. ✅ Check blacklist status monthly

---

## Common Mistakes to Avoid

### ❌ Don't:
- Send from unverified domains
- Use generic email addresses (noreply@, no-reply@)
- Send without authentication (SPF/DKIM/DMARC)
- Blast high volume immediately from new domain
- Use spam trigger words excessively
- Hide or make unsubscribe difficult
- Use shortened URLs or suspicious links

### ✅ Do:
- Verify your sending domain
- Use a real, monitored FROM address
- Set up proper authentication
- Warm up your domain gradually
- Write clear, professional content
- Make unsubscribe easy and obvious
- Use full, descriptive URLs

---

## Expected Timeline

**Immediate (< 24 hours):**
- Domain verification: Moves ~50% of emails from spam → inbox

**Short-term (1 week):**
- SPF/DKIM/DMARC setup: Moves ~80% from spam → inbox
- Content improvements: Additional 5-10% improvement

**Medium-term (1 month):**
- Domain warm-up: Full inbox delivery for engaged users
- Reputation building: Provider recognizes you as legitimate

**Long-term (3 months):**
- Established sender: 95%+ inbox placement
- Good engagement metrics: Gmail starts promoting your emails

---

## Resources

**Email Deliverability:**
- [SendGrid Email Deliverability Guide](https://sendgrid.com/blog/email-deliverability-guide/)
- [Postmark Email Guide](https://postmarkapp.com/guides/everything-you-need-to-know-about-email)
- [Google Email Sender Guidelines](https://support.google.com/mail/answer/81126)

**Testing Tools:**
- [Mail Tester](https://www.mail-tester.com/) - Spam score checker
- [MXToolbox](https://mxtoolbox.com/) - DNS/blacklist checker
- [GlockApps](https://glockapps.com/) - Deliverability testing

**DNS Setup:**
- [Cloudflare DNS](https://dash.cloudflare.com/)
- [DNSChecker](https://dnschecker.org/) - Verify DNS propagation

---

## Need Help?

Run the diagnostic script to see your current status:
```bash
uv run python scripts/diagnose_email_delivery.py
```

This will check:
- SMTP configuration
- Watchlist email addresses
- Recent delivery attempts
- Send a test email (if TEST_EMAIL is set)
