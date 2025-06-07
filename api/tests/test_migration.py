"""Tests for database migration functionality."""

import pytest
import uuid
import json
from datetime import datetime

from app.database.migrations import MigrationManager
from app.migrations.migrate_from_jetstream import JetStreamMigrator
from app.models import User, UserInDB, Wallet, Alert, WalletBalance


class TestMigrationManager:
    """Test MigrationManager functionality."""
    
    def test_check_table_exists(self, db_schema):
        """Test checking if tables exist."""
        migration_manager = MigrationManager()
        
        # Check that required tables exist
        assert migration_manager.check_table_exists("users") is True
        assert migration_manager.check_table_exists("wallets") is True
        assert migration_manager.check_table_exists("alerts") is True
        assert migration_manager.check_table_exists("wallet_balances") is True
        
        # Check non-existent table
        assert migration_manager.check_table_exists("non_existent_table") is False
    
    def test_get_table_row_count(self, db_schema):
        """Test getting table row counts."""
        migration_manager = MigrationManager()
        
        # Initially tables should be empty
        assert migration_manager.get_table_row_count("users") == 0
        assert migration_manager.get_table_row_count("wallets") == 0
        assert migration_manager.get_table_row_count("alerts") == 0
        
        # Non-existent table should return 0
        assert migration_manager.get_table_row_count("non_existent_table") == 0
    
    def test_validate_data_integrity(self, db_schema):
        """Test data integrity validation."""
        migration_manager = MigrationManager()
        
        integrity_report = migration_manager.validate_data_integrity()
        
        assert "timestamp" in integrity_report
        assert "tables" in integrity_report
        assert "foreign_key_violations" in integrity_report
        assert "status" in integrity_report
        
        # With empty tables, should be healthy
        assert integrity_report["status"] == "healthy"
        
        # Check table information
        tables = integrity_report["tables"]
        assert "users" in tables
        assert "wallets" in tables
        assert "alerts" in tables
        assert "wallet_balances" in tables
        
        for table_name, table_info in tables.items():
            assert table_info["exists"] is True
            assert table_info["row_count"] == 0


