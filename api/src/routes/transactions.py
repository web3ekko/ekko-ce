"""
Transactions API endpoints for querying blockchain transaction data from DuckDB/MinIO.
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import duckdb
import logging
from ..services.duckdb_service import DuckDBService
from ..services.auth_service import get_current_user
# Import from existing models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../app'))
from models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["transactions"])

# Simple test endpoint without authentication
@router.get("/test")
async def test_transactions():
    """
    Simple test endpoint to verify transactions router is working.
    """
    return {"status": "ok", "message": "Transactions router is working!"}

# Add new endpoints for network-subnet specific queries
@router.get("/networks", response_model=List[Dict[str, Any]])
async def get_networks(
    current_user: User = Depends(get_current_user),
    db_service: DuckDBService = Depends(DuckDBService)
):
    """
    Get all available networks and subnets with transaction counts.
    """
    try:
        query = """
        SELECT
            network,
            subnet,
            vm_type,
            COUNT(*) as transaction_count,
            MIN(timestamp) as earliest_transaction,
            MAX(timestamp) as latest_transaction
        FROM transactions
        GROUP BY network, subnet, vm_type
        ORDER BY network, subnet, vm_type
        """

        result = await db_service.execute_query(query)
        return result

    except Exception as e:
        logger.error(f"Error fetching networks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch networks: {str(e)}")

@router.get("/stats", response_model=Dict[str, Any])
async def get_transaction_stats(
    network: Optional[str] = Query(None, description="Filter by network"),
    subnet: Optional[str] = Query(None, description="Filter by subnet"),
    vm_type: Optional[str] = Query(None, description="Filter by VM type"),
    current_user: User = Depends(get_current_user),
    db_service: DuckDBService = Depends(DuckDBService)
):
    """
    Get transaction statistics with optional filtering.
    """
    try:
        # Build WHERE clause
        where_conditions = []
        params = []

        if network:
            where_conditions.append("network = ?")
            params.append(network)
        if subnet:
            where_conditions.append("subnet = ?")
            params.append(subnet)
        if vm_type:
            where_conditions.append("vm_type = ?")
            params.append(vm_type)

        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

        # Get comprehensive stats
        queries = {
            'total_count': f"SELECT COUNT(*) as count FROM transactions {where_clause}",
            'by_network': f"""
                SELECT network, subnet, vm_type, COUNT(*) as count
                FROM transactions {where_clause}
                GROUP BY network, subnet, vm_type
                ORDER BY count DESC
            """,
            'by_status': f"""
                SELECT status, COUNT(*) as count
                FROM transactions {where_clause}
                GROUP BY status
            """,
            'by_type': f"""
                SELECT transaction_type, COUNT(*) as count
                FROM transactions {where_clause}
                GROUP BY transaction_type
            """,
            'date_range': f"""
                SELECT
                    MIN(timestamp) as earliest,
                    MAX(timestamp) as latest
                FROM transactions {where_clause}
            """,
            'daily_volume': f"""
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as transaction_count,
                    SUM(CAST(value AS BIGINT)) as total_value
                FROM transactions {where_clause}
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                LIMIT 30
            """
        }

        results = {}
        for key, query in queries.items():
            try:
                results[key] = await db_service.execute_query(query, params if where_conditions else None)
            except Exception as e:
                logger.warning(f"Failed to execute {key} query: {str(e)}")
                results[key] = []

        return results

    except Exception as e:
        logger.error(f"Error fetching transaction stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

# Pydantic models for request/response
class TransactionResponse(BaseModel):
    hash: str
    from_address: str = Field(alias="from")
    to_address: Optional[str] = Field(alias="to")
    value: str
    gas: str
    gas_price: str
    nonce: str
    input: str
    block_number: int
    block_hash: str
    transaction_index: int
    timestamp: datetime
    network: str
    subnet: str
    status: str
    decoded_call: Optional[Dict[str, Any]] = None
    token_symbol: Optional[str] = None
    transaction_type: Optional[str] = None

    class Config:
        allow_population_by_field_name = True

class TransactionsListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

class TransactionStatsResponse(BaseModel):
    total_transactions: int
    total_value: str
    average_gas_price: str
    network_breakdown: List[Dict[str, Any]]
    type_breakdown: List[Dict[str, Any]]
    daily_volume: List[Dict[str, Any]]

@router.get("/", response_model=TransactionsListResponse)
async def get_transactions(
    wallet_addresses: Optional[str] = Query(None, description="Comma-separated wallet addresses"),
    networks: Optional[str] = Query(None, description="Comma-separated networks (e.g., avalanche,ethereum)"),
    subnets: Optional[str] = Query(None, description="Comma-separated subnets (e.g., mainnet,fuji)"),
    transaction_types: Optional[str] = Query(None, description="Comma-separated transaction types"),
    status: Optional[str] = Query(None, description="Comma-separated status values"),
    from_date: Optional[datetime] = Query(None, description="Start date filter"),
    to_date: Optional[datetime] = Query(None, description="End date filter"),
    search: Optional[str] = Query(None, description="Search in hash, addresses, or function names"),
    limit: int = Query(20, ge=1, le=1000, description="Number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip"),
    sort_by: str = Query("timestamp", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_user: User = Depends(get_current_user),
    db_service: DuckDBService = Depends(DuckDBService)
):
    """
    Fetch transactions with filtering, pagination, and sorting.
    """
    try:
        # Build the SQL query
        query_parts = []
        params = {}
        
        # Base query
        base_query = """
        SELECT 
            hash,
            from_address,
            to_address,
            value,
            gas,
            gas_price,
            nonce,
            input,
            block_number,
            block_hash,
            transaction_index,
            timestamp,
            network,
            subnet,
            status,
            decoded_call,
            token_symbol,
            transaction_type
        FROM transactions
        WHERE 1=1
        """
        
        # Add filters
        if wallet_addresses:
            addresses = [addr.strip() for addr in wallet_addresses.split(',')]
            placeholders = ','.join([f"${len(params) + i + 1}" for i in range(len(addresses))])
            query_parts.append(f"AND (from_address IN ({placeholders}) OR to_address IN ({placeholders}))")
            for addr in addresses:
                params[f"param_{len(params) + 1}"] = addr.lower()
                params[f"param_{len(params) + 1}"] = addr.lower()
        
        if networks:
            network_list = [net.strip() for net in networks.split(',')]
            placeholders = ','.join([f"${len(params) + i + 1}" for i in range(len(network_list))])
            query_parts.append(f"AND network IN ({placeholders})")
            for net in network_list:
                params[f"param_{len(params) + 1}"] = net.lower()
        
        if subnets:
            subnet_list = [sub.strip() for sub in subnets.split(',')]
            placeholders = ','.join([f"${len(params) + i + 1}" for i in range(len(subnet_list))])
            query_parts.append(f"AND subnet IN ({placeholders})")
            for sub in subnet_list:
                params[f"param_{len(params) + 1}"] = sub.lower()
        
        if transaction_types:
            type_list = [t.strip() for t in transaction_types.split(',')]
            placeholders = ','.join([f"${len(params) + i + 1}" for i in range(len(type_list))])
            query_parts.append(f"AND transaction_type IN ({placeholders})")
            for t in type_list:
                params[f"param_{len(params) + 1}"] = t
        
        if status:
            status_list = [s.strip() for s in status.split(',')]
            placeholders = ','.join([f"${len(params) + i + 1}" for i in range(len(status_list))])
            query_parts.append(f"AND status IN ({placeholders})")
            for s in status_list:
                params[f"param_{len(params) + 1}"] = s
        
        if from_date:
            query_parts.append(f"AND timestamp >= ${len(params) + 1}")
            params[f"param_{len(params) + 1}"] = from_date
        
        if to_date:
            query_parts.append(f"AND timestamp <= ${len(params) + 1}")
            params[f"param_{len(params) + 1}"] = to_date
        
        if search:
            search_term = f"%{search.lower()}%"
            query_parts.append(f"""
                AND (
                    LOWER(hash) LIKE ${len(params) + 1} OR
                    LOWER(from_address) LIKE ${len(params) + 1} OR
                    LOWER(to_address) LIKE ${len(params) + 1} OR
                    LOWER(decoded_call->>'function') LIKE ${len(params) + 1}
                )
            """)
            params[f"param_{len(params) + 1}"] = search_term
        
        # Build complete query
        where_clause = ' '.join(query_parts)
        
        # Count query for total
        count_query = f"SELECT COUNT(*) as total FROM transactions {where_clause}"
        
        # Main query with sorting and pagination
        main_query = f"""
        {base_query}
        {where_clause}
        ORDER BY {sort_by} {sort_order.upper()}
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """
        
        params[f"param_{len(params) + 1}"] = limit
        params[f"param_{len(params) + 2}"] = offset
        
        # Execute queries
        total_result = await db_service.execute_query(count_query, list(params.values())[:len(params)-2])
        total = total_result[0]['total'] if total_result else 0
        
        transactions_result = await db_service.execute_query(main_query, list(params.values()))
        
        # Convert to response models
        transactions = [
            TransactionResponse(**row) for row in transactions_result
        ]
        
        has_more = offset + limit < total
        
        return TransactionsListResponse(
            transactions=transactions,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more
        )
        
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")

@router.get("/{transaction_hash}", response_model=TransactionResponse)
async def get_transaction(
    transaction_hash: str,
    current_user: User = Depends(get_current_user),
    db_service: DuckDBService = Depends(DuckDBService)
):
    """
    Get a specific transaction by hash.
    """
    try:
        query = """
        SELECT 
            hash,
            from_address,
            to_address,
            value,
            gas,
            gas_price,
            nonce,
            input,
            block_number,
            block_hash,
            transaction_index,
            timestamp,
            network,
            subnet,
            status,
            decoded_call,
            token_symbol,
            transaction_type
        FROM transactions
        WHERE hash = $1
        """
        
        result = await db_service.execute_query(query, [transaction_hash.lower()])
        
        if not result:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return TransactionResponse(**result[0])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching transaction {transaction_hash}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transaction")

@router.get("/stats", response_model=TransactionStatsResponse)
async def get_transaction_stats(
    wallet_addresses: Optional[str] = Query(None),
    networks: Optional[str] = Query(None),
    subnets: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db_service: DuckDBService = Depends(DuckDBService)
):
    """
    Get transaction statistics.
    """
    try:
        # Build base filters (similar to main query)
        query_parts = []
        params = {}
        
        base_where = "WHERE 1=1"
        
        # Add same filters as main query
        if wallet_addresses:
            addresses = [addr.strip() for addr in wallet_addresses.split(',')]
            placeholders = ','.join([f"${len(params) + i + 1}" for i in range(len(addresses))])
            query_parts.append(f"AND (from_address IN ({placeholders}) OR to_address IN ({placeholders}))")
            for addr in addresses:
                params[f"param_{len(params) + 1}"] = addr.lower()
                params[f"param_{len(params) + 1}"] = addr.lower()
        
        # Add other filters...
        where_clause = f"{base_where} {' '.join(query_parts)}"
        
        # Execute stats queries
        stats_queries = {
            'total': f"SELECT COUNT(*) as count FROM transactions {where_clause}",
            'total_value': f"SELECT SUM(CAST(value AS DECIMAL)) as sum FROM transactions {where_clause}",
            'avg_gas': f"SELECT AVG(CAST(gas_price AS DECIMAL)) as avg FROM transactions {where_clause}",
            'networks': f"""
                SELECT network, COUNT(*) as count 
                FROM transactions {where_clause} 
                GROUP BY network
            """,
            'types': f"""
                SELECT transaction_type, COUNT(*) as count 
                FROM transactions {where_clause} 
                GROUP BY transaction_type
            """,
            'daily': f"""
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as count,
                    SUM(CAST(value AS DECIMAL)) as value
                FROM transactions {where_clause}
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                LIMIT 30
            """
        }
        
        results = {}
        param_values = list(params.values())
        
        for key, query in stats_queries.items():
            results[key] = await db_service.execute_query(query, param_values)
        
        # Format response
        total_transactions = results['total'][0]['count'] if results['total'] else 0
        total_value = str(results['total_value'][0]['sum'] or 0) if results['total_value'] else "0"
        avg_gas = str(results['avg_gas'][0]['avg'] or 0) if results['avg_gas'] else "0"
        
        network_breakdown = [
            {
                'network': row['network'],
                'count': row['count'],
                'percentage': (row['count'] / total_transactions * 100) if total_transactions > 0 else 0
            }
            for row in results['networks']
        ]
        
        type_breakdown = [
            {
                'type': row['transaction_type'],
                'count': row['count'],
                'percentage': (row['count'] / total_transactions * 100) if total_transactions > 0 else 0
            }
            for row in results['types']
        ]
        
        daily_volume = [
            {
                'date': row['date'].isoformat(),
                'count': row['count'],
                'value': str(row['value'] or 0)
            }
            for row in results['daily']
        ]
        
        return TransactionStatsResponse(
            total_transactions=total_transactions,
            total_value=total_value,
            average_gas_price=avg_gas,
            network_breakdown=network_breakdown,
            type_breakdown=type_breakdown,
            daily_volume=daily_volume
        )
        
    except Exception as e:
        logger.error(f"Error fetching transaction stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transaction statistics")
