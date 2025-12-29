"""
R2/S3 storage client for time-series data.

Handles reading and writing Parquet files to R2-compatible storage (MinIO locally).
"""

import io
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from src.config import config


class R2Client:
    """Client for interacting with R2/S3-compatible storage."""

    def __init__(self):
        """Initialize S3 client with configuration."""
        self.s3 = boto3.client(
            "s3",
            endpoint_url=config.r2_endpoint,
            aws_access_key_id=config.r2_access_key_id,
            aws_secret_access_key=config.r2_secret_access_key,
            region_name=config.r2_region,
        )
        self.bucket = config.r2_bucket

    def build_key(
        self, dataset: str, ticker: str, year: int, month: int, filename: str = "data.parquet"
    ) -> str:
        """
        Build storage key following the architecture pattern.

        Pattern: {dataset}/v1/{ticker}/{year}/{month}/{filename}

        Args:
            dataset: Dataset type (e.g., 'prices', 'fundamentals', 'signals_valuation')
            ticker: Stock ticker (will be uppercased)
            year: Year (YYYY)
            month: Month (1-12, will be zero-padded)
            filename: Filename (default: data.parquet)

        Returns:
            Storage key path
        """
        ticker = ticker.upper()
        month_str = f"{month:02d}"
        return f"{dataset}/v1/{ticker}/{year}/{month_str}/{filename}"

    def key_exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def put_parquet(self, key: str, df: pd.DataFrame) -> dict:
        """
        Write DataFrame to R2 as Parquet.

        Args:
            key: Storage key
            df: DataFrame to write

        Returns:
            S3 PutObject response
        """
        buffer = io.BytesIO()
        df.to_parquet(buffer, engine="pyarrow", compression="snappy", index=False)
        buffer.seek(0)

        response = self.s3.put_object(Bucket=self.bucket, Key=key, Body=buffer.getvalue())

        print(f"✓ Wrote {len(df)} rows to {key}")
        return response

    def get_parquet(self, key: str) -> Optional[pd.DataFrame]:
        """
        Read Parquet file from R2 as DataFrame.

        Args:
            key: Storage key

        Returns:
            DataFrame or None if key doesn't exist
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            buffer = io.BytesIO(response["Body"].read())
            df = pd.read_parquet(buffer, engine="pyarrow")
            print(f"✓ Read {len(df)} rows from {key}")
            return df
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                print(f"✗ Key not found: {key}")
                return None
            raise

    def merge_and_put(
        self,
        key: str,
        new_df: pd.DataFrame,
        dedupe_column: str = "date",
    ) -> int:
        """
        Merge new data with existing data and write back.

        This is the recommended pattern for daily batch updates:
        1. Download existing monthly file (if exists)
        2. Merge new rows with existing rows
        3. Deduplicate on key column
        4. Sort by key column
        5. Write back to same key

        Args:
            key: Storage key
            new_df: New data to merge
            dedupe_column: Column to deduplicate on (default: 'date')

        Returns:
            Number of rows in final merged file
        """
        # Get existing data if it exists
        existing_df = self.get_parquet(key)

        if existing_df is not None:
            # Merge and deduplicate
            merged_df = pd.concat([existing_df, new_df], ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=[dedupe_column], keep="last")
            merged_df = merged_df.sort_values(dedupe_column).reset_index(drop=True)

            rows_added = len(merged_df) - len(existing_df)
            print(f"  Merged: {len(existing_df)} existing + {len(new_df)} fetched = {len(merged_df)} stored ({rows_added:+d} net change)")
        else:
            # No existing data, just sort new data
            merged_df = new_df.sort_values(dedupe_column).reset_index(drop=True)
            print(f"  New file: {len(merged_df)} rows")

        # Write back
        self.put_parquet(key, merged_df)
        return len(merged_df)

    def get_timeseries(
        self,
        dataset: str,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """
        Read time-series data across multiple months.

        Args:
            dataset: Dataset type
            ticker: Stock ticker
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Concatenated DataFrame filtered to date range
        """
        dfs = []

        # Generate list of (year, month) tuples to fetch
        current = start_date.replace(day=1)
        end = end_date.replace(day=1)

        while current <= end:
            key = self.build_key(dataset, ticker, current.year, current.month)
            df = self.get_parquet(key)

            if df is not None:
                dfs.append(df)

            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        if not dfs:
            print(f"✗ No data found for {ticker} {dataset} between {start_date} and {end_date}")
            return pd.DataFrame()

        # Concatenate and filter
        result = pd.concat(dfs, ignore_index=True)

        # Determine date column (fundamentals use 'period_end', others use 'date')
        date_col = "period_end" if "period_end" in result.columns else "date"

        if date_col in result.columns:
            result[date_col] = pd.to_datetime(result[date_col])
            result = result[
                (result[date_col] >= pd.Timestamp(start_date))
                & (result[date_col] <= pd.Timestamp(end_date))
            ]
            result = result.sort_values(date_col).reset_index(drop=True)

        print(f"✓ Retrieved {len(result)} rows for {ticker} ({start_date} to {end_date})")
        return result

    def list_keys(self, prefix: str = "", max_keys: int = 1000) -> list[str]:
        """
        List keys with given prefix.

        Args:
            prefix: Key prefix to filter
            max_keys: Maximum number of keys to return

        Returns:
            List of keys
        """
        response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix, MaxKeys=max_keys)

        if "Contents" not in response:
            return []

        return [obj["Key"] for obj in response["Contents"]]


if __name__ == "__main__":
    # Test R2 client
    print("Testing R2 Client")
    print("=" * 50)

    client = R2Client()

    # Test bucket access
    try:
        response = client.s3.list_buckets()
        print(f"✓ Connected to R2")
        print(f"  Buckets: {[b['Name'] for b in response['Buckets']]}")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")

    # Test key building
    key = client.build_key("prices", "AAPL", 2024, 1)
    print(f"\nSample key: {key}")
