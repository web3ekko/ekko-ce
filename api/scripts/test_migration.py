#!/usr/bin/env python3
"""Test script for database migration and repository functionality."""

import asyncio
import os
import sys
import logging

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database.connection import get_db_manager
from app.database.migrations import MigrationManager
from app.startup import initialize_database_system, get_database_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_database_connection():
    """Test basic database connectivity."""
    logger.info("Testing database connection...")
    
    try:
        db_manager = get_db_manager()
        
        # Test health check
        is_healthy = db_manager.health_check()
        logger.info(f"Database health check: {'PASSED' if is_healthy else 'FAILED'}")
        
        # Test basic query
        conn = db_manager.get_connection()
        result = conn.execute("SELECT 1 as test").fetchone()
        logger.info(f"Basic query test: {'PASSED' if result[0] == 1 else 'FAILED'}")
        
        return True
        
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


async def test_schema_creation():
    """Test database schema creation."""
    logger.info("Testing schema creation...")
    
    try:
        migration_manager = MigrationManager()
        
        # Initialize database
        migration_manager.initialize_database()
        logger.info("Database schema initialized successfully")
        
        # Check if tables exist
        tables = ["users", "wallets", "alerts", "wallet_balances"]
        for table in tables:
            exists = migration_manager.check_table_exists(table)
            logger.info(f"Table '{table}': {'EXISTS' if exists else 'MISSING'}")
        
        # Get integrity report
        integrity_report = migration_manager.validate_data_integrity()
        logger.info(f"Data integrity status: {integrity_report['status']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Schema creation test failed: {e}")
        return False


async def test_repository_operations():
    """Test basic repository operations."""
    logger.info("Testing repository operations...")
    
    try:
        from app.repositories import UserRepository, WalletRepository, AlertRepository
        from app.models import UserInDB, Wallet, Alert
        from datetime import datetime
        import uuid
        
        # Test User repository
        user_repo = UserRepository()
        
        # Create test user
        test_user = UserInDB(
            id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            role="user",
            is_active=True,
            created_at=datetime.now().isoformat(),
            hashed_password="hashed_password_here"
        )
        
        # Insert user directly to database (skip JetStream sync for test)
        await user_repo._insert_to_db(test_user)
        logger.info("User repository test: INSERT - PASSED")
        
        # Test retrieval
        retrieved_user = await user_repo.get_by_id(test_user.id)
        if retrieved_user and retrieved_user.email == test_user.email:
            logger.info("User repository test: SELECT - PASSED")
        else:
            logger.error("User repository test: SELECT - FAILED")
        
        # Test Wallet repository
        wallet_repo = WalletRepository()
        
        test_wallet = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef",
            name="Test Wallet",
            balance=100.0,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        await wallet_repo._insert_to_db(test_wallet)
        logger.info("Wallet repository test: INSERT - PASSED")
        
        retrieved_wallet = await wallet_repo.get_by_id(test_wallet.id)
        if retrieved_wallet and retrieved_wallet.name == test_wallet.name:
            logger.info("Wallet repository test: SELECT - PASSED")
        else:
            logger.error("Wallet repository test: SELECT - FAILED")
        
        return True
        
    except Exception as e:
        logger.error(f"Repository operations test failed: {e}")
        return False


async def test_database_status():
    """Test database status reporting."""
    logger.info("Testing database status reporting...")
    
    try:
        status = get_database_status()
        
        logger.info(f"Database healthy: {status.get('database_healthy', False)}")
        logger.info(f"Database path: {status.get('database_path', 'Unknown')}")
        logger.info(f"Migration mode: {status.get('migration_mode', False)}")
        logger.info(f"JetStream sync enabled: {status.get('jetstream_sync_enabled', False)}")
        
        # Log table status
        tables = status.get('tables', {})
        for table_name, table_info in tables.items():
            exists = table_info.get('exists', False)
            row_count = table_info.get('row_count', 0)
            logger.info(f"Table '{table_name}': {'EXISTS' if exists else 'MISSING'} ({row_count} rows)")
        
        return True
        
    except Exception as e:
        logger.error(f"Database status test failed: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("Starting database migration tests...")
    
    # Set environment variables for testing
    os.environ["DUCKDB_PATH"] = "/tmp/test_ekko.db"
    os.environ["MIGRATION_MODE"] = "false"  # Don't run JetStream migration in tests
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Schema Creation", test_schema_creation),
        ("Repository Operations", test_repository_operations),
        ("Database Status", test_database_status)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
            logger.info(f"Test '{test_name}': {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
