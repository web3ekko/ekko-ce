"""
Django REST Framework Serializers for GenericGroup and GroupSubscription models.

Provides serializers for:
- GenericGroup CRUD operations
- Member add/remove operations
- GroupSubscription management
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..models.groups import (
    GenericGroup,
    GroupSubscription,
    GroupType,
    SYSTEM_GROUP_ACCOUNTS,
    UserWalletGroup,
    normalize_network_subnet_address_key,
)
from ..models.notifications import NotificationChannelEndpoint
from ..services.group_service import AlertValidationService

User = get_user_model()


class GenericGroupSerializer(serializers.ModelSerializer):
    """Full serializer for GenericGroup with all fields including member_data."""

    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    group_type_display = serializers.CharField(source='get_group_type_display', read_only=True)
    member_keys = serializers.SerializerMethodField()

    class Meta:
        model = GenericGroup
        fields = [
            'id', 'group_type', 'group_type_display', 'name', 'description',
            'owner', 'owner_email', 'settings', 'member_data', 'member_count',
            'member_keys', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'member_count', 'created_at', 'updated_at']

    def get_member_keys(self, obj) -> list:
        """Get list of all member keys in the group."""
        return obj.get_member_keys()

    def validate_group_type(self, value):
        """Validate that group_type is a valid choice."""
        valid_types = [choice[0] for choice in GroupType.choices]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid group_type. Must be one of: {valid_types}"
            )
        return value

    def create(self, validated_data):
        """Create group with current user as owner."""
        validated_data['owner'] = self.context['request'].user
        # Ensure member_data has correct structure
        if 'member_data' not in validated_data:
            validated_data['member_data'] = {'members': {}}
        return super().create(validated_data)


class GenericGroupListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for group lists (excludes member_data)."""

    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    group_type_display = serializers.CharField(source='get_group_type_display', read_only=True)

    class Meta:
        model = GenericGroup
        fields = [
            'id', 'group_type', 'group_type_display', 'name', 'description',
            'owner_email', 'settings', 'member_count', 'created_at', 'updated_at'
        ]


class GenericGroupCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating groups with optional initial members."""

    initial_members = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text="Initial members to add: [{'key': 'ETH:mainnet:0x...', 'label': 'Treasury', 'tags': ['defi']}]"
    )

    class Meta:
        model = GenericGroup
        fields = [
            'id', 'group_type', 'name', 'description', 'settings', 'initial_members'
        ]
        read_only_fields = ['id']

    def validate_group_type(self, value):
        """Validate that group_type is a valid choice."""
        valid_types = [choice[0] for choice in GroupType.choices]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid group_type. Must be one of: {valid_types}"
            )
        return value

    def validate_initial_members(self, value):
        """Validate initial members structure."""
        if not value:
            return value

        for i, member in enumerate(value):
            if not isinstance(member, dict):
                raise serializers.ValidationError(
                    f"Member at index {i} must be a dictionary"
                )
            if 'key' not in member:
                raise serializers.ValidationError(
                    f"Member at index {i} missing required field 'key'"
                )
        return value

    def validate(self, data):
        """
        Cross-field validation including AlertGroup homogeneity.

        For AlertGroups with initial_members, validate that all members
        match the group's alert_type.
        """
        group_type = data.get('group_type')
        settings = data.get('settings', {})
        initial_members = data.get('initial_members', [])

        if group_type == GroupType.WALLET and settings.get('system_key') == SYSTEM_GROUP_ACCOUNTS:
            raise serializers.ValidationError({
                'settings': "system_key='accounts' groups are server-managed; use /api/groups/accounts/add_wallet/."
            })

        # AlertGroup with initial_members: validate homogeneity
        if group_type == GroupType.ALERT and initial_members:
            alert_type = settings.get('alert_type')
            if not alert_type:
                raise serializers.ValidationError({
                    'settings': "AlertGroups require 'alert_type' in settings"
                })

            # Create temporary group instance for validation
            temp_group = GenericGroup(
                group_type=group_type,
                settings=settings
            )
            member_keys = [m['key'] for m in initial_members]
            # This will raise ValidationError if any member is invalid
            temp_group.validate_alert_group_members(member_keys)

        return data

    def create(self, validated_data):
        """Create group with initial members."""
        initial_members = validated_data.pop('initial_members', [])
        validated_data['owner'] = self.context['request'].user

        # Build member_data from initial_members
        member_data = {'members': {}}
        user_id = str(self.context['request'].user.id)
        temp_group = GenericGroup(
            group_type=validated_data.get('group_type'),
            settings=validated_data.get('settings', {}) or {},
        )

        for member in initial_members:
            key = temp_group.normalize_member_key(member['key'])
            member_data['members'][key] = {
                'added_at': timezone.now().isoformat(),
                'added_by': user_id,
                'label': member.get('label', ''),
                'tags': member.get('tags', []),
                'metadata': member.get('metadata', {})
            }

        validated_data['member_data'] = member_data
        validated_data['member_count'] = len(member_data['members'])

        return super().create(validated_data)


class GroupMemberSerializer(serializers.Serializer):
    """Serializer for add/remove member operations."""

    member_key = serializers.CharField(
        help_text="Member key, e.g., 'ETH:mainnet:0x123...' for wallets"
    )
    label = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional label for the member"
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Optional tags for the member"
    )
    metadata = serializers.DictField(
        required=False,
        help_text="Optional metadata dictionary"
    )

    def validate_member_key(self, value):
        """Validate member key is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Member key cannot be empty")
        return value.strip()


