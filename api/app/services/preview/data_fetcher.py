"""
Preview Data Fetcher

Fetches historical blockchain data from DuckLake for alert preview/dry-run.
Uses NATS request/reply pattern to query the DuckLake provider.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import nats
from django.conf import settings

logger = logging.getLogger(__name__)


class TimeRange(Enum):
    """Supported time ranges for preview queries."""
    HOUR_1 = "1h"
    HOURS_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"

    def to_timedelta(self) -> timedelta:
        """Convert time range to timedelta."""
        mapping = {
            TimeRange.HOUR_1: timedelta(hours=1),
            TimeRange.HOURS_24: timedelta(hours=24),
            TimeRange.DAYS_7: timedelta(days=7),
            TimeRange.DAYS_30: timedelta(days=30),
        }
        return mapping[self]

    @classmethod
    def from_string(cls, value: str) -> "TimeRange":
        """Parse time range from string."""
        mapping = {
            "1h": cls.HOUR_1,
            "24h": cls.HOURS_24,
            "7d": cls.DAYS_7,
            "30d": cls.DAYS_30,
        }
        if value not in mapping:
            raise ValueError(f"Invalid time range: {value}. Valid options: {list(mapping.keys())}")
        return mapping[value]


@dataclass
class PreviewDataResult:
    """Result from preview data fetch."""
    rows: List[Dict[str, Any]]
    total_rows: int
    time_range: TimeRange
    query_time_ms: float
    data_source: str
    columns: List[str] = field(default_factory=list)
    truncated: bool = False
    error: Optional[str] = None


@dataclass
class PreviewDataRequest:
    """Request configuration for preview data fetch."""
    alert_type: str  # wallet, network, token
    chain: str
    network: str = "mainnet"
    addresses: List[str] = field(default_factory=list)
    token_addresses: List[str] = field(default_factory=list)
    time_range: TimeRange = TimeRange.DAYS_7
    limit: int = 1000
    include_fields: List[str] = field(default_factory=list)


class PreviewDataFetcher:
    """
    Fetches historical blockchain data from DuckLake for alert preview.

    Uses NATS request/reply pattern to query the DuckLake provider
    for transaction and wallet balance data.
    """

    # Default columns to fetch for different data types
    TRANSACTION_COLUMNS = [
        "tx_hash",
        "block_number",
        "block_timestamp",
        "from_address",
        "to_address",
        "value",
        "value_usd",
        "gas_used",
        "gas_price",
        "status",
        "chain_id",
        "method_id",
        "method_name",
    ]

    BALANCE_COLUMNS = [
        "address",
        "token_address",
        "token_symbol",
        "balance",
        "balance_usd",
        "block_number",
        "block_timestamp",
    ]

    def __init__(
        self,
        nats_url: Optional[str] = None,
        timeout: int = 30,
        default_limit: int = 1000,
    ):
        """
        Initialize PreviewDataFetcher.

        Args:
            nats_url: NATS server URL (defaults to settings.NATS_URL)
            timeout: Query timeout in seconds
            default_limit: Default row limit for queries
        """
        self.nats_url = nats_url or getattr(settings, "NATS_URL", "nats://localhost:4222")
        self.timeout = timeout
        self.default_limit = default_limit
        self._nc = None

    async def connect(self) -> None:
        """Establish connection to NATS server."""
        if self._nc is None or not self._nc.is_connected:
            self._nc = await nats.connect(self.nats_url)
            logger.info(f"PreviewDataFetcher connected to NATS at {self.nats_url}")

    async def close(self) -> None:
        """Close NATS connection."""
        if self._nc and self._nc.is_connected:
            await self._nc.close()
            logger.info("PreviewDataFetcher closed NATS connection")

    async def _execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query against DuckLake via NATS.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            List of result rows as dictionaries

        Raises:
            Exception: If query fails or times out
        """
        await self.connect()

        request_payload = {
            "query": query,
            "params": params or {},
            "timeout": self.timeout,
        }

        try:
            response = await self._nc.request(
                "ducklake.query",
                json.dumps(request_payload).encode(),
                timeout=self.timeout,
            )

            result = json.loads(response.data.decode())

            if result.get("error"):
                logger.error(f"DuckLake query error: {result['error']}")
                raise Exception(f"DuckLake query failed: {result['error']}")

            return result.get("rows", [])

        except asyncio.TimeoutError:
            logger.error(f"DuckLake query timeout after {self.timeout}s")
            raise Exception("Query timeout")
        except Exception as e:
            logger.error(f"DuckLake query error: {e}")
            raise

    def _build_transaction_query(
        self,
        request: PreviewDataRequest,
        start_time: datetime,
        end_time: datetime,
    ) -> str:
        """
        Build SQL query for transaction data.

        Args:
            request: Preview data request configuration
            start_time: Query start timestamp
            end_time: Query end timestamp

        Returns:
            SQL query string
        """
        columns = request.include_fields or self.TRANSACTION_COLUMNS
        columns_str = ", ".join(columns)

        # Build WHERE clauses
        conditions = [
            f"block_timestamp >= '{start_time.isoformat()}'",
            f"block_timestamp <= '{end_time.isoformat()}'",
        ]

        # Add chain filter
        chain_id = self._get_chain_id(request.chain)
        if chain_id:
            conditions.append(f"chain_id = {chain_id}")

        # Add address filters
        if request.addresses:
            addresses_str = ", ".join(f"'{addr.lower()}'" for addr in request.addresses)
            conditions.append(
                f"(from_address IN ({addresses_str}) OR to_address IN ({addresses_str}))"
            )

        # Add token address filters
        if request.token_addresses:
            token_addrs_str = ", ".join(f"'{addr.lower()}'" for addr in request.token_addresses)
            conditions.append(f"token_address IN ({token_addrs_str})")

        where_clause = " AND ".join(conditions)

        query = f"""
        SELECT {columns_str}
        FROM transactions
        WHERE {where_clause}
        ORDER BY block_timestamp DESC
        LIMIT {request.limit}
        """

        return query.strip()

    def _build_balance_query(
        self,
        request: PreviewDataRequest,
        start_time: datetime,
        end_time: datetime,
    ) -> str:
        """
        Build SQL query for wallet balance data.

        Args:
            request: Preview data request configuration
            start_time: Query start timestamp
            end_time: Query end timestamp

        Returns:
            SQL query string
        """
        columns = request.include_fields or self.BALANCE_COLUMNS
        columns_str = ", ".join(columns)

        conditions = [
            f"block_timestamp >= '{start_time.isoformat()}'",
            f"block_timestamp <= '{end_time.isoformat()}'",
        ]

        # Add address filter
        if request.addresses:
            addresses_str = ", ".join(f"'{addr.lower()}'" for addr in request.addresses)
            conditions.append(f"address IN ({addresses_str})")

        # Add chain filter
        chain_id = self._get_chain_id(request.chain)
        if chain_id:
            conditions.append(f"chain_id = {chain_id}")

        where_clause = " AND ".join(conditions)

        query = f"""
        SELECT {columns_str}
        FROM wallet_balances
        WHERE {where_clause}
        ORDER BY block_timestamp DESC
        LIMIT {request.limit}
        """

        return query.strip()

    def _get_chain_id(self, chain: str) -> Optional[int]:
        """
        Map chain name to chain ID.

        Args:
            chain: Chain name (e.g., 'ethereum', 'polygon')

        Returns:
            Chain ID or None if not found
        """
        chain_mapping = {
            "ethereum": 1,
            "eth": 1,
            "polygon": 137,
            "matic": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "base": 8453,
            "avalanche": 43114,
            "avax": 43114,
            "bsc": 56,
            "bnb": 56,
            "solana": -1,  # Special handling for non-EVM
            "sol": -1,
            "bitcoin": -2,
            "btc": -2,
        }
        return chain_mapping.get(chain.lower())

    async def fetch_transactions(
        self,
        request: PreviewDataRequest,
    ) -> PreviewDataResult:
        """
        Fetch historical transaction data for preview.

        Args:
            request: Preview data request configuration

        Returns:
            PreviewDataResult with transaction data
        """
        import time
        start = time.time()

        end_time = datetime.utcnow()
        start_time = end_time - request.time_range.to_timedelta()

        query = self._build_transaction_query(request, start_time, end_time)

        try:
            rows = await self._execute_query(query)
            query_time_ms = (time.time() - start) * 1000

            columns = request.include_fields or self.TRANSACTION_COLUMNS

            return PreviewDataResult(
                rows=rows,
                total_rows=len(rows),
                time_range=request.time_range,
                query_time_ms=query_time_ms,
                data_source="transactions",
                columns=columns,
                truncated=len(rows) >= request.limit,
            )

        except Exception as e:
            query_time_ms = (time.time() - start) * 1000
            logger.error(f"Failed to fetch transactions: {e}")
            return PreviewDataResult(
                rows=[],
                total_rows=0,
                time_range=request.time_range,
                query_time_ms=query_time_ms,
                data_source="transactions",
                error=str(e),
            )

    async def fetch_balances(
        self,
        request: PreviewDataRequest,
    ) -> PreviewDataResult:
        """
        Fetch historical wallet balance data for preview.

        Args:
            request: Preview data request configuration

        Returns:
            PreviewDataResult with balance data
        """
        import time
        start = time.time()

        end_time = datetime.utcnow()
        start_time = end_time - request.time_range.to_timedelta()

        query = self._build_balance_query(request, start_time, end_time)

        try:
            rows = await self._execute_query(query)
            query_time_ms = (time.time() - start) * 1000

            columns = request.include_fields or self.BALANCE_COLUMNS

            return PreviewDataResult(
                rows=rows,
                total_rows=len(rows),
                time_range=request.time_range,
                query_time_ms=query_time_ms,
                data_source="wallet_balances",
                columns=columns,
                truncated=len(rows) >= request.limit,
            )

        except Exception as e:
            query_time_ms = (time.time() - start) * 1000
            logger.error(f"Failed to fetch balances: {e}")
            return PreviewDataResult(
                rows=[],
                total_rows=0,
                time_range=request.time_range,
                query_time_ms=query_time_ms,
                data_source="wallet_balances",
                error=str(e),
            )

    async def fetch_for_alert_type(
        self,
        alert_type: str,
        chain: str,
        addresses: Optional[List[str]] = None,
        token_addresses: Optional[List[str]] = None,
        time_range: str = "7d",
        limit: int = 1000,
    ) -> PreviewDataResult:
        """
        Fetch data appropriate for the alert type.

        Convenience method that selects the right data source based on alert type.

        Args:
            alert_type: Alert type (wallet, network, token)
            chain: Blockchain chain name
            addresses: List of wallet addresses to filter
            token_addresses: List of token addresses to filter
            time_range: Time range string (1h, 24h, 7d, 30d)
            limit: Maximum rows to return

        Returns:
            PreviewDataResult with appropriate data
        """
        request = PreviewDataRequest(
            alert_type=alert_type,
            chain=chain,
            addresses=addresses or [],
            token_addresses=token_addresses or [],
            time_range=TimeRange.from_string(time_range),
            limit=limit,
        )

        # Wallet and network alerts typically need transaction data
        # Token alerts may need both transactions and balances
        if alert_type in ("wallet", "network"):
            return await self.fetch_transactions(request)
        elif alert_type == "token":
            # For token alerts, prefer transactions but could extend to balances
            return await self.fetch_transactions(request)
        else:
            # Default to transactions
            return await self.fetch_transactions(request)


# Global fetcher instance
_preview_fetcher: Optional[PreviewDataFetcher] = None


def get_preview_fetcher() -> PreviewDataFetcher:
    """Get or create the global PreviewDataFetcher instance."""
    global _preview_fetcher
    if _preview_fetcher is None:
        _preview_fetcher = PreviewDataFetcher()
    return _preview_fetcher
