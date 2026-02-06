"""
Group Service - Unified group operations with Redis sync

This service provides:
1. JSONB member operations (add, remove, bulk)
2. Redis sync for wasmCloud O(1) lookups
3. Reverse index: wallet:{key}:alerts for instant alert lookups

Redis Structure (SET versions - for standard Redis clients):
    group:{id}:members         - SET of member keys
    member:{key}:groups        - SET of group IDs (reverse lookup)
    groups:type:{type}         - SET of group IDs by type
    groups:owner:{user_id}     - SET of group IDs by owner

Alert Runtime Indices (scheduler routing + partitioning):
    alerts:event_idx:target_groups:{target_key}          - SET of group IDs that contain target_key
    alerts:targets:group:{group_id}:{NETWORK}:{subnet}   - SET of member keys for the group partition
    alerts:targets:group_partitions:{group_id}           - SET of partition set keys (cleanup index)

JSON Array Versions (for wasmCloud - wasi:keyvalue doesn't support SMEMBERS):
    group:{id}:members:json    - JSON array of member keys
    wallet:{key}:alerts:json   - JSON array of alert IDs watching this wallet
    alert:{id}:targets:json    - JSON array of target wallet keys
    alert:{id}:groups:json     - JSON array of target group IDs

Alert Target Indexes (Critical for wasmCloud):
    alert:{alert_id}:targets   - SET of target keys this alert watches
    alert:{alert_id}:groups    - SET of target group IDs
    wallet:{key}:alerts        - SET of alert IDs watching this wallet (REVERSE INDEX)
    user:{user_id}:alerts      - SET of alert IDs owned by user

See PRD: /docs/prd/apps/api/PRD-Unified-Group-Model-USDT.md
"""

import re
import json
import logging
from typing import List, Dict, Optional, Set, Tuple
from uuid import UUID

import redis
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

ALERT_RUNTIME_TARGET_GROUPS_PREFIX = "alerts:event_idx:target_groups:"
ALERT_RUNTIME_GROUP_TARGETS_PREFIX = "alerts:targets:group:"
ALERT_RUNTIME_GROUP_PARTITIONS_PREFIX = "alerts:targets:group_partitions:"


def _alert_runtime_target_groups_key(member_key: str) -> str:
    return f"{ALERT_RUNTIME_TARGET_GROUPS_PREFIX}{member_key}"


def _alert_runtime_group_partition_set_key(group_id: UUID, network: str, subnet: str) -> str:
    return f"{ALERT_RUNTIME_GROUP_TARGETS_PREFIX}{group_id}:{network}:{subnet}"


def _alert_runtime_group_partitions_index_key(group_id: UUID) -> str:
    return f"{ALERT_RUNTIME_GROUP_PARTITIONS_PREFIX}{group_id}"


