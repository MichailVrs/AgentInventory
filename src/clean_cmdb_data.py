# -*- coding: utf-8 -*-
import argparse
import sys
import logging
from database import db
from models import CmdbObject
from application import create_app
from settings import Config

# Configure logging for standard output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def clean_cmdb_data(dry_run=False, batch_size=1000):
    logger.info("=== Starting CMDB Object Types Cleanup ===")
    if dry_run:
        logger.info("[DRY RUN] No database changes will be committed.")

    last_id = 0
    total_updated = 0

    while True:
        try:
            # Batch query ordered by ID to prevent loading all rows into memory at once
            objs = CmdbObject.query.filter(CmdbObject.id > last_id).order_by(CmdbObject.id).limit(batch_size).all()
            if not objs:
                break

            batch_updated = 0
            for obj in objs:
                original_type = obj.object_type
                if not original_type:
                    continue

                new_type = original_type
                # The startswith condition should be evaluated first,
                # as otherwise the broader 'in' check makes the startswith branch unreachable
                if original_type.startswith('cmdb_'):
                    new_type = original_type[5:]
                elif 'cmdb_' in original_type:
                    new_type = original_type.split('cmdb_')[-1]

                if new_type != original_type:
                    logger.info(f"Staged update for ID {obj.id}: '{original_type}' -> '{new_type}'")
                    obj.object_type = new_type
                    batch_updated += 1

            last_id = objs[-1].id

            if batch_updated > 0:
                if not dry_run:
                    db.session.commit()
                    logger.info(f"Committed batch of {batch_updated} updates.")
                else:
                    db.session.rollback()
                    logger.info(f"[DRY RUN] Would commit batch of {batch_updated} updates.")
                total_updated += batch_updated
            else:
                if dry_run:
                    db.session.rollback()

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during batch processing at ID > {last_id}: {e}. Session rolled back.")
            sys.exit(1)

    if total_updated > 0:
        logger.info(f"Cleanup finished. Total updated records: {total_updated}")
    else:
        logger.info("No records needed cleanup.")

def main():
    parser = argparse.ArgumentParser(description="Cleanup CMDB Object Types safely in batches.")
    parser.add_argument('--dry-run', action='store_true', help="Execute dry run without committing changes.")
    parser.add_argument('--batch-size', type=int, default=1000, help="Number of records to process in a single batch (default: 1000).")
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("Batch size must be a positive integer.")

    app = create_app(Config)
    with app.app_context():
        clean_cmdb_data(dry_run=args.dry_run, batch_size=args.batch_size)

if __name__ == '__main__':
    main()
