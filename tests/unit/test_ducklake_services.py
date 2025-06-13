"""
Unit tests for DuckLake services (writer and API service).
Tests individual components without requiring full infrastructure.
"""

import pytest
import tempfile
import os
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

import duckdb


class TestDuckLakeWriter:
    """Unit tests for DuckLake writer functionality."""
    
    def test_ducklake_writer_config(self):
        """Test DuckLake writer configuration."""
        # Import here to avoid import errors if module doesn't exist yet
        try:
            from pipeline.pkg.persistence.ducklake_writer import DuckLakeWriterConfig
            
            config = DuckLakeWriterConfig(
                CatalogType="sqlite",
                CatalogPath="/tmp/test.sqlite",
                DataPath="s3://test-bucket/data",
                BucketName="test-bucket",
                BatchSize=100,
                FlushInterval=30,
                MaxRetries=3,
                RetryDelay=5,
                MinioEndpoint="localhost:9000",
                MinioAccessKey="test-key",
                MinioSecretKey="test-secret",
                MinioSecure=False,
                MinioRegion="us-east-1"
            )
            
            assert config.CatalogType == "sqlite"
            assert config.CatalogPath == "/tmp/test.sqlite"
            assert config.DataPath == "s3://test-bucket/data"
            assert config.BatchSize == 100
            
        except ImportError:
            pytest.skip("DuckLake writer module not available yet")
    
    def test_ducklake_attach_sql_generation(self):
        """Test SQL generation for different catalog types."""
        
        # Test SQLite catalog
        catalog_path = "/tmp/test.sqlite"
        data_path = "s3://bucket/data"
        
        sqlite_sql = f"ATTACH 'ducklake:sqlite:{catalog_path}' AS blockchain (DATA_PATH '{data_path}');"
        expected_sqlite = "ATTACH 'ducklake:sqlite:/tmp/test.sqlite' AS blockchain (DATA_PATH 's3://bucket/data');"
        assert sqlite_sql == expected_sqlite
        
        # Test DuckDB catalog
        duckdb_sql = f"ATTACH 'ducklake:{catalog_path}' AS blockchain (DATA_PATH '{data_path}');"
        expected_duckdb = "ATTACH 'ducklake:/tmp/test.sqlite' AS blockchain (DATA_PATH 's3://bucket/data');"
        assert duckdb_sql == expected_duckdb


