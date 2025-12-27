#!/usr/bin/env python3
"""
Get unique tickers from active watchlists.

Outputs ticker symbols (space-separated) to stdout for use in scripts.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_supabase_client


def main():
    """Get watchlist tickers and print to stdout."""
    try:
        client = get_supabase_client()

        response = client.table('watchlists').select(
            'entity_id, entities(ticker)'
        ).eq('alerts_enabled', True).execute()

        tickers = set()
        for row in response.data:
            entity = row.get('entities')
            if entity and entity.get('ticker'):
                tickers.add(entity['ticker'])

        # Print space-separated list
        print(' '.join(sorted(tickers)))

        return 0

    except Exception as e:
        print(f"Error fetching watchlist tickers: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