class TestJetStreamMigrator:
    """Test JetStream to DuckDB migration."""
    
    @pytest.mark.asyncio
    async def test_migrate_users(self, jetstream, db_schema):
        """Test migrating users from JetStream to DuckDB."""
        migrator = JetStreamMigrator(jetstream)
        
        # Create test user data in JetStream
        test_users = []
        for i in range(2):
            user_data = {
                "id": str(uuid.uuid4()),
                "email": f"test{i}@example.com",
                "full_name": f"Test User {i}",
                "role": "user",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "hashed_password": "$2b$12$example_hashed_password"
            }
            test_users.append(user_data)
            
            # Store in JetStream KV
            kv = await jetstream.key_value(bucket="users")
            await kv.put(user_data["id"], json.dumps(user_data).encode('utf-8'))
        
        # Run user migration
        result = await migrator._migrate_users()
        
        assert result["status"] == "completed"
        assert result["migrated_count"] == 2
        assert result["failed_count"] == 0
        
        # Verify users were migrated to database
        migration_manager = MigrationManager()
        user_count = migration_manager.get_table_row_count("users")
        assert user_count == 2
    
    @pytest.mark.asyncio
    async def test_migrate_wallets(self, jetstream, db_schema):
        """Test migrating wallets from JetStream to DuckDB."""
        migrator = JetStreamMigrator(jetstream)
        
        # Create test wallet data in JetStream
        test_wallets = []
        for i in range(2):
            wallet_data = {
                "id": str(uuid.uuid4()),
                "blockchain_symbol": "ETH",
                "address": f"0x{uuid.uuid4().hex[:40]}",
                "name": f"Test Wallet {i}",
                "balance": float(i + 1),
                "status": "active",
                "created_at": datetime.now().isoformat()
            }
            test_wallets.append(wallet_data)
            
            # Store in JetStream KV
            kv = await jetstream.key_value(bucket="wallets")
            await kv.put(wallet_data["id"], json.dumps(wallet_data).encode('utf-8'))
        
        # Run wallet migration
        result = await migrator._migrate_wallets()
        
        assert result["status"] == "completed"
        assert result["migrated_count"] == 2
        assert result["failed_count"] == 0
        
        # Verify wallets were migrated to database
        migration_manager = MigrationManager()
        wallet_count = migration_manager.get_table_row_count("wallets")
        assert wallet_count == 2
    
    @pytest.mark.asyncio
    async def test_migrate_alerts(self, jetstream, db_schema):
        """Test migrating alerts from JetStream to DuckDB."""
        migrator = JetStreamMigrator(jetstream)
        
        # Create test alert data in JetStream
        test_alerts = []
        for i in range(2):
            alert_data = {
                "id": str(uuid.uuid4()),
                "type": "transaction",
                "message": f"Test alert {i}",
                "time": datetime.now().isoformat(),
                "status": "new",
                "icon": "warning",
                "priority": "high",
                "notifications_enabled": True
            }
            test_alerts.append(alert_data)
            
            # Store in JetStream KV
            kv = await jetstream.key_value(bucket="alerts")
            await kv.put(alert_data["id"], json.dumps(alert_data).encode('utf-8'))
        
        # Run alert migration
        result = await migrator._migrate_alerts()
        
        assert result["status"] == "completed"
        assert result["migrated_count"] == 2
        assert result["failed_count"] == 0
        
        # Verify alerts were migrated to database
        migration_manager = MigrationManager()
        alert_count = migration_manager.get_table_row_count("alerts")
        assert alert_count == 2
    
    @pytest.mark.asyncio
    async def test_migrate_wallet_balances(self, jetstream, db_schema):
        """Test migrating wallet balances from JetStream to DuckDB."""
        migrator = JetStreamMigrator(jetstream)
        
        # Create test wallet balance data in JetStream
        test_balances = []
        for i in range(2):
            balance_data = {
                "id": str(uuid.uuid4()),
                "wallet_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "balance": float(i + 1),
                "token_price": 2000.0,
                "fiat_value": float((i + 1) * 2000)
            }
            test_balances.append(balance_data)
            
            # Store in JetStream KV
            kv = await jetstream.key_value(bucket="wallet_balances")
            await kv.put(balance_data["id"], json.dumps(balance_data).encode('utf-8'))
        
        # Run wallet balance migration
        result = await migrator._migrate_wallet_balances()
        
        assert result["status"] == "completed"
        assert result["migrated_count"] == 2
        assert result["failed_count"] == 0
        
        # Verify wallet balances were migrated to database
        migration_manager = MigrationManager()
        balance_count = migration_manager.get_table_row_count("wallet_balances")
        assert balance_count == 2
    
    @pytest.mark.asyncio
    async def test_migrate_all(self, jetstream, db_schema):
        """Test complete migration of all data types."""
        migrator = JetStreamMigrator(jetstream)
        
        # Create test data in all JetStream buckets
        buckets_data = {
            "users": {
                "id": str(uuid.uuid4()),
                "email": "test@example.com",
                "full_name": "Test User",
                "role": "user",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "hashed_password": "$2b$12$example_hashed_password"
            },
            "wallets": {
                "id": str(uuid.uuid4()),
                "blockchain_symbol": "ETH",
                "address": "0x1234567890abcdef1234567890abcdef12345678",
                "name": "Test Wallet",
                "balance": 1.0,
                "status": "active",
                "created_at": datetime.now().isoformat()
            },
            "alerts": {
                "id": str(uuid.uuid4()),
                "type": "transaction",
                "message": "Test alert",
                "time": datetime.now().isoformat(),
                "status": "new",
                "notifications_enabled": True
            },
            "wallet_balances": {
                "id": str(uuid.uuid4()),
                "wallet_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "balance": 1.0
            }
        }
        
        # Store data in JetStream KV stores
        for bucket, data in buckets_data.items():
            kv = await jetstream.key_value(bucket=bucket)
            await kv.put(data["id"], json.dumps(data).encode('utf-8'))
        
        # Run complete migration
        migration_report = await migrator.migrate_all(backup_before_migration=False)
        
        assert migration_report["status"] == "completed"
        assert migration_report["total_migrated"] == 4
        assert migration_report["total_failed"] == 0
        
        # Verify all data was migrated
        migration_manager = MigrationManager()
        assert migration_manager.get_table_row_count("users") == 1
        assert migration_manager.get_table_row_count("wallets") == 1
        assert migration_manager.get_table_row_count("alerts") == 1
        assert migration_manager.get_table_row_count("wallet_balances") == 1
        
        # Check integrity after migration
        integrity_report = migration_manager.validate_data_integrity()
        assert integrity_report["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_migration_with_invalid_data(self, jetstream, db_schema):
        """Test migration handling of invalid data."""
        migrator = JetStreamMigrator(jetstream)
        
        # Create invalid user data (missing required fields)
        invalid_user_data = {
            "id": str(uuid.uuid4()),
            "email": "invalid-email-format"  # Missing other required fields
        }
        
        # Store invalid data in JetStream KV
        kv = await jetstream.key_value(bucket="users")
        await kv.put(invalid_user_data["id"], json.dumps(invalid_user_data).encode('utf-8'))
        
        # Run user migration
        result = await migrator._migrate_users()
        
        # Should handle the error gracefully
        assert result["status"] == "completed"
        assert result["failed_count"] == 1
        assert len(result["failed_entities"]) == 1
        
        # Verify no invalid data was migrated
        migration_manager = MigrationManager()
        user_count = migration_manager.get_table_row_count("users")
        assert user_count == 0
    
    @pytest.mark.asyncio
    async def test_migration_empty_buckets(self, jetstream, db_schema):
        """Test migration with empty JetStream buckets."""
        migrator = JetStreamMigrator(jetstream)
        
        # Run migration on empty buckets
        migration_report = await migrator.migrate_all(backup_before_migration=False)
        
        assert migration_report["status"] == "completed"
        assert migration_report["total_migrated"] == 0
        assert migration_report["total_failed"] == 0
        
        # All migration results should show 0 migrated
        for bucket, result in migration_report["migrations"].items():
            assert result["migrated_count"] == 0
            assert result["failed_count"] == 0
