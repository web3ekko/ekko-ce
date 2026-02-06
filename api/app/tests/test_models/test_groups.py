"""
Unit tests for Group models: GenericGroup, GroupSubscription, UserWalletGroup
Tests settings validation, alert_type constraints, and provider-managed groups.
"""

import pytest
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from app.models.groups import (
    GenericGroup, GroupSubscription, UserWalletGroup,
    GroupType, AlertType, ALERT_TYPE_TO_GROUP_TYPE, NotificationRoutingChoice
)

User = get_user_model()


@pytest.fixture
def provider_user(db):
    """Create a provider/developer user"""
    return User.objects.create_user(
        email='provider@example.com',
        first_name='Provider',
        last_name='User',
        password='providerpass123'
    )


@pytest.fixture
def end_user(db):
    """Create an end user"""
    return User.objects.create_user(
        email='enduser@example.com',
        first_name='End',
        last_name='User',
        password='enduserpass123'
    )


@pytest.fixture
def wallet_group(user):
    """Create a sample WalletGroup"""
    return GenericGroup.objects.create(
        group_type=GroupType.WALLET,
        name='My Wallets',
        owner=user,
        settings={'visibility': 'private'},
        member_data={'members': {
            'ETH:mainnet:0x123': {'added_at': '2025-01-01T00:00:00Z'},
            'ETH:mainnet:0x456': {'added_at': '2025-01-01T00:00:00Z'},
        }}
    )


@pytest.fixture
def alert_group(user):
    """Create a sample AlertGroup with alert_type=wallet"""
    return GenericGroup.objects.create(
        group_type=GroupType.ALERT,
        name='My Alert Group',
        owner=user,
        settings={'alert_type': 'wallet'}
    )


@pytest.fixture
def network_group(user):
    """Create a sample NetworkGroup"""
    return GenericGroup.objects.create(
        group_type=GroupType.NETWORK,
        name='EVM Networks',
        owner=user,
        member_data={'members': {
            'ETH:mainnet': {},
            'POLYGON:mainnet': {},
        }}
    )


@pytest.mark.django_db
class TestGenericGroupSettingsValidation:
    """Test GenericGroup settings validation"""

    def test_alert_group_requires_alert_type(self, user):
        """AlertGroups must have alert_type in settings"""
        with pytest.raises(ValidationError) as exc_info:
            GenericGroup.objects.create(
                group_type=GroupType.ALERT,
                name='Invalid Alert Group',
                owner=user,
                settings={}  # Missing alert_type
            )

        assert 'alert_type' in str(exc_info.value)

    def test_alert_group_invalid_alert_type(self, user):
        """AlertGroups must have valid alert_type"""
        with pytest.raises(ValidationError) as exc_info:
            GenericGroup.objects.create(
                group_type=GroupType.ALERT,
                name='Invalid Alert Group',
                owner=user,
                settings={'alert_type': 'invalid_type'}
            )

        assert 'Invalid alert_type' in str(exc_info.value)

    def test_alert_group_valid_alert_types(self, user):
        """AlertGroups can use any valid AlertType"""
        for alert_type in AlertType:
            group = GenericGroup.objects.create(
                group_type=GroupType.ALERT,
                name=f'{alert_type.value} Alert Group',
                owner=user,
                settings={'alert_type': alert_type.value}
            )
            assert group.get_alert_type() == alert_type.value
            group.delete()  # Clean up for next iteration

    def test_wallet_group_valid_visibility(self, user):
        """WalletGroups accept valid visibility values"""
        public_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Public Wallets',
            owner=user,
            settings={'visibility': 'public'}
        )
        assert public_group.is_public() is True

        private_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Private Wallets',
            owner=user,
            settings={'visibility': 'private'}
        )
        assert private_group.is_public() is False

    def test_wallet_group_invalid_visibility(self, user):
        """WalletGroups reject invalid visibility values"""
        with pytest.raises(ValidationError) as exc_info:
            GenericGroup.objects.create(
                group_type=GroupType.WALLET,
                name='Invalid Visibility',
                owner=user,
                settings={'visibility': 'unlisted'}  # Invalid
            )

        assert 'visibility' in str(exc_info.value)

    def test_wallet_group_default_visibility(self, user):
        """WalletGroups default to private visibility"""
        group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Default Visibility',
            owner=user,
            settings={}  # No visibility set
        )
        assert group.get_visibility() == 'private'
        assert group.is_public() is False

    def test_allows_subscriptions_default(self, user):
        """Groups default to not allowing subscriptions"""
        group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Default Subscriptions',
            owner=user
        )
        assert group.allows_subscriptions() is False

    def test_allows_subscriptions_public(self, user):
        """Public groups are subscribable"""
        group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Public Subscriptions',
            owner=user,
            settings={'visibility': 'public'}
        )
        assert group.allows_subscriptions() is True


