"""
Delta Events API router using Delta Lake for blockchain event data.
"""

import sys
import os
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging
import json

# Add src path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from services.delta_service import get_delta_service, DeltaService
    DELTA_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Delta service not available: {e}")
    DELTA_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delta-events", tags=["delta-events"])

class EventResponse(BaseModel):
    event_type: str
    tx_hash: str
    timestamp: str
    entity_type: str
    chain: str
    entity_address: str
    entity_name: Optional[str]
    entity_symbol: Optional[str]
    network: str
    subnet: str
    vm_type: str
    block_number: int
    block_hash: str
    tx_index: int
    details: Dict[str, Any]

class EventsListResponse(BaseModel):
    events: List[EventResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

@router.get("/test")
async def test_delta_events():
    """Test endpoint to verify Delta events router is working."""
    return {
        "status": "ok", 
        "message": "Delta events router working", 
        "delta_available": DELTA_AVAILABLE
    }

@router.get("/", response_model=EventsListResponse)
async def get_delta_events(
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    chains: Optional[str] = Query(None, description="Comma-separated chains"),
    networks: Optional[str] = Query(None, description="Comma-separated networks"),
    entity_address: Optional[str] = Query(None, description="Filter by entity address"),
    limit: int = Query(20, ge=1, le=100, description="Number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    delta_service: DeltaService = Depends(get_delta_service) if DELTA_AVAILABLE else None
):
    """
    Get blockchain events from Delta Lake with filtering and pagination.
    """
    try:
        if not DELTA_AVAILABLE or delta_service is None:
            logger.warning("Delta service not available, returning empty results")
            return EventsListResponse(
                events=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False
            )

        # Build the query
        where_conditions = []
        params = []

        # Filter by event types
        if event_types:
            event_type_list = [et.strip() for et in event_types.split(',')]
            placeholders = ','.join(['?' for _ in event_type_list])
            where_conditions.append(f"event_type IN ({placeholders})")
            params.extend(event_type_list)

        # Filter by chains
        if chains:
            chain_list = [chain.strip().lower() for chain in chains.split(',')]
            placeholders = ','.join(['?' for _ in chain_list])
            where_conditions.append(f"LOWER(chain) IN ({placeholders})")
            params.extend(chain_list)

        # Filter by networks
        if networks:
            network_list = [net.strip() for net in networks.split(',')]
            placeholders = ','.join(['?' for _ in network_list])
            where_conditions.append(f"network IN ({placeholders})")
            params.extend(network_list)

        # Filter by entity address
        if entity_address:
            where_conditions.append("LOWER(entity_address) = LOWER(?)")
            params.append(entity_address)

        # Build WHERE clause
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Count query for total
        count_query = f"""
            SELECT COUNT(*) as total
            FROM events
            {where_clause}
        """

        # Main query with pagination
        main_query = f"""
            SELECT
                event_type,
                tx_hash,
                timestamp,
                entity_type,
                chain,
                entity_address,
                entity_name,
                entity_symbol,
                network,
                subnet,
                vm_type,
                block_number,
                block_hash,
                tx_index,
                details
            FROM events
            {where_clause}
            ORDER BY timestamp DESC, block_number DESC, tx_index DESC
            LIMIT ? OFFSET ?
        """

        # Execute count query
        count_result = await delta_service.execute_query(count_query, params)
        total = count_result[0]['total'] if count_result else 0

        # Execute main query
        main_params = params + [limit, offset]
        events_result = await delta_service.execute_query(main_query, main_params)

        # Convert results to response models
        events = []
        for row in events_result:
            # Parse details JSON
            details = {}
            if row.get('details'):
                try:
                    details = json.loads(row['details']) if isinstance(row['details'], str) else row['details']
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse details JSON for event {row.get('tx_hash')}")
                    details = {}

            event_data = {
                "event_type": row.get("event_type", ""),
                "tx_hash": row.get("tx_hash", ""),
                "timestamp": str(row.get("timestamp", "")),
                "entity_type": row.get("entity_type", ""),
                "chain": row.get("chain", ""),
                "entity_address": row.get("entity_address", ""),
                "entity_name": row.get("entity_name"),
                "entity_symbol": row.get("entity_symbol"),
                "network": row.get("network", ""),
                "subnet": row.get("subnet", ""),
                "vm_type": row.get("vm_type", ""),
                "block_number": int(row.get("block_number", 0)),
                "block_hash": row.get("block_hash", ""),
                "tx_index": int(row.get("tx_index", 0)),
                "details": details
            }
            events.append(EventResponse(**event_data))

        has_more = offset + limit < total

        logger.info(f"Retrieved {len(events)} events (total: {total})")

        return EventsListResponse(
            events=events,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more
        )

    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        # Return empty results on error to avoid breaking the UI
        return EventsListResponse(
            events=[],
            total=0,
            limit=limit,
            offset=offset,
            has_more=False
        )

@router.get("/wallet/{wallet_address}")
async def get_wallet_events(
    wallet_address: str,
    chain: Optional[str] = Query(None, description="Filter by chain"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    limit: int = Query(20, ge=1, le=100, description="Number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    delta_service: DeltaService = Depends(get_delta_service) if DELTA_AVAILABLE else None
):
    """Get all events for a specific wallet address."""
    try:
        if not DELTA_AVAILABLE or delta_service is None:
            return {
                "wallet_address": wallet_address,
                "chain": chain,
                "events": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False
            }

        # Parse event types if provided
        event_type_list = None
        if event_types:
            event_type_list = [et.strip() for et in event_types.split(',')]

        # Get events for wallet
        events_result = await delta_service.get_events_for_wallet(
            wallet_address=wallet_address,
            chain=chain,
            event_types=event_type_list,
            limit=limit,
            offset=offset
        )

        # Convert to response format
        events = []
        for row in events_result:
            # Parse details JSON
            details = {}
            if row.get('details'):
                try:
                    details = json.loads(row['details']) if isinstance(row['details'], str) else row['details']
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse details JSON for event {row.get('tx_hash')}")
                    details = {}

            event_data = {
                "event_type": row.get("event_type", ""),
                "tx_hash": row.get("tx_hash", ""),
                "timestamp": str(row.get("timestamp", "")),
                "entity_type": row.get("entity_type", ""),
                "chain": row.get("chain", ""),
                "entity_address": row.get("entity_address", ""),
                "entity_name": row.get("entity_name"),
                "entity_symbol": row.get("entity_symbol"),
                "network": row.get("network", ""),
                "subnet": row.get("subnet", ""),
                "vm_type": row.get("vm_type", ""),
                "block_number": int(row.get("block_number", 0)),
                "block_hash": row.get("block_hash", ""),
                "tx_index": int(row.get("tx_index", 0)),
                "details": details
            }
            events.append(EventResponse(**event_data))

        # For now, use the returned count as total (could be optimized with separate count query)
        total = len(events)
        has_more = len(events) == limit  # Simple heuristic

        return {
            "wallet_address": wallet_address,
            "chain": chain,
            "events": events,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more
        }

    except Exception as e:
        logger.error(f"Error fetching wallet events: {str(e)}")
        return {
            "wallet_address": wallet_address,
            "chain": chain,
            "events": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False
        }

@router.get("/stats")
async def get_event_stats(
    chain: Optional[str] = Query(None, description="Filter by chain"),
    delta_service: DeltaService = Depends(get_delta_service) if DELTA_AVAILABLE else None
):
    """Get event statistics with optional filtering."""
    try:
        if not DELTA_AVAILABLE or delta_service is None:
            return {
                "total_events": 0,
                "by_event_type": [],
                "by_chain": [],
                "by_network": [],
                "date_range": {},
            }

        # Get table info which includes various statistics
        table_info = await delta_service.get_table_info()
        
        return {
            "total_events": table_info.get('count', [{'total_events': 0}])[0].get('total_events', 0),
            "by_event_type": table_info.get('event_types', []),
            "by_chain": table_info.get('chains', []),
            "date_range": table_info.get('date_range', [{}])[0] if table_info.get('date_range') else {},
            "schema": table_info.get('schema', [])
        }

    except Exception as e:
        logger.error(f"Error fetching event stats: {str(e)}")
        return {
            "total_events": 0,
            "by_event_type": [],
            "by_chain": [],
            "by_network": [],
            "date_range": {},
        }
