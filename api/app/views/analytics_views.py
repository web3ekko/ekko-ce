"""Analytics API views using direct DuckLake queries.

These endpoints provide direct access to blockchain analytics data
stored in the DuckLake lakehouse format.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from django.utils import timezone

from app.models.alerts import AlertInstance, AlertType
from app.services.duckdb_service import get_ducklake_service
from app.services.ducklake_client import DuckLakeClient
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


# =============================================================================
# Chain Mapping Constants for Newsfeed
# =============================================================================

# Maps short chain codes (used in target_keys) to DuckLake chain names
CHAIN_CODE_TO_NAME: Dict[str, str] = {
    "ETH": "ethereum",
    "SOL": "solana",
    "BTC": "bitcoin",
    "AVAX": "avalanche",
    "MATIC": "polygon",
    "ARB": "arbitrum",
    "OP": "optimism",
    "BASE": "base",
    "BSC": "bsc",
    "FTM": "fantom",
}


# =============================================================================
# Newsfeed Helper Functions
# =============================================================================


def _get_user_monitored_addresses(user) -> List[str]:
    """
    Get all wallet target keys from user's enabled wallet alerts.

    Queries AlertInstance for enabled wallet alerts and collects all
    target keys (individual wallets or from wallet groups).

    Args:
        user: Django User instance

    Returns:
        List of target keys in format ["ETH:mainnet:0x123...", ...]
    """
    target_keys: List[str] = []

    # Get all enabled wallet alerts for this user
    wallet_alerts = AlertInstance.objects.filter(
        user=user,
        enabled=True,
        alert_type=AlertType.WALLET,
    ).select_related("target_group")

    for alert in wallet_alerts:
        # get_effective_targets returns target_keys or group members
        targets = alert.get_effective_targets()
        target_keys.extend(targets)

    # Deduplicate while preserving order
    seen = set()
    unique_keys = []
    for key in target_keys:
        if key not in seen:
            seen.add(key)
            unique_keys.append(key)

    return unique_keys


def _parse_target_keys(
    keys: List[str],
    chain_filter: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    Parse target keys into chain_id → addresses mapping.

    Converts short chain codes to full DuckLake chain_ids and groups
    addresses by chain for efficient querying.

    Args:
        keys: List of target keys ["ETH:mainnet:0x123...", "SOL:mainnet:ABC..."]
        chain_filter: Optional comma-separated chain_ids to filter by

    Returns:
        Dict mapping chain_id to list of addresses:
        {"ethereum_mainnet": ["0x123...", "0x456..."], "solana_mainnet": ["ABC..."]}
    """
    # Parse chain filter if provided
    allowed_chains: Optional[set] = None
    if chain_filter:
        allowed_chains = {c.strip().lower() for c in chain_filter.split(",")}

    result: Dict[str, List[str]] = {}

    for key in keys:
        parts = key.split(":")
        if len(parts) < 3:
            logger.warning(f"Invalid target key format: {key}")
            continue

        chain_code = parts[0].upper()
        network = parts[1].lower()
        address = parts[2]

        # Convert chain code to full name
        chain_name = CHAIN_CODE_TO_NAME.get(chain_code, chain_code.lower())

        # Build chain_id (e.g., "ethereum_mainnet")
        chain_id = f"{chain_name}_{network}"

        # Apply chain filter if specified
        if allowed_chains and chain_id not in allowed_chains:
            continue

        # Group addresses by chain_id
        if chain_id not in result:
            result[chain_id] = []
        if address not in result[chain_id]:  # Deduplicate
            result[chain_id].append(address)

    return result


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _format_sql_list(values: List[str]) -> str:
    return ", ".join(f"'{_escape_sql_literal(v)}'" for v in values)