@pytest.mark.django_db
class TestGenericGroupHelperMethods:
    """Test GenericGroup helper methods"""

    def test_get_alert_type_for_alert_group(self, alert_group):
        """get_alert_type returns alert_type for AlertGroups"""
        assert alert_group.get_alert_type() == 'wallet'

    def test_get_alert_type_for_non_alert_group(self, wallet_group):
        """get_alert_type returns None for non-AlertGroups"""
        assert wallet_group.get_alert_type() is None

    def test_get_member_keys(self, wallet_group):
        """get_member_keys returns list of all member keys"""
        keys = wallet_group.get_member_keys()
        assert len(keys) == 2
        assert 'ETH:mainnet:0x123' in keys
        assert 'ETH:mainnet:0x456' in keys

    def test_has_member(self, wallet_group):
        """has_member checks membership correctly"""
        assert wallet_group.has_member('ETH:mainnet:0x123') is True
        assert wallet_group.has_member('ETH:mainnet:0x999') is False

    def test_member_count_sync(self, user):
        """member_count stays in sync with member_data"""
        group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Count Test',
            owner=user,
            member_data={'members': {
                'key1': {}, 'key2': {}, 'key3': {}
            }}
        )
        assert group.member_count == 3


@pytest.mark.django_db
class TestGroupSubscriptionValidation:
    """Test GroupSubscription validation for alert_type matching"""

    def test_subscription_requires_alert_group(self, user, wallet_group):
        """Subscription alert_group must be of type ALERT"""
        with pytest.raises(ValidationError) as exc_info:
            GroupSubscription.objects.create(
                alert_group=wallet_group,  # Wrong type - should be ALERT
                target_group=wallet_group,
                owner=user
            )

        assert 'Alert group must be of type' in str(exc_info.value)

    def test_subscription_same_group_not_allowed(self, user, alert_group):
        """Cannot subscribe alert_group to itself"""
        with pytest.raises(ValidationError) as exc_info:
            GroupSubscription.objects.create(
                alert_group=alert_group,
                target_group=alert_group,
                owner=user
            )

        assert 'cannot be the same' in str(exc_info.value)

    def test_subscription_wallet_alert_to_wallet_group(self, user, alert_group, wallet_group):
        """Wallet AlertGroup can subscribe to WalletGroup"""
        subscription = GroupSubscription.objects.create(
            alert_group=alert_group,
            target_group=wallet_group,
            owner=user
        )
        assert subscription.id is not None

    def test_subscription_with_target_key(self, user, alert_group):
        """Subscriptions can target a single wallet via target_key."""
        subscription = GroupSubscription.objects.create(
            alert_group=alert_group,
            target_key='eth:MainNet:0xAbCdEf000000000000000000000000000000000000',
            owner=user,
        )
        assert subscription.id is not None
        assert subscription.target_group_id is None
        assert subscription.target_key == 'ETH:mainnet:0xabcdef000000000000000000000000000000000000'

    def test_subscription_nft_token_id_target_key_preserves_token_id(self, user):
        """NFT subscriptions can target a specific token_id without normalizing token_id casing."""
        nft_alert_group = GenericGroup.objects.create(
            group_type=GroupType.ALERT,
            name='NFT Alert Group',
            owner=user,
            settings={'alert_type': 'nft'},
        )

        subscription = GroupSubscription.objects.create(
            alert_group=nft_alert_group,
            target_key='eth:MainNet:0xAbCdEf000000000000000000000000000000000000:Token:ID-V1',
            owner=user,
        )

        assert subscription.id is not None
        assert subscription.target_group_id is None
        assert subscription.target_key == 'ETH:mainnet:0xabcdef000000000000000000000000000000000000:Token:ID-V1'

    def test_subscription_requires_exactly_one_target(self, user, alert_group, wallet_group):
        """Subscriptions require exactly one of target_group or target_key."""
        with pytest.raises(ValidationError):
            GroupSubscription.objects.create(
                alert_group=alert_group,
                owner=user,
            )

        with pytest.raises(ValidationError):
            GroupSubscription.objects.create(
                alert_group=alert_group,
                target_group=wallet_group,
                target_key='ETH:mainnet:0xabcdef000000000000000000000000000000000000',
                owner=user,
            )

    def test_subscription_blank_target_key_rejected(self, user, alert_group):
        """Blank target_key should be treated as missing and rejected."""
        with pytest.raises(ValidationError) as exc_info:
            GroupSubscription.objects.create(
                alert_group=alert_group,
                target_key="   ",
                owner=user,
            )

        assert "Provide exactly one of target_group or target_key" in str(exc_info.value)

    def test_subscription_wallet_alert_to_network_group_fails(self, user, alert_group, network_group):
        """Wallet AlertGroup cannot subscribe to NetworkGroup"""
        with pytest.raises(ValidationError) as exc_info:
            GroupSubscription.objects.create(
                alert_group=alert_group,  # alert_type=wallet
                target_group=network_group,  # group_type=network
                owner=user
            )

        assert 'can only be applied to groups of type' in str(exc_info.value)

    def test_subscription_network_alert_to_network_group(self, user, network_group):
        """Network AlertGroup can subscribe to NetworkGroup"""
        network_alert_group = GenericGroup.objects.create(
            group_type=GroupType.ALERT,
            name='Network Alert Group',
            owner=user,
            settings={'alert_type': 'network'}
        )

        subscription = GroupSubscription.objects.create(
            alert_group=network_alert_group,
            target_group=network_group,
            owner=user
        )
        assert subscription.id is not None

    def test_get_effective_settings(self, user, alert_group, wallet_group):
        """get_effective_settings merges base settings with overrides"""
        subscription = GroupSubscription.objects.create(
            alert_group=alert_group,
            target_group=wallet_group,
            owner=user,
            settings={'cooldown_minutes': 10, 'severity': 'high'}
        )

        base = {'cooldown_minutes': 5, 'channel': 'email'}
        effective = subscription.get_effective_settings(base)

        # Override should win
        assert effective['cooldown_minutes'] == 10
        # Base should be preserved
        assert effective['channel'] == 'email'
        # New setting should be added
        assert effective['severity'] == 'high'


