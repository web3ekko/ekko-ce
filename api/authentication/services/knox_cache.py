"""
Knox Token Redis Cache Service

Caches Knox tokens in Redis for WebSocket provider authentication.
The WebSocket provider validates tokens by looking up the first 8 characters
of the token in Redis.

Redis Key Format: knox:tokens:{token_key}
Where token_key = first 8 characters of the Knox token

JSON Structure:
{
    "user_id": "string",
    "token_key": "string (first 8 chars)",
    "expiry": "ISO8601 datetime",
    "created_at": "ISO8601 datetime"
}
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import redis
from django.conf import settings
from knox.models import AuthToken

logger = logging.getLogger(__name__)


class KnoxTokenCacheService:
    """Service for caching Knox tokens in Redis for WebSocket authentication."""

    def __init__(self):
        """Initialize Redis connection."""
        redis_url = settings.CACHES['default']['LOCATION']
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    def cache_token(self, token: str, user_id: str, expiry: datetime) -> bool:
        """
        Cache a Knox token in Redis for WebSocket provider authentication.

        Args:
            token: The full Knox token string
            user_id: The user ID associated with the token
            expiry: Token expiry datetime

        Returns:
            True if caching succeeded, False otherwise
        """
        if len(token) < 8:
            logger.error("Token too short to cache (< 8 chars)")
            return False

        try:
            token_key = token[:8]
            redis_key = f"knox:tokens:{token_key}"

            # Ensure expiry is timezone-aware
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)

            token_data = {
                "user_id": str(user_id),
                "token_key": token_key,
                "expiry": expiry.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Calculate TTL from expiry
            ttl_seconds = int((expiry - datetime.now(timezone.utc)).total_seconds())
            if ttl_seconds <= 0:
                logger.warning(f"Token already expired, not caching: {token_key}")
                return False

            # Store in Redis with TTL
            self.redis_client.setex(
                redis_key,
                ttl_seconds,
                json.dumps(token_data)
            )

            logger.info(f"Cached Knox token {token_key} for user {user_id} (TTL: {ttl_seconds}s)")
            return True

        except Exception as e:
            logger.error(f"Failed to cache Knox token: {e}")
            return False

    def invalidate_token(self, token: str) -> bool:
        """
        Remove a Knox token from Redis cache.

        Args:
            token: The full Knox token string (or at least first 8 chars)

        Returns:
            True if invalidation succeeded, False otherwise
        """
        if len(token) < 8:
            logger.error("Token too short to invalidate (< 8 chars)")
            return False

        try:
            token_key = token[:8]
            redis_key = f"knox:tokens:{token_key}"

            result = self.redis_client.delete(redis_key)

            if result:
                logger.info(f"Invalidated Knox token from cache: {token_key}")
            else:
                logger.debug(f"Knox token not found in cache: {token_key}")

            return True

        except Exception as e:
            logger.error(f"Failed to invalidate Knox token: {e}")
            return False

    def invalidate_all_user_tokens(self, user_id: str) -> int:
        """
        Invalidate all cached tokens for a user.

        Note: This requires scanning Redis keys which can be expensive.
        In production, consider maintaining a user->tokens index.

        Args:
            user_id: The user ID

        Returns:
            Number of tokens invalidated
        """
        try:
            count = 0
            # Scan for all knox:tokens:* keys and check user_id
            for key in self.redis_client.scan_iter("knox:tokens:*"):
                try:
                    data = self.redis_client.get(key)
                    if data:
                        token_data = json.loads(data)
                        if token_data.get("user_id") == str(user_id):
                            self.redis_client.delete(key)
                            count += 1
                except json.JSONDecodeError:
                    continue

            logger.info(f"Invalidated {count} Knox tokens for user {user_id}")
            return count

        except Exception as e:
            logger.error(f"Failed to invalidate user tokens: {e}")
            return 0

    def get_token(self, token_key: str) -> Optional[dict]:
        """
        Get cached token data by token key.

        Args:
            token_key: First 8 characters of the token

        Returns:
            Token data dict or None if not found
        """
        try:
            redis_key = f"knox:tokens:{token_key}"
            data = self.redis_client.get(redis_key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Failed to get Knox token: {e}")
            return None

    def warm_cache(self) -> dict:
        """
        Warm the Redis cache with all valid Knox tokens from database.

        Returns:
            Dict with counts: {"synced": N, "failed": M, "expired": E}
        """
        from django.utils import timezone as dj_timezone

        stats = {"synced": 0, "failed": 0, "expired": 0}
        now = dj_timezone.now()

        # Get all non-expired Knox tokens
        # Note: AuthToken stores digest, not the original token
        # We can only warm cache for tokens we have the original for
        # This is mainly for new tokens going forward

        valid_tokens = AuthToken.objects.filter(expiry__gt=now)

        logger.info(f"Found {valid_tokens.count()} valid Knox tokens in database")
        logger.info("Note: Cache warming only works for tokens where original is available")
        logger.info("New tokens will be cached automatically on creation")

        return stats


# Singleton instance
_knox_cache_service = None


def get_knox_cache_service() -> KnoxTokenCacheService:
    """Get or create the Knox cache service singleton."""
    global _knox_cache_service
    if _knox_cache_service is None:
        _knox_cache_service = KnoxTokenCacheService()
    return _knox_cache_service
