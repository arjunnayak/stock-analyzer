#!/usr/bin/env python3
"""
Process Backfill Queue

Fetches stocks from backfill_queue table and backfills historical data from DoltHub.

Steps:
1. Query pending items from backfill_queue (ordered by priority)
2. For each ticker:
   - Fetch historical prices from DoltHub
   - Fetch historical fundamentals from DoltHub
   - Upload to R2 storage
   - Update entity metadata
   - Mark as completed in queue
3. Log results

Usage:
    python scripts/process_backfill_queue.py
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_supabase_client, get_r2_client
from src.ingest.dolt_backfill import DoltBackfiller

# Setup logging
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

log_file = log_dir / f'backfill-{datetime.now().strftime("%Y%m%d-%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def process_backfill_queue():
    """
    Main function to process backfill queue

    Returns:
        dict: Summary of processing results
    """
    logger.info("Starting backfill queue processing")

    # Initialize clients
    db = get_supabase_client()
    r2 = get_r2_client()

    # Get pending backfill items (ordered by priority DESC, oldest first)
    result = db.table('backfill_queue').select('id, ticker, requested_by, priority').eq('status', 'pending').order('priority', desc=True).order('requested_at').limit(50).execute()
    pending_items = result.data or []

    logger.info(f"Found {len(pending_items)} stocks in backfill queue")

    if not pending_items:
        logger.info("No stocks to backfill. Exiting.")
        return {
            'processed': 0,
            'succeeded': 0,
            'failed': 0
        }

    # Initialize backfiller
    backfiller = DoltBackfiller(db, r2)

    # Process each ticker
    succeeded = 0
    failed = 0

    for item in pending_items:
        ticker = item['ticker']
        queue_id = item['id']

        logger.info(f"Processing {ticker} (priority: {item['priority']})")

        try:
            # Mark as processing
            db.table('backfill_queue').update({
                'status': 'processing',
                'started_at': datetime.utcnow().isoformat()
            }).eq('id', queue_id).execute()

            # Backfill data from DoltHub
            backfiller.backfill_ticker(ticker)

            # Mark as completed
            db.table('backfill_queue').update({
                'status': 'completed',
                'completed_at': datetime.utcnow().isoformat()
            }).eq('id', queue_id).execute()

            succeeded += 1
            logger.info(f"✓ Successfully backfilled {ticker}")

        except Exception as e:
            logger.error(f"✗ Failed to backfill {ticker}: {e}")

            # Mark as failed and increment retry count
            db.table('backfill_queue').update({
                'status': 'failed',
                'error_message': str(e)[:500],  # Limit error message length
                'retry_count': item.get('retry_count', 0) + 1
            }).eq('id', queue_id).execute()

            failed += 1

    # Summary
    summary = {
        'processed': len(pending_items),
        'succeeded': succeeded,
        'failed': failed
    }

    logger.info(f"Backfill queue processing complete: {summary}")

    return summary


if __name__ == '__main__':
    process_backfill_queue()
