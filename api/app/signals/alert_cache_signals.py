"""
Django signals for syncing AlertInstance cache indexes to Redis.

These signals keep the alerts:address:* and related indices up to date for
wasmCloud alert routing, per PRD-REDIS-INDEX-MANAGER-001.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="app.AlertInstance")
def sync_alert_cache_on_save(sender, instance, created, **kwargs):
    """
    Sync alert cache for AlertInstance saves.

    - Enabled alerts are (re)cached.
    - Disabled alerts are removed from cache.
    - Updates remove stale indexes before re-sync.
    """
    try:
        from app.services.alert_cache import AlertCacheManager
        from app.services.group_service import GroupService

        manager = AlertCacheManager()
        alert_id = str(instance.id)
        user_id = str(instance.user_id) if getattr(instance, "user_id", None) is not None else None

        if not getattr(instance, "enabled", False):
            manager.remove_alert_from_redis(alert_id)
            GroupService.remove_alert_targets_from_redis(alert_id, user_id=user_id)
            return

        if not created:
            # Best-effort cleanup to avoid stale indexes after target changes.
            manager.remove_alert_from_redis(alert_id)

        manager.sync_alert_to_redis(instance)
        GroupService().sync_alert_targets_to_redis(instance)
    except Exception as exc:
        logger.error("Error syncing alert cache for AlertInstance %s: %s", instance.id, exc)


@receiver(post_delete, sender="app.AlertInstance")
def remove_alert_cache_on_delete(sender, instance, **kwargs):
    """Remove alert cache entries when an AlertInstance is deleted."""
    try:
        from app.services.alert_cache import AlertCacheManager
        from app.services.group_service import GroupService

        alert_id = str(instance.id)
        user_id = str(instance.user_id) if getattr(instance, "user_id", None) is not None else None
        AlertCacheManager().remove_alert_from_redis(alert_id)
        GroupService.remove_alert_targets_from_redis(alert_id, user_id=user_id)
    except Exception as exc:
        logger.error("Error removing alert cache for AlertInstance %s: %s", instance.id, exc)
