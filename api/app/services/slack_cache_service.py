"""
Slack notification cache service for syncing to Redis.

Ensures Slack channel configurations are available to wasmCloud providers.
"""

import json
import logging
from typing import Optional, Dict, Any
from django.core.cache import cache
from app.models.notifications import NotificationChannelEndpoint

logger = logging.getLogger(__name__)


class SlackCacheService:
    """Service for managing Slack notification channel cache in Redis."""

    # Cache TTL: 24 hours (Slack configs don't change frequently)
    CACHE_TTL = 86400

    def __init__(self):
        self.cache = cache

    def sync_slack_config_to_redis(self, user_id: str) -> bool:
        """
        Sync user's Slack configuration to Redis for wasmCloud provider access.

        Args:
            user_id: User UUID string

        Returns:
            True if synced successfully, False otherwise
        """
        try:
            # Query all enabled Slack endpoints for the user
            slack_endpoints = NotificationChannelEndpoint.objects.filter(
                owner_type='user',
                owner_id=user_id,
                channel_type='slack',
                enabled=True,
                verified=True
            )

            if not slack_endpoints.exists():
                # No Slack channels configured - clear cache
                self._clear_slack_cache(user_id)
                logger.debug(f"No Slack channels configured for user {user_id}")
                return True

            # Use the first enabled Slack channel (future: support multiple)
            slack_endpoint = slack_endpoints.first()

            # Build cache data matching wasmCloud provider's SlackChannelConfig struct
            slack_config = {
                'user_id': user_id,
                'webhook_url': slack_endpoint.config.get('webhook_url'),
                'channel_name': slack_endpoint.config.get('channel', '#alerts'),
                'workspace_name': slack_endpoint.config.get('workspace_name', 'Ekko Workspace'),
                'enabled': True
            }

            # Cache in Redis with key format: slack:config:{user_id}
            cache_key = f"slack:config:{user_id}"
            self.cache.set(
                cache_key,
                json.dumps(slack_config),
                timeout=self.CACHE_TTL
            )

            logger.info(f"Synced Slack config to Redis for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to sync Slack config for user {user_id}: {e}")
            return False

    def _clear_slack_cache(self, user_id: str):
        """Clear Slack configuration cache for a user."""
        cache_key = f"slack:config:{user_id}"
        self.cache.delete(cache_key)
        logger.debug(f"Cleared Slack cache for user {user_id}")

    def get_slack_config(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get Slack configuration from cache.

        Args:
            user_id: User UUID string

        Returns:
            Slack config dict or None if not found
        """
        cache_key = f"slack:config:{user_id}"
        cached_config = self.cache.get(cache_key)

        if cached_config:
            return json.loads(cached_config)

        # Cache miss - sync from database
        self.sync_slack_config_to_redis(user_id)
        cached_config = self.cache.get(cache_key)

        if cached_config:
            return json.loads(cached_config)

        return None

    def invalidate_slack_cache(self, user_id: str):
        """
        Invalidate and re-sync Slack cache for a user.

        Args:
            user_id: User UUID string
        """
        self._clear_slack_cache(user_id)
        self.sync_slack_config_to_redis(user_id)
        logger.info(f"Invalidated and re-synced Slack cache for user {user_id}")

    def warm_slack_cache_for_active_users(self, limit: int = 1000) -> int:
        """
        Pre-warm Slack cache for active users.

        Args:
            limit: Maximum number of users to cache

        Returns:
            Number of users cached
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get users with Slack channels configured
        user_ids = NotificationChannelEndpoint.objects.filter(
            owner_type='user',
            channel_type='slack',
            enabled=True,
            verified=True
        ).values_list('owner_id', flat=True).distinct()[:limit]

        cached_count = 0
        for user_id in user_ids:
            if self.sync_slack_config_to_redis(str(user_id)):
                cached_count += 1

        logger.info(f"Warmed Slack cache for {cached_count} users")
        return cached_count

    def health_check(self) -> Dict[str, Any]:
        """
        Check Slack cache service health.

        Returns:
            Health status dict
        """
        try:
            # Test cache connectivity
            test_key = "slack:health:test"
            self.cache.set(test_key, "ok", timeout=10)
            test_value = self.cache.get(test_key)
            self.cache.delete(test_key)

            if test_value == "ok":
                # Count cached Slack configs
                slack_count = NotificationChannelEndpoint.objects.filter(
                    channel_type='slack',
                    enabled=True,
                    verified=True
                ).count()

                return {
                    'status': 'healthy',
                    'cache_accessible': True,
                    'slack_channels_configured': slack_count
                }
            else:
                return {
                    'status': 'unhealthy',
                    'cache_accessible': False,
                    'error': 'Cache write/read test failed'
                }

        except Exception as e:
            logger.error(f"Slack cache health check failed: {e}")
            return {
                'status': 'unhealthy',
                'cache_accessible': False,
                'error': str(e)
            }
