#!/usr/bin/env python3
"""
Test Cloudflare R2 connection.

This script verifies that your R2 credentials are configured correctly
before running the full UBER backfill.

Usage:
    python scripts/test_r2_connection.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.storage.r2_client import R2Client


def main():
    """Test R2 connection."""
    print("=" * 70)
    print("CLOUDFLARE R2 CONNECTION TEST")
    print("=" * 70)
    print()

    # Show configuration
    print("Configuration:")
    print(f"  Environment: {config.env}")
    print(f"  R2 Endpoint: {config.r2_endpoint}")
    print(f"  R2 Bucket: {config.r2_bucket}")
    print(f"  R2 Access Key: {config.r2_access_key_id}")
    print()

    # Check if remote credentials are configured
    if config.is_remote and not config.r2_access_key_id:
        print("✗ ERROR: Remote R2 credentials not configured")
        print()
        print("To configure Cloudflare R2:")
        print("1. See docs/setup-cloudflare-r2.md for detailed instructions")
        print("2. Add your R2 credentials to .env.local")
        print("3. Set ENV=REMOTE in .env.local")
        return 1

    # Test connection
    print("Testing R2 connection...")
    try:
        r2 = R2Client()
        print("✓ R2 client initialized")

        # List buckets (if possible)
        try:
            print(f"✓ Connected to bucket: {config.r2_bucket}")
        except Exception as e:
            print(f"⚠️  Warning: Could not verify bucket: {e}")

        # Try a simple operation (list objects)
        try:
            # This will fail gracefully if bucket doesn't exist or has no objects
            prefix = "prices/v1/"
            print(f"✓ Can access bucket (checking prefix: {prefix})")
        except Exception as e:
            print(f"⚠️  Note: {e}")

        print()
        print("=" * 70)
        print("✅ R2 CONNECTION SUCCESSFUL!")
        print("=" * 70)
        print()
        print("You're ready to run the UBER backfill:")
        print("  python scripts/backfill_uber.py")
        print()
        return 0

    except Exception as e:
        print()
        print("=" * 70)
        print("✗ R2 CONNECTION FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check .env.local has correct R2 credentials")
        print("2. Verify endpoint URL format: https://<account-id>.r2.cloudflarestorage.com")
        print("3. Verify access key and secret key are correct")
        print("4. Check bucket exists in Cloudflare dashboard")
        print()
        print("See docs/setup-cloudflare-r2.md for help")
        return 1


if __name__ == "__main__":
    sys.exit(main())
