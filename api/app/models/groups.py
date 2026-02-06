"""
Unified Group Model - GenericGroup with JSONB member storage

This module implements a unified group model that consolidates all group types
(wallet, alert, user, network, token, contract, NFT) into a single model with
PostgreSQL JSONB member storage.

Architecture:
- GenericGroup: Single model for all group types with JSONB member storage
- GroupSubscription: Links object groups to alert groups
- Redis Projection: Django signals sync to Redis for wasmCloud O(1) lookups

See PRD: /docs/prd/apps/api/PRD-Unified-Group-Model-USDT.md
"""

import inspect
import uuid
import logging
from typing import List, Dict, Optional, Set
from django.db import models, transaction
from django.db.models import F
from django.contrib.auth import get_user_model
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


def _build_check_constraint(condition: models.Q, name: str) -> models.CheckConstraint:
    params = inspect.signature(models.CheckConstraint).parameters
    if "condition" in params:
        return models.CheckConstraint(condition=condition, name=name)
    return models.CheckConstraint(check=condition, name=name)


class GroupType(models.TextChoices):
    """
    Extensible group type enumeration.

    Adding new types requires only:
    1. Add enum value here (no migration needed for TextChoices)
    2. Define member key format in GroupService
    3. Implement type-specific validation if needed
    """
    WALLET = 'wallet', 'Wallet Group'
    ALERT = 'alert', 'Alert Group'
    USER = 'user', 'User Group'
    NETWORK = 'network', 'Network Group'      # For network alerts
    PROTOCOL = 'protocol', 'Protocol Group'   # For application protocols (e.g. Aave, Uniswap) scoped to a network
    TOKEN = 'token', 'Token Group'            # For token alerts
    CONTRACT = 'contract', 'Contract Group'   # For contract alerts -  a group can be tied to an entity
    NFT = 'nft', 'NFT Collection Group'       # for contract alerts that are also nfts


class AlertType(models.TextChoices):
    """
    Alert type enumeration - determines valid target types.

    Each alert type accepts specific target types:
    - wallet: Wallet addresses, Wallet Groups
    - network: Network IDs, Network Groups
    - protocol: Application Protocol IDs (e.g. Aave), Protocol Groups
    - token: Token addresses, Token Groups
    - contract: Contract addresses, Contract Groups
    - nft: NFT collections, NFT Groups
    """
    WALLET = 'wallet', 'Wallet Alert'
    NETWORK = 'network', 'Network Alert'
    PROTOCOL = 'protocol', 'Protocol Alert'
    TOKEN = 'token', 'Token Alert'
    CONTRACT = 'contract', 'Contract Alert'
    NFT = 'nft', 'NFT Alert'


# Mapping: alert_type → valid group_type(s)
ALERT_TYPE_TO_GROUP_TYPE = {
    AlertType.WALLET: [GroupType.WALLET],
    AlertType.NETWORK: [GroupType.NETWORK],
    AlertType.PROTOCOL: [GroupType.PROTOCOL],
    AlertType.TOKEN: [GroupType.TOKEN],
    AlertType.CONTRACT: [GroupType.CONTRACT],
    AlertType.NFT: [GroupType.NFT, GroupType.CONTRACT],
}


SYSTEM_GROUP_ACCOUNTS = "accounts"


def normalize_network_subnet_key(raw_key: str) -> str:
    """
    Normalize a network/subnet key to a canonical form.

    Canonical form:
      - network segment: UPPERCASE (e.g., ETH, SOL)
      - subnet segment: lowercase (e.g., mainnet, testnet)

    Example:
      - "eth:MainNet" -> "ETH:mainnet"
    """
    key = raw_key.strip()
    parts = [p.strip() for p in key.split(":")]
    if len(parts) != 2:
        return key

    network, subnet = parts[0].upper(), parts[1].lower()
    if not network or not subnet:
        return key

    return f"{network}:{subnet}"


def normalize_network_subnet_address_key(raw_key: str) -> str:
    """
    Normalize a network/subnet/address key to a canonical form.

    Canonical form:
      - network segment: UPPERCASE (e.g., ETH, SOL)
      - subnet segment: lowercase (e.g., mainnet, testnet)
      - address segment:
          - EVM addresses (0x...) are lowercased to prevent duplicates
          - non-EVM addresses preserve case (e.g., Solana base58)

    Examples:
      - "eth:MainNet:0xAbc" -> "ETH:mainnet:0xabc"
      - "SOL:mainnet:5yBb..." -> "SOL:mainnet:5yBb..." (unchanged address case)
    """
    key = raw_key.strip()
    parts = [p.strip() for p in key.split(":")]
    if len(parts) != 3:
        return key

    network, subnet, address = parts[0].upper(), parts[1].lower(), parts[2]
    if not network or not subnet or not address:
        return key

    if address.lower().startswith("0x"):
        address = address.lower()
    return f"{network}:{subnet}:{address}"