def _split_chain_id(chain_id: str) -> Tuple[str, str]:
    if "_" not in chain_id:
        return chain_id, "default"
    chain, subnet = chain_id.rsplit("_", 1)
    return chain, subnet


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_health(request: Request) -> Response:
    """Check DuckLake analytics service health.

    Returns:
        Service health status including catalog info and available tables.
    """
    service = get_ducklake_service()
    return Response(service.health_check())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_snapshots(request: Request) -> Response:
    """Get available DuckLake snapshots for time travel.

    Returns:
        List of snapshots with their IDs and timestamps.
    """
    service = get_ducklake_service()
    try:
        snapshots = service.get_snapshots()
        return Response({"snapshots": snapshots})
    except Exception as e:
        logger.error(f"Failed to get snapshots: {e}")
        return Response(
            {"error": "Failed to retrieve snapshots"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_tables(request: Request) -> Response:
    """Get list of available tables in the DuckLake catalog.

    Returns:
        List of table names.
    """
    service = get_ducklake_service()
    try:
        tables = service.get_tables()
        return Response({"tables": tables})
    except Exception as e:
        logger.error(f"Failed to get tables: {e}")
        return Response(
            {"error": "Failed to retrieve tables"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_table_schema(request: Request, table_name: str) -> Response:
    """Get schema information for a specific table.

    Args:
        table_name: Name of the table to get schema for.

    Returns:
        Column information for the table.
    """
    service = get_ducklake_service()
    try:
        schema = service.get_table_schema(table_name)
        return Response({"table": table_name, "columns": schema})
    except Exception as e:
        logger.error(f"Failed to get table schema: {e}")
        return Response(
            {"error": f"Failed to retrieve schema for table '{table_name}'"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_transactions(request: Request, address: str) -> Response:
    """Get transaction history for a wallet.

    Args:
        address: Wallet address to query.

    Query Parameters:
        chain: Blockchain network (default: 'ethereum')
        limit: Maximum number of results (default: 100)
        snapshot_id: Optional snapshot ID for time travel queries

    Returns:
        List of transactions involving the wallet.
    """
    service = get_ducklake_service()
    chain = request.query_params.get("chain", "ethereum")
    limit = int(request.query_params.get("limit", 100))
    snapshot_id = request.query_params.get("snapshot_id", None)

    # Sanitize and validate inputs
    if limit > 1000:
        limit = 1000

    sql = """
        SELECT hash, block_number, from_address, to_address,
               value, gas_used, timestamp, status
        FROM transactions
        WHERE (from_address = $address OR to_address = $address)
          AND chain = $chain
        ORDER BY timestamp DESC
        LIMIT $limit
    """
    params: Dict[str, Any] = {"address": address, "chain": chain, "limit": limit}

    try:
        # Support time travel via snapshot_id
        if snapshot_id:
            results = service.query_at_snapshot(sql, int(snapshot_id), params)
        else:
            results = service.query(sql, params)

        return Response({"address": address, "chain": chain, "transactions": results})
    except Exception as e:
        logger.error(f"Failed to get wallet transactions: {e}")
        return Response(
            {"error": "Failed to retrieve transactions"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_token_transfers(request: Request, address: str) -> Response:
    """Get token transfer history for a wallet.

    Args:
        address: Wallet address to query.

    Query Parameters:
        chain: Blockchain network (default: 'ethereum')
        token: Optional token address or symbol to filter by
        limit: Maximum number of results (default: 100)
        snapshot_id: Optional snapshot ID for time travel queries

    Returns:
        List of token transfers involving the wallet.
    """
    service = get_ducklake_service()
    chain = request.query_params.get("chain", "ethereum")
    token = request.query_params.get("token", None)
    limit = int(request.query_params.get("limit", 100))
    snapshot_id = request.query_params.get("snapshot_id", None)

    # Sanitize and validate inputs
    if limit > 1000:
        limit = 1000

    sql = """
        SELECT tx_hash, token_address, token_symbol,
               from_address, to_address, value, token_decimals, timestamp
        FROM token_transfers
        WHERE (from_address = $address OR to_address = $address)
          AND chain = $chain
    """
    params: Dict[str, Any] = {"address": address, "chain": chain}

    if token:
        sql += " AND (token_address = $token OR token_symbol = $token)"
        params["token"] = token

    sql += " ORDER BY timestamp DESC LIMIT $limit"
    params["limit"] = limit

    try:
        # Support time travel via snapshot_id
        if snapshot_id:
            results = service.query_at_snapshot(sql, int(snapshot_id), params)
        else:
            results = service.query(sql, params)

        return Response({"address": address, "chain": chain, "transfers": results})
    except Exception as e:
        logger.error(f"Failed to get token transfers: {e}")
        return Response(
            {"error": "Failed to retrieve token transfers"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_balances(request: Request, address: str) -> Response:
    """Get current token balances for a wallet.

    Args:
        address: Wallet address to query.

    Query Parameters:
        chain: Blockchain network (default: 'ethereum')
        snapshot_id: Optional snapshot ID for time travel queries

    Returns:
        Current token balances for the wallet.
    """
    service = get_ducklake_service()
    chain = request.query_params.get("chain", "ethereum")
    snapshot_id = request.query_params.get("snapshot_id", None)

    sql = """
        SELECT token_address, token_symbol, balance, token_decimals,
               last_updated
        FROM balances
        WHERE wallet_address = $address
          AND chain = $chain
        ORDER BY balance DESC
    """
    params: Dict[str, Any] = {"address": address, "chain": chain}

    try:
        if snapshot_id:
            results = service.query_at_snapshot(sql, int(snapshot_id), params)
        else:
            results = service.query(sql, params)

        return Response({"address": address, "chain": chain, "balances": results})
    except Exception as e:
        logger.error(f"Failed to get wallet balances: {e}")
        return Response(
            {"error": "Failed to retrieve balances"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def block_info(request: Request, block_number: int) -> Response:
    """Get information about a specific block.

    Args:
        block_number: Block number to query.

    Query Parameters:
        chain: Blockchain network (default: 'ethereum')

    Returns:
        Block details.
    """
    service = get_ducklake_service()
    chain = request.query_params.get("chain", "ethereum")

    sql = """
        SELECT block_number, block_hash, parent_hash, timestamp,
               gas_used, gas_limit, transaction_count
        FROM blocks
        WHERE block_number = $block_number
          AND chain = $chain
    """
    params: Dict[str, Any] = {"block_number": block_number, "chain": chain}

    try:
        results = service.query(sql, params)
        if not results:
            return Response(
                {"error": f"Block {block_number} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"chain": chain, "block": results[0]})
    except Exception as e:
        logger.error(f"Failed to get block info: {e}")
        return Response(
            {"error": "Failed to retrieve block information"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def token_prices(request: Request, token_address: str) -> Response:
    """Get historical price data for a token.

    Args:
        token_address: Token contract address.

    Query Parameters:
        chain: Blockchain network (default: 'ethereum')
        limit: Maximum number of results (default: 100)

    Returns:
        Historical price data for the token.
    """
    service = get_ducklake_service()
    chain = request.query_params.get("chain", "ethereum")
    limit = int(request.query_params.get("limit", 100))

    if limit > 1000:
        limit = 1000

    sql = """
        SELECT token_address, price_usd, volume_24h,
               market_cap, timestamp
        FROM prices
        WHERE token_address = $token_address
          AND chain = $chain
        ORDER BY timestamp DESC
        LIMIT $limit
    """
    params: Dict[str, Any] = {
        "token_address": token_address,
        "chain": chain,
        "limit": limit,
    }

    try:
        results = service.query(sql, params)
        return Response(
            {"token_address": token_address, "chain": chain, "prices": results}
        )
    except Exception as e:
        logger.error(f"Failed to get token prices: {e}")
        return Response(
            {"error": "Failed to retrieve token prices"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Transaction Newsfeed Endpoint
# =============================================================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def newsfeed_transactions(request: Request) -> Response:
    """
    Get transaction newsfeed for user's monitored wallets.

    Returns transactions involving wallets the user monitors via alerts,
    queried from the DuckLake address_transactions index joined with
    the unified transactions table.

    Query Parameters:
        limit: Maximum number of results (default: 50, max: 500)
        offset: Pagination offset (default: 0)
        chains: Comma-separated chain_ids to filter (e.g., "ethereum_mainnet,polygon_mainnet")
        start_date: ISO 8601 datetime for oldest transactions (default: 24h ago)
        transaction_type: Filter by type (TRANSFER, CONTRACT_CALL, CONTRACT_CREATE)

    Returns:
        JSON response with transactions list and metadata:
        {
            "transactions": [...],
            "total": 152,
            "monitored_addresses": 5,
            "chains": ["ethereum_mainnet", "polygon_mainnet"]
        }
    """
    # Parse query parameters
    limit = min(int(request.query_params.get("limit", 50)), 500)
    offset = int(request.query_params.get("offset", 0))
    chain_filter = request.query_params.get("chains", None)
    transaction_type_filter = request.query_params.get("transaction_type", None)

    # Parse start_date (default: 24 hours ago)
    start_date_str = request.query_params.get("start_date", None)
    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        except ValueError:
            return Response(
                {"error": "Invalid start_date format. Use ISO 8601."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        start_date = timezone.now() - timedelta(hours=24)

    # Get user's monitored wallet addresses
    target_keys = _get_user_monitored_addresses(request.user)

    if not target_keys:
        # No monitored wallets - return empty response
        return Response({
            "transactions": [],
            "total": 0,
            "monitored_addresses": 0,
            "chains": [],
        })

    # Parse target keys into chain_id → addresses mapping
    chain_addresses = _parse_target_keys(target_keys, chain_filter)

    if not chain_addresses:
        # No addresses match the filter - return empty response
        return Response({
            "transactions": [],
            "total": 0,
            "monitored_addresses": len(target_keys),
            "chains": [],
        })

    # Collect all addresses and chain_ids for query
    all_addresses: List[str] = []
    all_chain_ids: List[str] = list(chain_addresses.keys())
    for addresses in chain_addresses.values():
        all_addresses.extend(addresses)
    all_addresses = list(set(all_addresses))  # Deduplicate

    start_date_iso = start_date.isoformat()
    start_date_date = start_date.date().isoformat()
    per_chain_limit = limit + offset

    try:
        async def run_queries() -> Tuple[List[List[Dict[str, Any]]], List[str]]:
            client = DuckLakeClient()
            tasks: List[asyncio.Task[List[Dict[str, Any]]]] = []
            chain_order: List[str] = []
            try:
                for chain_id, addresses in chain_addresses.items():
                    if not addresses:
                        continue

                    chain, subnet = _split_chain_id(chain_id)
                    address_list = _format_sql_list(addresses)
                    chain_literal = _escape_sql_literal(chain_id)

                    sql = f"""
                        SELECT
                            t.transaction_hash,
                            t.block_timestamp,
                            t.chain_id,
                            t.from_address,
                            t.to_address,
                            addr_tx.address AS monitored_address,
                            addr_tx.is_sender,
                            t.amount_native,
                            t.amount_usd,
                            t.transaction_type,
                            t.transaction_subtype,
                            t.decoded_function_name,
                            t.decoded_summary,
                            t.status
                        FROM address_transactions addr_tx
                        INNER JOIN transactions t
                            ON addr_tx.chain_id = t.chain_id
                            AND addr_tx.transaction_hash = t.transaction_hash
                        WHERE addr_tx.address IN ({address_list})
                          AND addr_tx.chain_id = '{chain_literal}'
                          AND addr_tx.block_date >= CAST('{start_date_date}' AS DATE)
                    """

                    if transaction_type_filter:
                        transaction_literal = _escape_sql_literal(transaction_type_filter.upper())
                        sql += f" AND t.transaction_type = '{transaction_literal}'"

                    sql += f"""
                        ORDER BY t.block_timestamp DESC
                        LIMIT {per_chain_limit}
                    """

                    count_sql = f"""
                        SELECT COUNT(*) as total
                        FROM address_transactions addr_tx
                        WHERE addr_tx.address IN ({address_list})
                          AND addr_tx.chain_id = '{chain_literal}'
                  AND addr_tx.block_date >= CAST('{start_date_date}' AS DATE)
                    """

                    tasks.append(asyncio.create_task(
                        client.query_rows(
                            query=sql,
                            table="address_transactions",
                            chain=chain,
                            subnet=subnet,
                        )
                    ))
                    tasks.append(asyncio.create_task(
                        client.query_rows(
                            query=count_sql,
                            table="address_transactions",
                            chain=chain,
                            subnet=subnet,
                        )
                    ))
                    chain_order.append(chain_id)

                if not tasks:
                    return [], []

                results = await asyncio.gather(*tasks)
                return results, chain_order
            finally:
                await client.close()

        results, chain_order = async_to_sync(run_queries)()

        if not results:
            return Response({
                "transactions": [],
                "total": 0,
                "monitored_addresses": len(all_addresses),
                "chains": all_chain_ids,
            })

        combined: List[Dict[str, Any]] = []
        total = 0
        for index, chain_id in enumerate(chain_order):
            data_rows = results[index * 2]
            count_rows = results[index * 2 + 1]
            combined.extend(data_rows)
            if count_rows:
                total += count_rows[0].get("total", 0)

        combined.sort(
            key=lambda row: row.get("block_timestamp") or "",
            reverse=True,
        )
        paged = combined[offset: offset + limit]

        return Response({
            "transactions": paged,
            "total": total,
            "monitored_addresses": len(all_addresses),
            "chains": all_chain_ids,
        })

    except Exception as e:
        error_message = str(e)
        if "address_transactions" in error_message or "metadata.ducklake" in error_message:
            logger.warning(f"DuckLake newsfeed unavailable: {e}")
            return Response({
                "transactions": [],
                "total": 0,
                "monitored_addresses": len(all_addresses),
                "chains": all_chain_ids,
                "warning": "Newsfeed unavailable. DuckLake data not ready.",
            })

        logger.error(f"Failed to get newsfeed transactions: {e}")
        return Response(
            {"error": "Failed to retrieve newsfeed transactions"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
