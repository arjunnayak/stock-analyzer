"""
Lightweight Supabase REST API client for Cloudflare Workers.

Since the full Supabase Python client has dependencies that don't work in Pyodide,
this module provides a simple HTTP-based client using the Supabase REST API directly.
"""

import json
import os
from typing import Any, Optional


class SupabaseTable:
    """Represents a Supabase table for querying."""

    def __init__(self, client: "SupabaseClient", table_name: str):
        self.client = client
        self.table_name = table_name
        self._select_fields = "*"
        self._filters = []
        self._order = None
        self._limit_value = None
        self._offset_value = None

    def select(self, fields: str = "*") -> "SupabaseTable":
        """Select fields to return."""
        self._select_fields = fields
        return self

    def eq(self, column: str, value: Any) -> "SupabaseTable":
        """Filter where column equals value."""
        self._filters.append(f"{column}=eq.{value}")
        return self

    def neq(self, column: str, value: Any) -> "SupabaseTable":
        """Filter where column not equals value."""
        self._filters.append(f"{column}=neq.{value}")
        return self

    def gt(self, column: str, value: Any) -> "SupabaseTable":
        """Filter where column greater than value."""
        self._filters.append(f"{column}=gt.{value}")
        return self

    def gte(self, column: str, value: Any) -> "SupabaseTable":
        """Filter where column greater than or equal to value."""
        self._filters.append(f"{column}=gte.{value}")
        return self

    def lt(self, column: str, value: Any) -> "SupabaseTable":
        """Filter where column less than value."""
        self._filters.append(f"{column}=lt.{value}")
        return self

    def lte(self, column: str, value: Any) -> "SupabaseTable":
        """Filter where column less than or equal to value."""
        self._filters.append(f"{column}=lte.{value}")
        return self

    def like(self, column: str, pattern: str) -> "SupabaseTable":
        """Filter where column matches pattern."""
        self._filters.append(f"{column}=like.{pattern}")
        return self

    def ilike(self, column: str, pattern: str) -> "SupabaseTable":
        """Filter where column matches pattern (case insensitive)."""
        from urllib.parse import quote
        # URL encode the pattern (especially % characters)
        encoded_pattern = quote(pattern, safe='')
        self._filters.append(f"{column}=ilike.{encoded_pattern}")
        return self

    def is_(self, column: str, value: str) -> "SupabaseTable":
        """Filter where column is value (for null checks)."""
        self._filters.append(f"{column}=is.{value}")
        return self

    def order(self, column: str, desc: bool = False) -> "SupabaseTable":
        """Order results by column."""
        direction = "desc" if desc else "asc"
        self._order = f"{column}.{direction}"
        return self

    def limit(self, count: int) -> "SupabaseTable":
        """Limit number of results."""
        self._limit_value = count
        return self

    def offset(self, count: int) -> "SupabaseTable":
        """Offset results."""
        self._offset_value = count
        return self

    async def execute(self) -> dict:
        """Execute the query and return results."""
        # Build query parameters
        params = []
        params.append(f"select={self._select_fields}")

        for filter_clause in self._filters:
            params.append(filter_clause)

        if self._order:
            params.append(f"order={self._order}")

        if self._limit_value is not None:
            params.append(f"limit={self._limit_value}")

        if self._offset_value is not None:
            params.append(f"offset={self._offset_value}")

        # Make request
        query_string = "&".join(params)
        url = f"{self.client.base_url}/rest/v1/{self.table_name}?{query_string}"

        from workers import fetch

        response = await fetch(
            url,
            method="GET",
            headers={
                "apikey": self.client.service_role_key,
                "Authorization": f"Bearer {self.client.service_role_key}",
                "Content-Type": "application/json",
            },
        )

        if response.status >= 400:
            error_text = await response.text()
            raise Exception(f"Supabase query failed: {response.status} - {error_text}")

        data = await response.json()
        return {"data": data, "error": None}

    async def insert(self, data: dict | list[dict]) -> dict:
        """Insert data into the table."""
        url = f"{self.client.base_url}/rest/v1/{self.table_name}"

        from workers import fetch

        response = await fetch(
            url,
            method="POST",
            headers={
                "apikey": self.client.service_role_key,
                "Authorization": f"Bearer {self.client.service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            body=json.dumps(data),
        )

        if response.status >= 400:
            error_text = await response.text()
            raise Exception(f"Supabase insert failed: {response.status} - {error_text}")

        result_data = await response.json()
        return {"data": result_data, "error": None}

    async def update(self, data: dict) -> dict:
        """Update data in the table."""
        # Build query parameters from filters
        params = []
        for filter_clause in self._filters:
            params.append(filter_clause)

        query_string = "&".join(params) if params else ""
        url = f"{self.client.base_url}/rest/v1/{self.table_name}"
        if query_string:
            url += f"?{query_string}"

        from workers import fetch

        response = await fetch(
            url,
            method="PATCH",
            headers={
                "apikey": self.client.service_role_key,
                "Authorization": f"Bearer {self.client.service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            body=json.dumps(data),
        )

        if response.status >= 400:
            error_text = await response.text()
            raise Exception(f"Supabase update failed: {response.status} - {error_text}")

        result_data = await response.json()
        return {"data": result_data, "error": None}

    async def delete(self) -> dict:
        """Delete data from the table."""
        # Build query parameters from filters
        params = []
        for filter_clause in self._filters:
            params.append(filter_clause)

        query_string = "&".join(params) if params else ""
        url = f"{self.client.base_url}/rest/v1/{self.table_name}"
        if query_string:
            url += f"?{query_string}"

        from workers import fetch

        response = await fetch(
            url,
            method="DELETE",
            headers={
                "apikey": self.client.service_role_key,
                "Authorization": f"Bearer {self.client.service_role_key}",
                "Content-Type": "application/json",
            },
        )

        if response.status >= 400:
            error_text = await response.text()
            raise Exception(f"Supabase delete failed: {response.status} - {error_text}")

        return {"data": None, "error": None}


class SupabaseClient:
    """Lightweight Supabase client using REST API."""

    def __init__(self, supabase_url: str, service_role_key: str):
        self.base_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key

    def table(self, table_name: str) -> SupabaseTable:
        """Get a table for querying."""
        return SupabaseTable(self, table_name)


async def get_supabase_client(env) -> SupabaseClient:
    """
    Get a Supabase client instance for Cloudflare Workers.

    Args:
        env: The worker environment object containing bindings

    Reads configuration from environment variables:
    - SUPABASE_URL
    - SUPABASE_SERVICE_ROLE_KEY
    """
    supabase_url = getattr(env, "SUPABASE_URL", None)
    service_role_key = getattr(env, "SUPABASE_SERVICE_ROLE_KEY", None)

    if not supabase_url or not service_role_key:
        raise ValueError(
            f"Supabase configuration incomplete. "
            f"URL: {'✓' if supabase_url else '✗'}, "
            f"Service Role Key: {'✓' if service_role_key else '✗'}"
        )

    return SupabaseClient(supabase_url, service_role_key)
