"""
Service for syncing BlockchainNode configurations to Redis.

Handles the sync between Django BlockchainNode model and Redis keys
used by wasmCloud providers for configuration lookup.

Redis Key Pattern:
- provider:config:newheads-{vm_type}:{chain_id}

Examples:
- provider:config:newheads-evm:1 (Ethereum Mainnet)
- provider:config:newheads-evm:137 (Polygon)
- provider:config:newheads-svm:mainnet-beta (Solana)
"""

import json
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class BlockchainSyncService:
    """
    Service for syncing BlockchainNode configurations to Redis.

    This service manages the Redis keys that wasmCloud providers use
    to load their configuration. Each BlockchainNode maps to a single
    provider config in Redis.
    """

    _redis_client = None

    @classmethod
    def get_redis_client(cls):
        """
        Get or create Redis client connection.

        Uses Django settings REDIS_URL or falls back to localhost.
        """
        if cls._redis_client is None:
            import redis
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379')
            cls._redis_client = redis.from_url(redis_url, decode_responses=True)
        return cls._redis_client

    @classmethod
    def reset_client(cls):
        """Reset the Redis client. Useful for testing."""
        cls._redis_client = None

    @classmethod
    def get_provider_config_key(cls, vm_type: str, chain_id: str) -> str:
        """
        Generate Redis key for provider config.

        Args:
            vm_type: The VM type (EVM, SVM, UTXO, COSMOS)
            chain_id: The chain identifier

        Returns:
            Redis key in format: provider:config:newheads-{vm_type}:{chain_id}
        """
        vm_type_lower = vm_type.lower()
        return f"provider:config:newheads-{vm_type_lower}:{chain_id}"

    @classmethod
    def sync_node_to_redis(cls, node) -> bool:
        """
        Sync a BlockchainNode instance to Redis.

        Args:
            node: BlockchainNode instance

        Returns:
            True if sync was successful, False otherwise
        """
        try:
            client = cls.get_redis_client()
            key = cls.get_provider_config_key(node.vm_type, node.chain_id)

            config = node.get_provider_config()
            client.set(key, json.dumps(config))

            logger.info(
                f"Synced BlockchainNode {node.chain_id} ({node.chain_name}) "
                f"to Redis key: {key}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to sync BlockchainNode {node.chain_id} to Redis: {e}"
            )
            return False

    @classmethod
    def remove_node_from_redis(cls, vm_type: str, chain_id: str) -> bool:
        """
        Remove provider config from Redis.

        Args:
            vm_type: The VM type
            chain_id: The chain identifier

        Returns:
            True if removal was successful, False otherwise
        """
        try:
            client = cls.get_redis_client()
            key = cls.get_provider_config_key(vm_type, chain_id)
            client.delete(key)

            logger.info(f"Removed provider config from Redis: {key}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to remove provider config {vm_type}:{chain_id} from Redis: {e}"
            )
            return False

    @classmethod
    def get_node_config_from_redis(cls, vm_type: str, chain_id: str) -> Optional[dict]:
        """
        Get provider config from Redis.

        Args:
            vm_type: The VM type
            chain_id: The chain identifier

        Returns:
            Config dict if found, None otherwise
        """
        try:
            client = cls.get_redis_client()
            key = cls.get_provider_config_key(vm_type, chain_id)
            data = client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(
                f"Failed to get provider config {vm_type}:{chain_id} from Redis: {e}"
            )
            return None

    @classmethod
    def sync_all_nodes(cls) -> dict:
        """
        Sync all enabled BlockchainNodes to Redis.

        Returns:
            Dict with counts: {"synced": n, "failed": n, "skipped": n}
        """
        from app.models.blockchain import BlockchainNode

        results = {"synced": 0, "failed": 0, "skipped": 0}

        # Sync enabled nodes
        for node in BlockchainNode.objects.filter(enabled=True):
            if cls.sync_node_to_redis(node):
                results["synced"] += 1
            else:
                results["failed"] += 1

        # Count disabled nodes
        results["skipped"] = BlockchainNode.objects.filter(enabled=False).count()

        logger.info(
            f"Sync all nodes complete: {results['synced']} synced, "
            f"{results['failed']} failed, {results['skipped']} skipped"
        )

        return results

    @classmethod
    def list_all_provider_configs(cls) -> list:
        """
        List all provider config keys in Redis.

        Returns:
            List of Redis keys matching provider:config:newheads-*
        """
        try:
            client = cls.get_redis_client()
            keys = client.keys("provider:config:newheads-*")
            return sorted(keys)

        except Exception as e:
            logger.error(f"Failed to list provider configs from Redis: {e}")
            return []
