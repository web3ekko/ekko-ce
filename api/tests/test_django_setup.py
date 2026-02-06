"""
Test Django setup and configuration
Validates that Django testing infrastructure is working correctly
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


@pytest.mark.django_db
class TestDjangoSetup:
    """Test Django configuration and setup"""
    
    def test_django_settings_configured(self):
        """Test that Django settings are properly configured"""
        assert settings.configured
        assert settings.SECRET_KEY
        assert 'authentication' in settings.INSTALLED_APPS
        assert 'blockchain' in settings.INSTALLED_APPS
        assert 'organizations' in settings.INSTALLED_APPS
    
    def test_custom_user_model(self):
        """Test that custom user model is configured"""
        assert User._meta.get_field('email')
        assert User._meta.get_field('first_name')
        assert User._meta.get_field('last_name')
        assert User._meta.get_field('has_passkey')
        assert User._meta.get_field('has_2fa')
    
    def test_database_connection(self):
        """Test database connection works"""
        # This will fail if database connection is not working
        user_count = User.objects.count()
        assert user_count >= 0  # Should be 0 for fresh test database
    
    def test_user_creation(self):
        """Test creating a user"""
        user = User.objects.create_user(
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        assert user.email == "test@example.com"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert not user.has_passkey
        assert not user.has_2fa


class TestDjangoTestCase(TestCase):
    """Test using Django TestCase"""
    
    def test_django_test_case_works(self):
        """Test that Django TestCase works"""
        user = User.objects.create_user(
            email="testcase@example.com",
            first_name="TestCase",
            last_name="User"
        )
        self.assertEqual(user.email, "testcase@example.com")
        self.assertFalse(user.has_passkey)


@pytest.mark.factories
@pytest.mark.django_db
class TestFactories:
    """Test that our factories work correctly"""
    
    def test_import_factories(self):
        """Test that factories can be imported"""
        from tests.factories import UserFactory, BlockchainFactory, OrganizationFactory
        
        # Test that factories exist
        assert UserFactory
        assert BlockchainFactory
        assert OrganizationFactory
    
    def test_user_factory(self):
        """Test UserFactory creates valid users"""
        from tests.factories import UserFactory
        
        user = UserFactory()
        assert user.email
        assert user.first_name
        assert user.last_name
        assert isinstance(user.has_passkey, bool)
        assert isinstance(user.has_2fa, bool)
    
    def test_blockchain_factory(self):
        """Test BlockchainFactory creates valid blockchains"""
        from tests.factories import BlockchainFactory
        
        blockchain = BlockchainFactory()
        assert blockchain.name
        assert blockchain.symbol
        assert blockchain.chain_type
    
    def test_organization_factory(self):
        """Test OrganizationFactory creates valid organizations"""
        from tests.factories import OrganizationFactory
        
        org = OrganizationFactory()
        assert org.name
        assert org.slug
        assert isinstance(org.max_teams, int)
        assert isinstance(org.max_users_per_team, int)


@pytest.mark.integration
@pytest.mark.django_db
class TestModelIntegration:
    """Test model integration and relationships"""
    
    def test_user_device_relationship(self):
        """Test User-UserDevice relationship"""
        from tests.factories import UserFactory, UserDeviceFactory
        
        user = UserFactory()
        device = UserDeviceFactory(user=user)
        
        assert device.user == user
        assert device in user.devices.all()
    
    def test_wallet_blockchain_relationship(self):
        """Test Wallet-Blockchain relationship"""
        from tests.factories import BlockchainFactory, WalletFactory
        
        blockchain = BlockchainFactory()
        wallet = WalletFactory(blockchain=blockchain)
        
        assert wallet.blockchain == blockchain
        assert wallet in blockchain.wallets.all()
    
    def test_team_organization_relationship(self):
        """Test Team-Organization relationship"""
        from tests.factories import OrganizationFactory, TeamFactory
        
        org = OrganizationFactory()
        team = TeamFactory(organization=org)
        
        assert team.organization == org
        assert team in org.teams.all()


@pytest.mark.slow
@pytest.mark.django_db
class TestComplexFactories:
    """Test complex factory scenarios"""
    
    def test_complete_auth_setup(self):
        """Test creating complete authentication setup"""
        from tests.factories.auth_factories import create_complete_auth_setup
        
        auth_setup = create_complete_auth_setup()
        
        assert 'user' in auth_setup
        assert 'device' in auth_setup
        assert 'passkey' in auth_setup
        assert 'recovery_codes' in auth_setup
        
        user = auth_setup['user']
        assert user.has_passkey
        assert user.has_2fa
        assert len(auth_setup['recovery_codes']) == 10
    
    def test_organization_structure(self):
        """Test creating complete organization structure"""
        from tests.factories.organization_factories import create_complete_organization_structure
        
        org_structure = create_complete_organization_structure()
        
        assert 'organization' in org_structure
        assert 'teams' in org_structure
        assert 'members' in org_structure
        
        org = org_structure['organization']
        teams = org_structure['teams']
        members = org_structure['members']
        
        assert len(teams) == 3
        assert len(members) > 0
        
        # Verify all teams belong to the organization
        for team in teams:
            assert team.organization == org
    
    def test_blockchain_ecosystem(self):
        """Test creating blockchain ecosystem"""
        from tests.factories.blockchain_factories import create_blockchain_ecosystem
        
        ecosystem = create_blockchain_ecosystem("Ethereum")
        
        assert 'blockchain' in ecosystem
        assert 'tokens' in ecosystem
        assert 'wallets' in ecosystem
        assert 'daos' in ecosystem
        
        blockchain = ecosystem['blockchain']
        assert blockchain.name == "Ethereum"
        assert len(ecosystem['tokens']) == 2
        assert len(ecosystem['wallets']) == 3
        assert len(ecosystem['daos']) == 2