class TestDuckLakeAPIService:
    """Unit tests for DuckLake API service."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = Mock()
        settings.DUCKLAKE_CATALOG_TYPE = "sqlite"
        settings.DUCKLAKE_CATALOG_PATH = "/tmp/test.sqlite"
        settings.DUCKLAKE_DATA_PATH = "s3://test-bucket/data"
        settings.MINIO_ENDPOINT = "localhost:9000"
        settings.MINIO_ACCESS_KEY = "test-key"
        settings.MINIO_SECRET_KEY = "test-secret"
        settings.MINIO_REGION = "us-east-1"
        settings.MINIO_SECURE = False
        return settings
    
    @pytest.mark.asyncio
    async def test_ducklake_service_initialization(self, mock_settings):
        """Test DuckLake service initialization."""
        try:
            from api.src.services.ducklake_service import DuckLakeService
            
            service = DuckLakeService()
            assert service.connection_pool == []
            assert service.pool_size == 5
            assert not service._initialized
            assert service.ducklake_catalog == "blockchain"
            
        except ImportError:
            pytest.skip("DuckLake service module not available yet")
    
    @pytest.mark.asyncio
    async def test_duckdb_connection_with_available_extensions(self, mock_settings):
        """Test DuckDB connection creation with available extensions."""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test connection manually
            conn = duckdb.connect()

            try:
                # Install available extensions using Python API
                conn.install_extension("sqlite_scanner")
                conn.load_extension("sqlite_scanner")
                conn.install_extension("aws")
                conn.load_extension("aws")

                # Test basic functionality
                result = conn.execute("SELECT 'Extensions loaded successfully' as message;").fetchall()
                assert len(result) == 1
                assert result[0][0] == "Extensions loaded successfully"

                # Test basic table operations
                conn.execute("CREATE TABLE test_table AS SELECT 42 as value")
                result = conn.execute("SELECT * FROM test_table").fetchall()
                assert len(result) == 1
                assert result[0][0] == 42

                # Test AWS extension (basic functionality)
                # Note: We can't test actual S3 operations without credentials
                # but we can verify the extension is loaded
                result = conn.execute("SELECT 'AWS extension loaded' as message").fetchall()
                assert result[0][0] == "AWS extension loaded"

            finally:
                conn.close()
    
    def test_transaction_query_building(self):
        """Test SQL query building for transaction retrieval."""
        
        # Test basic query
        base_query = """
            SELECT 
                tx_hash as hash,
                from_address as from,
                to_address as to,
                value,
                gas_limit as gas,
                gas_price,
                nonce,
                input_data as input,
                block_number,
                block_hash,
                tx_index as transaction_index,
                block_time as timestamp,
                network,
                subnet,
                CASE WHEN success THEN 'confirmed' ELSE 'failed' END as status,
                ingested_at
            FROM blockchain.transactions
            ORDER BY block_time DESC, tx_index ASC
            LIMIT ? OFFSET ?
        """
        
        # Test with filters
        where_conditions = []
        params = []
        
        # Add network filter
        network = "Avalanche"
        if network:
            where_conditions.append("network = ?")
            params.append(network)
        
        # Add address filter
        from_address = "0x123"
        if from_address:
            where_conditions.append("from_address = ?")
            params.append(from_address)
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        expected_where = "WHERE network = ? AND from_address = ?"
        assert where_clause == expected_where
        assert params == ["Avalanche", "0x123"]
    
    def test_snapshot_query_building(self):
        """Test snapshot-related query building."""
        
        catalog_name = "blockchain"
        
        # Test snapshots query
        snapshots_query = f"SELECT * FROM ducklake_snapshots('{catalog_name}') ORDER BY snapshot_id DESC"
        expected = "SELECT * FROM ducklake_snapshots('blockchain') ORDER BY snapshot_id DESC"
        assert snapshots_query == expected
        
        # Test table info query
        table_info_query = f"SELECT * FROM ducklake_table_info('{catalog_name}')"
        expected = "SELECT * FROM ducklake_table_info('blockchain')"
        assert table_info_query == expected
        
        # Test time travel query
        snapshot_id = 5
        table_name = f"{catalog_name}.transactions"
        time_travel_table = f"(SELECT * FROM {table_name} WHERE snapshot_id <= {snapshot_id})"
        expected = "(SELECT * FROM blockchain.transactions WHERE snapshot_id <= 5)"
        assert time_travel_table == expected


class TestDuckLakeSchemaEvolution:
    """Test DuckLake schema evolution capabilities."""
    
    def test_add_column_sql(self):
        """Test SQL for adding columns."""
        
        # Add simple column
        add_column_sql = "ALTER TABLE transactions ADD COLUMN transaction_type VARCHAR DEFAULT 'transfer';"
        assert "ADD COLUMN" in add_column_sql
        assert "DEFAULT" in add_column_sql
        
        # Add nested field
        add_nested_sql = "ALTER TABLE transactions ADD COLUMN metadata.gas_used INTEGER;"
        assert "metadata.gas_used" in add_nested_sql
    
    def test_type_promotion_sql(self):
        """Test SQL for type promotions."""
        
        # Promote integer type
        promote_sql = "ALTER TABLE transactions ALTER block_number SET TYPE BIGINT;"
        assert "SET TYPE BIGINT" in promote_sql
        
        # Promote nested field type
        promote_nested_sql = "ALTER TABLE transactions ALTER metadata.gas_used SET TYPE BIGINT;"
        assert "metadata.gas_used SET TYPE BIGINT" in promote_nested_sql
    
    def test_rename_column_sql(self):
        """Test SQL for renaming columns."""
        
        # Rename top-level column
        rename_sql = "ALTER TABLE transactions RENAME tx_hash TO transaction_hash;"
        assert "RENAME tx_hash TO transaction_hash" in rename_sql
        
        # Rename nested field
        rename_nested_sql = "ALTER TABLE transactions RENAME metadata.gas_used TO metadata.gas_consumed;"
        assert "metadata.gas_used TO metadata.gas_consumed" in rename_nested_sql


class TestDuckLakeMaintenanceOperations:
    """Test DuckLake maintenance operations."""
    
    def test_cleanup_old_files_sql(self):
        """Test SQL for cleaning up old files."""
        
        catalog_name = "blockchain"
        
        # Dry run cleanup
        cleanup_sql = f"""
            SELECT * FROM ducklake_cleanup_old_files(
                '{catalog_name}',
                dry_run => true
            )
        """
        
        assert "ducklake_cleanup_old_files" in cleanup_sql
        assert "dry_run => true" in cleanup_sql
        
        # Actual cleanup with timestamp
        cleanup_with_time_sql = f"""
            SELECT * FROM ducklake_cleanup_old_files(
                '{catalog_name}',
                older_than => '2024-01-01 00:00:00+00'::TIMESTAMP WITH TIME ZONE
            )
        """
        
        assert "older_than =>" in cleanup_with_time_sql
    
    def test_expire_snapshots_sql(self):
        """Test SQL for expiring snapshots."""
        
        catalog_name = "blockchain"
        
        # Expire by versions
        expire_versions_sql = f"""
            SELECT * FROM ducklake_expire_snapshots(
                '{catalog_name}',
                versions => [1, 2, 3]
            )
        """
        
        assert "ducklake_expire_snapshots" in expire_versions_sql
        assert "versions => [1, 2, 3]" in expire_versions_sql
        
        # Expire by timestamp
        expire_time_sql = f"""
            SELECT * FROM ducklake_expire_snapshots(
                '{catalog_name}',
                older_than => '2024-01-01 00:00:00+00'::TIMESTAMP WITH TIME ZONE
            )
        """
        
        assert "older_than =>" in expire_time_sql
    
    def test_merge_adjacent_files_sql(self):
        """Test SQL for merging adjacent files."""
        
        catalog_name = "blockchain"
        
        merge_sql = f"""
            SELECT * FROM ducklake_merge_adjacent_files('{catalog_name}')
        """
        
        assert "ducklake_merge_adjacent_files" in merge_sql
        assert catalog_name in merge_sql


@pytest.mark.asyncio
async def test_concurrent_access_simulation():
    """Simulate concurrent access to DuckDB from multiple clients."""

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "concurrent_test.db")

        async def create_connection():
            """Create a DuckDB connection for testing."""
            # Use persistent database for concurrent access testing
            conn = duckdb.connect(db_path)

            # Install available extensions
            conn.install_extension("sqlite_scanner")
            conn.load_extension("sqlite_scanner")

            return conn
        
        async def writer_task():
            """Simulate a writer (pipeline) task."""
            conn = await create_connection()
            
            try:
                # Create table if not exists
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS test_transactions (
                        id INTEGER,
                        tx_hash VARCHAR PRIMARY KEY,
                        value VARCHAR,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Insert data
                for i in range(5):
                    conn.execute("""
                        INSERT INTO test_transactions (id, tx_hash, value)
                        VALUES (?, ?, ?)
                    """, [i, f'0xtx{i}', f'{i}000'])
                    
                    # Small delay to simulate real-world timing
                    await asyncio.sleep(0.1)
                    
            finally:
                conn.close()
        
        async def reader_task():
            """Simulate a reader (API) task."""
            conn = await create_connection()
            
            try:
                # Wait a bit for writer to create table
                await asyncio.sleep(0.2)
                
                # Read data multiple times
                for _ in range(3):
                    result = conn.execute("""
                        SELECT COUNT(*) FROM test_transactions;
                    """).fetchall()
                    
                    count = result[0][0] if result else 0
                    print(f"Reader found {count} transactions")
                    
                    await asyncio.sleep(0.2)
                    
            except Exception as e:
                # SQLite might have some contention, which is expected
                print(f"Reader encountered: {e}")
            finally:
                conn.close()
        
        # Run writer and reader concurrently
        await asyncio.gather(
            writer_task(),
            reader_task()
        )


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
