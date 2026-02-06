"""
Unit tests for AlertInstance target_keys and DefaultNetworkAlert models

Tests the enhanced AlertInstance with target_keys for fine-grained targeting,
and the DefaultNetworkAlert model for system-managed fallback alerts.
"""

import pytest
import uuid
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from app.models.alerts import AlertInstance, DefaultNetworkAlert
from app.models.alert_templates import AlertTemplate
from app.models.groups import GenericGroup, GroupType, AlertType
from blockchain.models import Chain

User = get_user_model()


# ===================================================================
# Test Fixtures
# ===================================================================

@pytest.fixture
def test_user(db):
    """Create a test user"""
    return User.objects.create_user(
        email='testuser@example.com',
        first_name='Test',
        last_name='User',
        password='testpass123'
    )


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
def ethereum_chain(db):
    """Create Ethereum chain for testing"""
    return Chain.objects.create(
        name='ethereum',
        display_name='Ethereum',
        chain_id=1,
        native_token='ETH',
        enabled=True
    )


@pytest.fixture
def solana_chain(db):
    """Create Solana chain for testing"""
    return Chain.objects.create(
        name='solana',
        display_name='Solana',
        chain_id=101,
        native_token='SOL',
        enabled=True
    )


@pytest.fixture
def public_alert_template(db, test_user):
    """Create a public alert template (vNext identity only)."""
    return AlertTemplate.objects.create(
        fingerprint="sha256:" + "a" * 64,
        name="All Transactions Template",
        description="Default template for all transactions",
        target_kind="wallet",
        is_public=True,
        is_verified=True,
        created_by=test_user,
    )


@pytest.fixture
def private_alert_template(db, test_user):
    """Create a private alert template (vNext identity only)."""
    return AlertTemplate.objects.create(
        fingerprint="sha256:" + "b" * 64,
        name="Private Template",
        description="Private template",
        target_kind="wallet",
        is_public=False,
        is_verified=False,
        created_by=test_user,
    )


@pytest.fixture
def wallet_group(db, test_user):
    """Create a wallet group with members"""
    group = GenericGroup.objects.create(
        name="Test Wallet Group",
        group_type=GroupType.WALLET,
        owner=test_user,
        member_data={
            "members": {
                "ETH:mainnet:0x1234567890abcdef": {"label": "Main Wallet"},
                "ETH:mainnet:0xfedcba0987654321": {"label": "Backup Wallet"},
                "SOL:mainnet:ABC123xyz": {"label": "SOL Wallet"}
            }
        },
        member_count=3
    )
    return group


@pytest.fixture
def network_group(db, test_user):
    """Create a network group"""
    group = GenericGroup.objects.create(
        name="Test Network Group",
        group_type=GroupType.NETWORK,
        owner=test_user,
        member_data={
            "members": {
                "ETH:mainnet": {"enabled": True},
                "ETH:goerli": {"enabled": True}
            }
        },
        member_count=2
    )
    return group


@pytest.fixture
def sample_alert_instance(db, test_user, public_alert_template):
    """Create a sample alert instance"""
    return AlertInstance.objects.create(
        name="Test Alert",
        nl_description="Test alert for wallet monitoring",
        template=public_alert_template,
        template_version=1,
        template_params={"wallet": "0x123", "chain": "ethereum"},
        event_type="ASSET_EVENT",
        sub_event="TOKEN_TRANSFER",
        alert_type=AlertType.WALLET,
        user=test_user,
        enabled=True
    )


# ===================================================================
# AlertInstance Target Keys Tests
# ===================================================================

