"""
Simple transactions router - returns empty data to stop infinite loops.
"""

from fastapi import APIRouter
from typing import List
from pydantic import BaseModel, Field

router = APIRouter(prefix="/transactions", tags=["transactions"])

class TransactionResponse(BaseModel):
    hash: str
    from_: str = Field(alias="from")
    to: str
    value: str
    gas: str
    gasPrice: str
    nonce: str
    input: str
    blockNumber: int
    blockHash: str
    transactionIndex: int
    timestamp: str
    network: str
    subnet: str
    status: str
    tokenSymbol: str
    transactionType: str

class TransactionsListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

# Simple test data - minimal to avoid loops
TEST_TRANSACTIONS = [
    {
        "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "from": "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF",
        "to": "0x8ba1f109551bD432803012645Hac136c22C501e",
        "value": "1000000000000000000",  # 1 AVAX
        "gas": "21000",
        "gasPrice": "25000000000",
        "nonce": "1",
        "input": "0x",
        "blockNumber": 1000001,
        "blockHash": "0xblock1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "transactionIndex": 0,
        "timestamp": "2024-12-19T10:00:00Z",
        "network": "Avalanche",
        "subnet": "Mainnet",
        "status": "confirmed",
        "tokenSymbol": "AVAX",
        "transactionType": "send"
    },
    {
        "hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "from": "0x8ba1f109551bD432803012645Hac136c22C501e",
        "to": "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF",
        "value": "2000000000000000000",  # 2 AVAX
        "gas": "21000",
        "gasPrice": "30000000000",
        "nonce": "2",
        "input": "0x",
        "blockNumber": 1000002,
        "blockHash": "0xblock2345678901bcdef2345678901bcdef2345678901bcdef2345678901bc",
        "transactionIndex": 1,
        "timestamp": "2024-12-19T11:00:00Z",
        "network": "Avalanche",
        "subnet": "Mainnet",
        "status": "confirmed",
        "tokenSymbol": "AVAX",
        "transactionType": "receive"
    }
]

@router.get("/", response_model=TransactionsListResponse)
async def get_transactions():
    """Return simple test transactions to verify UI works."""
    return TransactionsListResponse(
        transactions=[TransactionResponse(**tx) for tx in TEST_TRANSACTIONS],
        total=len(TEST_TRANSACTIONS),
        limit=20,
        offset=0,
        has_more=False
    )

@router.get("/test")
async def test_transactions():
    """Test endpoint."""
    return {"status": "ok", "message": "Transactions router working"}

@router.get("/networks")
async def get_networks():
    """Return empty networks list."""
    return []

@router.get("/stats")
async def get_transaction_stats():
    """Return empty stats."""
    return {
        "total_count": [{"count": 0}],
        "by_network": [],
        "by_status": [],
        "by_type": [],
        "date_range": [],
        "daily_volume": []
    }