@pytest.mark.django_db
class TestUserWalletGroup:
    """Test UserWalletGroup model for provider-managed wallets"""

    def test_create_user_wallet_group(self, provider_user, end_user):
        """Test basic UserWalletGroup creation"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        user_wallet_group = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user,
            wallet_keys=['ETH:mainnet:0xUser1', 'ETH:mainnet:0xUser2']
        )

        assert user_wallet_group.id is not None
        assert user_wallet_group.user == end_user
        assert user_wallet_group.provider == provider_user
        assert user_wallet_group.get_wallet_count() == 2

    def test_wallet_group_type_validation(self, provider_user, end_user):
        """UserWalletGroup.wallet_group must be of type WALLET"""
        network_group = GenericGroup.objects.create(
            group_type=GroupType.NETWORK,
            name='Networks',
            owner=provider_user
        )

        with pytest.raises(ValidationError) as exc_info:
            UserWalletGroup.objects.create(
                user=end_user,
                wallet_group=network_group,
                provider=provider_user
            )

        assert 'wallet_group must be of type' in str(exc_info.value)

    def test_wallet_keys_format_validation(self, provider_user, end_user):
        """wallet_keys must be in correct format"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        with pytest.raises(ValidationError) as exc_info:
            UserWalletGroup.objects.create(
                user=end_user,
                wallet_group=wallet_group,
                provider=provider_user,
                wallet_keys=['invalid-key-format']  # Missing colons
            )

        assert 'network:subnet:address' in str(exc_info.value)

    def test_notification_routing_choices(self, provider_user, end_user):
        """Test notification routing options"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        for routing in NotificationRoutingChoice:
            uwg = UserWalletGroup.objects.create(
                user=end_user,
                wallet_group=wallet_group,
                provider=provider_user,
                notification_routing=routing.value
            )
            assert uwg.notification_routing == routing.value
            uwg.delete()

    def test_default_notification_routing(self, provider_user, end_user):
        """Default notification routing is callback_only"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        uwg = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user
        )
        assert uwg.notification_routing == NotificationRoutingChoice.CALLBACK_ONLY

    def test_can_edit_provider_always_allowed(self, provider_user, end_user):
        """Provider always has edit access"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        uwg = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user
        )

        assert uwg.can_edit(user=provider_user) is True
        assert uwg.can_edit(user=end_user) is False

    def test_can_edit_granted_users(self, provider_user, end_user, user):
        """Users in access_control can edit"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        uwg = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user,
            access_control={'editors': {'users': [str(user.id)], 'api_keys': []}}
        )

        assert uwg.can_edit(user=user) is True
        assert uwg.can_edit(user=end_user) is False

    def test_can_edit_api_keys(self, provider_user, end_user):
        """API keys in access_control can edit"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        uwg = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user,
            access_control={'editors': {'users': [], 'api_keys': ['api-key-123']}}
        )

        assert uwg.can_edit(api_key_id='api-key-123') is True
        assert uwg.can_edit(api_key_id='wrong-key') is False

    def test_grant_edit_access(self, provider_user, end_user, user):
        """Test granting edit access"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        uwg = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user
        )

        # Initially no access
        assert uwg.can_edit(user=user) is False

        # Grant access
        result = uwg.grant_edit_access(user_id=str(user.id))
        assert result is True

        # Now has access
        uwg.refresh_from_db()
        assert uwg.can_edit(user=user) is True

        # Granting again returns False (already has access)
        result = uwg.grant_edit_access(user_id=str(user.id))
        assert result is False

    def test_revoke_edit_access(self, provider_user, end_user, user):
        """Test revoking edit access"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        uwg = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user,
            access_control={'editors': {'users': [str(user.id)], 'api_keys': []}}
        )

        # Initially has access
        assert uwg.can_edit(user=user) is True

        # Revoke access
        result = uwg.revoke_edit_access(user_id=str(user.id))
        assert result is True

        # No longer has access
        uwg.refresh_from_db()
        assert uwg.can_edit(user=user) is False

    def test_add_wallet(self, provider_user, end_user):
        """Test adding a wallet"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        uwg = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user,
            wallet_keys=[]
        )

        result = uwg.add_wallet('ETH:mainnet:0xNew')
        assert result is True
        assert uwg.get_wallet_count() == 1

        # Adding same wallet again returns False
        result = uwg.add_wallet('ETH:mainnet:0xNew')
        assert result is False

    def test_remove_wallet(self, provider_user, end_user):
        """Test removing a wallet"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        uwg = UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user,
            wallet_keys=['ETH:mainnet:0x123', 'ETH:mainnet:0x456']
        )

        result = uwg.remove_wallet('ETH:mainnet:0x123')
        assert result is True
        assert uwg.get_wallet_count() == 1

        # Removing non-existent wallet returns False
        result = uwg.remove_wallet('ETH:mainnet:0x999')
        assert result is False

    def test_unique_together_constraint(self, provider_user, end_user):
        """User can only have one membership per wallet_group"""
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider_user
        )

        UserWalletGroup.objects.create(
            user=end_user,
            wallet_group=wallet_group,
            provider=provider_user
        )

        # Creating another membership for same user+wallet_group fails
        with pytest.raises(ValidationError):
            UserWalletGroup.objects.create(
                user=end_user,
                wallet_group=wallet_group,
                provider=provider_user
            )


@pytest.mark.django_db
class TestAlertGroupMemberValidation:
    """
    Test AlertGroup member validation.

    AlertGroups contain AlertTemplates and enforce that all member templates share the same alert_type
    as specified in the AlertGroup's settings.alert_type.
    """

    @pytest.fixture
    def wallet_alert_template(self, user):
        """Create a wallet-type AlertTemplate (vNext)."""
        from app.models.alert_templates import AlertTemplate
        return AlertTemplate.objects.create(
            fingerprint="sha256:" + "0" * 64,
            created_by=user,
            name="Wallet Balance Template",
            description="Alert when wallet balance changes",
            target_kind=AlertType.WALLET,
        )

    @pytest.fixture
    def network_alert_template(self, user):
        """Create a network-type AlertTemplate (vNext)."""
        from app.models.alert_templates import AlertTemplate
        return AlertTemplate.objects.create(
            fingerprint="sha256:" + "1" * 64,
            created_by=user,
            name="Network Gas Template",
            description="Alert when network gas spikes",
            target_kind=AlertType.NETWORK,
        )

    @pytest.fixture
    def protocol_alert_template(self, user):
        """Create a protocol-type AlertTemplate (vNext)."""
        from app.models.alert_templates import AlertTemplate
        return AlertTemplate.objects.create(
            fingerprint="sha256:" + "2" * 64,
            created_by=user,
            name="Protocol Health Template",
            description="Alert when protocol metric changes",
            target_kind=AlertType.PROTOCOL,
        )

    @pytest.fixture
    def wallet_alert_group(self, user):
        """Create a wallet-type AlertGroup."""
        return GenericGroup.objects.create(
            group_type=GroupType.ALERT,
            name='Wallet Alert Group',
            owner=user,
            settings={'alert_type': 'wallet'}
        )

    @pytest.fixture
    def network_alert_group(self, user):
        """Create a network-type AlertGroup."""
        return GenericGroup.objects.create(
            group_type=GroupType.ALERT,
            name='Network Alert Group',
            owner=user,
            settings={'alert_type': 'network'}
        )

    @pytest.fixture
    def protocol_alert_group(self, user):
        """Create a protocol-type AlertGroup."""
        return GenericGroup.objects.create(
            group_type=GroupType.ALERT,
            name='Protocol Alert Group',
            owner=user,
            settings={'alert_type': 'protocol'}
        )

    def test_valid_member_addition(self, wallet_alert_group, wallet_alert_template):
        """Adding wallet template to wallet AlertGroup succeeds."""
        member_key = f'template:{wallet_alert_template.id}'

        # This should not raise any exception
        wallet_alert_group.validate_alert_group_members([member_key])

    def test_invalid_member_type_mismatch(self, wallet_alert_group, network_alert_template):
        """Adding network template to wallet AlertGroup fails validation."""
        member_key = f'template:{network_alert_template.id}'

        with pytest.raises(ValidationError) as exc_info:
            wallet_alert_group.validate_alert_group_members([member_key])

        error_str = str(exc_info.value)
        assert "doesn't match" in error_str
        assert "network" in error_str
        assert "wallet" in error_str

    def test_invalid_member_format(self, wallet_alert_group):
        """Adding non-template member key to AlertGroup fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            wallet_alert_group.validate_alert_group_members(['wallet:0x123'])

        assert "template:{uuid}" in str(exc_info.value)

    def test_invalid_member_uuid_not_found(self, wallet_alert_group):
        """Adding non-existent AlertTemplate fails validation."""
        fake_uuid = str(uuid4())
        member_key = f'template:{fake_uuid}'

        with pytest.raises(ValidationError) as exc_info:
            wallet_alert_group.validate_alert_group_members([member_key])

        assert "AlertTemplate not found" in str(exc_info.value)

    def test_bulk_validation_all_valid(
        self, user, wallet_alert_group
    ):
        """Bulk add with all valid members succeeds."""
        from app.models.alert_templates import AlertTemplate

        # Create multiple wallet templates
        alerts = [
            AlertTemplate.objects.create(
                fingerprint=f"sha256:{i:064x}",
                created_by=user,
                target_kind=AlertType.WALLET,
                name=f'Wallet Template {i}',
                description=f'Wallet template {i} for balance monitoring',
            )
            for i in range(3)
        ]

        member_keys = [f'template:{alert.id}' for alert in alerts]

        # This should not raise
        wallet_alert_group.validate_alert_group_members(member_keys)

    def test_bulk_validation_partial_failure(
        self, wallet_alert_group, wallet_alert_template, network_alert_template
    ):
        """Bulk add with some invalid members fails all validation."""
        member_keys = [
            f'template:{wallet_alert_template.id}',   # Valid - wallet type
            f'template:{network_alert_template.id}'   # Invalid - network type
        ]

        with pytest.raises(ValidationError):
            wallet_alert_group.validate_alert_group_members(member_keys)

    def test_validation_skipped_for_non_alert_groups(
        self, user, wallet_group, wallet_alert_template
    ):
        """Non-AlertGroups skip member validation (allow any key format)."""
        # WalletGroups should not validate member key format
        # This tests that validation only applies to AlertGroups
        wallet_group.validate_alert_group_members(['any:key:format'])
        # Should not raise - validation is skipped for non-AlertGroups

    def test_network_alert_to_network_group_valid(
        self, network_alert_group, network_alert_template
    ):
        """Adding network template to network AlertGroup succeeds."""
        member_key = f'template:{network_alert_template.id}'

        # Should not raise
        network_alert_group.validate_alert_group_members([member_key])

    def test_protocol_alert_to_protocol_group_valid(
        self, protocol_alert_group, protocol_alert_template
    ):
        """Adding protocol template to protocol AlertGroup succeeds."""
        member_key = f'template:{protocol_alert_template.id}'

        # Should not raise
        protocol_alert_group.validate_alert_group_members([member_key])

    def test_network_alert_to_wallet_group_invalid(
        self, wallet_alert_group, network_alert_template
    ):
        """Adding network template to wallet AlertGroup fails."""
        member_key = f'template:{network_alert_template.id}'

        with pytest.raises(ValidationError) as exc_info:
            wallet_alert_group.validate_alert_group_members([member_key])

        assert "doesn't match" in str(exc_info.value)

    def test_alert_group_missing_alert_type_setting(self, user):
        """AlertGroup without alert_type setting fails validation."""
        # Create group without going through normal validation
        # to test the member validation catches missing alert_type
        group = GenericGroup(
            group_type=GroupType.ALERT,
            name='Invalid AlertGroup',
            owner=user,
            settings={}  # Missing alert_type
        )
        # Note: Can't save due to model validation, so test method directly
        # by temporarily setting settings after construction

        with pytest.raises(ValidationError) as exc_info:
            group.validate_alert_group_members(['template:some-uuid'])

        assert "alert_type" in str(exc_info.value)