def normalize_network_subnet_address_token_id_key(raw_key: str) -> str:
    """
    Normalize a network/subnet/address/token_id key to a canonical form.

    Canonical form:
      - network segment: UPPERCASE (e.g., ETH, SOL)
      - subnet segment: lowercase (e.g., mainnet, testnet)
      - address segment:
          - EVM addresses (0x...) are lowercased to prevent duplicates
          - non-EVM addresses preserve case (e.g., Solana base58)
      - token_id segment: preserved as-is (after stripping); accepts any string

    Notes:
      - token_id may contain ":" characters; everything after the 3rd ":" is treated as token_id.

    Examples:
      - "eth:MainNet:0xAbc:123" -> "ETH:mainnet:0xabc:123"
      - "ETH:mainnet:0xAbc:MyToken" -> "ETH:mainnet:0xabc:MyToken"
      - "ETH:mainnet:0xAbc:foo:bar" -> "ETH:mainnet:0xabc:foo:bar"
    """
    key = raw_key.strip()
    parts = key.split(":", 3)
    if len(parts) < 4:
        return key

    network, subnet, address, token_id = [p.strip() for p in parts]
    if address.lower().startswith("0x"):
        address = address.lower()

    return f"{network.upper()}:{subnet.lower()}:{address}:{token_id}"


def normalize_network_subnet_protocol_key(raw_key: str) -> str:
    """
    Normalize a network/subnet/protocol key to a canonical form.

    Canonical form:
      - network segment: UPPERCASE (e.g., ETH, SOL)
      - subnet segment: lowercase (e.g., mainnet, testnet)
      - protocol segment: lowercase slug/id (e.g., aave, uniswap-v3)

    Examples:
      - "eth:MainNet:Aave" -> "ETH:mainnet:aave"
      - "ETH:mainnet:uniswap-v3" -> "ETH:mainnet:uniswap-v3"
    """
    key = raw_key.strip()
    parts = [p.strip() for p in key.split(":")]
    if len(parts) != 3:
        return key

    network, subnet, protocol = parts[0].upper(), parts[1].lower(), parts[2].strip().lower()
    if not network or not subnet or not protocol:
        return key

    return f"{network}:{subnet}:{protocol}"


