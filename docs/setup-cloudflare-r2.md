# Cloudflare R2 Setup for UBER Backfill

## Step 1: Get Cloudflare R2 Credentials

1. **Go to Cloudflare Dashboard**: https://dash.cloudflare.com
2. **Navigate to R2**: Click "R2" in the left sidebar
3. **Create a Bucket** (if you haven't already):
   - Click "Create bucket"
   - Name: `stock-analyzer` (or your preferred name)
   - Location: Automatic
   - Click "Create bucket"

4. **Create API Token**:
   - Click "Manage R2 API Tokens"
   - Click "Create API token"
   - Permissions: "Object Read & Write"
   - Click "Create API Token"
   - **IMPORTANT**: Copy these values immediately (you won't see them again):
     - Access Key ID
     - Secret Access Key
     - Endpoint URL (format: `https://<account-id>.r2.cloudflarestorage.com`)

## Step 2: Configure .env.local

Edit `/home/user/stock-analyzer/.env.local` and update the REMOTE R2 section:

```bash
# Remote Cloudflare R2
REMOTE_R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
REMOTE_R2_ACCESS_KEY_ID=your_access_key_id_here
REMOTE_R2_SECRET_ACCESS_KEY=your_secret_access_key_here
REMOTE_R2_BUCKET=stock-analyzer  # or your bucket name
```

## Step 3: Switch to REMOTE Mode

Change the ENV variable at the top of `.env.local`:

```bash
ENV=REMOTE  # Changed from LOCAL
```

## Step 4: Verify Configuration

```bash
python src/config.py
```

You should see:
```
Environment: REMOTE
R2/Storage:
  Endpoint: https://your-account-id.r2.cloudflarestorage.com
  Bucket: stock-analyzer
```

## Step 5: Run UBER Backfill

```bash
python scripts/backfill_uber.py
```

This will:
1. Fetch 5 years of UBER price data from EODHD
2. Write to your Cloudflare R2 bucket
3. Compute technical signals
4. Verify everything is working

---

## Quick Test (Without Backfilling UBER)

If you want to test R2 connection first:

```python
from src.storage.r2_client import R2Client

r2 = R2Client()
print("✓ R2 connected successfully!")
```

---

## Troubleshooting

### Error: "Could not connect to endpoint"
- Check `REMOTE_R2_ENDPOINT` is correct format
- Verify your account ID is in the endpoint URL

### Error: "Access Denied"
- Verify `REMOTE_R2_ACCESS_KEY_ID` and `REMOTE_R2_SECRET_ACCESS_KEY` are correct
- Check API token has "Object Read & Write" permissions

### Error: "Bucket does not exist"
- Create the bucket in Cloudflare dashboard
- Verify `REMOTE_R2_BUCKET` matches your bucket name

---

**Ready to proceed?** Once you've added your R2 credentials, we can run the backfill!
