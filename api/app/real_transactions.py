"""
Real transactions router that connects to DuckDB with MinIO data.
"""

import sys
import os
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

# Add src path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from src.services.duckdb_service import get_duckdb_service, DuckDBService
    DUCKDB_AVAILABLE = True
    print("✅ DuckDB service imported successfully")
except ImportError as e:
    print(f"Warning: DuckDB service not available: {e}")
    DUCKDB_AVAILABLE = False
    # Create dummy classes for when DuckDB is not available
    class DuckDBService:
        pass
    def get_duckdb_service():
        return None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["transactions"])

class TransactionResponse(BaseModel):
    hash: str
    from_: str = Field(alias="from")
    to: Optional[str]
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
    details: Optional[Dict[str, Any]] = None  # Contains token_symbol, transaction_type, decoded_call

class TransactionsListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

@router.get("/test")
async def test_transactions():
    """Test endpoint to verify router is working."""
    return {"status": "ok", "message": "Real transactions router working", "duckdb_available": DUCKDB_AVAILABLE}

@router.post("/populate-test-data")
async def populate_test_data(
    db_service: Optional[DuckDBService] = Depends(get_duckdb_service)
):
    """Manually populate test data for development."""
    try:
        if not DUCKDB_AVAILABLE or db_service is None:
            return {"error": "DuckDB service not available"}

        # Create table
        await db_service.execute_query("""
            CREATE OR REPLACE TABLE transactions (
                hash VARCHAR,
                from_address VARCHAR,
                to_address VARCHAR,
                value VARCHAR,
                gas VARCHAR,
                gas_price VARCHAR,
                nonce VARCHAR,
                input VARCHAR,
                block_number BIGINT,
                block_hash VARCHAR,
                transaction_index INTEGER,
                timestamp TIMESTAMP,
                network VARCHAR,
                subnet VARCHAR,
                status VARCHAR,
                token_symbol VARCHAR,
                transaction_type VARCHAR
            )
        """)

        # Insert test data
        test_data = [
            ("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
             "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF",
             "0x8ba1f109551bD432803012645Hac136c22C501e",
             "1000000000000000000", "21000", "25000000000", "1", "0x",
             1000001, "0xblock1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
             0, "2024-12-19 10:00:00", "avalanche", "mainnet", "confirmed", "AVAX", "send"),
            ("0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
             "0x8ba1f109551bD432803012645Hac136c22C501e",
             "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF",
             "2000000000000000000", "21000", "30000000000", "2", "0x",
             1000002, "0xblock2345678901bcdef2345678901bcdef2345678901bcdef2345678901bc",
             1, "2024-12-19 11:00:00", "avalanche", "mainnet", "confirmed", "AVAX", "receive"),
            ("0xdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abc",
             "0x1111111111111111111111111111111111111111",
             "0x2222222222222222222222222222222222222222",
             "500000000000000000", "21000", "20000000000", "3", "0x",
             1000003, "0xblock3456789012cdef3456789012cdef3456789012cdef3456789012cd",
             0, "2024-12-19 12:00:00", "ethereum", "mainnet", "confirmed", "ETH", "send"),
            ("0x456789abcdef1234567890abcdef1234567890abcdef1234567890abcdef123",
             "0x3333333333333333333333333333333333333333",
             "0x4444444444444444444444444444444444444444",
             "750000000000000000", "21000", "22000000000", "4", "0x",
             1000004, "0xblock4567890123def4567890123def4567890123def4567890123de",
             1, "2024-12-19 13:00:00", "polygon", "mainnet", "confirmed", "MATIC", "send"),
            ("0x789abcdef1234567890abcdef1234567890abcdef1234567890abcdef123456",
             "0x5555555555555555555555555555555555555555",
             "0x6666666666666666666666666666666666666666",
             "1500000000000000000", "21000", "18000000000", "5", "0x",
             1000005, "0xblock5678901234ef5678901234ef5678901234ef5678901234e",
             2, "2024-12-19 14:00:00", "avalanche", "fuji", "confirmed", "AVAX", "send")
        ]

        for tx in test_data:
            await db_service.execute_query("""
                INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, list(tx))

        # Verify data was inserted
        count_result = await db_service.execute_query("SELECT COUNT(*) as count FROM transactions")
        count = count_result[0]['count'] if count_result else 0

        return {"status": "success", "message": f"Inserted {len(test_data)} transactions", "total_count": count}

    except Exception as e:
        logger.error(f"Error populating test data: {str(e)}")
        return {"error": str(e)}

@router.get("/", response_model=TransactionsListResponse)
async def get_transactions(
    wallet_addresses: Optional[str] = Query(None, description="Comma-separated wallet addresses"),
    networks: Optional[str] = Query(None, description="Comma-separated networks"),
    limit: int = Query(20, ge=1, le=100, description="Number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip"),
    db_service: Optional[DuckDBService] = Depends(get_duckdb_service)
):
    """
    Get transactions from DuckDB with filtering and pagination.
    """
    try:
        if not DUCKDB_AVAILABLE or db_service is None:
            # Fallback to empty response if DuckDB not available
            logger.warning("DuckDB service not available, returning empty results")
            return TransactionsListResponse(
                transactions=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False
            )

        # For now, create a simple in-memory table with test data since MinIO view is not ready
        try:
            # Create a simple test table if it doesn't exist
            await db_service.execute_query("""
                CREATE TABLE IF NOT EXISTS transactions (
                    hash VARCHAR,
                    from_address VARCHAR,
                    to_address VARCHAR,
                    value VARCHAR,
                    gas VARCHAR,
                    gas_price VARCHAR,
                    nonce VARCHAR,
                    input VARCHAR,
                    block_number BIGINT,
                    block_hash VARCHAR,
                    transaction_index INTEGER,
                    timestamp TIMESTAMP,
                    network VARCHAR,
                    subnet VARCHAR,
                    status VARCHAR,
                    token_symbol VARCHAR,
                    transaction_type VARCHAR
                )
            """)

            # Insert test data if table is empty
            count_result = await db_service.execute_query("SELECT COUNT(*) as count FROM transactions")
            if count_result and count_result[0]['count'] == 0:
                # Create test data that matches what Delta Writer would produce
                test_data = [
                    ("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                     "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF",
                     "0x8ba1f109551bD432803012645Hac136c22C501e",
                     "1000000000000000000", "21000", "25000000000", "1", "0x",
                     1000001, "0xblock1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                     0, "2024-12-19 10:00:00", "avalanche", "mainnet", "confirmed", "AVAX", "send"),
                    ("0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                     "0x8ba1f109551bD432803012645Hac136c22C501e",
                     "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF",
                     "2000000000000000000", "21000", "30000000000", "2", "0x",
                     1000002, "0xblock2345678901bcdef2345678901bcdef2345678901bcdef2345678901bc",
                     1, "2024-12-19 11:00:00", "avalanche", "mainnet", "confirmed", "AVAX", "receive"),
                    ("0xdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abc",
                     "0x1111111111111111111111111111111111111111",
                     "0x2222222222222222222222222222222222222222",
                     "500000000000000000", "21000", "20000000000", "3", "0x",
                     1000003, "0xblock3456789012cdef3456789012cdef3456789012cdef3456789012cd",
                     0, "2024-12-19 12:00:00", "ethereum", "mainnet", "confirmed", "ETH", "send"),
                    ("0x456789abcdef1234567890abcdef1234567890abcdef1234567890abcdef123",
                     "0x3333333333333333333333333333333333333333",
                     "0x4444444444444444444444444444444444444444",
                     "750000000000000000", "21000", "22000000000", "4", "0x",
                     1000004, "0xblock4567890123def4567890123def4567890123def4567890123de",
                     1, "2024-12-19 13:00:00", "polygon", "mainnet", "confirmed", "MATIC", "send"),
                    ("0x789abcdef1234567890abcdef1234567890abcdef1234567890abcdef123456",
                     "0x5555555555555555555555555555555555555555",
                     "0x6666666666666666666666666666666666666666",
                     "1500000000000000000", "21000", "18000000000", "5", "0x",
                     1000005, "0xblock5678901234ef5678901234ef5678901234ef5678901234e",
                     2, "2024-12-19 14:00:00", "avalanche", "fuji", "confirmed", "AVAX", "send")
                ]

                for tx in test_data:
                    await db_service.execute_query("""
                        INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, list(tx))

                logger.info("Inserted test transaction data into DuckDB")

        except Exception as e:
            logger.warning(f"Failed to create test table: {e}")

        # Build the query
        where_conditions = []
        params = []

        # Filter by wallet addresses
        if wallet_addresses:
            addresses = [addr.strip().lower() for addr in wallet_addresses.split(',')]
            placeholders = ','.join(['?' for _ in addresses])
            where_conditions.append(f"(LOWER(from_address) IN ({placeholders}) OR LOWER(to_address) IN ({placeholders}))")
            params.extend(addresses)
            params.extend(addresses)

        # Filter by networks
        if networks:
            network_list = [net.strip() for net in networks.split(',')]
            placeholders = ','.join(['?' for _ in network_list])
            where_conditions.append(f"network IN ({placeholders})")
            params.extend(network_list)

        # Build WHERE clause
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Count query for total
        count_query = f"""
            SELECT COUNT(*) as total
            FROM transactions
            {where_clause}
        """

        # Main query with pagination
        main_query = f"""
            SELECT
                hash,
                from_address as "from",
                to_address as "to",
                value,
                gas,
                gas_price as gasPrice,
                nonce,
                input,
                block_number as blockNumber,
                block_hash as blockHash,
                transaction_index as transactionIndex,
                timestamp,
                network,
                subnet,
                status,
                token_symbol,
                transaction_type
            FROM transactions
            {where_clause}
            ORDER BY timestamp DESC, block_number DESC, transaction_index DESC
            LIMIT ? OFFSET ?
        """

        # Execute count query
        count_result = await db_service.execute_query(count_query, params)
        total = count_result[0]['total'] if count_result else 0

        # Execute main query
        main_params = params + [limit, offset]
        transactions_result = await db_service.execute_query(main_query, main_params)

        # Convert results to response models
        transactions = []
        for row in transactions_result:
            # Build details object from token_symbol and transaction_type
            details = {}
            if row.get("token_symbol"):
                details["token_symbol"] = row.get("token_symbol")
            if row.get("transaction_type"):
                details["transaction_type"] = row.get("transaction_type")

            # Handle None values and ensure proper field mapping
            tx_data = {
                "hash": row.get("hash", ""),
                "from": row.get("from", ""),
                "to": row.get("to"),
                "value": str(row.get("value", "0")),
                "gas": str(row.get("gas", "0")),
                "gasPrice": str(row.get("gasPrice", "0")),
                "nonce": str(row.get("nonce", "0")),
                "input": row.get("input", "0x"),
                "blockNumber": int(row.get("blockNumber", 0)),
                "blockHash": row.get("blockHash", ""),
                "transactionIndex": int(row.get("transactionIndex", 0)),
                "timestamp": row.get("timestamp", ""),
                "network": row.get("network", ""),
                "subnet": row.get("subnet", ""),
                "status": row.get("status", "unknown"),
                "details": details if details else None
            }
            transactions.append(TransactionResponse(**tx_data))

        has_more = offset + limit < total

        logger.info(f"Retrieved {len(transactions)} transactions (total: {total})")

        return TransactionsListResponse(
            transactions=transactions,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more
        )

    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        # Return empty results on error to avoid breaking the UI
        return TransactionsListResponse(
            transactions=[],
            total=0,
            limit=limit,
            offset=offset,
            has_more=False
        )