@pytest.mark.django_db
class TestAlertInstanceTargetKeys:
    """Tests for AlertInstance.target_keys functionality"""

    def test_target_keys_default_is_empty_list(self, test_user, public_alert_template):
        """Test that target_keys defaults to empty list"""
        alert = AlertInstance.objects.create(
            name="Test Alert",
            nl_description="Test",
            template=public_alert_template,
            template_params={"wallet": "0x123"},
            event_type="ASSET_EVENT",
            sub_event="TOKEN_TRANSFER",
            user=test_user
        )
        assert alert.target_keys == []

    def test_target_keys_can_be_set(self, test_user, public_alert_template):
        """Test that target_keys can be set on creation"""
        target_keys = ["ETH:mainnet:0x1234", "ETH:mainnet:0x5678"]
        alert = AlertInstance.objects.create(
            name="Test Alert",
            nl_description="Test",
            template=public_alert_template,
            template_params={"wallet": "0x123"},
            event_type="ASSET_EVENT",
            sub_event="TOKEN_TRANSFER",
            target_keys=target_keys,
            user=test_user
        )
        assert alert.target_keys == target_keys

    def test_validate_target_keys_valid_wallet_format(self, sample_alert_instance):
        """Test validation passes for valid wallet key format"""
        sample_alert_instance.alert_type = AlertType.WALLET
        sample_alert_instance.target_keys = [
            "ETH:mainnet:0x1234567890abcdef",
            "SOL:mainnet:ABC123xyz"
        ]
        # Should not raise
        sample_alert_instance.validate_target_keys_format()

    def test_validate_target_keys_valid_network_format(self, sample_alert_instance):
        """Test validation passes for valid network key format"""
        sample_alert_instance.alert_type = AlertType.NETWORK
        sample_alert_instance.target_keys = [
            "ETH:mainnet",
            "SOL:devnet"
        ]
        # Should not raise
        sample_alert_instance.validate_target_keys_format()

    def test_validate_target_keys_valid_protocol_format(self, sample_alert_instance):
        """Test validation passes for valid protocol key format"""
        sample_alert_instance.alert_type = AlertType.PROTOCOL
        sample_alert_instance.target_keys = [
            "ETH:mainnet:aave-v3",
            "SOL:mainnet:orca",
        ]
        # Should not raise
        sample_alert_instance.validate_target_keys_format()

    def test_validate_target_keys_invalid_wallet_format(self, sample_alert_instance):
        """Test validation fails for invalid wallet key format (missing address)"""
        sample_alert_instance.alert_type = AlertType.WALLET
        sample_alert_instance.target_keys = ["ETH:mainnet"]  # Missing address part

        with pytest.raises(ValidationError) as exc_info:
            sample_alert_instance.validate_target_keys_format()
        assert "must be in format 'network:subnet:address'" in str(exc_info.value)

    def test_validate_target_keys_invalid_network_format(self, sample_alert_instance):
        """Test validation fails for invalid network key format"""
        sample_alert_instance.alert_type = AlertType.NETWORK
        sample_alert_instance.target_keys = ["ETH"]  # Missing network part

        with pytest.raises(ValidationError) as exc_info:
            sample_alert_instance.validate_target_keys_format()
        assert "must be in format 'network:subnet'" in str(exc_info.value)

    def test_validate_target_keys_invalid_protocol_format(self, sample_alert_instance):
        """Test validation fails for invalid protocol key format"""
        sample_alert_instance.alert_type = AlertType.PROTOCOL
        sample_alert_instance.target_keys = ["ETH:mainnet"]  # Missing protocol part

        with pytest.raises(ValidationError) as exc_info:
            sample_alert_instance.validate_target_keys_format()
        assert "Protocol key" in str(exc_info.value)

    def test_validate_target_keys_not_list(self, sample_alert_instance):
        """Test validation fails when target_keys is not a list"""
        sample_alert_instance.target_keys = "ETH:mainnet:0x123"  # String instead of list

        with pytest.raises(ValidationError) as exc_info:
            sample_alert_instance.validate_target_keys_format()
        assert "must be a list" in str(exc_info.value)

    def test_validate_target_keys_non_string_element(self, sample_alert_instance):
        """Test validation fails when target_keys contains non-string element"""
        sample_alert_instance.target_keys = ["ETH:mainnet:0x123", 12345]

        with pytest.raises(ValidationError) as exc_info:
            sample_alert_instance.validate_target_keys_format()
        assert "must be a string" in str(exc_info.value)

    def test_validate_target_keys_empty_list_is_valid(self, sample_alert_instance):
        """Test that empty target_keys list is valid"""
        sample_alert_instance.target_keys = []
        # Should not raise
        sample_alert_instance.validate_target_keys_format()


@pytest.mark.django_db
class TestAlertInstanceGetEffectiveTargets:
    """Tests for AlertInstance.get_effective_targets() method"""

    def test_get_effective_targets_from_target_keys(self, sample_alert_instance):
        """Test get_effective_targets returns target_keys when set"""
        sample_alert_instance.target_keys = [
            "ETH:mainnet:0x1234",
            "ETH:mainnet:0x5678"
        ]

        targets = sample_alert_instance.get_effective_targets()
        assert targets == ["ETH:mainnet:0x1234", "ETH:mainnet:0x5678"]

    def test_get_effective_targets_from_group(self, sample_alert_instance, wallet_group):
        """Test get_effective_targets returns group members when no target_keys"""
        sample_alert_instance.target_keys = []
        sample_alert_instance.target_group = wallet_group
        sample_alert_instance.save()

        targets = sample_alert_instance.get_effective_targets()
        assert len(targets) == 3
        assert "ETH:mainnet:0x1234567890abcdef" in targets
        assert "ETH:mainnet:0xfedcba0987654321" in targets
        assert "SOL:mainnet:ABC123xyz" in targets

    def test_get_effective_targets_keys_override_group(self, sample_alert_instance, wallet_group):
        """Test that target_keys takes precedence over target_group"""
        sample_alert_instance.target_keys = ["ETH:mainnet:0xONLY_THIS_ONE"]
        sample_alert_instance.target_group = wallet_group
        sample_alert_instance.save()

        targets = sample_alert_instance.get_effective_targets()
        # Should return target_keys, not group members
        assert targets == ["ETH:mainnet:0xONLY_THIS_ONE"]

    def test_get_effective_targets_no_targets(self, sample_alert_instance):
        """Test get_effective_targets returns empty list when no targets"""
        sample_alert_instance.target_keys = []
        sample_alert_instance.target_group = None
        sample_alert_instance.save()

        targets = sample_alert_instance.get_effective_targets()
        assert targets == []


