"""Migration script to migrate data from JetStream KV stores to DuckDB."""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

from ..database.connection import get_db_connection
from ..database.migrations import MigrationManager
from ..models import User, UserInDB, Wallet, Alert, WalletBalance
from ..repositories import UserRepository, WalletRepository, AlertRepository, WalletBalanceRepository

logger = logging.getLogger(__name__)


class JetStreamMigrator:
    """Migrates data from JetStream KV stores to DuckDB."""
    
    def __init__(self, jetstream_context):
        self.js = jetstream_context
        self.db_connection = get_db_connection()
        self.migration_manager = MigrationManager()
        
        # Initialize repositories
        self.user_repo = UserRepository()
        self.wallet_repo = WalletRepository()
        self.alert_repo = AlertRepository()
        self.wallet_balance_repo = WalletBalanceRepository()
        
        # Set JetStream context for repositories
        self.user_repo.set_jetstream(self.js)
        self.wallet_repo.set_jetstream(self.js)
        self.alert_repo.set_jetstream(self.js)
        self.wallet_balance_repo.set_jetstream(self.js)
    
    async def migrate_all(self, backup_before_migration: bool = True) -> Dict[str, Any]:
        """Migrate all data from JetStream KV stores to DuckDB."""
        migration_report = {
            "started_at": datetime.now().isoformat(),
            "backup_created": False,
            "database_initialized": False,
            "migrations": {},
            "total_migrated": 0,
            "total_failed": 0,
            "status": "started"
        }
        
        try:
            logger.info("Starting JetStream to DuckDB migration...")
            
            # Create backup if requested
            if backup_before_migration:
                await self._create_backup()
                migration_report["backup_created"] = True
                logger.info("Backup created successfully")
            
            # Initialize database schema
            self.migration_manager.initialize_database()
            migration_report["database_initialized"] = True
            logger.info("Database schema initialized")
            
            # Migrate each entity type
            buckets_to_migrate = [
                ("users", self._migrate_users),
                ("wallets", self._migrate_wallets),
                ("alerts", self._migrate_alerts),
                ("wallet_balances", self._migrate_wallet_balances)
            ]
            
            for bucket_name, migrate_func in buckets_to_migrate:
                try:
                    logger.info(f"Migrating {bucket_name}...")
                    result = await migrate_func()
                    migration_report["migrations"][bucket_name] = result
                    migration_report["total_migrated"] += result.get("migrated_count", 0)
                    migration_report["total_failed"] += result.get("failed_count", 0)
                    logger.info(f"Completed migration for {bucket_name}: {result}")
                except Exception as e:
                    logger.error(f"Failed to migrate {bucket_name}: {e}")
                    migration_report["migrations"][bucket_name] = {
                        "status": "failed",
                        "error": str(e),
                        "migrated_count": 0,
                        "failed_count": 0
                    }
            
            # Validate data integrity
            integrity_report = self.migration_manager.validate_data_integrity()
            migration_report["integrity_check"] = integrity_report
            
            migration_report["completed_at"] = datetime.now().isoformat()
            migration_report["status"] = "completed"
            
            logger.info(f"Migration completed. Total migrated: {migration_report['total_migrated']}, Failed: {migration_report['total_failed']}")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            migration_report["status"] = "failed"
            migration_report["error"] = str(e)
            migration_report["completed_at"] = datetime.now().isoformat()
        
        return migration_report
    
    async def _migrate_users(self) -> Dict[str, Any]:
        """Migrate users from JetStream KV to DuckDB."""
        result = {
            "bucket": "users",
            "migrated_count": 0,
            "failed_count": 0,
            "failed_entities": [],
            "status": "started"
        }
        
        try:
            # Get all users from JetStream KV
            kv = await self.js.key_value(bucket="users")
            keys = await kv.keys()
            
            for key in keys:
                try:
                    data = await kv.get(key)
                    if data and data.value:
                        # Decode and parse user data
                        if isinstance(data.value, bytes):
                            json_str = data.value.decode('utf-8')
                        else:
                            json_str = data.value
                        
                        user_data = json.loads(json_str)
                        
                        # Ensure required fields
                        if not user_data.get('id'):
                            user_data['id'] = key
                        
                        # Create UserInDB instance
                        user = UserInDB(**user_data)
                        
                        # Insert directly to database (skip JetStream sync during migration)
                        await self.user_repo._insert_to_db(user)
                        result["migrated_count"] += 1
                        
                        logger.debug(f"Migrated user: {user.id}")
                        
                except Exception as e:
                    logger.error(f"Failed to migrate user {key}: {e}")
                    result["failed_count"] += 1
                    result["failed_entities"].append({"key": key, "error": str(e)})
            
            result["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Error migrating users: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    async def _migrate_wallets(self) -> Dict[str, Any]:
        """Migrate wallets from JetStream KV to DuckDB."""
        result = {
            "bucket": "wallets",
            "migrated_count": 0,
            "failed_count": 0,
            "failed_entities": [],
            "status": "started"
        }
        
        try:
            kv = await self.js.key_value(bucket="wallets")
            keys = await kv.keys()
            
            for key in keys:
                try:
                    data = await kv.get(key)
                    if data and data.value:
                        if isinstance(data.value, bytes):
                            json_str = data.value.decode('utf-8')
                        else:
                            json_str = data.value
                        
                        wallet_data = json.loads(json_str)
                        
                        # Ensure required fields
                        if not wallet_data.get('id'):
                            wallet_data['id'] = key
                        
                        # Set default values for missing fields
                        wallet_data.setdefault('balance', 0.0)
                        wallet_data.setdefault('status', 'active')
                        
                        # Create Wallet instance
                        wallet = Wallet(**wallet_data)
                        
                        # Insert directly to database
                        await self.wallet_repo._insert_to_db(wallet)
                        result["migrated_count"] += 1
                        
                        logger.debug(f"Migrated wallet: {wallet.id}")
                        
                except Exception as e:
                    logger.error(f"Failed to migrate wallet {key}: {e}")
                    result["failed_count"] += 1
                    result["failed_entities"].append({"key": key, "error": str(e)})
            
            result["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Error migrating wallets: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    async def _migrate_alerts(self) -> Dict[str, Any]:
        """Migrate alerts from JetStream KV to DuckDB."""
        result = {
            "bucket": "alerts",
            "migrated_count": 0,
            "failed_count": 0,
            "failed_entities": [],
            "status": "started"
        }
        
        try:
            kv = await self.js.key_value(bucket="alerts")
            keys = await kv.keys()
            
            for key in keys:
                try:
                    data = await kv.get(key)
                    if data and data.value:
                        if isinstance(data.value, bytes):
                            json_str = data.value.decode('utf-8')
                        else:
                            json_str = data.value
                        
                        alert_data = json.loads(json_str)
                        
                        # Ensure required fields
                        if not alert_data.get('id'):
                            alert_data['id'] = key
                        
                        # Set default values for missing fields
                        alert_data.setdefault('notifications_enabled', True)
                        
                        # Create Alert instance
                        alert = Alert(**alert_data)
                        
                        # Insert directly to database
                        await self.alert_repo._insert_to_db(alert)
                        result["migrated_count"] += 1
                        
                        logger.debug(f"Migrated alert: {alert.id}")
                        
                except Exception as e:
                    logger.error(f"Failed to migrate alert {key}: {e}")
                    result["failed_count"] += 1
                    result["failed_entities"].append({"key": key, "error": str(e)})
            
            result["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Error migrating alerts: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    async def _migrate_wallet_balances(self) -> Dict[str, Any]:
        """Migrate wallet balances from JetStream KV to DuckDB."""
        result = {
            "bucket": "wallet_balances",
            "migrated_count": 0,
            "failed_count": 0,
            "failed_entities": [],
            "status": "started"
        }
        
        try:
            kv = await self.js.key_value(bucket="wallet_balances")
            keys = await kv.keys()
            
            for key in keys:
                try:
                    data = await kv.get(key)
                    if data and data.value:
                        if isinstance(data.value, bytes):
                            json_str = data.value.decode('utf-8')
                        else:
                            json_str = data.value
                        
                        balance_data = json.loads(json_str)
                        
                        # Ensure required fields
                        if not balance_data.get('id'):
                            balance_data['id'] = key
                        
                        # Create WalletBalance instance
                        wallet_balance = WalletBalance(**balance_data)
                        
                        # Insert directly to database
                        await self.wallet_balance_repo._insert_to_db(wallet_balance)
                        result["migrated_count"] += 1
                        
                        logger.debug(f"Migrated wallet balance: {wallet_balance.id}")
                        
                except Exception as e:
                    logger.error(f"Failed to migrate wallet balance {key}: {e}")
                    result["failed_count"] += 1
                    result["failed_entities"].append({"key": key, "error": str(e)})
            
            result["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Error migrating wallet balances: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    async def _create_backup(self):
        """Create backup of existing data before migration."""
        try:
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup each KV bucket
            buckets = ["users", "wallets", "alerts", "wallet_balances"]
            
            for bucket in buckets:
                try:
                    backup_path = f"/app/data/backup_{bucket}_{backup_timestamp}.json"
                    await self._backup_kv_bucket(bucket, backup_path)
                    logger.info(f"Backed up {bucket} to {backup_path}")
                except Exception as e:
                    logger.warning(f"Failed to backup {bucket}: {e}")
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            raise
    
    async def _backup_kv_bucket(self, bucket: str, backup_path: str):
        """Backup a single KV bucket to JSON file."""
        try:
            kv = await self.js.key_value(bucket=bucket)
            keys = await kv.keys()
            
            backup_data = {}
            for key in keys:
                try:
                    data = await kv.get(key)
                    if data and data.value:
                        if isinstance(data.value, bytes):
                            json_str = data.value.decode('utf-8')
                        else:
                            json_str = data.value
                        
                        backup_data[key] = json.loads(json_str)
                except Exception as e:
                    logger.warning(f"Failed to backup key {key} from {bucket}: {e}")
            
            # Write backup to file
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"Error backing up bucket {bucket}: {e}")
            raise
