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

    # Database Configuration
    @property
    def database_url(self) -> str:
        """Get database connection URL based on environment."""
        if self.is_local:
            return os.getenv("LOCAL_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
        return os.getenv("REMOTE_DATABASE_URL", "")

    @property
    def db_host(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_DB_HOST", "localhost")
        return os.getenv("REMOTE_DB_HOST", "")

    @property
    def db_port(self) -> int:
        if self.is_local:
            return int(os.getenv("LOCAL_DB_PORT", "5432"))
        return int(os.getenv("REMOTE_DB_PORT", "5432"))

    @property
    def db_name(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_DB_NAME", "postgres")
        return os.getenv("REMOTE_DB_NAME", "")

    @property
    def db_user(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_DB_USER", "postgres")
        return os.getenv("REMOTE_DB_USER", "")

    @property
    def db_password(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_DB_PASSWORD", "postgres")
        return os.getenv("REMOTE_DB_PASSWORD", "")

    # Supabase Configuration
    @property
    def supabase_url(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_SUPABASE_URL", "http://localhost:54321")
        return os.getenv("REMOTE_SUPABASE_URL", "")

    @property
    def supabase_anon_key(self) -> str:
        if self.is_local:
            return os.getenv(
                "LOCAL_SUPABASE_ANON_KEY",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
            )
        return os.getenv("REMOTE_SUPABASE_PUBLISHABLE_DEFAULT_KEY", "")

    # R2/S3 Storage Configuration
    @property
    def r2_endpoint(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_ENDPOINT", "http://localhost:9000")
        return os.getenv("REMOTE_R2_ENDPOINT", "")

    @property
    def r2_access_key_id(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_ACCESS_KEY_ID", "minioadmin")
        return os.getenv("REMOTE_R2_ACCESS_KEY_ID", "")

    @property
    def r2_secret_access_key(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_SECRET_ACCESS_KEY", "minioadmin")
        return os.getenv("REMOTE_R2_SECRET_ACCESS_KEY", "")

    @property
    def r2_bucket(self) -> str:
        if self.is_local:
            return os.getenv("LOCAL_R2_BUCKET", "market-data")
        return os.getenv("REMOTE_R2_BUCKET", "market-data")

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

    def __repr__(self) -> str:
        return f"Config(env={self.env}, is_local={self.is_local})"


# Global config instance
config = Config()


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
