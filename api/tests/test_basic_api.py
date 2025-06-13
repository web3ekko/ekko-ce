"""
Basic API tests to verify the transactions service structure.
"""

import pytest
from unittest.mock import Mock, AsyncMock

def test_transactions_service_imports():
    """Test that we can import the transactions service components."""
    try:
        from src.services.duckdb_service import DuckDBService
        from src.config import settings
        assert DuckDBService is not None
        assert settings is not None
        print("✅ Successfully imported DuckDBService and settings")
    except ImportError as e:
        pytest.fail(f"Failed to import required modules: {e}")

def test_config_settings():
    """Test that configuration settings are accessible."""
    from src.config import settings
    
    # Test that required settings exist
    assert hasattr(settings, 'MINIO_ENDPOINT')
    assert hasattr(settings, 'MINIO_ACCESS_KEY')
    assert hasattr(settings, 'MINIO_SECRET_KEY')
    assert hasattr(settings, 'MINIO_BUCKET_NAME')
    
    print("✅ Configuration settings are properly defined")

@pytest.mark.asyncio
async def test_duckdb_service_creation():
    """Test that DuckDBService can be instantiated."""
    from src.services.duckdb_service import DuckDBService
    
    service = DuckDBService()
    assert service is not None
    assert service.connection_pool == []
    assert service._initialized == False
    
    print("✅ DuckDBService can be instantiated")

def test_transaction_response_model():
    """Test the transaction response model structure."""
    from src.routes.transactions import TransactionResponse
    from datetime import datetime
    
    # Test creating a transaction response
    transaction_data = {
        'hash': '0x123',
        'from': '0xabc',
        'to': '0xdef',
        'value': '1000000000000000000',
        'gas': '21000',
        'gas_price': '20000000000',
        'nonce': '42',
        'input': '0x',
        'block_number': 18500000,
        'block_hash': '0xblock123',
        'transaction_index': 0,
        'timestamp': datetime.now(),
        'network': 'avalanche',
        'subnet': 'mainnet',
        'status': 'confirmed'
    }
    
    transaction = TransactionResponse(**transaction_data)
    assert transaction.hash == '0x123'
    assert transaction.from_address == '0xabc'
    assert transaction.network == 'avalanche'
    
    print("✅ TransactionResponse model works correctly")

def test_transactions_list_response_model():
    """Test the transactions list response model."""
    from src.routes.transactions import TransactionsListResponse, TransactionResponse
    from datetime import datetime
    
    # Create a mock transaction
    transaction_data = {
        'hash': '0x123',
        'from': '0xabc',
        'to': '0xdef',
        'value': '1000000000000000000',
        'gas': '21000',
        'gas_price': '20000000000',
        'nonce': '42',
        'input': '0x',
        'block_number': 18500000,
        'block_hash': '0xblock123',
        'transaction_index': 0,
        'timestamp': datetime.now(),
        'network': 'avalanche',
        'subnet': 'mainnet',
        'status': 'confirmed'
    }
    
    transaction = TransactionResponse(**transaction_data)
    
    # Create list response
    list_response = TransactionsListResponse(
        transactions=[transaction],
        total=1,
        limit=20,
        offset=0,
        has_more=False
    )
    
    assert len(list_response.transactions) == 1
    assert list_response.total == 1
    assert list_response.has_more == False
    
    print("✅ TransactionsListResponse model works correctly")

@pytest.mark.asyncio
async def test_mock_duckdb_query():
    """Test mock DuckDB query execution."""
    from src.services.duckdb_service import DuckDBService
    
    service = DuckDBService()
    
    # Mock the execute_query method
    service.execute_query = AsyncMock(return_value=[
        {
            'hash': '0x123',
            'from_address': '0xabc',
            'to_address': '0xdef',
            'value': '1000000000000000000',
            'network': 'avalanche',
            'status': 'confirmed'
        }
    ])
    
    # Test the mocked query
    result = await service.execute_query("SELECT * FROM transactions LIMIT 1")
    
    assert len(result) == 1
    assert result[0]['hash'] == '0x123'
    assert result[0]['network'] == 'avalanche'
    
    print("✅ Mock DuckDB query execution works")

def test_api_router_creation():
    """Test that the API router can be created."""
    from src.routes.transactions import router
    from fastapi import APIRouter
    
    assert isinstance(router, APIRouter)
    assert router.prefix == "/transactions"
    assert "transactions" in router.tags
    
    print("✅ API router is properly configured")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
