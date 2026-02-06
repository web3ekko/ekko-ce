"""
Telegram Cache Service

Synchronizes Telegram notification channel configurations to Redis cache
for fast access by the wasmCloud Telegram notification provider.

Architecture:
- Django stores Telegram configs in PostgreSQL
- This service syncs configs to Redis for wasmCloud provider access
- Automatic sync via Django signals on save/delete
- Manual sync available via service methods

Cache Structure:
- telegram:config:{user_id} - Telegram channel configuration (24h TTL)
- telegram:stats:{user_id}:success - Successful delivery count (30d TTL)
- telegram:stats:{user_id}:failure - Failed delivery count (30d TTL)
"""

import json
import logging
from typing import Dict, Optional

from django.core.cache import cache

from app.models.notifications import NotificationChannelEndpoint

logger = logging.getLogger(__name__)


class TelegramCacheService:
    """Service for syncing Telegram configurations to Redis"""

    CACHE_TTL = 86400  # 24 hours

    def __init__(self):
        self.cache = cache

    def sync_telegram_config_to_redis(self, user_id: str) -> bool:
        """
        Sync Telegram configuration for a user to Redis cache.

        Args:
            user_id: User UUID as string

        Returns:
            bool: True if sync successful, False otherwise
        """
        try:
            # Get enabled and verified Telegram endpoints for this user
            telegram_endpoints = NotificationChannelEndpoint.objects.filter(
                owner_type='user',
                owner_id=user_id,
                channel_type='telegram',
                enabled=True,
                verified=True
            )

            if not telegram_endpoints.exists():
                # No active Telegram endpoints - clear cache
                self._clear_telegram_cache(user_id)
                logger.info(f"No active Telegram endpoints for user {user_id}, cache cleared")
                return True

            # Use the first enabled endpoint (multi-endpoint support can be added later)
            telegram_endpoint = telegram_endpoints.first()

            # Build Telegram config
            telegram_config = {
                'user_id': user_id,
                'bot_token': telegram_endpoint.config.get('bot_token'),
                'chat_id': telegram_endpoint.config.get('chat_id'),
                'username': telegram_endpoint.config.get('username'),
                'enabled': True
            }

            # Store in Redis
            cache_key = f"telegram:config:{user_id}"
            self.cache.set(cache_key, json.dumps(telegram_config), timeout=self.CACHE_TTL)

            logger.info(f"Synced Telegram config to Redis for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to sync Telegram config for user {user_id}: {str(e)}")
            return False

    def _clear_telegram_cache(self, user_id: str) -> None:
        """Clear Telegram config from Redis cache"""
        cache_key = f"telegram:config:{user_id}"
        self.cache.delete(cache_key)

    def get_telegram_config(self, user_id: str) -> Optional[Dict]:
        """
        Get Telegram configuration from Redis cache.

        Args:
            user_id: User UUID as string

        Returns:
            Dict with Telegram config or None if not found
        """
        try:
            cache_key = f"telegram:config:{user_id}"
            config_json = self.cache.get(cache_key)

            if config_json:
                return json.loads(config_json)

            return None

        except Exception as e:
            logger.error(f"Failed to get Telegram config for user {user_id}: {str(e)}")
            return None

    def is_telegram_enabled_for_user(self, user_id: str) -> bool:
        """
        Check if Telegram is enabled for a user.

        Args:
            user_id: User UUID as string

        Returns:
            bool: True if Telegram is enabled and configured
        """
        config = self.get_telegram_config(user_id)
        return config is not None and config.get('enabled', False)

    def get_delivery_stats(self, user_id: str) -> Dict[str, int]:
        """
        Get delivery statistics for a user's Telegram notifications.

        Args:
            user_id: User UUID as string

        Returns:
            Dict with success_count and failure_count
        """
        try:
            success_key = f"telegram:stats:{user_id}:success"
            failure_key = f"telegram:stats:{user_id}:failure"

            success_count = self.cache.get(success_key, 0)
            failure_count = self.cache.get(failure_key, 0)

            return {
                'success_count': int(success_count),
                'failure_count': int(failure_count)
            }

        except Exception as e:
            logger.error(f"Failed to get delivery stats for user {user_id}: {str(e)}")
            return {'success_count': 0, 'failure_count': 0}

    def store_verification_code(self, user_id: str, chat_id: str, code: str) -> bool:
        """
        Store verification code for Telegram channel setup.

        Args:
            user_id: User UUID as string
            chat_id: Telegram chat ID
            code: 6-digit verification code

        Returns:
            bool: True if stored successfully
        """
        try:
            cache_key = f"telegram:verification:{user_id}:{chat_id}"
            # 15 minute expiry for verification codes
            self.cache.set(cache_key, code, timeout=900)

            logger.info(f"Stored verification code for user {user_id}, chat_id {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store verification code: {str(e)}")
            return False

    def get_verification_code(self, user_id: str, chat_id: str) -> Optional[str]:
        """
        Get verification code for Telegram channel setup.

        Args:
            user_id: User UUID as string
            chat_id: Telegram chat ID

        Returns:
            Verification code or None if not found/expired
        """
        try:
            cache_key = f"telegram:verification:{user_id}:{chat_id}"
            return self.cache.get(cache_key)

        except Exception as e:
            logger.error(f"Failed to get verification code: {str(e)}")
            return None

    def delete_verification_code(self, user_id: str, chat_id: str) -> bool:
        """
        Delete verification code after successful verification.

        Args:
            user_id: User UUID as string
            chat_id: Telegram chat ID

        Returns:
            bool: True if deleted successfully
        """
        try:
            cache_key = f"telegram:verification:{user_id}:{chat_id}"
            self.cache.delete(cache_key)

            logger.info(f"Deleted verification code for user {user_id}, chat_id {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete verification code: {str(e)}")
            return False
