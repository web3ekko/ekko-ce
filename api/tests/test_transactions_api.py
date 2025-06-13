"""
Tests for the transactions API endpoints.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from src.routes.transactions import router
from src.services.duckdb_service import DuckDBService
from src.services.auth_service import get_current_user

# Import from existing models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../app'))
from models import User

# Mock data for testing
MOCK_TRANSACTIONS = [
    {
        'hash': '0x1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890',
        'from_address': '0x742d35cc6634c0532925a3b8d4c0c8b3c2e1e416',
        'to_address': '0x8ba1f109551bd432803012645hac136c22c177e9',
        'value': '2500000000000000000',  # 2.5 AVAX in wei
        'gas': '21000',
        'gas_price': '20000000000',
        'nonce': '42',
        'input': '0x',
        'block_number': 18500000,
        'block_hash': '0xabc123def456...',
        'transaction_index': 0,
        'timestamp': datetime.now() - timedelta(minutes=5),
        'network': 'avalanche',
        'subnet': 'mainnet',
        'status': 'confirmed',
        'decoded_call': {'function': 'Transfer', 'params': {'to': '0x8ba1f109551bd432803012645hac136c22c177e9', 'value': '2.5'}},
        'token_symbol': 'AVAX',
        'transaction_type': 'send'
    },
    {
        'hash': '0x2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890ab',
        'from_address': '0x8ba1f109551bd432803012645hac136c22c177e9',
        'to_address': '0x742d35cc6634c0532925a3b8d4c0c8b3c2e1e416',
        'value': '1000000000',  # 1000 USDC (6 decimals)
        'gas': '65000',
        'gas_price': '25000000000',
        'nonce': '43',
        'input': '0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c0c8b3c2e1e416',
        'block_number': 18499950,
        'block_hash': '0xdef456ghi789...',
        'transaction_index': 1,
        'timestamp': datetime.now() - timedelta(minutes=15),
        'network': 'avalanche',
        'subnet': 'mainnet',
        'status': 'confirmed',
        'decoded_call': {'function': 'Transfer', 'params': {'to': '0x742d35cc6634c0532925a3b8d4c0c8b3c2e1e416', 'value': '1000'}},
        'token_symbol': 'USDC.e',
        'transaction_type': 'contract_interaction'
    },
    {
        'hash': '0x3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890abcd',
        'from_address': '0x742d35cc6634c0532925a3b8d4c0c8b3c2e1e416',
        'to_address': '0x60781c2586d68229fde47564546784ab3faca982',
        'value': '50000000000000000000',  # 50 PNG
        'gas': '150000',
        'gas_price': '30000000000',
        'nonce': '44',
        'input': '0x38ed1739000000000000000000000000000000000000000000000000000000000000000a',
        'block_number': 18500100,
        'block_hash': '0xghi789jkl012...',
        'transaction_index': 2,
        'timestamp': datetime.now() - timedelta(minutes=2),
        'network': 'avalanche',
        'subnet': 'mainnet',
        'status': 'pending',
        'decoded_call': {'function': 'Swap', 'params': {'amountIn': '50.0', 'tokenIn': 'PNG', 'tokenOut': 'AVAX'}},
        'token_symbol': 'PNG',
        'transaction_type': 'contract_interaction'
    }
]

MOCK_USER = User(
    id="test-user-id",
    email="test@example.com",
    full_name="Test User",
    is_active=True
)

class TestTransactionsAPI:
    """Test class for transactions API endpoints."""
    
    @pytest.fixture
    def mock_db_service(self):
        """Mock DuckDB service."""
        service = Mock(spec=DuckDBService)
        service.execute_query = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return MOCK_USER
    
    @pytest.fixture
    def client(self, mock_db_service, mock_user):
        """Test client with mocked dependencies."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        app.include_router(router)
        
        # Override dependencies
        app.dependency_overrides[DuckDBService] = lambda: mock_db_service
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_get_transactions_success(self, client, mock_db_service):
        """Test successful transaction retrieval."""
        # Mock database responses
        mock_db_service.execute_query.side_effect = [
            [{'total': 3}],  # Count query
            MOCK_TRANSACTIONS  # Main query
        ]
        
        response = client.get("/transactions/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total'] == 3
        assert len(data['transactions']) == 3
        assert data['limit'] == 20
        assert data['offset'] == 0
        assert data['has_more'] == False
        
        # Verify transaction structure
        transaction = data['transactions'][0]
        assert transaction['hash'] == MOCK_TRANSACTIONS[0]['hash']
        assert transaction['from'] == MOCK_TRANSACTIONS[0]['from_address']
        assert transaction['network'] == 'avalanche'
    
    @pytest.mark.asyncio
    async def test_get_transactions_with_filters(self, client, mock_db_service):
        """Test transaction retrieval with filters."""
        mock_db_service.execute_query.side_effect = [
            [{'total': 1}],
            [MOCK_TRANSACTIONS[0]]
        ]
        
        response = client.get(
            "/transactions/",
            params={
                'wallet_addresses': '0x742d35cc6634c0532925a3b8d4c0c8b3c2e1e416',
                'networks': 'avalanche',
                'status': 'confirmed',
                'limit': 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['transactions']) == 1
    
    @pytest.mark.asyncio
    async def test_get_transactions_with_search(self, client, mock_db_service):
        """Test transaction search functionality."""
        mock_db_service.execute_query.side_effect = [
            [{'total': 1}],
            [MOCK_TRANSACTIONS[0]]
        ]
        
        response = client.get(
            "/transactions/",
            params={'search': '0x1a2b3c4d'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
    
    @pytest.mark.asyncio
    async def test_get_transactions_pagination(self, client, mock_db_service):
        """Test transaction pagination."""
        mock_db_service.execute_query.side_effect = [
            [{'total': 100}],
            MOCK_TRANSACTIONS[:2]  # Return 2 transactions
        ]
        
        response = client.get(
            "/transactions/",
            params={'limit': 2, 'offset': 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 100
        assert data['limit'] == 2
        assert data['offset'] == 0
        assert data['has_more'] == True
        assert len(data['transactions']) == 2
    
    @pytest.mark.asyncio
    async def test_get_transactions_sorting(self, client, mock_db_service):
        """Test transaction sorting."""
        mock_db_service.execute_query.side_effect = [
            [{'total': 3}],
            MOCK_TRANSACTIONS
        ]
        
        response = client.get(
            "/transactions/",
            params={'sort_by': 'block_number', 'sort_order': 'asc'}
        )
        
        assert response.status_code == 200
        # Verify the query was called with correct parameters
        assert mock_db_service.execute_query.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_transaction_by_hash_success(self, client, mock_db_service):
        """Test successful single transaction retrieval."""
        mock_db_service.execute_query.return_value = [MOCK_TRANSACTIONS[0]]
        
        transaction_hash = MOCK_TRANSACTIONS[0]['hash']
        response = client.get(f"/transactions/{transaction_hash}")
        
        assert response.status_code == 200
        data = response.json()
        assert data['hash'] == transaction_hash
        assert data['network'] == 'avalanche'
    
    @pytest.mark.asyncio
    async def test_get_transaction_by_hash_not_found(self, client, mock_db_service):
        """Test transaction not found."""
        mock_db_service.execute_query.return_value = []
        
        response = client.get("/transactions/0xinvalidhash")
        
        assert response.status_code == 404
        assert "not found" in response.json()['detail'].lower()
    
    @pytest.mark.asyncio
    async def test_get_transaction_stats_success(self, client, mock_db_service):
        """Test transaction statistics retrieval."""
        # Mock stats query responses
        mock_db_service.execute_query.side_effect = [
            [{'count': 100}],  # total
            [{'sum': '1000000000000000000000'}],  # total_value
            [{'avg': '25000000000'}],  # avg_gas
            [{'network': 'avalanche', 'count': 80}, {'network': 'ethereum', 'count': 20}],  # networks
            [{'transaction_type': 'send', 'count': 50}, {'transaction_type': 'receive', 'count': 30}],  # types
            [{'date': datetime.now().date(), 'count': 10, 'value': '100000000000000000000'}]  # daily
        ]
        
        response = client.get("/transactions/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['total_transactions'] == 100
        assert data['total_value'] == '1000000000000000000000'
        assert len(data['network_breakdown']) == 2
        assert len(data['type_breakdown']) == 2
        assert len(data['daily_volume']) == 1
        
        # Verify percentages are calculated
        assert data['network_breakdown'][0]['percentage'] == 80.0
        assert data['network_breakdown'][1]['percentage'] == 20.0
    
    @pytest.mark.asyncio
    async def test_get_transactions_database_error(self, client, mock_db_service):
        """Test database error handling."""
        mock_db_service.execute_query.side_effect = Exception("Database connection failed")
        
        response = client.get("/transactions/")
        
        assert response.status_code == 500
        assert "Failed to fetch transactions" in response.json()['detail']
    
    @pytest.mark.asyncio
    async def test_get_transactions_invalid_parameters(self, client, mock_db_service):
        """Test invalid parameter handling."""
        # Test invalid limit
        response = client.get("/transactions/", params={'limit': 0})
        assert response.status_code == 422
        
        # Test invalid sort order
        response = client.get("/transactions/", params={'sort_order': 'invalid'})
        assert response.status_code == 422
        
        # Test negative offset
        response = client.get("/transactions/", params={'offset': -1})
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_get_transactions_date_filtering(self, client, mock_db_service):
        """Test date range filtering."""
        mock_db_service.execute_query.side_effect = [
            [{'total': 1}],
            [MOCK_TRANSACTIONS[0]]
        ]
        
        from_date = (datetime.now() - timedelta(days=1)).isoformat()
        to_date = datetime.now().isoformat()
        
        response = client.get(
            "/transactions/",
            params={
                'from_date': from_date,
                'to_date': to_date
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
    
    @pytest.mark.asyncio
    async def test_get_transactions_multiple_networks(self, client, mock_db_service):
        """Test filtering by multiple networks."""
        mock_db_service.execute_query.side_effect = [
            [{'total': 2}],
            MOCK_TRANSACTIONS[:2]
        ]
        
        response = client.get(
            "/transactions/",
            params={'networks': 'avalanche,ethereum'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 2
    
    @pytest.mark.asyncio
    async def test_get_transactions_empty_result(self, client, mock_db_service):
        """Test empty transaction result."""
        mock_db_service.execute_query.side_effect = [
            [{'total': 0}],
            []
        ]
        
        response = client.get("/transactions/")
        
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 0
        assert len(data['transactions']) == 0
        assert data['has_more'] == False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