@pytest.mark.django_db
class TestAlertInstanceHasExplicitTargets:
    """Tests for AlertInstance.has_explicit_targets() method"""

    def test_has_explicit_targets_with_keys(self, sample_alert_instance):
        """Test has_explicit_targets returns True when target_keys set"""
        sample_alert_instance.target_keys = ["ETH:mainnet:0x123"]
        assert sample_alert_instance.has_explicit_targets() is True

    def test_has_explicit_targets_with_group(self, sample_alert_instance, wallet_group):
        """Test has_explicit_targets returns True when target_group set"""
        sample_alert_instance.target_keys = []
        sample_alert_instance.target_group = wallet_group
        assert sample_alert_instance.has_explicit_targets() is True

    def test_has_explicit_targets_with_both(self, sample_alert_instance, wallet_group):
        """Test has_explicit_targets returns True when both set"""
        sample_alert_instance.target_keys = ["ETH:mainnet:0x123"]
        sample_alert_instance.target_group = wallet_group
        assert sample_alert_instance.has_explicit_targets() is True

    def test_has_explicit_targets_with_neither(self, sample_alert_instance):
        """Test has_explicit_targets returns False when neither set"""
        sample_alert_instance.target_keys = []
        sample_alert_instance.target_group = None
        assert sample_alert_instance.has_explicit_targets() is False


@pytest.mark.django_db
class TestAlertInstanceTargetGroupValidation:
    """Tests for AlertInstance.validate_target_group_type() method"""

    def test_wallet_alert_with_wallet_group_valid(self, sample_alert_instance, wallet_group):
        """Test wallet alert can target wallet group"""
        sample_alert_instance.alert_type = AlertType.WALLET
        sample_alert_instance.target_group = wallet_group
        # Should not raise
        sample_alert_instance.validate_target_group_type()

    def test_wallet_alert_with_network_group_invalid(self, sample_alert_instance, network_group):
        """Test wallet alert cannot target network group"""
        sample_alert_instance.alert_type = AlertType.WALLET
        sample_alert_instance.target_group = network_group

        with pytest.raises(ValidationError) as exc_info:
            sample_alert_instance.validate_target_group_type()
        assert "requires target group of type" in str(exc_info.value)

    def test_network_alert_with_network_group_valid(self, sample_alert_instance, network_group):
        """Test network alert can target network group"""
        sample_alert_instance.alert_type = AlertType.NETWORK
        sample_alert_instance.target_group = network_group
        # Should not raise
        sample_alert_instance.validate_target_group_type()

    def test_alert_without_target_group_valid(self, sample_alert_instance):
        """Test alert without target group is valid"""
        sample_alert_instance.target_group = None
        # Should not raise for any alert type
        sample_alert_instance.validate_target_group_type()


# ===================================================================
# DefaultNetworkAlert Model Tests
# ===================================================================

@pytest.mark.django_db
class TestDefaultNetworkAlertModel:
    """Tests for DefaultNetworkAlert model"""

    def test_create_default_network_alert(self, ethereum_chain, public_alert_template):
        """Test creating a default network alert"""
        default_alert = DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template,
            enabled=True,
            settings={'default_priority': 'normal'}
        )

        assert default_alert.id is not None
        assert default_alert.chain == ethereum_chain
        assert default_alert.subnet == 'mainnet'
        assert default_alert.alert_template == public_alert_template
        assert default_alert.enabled is True
        assert default_alert.settings == {'default_priority': 'normal'}

    def test_default_network_alert_str(self, ethereum_chain, public_alert_template):
        """Test string representation"""
        default_alert = DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template
        )

        expected = f"Default Alert: {ethereum_chain.display_name} (mainnet)"
        assert str(default_alert) == expected

    def test_unique_constraint_chain_subnet(self, ethereum_chain, public_alert_template):
        """Test unique together constraint on chain + subnet"""
        DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template
        )

        # Create another template for the second alert
        another_template = AlertTemplate.objects.create(
            fingerprint="sha256:" + "c" * 64,
            name="Another Template",
            description="Another template",
            target_kind="wallet",
            is_public=True,
            created_by=public_alert_template.created_by,
        )

        with pytest.raises(IntegrityError):
            DefaultNetworkAlert.objects.create(
                chain=ethereum_chain,
                subnet='mainnet',  # Same chain + subnet
                alert_template=another_template
            )

    def test_different_subnet_allowed(self, ethereum_chain, public_alert_template, test_user):
        """Test that same chain with different subnet is allowed"""
        # Create mainnet default
        mainnet_default = DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template
        )

        # Create another template for testnet
        testnet_template = AlertTemplate.objects.create(
            fingerprint="sha256:" + "d" * 64,
            name="Testnet Template",
            description="Testnet template",
            target_kind="wallet",
            is_public=True,
            created_by=test_user,
        )

        # Create testnet default - should succeed
        testnet_default = DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='goerli',  # Different subnet
            alert_template=testnet_template
        )

        assert mainnet_default.subnet == 'mainnet'
        assert testnet_default.subnet == 'goerli'


