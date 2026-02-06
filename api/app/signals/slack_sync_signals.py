"""
Django signals for auto-syncing Slack channel configurations to Redis.

Ensures wasmCloud Slack provider always has up-to-date channel configs.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from app.models.notifications import NotificationChannelEndpoint
from app.services.slack_cache_service import SlackCacheService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=NotificationChannelEndpoint)
def sync_slack_config_on_save(sender, instance, **kwargs):
    """
    Auto-sync Slack configuration to Redis when a Slack endpoint is created or updated.

    Triggers on:
    - New Slack channel created
    - Slack webhook URL updated
    - Slack channel enabled/disabled
    - Slack channel verified
    """
    if instance.channel_type == 'slack':
        cache_service = SlackCacheService()
        cache_service.sync_slack_config_to_redis(str(instance.owner_id))
        logger.info(
            f"Auto-synced Slack config to Redis for user {instance.owner_id} "
            f"(endpoint: {instance.label})"
        )


@receiver(post_delete, sender=NotificationChannelEndpoint)
def sync_slack_config_on_delete(sender, instance, **kwargs):
    """
    Auto-sync Slack configuration to Redis when a Slack endpoint is deleted.

    This clears the cache if it was the last Slack channel for the user.
    """
    if instance.channel_type == 'slack':
        cache_service = SlackCacheService()
        cache_service.sync_slack_config_to_redis(str(instance.owner_id))
        logger.info(
            f"Auto-synced Slack config to Redis after deletion for user {instance.owner_id} "
            f"(deleted endpoint: {instance.label})"
        )
