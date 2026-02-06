"""
Alert Cache Manager - Syncs AlertInstance data to Redis for Alert Scheduler Provider

This service manages the Redis cache that the Alert Scheduler Provider and blockchain
actors use to query alerts. It syncs AlertInstance data from PostgreSQL to Redis using
post_save/post_delete signals.

Redis Structure:
    alert:{id}                                  - Hash with all alert fields (TTL: 7 days)
    alerts:active                               - Set of enabled alert IDs
    alerts:address:{CHAIN}:{network}:{addr}     - JSON array string of alert IDs monitoring this address
                                                  (JSON string for wasi:keyvalue compatibility)
                                                  Example: alerts:address:ETH:mainnet:0x742d35cc...
    alerts:contract:{CHAIN}:{network}:{contract} - JSON array string of alert IDs monitoring this contract
                                                  (JSON string for wasi:keyvalue compatibility)
                                                  Example: alerts:contract:ETH:mainnet:0xdac17f958d2ee...
    alerts:chain:{chain}:{event}                - Set of alert IDs for chain+event combination
    periodic_schedule                           - SortedSet {alert_id: next_run_timestamp}
    onetime_schedule                            - SortedSet {alert_id: scheduled_timestamp}

IMPORTANT: The same wallet address can exist on multiple networks (e.g., 0x123... on Ethereum,
Polygon, Arbitrum). All address and contract keys MUST include chain and network to prevent
collisions and false positives.

NOTE: alerts:address:* and alerts:contract:* use JSON strings instead of Redis SETs
to ensure compatibility with the wasi:keyvalue/store interface used by wasmCloud actors.

Performance Optimizations:
- Uses Redis pipelining for batch operations
- Batch cache warming processes alerts in chunks of 500
- SCAN used instead of KEYS for non-blocking iteration
- TTLs on all keys to prevent memory leaks
"""

from typing import Dict, List, Set, Optional, Any
from datetime import datetime
import json
import redis
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

# TTL constants
ALERT_HASH_TTL = 7 * 24 * 3600  # 7 days for alert:{id} hashes
INDEX_KEY_TTL = 24 * 3600  # 24 hours for address/contract indexes (refreshed on sync)
BATCH_SIZE = 500  # Number of alerts to process in each batch


_TARGET_KEY_PREFIX_BY_CHAIN_NAME: dict[str, str] = {
    "ethereum": "ETH",
    "eth": "ETH",
    "polygon": "MATIC",
    "matic": "MATIC",
    "arbitrum": "ARB",
    "optimism": "OP",
    "avalanche": "AVAX",
    "avax": "AVAX",
    "base": "BASE",
    "bsc": "BNB",
    "binance": "BNB",
    "bnb": "BNB",
    "solana": "SOL",
    "sol": "SOL",
    "bitcoin": "BTC",
    "btc": "BTC",
}


def _normalize_chain_prefix(raw: Any) -> str:
    """
    Normalize a chain identifier to the canonical key prefix used in Redis indexes.

    Examples:
      - "ethereum" -> "ETH"
      - "ETH" -> "ETH"
      - "polygon" -> "MATIC"
    """
    value = str(raw or "").strip()
    if not value:
        return "ETH"
    mapped = _TARGET_KEY_PREFIX_BY_CHAIN_NAME.get(value.lower())
    return mapped or value.upper()