class GroupService:
    """
    Unified service for all group operations with Redis sync.

    Handles:
    - Member CRUD operations with atomic JSONB updates
    - Redis cache sync for wasmCloud performance
    - Group lifecycle management
    """

    def __init__(self):
        """Initialize Redis connection."""
        cache_location = settings.CACHES.get("default", {}).get("LOCATION")
        # Tests often use LocMemCache, but group sync still targets a real Redis instance.
        redis_url = (
            cache_location
            if isinstance(cache_location, str)
            and cache_location.startswith(("redis://", "rediss://", "unix://"))
            else getattr(settings, "REDIS_URL", cache_location)
        )
        self.redis = redis.from_url(redis_url, decode_responses=True)

    # -------------------------------------------------------------------------
    # Member Operations (JSONB + Redis sync)
    # -------------------------------------------------------------------------

    @transaction.atomic
    def add_members(
        self,
        group_id: UUID,
        members: List[Dict],
        sync_redis: bool = True
    ) -> int:
        """
        Add members to group with JSONB update and Redis sync.

        Args:
            group_id: UUID of the group
            members: List of dicts with 'key' and optional metadata:
                [
                    {"key": "ETH:mainnet:0x123", "label": "Treasury", "tags": ["defi"]},
                    {"key": "SOL:mainnet:5yBb...", "metadata": {"source": "import"}}
                ]
            sync_redis: Whether to sync to Redis (default: True)

        Returns:
            Number of members added

        Raises:
            GenericGroup.DoesNotExist: If group not found
            ValidationError: If AlertGroup members have mismatched alert_type
        """
        from app.models.groups import GenericGroup, GroupType, SYSTEM_GROUP_ACCOUNTS

        group = GenericGroup.objects.select_for_update().get(id=group_id)

        # Normalize member keys to canonical form for this group type.
        normalized_members: List[Dict] = []
        for member in members:
            raw_key = member.get('key')
            if not isinstance(raw_key, str) or not raw_key.strip():
                raise ValidationError("Member must include non-empty 'key'")
            normalized_members.append({**member, 'key': group.normalize_member_key(raw_key)})

        # Validate AlertGroup members before adding
        if group.group_type == GroupType.ALERT:
            member_keys = [m['key'] for m in normalized_members]
            group.validate_alert_group_members(member_keys)

        current_members = group.member_data.get('members', {})
        now = timezone.now().isoformat()
        added_keys = []

        for member in normalized_members:
            key = member['key']
            if key not in current_members:
                member_metadata = member.get('metadata', {}) or {}
                if group.group_type == GroupType.WALLET and group.settings.get('system_key') == SYSTEM_GROUP_ACCOUNTS:
                    member_metadata = {
                        "owner_verified": bool(member_metadata.get("owner_verified", False)),
                        **member_metadata,
                    }

                current_members[key] = {
                    'added_at': now,
                    'added_by': str(member.get('added_by', '')),
                    'label': member.get('label', ''),
                    'tags': member.get('tags', []),
                    'metadata': member_metadata
                }
                added_keys.append(key)

        if added_keys:
            group.member_data['members'] = current_members
            group.member_count = len(current_members)
            group.save(update_fields=['member_data', 'member_count', 'updated_at'])

            if sync_redis:
                self._sync_members_to_redis(group_id, added_keys, add=True)

            logger.info(f"Added {len(added_keys)} members to group {group_id}")

        return len(added_keys)

    @transaction.atomic
    def remove_members(
        self,
        group_id: UUID,
        member_keys: List[str],
        sync_redis: bool = True
    ) -> int:
        """
        Remove members from group with JSONB update and Redis sync.

        Args:
            group_id: UUID of the group
            member_keys: List of member keys to remove
            sync_redis: Whether to sync to Redis (default: True)

        Returns:
            Number of members removed
        """
        from app.models.groups import GenericGroup

        group = GenericGroup.objects.select_for_update().get(id=group_id)
        current_members = group.member_data.get('members', {})
        removed_keys = []

        for key in member_keys:
            normalized_key = group.normalize_member_key(key)
            if key in current_members:
                del current_members[key]
                removed_keys.append(key)
            elif normalized_key in current_members:
                del current_members[normalized_key]
                removed_keys.append(normalized_key)

        if removed_keys:
            group.member_data['members'] = current_members
            group.member_count = len(current_members)
            group.save(update_fields=['member_data', 'member_count', 'updated_at'])

            if sync_redis:
                self._sync_members_to_redis(group_id, removed_keys, add=False)

            logger.info(f"Removed {len(removed_keys)} members from group {group_id}")

        return len(removed_keys)

    def get_members(
        self,
        group_id: UUID,
        use_cache: bool = True
    ) -> List[str]:
        """
        Get member keys - Redis first, PostgreSQL fallback.

        Args:
            group_id: UUID of the group
            use_cache: Whether to try Redis first (default: True)

        Returns:
            List of member keys
        """
        if use_cache:
            members = self.redis.smembers(f"group:{group_id}:members")
            if members:
                return list(members)

        # Fallback to PostgreSQL
        from app.models.groups import GenericGroup
        group = GenericGroup.objects.get(id=group_id)
        return list(group.member_data.get('members', {}).keys())

    def is_member(self, group_id: UUID, member_key: str) -> bool:
        """O(1) membership check via Redis."""
        return bool(self.redis.sismember(f"group:{group_id}:members", member_key))

    def get_member_metadata(
        self,
        group_id: UUID,
        member_key: str
    ) -> Optional[Dict]:
        """Get metadata for a specific member from PostgreSQL."""
        from app.models.groups import GenericGroup
        group = GenericGroup.objects.get(id=group_id)
        normalized_key = group.normalize_member_key(member_key)
        members = group.member_data.get('members', {})
        return members.get(member_key) or members.get(normalized_key)

    # -------------------------------------------------------------------------
    # Reverse Index Operations (wallet → alerts)
    # -------------------------------------------------------------------------

    def get_groups_for_member(self, member_key: str) -> List[str]:
        """Get all group IDs containing this member key (O(1) via Redis)."""
        return list(self.redis.smembers(f"member:{member_key}:groups"))

    def get_alerts_for_wallet(self, wallet_key: str) -> List[str]:
        """
        Get all alert IDs watching this wallet (O(1) via Redis).

        This is the critical lookup for wasmCloud actors:
        1. Transaction arrives with wallet_key
        2. Redis lookup: SMEMBERS wallet:{key}:alerts
        3. For each alert, evaluate condition

        Args:
            wallet_key: Wallet key in format {network}:{subnet}:{address}

        Returns:
            List of alert UUIDs watching this wallet
        """
        return list(self.redis.smembers(f"wallet:{wallet_key}:alerts"))

    # -------------------------------------------------------------------------
    # Alert Target Sync (called from Django signals)
    # -------------------------------------------------------------------------

    def sync_alert_targets_to_redis(self, alert_instance) -> None:
        """
        Sync alert targets to Redis for wasmCloud lookups.

        Updates:
        - alert:{id}:targets - SET of target keys
        - alert:{id}:targets:json - JSON array for wasmCloud
        - alert:{id}:groups - SET of target group IDs
        - alert:{id}:groups:json - JSON array of group IDs for wasmCloud
        - wallet:{key}:alerts - Reverse index (CRITICAL for wasmCloud)
        - wallet:{key}:alerts:json - JSON array for wasmCloud
        - user:{user_id}:alerts - User's alert index

        Args:
            alert_instance: AlertInstance model instance
        """
        alert_id = str(alert_instance.id)
        pipe = self.redis.pipeline()

        # Get target wallet keys
        target_keys = self._get_alert_target_keys(alert_instance)

        # Get target group IDs if using group-based targeting
        target_group_ids = []
        if hasattr(alert_instance, 'target_group') and alert_instance.target_group:
            target_group_ids = [str(alert_instance.target_group.id)]

        # Get existing targets to compute diff for reverse index cleanup
        existing_targets = self.redis.smembers(f"alert:{alert_id}:targets")

        # Clear and rebuild alert targets
        pipe.delete(f"alert:{alert_id}:targets")
        if target_keys:
            pipe.sadd(f"alert:{alert_id}:targets", *target_keys)

        # Store target groups (SET + JSON)
        pipe.delete(f"alert:{alert_id}:groups")
        if target_group_ids:
            pipe.sadd(f"alert:{alert_id}:groups", *target_group_ids)
        pipe.set(f"alert:{alert_id}:groups:json", json.dumps(target_group_ids))

        # Update reverse indexes
        # Remove from old targets no longer in list
        for old_key in existing_targets:
            if old_key not in target_keys:
                pipe.srem(f"wallet:{old_key}:alerts", alert_id)
                self._update_wallet_alerts_json(old_key, alert_id, add=False)

        # Add to new targets
        for wallet_key in target_keys:
            pipe.sadd(f"wallet:{wallet_key}:alerts", alert_id)
            # Also update JSON array for wasmCloud compatibility
            self._update_wallet_alerts_json(wallet_key, alert_id, add=True)

        # User's alerts index
        pipe.sadd(f"user:{alert_instance.user_id}:alerts", alert_id)

        # Store targets as JSON array for wasmCloud compatibility (wasi:keyvalue doesn't support SMEMBERS)
        pipe.set(f"alert:{alert_id}:targets:json", json.dumps(list(target_keys)))

        pipe.execute()
        logger.info(f"Synced alert {alert_id} with {len(target_keys)} targets and {len(target_group_ids)} groups to Redis")

    def remove_alert_from_redis(self, alert_id: str, user_id: Optional[str] = None) -> None:
        """
        Remove alert data from Redis.

        Cleans up:
        - alert:{id}:targets (SET + JSON)
        - alert:{id}:groups (SET + JSON)
        - wallet:{key}:alerts (SET + JSON reverse index)
        - user:{user_id}:alerts

        Args:
            alert_id: UUID of the alert
            user_id: User ID for user index cleanup
        """
        pipe = self.redis.pipeline()

        # Get targets before deleting
        target_keys = self.redis.smembers(f"alert:{alert_id}:targets")

        # Remove from reverse indexes (both SET and JSON)
        for wallet_key in target_keys:
            pipe.srem(f"wallet:{wallet_key}:alerts", alert_id)
            self._update_wallet_alerts_json(wallet_key, alert_id, add=False)

        # Remove alert data (both SET and JSON versions)
        pipe.delete(f"alert:{alert_id}:targets")
        pipe.delete(f"alert:{alert_id}:targets:json")
        pipe.delete(f"alert:{alert_id}:groups")
        pipe.delete(f"alert:{alert_id}:groups:json")

        # Remove from user's alerts
        if user_id:
            pipe.srem(f"user:{user_id}:alerts", alert_id)

        pipe.execute()
        logger.info(f"Removed alert {alert_id} from Redis cache")

    # -------------------------------------------------------------------------
    # Class Methods for Signal Handlers
    # -------------------------------------------------------------------------

    @classmethod
    def sync_group_to_redis(cls, group) -> None:
        """
        Sync group to Redis (called from Django signal).

        Args:
            group: GenericGroup instance
        """
        service = cls()
        service.rebuild_group_redis_cache(group.id)

    @classmethod
    def remove_group_from_redis(cls, group_id: UUID, member_keys: List[str] = None) -> None:
        """
        Remove group from Redis (called from Django signal).

        Cleans up both SET and JSON versions for wasmCloud compatibility.

        Args:
            group_id: UUID of the group
            member_keys: Optional list of member keys (for reverse index cleanup)
        """
        service = cls()
        pipe = service.redis.pipeline()

        # Get members if not provided
        if member_keys is None:
            member_keys = list(service.redis.smembers(f"group:{group_id}:members"))

        partitions_index_key = _alert_runtime_group_partitions_index_key(group_id)
        partition_keys = list(service.redis.smembers(partitions_index_key))

        # Remove from reverse indexes
        for member_key in member_keys:
            pipe.srem(f"member:{member_key}:groups", str(group_id))
            pipe.srem(_alert_runtime_target_groups_key(member_key), str(group_id))

        # Remove alert runtime partition sets
        for partition_key in partition_keys:
            pipe.delete(partition_key)
        pipe.delete(partitions_index_key)

        # Remove group members (SET + JSON versions)
        pipe.delete(f"group:{group_id}:members")
        pipe.delete(f"group:{group_id}:members:json")

        # Remove from type index (we don't know the type, so try all)
        from app.models.groups import GroupType
        for group_type in GroupType.values:
            pipe.srem(f"groups:type:{group_type}", str(group_id))

        pipe.execute()
        logger.info(f"Removed group {group_id} from Redis cache")

    @classmethod
    def materialize_subscription(cls, subscription) -> None:
        """
        Materialize a GroupSubscription by cloning AlertInstances per subscriber.

        AlertGroups (GenericGroup type 'alert') contain AlertTemplates as members.
        A subscription clones one AlertInstance per template and targets it to the
        subscription's target_group.

        This method is idempotent:
        - Creates missing AlertInstances for templates in the group
        - Disables AlertInstances whose template was removed from the group
        - Retargets existing subscription-managed instances if target_group changes

        Notes:
        - For wallet AlertGroups, new instances default to enabled when subscription settings provide
          all required (non-targeting) template params (e.g. thresholds).
        - Redis indexing is handled by AlertInstance save signals (targets sync) when instances are enabled.
        """
        from app.models.alerts import AlertInstance
        from app.models.alert_templates import AlertTemplate

        template_ids = cls._extract_template_ids_from_alert_group(subscription.alert_group)

        managed_instances = AlertInstance.objects.filter(
            user=subscription.owner,
            source_subscription=subscription,
        ).select_related('template', 'target_group')

        desired_target_group = getattr(subscription, "target_group", None)
        desired_target_group_id = getattr(subscription, "target_group_id", None)
        desired_target_keys: List[str] = []
        desired_target_label = None

        if desired_target_group_id:
            desired_target_label = desired_target_group.name
        else:
            target_key = getattr(subscription, "target_key", None)
            if target_key:
                desired_target_keys = [target_key]
                desired_target_label = target_key

        def disable_due_to_subscription(alert_instance: AlertInstance) -> None:
            if not alert_instance.enabled:
                return
            alert_instance.enabled = False
            alert_instance.disabled_by_subscription = True
            alert_instance.save(update_fields=['enabled', 'disabled_by_subscription', 'updated_at'])

        if not subscription.is_active:
            for instance in managed_instances:
                disable_due_to_subscription(instance)
            return

        if not template_ids:
            for instance in managed_instances:
                disable_due_to_subscription(instance)
            return

        templates = AlertTemplate.objects.filter(id__in=template_ids)
        templates_by_id = {str(t.id): t for t in templates}

        managed_by_template_id = {
            str(instance.template_id): instance
            for instance in managed_instances
            if instance.template_id is not None
        }

        # Disable instances whose templates were removed from the group
        for template_id, instance in managed_by_template_id.items():
            if template_id not in template_ids:
                disable_due_to_subscription(instance)

        # Ensure existing instances target the current target_group
        for instance in managed_instances:
            if desired_target_group_id:
                if instance.target_group_id != desired_target_group_id or instance.target_keys:
                    instance.target_group = desired_target_group
                    instance.target_keys = []
                    instance.save(update_fields=['target_group', 'target_keys', 'updated_at'])
            else:
                if instance.target_group_id is not None or instance.target_keys != desired_target_keys:
                    instance.target_group = None
                    instance.target_keys = desired_target_keys
                    instance.save(update_fields=['target_group', 'target_keys', 'updated_at'])

        def get_template_params(template: AlertTemplate) -> Dict:
            return cls._build_subscription_template_params(
                template=template,
                subscription_settings=(subscription.settings or {}),
            )

        def get_missing_required(template: AlertTemplate, params: Dict) -> List[str]:
            return cls._missing_required_template_params(template=template, params=params)

        # Update existing instances and create missing ones
        for template_id in template_ids:
            template = templates_by_id.get(template_id)
            if not template:
                logger.warning(
                    f"Subscription {subscription.id} references missing template {template_id}"
                )
                continue

            desired_params = get_template_params(template)
            missing_required = get_missing_required(template, desired_params)

            instance = managed_by_template_id.get(template_id)

            if instance:
                changed_fields: List[str] = []

                if instance.template_params != desired_params:
                    instance.template_params = desired_params
                    changed_fields.append('template_params')

                if missing_required:
                    disable_due_to_subscription(instance)
                else:
                    # If subscription previously disabled this instance (e.g., toggle off, config incomplete),
                    # restore it. If the user disabled it manually, keep it disabled.
                    if instance.disabled_by_subscription:
                        instance.enabled = True
                        instance.disabled_by_subscription = False
                        changed_fields.extend(['enabled', 'disabled_by_subscription'])

                if changed_fields:
                    instance.save(update_fields=[*changed_fields, 'updated_at'])

                continue

            # Create missing instance
            enabled_default = not missing_required
            latest = template.versions.order_by("-template_version").first()
            template_version = int(getattr(latest, "template_version", 1) or 1)

            event_type_map = {
                "wallet": "ACCOUNT_EVENT",
                "token": "ASSET_EVENT",
                "contract": "CONTRACT_INTERACTION",
                "network": "PROTOCOL_EVENT",
                "protocol": "DEFI_EVENT",
                "nft": "ASSET_EVENT",
            }

            AlertInstance.objects.create(
                name=f"{template.name} ({desired_target_label or 'target'})",
                nl_description=str(getattr(template, "description", "") or getattr(template, "name", "") or "").strip(),
                template=template,
                template_version=template_version,
                template_params=desired_params,
                event_type=event_type_map.get(str(template.alert_type), "ACCOUNT_EVENT"),
                sub_event="CUSTOM",
                sub_event_confidence=1.0,
                user=subscription.owner,
                enabled=enabled_default,
                disabled_by_subscription=(not enabled_default and bool(missing_required)),
                alert_type=template.alert_type,
                target_group=desired_target_group,
                target_keys=desired_target_keys,
                source_subscription=subscription,
            )

        logger.info(
            f"Materialized subscription {subscription.id}: "
            f"{len(template_ids)} templates → AlertInstances"
        )

    SUBSCRIPTION_TEMPLATE_PARAMS_KEY = "template_params"
    SUBSCRIPTION_TEMPLATE_PARAMS_BY_TEMPLATE_KEY = "template_params_by_template"

    @classmethod
    def _get_template_variable_id(cls, variable: Dict) -> Optional[str]:
        variable_id = variable.get("id") or variable.get("name")
        if not variable_id or not isinstance(variable_id, str):
            return None
        return variable_id.strip()

    @classmethod
    def _build_subscription_template_params(
        cls,
        *,
        template,
        subscription_settings: Dict,
    ) -> Dict:
        base_params = subscription_settings.get(cls.SUBSCRIPTION_TEMPLATE_PARAMS_KEY, {}) or {}
        params_by_template = subscription_settings.get(cls.SUBSCRIPTION_TEMPLATE_PARAMS_BY_TEMPLATE_KEY, {}) or {}

        if not isinstance(base_params, dict):
            base_params = {}
        if not isinstance(params_by_template, dict):
            params_by_template = {}

        template_id = str(template.id).lower()
        template_specific = params_by_template.get(template_id) or params_by_template.get(str(template.id)) or {}
        if not isinstance(template_specific, dict):
            template_specific = {}

        params: Dict = {**base_params, **template_specific}

        # Fill defaults from template variable definitions.
        for variable in template.get_spec_variables() or []:
            variable_id = cls._get_template_variable_id(variable)
            if not variable_id:
                continue
            if variable_id in params:
                continue
            default_value = variable.get("default")
            if default_value is not None:
                params[variable_id] = default_value

        return params

    @classmethod
    def _missing_required_template_params(cls, *, template, params: Dict) -> List[str]:
        missing: List[str] = []
        targeting_ids = {v.lower() for v in template.get_targeting_variable_names()}
        variables = template.get_spec_variables() or []
        for variable in variables:
            if not isinstance(variable, dict):
                continue
            if not bool(variable.get("required", False)):
                continue

            variable_id = cls._get_template_variable_id(variable)
            if not variable_id:
                continue

            if variable_id.lower() in targeting_ids:
                continue

            if variable_id not in params:
                missing.append(variable_id)

        return missing

    @classmethod
    def materialize_alert_group_subscriptions(cls, alert_group_id: UUID) -> None:
        """Materialize all subscriptions for a given alert group."""
        from app.models.groups import GroupSubscription

        subscriptions = GroupSubscription.objects.filter(
            alert_group_id=alert_group_id,
        ).select_related('alert_group', 'target_group', 'owner')

        for subscription in subscriptions:
            cls.materialize_subscription(subscription)

    @classmethod
    def remove_alert_targets_from_redis(cls, alert_id: str, user_id: Optional[str] = None) -> None:
        """
        Remove alert targets from Redis (wrapper for signal handler).

        Args:
            alert_id: UUID of the alert
            user_id: Optional user ID for user index cleanup
        """
        service = cls()
        service.remove_alert_from_redis(alert_id, user_id)

    # -------------------------------------------------------------------------
    # Group Redis Sync
    # -------------------------------------------------------------------------

    def rebuild_group_redis_cache(self, group_id: UUID) -> None:
        """
        Full rebuild of Redis cache for a group.

        Called from Django signal on group save.

        Stores both Redis SET and JSON array for wasmCloud compatibility
        (wasi:keyvalue doesn't support SMEMBERS).
        """
        from app.models.groups import GenericGroup

        group = GenericGroup.objects.get(id=group_id)
        members = list(group.member_data.get("members", {}).keys())
        previous_members = set(self.redis.smembers(f"group:{group_id}:members"))
        removed_members = previous_members - set(members)

        partitions_index_key = _alert_runtime_group_partitions_index_key(group_id)
        previous_partition_keys = set(self.redis.smembers(partitions_index_key))

        pipe = self.redis.pipeline()

        # Rebuild group members set
        redis_key = f"group:{group_id}:members"
        pipe.delete(redis_key)
        if members:
            pipe.sadd(redis_key, *members)

        # Also store as JSON array for wasmCloud compatibility
        pipe.set(f"group:{group_id}:members:json", json.dumps(members))

        # Clean reverse indexes for removed members (group membership)
        for member_key in removed_members:
            pipe.srem(f"member:{member_key}:groups", str(group_id))
            pipe.srem(_alert_runtime_target_groups_key(member_key), str(group_id))

        # Rebuild reverse indexes for current members
        for member_key in members:
            pipe.sadd(f"member:{member_key}:groups", str(group_id))
            pipe.sadd(_alert_runtime_target_groups_key(member_key), str(group_id))

        # Rebuild per-partition member sets for scheduler partitioning
        for partition_key in previous_partition_keys:
            pipe.delete(partition_key)
        pipe.delete(partitions_index_key)

        partition_set_keys: set[str] = set()
        for member_key in members:
            if not isinstance(member_key, str):
                continue
            parts = [p.strip() for p in member_key.split(":")]
            if len(parts) < 2:
                continue
            network, subnet = parts[0], parts[1].lower()
            partition_set_key = _alert_runtime_group_partition_set_key(group_id, network, subnet)
            partition_set_keys.add(partition_set_key)
            pipe.sadd(partition_set_key, member_key)

        if partition_set_keys:
            pipe.sadd(partitions_index_key, *sorted(partition_set_keys))

        # Update type index
        pipe.sadd(f"groups:type:{group.group_type}", str(group_id))

        # Update owner index
        pipe.sadd(f"groups:owner:{group.owner_id}", str(group_id))

        pipe.execute()
        logger.info(f"Rebuilt Redis cache for group {group_id}")

    def remove_group_from_redis(self, group_id: UUID, group_type: str, owner_id: int) -> None:
        """
        Remove group data from Redis on deletion.

        Args:
            group_id: UUID of the group
            group_type: Group type for type index cleanup
            owner_id: Owner ID for owner index cleanup
        """
        pipe = self.redis.pipeline()

        # Get members before deleting
        members = self.redis.smembers(f"group:{group_id}:members")
        partitions_index_key = _alert_runtime_group_partitions_index_key(group_id)
        partition_keys = self.redis.smembers(partitions_index_key)

        # Remove from reverse indexes
        for member_key in members:
            pipe.srem(f"member:{member_key}:groups", str(group_id))
            pipe.srem(_alert_runtime_target_groups_key(member_key), str(group_id))

        # Remove group members (SET + JSON versions)
        pipe.delete(f"group:{group_id}:members")
        pipe.delete(f"group:{group_id}:members:json")

        # Remove alert runtime partition sets
        for partition_key in partition_keys:
            pipe.delete(partition_key)
        pipe.delete(partitions_index_key)

        # Remove from type index
        pipe.srem(f"groups:type:{group_type}", str(group_id))

        # Remove from owner index
        pipe.srem(f"groups:owner:{owner_id}", str(group_id))

        pipe.execute()
        logger.info(f"Removed group {group_id} from Redis cache")

    # -------------------------------------------------------------------------
    # Reconciliation (run periodically to fix drift)
    # -------------------------------------------------------------------------

    def reconcile_group(self, group_id: UUID) -> Dict[str, int]:
        """
        Reconcile PostgreSQL and Redis for a single group.

        Fixes any drift between the two data stores.

        Returns:
            Dict with stats: {"added": N, "removed": M}
        """
        from app.models.groups import GenericGroup

        group = GenericGroup.objects.get(id=group_id)
        pg_members = set(group.member_data.get('members', {}).keys())
        redis_members = self.redis.smembers(f"group:{group_id}:members")

        stats = {"added": 0, "removed": 0}

        # Fix missing in Redis
        for key in pg_members - redis_members:
            self.redis.sadd(f"group:{group_id}:members", key)
            self.redis.sadd(f"member:{key}:groups", str(group_id))
            stats["added"] += 1

        # Fix orphaned in Redis
        for key in redis_members - pg_members:
            self.redis.srem(f"group:{group_id}:members", key)
            self.redis.srem(f"member:{key}:groups", str(group_id))
            stats["removed"] += 1

        if stats["added"] or stats["removed"]:
            logger.warning(f"Reconciled group {group_id}: {stats}")

        return stats

    def reconcile_all_groups(self) -> Dict[str, int]:
        """
        Reconcile all groups (run every 5 minutes via Celery beat).

        Returns:
            Aggregate stats
        """
        from app.models.groups import GenericGroup

        total_stats = {"groups": 0, "added": 0, "removed": 0}

        for group in GenericGroup.objects.all():
            stats = self.reconcile_group(group.id)
            total_stats["groups"] += 1
            total_stats["added"] += stats["added"]
            total_stats["removed"] += stats["removed"]

        logger.info(f"Reconciliation complete: {total_stats}")
        return total_stats

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _sync_members_to_redis(
        self,
        group_id: UUID,
        member_keys: List[str],
        add: bool = True
    ) -> None:
        """
        Sync member changes to Redis.

        Updates both SET and JSON array versions for wasmCloud compatibility.
        """
        pipe = self.redis.pipeline()
        group_key = f"group:{group_id}:members"

        if add:
            if member_keys:
                pipe.sadd(group_key, *member_keys)
            for key in member_keys:
                pipe.sadd(f"member:{key}:groups", str(group_id))
        else:
            if member_keys:
                pipe.srem(group_key, *member_keys)
            for key in member_keys:
                pipe.srem(f"member:{key}:groups", str(group_id))

        pipe.execute()

        # Update JSON array version for wasmCloud compatibility
        self._update_group_members_json(group_id)

    def _update_group_members_json(self, group_id: UUID) -> None:
        """
        Update JSON array version of group members for wasmCloud compatibility.

        wasmCloud uses wasi:keyvalue which doesn't support Redis SMEMBERS,
        so we maintain a parallel JSON array.

        Args:
            group_id: UUID of the group
        """
        json_key = f"group:{group_id}:members:json"
        try:
            # Read current members from the SET
            members = list(self.redis.smembers(f"group:{group_id}:members"))
            # Store as JSON array
            self.redis.set(json_key, json.dumps(members))
        except Exception as e:
            logger.warning(f"Failed to update group members JSON for {group_id}: {e}")

    def _get_alert_target_keys(self, alert_instance) -> Set[str]:
        """
        Extract target wallet keys from AlertInstance.

        Sources:
        1. target_keys: Explicit keys (preferred, mutually exclusive with target_group)
        2. target_group: Get all members from linked GenericGroup
        """
        from app.models.groups import (
            AlertType,
            normalize_network_subnet_address_key,
            normalize_network_subnet_address_token_id_key,
            normalize_network_subnet_key,
            normalize_network_subnet_protocol_key,
        )

        target_keys: Set[str] = set()

        # Source 1: explicit target_keys (preferred)
        explicit_keys = getattr(alert_instance, 'target_keys', None) or []
        if explicit_keys:
            for key in explicit_keys:
                if not isinstance(key, str) or not key.strip():
                    continue
                key = key.strip()
                alert_type = getattr(alert_instance, 'alert_type', None)
                if alert_type == AlertType.NETWORK:
                    target_keys.add(normalize_network_subnet_key(key))
                elif alert_type == AlertType.PROTOCOL:
                    target_keys.add(normalize_network_subnet_protocol_key(key))
                elif alert_type == AlertType.NFT:
                    raw = key
                    if raw.count(":") >= 3:
                        target_keys.add(normalize_network_subnet_address_token_id_key(raw))
                    else:
                        target_keys.add(normalize_network_subnet_address_key(raw))
                else:
                    target_keys.add(normalize_network_subnet_address_key(key))
            return target_keys

        # Source 1: target_group (if using group-level alerts)
        if hasattr(alert_instance, 'target_group') and alert_instance.target_group:
            group = alert_instance.target_group
            members = group.member_data.get('members', {})
            for key in members.keys():
                target_keys.add(group.normalize_member_key(key))

        return target_keys

    @staticmethod
    def _extract_template_ids_from_alert_group(alert_group) -> Set[str]:
        members = (alert_group.member_data or {}).get('members', {})
        template_ids: Set[str] = set()
        for key in members.keys():
            key = str(key)
            if key.lower().startswith('template:'):
                template_id = key.split(':', 1)[1].strip()
                if template_id:
                    template_ids.add(template_id.lower())
        return template_ids

    def _update_wallet_alerts_json(self, wallet_key: str, alert_id: str, add: bool = True) -> None:
        """
        Update JSON array version of wallet→alerts for wasmCloud compatibility.

        wasmCloud uses wasi:keyvalue which doesn't support Redis SMEMBERS,
        so we maintain a parallel JSON array for O(1) lookups.

        Args:
            wallet_key: Wallet key (e.g., "ETH:mainnet:0x123")
            alert_id: Alert UUID
            add: True to add, False to remove
        """
        json_key = f"wallet:{wallet_key}:alerts:json"
        try:
            # Get current array
            current = self.redis.get(json_key)
            alerts = json.loads(current) if current else []

            if add and alert_id not in alerts:
                alerts.append(alert_id)
            elif not add and alert_id in alerts:
                alerts.remove(alert_id)

            # Store updated array
            self.redis.set(json_key, json.dumps(alerts))
        except Exception as e:
            logger.warning(f"Failed to update wallet alerts JSON for {wallet_key}: {e}")

