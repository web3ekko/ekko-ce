"""
Example usage of NotificationCacheManager service.

This demonstrates how to use the three types of persistent Redis caches:
1. Alert subscription index
2. Wallet nicknames
3. User notification settings
"""

from app.services.notification_cache import NotificationCacheManager


# ===================================================================
# Example 1: Alert Subscription Index Management
# ===================================================================

def example_alert_subscription_index():
    """
    Manage which users are subscribed to which alert templates.

    Redis Key: template:subscribers:{template_id}
    Redis Type: SET
    Persistence: PERMANENT (no TTL)
    """
    cache_manager = NotificationCacheManager()

    # Add subscribers to an alert template
    template_id = "price-drop-alert-template-uuid"

    cache_manager.add_subscriber_to_template(template_id, "user-123")
    cache_manager.add_subscriber_to_template(template_id, "user-456")
    cache_manager.add_subscriber_to_template(template_id, "user-789")

    # Get all subscribers for the template
    subscribers = cache_manager.get_template_subscribers(template_id)
    print(f"Subscribers for {template_id}: {subscribers}")
    # Output: ['user-123', 'user-456', 'user-789']

    # Remove a subscriber
    cache_manager.remove_subscriber_from_template(template_id, "user-456")

    # Verify removal
    subscribers = cache_manager.get_template_subscribers(template_id)
    print(f"Updated subscribers: {subscribers}")
    # Output: ['user-123', 'user-789']


# ===================================================================
# Example 2: Wallet Nicknames Cache (Cache-Aside Pattern)
# ===================================================================

def example_wallet_nicknames():
    """
    Cache user's custom wallet names for personalized notifications.

    Redis Key: user:wallet_names:{user_id}
    Redis Type: HASH {address:chain_id: nickname}
    Persistence: PERMANENT (no TTL)
    Pattern: Cache-aside (try Redis → PostgreSQL on miss → populate cache)
    """
    cache_manager = NotificationCacheManager()

    user_id = "user-123"

    # First access: Cache miss → queries PostgreSQL → populates Redis
    nicknames = cache_manager.get_wallet_nicknames(user_id)
    print(f"Wallet nicknames for {user_id}: {nicknames}")
    # Output: {'0x1234...5678:1': 'My Main Wallet', '0xabcd...ef01:137': 'Polygon Trading Wallet'}

    # Second access: Cache hit → fast Redis lookup
    nicknames = cache_manager.get_wallet_nicknames(user_id)
    print(f"Cached nicknames: {nicknames}")

    # Invalidate cache when user updates nicknames
    cache_manager.invalidate_wallet_nicknames(user_id)

    # Next access will repopulate from PostgreSQL
    nicknames = cache_manager.get_wallet_nicknames(user_id)


# ===================================================================
# Example 3: User Notification Settings Cache (Cache-Aside Pattern)
# ===================================================================

def example_user_notification_settings():
    """
    Cache user notification preferences and channel configurations.

    Redis Key: user:notifications:{user_id}
    Redis Type: STRING (JSON)
    Persistence: PERMANENT (no TTL)
    Pattern: Cache-aside (try Redis → PostgreSQL on miss → populate cache)
    """
    cache_manager = NotificationCacheManager()

    user_id = "user-123"

    # First access: Cache miss → queries PostgreSQL → populates Redis
    settings = cache_manager.get_user_settings(user_id)
    print(f"User settings: {settings}")
    # Output: {
    #     'user_id': 'user-123',
    #     'websocket_enabled': True,
    #     'notifications_enabled': True,
    #     'channels': {'email': {'enabled': True, 'config': {...}}},
    #     'priority_routing': {...},
    #     'quiet_hours': {...},
    #     'cached_at': '2025-10-20T10:30:00Z'
    # }

    # Check specific channel settings
    if settings:
        websocket_enabled = settings.get('websocket_enabled', False)
        channels = settings.get('channels', {})
        print(f"WebSocket enabled: {websocket_enabled}")
        print(f"Configured channels: {list(channels.keys())}")

    # Invalidate cache when user updates settings
    cache_manager.invalidate_user_cache(user_id)

    # Next access will repopulate from PostgreSQL
    settings = cache_manager.get_user_settings(user_id)


