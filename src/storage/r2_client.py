"""
R2/S3 storage client for time-series data.

Handles reading and writing Parquet files to R2-compatible storage (MinIO locally).
"""

import io
from datetime import date, datetime, timedelta
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

    # =========================================================================
    # Date-Partitioned Features (features/v1/date=YYYY-MM-DD/)
    # =========================================================================

    def build_features_key(self, run_date: date, part: int = 0) -> str:
        """
        Build storage key for date-partitioned features.

        Pattern: features/v1/date=YYYY-MM-DD/part-{part:03d}.parquet

        Args:
            run_date: Date of the feature snapshot
            part: Part number (default: 0)

        Returns:
            Storage key path
        """
        date_str = run_date.strftime("%Y-%m-%d")
        return f"features/v1/date={date_str}/part-{part:03d}.parquet"

    def build_features_latest_key(self) -> str:
        """
        Build storage key for latest features snapshot.

        Returns:
            Storage key: features/v1/latest.parquet
        """
        return "features/v1/latest.parquet"

    def put_features(self, run_date: date, df: pd.DataFrame) -> str:
        """
        Write daily features snapshot to R2.

        Args:
            run_date: Date of the snapshot
            df: DataFrame with feature columns

        Returns:
            Key that was written
        """
        key = self.build_features_key(run_date)
        self.put_parquet(key, df)
        return key

    def put_features_latest(self, df: pd.DataFrame) -> str:
        """
        Write/overwrite latest features snapshot.

        Args:
            df: DataFrame with feature columns

        Returns:
            Key that was written
        """
        key = self.build_features_latest_key()
        self.put_parquet(key, df)
        return key

    def get_features(self, run_date: date) -> Optional[pd.DataFrame]:
        """
        Read features for a specific date.

        Args:
            run_date: Date of the snapshot

        Returns:
            DataFrame or None if not found
        """
        key = self.build_features_key(run_date)
        return self.get_parquet(key)

    def get_features_latest(self) -> Optional[pd.DataFrame]:
        """
        Read latest features snapshot.

        Returns:
            DataFrame or None if not found
        """
        key = self.build_features_latest_key()
        return self.get_parquet(key)

    def get_features_range(
        self, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """
        Read features across a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Concatenated DataFrame
        """
        dfs = []
        current = start_date

        while current <= end_date:
            df = self.get_features(current)
            if df is not None and not df.empty:
                dfs.append(df)
            current += timedelta(days=1)

        if not dfs:
            return pd.DataFrame()

        return pd.concat(dfs, ignore_index=True)

    def list_feature_dates(self, limit: int = 1000) -> list[date]:
        """
        List all available feature dates.

        Returns:
            List of dates (sorted descending)
        """
        prefix = "features/v1/date="
        keys = self.list_keys(prefix=prefix, max_keys=limit)

        dates = []
        for key in keys:
            # Extract date from key like: features/v1/date=2024-12-01/part-000.parquet
            try:
                date_part = key.split("date=")[1].split("/")[0]
                dates.append(date.fromisoformat(date_part))
            except (IndexError, ValueError):
                continue

        return sorted(set(dates), reverse=True)

    # =========================================================================
    # Alert Triggers (alerts_eval/v1/date=YYYY-MM-DD/)
    # =========================================================================

    def build_triggers_key(self, run_date: date) -> str:
        """
        Build storage key for template trigger results.

        Pattern: alerts_eval/v1/date=YYYY-MM-DD/triggers.parquet

        Args:
            run_date: Date of evaluation

        Returns:
            Storage key path
        """
        date_str = run_date.strftime("%Y-%m-%d")
        return f"alerts_eval/v1/date={date_str}/triggers.parquet"

    def put_triggers(self, run_date: date, df: pd.DataFrame) -> str:
        """
        Write template trigger results.

        Args:
            run_date: Date of evaluation
            df: DataFrame with trigger data

        Returns:
            Key that was written
        """
        key = self.build_triggers_key(run_date)
        self.put_parquet(key, df)
        return key

    def get_triggers(self, run_date: date) -> Optional[pd.DataFrame]:
        """
        Read template triggers for a specific date.

        Args:
            run_date: Date of evaluation

        Returns:
            DataFrame or None if not found
        """
        key = self.build_triggers_key(run_date)
        return self.get_parquet(key)

    # =========================================================================
    # Price Snapshots (prices_snapshots/v1/date=YYYY-MM-DD/)
    # =========================================================================

    def build_price_snapshot_key(self, run_date: date) -> str:
        """
        Build storage key for daily price snapshot.

        Pattern: prices_snapshots/v1/date=YYYY-MM-DD/close.parquet

        Args:
            run_date: Date of the snapshot

        Returns:
            Storage key path
        """
        date_str = run_date.strftime("%Y-%m-%d")
        return f"prices_snapshots/v1/date={date_str}/close.parquet"

    def put_price_snapshot(self, run_date: date, df: pd.DataFrame) -> str:
        """
        Write daily price snapshot.

        Args:
            run_date: Date of the snapshot
            df: DataFrame with columns: date, ticker, close, volume

        Returns:
            Key that was written
        """
        key = self.build_price_snapshot_key(run_date)
        self.put_parquet(key, df)
        return key

    def get_price_snapshot(self, run_date: date) -> Optional[pd.DataFrame]:
        """
        Read price snapshot for a specific date.

        Args:
            run_date: Date of the snapshot

        Returns:
            DataFrame or None if not found
        """
        key = self.build_price_snapshot_key(run_date)
        return self.get_parquet(key)


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