class GroupMemberUpdateSerializer(serializers.Serializer):
    """Serializer for updating existing member metadata (label/tags/metadata)."""

    member_key = serializers.CharField(
        help_text="Member key, e.g., 'ETH:mainnet:0x123...' for wallets"
    )
    label = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional label for the member"
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Optional tags for the member"
    )
    metadata = serializers.DictField(
        required=False,
        help_text="Optional metadata dictionary"
    )

    def validate_member_key(self, value):
        """Validate member key is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Member key cannot be empty")
        return value.strip()


class GroupMemberBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk updating existing group members."""

    members = serializers.ListField(
        child=GroupMemberUpdateSerializer(),
        min_length=1,
        max_length=10000,
        help_text="List of members to update (max 10,000)"
    )


class AccountsWalletAddSerializer(serializers.Serializer):
    """Serializer for adding a wallet to the user's Accounts group."""

    member_key = serializers.CharField(
        help_text="Wallet key in format '{NETWORK}:{subnet}:{address}', e.g. 'ETH:mainnet:0x123...'"
    )
    label = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional nickname for this wallet (used in notifications)"
    )
    owner_verified = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether the user has verified they own this wallet"
    )

    def validate_member_key(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("member_key cannot be empty")

        from app.models.groups import normalize_network_subnet_address_key
        from app.services.group_service import AlertValidationService

        normalized = normalize_network_subnet_address_key(value.strip())
        AlertValidationService.validate_targets('wallet', [normalized])
        return normalized


class AccountsWalletBulkAddSerializer(serializers.Serializer):
    """Serializer for bulk-adding wallets to the user's Accounts group."""

    wallets = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=10000,
        help_text="Wallets to add to Accounts (max 10,000)",
    )


class GroupMemberBulkSerializer(serializers.Serializer):
    """Serializer for bulk add/remove member operations."""

    members = serializers.ListField(
        child=GroupMemberSerializer(),
        min_length=1,
        max_length=10000,
        help_text="List of members to add/remove (max 10,000)"
    )

    def validate_members(self, value):
        """
        Validate members, including AlertGroup homogeneity validation.

        For AlertGroups, all member keys must:
        1. Be in format 'template:{uuid}'
        2. Reference AlertTemplates with matching alert_type
        """
        # Get group from context (passed from view)
        group = self.context.get('group')
        if group and group.group_type == GroupType.ALERT:
            member_keys = [group.normalize_member_key(m['member_key']) for m in value]
            # This will raise ValidationError if any member is invalid
            group.validate_alert_group_members(member_keys)
        return value


class GroupSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for GroupSubscription model."""

    alert_group_name = serializers.CharField(source='alert_group.name', read_only=True)
    target_group_name = serializers.CharField(source='target_group.name', read_only=True)
    target_group_type = serializers.CharField(source='target_group.group_type', read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)

    class Meta:
        model = GroupSubscription
        fields = [
            'id', 'alert_group', 'alert_group_name', 'target_group',
            'target_group_name', 'target_group_type', 'target_key', 'owner', 'owner_email',
            'settings', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']
        extra_kwargs = {
            # Exactly one of target_group or target_key is required, so both must be optional at the field level.
            'target_group': {'required': False, 'allow_null': True},
            'target_key': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def validate(self, data):
        """Validate subscription constraints."""
        alert_group = data.get('alert_group')
        target_group = data.get('target_group')
        target_key = data.get('target_key')
        user = self.context['request'].user
        subscription_settings = data.get('settings', {}) or {}
        effective_alert_type = (alert_group.get_alert_type() if alert_group else None) or 'wallet'
        templates = None

        if subscription_settings and not isinstance(subscription_settings, dict):
            raise serializers.ValidationError({
                'settings': "settings must be a JSON object"
            })

        # Alert group must be of type ALERT
        if alert_group and alert_group.group_type != GroupType.ALERT:
            raise serializers.ValidationError({
                'alert_group': f"Alert group must be of type '{GroupType.ALERT}', "
                               f"got '{alert_group.group_type}'"
            })

        if bool(target_group) == bool(target_key):
            raise serializers.ValidationError({
                'target_group': "Provide exactly one of target_group or target_key",
                'target_key': "Provide exactly one of target_group or target_key",
            })

        # Target group must be visible to the subscriber (owned or public)
        if target_group and target_group.owner_id != user.id and not target_group.is_public():
            raise serializers.ValidationError({
                'target_group': "Cannot target a private group owned by another user"
            })

        # Alert group must be either owned by the user or public
        if alert_group and alert_group.owner_id != user.id and not alert_group.is_public():
            raise serializers.ValidationError({
                'alert_group': "Cannot subscribe to a private alert group owned by another user"
            })

        # Target group cannot be the same as alert group
        if alert_group and target_group and alert_group.id == target_group.id:
            raise serializers.ValidationError({
                'target_group': "Target group cannot be the same as alert group"
            })

        # If the alert group has templates, derive the target type from template type
        # and ensure it matches AlertGroup.settings.alert_type.
        if alert_group and alert_group.group_type == GroupType.ALERT:
            from app.services.group_service import GroupService
            from app.models.alert_templates import AlertTemplate

            template_ids = GroupService._extract_template_ids_from_alert_group(alert_group)
            if template_ids:
                templates = list(AlertTemplate.objects.filter(id__in=template_ids))
                if len(templates) != len(template_ids):
                    raise serializers.ValidationError({
                        'alert_group': "AlertGroup contains missing templates"
                    })

                derived_types = {t.get_target_alert_type() for t in templates}
                if len(derived_types) != 1:
                    raise serializers.ValidationError({
                        'alert_group': "AlertGroup templates must share the same target type"
                    })

                derived_target_type = next(iter(derived_types))
                if alert_group.get_alert_type() and derived_target_type != alert_group.get_alert_type():
                    raise serializers.ValidationError({
                        'alert_group': (
                            f"AlertGroup alert_type '{alert_group.get_alert_type()}' does not match "
                            f"derived template target type '{derived_target_type}'"
                        )
                    })

                effective_alert_type = derived_target_type

        # Validate target_group type matches derived type (owned/public checks already done).
        if target_group:
            from app.models.groups import ALERT_TYPE_TO_GROUP_TYPE

            valid_group_types = ALERT_TYPE_TO_GROUP_TYPE.get(effective_alert_type, [])
            if target_group.group_type not in valid_group_types:
                raise serializers.ValidationError({
                    'target_group': (
                        f"AlertGroup with alert_type='{effective_alert_type}' can only be applied "
                        f"to groups of type {valid_group_types}, got '{target_group.group_type}'"
                    )
                })

        # Normalize and validate target_key (if used)
        normalized_target_key = None
        if target_key:
            from app.models.groups import (
                normalize_network_subnet_address_key,
                normalize_network_subnet_address_token_id_key,
                normalize_network_subnet_key,
                normalize_network_subnet_protocol_key,
            )
            from app.services.group_service import AlertValidationService

            raw = str(target_key).strip()
            if effective_alert_type == 'network':
                normalized_target_key = normalize_network_subnet_key(raw)
            elif effective_alert_type == 'protocol':
                normalized_target_key = normalize_network_subnet_protocol_key(raw)
            elif effective_alert_type == 'nft':
                if raw.count(":") >= 3:
                    normalized_target_key = normalize_network_subnet_address_token_id_key(raw)
                else:
                    normalized_target_key = normalize_network_subnet_address_key(raw)
            else:
                normalized_target_key = normalize_network_subnet_address_key(raw)
            AlertValidationService.validate_targets(effective_alert_type, [normalized_target_key])
            data['target_key'] = normalized_target_key

        # Check for duplicate subscription
        if alert_group:
            if target_group:
                existing = GroupSubscription.objects.filter(
                    alert_group=alert_group,
                    target_group=target_group,
                    owner=user
                )
            else:
                existing = GroupSubscription.objects.filter(
                    alert_group=alert_group,
                    target_key=normalized_target_key,
                    owner=user,
                )

            # Exclude current instance if updating
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            if existing.exists():
                raise serializers.ValidationError(
                    "A subscription with this alert group and target already exists"
                )

        # Validate required template params for AlertGroup subscriptions.
        #
        # The subscription form should ask for required (non-targeting) params for each template,
        # so wallet-alert instances can start enabled immediately.
        if alert_group and alert_group.group_type == GroupType.ALERT:
            from app.services.group_service import GroupService
            from app.models.alert_templates import AlertTemplate

            template_ids = GroupService._extract_template_ids_from_alert_group(alert_group)
            if template_ids:
                if templates is None:
                    templates = list(AlertTemplate.objects.filter(id__in=template_ids))
                missing_by_template: dict = {}

                for template in templates:
                    params = GroupService._build_subscription_template_params(
                        template=template,
                        subscription_settings=subscription_settings,
                    )
                    missing = GroupService._missing_required_template_params(
                        template=template,
                        params=params,
                    )
                    if missing:
                        missing_by_template[str(template.id)] = missing

                if missing_by_template:
                    raise serializers.ValidationError({
                        'settings': {
                            'missing_template_params': missing_by_template,
                            'hint': (
                                "Provide values in settings.template_params "
                                "or settings.template_params_by_template[template_id]."
                            ),
                        }
                    })

        return data

    def create(self, validated_data):
        """Create subscription with current user as owner."""
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class GroupSubscriptionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for subscription lists."""

    alert_group_name = serializers.CharField(source='alert_group.name', read_only=True)
    target_group_name = serializers.CharField(source='target_group.name', read_only=True)
    target_group_type = serializers.CharField(source='target_group.group_type', read_only=True)
    target_member_count = serializers.SerializerMethodField()

    class Meta:
        model = GroupSubscription
        fields = [
            'id', 'alert_group', 'alert_group_name', 'target_group',
            'target_group_name', 'target_group_type', 'target_key', 'target_member_count',
            'is_active', 'created_at'
        ]

    def get_target_member_count(self, obj) -> int:
        if obj.target_group_id:
            return obj.target_group.member_count
        if obj.target_key:
            return 1
        return 0


