"""
Configuration management for stock-analyzer.

Automatically switches between LOCAL and REMOTE configurations based on ENV variable.
"""

import os
from pathlib import Path
from typing import Literal

# Load .env.local file
env_file = Path(__file__).parent.parent / ".env.local"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Remove inline comments
                    value = value.split("#")[0].strip()
                    os.environ.setdefault(key.strip(), value)


class Config:
    """Application configuration with automatic LOCAL/REMOTE switching."""

    def __init__(self):
        self.env: Literal["LOCAL", "REMOTE"] = os.getenv("ENV", "LOCAL")  # type: ignore

    @property
    def is_local(self) -> bool:
        """Check if running in local development mode."""
        return self.env == "LOCAL"

    @property
    def is_remote(self) -> bool:
        """Check if running in remote/production mode."""
        return self.env == "REMOTE"

    # Supabase Configuration
    @property
    def supabase_url(self) -> str:
        """Supabase API URL (e.g., https://xxx.supabase.co)."""
        if self.is_local:
            return os.getenv("LOCAL_SUPABASE_URL", "http://localhost:54321")
        return os.getenv("SUPABASE_URL") or os.getenv("REMOTE_SUPABASE_URL", "")

    @property
    def supabase_service_role_key(self) -> str:
        """Supabase service role key (full access, for backend/CI only)."""
        if self.is_local:
            return os.getenv("LOCAL_SUPABASE_SECRET_KEY", "")
        return os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY", "")

    @property
    def supabase_publishable_key(self) -> str:
        """Supabase publishable/anon key (for frontend)."""
        if self.is_local:
            return os.getenv("LOCAL_SUPABASE_ANON_KEY", "")
        return os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("REMOTE_SUPABASE_PUBLISHABLE_DEFAULT_KEY", "")

    @property
    def supabase_anon_key(self) -> str:
        """Alias for supabase_publishable_key (for backwards compatibility)."""
        return self.supabase_publishable_key

    # R2/S3 Storage Configuration
    @property
    def r2_endpoint(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_ENDPOINT", "http://localhost:9000")
        # Check simple name first (for GitHub Actions), then REMOTE_ prefix
        return os.getenv("R2_ENDPOINT_URL") or os.getenv("REMOTE_R2_ENDPOINT", "")

    @property
    def r2_access_key_id(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_ACCESS_KEY_ID", "")
        # Check AWS standard name, simple name, then REMOTE_ prefix
        return os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY_ID") or os.getenv("REMOTE_R2_ACCESS_KEY_ID", "")

    @property
    def r2_secret_access_key(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_SECRET_ACCESS_KEY", "")
        # Check AWS standard name, simple name, then REMOTE_ prefix
        return os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("REMOTE_R2_SECRET_ACCESS_KEY", "")

    @property
    def r2_bucket(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_BUCKET", "market-data")
        # Check simple name first (for GitHub Actions), then REMOTE_ prefix
        return os.getenv("R2_BUCKET_NAME") or os.getenv("R2_BUCKET") or os.getenv("REMOTE_R2_BUCKET", "market-data")

    @property
    def r2_region(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_REGION", "us-east-1")
        return os.getenv("REMOTE_R2_REGION", "auto")

    # External API Keys
    @property
    def eodhd_api_key(self) -> str:
        return os.getenv("EODHD_API_KEY", "")

    @property
    def alpha_vantage_api_key(self) -> str:
        return os.getenv("ALPHA_VANTAGE_API_KEY", "")

    def get_supabase_client(self):
        """
        Get a Supabase client instance configured for the current environment.

        Returns:
            Supabase client with service role key (full access) for backend/CI use
        """
        from supabase import create_client

        url = self.supabase_url
        key = self.supabase_service_role_key

        if not url or not key:
            raise ValueError(
                f"Supabase configuration incomplete. "
                f"URL: {'✓' if url else '✗'}, "
                f"Service Role Key: {'✓' if key else '✗'}"
            )

        return create_client(url, key)

    def __repr__(self) -> str:
        return f"Config(env={self.env}, is_local={self.is_local})"


# Global config instance
config = Config()


# Helper functions for quick access
def get_supabase_client():
    """
    Get a Supabase client instance configured for the current environment.

    Returns:
        Supabase client with service role key (full access) for backend/CI use
    """
    return config.get_supabase_client()


def get_r2_client():
    """
    Get an R2 storage client instance configured for the current environment.

    Returns:
        R2Client instance for object storage operations
    """
    from src.storage.r2_client import R2Client
    return R2Client()


if __name__ == "__main__":
    # Test configuration
    print("Configuration Test")
    print("=" * 50)
    print(f"Environment: {config.env}")
    print(f"Is Local: {config.is_local}")
    print(f"\nDatabase:")
    print(f"  URL: {config.database_url}")
    print(f"  Host: {config.db_host}:{config.db_port}")
    print(f"\nSupabase:")
    print(f"  URL: {config.supabase_url}")
    print(f"  Anon Key: {config.supabase_anon_key[:20]}...")
    print(f"\nR2/Storage:")
    print(f"  Endpoint: {config.r2_endpoint}")
    print(f"  Bucket: {config.r2_bucket}")
    print(f"  Access Key: {config.r2_access_key_id}")
    print(f"\nExternal APIs:")
    print(f"  EODHD: {'✓ configured' if config.eodhd_api_key else '✗ missing'}")
