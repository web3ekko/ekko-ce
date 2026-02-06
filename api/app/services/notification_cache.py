"""
Notification Cache Manager for persistent Redis caching in Ekko notification system.

This service manages three types of PERSISTENT (no TTL) Redis caches:
1. Alert subscription index - Which users are subscribed to which alert templates
2. Wallet nicknames - User's custom names for wallet addresses
3. Accounts wallet labels - User's Accounts membership labels (preferred display names)
4. User notification settings - Channel preferences and configuration

All caches are PERMANENT - they persist until explicitly invalidated.
Cache invalidation happens via delete operations when data changes.
"""

import json
import logging
import redis
from typing import Dict, List, Any, Optional
from django.conf import settings

from blockchain.models_wallet_nicknames import WalletNickname
from app.models.notifications import UserNotificationSettings

logger = logging.getLogger(__name__)


class NotificationCacheManager:
    """
    Manages persistent Redis caches for the personalized notification flow.

    All caches are PERMANENT (no TTL) and use a cache-aside pattern:
    - Try Redis first
    - On cache miss: query PostgreSQL
    - Populate Redis with result (no expiry)
    - Return data

    Cache invalidation happens explicitly via delete operations.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize Redis client.

        Args:
            redis_client: Optional Redis client instance. If not provided,
                         creates one from Django settings.REDIS_URL
        """
        self.redis_client = redis_client or redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True  # Automatically decode responses to strings
        )

    # === Alert Subscription Index ===

    def add_subscriber_to_template(self, template_id: str, user_id: str) -> None:
        """
        Add a user to an alert template's subscriber list.

        Creates a PERMANENT Redis key storing JSON array of subscribed user IDs.
        No TTL - persists until explicitly removed.

        Args:
            template_id: Alert template identifier
            user_id: User identifier to add to subscriber list

        Redis Key: template:subscribers:{template_id}
        Redis Type: STRING (JSON array)
        """
        try:
            cache_key = f"template:subscribers:{template_id}"

            # Get current subscribers as JSON array
            current_json = self.redis_client.get(cache_key)

            if current_json:
                subscribers = json.loads(current_json)
            else:
                subscribers = []

            # Add user_id if not already present
            if user_id not in subscribers:
                subscribers.append(user_id)

                # Save updated array as JSON (PERMANENT - no expiry)
                self.redis_client.set(cache_key, json.dumps(subscribers))
                logger.debug(f"Added user {user_id} to template {template_id} subscribers")
            else:
                logger.debug(f"User {user_id} already subscribed to template {template_id}")

        except redis.RedisError as e:
            logger.error(f"Redis error adding subscriber to template {template_id}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for template {template_id}: {e}")

    def remove_subscriber_from_template(self, template_id: str, user_id: str) -> None:
        """
        Remove a user from an alert template's subscriber list.

        Args:
            template_id: Alert template identifier
            user_id: User identifier to remove from subscriber list

        Redis Key: template:subscribers:{template_id}
        Redis Type: STRING (JSON array)
        """
        try:
            cache_key = f"template:subscribers:{template_id}"

            # Get current subscribers as JSON array
            current_json = self.redis_client.get(cache_key)

            if current_json:
                subscribers = json.loads(current_json)

                # Remove user_id if present
                if user_id in subscribers:
                    subscribers.remove(user_id)

                    # Save updated array as JSON (PERMANENT - no expiry)
                    self.redis_client.set(cache_key, json.dumps(subscribers))
                    logger.debug(f"Removed user {user_id} from template {template_id} subscribers")
                else:
                    logger.debug(f"User {user_id} not found in template {template_id} subscribers")
            else:
                logger.debug(f"No subscribers found for template {template_id}")

        except redis.RedisError as e:
            logger.error(f"Redis error removing subscriber from template {template_id}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for template {template_id}: {e}")

    def get_template_subscribers(self, template_id: str) -> List[str]:
        """
        Get all users subscribed to an alert template.

        Args:
            template_id: Alert template identifier

        Returns:
            List of user IDs subscribed to the template. Empty list on error.

        Redis Key: template:subscribers:{template_id}
        Redis Type: STRING (JSON array)
        """
        try:
            cache_key = f"template:subscribers:{template_id}"

            # Get JSON array from Redis
            current_json = self.redis_client.get(cache_key)

            if current_json:
                return json.loads(current_json)
            else:
                return []

        except redis.RedisError as e:
            logger.error(f"Redis error getting subscribers for template {template_id}: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for template {template_id}: {e}")
            return []

    # === Wallet Nicknames Cache ===

    def cache_wallet_nicknames(self, user_id: str) -> Dict[str, str]:
        """
        Cache all wallet nicknames for a user from PostgreSQL.

        Creates a PERMANENT Redis key storing JSON object mapping "address:chain_id" → nickname.
        No TTL - persists until explicitly invalidated.

        Args:
            user_id: User identifier

        Returns:
            Dictionary mapping "address:chain_id" to custom nickname

        Redis Key: user:wallet_names:{user_id}
        Redis Type: STRING (JSON object)
        """
        try:
            # Query PostgreSQL for all user's wallet nicknames
            nicknames = WalletNickname.objects.filter(
                user_id=user_id
            ).values('wallet_address', 'chain_id', 'custom_name')

            if not nicknames:
                logger.debug(f"No wallet nicknames found for user {user_id}")
                return {}

            # Build dictionary mapping: "address:chain_id" → nickname
            cache_key = f"user:wallet_names:{user_id}"
            nickname_map = {}

            for nickname in nicknames:
                hash_field = f"{nickname['wallet_address']}:{nickname['chain_id']}"
                nickname_map[hash_field] = nickname['custom_name']

            # Store in Redis as JSON object (PERMANENT - no expiry)
            self.redis_client.set(cache_key, json.dumps(nickname_map))

            logger.info(
                f"Cached {len(nickname_map)} wallet nicknames for user {user_id}"
            )
            return nickname_map

        except Exception as e:
            logger.error(f"Error caching wallet nicknames for user {user_id}: {e}")
            return {}

    def invalidate_wallet_nicknames(self, user_id: str) -> None:
        """
        Invalidate wallet nicknames cache for a user.

        Deletes the entire HASH for the user. Next access will trigger
        cache_wallet_nicknames() to repopulate from PostgreSQL.

        Args:
            user_id: User identifier

        Redis Key: user:wallet_names:{user_id}
        """
        try:
            cache_key = f"user:wallet_names:{user_id}"
            self.redis_client.delete(cache_key)
            logger.info(f"Invalidated wallet nicknames cache for user {user_id}")
        except redis.RedisError as e:
            logger.error(f"Redis error invalidating wallet nicknames for user {user_id}: {e}")

    def get_wallet_nicknames(self, user_id: str) -> Dict[str, str]:
        """
        Get wallet nicknames for a user (cache-aside pattern).

        1. Try Redis first
        2. On cache miss: query PostgreSQL via cache_wallet_nicknames()
        3. Return data

        Args:
            user_id: User identifier

        Returns:
            Dictionary mapping "address:chain_id" to custom nickname.
            Empty dict on error or no nicknames.

        Redis Key: user:wallet_names:{user_id}
        Redis Type: STRING (JSON object)
        """
        try:
            cache_key = f"user:wallet_names:{user_id}"

            # Try Redis first - get JSON object
            cached_json = self.redis_client.get(cache_key)

            if cached_json:
                logger.debug(f"Cache hit for wallet nicknames: user {user_id}")
                return json.loads(cached_json)

            # Cache miss - populate from PostgreSQL
            logger.debug(f"Cache miss for wallet nicknames: user {user_id}")
            return self.cache_wallet_nicknames(user_id)

        except redis.RedisError as e:
            logger.error(f"Redis error getting wallet nicknames for user {user_id}: {e}")
            # Fallback to PostgreSQL on Redis error
            return self._get_wallet_nicknames_from_db(user_id)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for user {user_id}: {e}")
            # Fallback to PostgreSQL on JSON error
            return self._get_wallet_nicknames_from_db(user_id)

    def _get_wallet_nicknames_from_db(self, user_id: str) -> Dict[str, str]:
        """
        Fallback: Get wallet nicknames directly from PostgreSQL.

        Used when Redis is unavailable. Does NOT populate cache.

        Args:
            user_id: User identifier

        Returns:
            Dictionary mapping "address:chain_id" to custom nickname
        """
        try:
            nicknames = WalletNickname.objects.filter(
                user_id=user_id
            ).values('wallet_address', 'chain_id', 'custom_name')

            nickname_map = {}
            for nickname in nicknames:
                hash_field = f"{nickname['wallet_address']}:{nickname['chain_id']}"
                nickname_map[hash_field] = nickname['custom_name']

            return nickname_map
        except Exception as e:
            logger.error(f"Database error getting wallet nicknames for user {user_id}: {e}")
            return {}

    # === Accounts Wallet Labels Cache ===

    def cache_accounts_wallet_labels(self, user_id: str) -> Dict[str, str]:
        """
        Cache Accounts-group wallet labels for a user from PostgreSQL.

        This enables notification personalization to prefer Accounts membership labels
        over WalletNickname entries.

        Redis Key: user:wallet_labels:{user_id}
        Redis Type: STRING (JSON object)
        Key Format: "{NETWORK}:{subnet}:{address}" (wallet_key, canonical)
        """
        cache_key = f"user:wallet_labels:{user_id}"
        try:
            from app.models.groups import GenericGroup, GroupType, SYSTEM_GROUP_ACCOUNTS
            from app.models.groups import normalize_network_subnet_address_key

            accounts_group = GenericGroup.objects.filter(
                owner_id=user_id,
                group_type=GroupType.WALLET,
                settings__system_key=SYSTEM_GROUP_ACCOUNTS,
            ).first()

            if not accounts_group:
                self.redis_client.delete(cache_key)
                return {}

            labels: Dict[str, str] = {}
            members = (accounts_group.member_data or {}).get("members", {}) or {}

            for member_key, member_meta in members.items():
                if not isinstance(member_meta, dict):
                    continue

                label = str(member_meta.get("label") or "").strip()
                if not label:
                    continue

                normalized_key = normalize_network_subnet_address_key(str(member_key))
                if normalized_key.count(":") < 2:
                    continue
                labels[normalized_key] = label

            self.redis_client.set(cache_key, json.dumps(labels))
            logger.info(f"Cached {len(labels)} accounts wallet labels for user {user_id}")
            return labels

        except Exception as e:
            logger.error(f"Error caching accounts wallet labels for user {user_id}: {e}")
            return {}

    def invalidate_accounts_wallet_labels(self, user_id: str) -> None:
        """Invalidate cached Accounts wallet labels for a user."""
        try:
            cache_key = f"user:wallet_labels:{user_id}"
            self.redis_client.delete(cache_key)
            logger.info(f"Invalidated accounts wallet labels cache for user {user_id}")
        except redis.RedisError as e:
            logger.error(f"Redis error invalidating accounts wallet labels for user {user_id}: {e}")

    def get_accounts_wallet_labels(self, user_id: str) -> Dict[str, str]:
        """
        Get Accounts wallet labels for a user (cache-aside pattern).

        Returns:
            Dict mapping canonical wallet_key (`{NETWORK}:{subnet}:{address}`) → Accounts label.
        """
        cache_key = f"user:wallet_labels:{user_id}"
        try:
            cached_json = self.redis_client.get(cache_key)
            if cached_json:
                return json.loads(cached_json)
            return self.cache_accounts_wallet_labels(user_id)
        except Exception as e:
            logger.error(f"Error getting accounts wallet labels for user {user_id}: {e}")
            return {}

    # === User Notification Settings Cache ===

    def cache_user_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Cache user notification settings from PostgreSQL.

        Creates a PERMANENT Redis STRING storing JSON-serialized settings.
        No TTL - persists until explicitly invalidated.

        Args:
            user_id: User identifier

        Returns:
            Dictionary containing user notification settings.
            Empty dict on error or settings not found.

        Redis Key: user:notifications:{user_id}
        Redis Type: STRING (JSON)
        """
        try:
            # Query PostgreSQL for user settings
            settings_obj = UserNotificationSettings.objects.select_related('user').get(
                user_id=user_id
            )

            # Convert to cache format
            settings_data = settings_obj.to_cache_format()

            # Store in Redis as JSON (PERMANENT - no expiry)
            cache_key = f"user:notifications:{user_id}"
            self.redis_client.set(cache_key, json.dumps(settings_data))

            logger.info(f"Cached notification settings for user {user_id}")
            return settings_data

        except UserNotificationSettings.DoesNotExist:
            logger.warning(f"No notification settings found for user {user_id}")
            return {}
        except Exception as e:
            logger.error(f"Error caching notification settings for user {user_id}: {e}")
            return {}

    def invalidate_user_cache(self, user_id: str) -> None:
        """
        Invalidate user notification settings cache.

        Deletes the JSON string. Next access will trigger cache_user_settings()
        to repopulate from PostgreSQL.

        Args:
            user_id: User identifier

        Redis Key: user:notifications:{user_id}
        """
        try:
            cache_key = f"user:notifications:{user_id}"
            self.redis_client.delete(cache_key)
            logger.info(f"Invalidated notification settings cache for user {user_id}")
        except redis.RedisError as e:
            logger.error(f"Redis error invalidating user cache for user {user_id}: {e}")

    def get_user_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get user notification settings (cache-aside pattern).

        1. Try Redis first
        2. On cache miss: query PostgreSQL via cache_user_settings()
        3. Return data

        Args:
            user_id: User identifier

        Returns:
            Dictionary containing user notification settings.
            Empty dict on error or settings not found.

        Redis Key: user:notifications:{user_id}
        Redis Type: STRING (JSON)
        """
        try:
            cache_key = f"user:notifications:{user_id}"

            # Try Redis first
            cached_settings = self.redis_client.get(cache_key)

            if cached_settings:
                logger.debug(f"Cache hit for notification settings: user {user_id}")
                return json.loads(cached_settings)

            # Cache miss - populate from PostgreSQL
            logger.debug(f"Cache miss for notification settings: user {user_id}")
            return self.cache_user_settings(user_id)

        except redis.RedisError as e:
            logger.error(f"Redis error getting notification settings for user {user_id}: {e}")
            # Fallback to PostgreSQL on Redis error
            return self._get_user_settings_from_db(user_id)

    def _get_user_settings_from_db(self, user_id: str) -> Dict[str, Any]:
        """
        Fallback: Get user settings directly from PostgreSQL.

        Used when Redis is unavailable. Does NOT populate cache.

        Args:
            user_id: User identifier

        Returns:
            Dictionary containing user notification settings
        """
        try:
            settings_obj = UserNotificationSettings.objects.select_related('user').get(
                user_id=user_id
            )
            return settings_obj.to_cache_format()
        except UserNotificationSettings.DoesNotExist:
            logger.warning(f"No notification settings found for user {user_id}")
            return {}
        except Exception as e:
            logger.error(f"Database error getting notification settings for user {user_id}: {e}")
            return {}

    # === Utility Methods ===

    def warm_cache_for_active_users(self, limit: int = 1000) -> int:
        """
        Pre-warm caches for recently active users.

        Caches both wallet nicknames and notification settings for users
        who have been active recently. Useful for performance optimization.

        Args:
            limit: Maximum number of users to cache (default: 1000)

        Returns:
            Number of users successfully cached
        """
        try:
            from django.contrib.auth import get_user_model
            from django.utils import timezone
            from datetime import timedelta

            User = get_user_model()

            # Get recently active users (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            active_users = User.objects.filter(
                last_login__gte=thirty_days_ago
            ).values_list('id', flat=True)[:limit]

            cached_count = 0
            for user_id in active_users:
                try:
                    # Cache wallet nicknames
                    self.cache_wallet_nicknames(str(user_id))

                    # Cache notification settings
                    self.cache_user_settings(str(user_id))

                    cached_count += 1
                except Exception as e:
                    logger.warning(f"Failed to cache data for user {user_id}: {e}")

            logger.info(
                f"Warmed notification cache for {cached_count}/{len(active_users)} active users"
            )
            return cached_count

        except Exception as e:
            logger.error(f"Error warming cache for active users: {e}")
            return 0

    def health_check(self) -> Dict[str, Any]:
        """
        Check Redis connectivity and basic operations.

        Returns:
            Dictionary with health status and diagnostics
        """
        try:
            # Test basic Redis operations
            test_key = "health:check:notification_cache"
            self.redis_client.set(test_key, "ok", ex=5)  # 5 second TTL for test key
            test_value = self.redis_client.get(test_key)

            return {
                "status": "healthy" if test_value == "ok" else "degraded",
                "redis_connected": True,
                "message": "Redis connection successful"
            }
        except redis.RedisError as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "message": f"Redis connection failed: {str(e)}"
            }