class NotificationChannelEndpointLiteSerializer(serializers.ModelSerializer):
    """Lite serializer for nested callback endpoints in UserWalletGroup responses."""

    class Meta:
        from app.models.notifications import NotificationChannelEndpoint

        model = NotificationChannelEndpoint
        fields = ['id', 'channel_type', 'label', 'config']
        read_only_fields = fields


class UserWalletGroupSerializer(serializers.ModelSerializer):
    """Serializer for UserWalletGroup (provider-managed wallet associations)."""

    user_email = serializers.EmailField(source='user.email', read_only=True)
    wallet_group_name = serializers.CharField(source='wallet_group.name', read_only=True)
    provider_name = serializers.EmailField(source='provider.email', read_only=True)
    callback = NotificationChannelEndpointLiteSerializer(read_only=True)

    class Meta:
        model = UserWalletGroup
        fields = [
            'id',
            'user',
            'user_email',
            'wallet_group',
            'wallet_group_name',
            'provider',
            'provider_name',
            'callback',
            'wallet_keys',
            'auto_subscribe_alerts',
            'notification_routing',
            'access_control',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'user_email',
            'wallet_group',
            'wallet_group_name',
            'provider',
            'provider_name',
            'callback',
            'wallet_keys',
            'access_control',
            'created_at',
            'updated_at',
        ]


class UserWalletGroupCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating provider-managed UserWalletGroup memberships."""

    wallet_keys = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="List of wallet keys in format '{NETWORK}:{subnet}:{address}'",
    )
    callback = serializers.PrimaryKeyRelatedField(
        queryset=NotificationChannelEndpoint.objects.filter(channel_type='webhook'),
        required=False,
        allow_null=True,
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        default=serializers.CurrentUserDefault(),
    )
    provider = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = UserWalletGroup
        fields = [
            'id',
            'user',
            'wallet_group',
            'provider',
            'callback',
            'wallet_keys',
            'auto_subscribe_alerts',
            'notification_routing',
            'access_control',
            'is_active',
        ]
        read_only_fields = ['id']

    def _normalize_wallet_key(self, raw_key: str) -> str:
        normalized = normalize_network_subnet_address_key(raw_key.strip())
        AlertValidationService.validate_targets('wallet', [normalized])
        return normalized

    def validate_wallet_group(self, value):
        if value.group_type != GroupType.WALLET:
            raise serializers.ValidationError("wallet_group must be of type 'wallet'")
        return value

    def validate_wallet_keys(self, value):
        normalized = []
        for raw in value or []:
            if not isinstance(raw, str) or not raw.strip():
                raise serializers.ValidationError("wallet_keys must be non-empty strings")
            normalized.append(self._normalize_wallet_key(raw))
        return normalized

    def validate_callback(self, value):
        if value is None:
            return value
        request_user = self.context['request'].user
        if value.owner_id != request_user.id:
            raise serializers.ValidationError("callback must belong to the authenticated user")
        return value

    def validate(self, data):
        request_user = self.context['request'].user
        provider = data.get('provider') or request_user
        user = data.get('user') or request_user

        if provider != request_user:
            raise serializers.ValidationError("provider must match the authenticated user")

        wallet_group = data.get('wallet_group')
        if wallet_group and wallet_group.owner_id != provider.id:
            raise serializers.ValidationError("wallet_group must be owned by the provider")

        data['provider'] = provider
        data['user'] = user
        return data


class UserWalletGroupUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for user-editable UserWalletGroup fields."""

    callback = serializers.PrimaryKeyRelatedField(
        queryset=NotificationChannelEndpoint.objects.filter(channel_type='webhook'),
        required=False,
        allow_null=True,
    )
    access_control = serializers.DictField(required=False)

    class Meta:
        model = UserWalletGroup
        fields = [
            'auto_subscribe_alerts',
            'notification_routing',
            'is_active',
            'callback',
            'access_control',
        ]

    def validate_callback(self, value):
        if value is None:
            return value
        request_user = self.context['request'].user
        if value.owner_id != request_user.id:
            raise serializers.ValidationError("callback must belong to the authenticated user")
        return value


class UserWalletGroupWalletKeysSerializer(serializers.Serializer):
    """Serializer for adding/removing wallet keys in a UserWalletGroup."""

    wallet_keys = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=10000,
        help_text="Wallet keys in format '{NETWORK}:{subnet}:{address}'",
    )
    dedupe = serializers.BooleanField(default=True, required=False)

    def _normalize_wallet_key(self, raw_key: str) -> str:
        normalized = normalize_network_subnet_address_key(raw_key.strip())
        AlertValidationService.validate_targets('wallet', [normalized])
        return normalized

    def validate_wallet_keys(self, value):
        normalized = []
        for raw in value:
            if not isinstance(raw, str) or not raw.strip():
                raise serializers.ValidationError("wallet_keys must be non-empty strings")
            normalized.append(self._normalize_wallet_key(raw))
        return normalized


class UserWalletGroupImportSerializer(serializers.Serializer):
    """Serializer for bulk importing wallets into a UserWalletGroup."""

    format = serializers.ChoiceField(choices=[('csv', 'CSV'), ('json', 'JSON')])
    payload = serializers.CharField()
    merge_mode = serializers.ChoiceField(choices=[('append', 'append'), ('replace', 'replace')], default='append')
    dedupe = serializers.BooleanField(default=True, required=False)
