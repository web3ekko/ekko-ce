"""
Tests for the DuckDB service.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import duckdb
from datetime import datetime

from src.services.duckdb_service import DuckDBService, get_duckdb_service

class TestDuckDBService:
    """Test class for DuckDB service."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh DuckDB service instance for testing."""
        return DuckDBService()
    
    @pytest.fixture
    def mock_connection(self):
        """Mock DuckDB connection."""
        conn = Mock()
        conn.execute.return_value.fetchall.return_value = [
            ('0x123', '0xabc', '0xdef', '1000000000000000000', '21000', '20000000000', 
             '42', '0x', 18500000, '0xblock123', 0, datetime.now(), 'avalanche', 
             'mainnet', 'confirmed', None, 'AVAX', 'send')
        ]
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.description = [
            ('hash',), ('from_address',), ('to_address',), ('value',), ('gas',), 
            ('gas_price',), ('nonce',), ('input',), ('block_number',), ('block_hash',), 
            ('transaction_index',), ('timestamp',), ('network',), ('subnet',), 
            ('status',), ('decoded_call',), ('token_symbol',), ('transaction_type',)
        ]
        return conn
    
    @pytest.mark.asyncio
    async def test_initialize_service(self, service):
        """Test service initialization."""
        with patch.object(service, '_create_connection') as mock_create:
            mock_create.return_value = Mock()
            
            await service.initialize()
            
            assert service._initialized == True
            assert len(service.connection_pool) == service.pool_size
            assert mock_create.call_count == service.pool_size
    
    @pytest.mark.asyncio
    async def test_create_connection(self, service):
        """Test DuckDB connection creation."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            conn = await service._create_connection()
            
            assert conn == mock_conn
            # Verify extensions are installed
            mock_conn.execute.assert_any_call("INSTALL httpfs;")
            mock_conn.execute.assert_any_call("LOAD httpfs;")
    
    @pytest.mark.asyncio
    async def test_execute_query_success(self, service, mock_connection):
        """Test successful query execution."""
        service.connection_pool = [mock_connection]
        service._initialized = True
        
        query = "SELECT * FROM transactions LIMIT 1"
        result = await service.execute_query(query)
        
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert 'hash' in result[0]
        assert result[0]['hash'] == '0x123'
    
    @pytest.mark.asyncio
    async def test_execute_query_with_params(self, service, mock_connection):
        """Test query execution with parameters."""
        service.connection_pool = [mock_connection]
        service._initialized = True
        
        query = "SELECT * FROM transactions WHERE hash = $1"
        params = ['0x123']
        
        result = await service.execute_query(query, params)
        
        mock_connection.execute.assert_called_with(query, params)
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_execute_query_error_handling(self, service, mock_connection):
        """Test query execution error handling."""
        service.connection_pool = [mock_connection]
        service._initialized = True
        
        mock_connection.execute.side_effect = Exception("Query failed")
        
        with pytest.raises(Exception) as exc_info:
            await service.execute_query("INVALID QUERY")
        
        assert "Query failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_connection_context_manager(self, service, mock_connection):
        """Test connection context manager."""
        service.connection_pool = [mock_connection]
        service._initialized = True
        
        async with service.get_connection() as conn:
            assert conn == mock_connection
        
        # Connection should be returned to pool
        assert mock_connection in service.connection_pool
    
    @pytest.mark.asyncio
    async def test_get_connection_pool_empty(self, service):
        """Test getting connection when pool is empty."""
        service._initialized = True
        service.connection_pool = []
        
        with patch.object(service, '_create_connection') as mock_create:
            mock_create.return_value = Mock()
            
            async with service.get_connection() as conn:
                assert conn is not None
            
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self, service, mock_connection):
        """Test connection testing - success case."""
        service.connection_pool = [mock_connection]
        service._initialized = True
        
        # Mock successful responses
        mock_connection.execute.return_value.fetchone.side_effect = [
            (1,),  # Basic test
            (100,)  # MinIO test
        ]
        
        result = await service.test_connection()
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, service, mock_connection):
        """Test connection testing - failure case."""
        service.connection_pool = [mock_connection]
        service._initialized = True
        
        mock_connection.execute.side_effect = Exception("Connection failed")
        
        result = await service.test_connection()
        
        assert result == False
    
    @pytest.mark.asyncio
    async def test_get_table_info(self, service, mock_connection):
        """Test getting table information."""
        service.connection_pool = [mock_connection]
        service._initialized = True
        
        # Mock different query responses
        mock_responses = [
            [{'column_name': 'hash', 'column_type': 'VARCHAR'}],  # schema
            [{'total_transactions': 1000}],  # count
            [{'earliest_transaction': datetime.now(), 'latest_transaction': datetime.now()}],  # date_range
            [{'network': 'avalanche', 'count': 800}, {'network': 'ethereum', 'count': 200}]  # networks
        ]
        
        call_count = 0
        def mock_execute_query(query, params=None):
            nonlocal call_count
            result = mock_responses[call_count]
            call_count += 1
            return result
        
        service.execute_query = AsyncMock(side_effect=mock_execute_query)
        
        result = await service.get_table_info()
        
        assert 'schema' in result
        assert 'count' in result
        assert 'date_range' in result
        assert 'networks' in result
        assert service.execute_query.call_count == 4
    
    @pytest.mark.asyncio
    async def test_close_service(self, service):
        """Test service cleanup."""
        mock_conn1 = Mock()
        mock_conn2 = Mock()
        service.connection_pool = [mock_conn1, mock_conn2]
        service._initialized = True
        
        await service.close()
        
        mock_conn1.close.assert_called_once()
        mock_conn2.close.assert_called_once()
        assert len(service.connection_pool) == 0
        assert service._initialized == False
    
    @pytest.mark.asyncio
    async def test_close_service_with_errors(self, service):
        """Test service cleanup with connection errors."""
        mock_conn = Mock()
        mock_conn.close.side_effect = Exception("Close failed")
        service.connection_pool = [mock_conn]
        service._initialized = True
        
        # Should not raise exception
        await service.close()
        
        assert len(service.connection_pool) == 0
        assert service._initialized == False
    
    @pytest.mark.asyncio
    async def test_dependency_injection(self):
        """Test dependency injection function."""
        with patch('src.services.duckdb_service.duckdb_service') as mock_service:
            mock_service._initialized = False
            mock_service.initialize = AsyncMock()
            
            result = await get_duckdb_service()
            
            assert result == mock_service
            mock_service.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_queries(self, service):
        """Test concurrent query execution."""
        # Create multiple mock connections
        mock_connections = [Mock() for _ in range(3)]
        for conn in mock_connections:
            conn.execute.return_value.fetchall.return_value = [('result',)]
            conn.description = [('column',)]
        
        service.connection_pool = mock_connections.copy()
        service._initialized = True
        
        # Execute multiple queries concurrently
        queries = ["SELECT 1", "SELECT 2", "SELECT 3"]
        tasks = [service.execute_query(query) for query in queries]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        for result in results:
            assert len(result) == 1
            assert 'column' in result[0]
    
    @pytest.mark.asyncio
    async def test_connection_pool_management(self, service):
        """Test connection pool size management."""
        service._initialized = True
        service.pool_size = 2
        
        # Fill pool beyond capacity
        mock_connections = [Mock() for _ in range(5)]
        
        with patch.object(service, '_create_connection') as mock_create:
            mock_create.side_effect = mock_connections
            
            # Use connections
            async with service.get_connection() as conn1:
                async with service.get_connection() as conn2:
                    async with service.get_connection() as conn3:
                        pass
            
            # Pool should not exceed max size
            assert len(service.connection_pool) <= service.pool_size

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
