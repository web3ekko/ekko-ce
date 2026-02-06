"""
DuckLake client for querying analytics data via NATS.

This module provides a client interface to query the DuckLake provider
through NATS request/reply messaging for notification delivery analytics.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import nats
from nats.aio.client import Client as NATSClient
from django.conf import settings

logger = logging.getLogger(__name__)


class DuckLakeQueryError(RuntimeError):
    """Raised when DuckLake returns an error response instead of Arrow IPC."""


def _is_missing_table_error(message: str, table: str) -> bool:
    msg = (message or "").lower()
    return (
        "failed to prepare query" in msg
        or "does not exist" in msg
        or "unknown table" in msg
        or f"table with name {table.lower()}" in msg
        or table.lower() in msg and "table" in msg
    )


@dataclass
class DeliveryMetrics:
    """Aggregated delivery metrics for a time period."""
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    success_rate: float
    avg_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    error_breakdown: Dict[str, int]
    hourly_volume: List[Dict[str, Any]]
    channel_breakdown: Dict[str, Dict[str, Any]]


@dataclass
class ChannelHealthMetrics:
    """Health metrics for a specific notification channel."""
    channel_id: str
    channel_type: str
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    success_rate: float
    avg_response_time_ms: float
    last_success_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    last_error: Optional[str]
    consecutive_failures: int
    is_healthy: bool


@dataclass
class NotificationHistoryItem:
    """A single notification in user history."""
    notification_id: str
    alert_id: str
    alert_name: str
    title: str
    message: str
    priority: str
    delivery_status: str
    channels_delivered: int
    channels_failed: int
    created_at: datetime
    transaction_hash: Optional[str] = None
    chain_id: Optional[str] = None
    block_number: Optional[int] = None
    value_usd: Optional[float] = None
    target_channels: Optional[List[str]] = None


@dataclass
class NotificationHistoryResponse:
    """Paginated notification history response."""
    count: int
    items: List[NotificationHistoryItem]
    has_more: bool


class DuckLakeClient:
    """
    Client for querying DuckLake provider via NATS.

    Uses NATS request/reply pattern to query the DuckLake provider
    for notification delivery analytics stored in DuckDB/DuckLake.
    """

    def __init__(self, nats_url: Optional[str] = None, timeout: int = 30):
        """
        Initialize DuckLake client.

        Args:
            nats_url: NATS server URL (defaults to settings.NATS_URL)
            timeout: Request timeout in seconds
        """
        self.nats_url = nats_url or getattr(settings, 'NATS_URL', 'nats://localhost:4222')
        self.timeout = timeout
        self._nc: Optional[NATSClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self):
        """Establish connection to NATS server."""
        current_loop = asyncio.get_running_loop()

        if self._nc is not None:
            same_loop = self._loop is current_loop
            if self._nc.is_connected and same_loop:
                return
            try:
                await self._nc.close()
            except Exception:
                logger.debug("Failed to close stale NATS connection", exc_info=True)
            self._nc = None

        self._nc = await nats.connect(self.nats_url)
        self._loop = current_loop
        logger.info(f"Connected to NATS at {self.nats_url}")

    async def close(self):
        """Close NATS connection."""
        if self._nc and self._nc.is_connected:
            await self._nc.close()
            logger.info("Closed NATS connection")
        self._nc = None
        self._loop = None

    async def _query(
        self,
        *,
        query: str,
        table: str,
        params: Optional[List[Dict[str, Any]]] = None,
        chain: Optional[str] = None,
        subnet: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query against DuckLake via NATS.

        Args:
            query: SQL query string
            table: DuckLake table name
            params: Optional query parameters (DuckLake typed params)
            chain: Optional chain name (default: ekko)
            subnet: Optional subnet name (default: default)
            limit: Optional row limit

        Returns:
            List of result rows as dictionaries
        """
        await self.connect()

        resolved_chain, resolved_subnet = self._resolve_chain_subnet(chain, subnet)
        subject = self._build_query_subject(table, resolved_chain, resolved_subnet)

        request_payload = {
            "query": query,
            "limit": int(limit) if limit is not None else None,
            "timeout_seconds": self.timeout,
            "parameters": params or None,
        }

        try:
            response = await self._nc.request(
                subject,
                json.dumps(request_payload).encode(),
                timeout=self.timeout,
            )
            return _decode_arrow_ipc_rows(response.data)

        except asyncio.TimeoutError:
            logger.error(f"DuckLake query timeout after {self.timeout}s")
            raise Exception("Query timeout")
        except Exception as e:
            logger.error(f"DuckLake query error: {e}")
            raise

    async def query_rows(
        self,
        *,
        query: str,
        table: str,
        params: Optional[List[Dict[str, Any]]] = None,
        chain: Optional[str] = None,
        subnet: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return await self._query(
            query=query,
            table=table,
            params=params,
            chain=chain,
            subnet=subnet,
            limit=limit,
        )

    @staticmethod
    def _resolve_chain_subnet(
        chain: Optional[str], subnet: Optional[str]
    ) -> Tuple[str, str]:
        resolved_chain = (chain or "ekko").strip() or "ekko"
        resolved_subnet = (subnet or "default").strip() or "default"
        return resolved_chain, resolved_subnet

    @staticmethod
    def _build_query_subject(table: str, chain: str, subnet: str) -> str:
        return f"ducklake.{table}.{chain}.{subnet}.query"

    async def get_platform_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        channel_type: Optional[str] = None
    ) -> DeliveryMetrics:
        """
        Get aggregated platform health metrics for a time period.

        Args:
            start_date: Start of time range
            end_date: End of time range
            channel_type: Optional filter by channel type (slack, telegram, webhook)

        Returns:
            DeliveryMetrics with aggregated statistics
        """
        # Build channel filter
        channel_filter = ""
        if channel_type:
            channel_filter = f"AND channel_type = '{channel_type}'"

        # Query for overall metrics
        overall_query = f"""
        SELECT
            COUNT(*) as total_deliveries,
            SUM(CASE WHEN delivery_status = 'DELIVERED' THEN 1 ELSE 0 END) as successful_deliveries,
            SUM(CASE WHEN delivery_status = 'FAILED' THEN 1 ELSE 0 END) as failed_deliveries,
            AVG(response_time_ms) as avg_response_time_ms,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms) as p50_response_time_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_response_time_ms,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99_response_time_ms
        FROM notification_deliveries
        WHERE delivery_date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
        {channel_filter}
        """

        # Query for error breakdown
        error_query = f"""
        SELECT
            error_type,
            COUNT(*) as count
        FROM notification_deliveries
        WHERE delivery_date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
        AND delivery_status = 'FAILED'
        AND error_type IS NOT NULL
        {channel_filter}
        GROUP BY error_type
        ORDER BY count DESC
        """

        # Query for hourly volume
        hourly_query = f"""
        SELECT
            DATE_TRUNC('hour', started_at) as hour,
            COUNT(*) as volume,
            SUM(CASE WHEN delivery_status = 'DELIVERED' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN delivery_status = 'FAILED' THEN 1 ELSE 0 END) as failed
        FROM notification_deliveries
        WHERE delivery_date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
        {channel_filter}
        GROUP BY hour
        ORDER BY hour
        """

        # Query for channel breakdown
        channel_query = f"""
        SELECT
            channel_type,
            COUNT(*) as total,
            SUM(CASE WHEN delivery_status = 'DELIVERED' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN delivery_status = 'FAILED' THEN 1 ELSE 0 END) as failed,
            AVG(response_time_ms) as avg_response_time
        FROM notification_deliveries
        WHERE delivery_date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
        GROUP BY channel_type
        """

        # Execute queries in parallel
        overall_results, error_results, hourly_results, channel_results = await asyncio.gather(
            self._query(query=overall_query, table="notification_deliveries"),
            self._query(query=error_query, table="notification_deliveries"),
            self._query(query=hourly_query, table="notification_deliveries"),
            self._query(query=channel_query, table="notification_deliveries"),
        )

        # Parse results
        overall = overall_results[0] if overall_results else {}
        total = overall.get('total_deliveries', 0)
        successful = overall.get('successful_deliveries', 0)

        success_rate = (successful / total * 100) if total > 0 else 0.0

        error_breakdown = {
            row['error_type']: row['count']
            for row in error_results
        }

        hourly_volume = [
            {
                'hour': row['hour'],
                'volume': row['volume'],
                'successful': row['successful'],
                'failed': row['failed']
            }
            for row in hourly_results
        ]

        channel_breakdown = {
            row['channel_type']: {
                'total': row['total'],
                'successful': row['successful'],
                'failed': row['failed'],
                'success_rate': (row['successful'] / row['total'] * 100) if row['total'] > 0 else 0.0,
                'avg_response_time': row['avg_response_time']
            }
            for row in channel_results
        }

        return DeliveryMetrics(
            total_deliveries=total,
            successful_deliveries=successful,
            failed_deliveries=overall.get('failed_deliveries', 0),
            success_rate=success_rate,
            avg_response_time_ms=overall.get('avg_response_time_ms', 0.0),
            p50_response_time_ms=overall.get('p50_response_time_ms', 0.0),
            p95_response_time_ms=overall.get('p95_response_time_ms', 0.0),
            p99_response_time_ms=overall.get('p99_response_time_ms', 0.0),
            error_breakdown=error_breakdown,
            hourly_volume=hourly_volume,
            channel_breakdown=channel_breakdown
        )

    async def get_user_notifications(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        priority: Optional[str] = None,
        alert_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> NotificationHistoryResponse:
        """
        Get notification history for a user.

        Args:
            user_id: User identifier
            limit: Maximum results to return (default 50, max 100)
            offset: Number of results to skip for pagination
            priority: Optional filter by priority (critical, high, normal, low)
            alert_id: Optional filter by specific alert
            start_date: Optional start of date range
            end_date: Optional end of date range

        Returns:
            NotificationHistoryResponse with paginated notification history
        """
        # Validate and clamp limit
        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        # Build WHERE clauses
        where_clauses = [f"user_id = '{user_id}'"]

        if priority:
            where_clauses.append(f"priority = '{priority.lower()}'")

        if alert_id:
            where_clauses.append(f"alert_id = '{alert_id}'")

        if start_date:
            where_clauses.append(f"created_at >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'")

        if end_date:
            where_clauses.append(f"created_at <= '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'")

        where_clause = " AND ".join(where_clauses)

        # Query for count
        count_query = f"""
        SELECT COUNT(*) as total_count
        FROM notification_content
        WHERE {where_clause}
        """

        # Query for paginated results
        data_query = f"""
        SELECT
            notification_id,
            alert_id,
            alert_name,
            title,
            message,
            priority,
            delivery_status,
            channels_delivered,
            channels_failed,
            created_at,
            transaction_hash,
            chain_id,
            block_number,
            value_usd,
            target_channels
        FROM notification_content
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT {limit}
        OFFSET {offset}
        """

        # Execute queries in parallel
        try:
            count_results, data_results = await asyncio.gather(
                self._query(query=count_query, table="notification_content"),
                self._query(query=data_query, table="notification_content"),
            )
        except DuckLakeQueryError as exc:
            if _is_missing_table_error(str(exc), "notification_content"):
                logger.warning(
                    "DuckLake table notification_content missing or not ready. Returning empty history."
                )
                return NotificationHistoryResponse(count=0, items=[], has_more=False)
            raise

        # Parse count
        total_count = count_results[0].get('total_count', 0) if count_results else 0

        # Parse notification items
        items = []
        for row in data_results:
            # Parse target_channels from JSON if present
            target_channels = row.get('target_channels')
            if isinstance(target_channels, str):
                try:
                    target_channels = json.loads(target_channels)
                except json.JSONDecodeError:
                    target_channels = None

            # Parse created_at timestamp
            created_at = row.get('created_at')
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except ValueError:
                    created_at = datetime.utcnow()

            item = NotificationHistoryItem(
                notification_id=row.get('notification_id', ''),
                alert_id=row.get('alert_id', ''),
                alert_name=row.get('alert_name', ''),
                title=row.get('title', ''),
                message=row.get('message', ''),
                priority=row.get('priority', 'normal'),
                delivery_status=row.get('delivery_status', 'unknown'),
                channels_delivered=row.get('channels_delivered', 0) or 0,
                channels_failed=row.get('channels_failed', 0) or 0,
                created_at=created_at,
                transaction_hash=row.get('transaction_hash'),
                chain_id=row.get('chain_id'),
                block_number=row.get('block_number'),
                value_usd=row.get('value_usd'),
                target_channels=target_channels,
            )
            items.append(item)

        # Determine if there are more results
        has_more = (offset + len(items)) < total_count

        return NotificationHistoryResponse(
            count=total_count,
            items=items,
            has_more=has_more,
        )

    async def get_channel_health(
        self,
        channel_id: str,
        lookback_hours: int = 24
    ) -> ChannelHealthMetrics:
        """
        Get health metrics for a specific notification channel.

        Args:
            channel_id: Channel identifier (user_id)
            lookback_hours: Hours to look back for metrics

        Returns:
            ChannelHealthMetrics for the channel
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=lookback_hours)

        query = f"""
        SELECT
            channel_id,
            channel_type,
            COUNT(*) as total_deliveries,
            SUM(CASE WHEN delivery_status = 'DELIVERED' THEN 1 ELSE 0 END) as successful_deliveries,
            SUM(CASE WHEN delivery_status = 'FAILED' THEN 1 ELSE 0 END) as failed_deliveries,
            AVG(response_time_ms) as avg_response_time_ms,
            MAX(CASE WHEN delivery_status = 'DELIVERED' THEN completed_at END) as last_success_at,
            MAX(CASE WHEN delivery_status = 'FAILED' THEN completed_at END) as last_failure_at,
            (SELECT error_message FROM notification_deliveries
             WHERE channel_id = '{channel_id}'
             AND delivery_status = 'FAILED'
             ORDER BY started_at DESC LIMIT 1) as last_error
        FROM notification_deliveries
        WHERE channel_id = '{channel_id}'
        AND delivery_date >= '{start_date.strftime('%Y-%m-%d')}'
        GROUP BY channel_id, channel_type
        """

        results = await self._query(query=query, table="notification_deliveries")

        if not results:
            raise ValueError(f"No data found for channel {channel_id}")

        row = results[0]
        total = row['total_deliveries']
        successful = row['successful_deliveries']
        failed = row['failed_deliveries']

        success_rate = (successful / total * 100) if total > 0 else 0.0

        # Calculate consecutive failures (simplified - would need ordering in real implementation)
        consecutive_failures = failed if failed > 0 else 0
        is_healthy = consecutive_failures < 3 and success_rate >= 90.0

        return ChannelHealthMetrics(
            channel_id=channel_id,
            channel_type=row['channel_type'],
            total_deliveries=total,
            successful_deliveries=successful,
            failed_deliveries=failed,
            success_rate=success_rate,
            avg_response_time_ms=row['avg_response_time_ms'] or 0.0,
            last_success_at=row.get('last_success_at'),
            last_failure_at=row.get('last_failure_at'),
            last_error=row.get('last_error'),
            consecutive_failures=consecutive_failures,
            is_healthy=is_healthy
        )


# Global client instance
_ducklake_client: Optional[DuckLakeClient] = None


def get_ducklake_client() -> DuckLakeClient:
    """Get or create the global DuckLake client instance."""
    global _ducklake_client
    if _ducklake_client is None:
        _ducklake_client = DuckLakeClient()
    return _ducklake_client


def _decode_arrow_ipc_rows(payload: bytes) -> List[Dict[str, Any]]:
    try:
        import pyarrow.ipc as ipc
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise Exception("pyarrow is required to decode DuckLake query responses") from exc

    try:
        reader = ipc.open_stream(payload)
        table = reader.read_all()
        return table.to_pylist()
    except Exception as exc:
        # DuckLake returns JSON error payloads on failure; surface those cleanly.
        try:
            text = payload.decode("utf-8", errors="replace").strip()
        except Exception:
            text = ""

        if text:
            # JSON error response from provider
            if text.startswith("{") and text.endswith("}"):
                try:
                    data = json.loads(text)
                    err = data.get("error") or data.get("message")
                    if err:
                        raise DuckLakeQueryError(str(err))
                except DuckLakeQueryError:
                    raise
                except Exception:
                    pass
            # Plain text error response
            if "error" in text.lower() or "failed" in text.lower():
                raise DuckLakeQueryError(text)

        raise Exception(f"Failed to decode Arrow IPC stream: {exc}") from exc