# ===================================================================
# Example 4: Cache Warming for Performance Optimization
# ===================================================================

def example_cache_warming():
    """
    Pre-warm caches for recently active users to improve performance.
    """
    cache_manager = NotificationCacheManager()

    # Warm cache for up to 1000 recently active users
    cached_count = cache_manager.warm_cache_for_active_users(limit=1000)
    print(f"Successfully cached data for {cached_count} active users")


# ===================================================================
# Example 5: Health Check and Diagnostics
# ===================================================================

def example_health_check():
    """
    Check Redis connectivity and service health.
    """
    cache_manager = NotificationCacheManager()

    health_status = cache_manager.health_check()
    print(f"Cache Manager Health: {health_status}")
    # Output: {
    #     'status': 'healthy',
    #     'redis_connected': True,
    #     'message': 'Redis connection successful'
    # }


# ===================================================================
# Example 6: Real-World Notification Flow Integration
# ===================================================================

def example_personalized_notification_flow():
    """
    Complete example: Using all three cache types in a notification flow.

    Scenario: Alert triggered for wallet address → personalize notification
    """
    cache_manager = NotificationCacheManager()

    # Step 1: Get all users subscribed to this alert template
    template_id = "whale-movement-alert-template"
    subscribers = cache_manager.get_template_subscribers(template_id)
    print(f"Found {len(subscribers)} subscribers for alert template")

    # Step 2: For each subscriber, personalize the notification
    for user_id in subscribers:
        # Get user's notification settings
        settings = cache_manager.get_user_settings(user_id)

        if not settings or not settings.get('notifications_enabled'):
            print(f"Skipping user {user_id}: notifications disabled")
            continue

        # Get user's wallet nicknames for personalization
        nicknames = cache_manager.get_wallet_nicknames(user_id)

        # Example wallet address from the alert
        wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
        chain_id = 1  # Ethereum mainnet

        # Build personalized message
        hash_key = f"{wallet_address.lower()}:{chain_id}"
        display_name = nicknames.get(hash_key, f"{wallet_address[:6]}...{wallet_address[-4:]}")

        # Determine notification channels based on priority
        priority = "high"  # From alert
        channels = settings.get('priority_routing', {}).get(priority, ['websocket'])

        print(f"User {user_id}: Send to channels {channels}")
        print(f"  Message: Whale movement detected for {display_name}")

        # Here you would send the actual notification via channels


# ===================================================================
# Example 7: Error Handling and Graceful Degradation
# ===================================================================

def example_error_handling():
    """
    Demonstrate graceful degradation when Redis is unavailable.

    The service automatically falls back to PostgreSQL on Redis errors.
    """
    cache_manager = NotificationCacheManager()

    user_id = "user-123"

    # If Redis is down, get_wallet_nicknames() will:
    # 1. Catch Redis error
    # 2. Log the error
    # 3. Fall back to PostgreSQL via _get_wallet_nicknames_from_db()
    # 4. Return data (but NOT populate cache)
    nicknames = cache_manager.get_wallet_nicknames(user_id)

    # Application continues working even if Redis is unavailable
    print(f"Got nicknames (possibly from fallback): {nicknames}")


# ===================================================================
# Running Examples
# ===================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("NotificationCacheManager Examples")
    print("=" * 70)

    print("\n1. Alert Subscription Index:")
    print("-" * 70)
    example_alert_subscription_index()

    print("\n2. Wallet Nicknames Cache:")
    print("-" * 70)
    example_wallet_nicknames()

    print("\n3. User Notification Settings:")
    print("-" * 70)
    example_user_notification_settings()

    print("\n4. Cache Warming:")
    print("-" * 70)
    example_cache_warming()

    print("\n5. Health Check:")
    print("-" * 70)
    example_health_check()

    print("\n6. Complete Notification Flow:")
    print("-" * 70)
    example_personalized_notification_flow()

    print("\n7. Error Handling:")
    print("-" * 70)
    example_error_handling()