class GenericGroup(models.Model):
    """
    Unified group model for all object types.

    Stores members in JSONB format for flexibility and performance:
    - Supports bulk operations (10K+ members/second)
    - GIN index for efficient containment queries
    - No migrations needed for new member metadata

    Member Key Formats:
    - Wallet: {network}:{subnet}:{address} (e.g., ETH:mainnet:0x123...)
    - Network: {network}:{subnet} (e.g., ETH:mainnet)
    - Protocol: {network}:{subnet}:{protocol} (e.g., ETH:mainnet:aave)
    - Token: {network}:{subnet}:{contract} (e.g., ETH:mainnet:0xUSDC...)
    - AlertTemplate: template:{uuid}
    - User: user:{uuid}

    JSONB Schema:
    {
        "members": {
            "ETH:mainnet:0x123...": {
                "added_at": "2025-01-15T10:00:00Z",
                "added_by": "user-uuid",
                "label": "Treasury",
                "tags": ["defi", "hot-wallet"],
                "metadata": {...}
            }
        }
    }
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_type = models.CharField(max_length=20, choices=GroupType.choices)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')

    # Ownership
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_groups'
    )

    # Settings per group type (notifications, filters, etc.)
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Group-specific settings: {'is_default': true, 'network_filter': 'mainnet'}"
    )

    # Member storage - JSONB with member keys
    member_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Format: {"members": {"key1": {metadata}, "key2": {metadata}}}'
    )

    # Denormalized count for quick access (kept in sync by service layer)
    member_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'generic_groups'
        verbose_name = 'Generic Group'
        verbose_name_plural = 'Generic Groups'
        indexes = [
            models.Index(fields=['group_type', 'owner']),
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['group_type', 'created_at']),
            GinIndex(fields=['member_data'], name='generic_group_member_gin'),
        ]

    def __str__(self):
        return f"{self.get_group_type_display()}: {self.name} ({self.member_count} members)"

    # -------------------------------------------------------------------------
    # Settings Validation
    # -------------------------------------------------------------------------

    VALID_VISIBILITY_VALUES = {'private', 'public'}

    def validate_settings(self):
        """
        Validate settings based on group_type.

        Common settings (all group types):
        - visibility: 'private'|'public' (optional, defaults to 'private')

        WalletGroup settings:
        - system_key: 'accounts' for the per-user Accounts group (server-managed)

        AlertGroup settings:
        - alert_type: 'wallet'|'network'|'protocol'|'token'|'contract'|'nft' (REQUIRED for AlertGroups)
        """
        if not self.settings:
            self.settings = {}

        # AlertGroup: settings.alert_type is REQUIRED
        if self.group_type == GroupType.ALERT:
            alert_type = self.settings.get('alert_type')
            if not alert_type:
                raise ValidationError({
                    'settings': "AlertGroups require 'alert_type' in settings "
                               f"(one of: {', '.join(at.value for at in AlertType)})"
                })
            if alert_type not in [at.value for at in AlertType]:
                raise ValidationError({
                    'settings': f"Invalid alert_type '{alert_type}'. "
                               f"Must be one of: {', '.join(at.value for at in AlertType)}"
                })

        # WalletGroup: validate visibility if provided
        # Visibility: allowed on ALL group types (public ⇒ subscribable/discoverable).
        # Accounts group is always private.
        if self.settings.get('system_key') == SYSTEM_GROUP_ACCOUNTS:
            self.settings['visibility'] = 'private'

        visibility = self.settings.get('visibility')
        if visibility and visibility not in self.VALID_VISIBILITY_VALUES:
            raise ValidationError({
                'settings': f"Invalid visibility '{visibility}'. "
                           f"Must be one of: {', '.join(self.VALID_VISIBILITY_VALUES)}"
            })

    def get_alert_type(self) -> Optional[str]:
        """Get the alert_type from settings (for AlertGroups only)."""
        if self.group_type == GroupType.ALERT:
            return self.settings.get('alert_type')
        return None

    def get_visibility(self) -> str:
        """Get visibility setting (defaults to 'private')."""
        return self.settings.get('visibility', 'private')

    def is_public(self) -> bool:
        """Check if group is publicly visible."""
        return self.get_visibility() == 'public'

    def allows_subscriptions(self) -> bool:
        """Public groups are subscribable."""
        return self.is_public()

    def validate_alert_group_members(self, member_keys: List[str]) -> None:
        """Validate member keys for AlertGroups.

        AlertGroups store template members in `template:{uuid}` format and enforce that
        all referenced templates share the same `alert_type` as
        `self.settings['alert_type']`.

        For vNext, the template alert_type is derived from `AlertTemplate.target_kind`.
        """

        if self.group_type != GroupType.ALERT:
            return  # Only validate for AlertGroups

        alert_type = self.settings.get('alert_type')
        if not alert_type:
            raise ValidationError({'settings': "AlertGroup missing required 'alert_type' in settings"})

        # Import here to avoid circular imports.
        from .alert_templates import AlertTemplate

        invalid_members = []

        existing_members = (self.member_data or {}).get('members', {}) or {}
        existing_template_ids = {
            str(k).split(':', 1)[1].strip().lower()
            for k in existing_members.keys()
            if str(k).lower().startswith('template:')
        }

        incoming_template_ids: Set[str] = set()
        for key in member_keys:
            if not str(key).lower().startswith('template:'):
                invalid_members.append((key, f"Must be in format 'template:{{uuid}}', got '{key}'"))
                continue
            template_id = str(key).split(':', 1)[1].strip()
            if not template_id:
                invalid_members.append((key, 'Template id cannot be empty'))
                continue
            incoming_template_ids.add(template_id.lower())

        all_template_ids = existing_template_ids | incoming_template_ids
        templates = AlertTemplate.objects.filter(id__in=all_template_ids)
        templates_by_id = {str(t.id).lower(): t for t in templates}

        for key in member_keys:
            if not str(key).lower().startswith('template:'):
                continue
            template_id = str(key).split(':', 1)[1].strip().lower()
            template = templates_by_id.get(template_id)
            if not template:
                invalid_members.append((key, 'AlertTemplate not found'))
                continue

            template_kind = str(getattr(template, 'target_kind', '') or '').strip().lower()
            if template_kind != str(alert_type).strip().lower():
                invalid_members.append(
                    (
                        key,
                        f"Template target_kind '{template_kind}' doesn't match AlertGroup alert_type '{alert_type}'",
                    )
                )

        # Enforce AlertGroup homogeneity beyond target_kind:
        # - all templates must share the same derived template_type (legacy: event_type category)
        # - all templates must share the same required (non-targeting) variable id set
        if templates_by_id:
            template_types: set[str] = set()
            required_sets: set[frozenset[str]] = set()

            for template in templates_by_id.values():
                try:
                    template_types.add(str(template.get_template_type() or "").strip().lower())
                except Exception:
                    template_types.add(str(getattr(template, "target_kind", "wallet") or "wallet").strip().lower())

                targeting = {n.lower() for n in getattr(template, "get_targeting_variable_names", lambda: [])() or []}
                required: set[str] = set()
                for var in getattr(template, "get_spec_variables", lambda: [])() or []:
                    if not isinstance(var, dict):
                        continue
                    if not bool(var.get("required", False)):
                        continue
                    var_id = var.get("id") or var.get("name")
                    if not isinstance(var_id, str) or not var_id.strip():
                        continue
                    if var_id.strip().lower() in targeting:
                        continue
                    required.add(var_id.strip().lower())
                required_sets.add(frozenset(sorted(required)))

            if len(template_types) > 1:
                invalid_members.append((
                    "template_type",
                    f"AlertGroup templates must share the same template_type, got: {sorted(t for t in template_types if t)}",
                ))

            if len(required_sets) > 1:
                invalid_members.append((
                    "variables",
                    "AlertGroup templates must share the same required (non-targeting) variable set",
                ))

        if invalid_members:
            error_messages = [f"{key}: {error}" for key, error in invalid_members]
            raise ValidationError({'members': error_messages})
    def clean(self):
        """Validate the model before saving."""
        super().clean()
        self.validate_settings()

    def save(self, *args, **kwargs):
        # Validate settings before save
        self.validate_settings()

        # Ensure member_data has correct structure
        if not self.member_data:
            self.member_data = {'members': {}}
        elif 'members' not in self.member_data:
            self.member_data['members'] = {}

        # Keep member_count in sync
        self.member_count = len(self.member_data.get('members', {}))

        super().save(*args, **kwargs)

    # -------------------------------------------------------------------------
    # Member Operations (use GroupService for full functionality with Redis sync)
    # -------------------------------------------------------------------------

    def get_member_keys(self) -> List[str]:
        """Get list of all member keys in this group."""
        return list(self.member_data.get('members', {}).keys())

    def normalize_member_key(self, member_key: str) -> str:
        """
        Normalize a member key to the canonical form for this group's type.

        Notes:
        - Wallet/token/contract group keys normalize EVM `0x...` addresses to lowercase.
        - Network keys normalize to `{NETWORK}:{subnet}`.
        - Alert groups store template members in `template:{uuid}` format.
        """
        key = member_key.strip()

        if self.group_type == GroupType.ALERT:
            lowered = key.lower()
            if lowered.startswith("template:"):
                template_id = key.split(":", 1)[1].strip()
                return f"template:{template_id.lower()}"
            return key

        if self.group_type == GroupType.NETWORK:
            return normalize_network_subnet_key(key)

        if self.group_type == GroupType.PROTOCOL:
            return normalize_network_subnet_protocol_key(key)

        if self.group_type == GroupType.NFT:
            if key.count(":") >= 3:
                return normalize_network_subnet_address_token_id_key(key)
            return normalize_network_subnet_address_key(key)

        if self.group_type in {GroupType.WALLET, GroupType.TOKEN, GroupType.CONTRACT}:
            return normalize_network_subnet_address_key(key)

        return key

    def has_member(self, member_key: str) -> bool:
        """Check if member exists in group (PostgreSQL-only, no Redis)."""
        normalized_key = self.normalize_member_key(member_key)
        return normalized_key in self.member_data.get('members', {})

    def get_member_metadata(self, member_key: str) -> Optional[Dict]:
        """Get metadata for a specific member."""
        normalized_key = self.normalize_member_key(member_key)
        return self.member_data.get('members', {}).get(normalized_key)

    def add_member_local(
        self,
        member_key: str,
        added_by: Optional[str] = None,
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add a member to the group (PostgreSQL only, no Redis sync).
        Use GroupService.add_members() for full functionality with Redis.

        Returns:
            True if member was added, False if already exists
        """
        members = self.member_data.get('members', {})
        normalized_key = self.normalize_member_key(member_key)
        if normalized_key in members:
            return False

        effective_metadata = metadata or {}
        if self.group_type == GroupType.WALLET and self.settings.get("system_key") == SYSTEM_GROUP_ACCOUNTS:
            effective_metadata = {
                "owner_verified": bool(effective_metadata.get("owner_verified", False)),
                **effective_metadata,
            }

        members[normalized_key] = {
            'added_at': timezone.now().isoformat(),
            'added_by': added_by or '',
            'label': label or '',
            'tags': tags or [],
            'metadata': effective_metadata
        }

        self.member_data['members'] = members
        self.member_count = len(members)
        self.save(update_fields=['member_data', 'member_count', 'updated_at'])
        return True

    def remove_member_local(self, member_key: str) -> bool:
        """
        Remove a member from the group (PostgreSQL only, no Redis sync).
        Use GroupService.remove_members() for full functionality with Redis.

        Returns:
            True if member was removed, False if not found
        """
        members = self.member_data.get('members', {})
        normalized_key = self.normalize_member_key(member_key)
        if normalized_key not in members:
            return False

        del members[normalized_key]
        self.member_data['members'] = members
        self.member_count = len(members)
        self.save(update_fields=['member_data', 'member_count', 'updated_at'])
        return True

    # -------------------------------------------------------------------------
    # Accounts Group Factory
    # -------------------------------------------------------------------------

    @classmethod
    def create_accounts_group(cls, user: User) -> 'GenericGroup':
        """
        Create the Accounts group for a user.

        The Accounts group is a private, user-owned wallet group representing wallets
        the user claims to own. It is created lazily when the user adds their first wallet.
        """
        return cls.objects.create(
            group_type=GroupType.WALLET,
            name='Accounts',
            description='Wallets you own (accounts)',
            owner=user,
            settings={'system_key': SYSTEM_GROUP_ACCOUNTS, 'visibility': 'private'},
            member_data={'members': {}},
            member_count=0,
        )

    @classmethod
    def get_or_create_accounts_group(cls, user: User) -> 'GenericGroup':
        """Get user's Accounts group, creating if needed."""
        existing = cls.objects.filter(
            owner=user,
            group_type=GroupType.WALLET,
            settings__system_key=SYSTEM_GROUP_ACCOUNTS,
        ).first()
        if existing:
            return existing

        # Backward-compatible fallback for legacy default groups using settings.is_default
        legacy = cls.objects.filter(
            owner=user,
            group_type=GroupType.WALLET,
            settings__is_default=True,
        ).first()
        if legacy:
            legacy.settings = {
                **(legacy.settings or {}),
                'system_key': SYSTEM_GROUP_ACCOUNTS,
                'visibility': (legacy.settings or {}).get('visibility', 'private'),
            }
            legacy.save(update_fields=['settings', 'updated_at'])
            return legacy

        return cls.create_accounts_group(user)