@pytest.mark.django_db
class TestDefaultNetworkAlertValidation:
    """Tests for DefaultNetworkAlert validation"""

    def test_requires_public_template(self, ethereum_chain, private_alert_template):
        """Test that validation fails for non-public template"""
        default_alert = DefaultNetworkAlert(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=private_alert_template
        )

        with pytest.raises(ValidationError) as exc_info:
            default_alert.clean()
        assert "must use a public template" in str(exc_info.value)

    def test_public_template_passes_validation(self, ethereum_chain, public_alert_template):
        """Test that validation passes for public template"""
        default_alert = DefaultNetworkAlert(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template
        )
        # Should not raise
        default_alert.clean()


@pytest.mark.django_db
class TestDefaultNetworkAlertClassMethods:
    """Tests for DefaultNetworkAlert class methods"""

    def test_get_for_chain_exists(self, ethereum_chain, public_alert_template):
        """Test get_for_chain returns alert when it exists"""
        DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template,
            enabled=True
        )

        result = DefaultNetworkAlert.get_for_chain('ethereum', 'mainnet')

        assert result is not None
        assert result.chain == ethereum_chain
        assert result.subnet == 'mainnet'

    def test_get_for_chain_not_found(self, ethereum_chain, public_alert_template):
        """Test get_for_chain returns None when not found"""
        # Don't create any default alert
        result = DefaultNetworkAlert.get_for_chain('nonexistent', 'mainnet')
        assert result is None

    def test_get_for_chain_disabled(self, ethereum_chain, public_alert_template):
        """Test get_for_chain returns None for disabled alert"""
        DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template,
            enabled=False  # Disabled
        )

        result = DefaultNetworkAlert.get_for_chain('ethereum', 'mainnet')
        assert result is None

    def test_get_for_chain_different_subnet(self, ethereum_chain, public_alert_template):
        """Test get_for_chain returns None for different subnet"""
        DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template,
            enabled=True
        )

        result = DefaultNetworkAlert.get_for_chain('ethereum', 'goerli')
        assert result is None

    def test_get_fallback_template_exists(self, ethereum_chain, public_alert_template):
        """Test get_fallback_template returns template when alert exists"""
        DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template,
            enabled=True
        )

        result = DefaultNetworkAlert.get_fallback_template('ethereum', 'mainnet')

        assert result is not None
        assert result == public_alert_template

    def test_get_fallback_template_not_found(self):
        """Test get_fallback_template returns None when not found"""
        result = DefaultNetworkAlert.get_fallback_template('nonexistent', 'mainnet')
        assert result is None

    def test_get_for_chain_default_subnet(self, ethereum_chain, public_alert_template):
        """Test get_for_chain uses mainnet as default subnet"""
        DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template,
            enabled=True
        )

        # Call without specifying subnet
        result = DefaultNetworkAlert.get_for_chain('ethereum')

        assert result is not None
        assert result.subnet == 'mainnet'


@pytest.mark.django_db
class TestDefaultNetworkAlertSettings:
    """Tests for DefaultNetworkAlert settings field"""

    def test_settings_default_empty_dict(self, ethereum_chain, public_alert_template):
        """Test settings defaults to empty dict"""
        default_alert = DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template
        )

        assert default_alert.settings == {}

    def test_settings_with_custom_values(self, ethereum_chain, public_alert_template):
        """Test settings can store custom values"""
        settings = {
            'default_priority': 'high',
            'cooldown_minutes': 10,
            'max_notifications_per_hour': 50
        }

        default_alert = DefaultNetworkAlert.objects.create(
            chain=ethereum_chain,
            subnet='mainnet',
            alert_template=public_alert_template,
            settings=settings
        )

        assert default_alert.settings['default_priority'] == 'high'
        assert default_alert.settings['cooldown_minutes'] == 10
        assert default_alert.settings['max_notifications_per_hour'] == 50
