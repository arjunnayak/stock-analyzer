# GitHub Actions Secrets Configuration

## Required Secrets

Configure these secrets at:
https://github.com/[your-username]/stock-analyzer/settings/secrets/actions

### Supabase Secrets

**Name:** `SUPABASE_URL`
**Value:** `https://xsyjjwyerazihuqoinhz.supabase.co`
**Description:** Supabase API URL
**Note:** Get from Supabase Dashboard → Project Settings → API → Project URL

**Name:** `SUPABASE_SERVICE_ROLE_KEY`
**Value:** `[Your service role key]`
**Description:** Supabase service role key (full database access, for backend/CI only)
**Note:** Get from Supabase Dashboard → Project Settings → API → Service Role Key (secret!)
**⚠️ IMPORTANT:** This key has full database access - never expose it in frontend code!

---

### R2 Storage Secrets

**Name:** `R2_ACCESS_KEY_ID`  
**Value:** `d8163735a0211f8686a8623542a0c1e1`  
**Description:** Cloudflare R2 access key ID

**Name:** `R2_SECRET_ACCESS_KEY`  
**Value:** `27ea4c2a22f5e23b875b7aff9127f207b95ef6a64add9c2f6be2dbf974c9efee`  
**Description:** Cloudflare R2 secret access key

**Name:** `R2_ENDPOINT_URL`  
**Value:** `https://68bea3930baeaf37663861d6187827b9.r2.cloudflarestorage.com`  
**Description:** Cloudflare R2 endpoint URL (without bucket name)

**Name:** `R2_BUCKET_NAME`  
**Value:** `stock-analyzer`  
**Description:** R2 bucket name

---

### External API Secrets

**Name:** `EODHD_API_KEY`  
**Value:** `694d85a8b6c134.94799173`  
**Description:** EODHD Financial Data API key

---

### Email/SMTP Secrets (Optional - for alert notifications)

**Name:** `SMTP_HOST`  
**Value:** `smtp.sendgrid.net` (or your SMTP provider)  
**Description:** SMTP server hostname

**Name:** `SMTP_PORT`  
**Value:** `587`  
**Description:** SMTP server port

**Name:** `SMTP_USER`  
**Value:** `apikey` (for SendGrid) or your SMTP username  
**Description:** SMTP authentication username

**Name:** `SMTP_PASSWORD`  
**Value:** [Your SendGrid API key or SMTP password]  
**Description:** SMTP authentication password

**Name:** `ALERT_EMAIL`  
**Value:** [Your email address for failure notifications]  
**Description:** Email address to receive workflow failure alerts

---

## Environment Variable Mapping

The workflows set these environment variables which map to `config.py`:

| GitHub Secret | Environment Variable | Config Property | Usage |
|--------------|---------------------|-----------------|-------|
| SUPABASE_URL | SUPABASE_URL | config.supabase_url | Supabase API URL (for future client SDK) |
| SUPABASE_SERVICE_ROLE_KEY | SUPABASE_SERVICE_ROLE_KEY | config.supabase_service_role_key | Backend/CI authentication |
| R2_ACCESS_KEY_ID | AWS_ACCESS_KEY_ID | config.r2_access_key_id | R2 storage access |
| R2_SECRET_ACCESS_KEY | AWS_SECRET_ACCESS_KEY | config.r2_secret_access_key | R2 storage secret |
| R2_ENDPOINT_URL | R2_ENDPOINT_URL | config.r2_endpoint | R2 endpoint URL |
| R2_BUCKET_NAME | R2_BUCKET_NAME | config.r2_bucket | R2 bucket name |
| EODHD_API_KEY | EODHD_API_KEY | config.eodhd_api_key | Financial data API |

All workflows also set `ENV=REMOTE` to trigger remote configuration mode.

**Architecture Notes:**
- We can migrate to Supabase client SDK using `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`
- **Frontend:** Will use `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` (anon key)

---

## Testing Workflow Configuration

After configuring secrets, test with manual workflow triggers:

1. **Compute Metrics:** Go to Actions → "Compute Valuation Metrics" → Run workflow
   - Input: ticker = UBER, force = true
   - Expected: Successful computation and file writes to R2

2. **Daily Evaluation:** Go to Actions → "Daily Signal Evaluation" → Run workflow
   - Expected: Processes all active watchlists, detects state changes

3. **CI/CD:** Push a commit or create a PR
   - Expected: Tests pass, data availability check succeeds

