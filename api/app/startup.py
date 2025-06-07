"""Startup utilities for database initialization and migration."""

import os
import logging
from typing import Any

from .database.connection import get_db_manager
from .database.migrations import MigrationManager
from .migrations.migrate_from_jetstream import JetStreamMigrator

logger = logging.getLogger(__name__)


async def initialize_database_system(jetstream_context: Any = None):
    """Initialize the database system and run migrations if needed."""
    try:
        logger.info("Initializing database system...")
        
        # Initialize database manager
        db_manager = get_db_manager()
        
        # Check database health
        if not db_manager.health_check():
            raise Exception("Database health check failed")
        
        logger.info("Database connection established successfully")
        
        # Initialize database schema
        migration_manager = MigrationManager()
        
        # Check if tables exist
        tables_exist = all([
            migration_manager.check_table_exists("users"),
            migration_manager.check_table_exists("wallets"),
            migration_manager.check_table_exists("alerts"),
            migration_manager.check_table_exists("wallet_balances")
        ])
        
        if not tables_exist:
            logger.info("Database tables not found, initializing schema...")
            migration_manager.initialize_database()
            logger.info("Database schema initialized successfully")
        else:
            logger.info("Database tables already exist")
        
        # Check if migration from JetStream is needed
        migration_mode = os.getenv("MIGRATION_MODE", "false").lower() == "true"
        
        if migration_mode and jetstream_context:
            logger.info("Migration mode enabled, checking for JetStream data...")
            
            # Check if database is empty (indicating fresh installation)
            user_count = migration_manager.get_table_row_count("users")
            wallet_count = migration_manager.get_table_row_count("wallets")
            alert_count = migration_manager.get_table_row_count("alerts")
            
            if user_count == 0 and wallet_count == 0 and alert_count == 0:
                logger.info("Database is empty, running JetStream migration...")
                
                migrator = JetStreamMigrator(jetstream_context)
                migration_report = await migrator.migrate_all(backup_before_migration=True)
                
                if migration_report["status"] == "completed":
                    logger.info(f"Migration completed successfully. Migrated {migration_report['total_migrated']} entities")
                else:
                    logger.error(f"Migration failed: {migration_report.get('error', 'Unknown error')}")
            else:
                logger.info("Database contains data, skipping migration")
        
        # Validate data integrity
        integrity_report = migration_manager.validate_data_integrity()
        if integrity_report["status"] == "healthy":
            logger.info("Database integrity validation passed")
        else:
            logger.warning(f"Database integrity issues found: {integrity_report}")
        
        logger.info("Database system initialization completed")
        
    except Exception as e:
        logger.error(f"Failed to initialize database system: {e}")
        raise


async def cleanup_database_system():
    """Cleanup database connections and resources."""
    try:
        logger.info("Cleaning up database system...")
        
        db_manager = get_db_manager()
        db_manager.close_all_connections()
        
        logger.info("Database system cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")


def get_database_status() -> dict:
    """Get current database system status."""
    try:
        db_manager = get_db_manager()
        migration_manager = MigrationManager()
        
        # Check database health
        is_healthy = db_manager.health_check()
        
        # Check table existence
        tables = ["users", "wallets", "alerts", "wallet_balances"]
        table_status = {}
        
        for table in tables:
            table_status[table] = {
                "exists": migration_manager.check_table_exists(table),
                "row_count": migration_manager.get_table_row_count(table) if migration_manager.check_table_exists(table) else 0
            }
        
        # Get integrity status
        integrity_report = migration_manager.validate_data_integrity()
        
        return {
            "database_healthy": is_healthy,
            "database_path": db_manager.db_path,
            "tables": table_status,
            "integrity": integrity_report,
            "migration_mode": os.getenv("MIGRATION_MODE", "false").lower() == "true",
            "jetstream_sync_enabled": os.getenv("ENABLE_JETSTREAM_SYNC", "true").lower() == "true"
        }
        
    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        return {
            "database_healthy": False,
            "error": str(e)
        }
