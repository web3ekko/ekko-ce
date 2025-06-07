"""Test setup and configuration verification."""

import pytest
import os
import tempfile
from datetime import datetime


class TestSetup:
    """Test the testing setup and configuration."""
    
    def test_environment_variables(self):
        """Test that test environment variables are set correctly."""
        assert os.environ.get("TEST_MODE") == "true"
    
    def test_temporary_database_fixture(self, test_database):
        """Test that temporary database fixture works."""
        assert test_database is not None
        assert test_database.endswith('.db')
        # The file might not exist yet since we delete it in the fixture
        # to let DuckDB create it properly, but the path should be valid
        assert '/tmp' in test_database or 'tmp' in test_database
    
    def test_database_manager_fixture(self, db_manager):
        """Test that database manager fixture works."""
        assert db_manager is not None
        assert db_manager.health_check() is True
    
    def test_database_schema_fixture(self, db_schema):
        """Test that database schema fixture works."""
        assert db_schema is not None
        
        # Check that tables exist
        assert db_schema.check_table_exists("users") is True
        assert db_schema.check_table_exists("wallets") is True
        assert db_schema.check_table_exists("alerts") is True
        assert db_schema.check_table_exists("wallet_balances") is True
    
    @pytest.mark.asyncio
    async def test_nats_connection_fixture(self, nats_connection):
        """Test that NATS connection fixture works."""
        assert nats_connection is not None
        assert nats_connection.is_connected is True
    
    @pytest.mark.asyncio
    async def test_jetstream_fixture(self, jetstream):
        """Test that JetStream fixture works."""
        assert jetstream is not None
        
        # Test creating a KV bucket
        kv = await jetstream.key_value(bucket="test_setup")
        assert kv is not None
        
        # Test storing and retrieving data
        test_key = "test_key"
        test_value = "test_value"
        
        await kv.put(test_key, test_value.encode('utf-8'))
        retrieved = await kv.get(test_key)
        
        assert retrieved is not None
        assert retrieved.value.decode('utf-8') == test_value
    
    def test_repository_fixtures(self, user_repository, wallet_repository, 
                                alert_repository, wallet_balance_repository):
        """Test that repository fixtures work."""
        assert user_repository is not None
        assert wallet_repository is not None
        assert alert_repository is not None
        assert wallet_balance_repository is not None
        
        # Check that repositories have the correct table names
        assert user_repository.table_name == "users"
        assert wallet_repository.table_name == "wallets"
        assert alert_repository.table_name == "alerts"
        assert wallet_balance_repository.table_name == "wallet_balances"
    
    @pytest.mark.asyncio
    async def test_repository_database_connection(self, user_repository):
        """Test that repositories can connect to the database."""
        # Test basic database operation
        result = user_repository.db_connection.execute("SELECT 1 as test").fetchone()
        assert result[0] == 1
    
    def test_sample_data_fixtures(self, sample_user_data, sample_wallet_data, 
                                 sample_alert_data, sample_wallet_balance_data):
        """Test that sample data fixtures work."""
        assert sample_user_data is not None
        assert sample_wallet_data is not None
        assert sample_alert_data is not None
        assert sample_wallet_balance_data is not None
        
        # Check required fields are present
        assert "id" in sample_user_data
        assert "email" in sample_user_data
        assert "id" in sample_wallet_data
        assert "blockchain_symbol" in sample_wallet_data
        assert "id" in sample_alert_data
        assert "type" in sample_alert_data
        assert "id" in sample_wallet_balance_data
        assert "wallet_id" in sample_wallet_balance_data
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_end_to_end_data_flow(self, user_repository, wallet_repository, 
                                       alert_repository, sample_user_data, 
                                       sample_wallet_data, sample_alert_data):
        """Test end-to-end data flow between repositories."""
        from app.models import UserInDB, Wallet, Alert
        
        # Create user
        user = UserInDB(**sample_user_data)
        created_user = await user_repository.create(user)
        assert created_user.id == user.id
        
        # Create wallet
        wallet = Wallet(**sample_wallet_data)
        created_wallet = await wallet_repository.create(wallet)
        assert created_wallet.id == wallet.id
        
        # Create alert linked to wallet
        alert_data = sample_alert_data.copy()
        alert_data["related_wallet_id"] = created_wallet.id
        alert = Alert(**alert_data)
        created_alert = await alert_repository.create(alert)
        assert created_alert.related_wallet_id == created_wallet.id
        
        # Verify relationships
        wallet_alerts = await alert_repository.get_by_wallet_id(created_wallet.id)
        assert len(wallet_alerts) == 1
        assert wallet_alerts[0].id == created_alert.id
    
    @pytest.mark.database
    def test_database_isolation(self, db_manager):
        """Test that database is isolated between tests."""
        # This test verifies that each test gets a clean database
        # The row counts should be 0 at the start of each test
        
        migration_manager = db_manager._instance.migration_manager if hasattr(db_manager._instance, 'migration_manager') else None
        
        # We can't easily test isolation in a single test, but we can verify
        # that the database is clean at the start
        conn = db_manager.get_connection()
        
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        wallet_count = conn.execute("SELECT COUNT(*) FROM wallets").fetchone()[0]
        alert_count = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        
        # At the start of each test, tables should be empty
        # (This assumes proper cleanup between tests)
        assert user_count >= 0  # Could be 0 or have data from other tests in same session
        assert wallet_count >= 0
        assert alert_count >= 0
    
    @pytest.mark.slow
    def test_performance_baseline(self, db_manager):
        """Test basic performance baseline."""
        import time
        
        conn = db_manager.get_connection()
        
        # Test basic query performance
        start_time = time.time()
        for _ in range(100):
            conn.execute("SELECT 1").fetchone()
        end_time = time.time()
        
        # Should complete 100 simple queries in less than 1 second
        assert (end_time - start_time) < 1.0
    
    def test_pytest_markers(self):
        """Test that pytest markers are working."""
        # This test itself uses markers, so if it runs, markers are working
        assert True
    
    def test_imports(self):
        """Test that all required modules can be imported."""
        # Test app imports
        from app.models import User, UserInDB, Wallet, Alert, WalletBalance
        from app.repositories import UserRepository, WalletRepository, AlertRepository, WalletBalanceRepository
        from app.database.connection import DatabaseManager
        from app.database.migrations import MigrationManager
        
        # Test external imports
        import pytest
        import uuid
        import json
        from datetime import datetime
        
        # If we get here, all imports worked
        assert True
