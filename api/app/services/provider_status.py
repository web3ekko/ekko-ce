"""Service for reading provider status from Redis.

Reads provider status data written by wasmCloud providers (newheads-evm, etc.)
for display in the dashboard network status view.

Redis Structure (written by provider-status-common):
    provider:registry                   - Hash: provider_id -> provider_type
    provider:status:{provider_id}       - JSON: ProviderStatus
    provider:subscription:{id}:{chain}  - JSON: SubscriptionStatus
    provider:errors:{provider_id}       - List: ErrorRecord JSON
"""
import json
import logging
from typing import Optional, List, Tuple

from django.conf import settings
import redis

logger = logging.getLogger(__name__)


class ProviderStatusService:
    """Reads provider status data from Redis.

    This service reads status data written by wasmCloud blockchain providers
    using the provider-status-common shared library.
    """

    KEY_REGISTRY = "provider:registry"
    KEY_PREFIX_STATUS = "provider:status"

    def __init__(self):
        """Initialize Redis connection using Django cache settings."""
        self.redis_client = redis.from_url(
            settings.CACHES['default']['LOCATION'],
            decode_responses=True
        )

    def list_providers(self) -> List[Tuple[str, str]]:
        """Get all registered providers from registry.

        Returns:
            List of (provider_id, provider_type) tuples
        """
        try:
            registry = self.redis_client.hgetall(self.KEY_REGISTRY)
            return list(registry.items())
        except Exception as e:
            logger.warning(f"Failed to list providers from Redis: {e}")
            return []

    def get_provider_status(self, provider_id: str) -> Optional[dict]:
        """Get status for a specific provider.

        Args:
            provider_id: The provider instance ID

        Returns:
            ProviderStatus dict or None if not found
        """
        try:
            key = f"{self.KEY_PREFIX_STATUS}:{provider_id}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Failed to get provider status for {provider_id}: {e}")
            return None

    def get_all_provider_statuses(self) -> List[dict]:
        """Get status for all registered providers.

        Returns:
            List of ProviderStatus dicts
        """
        providers = self.list_providers()
        statuses = []
        for provider_id, provider_type in providers:
            status = self.get_provider_status(provider_id)
            if status:
                statuses.append(status)
        return statuses