class AlertValidationService:
    """
    Validates alert targets match alert type.

    Key format patterns per alert type:
    - wallet: {NETWORK}:{subnet}:{address}
    - network: {NETWORK}:{subnet}
    - protocol: {NETWORK}:{subnet}:{protocol}
    - token: {NETWORK}:{subnet}:{contract_address}
    - nft: {NETWORK}:{subnet}:{collection_address} OR {NETWORK}:{subnet}:{collection_address}:{token_id}
    """

    # Key format patterns per alert type
    KEY_PATTERNS = {
        'wallet': r'^[A-Z]+:[a-z0-9\-]+:(0x[a-fA-F0-9]+|[a-zA-Z0-9]+)$',  # ETH:mainnet:0x123 or SOL:mainnet:5yBb
        'network': r'^[A-Z]+:[a-z0-9\-]+$',                                 # ETH:mainnet
        'protocol': r'^[A-Z]+:[a-z0-9\-]+:[a-z0-9][a-z0-9\-_\.]*$',         # ETH:mainnet:aave
        'token': r'^[A-Z]+:[a-z0-9\-]+:(0x[a-fA-F0-9]+|[a-zA-Z0-9]+)$',    # ETH:mainnet:0xUSDC
        'contract': r'^[A-Z]+:[a-z0-9\-]+:(0x[a-fA-F0-9]+|[a-zA-Z0-9]+)$', # ETH:mainnet:0xContract
        # NFT keys may optionally include a token_id segment. token_id accepts any string.
        'nft': r'^[A-Z]+:[a-z0-9\-]+:(0x[a-fA-F0-9]+|[a-zA-Z0-9]+)(:.+)?$',  # ETH:mainnet:0xCollection[:token_id]
    }

    @classmethod
    def validate_targets(cls, alert_type: str, targets: List[str]) -> None:
        """
        Validate individual target keys match alert type format.

        Args:
            alert_type: Type of alert ('wallet', 'network', 'token')
            targets: List of target keys to validate

        Raises:
            ValidationError: If any target doesn't match expected format
        """
        pattern = cls.KEY_PATTERNS.get(alert_type)
        if not pattern:
            raise ValueError(f"Unknown alert type: {alert_type}")

        for target in targets:
            if not re.match(pattern, target):
                raise ValidationError(
                    f"Target '{target}' does not match expected format "
                    f"for alert type '{alert_type}'"
                )

    @classmethod
    def validate_alert_instance(cls, instance) -> None:
        """
        Full validation of AlertInstance targets.

        Validates:
        1. target_group type matches alert_type
        2. Individual targets in spec match alert_type format

        Args:
            instance: AlertInstance model instance

        Raises:
            ValidationError: If validation fails
        """
        from app.models.groups import ALERT_TYPE_TO_GROUP_TYPE, AlertType

        # Get alert_type (from new field or infer from spec)
        alert_type = getattr(instance, 'alert_type', None)
        if not alert_type:
            # Default to wallet for backward compatibility
            alert_type = AlertType.WALLET

        # Validate target_group if present
        if hasattr(instance, 'target_group') and instance.target_group:
            valid_types = ALERT_TYPE_TO_GROUP_TYPE.get(alert_type, [])
            if instance.target_group.group_type not in valid_types:
                raise ValidationError({
                    'target_group': f"Group type '{instance.target_group.group_type}' "
                                    f"not valid for alert type '{alert_type}'. "
                                    f"Expected: {valid_types}"
                })

        # Validate individual targets in spec
        spec = instance.spec or {}
        targets = spec.get('targets', [])
        if targets:
            cls.validate_targets(alert_type, targets)

        # Validate wallet key if present
        wallet = spec.get('wallet')
        if wallet:
            cls.validate_targets(alert_type, [wallet])