class GroupSubscription(models.Model):
    """
    Links an object group (wallets, contracts, etc.) to an alert group.

    This model enables group-to-group bindings where:
    - alert_group: A GenericGroup of type ALERT containing AlertTemplates
    - target_group: A GenericGroup of any type (WALLET, NETWORK, TOKEN, etc.)

    The subscription means "apply all templates in alert_group to all targets in target_group"
    by cloning AlertInstances per subscriber.

    Settings Override Example:
    {
        "notification_channels": ["webhook", "email"],
        "cooldown_minutes": 15,
        "severity_filter": ["high", "critical"]
    }
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Alert group being subscribed to (must be type ALERT)
    alert_group = models.ForeignKey(
        GenericGroup,
        on_delete=models.CASCADE,
        related_name='alert_subscriptions',
        limit_choices_to={'group_type': GroupType.ALERT}
    )

    # Target group (wallets, networks, tokens, etc.) OR a single target key (wallet/network/token/etc.)
    # Exactly one of target_group or target_key must be provided.
    target_group = models.ForeignKey(
        GenericGroup,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subscribed_to_alerts'
    )
    target_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Optional single target key (e.g., 'ETH:mainnet:0x123...') when not targeting a group"
    )

    # User who created the subscription
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='group_subscriptions'
    )

    # Override settings for this subscription
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Override settings for alerts in this subscription"
    )

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'group_subscriptions'
        verbose_name = 'Group Subscription'
        verbose_name_plural = 'Group Subscriptions'
        constraints = [
            _build_check_constraint(
                (
                    (models.Q(target_group__isnull=False) & models.Q(target_key__isnull=True)) |
                    (models.Q(target_group__isnull=True) & models.Q(target_key__isnull=False))
                ),
                'groupsubscription_exactly_one_target',
            ),
            _build_check_constraint(
                models.Q(target_key__isnull=True) | ~models.Q(target_key=""),
                'groupsubscription_target_key_not_blank',
            ),
            models.UniqueConstraint(
                fields=['owner', 'alert_group', 'target_group'],
                condition=models.Q(target_group__isnull=False),
                name='unique_groupsubscription_owner_alert_group_target_group',
            ),
            models.UniqueConstraint(
                fields=['owner', 'alert_group', 'target_key'],
                condition=models.Q(target_key__isnull=False),
                name='unique_groupsubscription_owner_alert_group_target_key',
            ),
        ]
        indexes = [
            models.Index(fields=['alert_group', 'is_active']),
            models.Index(fields=['target_group', 'is_active']),
            models.Index(fields=['owner', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        target = self.target_group.name if self.target_group else (self.target_key or "<missing target>")
        return f"{self.alert_group.name} → {target}"

    def clean(self):
        """Validate subscription constraints."""
        super().clean()

        if self.target_key is not None:
            self.target_key = self.target_key.strip() or None

        # Alert group must be of type ALERT
        if self.alert_group and self.alert_group.group_type != GroupType.ALERT:
            raise ValidationError({
                'alert_group': f"Alert group must be of type '{GroupType.ALERT}', "
                               f"got '{self.alert_group.group_type}'"
            })

        if bool(self.target_group) == bool(self.target_key):
            raise ValidationError({
                'target_group': "Provide exactly one of target_group or target_key",
                'target_key': "Provide exactly one of target_group or target_key",
            })

        # Target group cannot be the same as alert group
        if self.alert_group_id and self.target_group_id:
            if self.alert_group_id == self.target_group_id:
                raise ValidationError({
                    'target_group': "Target group cannot be the same as alert group"
                })

        # AlertGroup.settings.alert_type must match target_group.group_type
        # This enforces homogeneous alert group bindings:
        # - wallet AlertGroup → wallet target_group only
        # - network AlertGroup → network target_group only
        # - token AlertGroup → token target_group only
        if self.alert_group and self.target_group:
            from app.services.group_service import GroupService
            from app.models.alert_templates import AlertTemplate

            alert_type_setting = self.alert_group.get_alert_type()
            template_ids = GroupService._extract_template_ids_from_alert_group(self.alert_group)

            derived_target_type: Optional[str] = None
            if template_ids:
                templates = AlertTemplate.objects.filter(id__in=template_ids)
                derived_types = {t.get_target_alert_type() for t in templates}
                if len(derived_types) != 1:
                    raise ValidationError({
                        'alert_group': "AlertGroup templates must share the same target type"
                    })
                derived_target_type = next(iter(derived_types))

            effective_alert_type = derived_target_type or alert_type_setting or AlertType.WALLET

            if alert_type_setting and derived_target_type and alert_type_setting != derived_target_type:
                raise ValidationError({
                    'alert_group': (
                        f"AlertGroup alert_type '{alert_type_setting}' does not match "
                        f"derived template target type '{derived_target_type}'"
                    )
                })

            valid_group_types = ALERT_TYPE_TO_GROUP_TYPE.get(effective_alert_type, [])
            if self.target_group.group_type not in valid_group_types:
                raise ValidationError({
                    'target_group': f"AlertGroup with alert_type='{effective_alert_type}' can only "
                                   f"be applied to groups of type {valid_group_types}, "
                                   f"got '{self.target_group.group_type}'"
                })

        if self.alert_group and self.target_key:
            from app.services.group_service import AlertValidationService

            from app.services.group_service import GroupService
            from app.models.alert_templates import AlertTemplate

            alert_type_setting = self.alert_group.get_alert_type()
            template_ids = GroupService._extract_template_ids_from_alert_group(self.alert_group)

            derived_target_type: Optional[str] = None
            if template_ids:
                templates = AlertTemplate.objects.filter(id__in=template_ids)
                derived_types = {t.get_target_alert_type() for t in templates}
                if len(derived_types) != 1:
                    raise ValidationError({
                        'alert_group': "AlertGroup templates must share the same target type"
                    })
                derived_target_type = next(iter(derived_types))

            effective_alert_type = derived_target_type or alert_type_setting or AlertType.WALLET

            if alert_type_setting and derived_target_type and alert_type_setting != derived_target_type:
                raise ValidationError({
                    'alert_group': (
                        f"AlertGroup alert_type '{alert_type_setting}' does not match "
                        f"derived template target type '{derived_target_type}'"
                    )
                })

            if effective_alert_type == AlertType.NETWORK:
                normalized_key = normalize_network_subnet_key(self.target_key)
            elif effective_alert_type == AlertType.PROTOCOL:
                normalized_key = normalize_network_subnet_protocol_key(self.target_key)
            elif effective_alert_type == AlertType.NFT:
                raw = self.target_key
                if raw.count(":") >= 3:
                    normalized_key = normalize_network_subnet_address_token_id_key(raw)
                else:
                    normalized_key = normalize_network_subnet_address_key(raw)
            else:
                normalized_key = normalize_network_subnet_address_key(self.target_key)

            AlertValidationService.validate_targets(effective_alert_type, [normalized_key])
            self.target_key = normalized_key

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_effective_settings(self, base_settings: Optional[Dict] = None) -> Dict:
        """
        Get effective settings combining base settings with subscription overrides.

        Args:
            base_settings: Base settings to merge with (from AlertGroup defaults)

        Returns:
            Merged settings dictionary
        """
        settings = base_settings.copy() if base_settings else {}
        if self.settings:
            settings.update(self.settings)
        return settings

    def get_target_member_keys(self) -> List[str]:
        """Get all member keys from the target group."""
        if self.target_group:
            return self.target_group.get_member_keys()
        if self.target_key:
            return [self.target_key]
        return []


class NotificationRoutingChoice(models.TextChoices):
    """
    User choice for how notifications are routed in provider-managed groups.
    """
    CALLBACK_ONLY = 'callback_only', 'Callback Only'      # Provider webhook only
    USER_CHANNELS = 'user_channels', 'User Channels'      # User's notification settings only
    BOTH = 'both', 'Both'                                  # Both callback AND user channels


class UserWalletGroup(models.Model):
    """
    Associates a user's wallets with a developer/provider-managed WalletGroup.

    Wallet providers create WalletGroups and manage users' wallets within them.
    PROVIDER-ONLY CONTROL: Only the provider can add/remove wallets.
    Users auto-subscribe and receive notifications via the provider's callbacks.

    PRIVATE BY DEFAULT: Provider controls who can view/edit via access_control.

    Use Cases:
    1. Wallet Provider Integration:
       - Provider creates WalletGroup for their service
       - Provider creates UserWalletGroup for each user
       - Provider manages wallet_keys (user's addresses in their system)
       - Notifications route to provider's webhook callback

    2. Enterprise Multi-Tenant:
       - Organization creates WalletGroup per client
       - UserWalletGroup tracks which addresses belong to which user
       - Centralized notification routing via callbacks

    Example:
        # Provider creates group for their exchange users
        exchange_wallets = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Exchange Hot Wallets',
            owner=provider_user,
            settings={'visibility': 'private'}
        )

        # Provider associates Alice's wallets
        alice_membership = UserWalletGroup.objects.create(
            user=alice,
            wallet_group=exchange_wallets,
            provider=provider_user,
            callback=provider_webhook,
            wallet_keys=['ETH:mainnet:0xAlice1...', 'ETH:mainnet:0xAlice2...']
        )
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The user whose wallets are in the group
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='provider_wallet_groups',
        help_text="The end-user whose wallets are managed in this group"
    )

    # The provider's WalletGroup
    wallet_group = models.ForeignKey(
        GenericGroup,
        on_delete=models.CASCADE,
        related_name='user_wallet_memberships',
        limit_choices_to={'group_type': GroupType.WALLET},
        help_text="The provider's WalletGroup containing these wallets"
    )

    # Provider who manages this relationship (ONLY provider can modify wallet_keys)
    provider = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='managed_user_wallet_groups',
        help_text="The provider/developer who manages this user's wallets"
    )

    # Callback for this user's notifications (uses existing NotificationChannelEndpoint)
    # String reference to avoid circular import - model is in notifications.py
    callback = models.ForeignKey(
        'NotificationChannelEndpoint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_wallet_groups',
        limit_choices_to={'channel_type': 'webhook'},
        help_text="Provider's webhook endpoint for this user's notifications"
    )

    # User's wallets in this group - MANAGED BY PROVIDER ONLY
    wallet_keys = models.JSONField(
        default=list,
        blank=True,
        help_text='''User's wallet keys managed by the provider.
        Format: ["ETH:mainnet:0x123...", "SOL:mainnet:ABC..."]
        IMPORTANT: Only the provider can modify this field.'''
    )

    # Auto-subscription settings
    auto_subscribe_alerts = models.BooleanField(
        default=True,
        help_text="Automatically subscribe user to alerts on this group"
    )

    # USER CHOICE: How to route notifications
    notification_routing = models.CharField(
        max_length=20,
        choices=NotificationRoutingChoice.choices,
        default=NotificationRoutingChoice.CALLBACK_ONLY,
        help_text="How notifications are delivered: callback only, user channels, or both"
    )

    # PRIVACY: Private by default, provider grants edit access
    access_control = models.JSONField(
        default=dict,
        blank=True,
        help_text='''Access control for who can edit this UserWalletGroup.
        {
            "editors": {
                "users": ["user-uuid-1", "user-uuid-2"],
                "api_keys": ["api-key-id-1"]
            }
        }'''
    )

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_wallet_groups'
        verbose_name = 'User Wallet Group'
        verbose_name_plural = 'User Wallet Groups'
        unique_together = ['user', 'wallet_group']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['wallet_group', 'is_active']),
            models.Index(fields=['provider', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} in {self.wallet_group.name} (by {self.provider.email})"

    def clean(self):
        """Validate the model."""
        super().clean()

        # Ensure wallet_group is of type WALLET
        if self.wallet_group and self.wallet_group.group_type != GroupType.WALLET:
            raise ValidationError({
                'wallet_group': f"wallet_group must be of type '{GroupType.WALLET}', "
                               f"got '{self.wallet_group.group_type}'"
            })

        # Validate wallet_keys format
        if self.wallet_keys:
            if not isinstance(self.wallet_keys, list):
                raise ValidationError({
                    'wallet_keys': "wallet_keys must be a list of strings"
                })

            for i, key in enumerate(self.wallet_keys):
                if not isinstance(key, str):
                    raise ValidationError({
                        'wallet_keys': f"wallet_keys[{i}] must be a string"
                    })

                # Validate key format: {network}:{subnet}:{address}
                parts = key.split(':')
                if len(parts) < 3:
                    raise ValidationError({
                        'wallet_keys': f"Key '{key}' must be in format 'network:subnet:address' "
                                       f"(e.g., 'ETH:mainnet:0x123...')"
                    })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def can_edit(self, user=None, api_key_id: Optional[str] = None) -> bool:
        """
        Check if user or API key has edit permission.

        Permission hierarchy:
        1. Provider always has full edit access
        2. Users in access_control.editors.users list
        3. API keys in access_control.editors.api_keys list

        Args:
            user: User instance to check
            api_key_id: API key ID string to check

        Returns:
            True if the user/api_key has edit permission
        """
        # Provider always has edit access
        if user and user.id == self.provider_id:
            return True

        editors = self.access_control.get('editors', {})

        if user and str(user.id) in editors.get('users', []):
            return True

        if api_key_id and api_key_id in editors.get('api_keys', []):
            return True

        return False

    def grant_edit_access(self, user_id: Optional[str] = None, api_key_id: Optional[str] = None) -> bool:
        """
        Grant edit access to a user or API key.

        Args:
            user_id: User UUID string to grant access
            api_key_id: API key ID to grant access

        Returns:
            True if access was granted, False if already had access
        """
        if not self.access_control:
            self.access_control = {'editors': {'users': [], 'api_keys': []}}

        if 'editors' not in self.access_control:
            self.access_control['editors'] = {'users': [], 'api_keys': []}

        changed = False

        if user_id:
            users = self.access_control['editors'].setdefault('users', [])
            if user_id not in users:
                users.append(user_id)
                changed = True

        if api_key_id:
            api_keys = self.access_control['editors'].setdefault('api_keys', [])
            if api_key_id not in api_keys:
                api_keys.append(api_key_id)
                changed = True

        if changed:
            self.save(update_fields=['access_control', 'updated_at'])

        return changed

    def revoke_edit_access(self, user_id: Optional[str] = None, api_key_id: Optional[str] = None) -> bool:
        """
        Revoke edit access from a user or API key.

        Args:
            user_id: User UUID string to revoke access
            api_key_id: API key ID to revoke access

        Returns:
            True if access was revoked, False if didn't have access
        """
        if not self.access_control or 'editors' not in self.access_control:
            return False

        changed = False

        if user_id:
            users = self.access_control['editors'].get('users', [])
            if user_id in users:
                users.remove(user_id)
                changed = True

        if api_key_id:
            api_keys = self.access_control['editors'].get('api_keys', [])
            if api_key_id in api_keys:
                api_keys.remove(api_key_id)
                changed = True

        if changed:
            self.save(update_fields=['access_control', 'updated_at'])

        return changed

    def get_wallet_count(self) -> int:
        """Get the number of wallets in this user's membership."""
        return len(self.wallet_keys) if self.wallet_keys else 0

    def add_wallet(self, wallet_key: str) -> bool:
        """
        Add a wallet to this user's membership.

        Args:
            wallet_key: Wallet key in format 'chain:network:address'

        Returns:
            True if added, False if already exists
        """
        if not self.wallet_keys:
            self.wallet_keys = []

        if wallet_key in self.wallet_keys:
            return False

        self.wallet_keys.append(wallet_key)
        self.save(update_fields=['wallet_keys', 'updated_at'])
        return True

    def remove_wallet(self, wallet_key: str) -> bool:
        """
        Remove a wallet from this user's membership.

        Args:
            wallet_key: Wallet key to remove

        Returns:
            True if removed, False if not found
        """
        if not self.wallet_keys or wallet_key not in self.wallet_keys:
            return False

        self.wallet_keys.remove(wallet_key)
        self.save(update_fields=['wallet_keys', 'updated_at'])
        return True
