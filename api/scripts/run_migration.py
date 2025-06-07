#!/usr/bin/env python3
"""Manual migration script to migrate data from JetStream to DuckDB."""

import asyncio
import os
import sys
import logging
import argparse

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import nats
from app.database.connection import get_db_manager
from app.database.migrations import MigrationManager
from app.migrations.migrate_from_jetstream import JetStreamMigrator
from app.startup import initialize_database_system, get_database_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def connect_to_nats(nats_url: str):
    """Connect to NATS and return JetStream context."""
    try:
        logger.info(f"Connecting to NATS at {nats_url}")
        nc = await nats.connect(nats_url)
        js = nc.jetstream()
        logger.info("Connected to NATS JetStream successfully")
        return nc, js
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        raise


async def check_jetstream_data(js):
    """Check what data exists in JetStream KV stores."""
    logger.info("Checking JetStream KV stores for existing data...")
    
    buckets = ["users", "wallets", "alerts", "wallet_balances"]
    data_summary = {}
    
    for bucket in buckets:
        try:
            kv = await js.key_value(bucket=bucket)
            keys = await kv.keys()
            data_summary[bucket] = len(keys)
            logger.info(f"Bucket '{bucket}': {len(keys)} keys found")
        except Exception as e:
            data_summary[bucket] = 0
            logger.warning(f"Bucket '{bucket}': Not found or empty ({e})")
    
    total_items = sum(data_summary.values())
    logger.info(f"Total items in JetStream: {total_items}")
    
    return data_summary, total_items


async def run_migration(nats_url: str, backup: bool = True, force: bool = False):
    """Run the complete migration process."""
    logger.info("Starting JetStream to DuckDB migration...")
    
    # Connect to NATS
    nc, js = await connect_to_nats(nats_url)
    
    try:
        # Check JetStream data
        data_summary, total_items = await check_jetstream_data(js)
        
        if total_items == 0:
            logger.warning("No data found in JetStream KV stores. Nothing to migrate.")
            return {"status": "no_data", "message": "No data to migrate"}
        
        # Check database status
        db_status = get_database_status()
        
        if not db_status.get("database_healthy", False):
            logger.error("Database is not healthy. Cannot proceed with migration.")
            return {"status": "error", "message": "Database not healthy"}
        
        # Check if database already has data
        tables = db_status.get("tables", {})
        existing_data = any(table.get("row_count", 0) > 0 for table in tables.values())
        
        if existing_data and not force:
            logger.warning("Database already contains data. Use --force to overwrite.")
            return {"status": "error", "message": "Database contains data, use --force to overwrite"}
        
        # Initialize database system
        await initialize_database_system(js)
        
        # Run migration
        migrator = JetStreamMigrator(js)
        migration_report = await migrator.migrate_all(backup_before_migration=backup)
        
        logger.info("Migration completed!")
        logger.info(f"Status: {migration_report['status']}")
        logger.info(f"Total migrated: {migration_report['total_migrated']}")
        logger.info(f"Total failed: {migration_report['total_failed']}")
        
        # Show detailed results
        for bucket, result in migration_report.get("migrations", {}).items():
            status = result.get("status", "unknown")
            migrated = result.get("migrated_count", 0)
            failed = result.get("failed_count", 0)
            logger.info(f"  {bucket}: {status} ({migrated} migrated, {failed} failed)")
        
        return migration_report
        
    finally:
        # Close NATS connection
        await nc.close()
        logger.info("NATS connection closed")


async def check_migration_status():
    """Check the current migration status without running migration."""
    logger.info("Checking migration status...")
    
    # Get database status
    db_status = get_database_status()
    
    logger.info(f"Database healthy: {db_status.get('database_healthy', False)}")
    logger.info(f"Database path: {db_status.get('database_path', 'Unknown')}")
    
    # Show table status
    tables = db_status.get("tables", {})
    total_rows = 0
    
    for table_name, table_info in tables.items():
        exists = table_info.get("exists", False)
        row_count = table_info.get("row_count", 0)
        total_rows += row_count
        status = "EXISTS" if exists else "MISSING"
        logger.info(f"  {table_name}: {status} ({row_count} rows)")
    
    logger.info(f"Total rows in database: {total_rows}")
    
    # Check integrity
    integrity = db_status.get("integrity", {})
    integrity_status = integrity.get("status", "unknown")
    logger.info(f"Data integrity: {integrity_status}")
    
    if integrity_status != "healthy":
        violations = integrity.get("foreign_key_violations", [])
        if violations:
            logger.warning(f"Foreign key violations found: {len(violations)}")
    
    return db_status


def main():
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(description="Migrate data from JetStream to DuckDB")
    parser.add_argument(
        "--nats-url", 
        default=os.getenv("NATS_URL", "nats://localhost:4222"),
        help="NATS server URL"
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("DUCKDB_PATH", "/app/data/ekko.db"),
        help="DuckDB database file path"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup before migration"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force migration even if database contains data"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check migration status, don't run migration"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set environment variables
    os.environ["DUCKDB_PATH"] = args.db_path
    os.environ["NATS_URL"] = args.nats_url
    
    async def run():
        try:
            if args.check_only:
                return await check_migration_status()
            else:
                return await run_migration(
                    args.nats_url,
                    backup=not args.no_backup,
                    force=args.force
                )
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return {"status": "error", "error": str(e)}
    
    # Run the migration
    result = asyncio.run(run())
    
    # Exit with appropriate code
    if result.get("status") in ["completed", "no_data"]:
        logger.info("Migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
