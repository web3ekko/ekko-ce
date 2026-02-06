"""
Django signals for GenericGroup and GroupSubscription Redis sync.

These signals ensure that PostgreSQL changes are automatically synced to Redis
for O(1) wasmCloud actor lookups.

Redis Key Patterns:
- group:{group_id}:members → Set of member keys
- member:{target_key}:groups → Set of group IDs (reverse lookup)
"""

import logging
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='app.GenericGroup')
def sync_group_to_redis_on_save(sender, instance, created, **kwargs):
    """
    Sync GenericGroup to Redis when created or updated.

    Args:
        sender: The model class (GenericGroup)
        instance: The GenericGroup being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    try:
        from app.services.group_service import GroupService
        from app.models.groups import GroupType, SYSTEM_GROUP_ACCOUNTS

        # Sync the group members to Redis
        GroupService.sync_group_to_redis(instance)

        # Sync Accounts wallet labels for notification personalization.
        if (
            instance.group_type == GroupType.WALLET
            and (instance.settings or {}).get("system_key") == SYSTEM_GROUP_ACCOUNTS
        ):
            from app.services.notification_cache import NotificationCacheManager

            NotificationCacheManager().cache_accounts_wallet_labels(str(instance.owner_id))

        # Propagate AlertGroup membership changes to subscriptions
        if instance.group_type == GroupType.ALERT:
            GroupService.materialize_alert_group_subscriptions(instance.id)

        action = "created" if created else "updated"
        logger.info(
            f"Synced GenericGroup {instance.id} ({instance.name}) to Redis [{action}] "
            f"({instance.member_count} members)"
        )

    except Exception as e:
        # Signal handlers should NOT raise exceptions that break model operations
        logger.error(
            f"Error syncing GenericGroup {instance.id} to Redis: {e}"
        )


@receiver(post_delete, sender='app.GenericGroup')
def remove_group_from_redis_on_delete(sender, instance, **kwargs):
    """
    Remove GenericGroup from Redis when deleted.

    Args:
        sender: The model class (GenericGroup)
        instance: The GenericGroup being deleted
        **kwargs: Additional signal arguments
    """
    try:
        from app.services.group_service import GroupService
        from app.models.groups import GroupType, SYSTEM_GROUP_ACCOUNTS

        # Get all member keys before deletion (for reverse index cleanup)
        member_keys = instance.get_member_keys()

        # Remove group from Redis
        GroupService.remove_group_from_redis(instance.id, member_keys)

        if (
            instance.group_type == GroupType.WALLET
            and (instance.settings or {}).get("system_key") == SYSTEM_GROUP_ACCOUNTS
        ):
            from app.services.notification_cache import NotificationCacheManager

            NotificationCacheManager().invalidate_accounts_wallet_labels(str(instance.owner_id))

        logger.info(
            f"Removed GenericGroup {instance.id} ({instance.name}) from Redis"
        )

    except Exception as e:
        logger.error(
            f"Error removing GenericGroup {instance.id} from Redis: {e}"
        )


@receiver(pre_delete, sender='app.GenericGroup')
def disable_alerts_targeting_deleted_group(sender, instance, **kwargs):
    """
    Disable alerts that target a group being deleted.

    AlertInstance.target_group uses SET_NULL on delete, which would otherwise leave
    enabled alerts orphaned with stale Redis indexes.
    """
    try:
        from app.models.groups import GroupType
        from app.models.alerts import AlertInstance

        if instance.group_type not in {
            GroupType.WALLET,
            GroupType.NETWORK,
            GroupType.PROTOCOL,
            GroupType.TOKEN,
            GroupType.CONTRACT,
            GroupType.NFT,
        }:
            return

        for alert_instance in AlertInstance.objects.filter(target_group=instance):
            alert_instance.enabled = False
            alert_instance.target_group = None
            alert_instance.save(update_fields=['enabled', 'target_group', 'updated_at'])

    except Exception as e:
        logger.error(
            f"Error disabling alerts targeting deleted group {instance.id}: {e}"
        )


@receiver(post_save, sender='app.GroupSubscription')
def sync_subscription_to_redis_on_save(sender, instance, created, **kwargs):
    """
    Sync GroupSubscription to Redis when created or updated.

    This materializes (or deactivates) subscription-managed AlertInstances when a target
    group/key is subscribed to an alert group.

    Args:
        sender: The model class (GroupSubscription)
        instance: The GroupSubscription being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    try:
        from app.services.group_service import GroupService

        # Materialize (or deactivate) subscription-managed alerts
        GroupService.materialize_subscription(instance)

        action = "created" if created else "updated"
        target_label = (
            instance.target_group.name
            if getattr(instance, "target_group", None)
            else (getattr(instance, "target_key", None) or "<missing target>")
        )
        logger.info(
            f"Materialized GroupSubscription {instance.id} [{action}] "
            f"({instance.alert_group.name} → {target_label}, active={instance.is_active})"
        )

    except Exception as e:
        logger.error(
            f"Error syncing GroupSubscription {instance.id} to Redis: {e}"
        )


@receiver(pre_delete, sender='app.GroupSubscription')
def disable_subscription_alerts_on_delete(sender, instance, **kwargs):
    """
    Disable subscription-managed alerts before deleting a GroupSubscription.

    This ensures we clean up Redis indexes even though `source_subscription` is SET_NULL.
    """
    try:
        from app.models.alerts import AlertInstance

        for alert_instance in AlertInstance.objects.filter(source_subscription=instance, enabled=True):
            alert_instance.enabled = False
            alert_instance.save(update_fields=['enabled', 'updated_at'])

    except Exception as e:
        logger.error(
            f"Error disabling alerts for deleted GroupSubscription {instance.id}: {e}"
        )
