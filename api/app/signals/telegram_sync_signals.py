"""
Telegram Sync Signals

Automatically sync Telegram notification configurations to Redis cache
when NotificationChannelEndpoint models are saved or deleted.

This ensures the wasmCloud Telegram provider always has up-to-date
configuration data without manual cache invalidation.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from app.models.notifications import NotificationChannelEndpoint
from app.services.telegram_cache_service import TelegramCacheService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=NotificationChannelEndpoint)
def sync_telegram_config_on_save(sender, instance, **kwargs):
    """
    Sync Telegram configuration to Redis after NotificationChannelEndpoint save.

    Triggered when:
    - New Telegram endpoint is created
    - Existing Telegram endpoint is updated (enabled/disabled, verified, config changed)
    """
    if instance.channel_type == 'telegram':
        logger.info(f"Syncing Telegram config for user {instance.owner_id} after save")

        cache_service = TelegramCacheService()
        success = cache_service.sync_telegram_config_to_redis(str(instance.owner_id))

        if success:
            logger.info(f"Successfully synced Telegram config for user {instance.owner_id}")
        else:
            logger.error(f"Failed to sync Telegram config for user {instance.owner_id}")


@receiver(post_delete, sender=NotificationChannelEndpoint)
def sync_telegram_config_on_delete(sender, instance, **kwargs):
    """
    Sync Telegram configuration to Redis after NotificationChannelEndpoint deletion.

    This will clear the cache if no other enabled Telegram endpoints exist for the user.
    """
    if instance.channel_type == 'telegram':
        logger.info(f"Syncing Telegram config for user {instance.owner_id} after delete")

        cache_service = TelegramCacheService()
        success = cache_service.sync_telegram_config_to_redis(str(instance.owner_id))

        if success:
            logger.info(f"Successfully synced Telegram config for user {instance.owner_id}")
        else:
            logger.error(f"Failed to sync Telegram config for user {instance.owner_id}")
