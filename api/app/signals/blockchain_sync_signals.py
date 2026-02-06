"""
Django signals for BlockchainNode Redis sync.

These signals ensure that BlockchainNode changes are automatically synced
to Redis for wasmCloud provider configuration lookup.

Redis Key Pattern:
- provider:config:newheads-{vm_type}:{chain_id}

Behavior:
- On save with enabled=True: Sync config to Redis
- On save with enabled=False: Remove config from Redis
- On delete: Remove config from Redis
"""

import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='app.BlockchainNode')
def sync_blockchain_node_to_redis(sender, instance, created, **kwargs):
    """
    Sync BlockchainNode to Redis when created or updated.

    Args:
        sender: The model class (BlockchainNode)
        instance: The BlockchainNode instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    try:
        from app.services.blockchain_sync_service import BlockchainSyncService

        if instance.enabled:
            # Sync enabled node to Redis
            BlockchainSyncService.sync_node_to_redis(instance)
            action = "created" if created else "updated"
            logger.info(
                f"Synced BlockchainNode {instance.chain_id} ({instance.chain_name}) "
                f"to Redis [{action}]"
            )
        else:
            # Remove disabled node from Redis
            BlockchainSyncService.remove_node_from_redis(
                instance.vm_type, instance.chain_id
            )
            logger.info(
                f"Removed disabled BlockchainNode {instance.chain_id} "
                f"({instance.chain_name}) from Redis"
            )

    except Exception as e:
        # Signal handlers should NOT raise exceptions that break model operations
        logger.error(
            f"Error syncing BlockchainNode {instance.chain_id} to Redis: {e}"
        )


@receiver(post_delete, sender='app.BlockchainNode')
def remove_blockchain_node_from_redis(sender, instance, **kwargs):
    """
    Remove BlockchainNode from Redis when deleted.

    Args:
        sender: The model class (BlockchainNode)
        instance: The BlockchainNode instance being deleted
        **kwargs: Additional signal arguments
    """
    try:
        from app.services.blockchain_sync_service import BlockchainSyncService

        BlockchainSyncService.remove_node_from_redis(
            instance.vm_type, instance.chain_id
        )
        logger.info(
            f"Removed BlockchainNode {instance.chain_id} ({instance.chain_name}) "
            f"from Redis [deleted]"
        )

    except Exception as e:
        # Signal handlers should NOT raise exceptions that break model operations
        logger.error(
            f"Error removing BlockchainNode {instance.chain_id} from Redis: {e}"
        )