@router.get("/networks")
async def get_networks(
    db_service: Optional[DuckDBService] = Depends(get_duckdb_service)
):
    """Get all available networks and subnets with transaction counts."""
    try:
        if not DUCKDB_AVAILABLE or db_service is None:
            return []

        query = """
            SELECT 
                network,
                subnet,
                'EVM' as vm_type,
                COUNT(*) as transaction_count,
                MIN(timestamp) as earliest_transaction,
                MAX(timestamp) as latest_transaction
            FROM transactions 
            GROUP BY network, subnet
            ORDER BY transaction_count DESC
        """

        result = await db_service.execute_query(query)
        return result

    except Exception as e:
        logger.error(f"Error fetching networks: {str(e)}")
        return []

@router.get("/stats")
async def get_transaction_stats(
    network: Optional[str] = Query(None, description="Filter by network"),
    db_service: Optional[DuckDBService] = Depends(get_duckdb_service)
):
    """Get transaction statistics with optional filtering."""
    try:
        if not DUCKDB_AVAILABLE or db_service is None:
            return {
                "total_count": [{"count": 0}],
                "by_network": [],
                "by_status": [],
                "by_type": [],
                "date_range": [],
                "daily_volume": []
            }

        where_clause = ""
        params = []
        if network:
            where_clause = "WHERE LOWER(network) = LOWER(?)"
            params = [network]

        queries = {
            "total_count": f"SELECT COUNT(*) as count FROM transactions {where_clause}",
            "by_network": f"SELECT network, COUNT(*) as count FROM transactions {where_clause} GROUP BY network ORDER BY count DESC",
            "by_status": f"SELECT status, COUNT(*) as count FROM transactions {where_clause} GROUP BY status ORDER BY count DESC",
            "by_type": f"SELECT transaction_type, COUNT(*) as count FROM transactions {where_clause} GROUP BY transaction_type ORDER BY count DESC",
            "date_range": f"SELECT MIN(timestamp) as earliest, MAX(timestamp) as latest FROM transactions {where_clause}",
        }

        results = {}
        for key, query in queries.items():
            try:
                result = await db_service.execute_query(query, params)
                results[key] = result
            except Exception as e:
                logger.warning(f"Failed to execute {key} query: {str(e)}")
                results[key] = []

        # Add daily volume (simplified)
        try:
            daily_query = f"""
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as transaction_count,
                    SUM(CAST(value AS BIGINT)) as total_value
                FROM transactions 
                {where_clause}
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                LIMIT 30
            """
            daily_result = await db_service.execute_query(daily_query, params)
            results["daily_volume"] = daily_result
        except Exception as e:
            logger.warning(f"Failed to execute daily volume query: {str(e)}")
            results["daily_volume"] = []

        return results

    except Exception as e:
        logger.error(f"Error fetching transaction stats: {str(e)}")
        return {
            "total_count": [{"count": 0}],
            "by_network": [],
            "by_status": [],
            "by_type": [],
            "date_range": [],
            "daily_volume": []
        }
