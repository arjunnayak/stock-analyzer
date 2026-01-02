#!/usr/bin/env python3
"""
Add stocks to a user's watchlist in Supabase.

This script:
1. Creates entity records if they don't exist
2. Adds them to the user's watchlist

Usage:
    # Add stocks for a specific user email
    ENV=REMOTE python scripts/add_stocks_to_watchlist.py --email user@example.com --tickers NVDA MSFT GOOG

    # Add stocks from tickers.txt
    ENV=REMOTE python scripts/add_stocks_to_watchlist.py --email user@example.com --tickers-file tickers.txt

    # Add to first user (useful for testing)
    ENV=REMOTE python scripts/add_stocks_to_watchlist.py --first-user --tickers NVDA MSFT GOOG
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_supabase_client


def read_tickers_from_file(file_path: str) -> list[str]:
    """Read tickers from a file."""
    tickers = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tickers.append(line.upper())
    return tickers


def get_or_create_entity(client, ticker: str) -> str:
    """
    Get or create entity record for a ticker.

    Args:
        client: Supabase client
        ticker: Stock ticker

    Returns:
        Entity UUID
    """
    ticker = ticker.upper()

    # Check if entity exists
    response = client.table("entities").select("id").eq("ticker", ticker).execute()

    if response.data:
        return response.data[0]["id"]

    # Create entity
    print(f"  Creating entity for {ticker}...")
    response = client.table("entities").insert({
        "ticker": ticker,
        "name": ticker,  # Will be updated later with real company name
        "sector": None,
    }).execute()

    return response.data[0]["id"]


def add_to_watchlist(client, user_id: str, entity_id: str, ticker: str) -> bool:
    """
    Add entity to user's watchlist.

    Args:
        client: Supabase client
        user_id: User UUID
        entity_id: Entity UUID
        ticker: Stock ticker (for display)

    Returns:
        True if added, False if already exists
    """
    # Check if already in watchlist
    response = (
        client.table("watchlists")
        .select("id")
        .eq("user_id", user_id)
        .eq("entity_id", entity_id)
        .execute()
    )

    if response.data:
        print(f"  {ticker}: Already in watchlist")
        return False

    # Add to watchlist
    client.table("watchlists").insert({
        "user_id": user_id,
        "entity_id": entity_id,
        "alerts_enabled": True,
    }).execute()

    print(f"  {ticker}: ✓ Added to watchlist")
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add stocks to user's watchlist in Supabase"
    )
    parser.add_argument(
        "--email",
        type=str,
        help="User email address",
    )
    parser.add_argument(
        "--first-user",
        action="store_true",
        help="Use the first user in the database (for testing)",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Ticker symbols to add (e.g., NVDA MSFT GOOG)",
    )
    parser.add_argument(
        "--tickers-file",
        type=str,
        help="Path to tickers file (e.g., tickers.txt)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.email and not args.first_user:
        print("✗ Error: Must specify --email or --first-user")
        sys.exit(1)

    if not args.tickers and not args.tickers_file:
        print("✗ Error: Must specify --tickers or --tickers-file")
        sys.exit(1)

    # Get tickers
    tickers = []
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    elif args.tickers_file:
        try:
            tickers = read_tickers_from_file(args.tickers_file)
        except FileNotFoundError:
            print(f"✗ Error: File not found: {args.tickers_file}")
            sys.exit(1)

    if not tickers:
        print("✗ Error: No tickers to add")
        sys.exit(1)

    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "ADD STOCKS TO WATCHLIST" + " " * 25 + "║")
    print("╚" + "=" * 68 + "╝")

    # Connect to Supabase
    client = get_supabase_client()

    # Get user
    if args.first_user:
        print("\nFinding first user...")
        response = client.table("users").select("id, email").limit(1).execute()
        if not response.data:
            print("✗ Error: No users found in database")
            sys.exit(1)
        user = response.data[0]
        print(f"✓ Using user: {user['email']}")
    else:
        print(f"\nFinding user: {args.email}...")
        response = client.table("users").select("id, email").eq("email", args.email).execute()
        if not response.data:
            print(f"✗ Error: User not found: {args.email}")
            sys.exit(1)
        user = response.data[0]
        print(f"✓ Found user: {user['email']}")

    user_id = user["id"]

    # Process tickers
    print(f"\nAdding {len(tickers)} stocks to watchlist...")
    added = 0
    skipped = 0

    for ticker in tickers:
        try:
            # Get or create entity
            entity_id = get_or_create_entity(client, ticker)

            # Add to watchlist
            if add_to_watchlist(client, user_id, entity_id, ticker):
                added += 1
            else:
                skipped += 1

        except Exception as e:
            print(f"  {ticker}: ✗ Error - {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"User: {user['email']}")
    print(f"Tickers processed: {len(tickers)}")
    print(f"Added: {added}")
    print(f"Skipped (already in watchlist): {skipped}")

    # Show current watchlist
    print("\nCurrent watchlist:")
    response = (
        client.table("watchlists")
        .select("entities(ticker)")
        .eq("user_id", user_id)
        .execute()
    )

    watchlist_tickers = sorted([
        row["entities"]["ticker"] for row in response.data
        if row.get("entities")
    ])
    print(f"  {', '.join(watchlist_tickers)}")

    sys.exit(0)


if __name__ == "__main__":
    main()