class AlertCacheManager:
    """Manages Redis cache for AlertInstance data with optimized batch operations"""

    def __init__(self):
        """Initialize Redis connection"""
        cache_location = settings.CACHES.get("default", {}).get("LOCATION")
        redis_url = (
            cache_location
            if isinstance(cache_location, str)
            and cache_location.startswith(("redis://", "rediss://", "unix://"))
            else getattr(settings, "REDIS_URL", cache_location)
        )
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    def sync_alert_to_redis(self, alert_instance) -> None:
        """
        Sync AlertInstance to Redis cache for Alert Scheduler Provider.

        Uses pipelined operations to minimize Redis round-trips.

        Creates/updates:
        - alert:{id} hash with all fields
        - alerts:active set if enabled
        - alerts:address:{CHAIN}:{network}:{addr} indexes for each address
        - alerts:contract:{CHAIN}:{network}:{contract} indexes for each contract
        - alerts:chain:{chain}:{event} sets for indexing
        - periodic_schedule or onetime_schedule sorted sets
        """
        alert_id = str(alert_instance.id)

        try:
            # Only cache alerts with execution-safe AlertTemplateIR v1 spec.
            execution_spec = self._get_execution_spec(alert_instance)
            if not isinstance(execution_spec, dict) or execution_spec.get("version") != "v1":
                logger.warning(
                    "Skipping Redis cache sync for alert %s: unsupported spec version",
                    alert_id,
                )
                return

            expanded_targets = self._get_expanded_targets(alert_instance)

            # Collect all index keys that need updating
            index_keys = self._collect_index_keys(
                alert_instance=alert_instance,
                expanded_targets=expanded_targets,
                fallback_spec=alert_instance.spec,
            )

            # Phase 1: Batch GET all current index values
            if index_keys:
                with self.redis_client.pipeline() as pipe:
                    for key in index_keys:
                        pipe.get(key)
                    current_values = pipe.execute()
                current_index_state = dict(zip(index_keys, current_values))
            else:
                current_index_state = {}

            # Compute new index values
            new_index_values = {}
            for key, current in current_index_state.items():
                alert_ids = self._parse_json_index(current)
                if alert_id not in alert_ids:
                    alert_ids.append(alert_id)
                    new_index_values[key] = json.dumps(alert_ids)

            # Phase 2: Single pipeline for all SET operations
            with self.redis_client.pipeline() as pipe:
                # 1. Create alert:{id} hash with TTL
                alert_data = self._serialize_alert_for_redis(
                    alert_instance=alert_instance,
                    execution_spec=execution_spec,
                    expanded_targets=expanded_targets,
                )
                pipe.hset(f"alert:{alert_id}", mapping=alert_data)
                pipe.expire(f"alert:{alert_id}", ALERT_HASH_TTL)

                # 2. Add to active alerts set if enabled
                if alert_instance.enabled:
                    pipe.sadd("alerts:active", alert_id)
                else:
                    pipe.srem("alerts:active", alert_id)

                # 3. Update all JSON indexes with TTL
                for key, value in new_index_values.items():
                    pipe.set(key, value)
                    pipe.expire(key, INDEX_KEY_TTL)

                # 4. Index by chain + event_type combinations
                chain_events = self._extract_chain_events(alert_instance)
                for chain, event_type in chain_events:
                    pipe.sadd(f"alerts:chain:{chain}:{event_type}", alert_id)

                # 5. Add to schedule sorted sets based on trigger_type
                if alert_instance.trigger_type == 'periodic':
                    next_run = self._calculate_next_run(alert_instance)
                    if next_run:
                        pipe.zadd("periodic_schedule", {alert_id: next_run.timestamp()})
                elif alert_instance.trigger_type == 'one_time':
                    scheduled_time = self._get_scheduled_time(alert_instance)
                    if scheduled_time:
                        pipe.zadd("onetime_schedule", {alert_id: scheduled_time.timestamp()})

                # Execute pipeline
                pipe.execute()

            logger.info(f"Synced alert {alert_id} to Redis cache")

        except Exception as e:
            logger.error(f"Failed to sync alert {alert_id} to Redis: {e}")
            raise

    def _collect_index_keys(
        self,
        alert_instance,
        expanded_targets: List[str],
        fallback_spec: Dict[str, Any],
    ) -> List[str]:
        """
        Collect all index keys that need to be updated for an alert.

        Returns list of keys for batch GET/SET operations.
        """
        keys: List[str] = []

        alert_type = str(getattr(alert_instance, "alert_type", "wallet") or "wallet")

        if expanded_targets:
            for target in expanded_targets:
                if not isinstance(target, str):
                    continue
                parts = [p.strip() for p in target.split(":")]
                if len(parts) < 3:
                    continue
                chain, network, address = (
                    _normalize_chain_prefix(parts[0]),
                    parts[1].lower(),
                    parts[2],
                )
                address = address.lower()

                if alert_type == "wallet":
                    keys.append(f"alerts:address:{chain}:{network}:{address}")
                elif alert_type in {"token", "contract", "nft"}:
                    keys.append(f"alerts:contract:{chain}:{network}:{address}")

            # Deduplicate
            return sorted(set(keys))
        return []

    def _parse_json_index(self, value: Optional[str]) -> List[str]:
        """
        Parse a JSON array index value, handling edge cases.

        Returns list of alert IDs.
        """
        if not value:
            return []
        try:
            alert_ids = json.loads(value)
            if not isinstance(alert_ids, list):
                return [alert_ids] if alert_ids else []
            return alert_ids
        except json.JSONDecodeError:
            return []

    def remove_alert_from_redis(self, alert_id: str) -> None:
        """
        Remove AlertInstance from all Redis structures.

        Removes from:
        - alert:{id} hash
        - alerts:active set
        - All alerts:address:{CHAIN}:{network}:* indexes
        - All alerts:contract:{CHAIN}:{network}:* indexes
        - All alerts:chain:*:* sets
        - Schedule sorted sets
        """
        try:
            # Get alert data before deletion to know which sets to clean
            alert_data = self.redis_client.hgetall(f"alert:{alert_id}")

            if alert_data:
                spec = json.loads(alert_data.get('spec', '{}'))
                alert_type = str(alert_data.get("alert_type") or "wallet")
                chains_for_chain_events: List[str] = []

                expanded_targets: List[str] = []
                raw_targets = alert_data.get("target_keys") or ""
                if raw_targets:
                    try:
                        parsed = json.loads(raw_targets)
                        if isinstance(parsed, list):
                            expanded_targets = [t for t in parsed if isinstance(t, str)]
                    except json.JSONDecodeError:
                        expanded_targets = []

                # Collect all index keys to clean
                index_keys: List[str] = []
                if expanded_targets:
                    for target in expanded_targets:
                        parts = [p.strip() for p in target.split(":")]
                        if len(parts) < 3:
                            continue
                        chain, network, address = (
                            _normalize_chain_prefix(parts[0]),
                            parts[1].lower(),
                            parts[2].lower(),
                        )
                        chains_for_chain_events.append(f"{chain}:{network}")
                        if alert_type == "wallet":
                            index_keys.append(f"alerts:address:{chain}:{network}:{address}")
                        else:
                            index_keys.append(f"alerts:contract:{chain}:{network}:{address}")
                else:
                    trigger = spec.get("trigger", {}) if isinstance(spec, dict) else {}
                    chain_id = trigger.get("chain_id") if isinstance(trigger, dict) else None
                    if isinstance(chain_id, int):
                        chain_prefix_by_id = {
                            1: "ETH",
                            10: "OP",
                            56: "BNB",
                            137: "MATIC",
                            42161: "ARB",
                            43114: "AVAX",
                            8453: "BASE",
                        }
                        chain = chain_prefix_by_id.get(chain_id, "ETH")
                        chains_for_chain_events.append(f"{chain}:mainnet")

                # Batch remove from indexes
                if index_keys:
                    self._batch_remove_from_indexes(index_keys, alert_id)

                # Get chain:event keys to clean
                chain_event_keys = []
                if alert_data.get('trigger_type') == 'event_driven':
                    trigger_config = json.loads(alert_data.get('trigger_config', '{}'))
                    event_types = trigger_config.get('event_types', [])
                    for chain in sorted(set(chains_for_chain_events)):
                        for event_type in event_types:
                            chain_event_keys.append(f"alerts:chain:{chain}:{event_type}")

            with self.redis_client.pipeline() as pipe:
                # Delete alert hash
                pipe.delete(f"alert:{alert_id}")

                # Remove from active set
                pipe.srem("alerts:active", alert_id)

                # Remove from schedule sets
                pipe.zrem("periodic_schedule", alert_id)
                pipe.zrem("onetime_schedule", alert_id)

                # Remove from chain:event sets
                if alert_data:
                    for key in chain_event_keys:
                        pipe.srem(key, alert_id)

                pipe.execute()

            logger.info(f"Removed alert {alert_id} from Redis cache")

        except Exception as e:
            logger.error(f"Failed to remove alert {alert_id} from Redis: {e}")
            raise

    def _get_execution_spec(self, alert_instance) -> Dict[str, Any]:
        """
        Get the execution-time template spec for an alert instance.

        Preference order:
        - Template-based alerts: AlertTemplate.spec (AlertTemplateIR v1)
        - Standalone alerts: _standalone_spec (must already be v1 to be cached)
        - Fallback: computed instance spec
        """
        template = getattr(alert_instance, "template", None)
        template_spec = getattr(template, "spec", None) if template is not None else None
        if isinstance(template_spec, dict) and template_spec:
            return template_spec

        standalone = getattr(alert_instance, "_standalone_spec", None)
        if isinstance(standalone, dict) and standalone:
            return standalone

        computed = getattr(alert_instance, "spec", None)
        if isinstance(computed, dict):
            return computed

        return {}

    def _get_expanded_targets(self, alert_instance) -> List[str]:
        targets: Any = []
        if hasattr(alert_instance, "get_effective_targets"):
            try:
                targets = alert_instance.get_effective_targets()
            except Exception:
                targets = []
        elif hasattr(alert_instance, "target_keys"):
            targets = getattr(alert_instance, "target_keys", [])

        if not isinstance(targets, list):
            return []
        return [t for t in targets if isinstance(t, str) and t.strip()]

    def _batch_remove_from_indexes(self, keys: List[str], alert_id: str) -> None:
        """
        Remove alert_id from multiple JSON array indexes in a batched manner.

        Uses pipeline for efficient GET/SET operations.
        """
        if not keys:
            return

        # Batch GET all current values
        with self.redis_client.pipeline() as pipe:
            for key in keys:
                pipe.get(key)
            current_values = pipe.execute()

        # Compute updates
        updates = {}  # key -> new_value or None (to delete)
        for key, current in zip(keys, current_values):
            alert_ids = self._parse_json_index(current)
            if alert_id in alert_ids:
                alert_ids.remove(alert_id)
                if alert_ids:
                    updates[key] = json.dumps(alert_ids)
                else:
                    updates[key] = None  # Mark for deletion

        # Batch SET/DELETE
        if updates:
            with self.redis_client.pipeline() as pipe:
                for key, value in updates.items():
                    if value is None:
                        pipe.delete(key)
                    else:
                        pipe.set(key, value)
                        pipe.expire(key, INDEX_KEY_TTL)
                pipe.execute()

    def warm_cache(self) -> Dict[str, int]:
        """
        Warm Redis cache with all enabled AlertInstances from database.

        Uses batch operations for efficiency - processes alerts in chunks.

        Returns:
            Dict with counts: {"synced": N, "failed": M}
        """
        from app.models.alerts import AlertInstance

        stats = {"synced": 0, "failed": 0}

        # Get all enabled alerts
        alerts = list(
            AlertInstance.objects.filter(enabled=True).select_related('template')
        )

        total_alerts = len(alerts)
        logger.info(f"Warming alert cache with {total_alerts} enabled alerts")

        # Process in batches
        for i in range(0, total_alerts, BATCH_SIZE):
            batch = alerts[i:i + BATCH_SIZE]
            batch_stats = self._sync_batch_to_redis(batch)
            stats["synced"] += batch_stats["synced"]
            stats["failed"] += batch_stats["failed"]

            if (i + BATCH_SIZE) % 1000 == 0:
                logger.info(f"Processed {min(i + BATCH_SIZE, total_alerts)}/{total_alerts} alerts")

        logger.info(f"Cache warming complete: {stats}")
        return stats

    def _sync_batch_to_redis(self, alerts: List) -> Dict[str, int]:
        """
        Sync a batch of AlertInstances to Redis efficiently.

        Batches all GET operations, computes updates, then batches all SET operations.

        Returns:
            Dict with counts: {"synced": N, "failed": M}
        """
        stats = {"synced": 0, "failed": 0}

        if not alerts:
            return stats

        try:
            # Step 1: Collect all index keys across all alerts
            all_index_keys: Set[str] = set()
            alert_data_map: Dict[str, Dict[str, Any]] = {}  # alert_id -> {keys, data, instance}

            for alert in alerts:
                alert_id = str(alert.id)
                try:
                    execution_spec = self._get_execution_spec(alert)
                    if not isinstance(execution_spec, dict) or execution_spec.get("version") != "v1":
                        logger.warning(
                            "Skipping Redis cache sync for alert %s: unsupported spec version",
                            alert_id,
                        )
                        stats["failed"] += 1
                        continue

                    expanded_targets = self._get_expanded_targets(alert)
                    keys = self._collect_index_keys(
                        alert_instance=alert,
                        expanded_targets=expanded_targets,
                        fallback_spec=alert.spec,
                    )
                    all_index_keys.update(keys)

                    alert_data_map[alert_id] = {
                        'keys': keys,
                        'data': self._serialize_alert_for_redis(
                            alert_instance=alert,
                            execution_spec=execution_spec,
                            expanded_targets=expanded_targets,
                        ),
                        'instance': alert,
                    }
                except Exception as e:
                    logger.error(f"Failed to prepare alert {alert.id}: {e}")
                    stats["failed"] += 1

            # Step 2: Batch GET all current index values
            index_keys_list = list(all_index_keys)
            if index_keys_list:
                with self.redis_client.pipeline() as pipe:
                    for key in index_keys_list:
                        pipe.get(key)
                    current_values = pipe.execute()
                current_index_state = dict(zip(index_keys_list, current_values))
            else:
                current_index_state = {}

            # Step 3: Compute new index values (accumulate all alert_ids per key)
            index_updates: Dict[str, List[str]] = {}  # key -> list of alert_ids

            # Initialize with current values
            for key, value in current_index_state.items():
                index_updates[key] = self._parse_json_index(value)

            # Add all alert_ids to their respective indexes
            for alert_id, info in alert_data_map.items():
                for key in info['keys']:
                    if key not in index_updates:
                        index_updates[key] = []
                    if alert_id not in index_updates[key]:
                        index_updates[key].append(alert_id)

            # Step 4: Single pipeline for all SET operations
            with self.redis_client.pipeline() as pipe:
                for alert_id, info in alert_data_map.items():
                    instance = info['instance']

                    # Create alert:{id} hash with TTL
                    pipe.hset(f"alert:{alert_id}", mapping=info['data'])
                    pipe.expire(f"alert:{alert_id}", ALERT_HASH_TTL)

                    # Add to active alerts set if enabled
                    if instance.enabled:
                        pipe.sadd("alerts:active", alert_id)
                    else:
                        pipe.srem("alerts:active", alert_id)

                    # Index by chain + event_type combinations
                    chain_events = self._extract_chain_events(instance)
                    for chain, event_type in chain_events:
                        pipe.sadd(f"alerts:chain:{chain}:{event_type}", alert_id)

                    # Add to schedule sorted sets based on trigger_type
                    if instance.trigger_type == 'periodic':
                        next_run = self._calculate_next_run(instance)
                        if next_run:
                            pipe.zadd("periodic_schedule", {alert_id: next_run.timestamp()})
                    elif instance.trigger_type == 'one_time':
                        scheduled_time = self._get_scheduled_time(instance)
                        if scheduled_time:
                            pipe.zadd("onetime_schedule", {alert_id: scheduled_time.timestamp()})

                # Write all index updates
                for key, alert_ids in index_updates.items():
                    if alert_ids:
                        pipe.set(key, json.dumps(alert_ids))
                        pipe.expire(key, INDEX_KEY_TTL)

                pipe.execute()

            stats["synced"] = len(alert_data_map)

        except Exception as e:
            logger.error(f"Batch sync failed: {e}")
            stats["failed"] = len(alerts)

        return stats

    def _serialize_alert_for_redis(
        self,
        alert_instance,
        execution_spec: Dict[str, Any],
        expanded_targets: List[str],
    ) -> Dict[str, str]:
        """
        Convert AlertInstance to Redis hash fields.

        Returns hash mapping for HSET command.
        """
        template_id = getattr(alert_instance, "template_id", None)
        return {
            "trigger_type": alert_instance.trigger_type,
            "trigger_config": json.dumps(alert_instance.trigger_config or {}),
            "spec": json.dumps(execution_spec),
            "template_id": str(template_id) if template_id else "",
            "template_params": json.dumps(getattr(alert_instance, "template_params", None) or {}),
            "alert_type": str(getattr(alert_instance, "alert_type", "wallet") or "wallet"),
            "target_keys": json.dumps(expanded_targets),
            "user_id": str(alert_instance.user_id),
            "enabled": "1" if alert_instance.enabled else "0",
            "version": str(alert_instance.version),
            "created_at": alert_instance.created_at.isoformat(),
            "last_job_created_at": (
                alert_instance.last_job_created_at.isoformat()
                if alert_instance.last_job_created_at else ""
            ),
            "job_creation_count": str(alert_instance.job_creation_count),
            "name": alert_instance.name or "",
        }

    def _extract_chain_events(self, alert_instance) -> List[tuple]:
        """
        Extract chain + event_type combinations for indexing.

        Returns list of (chain, event_type) tuples.
        """
        chain_events = []

        # Get event types from trigger_config (for event_driven)
        if alert_instance.trigger_type == 'event_driven':
            trigger_config = alert_instance.trigger_config or {}
            event_types = trigger_config.get('event_types', [])

            chains: List[str] = []
            if hasattr(alert_instance, "get_chains"):
                try:
                    chains = [
                        str(c).replace("-", ":")
                        for c in (alert_instance.get_chains() or [])
                        if isinstance(c, str)
                    ]
                except Exception:
                    chains = []

            if not chains:
                for raw in getattr(alert_instance, "target_keys", []) or []:
                    if not isinstance(raw, str):
                        continue
                    parts = [p.strip() for p in raw.split(":")]
                    if len(parts) < 2:
                        continue
                    chains.append(f"{_normalize_chain_prefix(parts[0])}:{parts[1].lower()}")

            for chain in sorted(set(chains)):
                for event_type in event_types:
                    chain_events.append((chain, event_type))

        return chain_events

    def _calculate_next_run(self, alert_instance) -> Optional[datetime]:
        """
        Calculate next run time for periodic alert from trigger_config.

        Uses cron expression if available, otherwise interval_seconds.
        """
        trigger_config = alert_instance.trigger_config or {}

        # For now, return None - let Rust provider calculate this
        # Alternatively, could use croniter library to calculate next run
        return None

    def _get_scheduled_time(self, alert_instance) -> Optional[datetime]:
        """Get scheduled time for one-time alert from trigger_config"""
        trigger_config = alert_instance.trigger_config or {}

        # For now, return None - would need to parse from trigger_config
        # if there's a specific scheduled_time field
        return None

    def migrate_sets_to_json(self) -> Dict[str, int]:
        """
        Migrate existing Redis SET-based indexes to JSON arrays.

        This is needed for backwards compatibility with existing data that
        was stored using SADD before the keyvalue compatibility change.

        Uses SCAN instead of KEYS to avoid blocking Redis.

        Returns:
            Dict with counts: {"migrated": N, "failed": M, "skipped": S}
        """
        stats = {"migrated": 0, "failed": 0, "skipped": 0}

        # Find all address and contract index keys using SCAN (non-blocking)
        for pattern in ["alerts:address:*", "alerts:contract:*"]:
            cursor = 0
            while True:
                cursor, keys = self.redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100  # Process 100 keys per iteration
                )

                for key in keys:
                    try:
                        key_type = self.redis_client.type(key)

                        if key_type == "set":
                            # Get all members from SET
                            members = list(self.redis_client.smembers(key))
                            # Delete SET
                            self.redis_client.delete(key)
                            # Write as JSON array with TTL
                            if members:
                                self.redis_client.set(key, json.dumps(members))
                                self.redis_client.expire(key, INDEX_KEY_TTL)
                            stats["migrated"] += 1
                            logger.info(f"Migrated {key} from SET to JSON ({len(members)} items)")

                        elif key_type == "string":
                            # Already a string, verify it's valid JSON
                            try:
                                current = self.redis_client.get(key)
                                json.loads(current)
                                stats["skipped"] += 1
                            except json.JSONDecodeError:
                                # Invalid JSON string, delete it
                                self.redis_client.delete(key)
                                stats["failed"] += 1
                                logger.warning(f"Deleted invalid JSON at {key}")
                        else:
                            stats["skipped"] += 1

                    except Exception as e:
                        stats["failed"] += 1
                        logger.error(f"Failed to migrate {key}: {e}")

                # Exit when scan is complete
                if cursor == 0:
                    break

        logger.info(f"Migration complete: {stats}")
        return stats

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current alert cache state.

        Returns:
            Dict with cache statistics
        """
        stats = {}

        # Count active alerts
        stats["active_alerts"] = self.redis_client.scard("alerts:active")

        # Count scheduled alerts
        stats["periodic_scheduled"] = self.redis_client.zcard("periodic_schedule")
        stats["onetime_scheduled"] = self.redis_client.zcard("onetime_schedule")

        # Count index keys using SCAN
        address_count = 0
        contract_count = 0

        cursor = 0
        while True:
            cursor, keys = self.redis_client.scan(
                cursor=cursor, match="alerts:address:*", count=100
            )
            address_count += len(keys)
            if cursor == 0:
                break

        cursor = 0
        while True:
            cursor, keys = self.redis_client.scan(
                cursor=cursor, match="alerts:contract:*", count=100
            )
            contract_count += len(keys)
            if cursor == 0:
                break

        stats["address_indexes"] = address_count
        stats["contract_indexes"] = contract_count

        return stats
