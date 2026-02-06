"""
API tests for GenericGroup and GroupSubscription endpoints.

Tests cover:
- Group CRUD operations
- Member add/remove operations
- Group type filtering
- Subscription CRUD
- Permission enforcement
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from app.models.alerts import AlertInstance
from app.models.groups import GenericGroup, GroupSubscription, GroupType
from tests.factories import UserFactory, AlertTemplateFactory
from tests.factories.group_factories import (
    GenericGroupFactory,
    WalletGroupFactory,
    AlertGroupFactory,
    NetworkGroupFactory,
    GroupSubscriptionFactory,
    create_group_with_members,
)


@pytest.mark.django_db
class TestGenericGroupViewSet:
    """Tests for GenericGroup API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.client.force_authenticate(user=self.user)

    # -------------------------------------------------------------------------
    # List Groups
    # -------------------------------------------------------------------------

    def test_list_groups_empty(self):
        """Test listing groups when user has none."""
        url = reverse('alerts:groups-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['my_groups']['count'] == 0
        assert response.data['my_groups']['results'] == []
        assert response.data['public_groups']['count'] == 0
        assert response.data['public_groups']['results'] == []

    def test_list_groups_returns_user_groups_only(self):
        """Test that users can only see their own groups."""
        # Create groups for both users
        user_group = WalletGroupFactory(owner=self.user)
        other_group = WalletGroupFactory(owner=self.other_user)

        url = reverse('alerts:groups-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['my_groups']['count'] == 1
        assert str(response.data['my_groups']['results'][0]['id']) == str(user_group.id)
        assert response.data['public_groups']['count'] == 0

    def test_list_groups_excludes_public_groups(self):
        """My groups list excludes public groups owned by others."""
        WalletGroupFactory(owner=self.user)
        public_group = WalletGroupFactory(owner=self.other_user, settings={'visibility': 'public'})

        url = reverse('alerts:groups-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {row['id'] for row in response.data['my_groups']['results']}
        assert str(public_group.id) not in returned_ids
        public_ids = {row['id'] for row in response.data['public_groups']['results']}
        assert str(public_group.id) in public_ids

    def test_list_public_groups_includes_public_groups_owned_by_others(self):
        """Public groups list includes all public groups, including ones you own."""
        own_public_group = WalletGroupFactory(owner=self.user, settings={'visibility': 'public'})
        public_group = WalletGroupFactory(owner=self.other_user, settings={'visibility': 'public'})

        url = reverse('alerts:groups-public')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {row['id'] for row in response.data['results']}
        assert str(own_public_group.id) in returned_ids
        assert str(public_group.id) in returned_ids

    def test_list_groups_filterable_by_type(self):
        """Test filtering groups by type."""
        WalletGroupFactory(owner=self.user)
        WalletGroupFactory(owner=self.user)
        AlertGroupFactory(owner=self.user)

        url = reverse('alerts:groups-list')
        response = self.client.get(url, {'group_type': GroupType.WALLET})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['my_groups']['count'] == 2
        for group in response.data['my_groups']['results']:
            assert group['group_type'] == GroupType.WALLET

    def test_list_groups_searchable(self):
        """Test searching groups by name."""
        WalletGroupFactory(owner=self.user, name="Treasury Wallets")
        WalletGroupFactory(owner=self.user, name="Hot Wallets")
        WalletGroupFactory(owner=self.user, name="Other Group")

        url = reverse('alerts:groups-list')
        response = self.client.get(url, {'search': 'Wallets'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['my_groups']['count'] == 2

    # -------------------------------------------------------------------------
    # Create Group
    # -------------------------------------------------------------------------

    def test_create_group_minimal(self):
        """Test creating a group with minimal data."""
        url = reverse('alerts:groups-list')
        data = {
            'group_type': GroupType.WALLET,
            'name': 'My Wallets'
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'My Wallets'
        assert response.data['group_type'] == GroupType.WALLET
        group = GenericGroup.objects.get(id=response.data['id'])
        assert group.member_count == 0

    def test_create_group_with_initial_members(self):
        """Test creating a group with initial members."""
        url = reverse('alerts:groups-list')
        data = {
            'group_type': GroupType.WALLET,
            'name': 'My Wallets',
            'description': 'My personal wallets',
            'initial_members': [
                {'key': 'eth:MainNet:0xAbCdEf000000000000000000000000000000000000', 'label': 'Treasury'},
                {'key': 'ETH:mainnet:0x0987654321098765432109876543210987654321', 'label': 'Hot Wallet', 'tags': ['active']}
            ]
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        # Verify via database
        group = GenericGroup.objects.get(id=response.data['id'])
        assert group.member_count == 2
        assert 'ETH:mainnet:0xabcdef000000000000000000000000000000000000' in group.get_member_keys()

    def test_create_group_invalid_type(self):
        """Test creating a group with invalid type fails."""
        url = reverse('alerts:groups-list')
        data = {
            'group_type': 'invalid_type',
            'name': 'Bad Group'
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # -------------------------------------------------------------------------
    # Get Group
    # -------------------------------------------------------------------------

    def test_get_group_detail(self):
        """Test getting a specific group's details."""
        group = create_group_with_members(owner=self.user, member_count=3)

        url = reverse('alerts:groups-detail', args=[group.id])
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == group.name
        assert response.data['member_count'] == 3
        assert len(response.data['member_keys']) == 3

    def test_get_group_other_user_forbidden(self):
        """Test that users cannot access other users' groups."""
        group = WalletGroupFactory(owner=self.other_user)

        url = reverse('alerts:groups-detail', args=[group.id])
        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_public_group_visible(self):
        """Test that users can access public groups owned by others."""
        group = WalletGroupFactory(owner=self.other_user, settings={'visibility': 'public'})

        url = reverse('alerts:groups-detail', args=[group.id])
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(group.id)

    # -------------------------------------------------------------------------
    # Update Group
    # -------------------------------------------------------------------------

    def test_update_group(self):
        """Test updating a group."""
        group = WalletGroupFactory(owner=self.user, name='Old Name')

        url = reverse('alerts:groups-detail', args=[group.id])
        data = {'name': 'New Name', 'description': 'Updated description'}
        response = self.client.patch(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'New Name'
        assert response.data['description'] == 'Updated description'

    # -------------------------------------------------------------------------
    # Delete Group
    # -------------------------------------------------------------------------

    def test_delete_group(self):
        """Test deleting a group."""
        group = WalletGroupFactory(owner=self.user)
        group_id = group.id

        url = reverse('alerts:groups-detail', args=[group.id])
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not GenericGroup.objects.filter(id=group_id).exists()

    # -------------------------------------------------------------------------
    # Add Members
    # -------------------------------------------------------------------------

    def test_add_members(self):
        """Test adding members to a group."""
        group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:groups-add-members', args=[group.id])
        data = {
            'members': [
                {'member_key': 'ETH:mainnet:0x1234567890123456789012345678901234567890', 'label': 'Wallet 1'},
                {'member_key': 'ETH:mainnet:0x0987654321098765432109876543210987654321', 'label': 'Wallet 2'}
            ]
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['added'] == 2
        assert response.data['total_members'] == 2

    def test_add_members_normalizes_wallet_keys(self):
        """Test that wallet keys are normalized on add."""
        group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:groups-add-members', args=[group.id])
        data = {
            'members': [
                {'member_key': 'eth:MainNet:0xAbCdEf000000000000000000000000000000000000', 'label': 'Wallet 1'},
            ]
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        group.refresh_from_db()
        assert group.has_member('ETH:mainnet:0xabcdef000000000000000000000000000000000000')

    def test_add_members_alert_group_requires_templates(self):
        """Test that AlertGroup members must be template:{uuid}."""
        alert_group = AlertGroupFactory(owner=self.user, settings={'alert_type': 'wallet'})
        template = AlertTemplateFactory(alert_type='wallet')

        url = reverse('alerts:groups-add-members', args=[alert_group.id])
        response = self.client.post(
            url,
            {'members': [{'member_key': f'template:{template.id}'}]},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        alert_group.refresh_from_db()
        assert alert_group.has_member(f'template:{str(template.id).lower()}')

    def test_add_members_alert_group_rejects_wrong_alert_type(self):
        """Test that AlertGroup rejects templates with mismatched alert_type."""
        alert_group = AlertGroupFactory(owner=self.user, settings={'alert_type': 'wallet'})
        template = AlertTemplateFactory(alert_type='network')

        url = reverse('alerts:groups-add-members', args=[alert_group.id])
        response = self.client.post(
            url,
            {'members': [{'member_key': f'template:{template.id}'}]},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'members' in response.data

    def test_add_members_alert_group_requires_same_required_variable_set(self):
        """AlertGroups require all templates share the same required (non-targeting) variables."""
        alert_group = AlertGroupFactory(owner=self.user, settings={'alert_type': 'wallet'})

        template_a = AlertTemplateFactory(
            alert_type='wallet',
            event_type='ACCOUNT_EVENT',
            variables=[
                {"name": "wallet", "type": "address", "required": True},
                {"name": "threshold", "type": "uint256", "required": True},
            ],
        )
        template_b = AlertTemplateFactory(
            alert_type='wallet',
            event_type='ACCOUNT_EVENT',
            variables=[
                {"name": "wallet", "type": "address", "required": True},
                {"name": "min_amount", "type": "uint256", "required": True},
            ],
        )

        url = reverse('alerts:groups-add-members', args=[alert_group.id])

        response = self.client.post(
            url,
            {'members': [{'member_key': f'template:{template_a.id}'}]},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

        response = self.client.post(
            url,
            {'members': [{'member_key': f'template:{template_b.id}'}]},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'members' in response.data

    def test_add_members_alert_group_requires_same_template_type(self):
        """AlertGroups require all templates share the same derived template_type (event_type)."""
        alert_group = AlertGroupFactory(owner=self.user, settings={'alert_type': 'wallet'})

        template_a = AlertTemplateFactory(
            alert_type='wallet',
            event_type='ACCOUNT_EVENT',
            variables=[
                {"name": "wallet", "type": "address", "required": True},
                {"name": "threshold", "type": "uint256", "required": True},
            ],
        )
        template_b = AlertTemplateFactory(
            alert_type='wallet',
            event_type='PROTOCOL_EVENT',
            variables=[
                {"name": "wallet", "type": "address", "required": True},
                {"name": "threshold", "type": "uint256", "required": True},
            ],
        )

        url = reverse('alerts:groups-add-members', args=[alert_group.id])

        response = self.client.post(
            url,
            {'members': [{'member_key': f'template:{template_a.id}'}]},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

        response = self.client.post(
            url,
            {'members': [{'member_key': f'template:{template_b.id}'}]},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'members' in response.data

    def test_add_duplicate_members(self):
        """Test that adding duplicate members returns already_exists."""
        group = WalletGroupFactory(owner=self.user)
        existing_key = 'ETH:mainnet:0x1234567890123456789012345678901234567890'
        group.add_member_local(member_key=existing_key)

        url = reverse('alerts:groups-add-members', args=[group.id])
        data = {
            'members': [
                {'member_key': existing_key},
                {'member_key': 'ETH:mainnet:0x0987654321098765432109876543210987654321'}
            ]
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['added'] == 1
        assert existing_key in response.data['already_exists']

    # -------------------------------------------------------------------------
    # Remove Members
    # -------------------------------------------------------------------------

    def test_remove_members(self):
        """Test removing members from a group."""
        group = create_group_with_members(owner=self.user, member_count=3)
        keys = group.get_member_keys()

        url = reverse('alerts:groups-remove-members', args=[group.id])
        data = {
            'members': [{'member_key': keys[0]}]
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['removed'] == 1
        assert response.data['total_members'] == 2

    def test_remove_nonexistent_members(self):
        """Test removing non-existent members returns not_found."""
        group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:groups-remove-members', args=[group.id])
        data = {
            'members': [{'member_key': 'ETH:mainnet:0xnonexistent'}]
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['removed'] == 0
        assert 'ETH:mainnet:0xnonexistent' in response.data['not_found']

    # -------------------------------------------------------------------------
    # By Type Action
    # -------------------------------------------------------------------------

    def test_by_type_action(self):
        """Test filtering groups by type via action endpoint."""
        WalletGroupFactory(owner=self.user)
        WalletGroupFactory(owner=self.user)
        AlertGroupFactory(owner=self.user)

        url = reverse('alerts:groups-by-type')
        response = self.client.get(url, {'type': GroupType.WALLET})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_by_type_action_missing_param(self):
        """Test by_type action without type parameter."""
        url = reverse('alerts:groups-by-type')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'type parameter required' in response.data['error']

    def test_by_type_action_invalid_type(self):
        """Test by_type action with invalid type parameter."""
        url = reverse('alerts:groups-by-type')
        response = self.client.get(url, {'type': 'invalid'})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # -------------------------------------------------------------------------
    # Summary Action
    # -------------------------------------------------------------------------

    def test_summary_action(self):
        """Test group summary action."""
        WalletGroupFactory(owner=self.user)
        create_group_with_members(owner=self.user, group_type=GroupType.WALLET, member_count=5)
        AlertGroupFactory(owner=self.user)

        url = reverse('alerts:groups-summary')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert GroupType.WALLET in response.data
        assert response.data[GroupType.WALLET]['count'] == 2
        assert response.data[GroupType.WALLET]['total_members'] == 5

    # -------------------------------------------------------------------------
    # List Members Action
    # -------------------------------------------------------------------------

    def test_list_members_action(self):
        """Test listing members of a group."""
        group = create_group_with_members(owner=self.user, member_count=3)

        url = reverse('alerts:groups-list-members', args=[group.id])
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['member_count'] == 3
        assert len(response.data['members']) == 3

    # -------------------------------------------------------------------------
    # Accounts (My Wallets) Actions
    # -------------------------------------------------------------------------

    def test_accounts_get_missing_returns_404(self):
        """Accounts group should not exist until first wallet is added."""
        url = reverse('alerts:groups-accounts')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_accounts_add_wallet_creates_group_and_sets_owner_verified(self):
        """POST /groups/accounts/add_wallet lazily creates Accounts group and stores owner_verified."""
        url = reverse('alerts:groups-accounts-add-wallet')
        response = self.client.post(
            url,
            {
                'member_key': 'eth:MainNet:0xAbCdEf000000000000000000000000000000000000',
                'label': 'My Wallet',
                'owner_verified': True,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['created'] is True
        assert response.data['added'] is True
        assert response.data['wallet_id'] is not None

        accounts_url = reverse('alerts:groups-accounts')
        accounts_response = self.client.get(accounts_url)
        assert accounts_response.status_code == status.HTTP_200_OK
        assert accounts_response.data['settings']['system_key'] == 'accounts'
        assert accounts_response.data['settings']['visibility'] == 'private'

        member_key = 'ETH:mainnet:0xabcdef000000000000000000000000000000000000'
        members = accounts_response.data['member_data']['members']
        assert member_key in members
        assert members[member_key]['metadata']['owner_verified'] is True

        from blockchain.models import Wallet

        wallet = Wallet.objects.get(id=response.data['wallet_id'])
        assert wallet.blockchain_id == 'ETH'
        assert wallet.subnet == 'mainnet'
        assert wallet.address == '0xabcdef000000000000000000000000000000000000'


@pytest.mark.django_db
class TestAlertGroupTemplatesEndpoint:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_templates_endpoint_lists_group_templates(self):
        alert_group = AlertGroupFactory(owner=self.user, settings={'alert_type': 'network'})
        template = AlertTemplateFactory(created_by=self.user, event_type='PROTOCOL_EVENT')
        alert_group.add_member_local(
            member_key=f"template:{template.id}",
            added_by=str(self.user.id),
        )

        url = reverse('alerts:groups-templates', args=[alert_group.id])
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['alert_group_id'] == str(alert_group.id)
        assert response.data['templates'][0]['id'] == str(template.id)
        assert response.data['templates'][0]['template_type'] == 'network'
        assert isinstance(response.data['templates'][0]['variables'], list)


@pytest.mark.django_db
class TestGroupSubscriptionViewSet:
    """Tests for GroupSubscription API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.client.force_authenticate(user=self.user)

    # -------------------------------------------------------------------------
    # List Subscriptions
    # -------------------------------------------------------------------------

    def test_list_subscriptions_empty(self):
        """Test listing subscriptions when user has none."""
        url = reverse('alerts:subscriptions-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []

    def test_list_subscriptions_returns_user_subscriptions_only(self):
        """Test that users can only see their own subscriptions."""
        alert_group = AlertGroupFactory(owner=self.user)
        target_group = WalletGroupFactory(owner=self.user)
        user_subscription = GroupSubscriptionFactory(
            alert_group=alert_group,
            target_group=target_group,
            owner=self.user
        )

        other_alert = AlertGroupFactory(owner=self.other_user)
        other_target = WalletGroupFactory(owner=self.other_user)
        GroupSubscriptionFactory(
            alert_group=other_alert,
            target_group=other_target,
            owner=self.other_user
        )

        url = reverse('alerts:subscriptions-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert str(response.data['results'][0]['id']) == str(user_subscription.id)

    # -------------------------------------------------------------------------
    # Create Subscription
    # -------------------------------------------------------------------------

    def test_create_subscription(self):
        """Test creating a subscription."""
        alert_group = AlertGroupFactory(owner=self.user)
        target_group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:subscriptions-list')
        data = {
            'alert_group': str(alert_group.id),
            'target_group': str(target_group.id)
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert str(response.data['alert_group']) == str(alert_group.id)
        assert str(response.data['target_group']) == str(target_group.id)
        assert response.data['is_active'] is True

    def test_create_subscription_requires_template_params_when_group_has_templates(self):
        """Subscribing to a non-empty AlertGroup must include required params for its templates."""
        alert_group = AlertGroupFactory(owner=self.user)
        template = AlertTemplateFactory(created_by=self.user)
        alert_group.add_member_local(
            member_key=f"template:{template.id}",
            added_by=str(self.user.id),
        )
        target_group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {'alert_group': str(alert_group.id), 'target_group': str(target_group.id)},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'settings' in response.data

    def test_create_subscription_does_not_require_network_chain_subnet_template_params(self):
        """Network/chain/subnet variables are treated as targeting (not required template params)."""
        alert_group = AlertGroupFactory(owner=self.user)
        template = AlertTemplateFactory(
            created_by=self.user,
            event_type='ACCOUNT_EVENT',
            alert_type='wallet',
            variables=[
                {"name": "network", "type": "string", "required": True},
                {"name": "subnet", "type": "string", "required": True},
                {"name": "threshold", "type": "uint256", "required": True},
            ],
        )

        add_url = reverse('alerts:groups-add-members', args=[alert_group.id])
        add_resp = self.client.post(
            add_url,
            {'members': [{'member_key': f'template:{template.id}'}]},
            format='json',
        )
        assert add_resp.status_code == status.HTTP_200_OK

        target_group = WalletGroupFactory(owner=self.user)
        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_group': str(target_group.id),
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_subscription_materializes_enabled_alert_instances(self):
        """Subscribing to a wallet AlertGroup creates enabled AlertInstances by default."""
        alert_group = AlertGroupFactory(owner=self.user)
        template = AlertTemplateFactory(created_by=self.user)
        alert_group.add_member_local(
            member_key=f"template:{template.id}",
            added_by=str(self.user.id),
        )
        target_group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_group': str(target_group.id),
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data['id']

        instances = AlertInstance.objects.filter(source_subscription_id=subscription_id)
        assert instances.count() == 1

        instance = instances.first()
        assert instance is not None
        assert instance.enabled is True
        assert instance.template_id == template.id
        assert instance.target_group_id == target_group.id
        assert instance.template_params['threshold'] == 500

    def test_create_subscription_token_alert_group_requires_token_target_group(self):
        """Token-type AlertGroups can only target token groups or token keys."""
        alert_group = AlertGroupFactory(owner=self.user, settings={'alert_type': 'token'})
        template = AlertTemplateFactory(
            created_by=self.user,
            event_type='ASSET_EVENT',
            variables=[
                {"name": "token_address", "type": "address", "required": True},
                {"name": "threshold", "type": "uint256", "required": True},
            ],
        )

        add_url = reverse('alerts:groups-add-members', args=[alert_group.id])
        add_resp = self.client.post(
            add_url,
            {'members': [{'member_key': f'template:{template.id}'}]},
            format='json',
        )
        assert add_resp.status_code == status.HTTP_200_OK

        wrong_target_group = WalletGroupFactory(owner=self.user)
        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_group': str(wrong_target_group.id),
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'target_group' in response.data

        token_target_group = GenericGroupFactory(owner=self.user, group_type=GroupType.TOKEN)
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_group': str(token_target_group.id),
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_subscription_protocol_alert_group_requires_protocol_target_group(self):
        """Protocol-type AlertGroups can only target protocol groups or protocol keys."""
        alert_group = AlertGroupFactory(owner=self.user, settings={'alert_type': 'protocol'})
        template = AlertTemplateFactory(
            created_by=self.user,
            event_type='DEFI_EVENT',
            alert_type='protocol',
            variables=[
                {"name": "protocol", "type": "string", "required": True},
                {"name": "threshold", "type": "uint256", "required": True},
            ],
        )

        add_url = reverse('alerts:groups-add-members', args=[alert_group.id])
        add_resp = self.client.post(
            add_url,
            {'members': [{'member_key': f'template:{template.id}'}]},
            format='json',
        )
        assert add_resp.status_code == status.HTTP_200_OK

        wrong_target_group = WalletGroupFactory(owner=self.user)
        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_group': str(wrong_target_group.id),
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'target_group' in response.data

        protocol_target_group = GenericGroupFactory(owner=self.user, group_type=GroupType.PROTOCOL)
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_group': str(protocol_target_group.id),
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_subscription_with_target_key_materializes_enabled_alert_instances(self):
        """AlertGroup subscriptions can target a single wallet key (target_key)."""
        alert_group = AlertGroupFactory(owner=self.user)
        template = AlertTemplateFactory(created_by=self.user)
        alert_group.add_member_local(
            member_key=f"template:{template.id}",
            added_by=str(self.user.id),
        )

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_key': 'eth:MainNet:0xAbCdEf000000000000000000000000000000000000',
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data['id']

        instance = AlertInstance.objects.get(source_subscription_id=subscription_id)
        assert instance.enabled is True
        assert instance.target_group_id is None
        assert instance.target_keys == ['ETH:mainnet:0xabcdef000000000000000000000000000000000000']

    def test_create_subscription_with_protocol_target_key_materializes_enabled_alert_instances(self):
        """Protocol AlertGroup subscriptions can target a single protocol key (target_key)."""
        alert_group = AlertGroupFactory(owner=self.user, settings={'alert_type': 'protocol'})
        template = AlertTemplateFactory(
            created_by=self.user,
            event_type='DEFI_EVENT',
            alert_type='protocol',
            variables=[
                {"name": "protocol", "type": "string", "required": True},
                {"name": "threshold", "type": "uint256", "required": True},
            ],
        )
        alert_group.add_member_local(
            member_key=f"template:{template.id}",
            added_by=str(self.user.id),
        )

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_key': 'eth:MainNet:Aave-v3',
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data['id']

        instance = AlertInstance.objects.get(source_subscription_id=subscription_id)
        assert instance.enabled is True
        assert instance.target_group_id is None
        assert instance.target_keys == ['ETH:mainnet:aave-v3']

    def test_toggle_subscription_disables_and_reenables_instances(self):
        alert_group = AlertGroupFactory(owner=self.user)
        template = AlertTemplateFactory(created_by=self.user)
        alert_group.add_member_local(
            member_key=f"template:{template.id}",
            added_by=str(self.user.id),
        )
        target_group = WalletGroupFactory(owner=self.user)

        create_url = reverse('alerts:subscriptions-list')
        create_response = self.client.post(
            create_url,
            {
                'alert_group': str(alert_group.id),
                'target_group': str(target_group.id),
                'settings': {'template_params': {'threshold': 500}},
            },
            format='json',
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        subscription_id = create_response.data['id']

        instance = AlertInstance.objects.get(source_subscription_id=subscription_id)
        assert instance.enabled is True

        toggle_url = reverse('alerts:subscriptions-toggle', args=[subscription_id])
        response = self.client.post(toggle_url)
        assert response.status_code == status.HTTP_200_OK

        instance.refresh_from_db()
        assert instance.enabled is False
        assert instance.disabled_by_subscription is True

        response = self.client.post(toggle_url)
        assert response.status_code == status.HTTP_200_OK

        instance.refresh_from_db()
        assert instance.enabled is True
        assert instance.disabled_by_subscription is False

    def test_create_subscription_invalid_alert_group_type(self):
        """Test that subscription fails if alert_group is not ALERT type."""
        wallet_group = WalletGroupFactory(owner=self.user)  # Not ALERT type
        target_group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:subscriptions-list')
        data = {
            'alert_group': str(wallet_group.id),
            'target_group': str(target_group.id)
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'alert_group' in response.data

    def test_create_subscription_same_group_fails(self):
        """Test that subscription fails if alert_group == target_group."""
        alert_group = AlertGroupFactory(owner=self.user)

        url = reverse('alerts:subscriptions-list')
        data = {
            'alert_group': str(alert_group.id),
            'target_group': str(alert_group.id)
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_duplicate_subscription_fails(self):
        """Test that duplicate subscriptions are rejected."""
        alert_group = AlertGroupFactory(owner=self.user)
        target_group = WalletGroupFactory(owner=self.user)
        GroupSubscriptionFactory(
            alert_group=alert_group,
            target_group=target_group,
            owner=self.user
        )

        url = reverse('alerts:subscriptions-list')
        data = {
            'alert_group': str(alert_group.id),
            'target_group': str(target_group.id)
        }
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_duplicate_target_key_subscription_fails(self):
        """Duplicate (owner, alert_group, target_key) subscriptions are rejected."""
        alert_group = AlertGroupFactory(owner=self.user)

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_key': 'ETH:mainnet:0xabcdef000000000000000000000000000000000000',
            },
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = self.client.post(
            url,
            {
                'alert_group': str(alert_group.id),
                'target_key': 'eth:MainNet:0xAbCdEf000000000000000000000000000000000000',
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_subscription_can_target_public_group_owned_by_other_user(self):
        """Target group can be public and owned by another user."""
        alert_group = AlertGroupFactory(owner=self.user)
        public_target_group = WalletGroupFactory(owner=self.other_user, settings={'visibility': 'public'})

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {'alert_group': str(alert_group.id), 'target_group': str(public_target_group.id)},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_subscription_rejects_private_group_owned_by_other_user(self):
        """Target group cannot be private and owned by another user."""
        alert_group = AlertGroupFactory(owner=self.user)
        private_target_group = WalletGroupFactory(owner=self.other_user)  # private by default

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {'alert_group': str(alert_group.id), 'target_group': str(private_target_group.id)},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'target_group' in response.data

    def test_create_subscription_to_public_alert_group_owned_by_other_user(self):
        """Alert group can be public and owned by another user."""
        public_alert_group = AlertGroupFactory(owner=self.other_user, settings={'alert_type': 'wallet', 'visibility': 'public'})
        target_group = WalletGroupFactory(owner=self.user)

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {'alert_group': str(public_alert_group.id), 'target_group': str(target_group.id)},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_subscription_uniqueness_is_per_owner(self):
        """Two different owners can subscribe to the same (alert_group, target_group)."""
        public_alert_group = AlertGroupFactory(owner=self.other_user, settings={'alert_type': 'wallet', 'visibility': 'public'})
        public_target_group = WalletGroupFactory(owner=self.other_user, settings={'visibility': 'public'})
        GroupSubscriptionFactory(
            alert_group=public_alert_group,
            target_group=public_target_group,
            owner=self.other_user,
        )

        url = reverse('alerts:subscriptions-list')
        response = self.client.post(
            url,
            {'alert_group': str(public_alert_group.id), 'target_group': str(public_target_group.id)},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

    # -------------------------------------------------------------------------
    # Delete Subscription
    # -------------------------------------------------------------------------

    def test_delete_subscription(self):
        """Test deleting a subscription."""
        alert_group = AlertGroupFactory(owner=self.user)
        target_group = WalletGroupFactory(owner=self.user)
        subscription = GroupSubscriptionFactory(
            alert_group=alert_group,
            target_group=target_group,
            owner=self.user
        )
        subscription_id = subscription.id

        url = reverse('alerts:subscriptions-detail', args=[subscription.id])
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not GroupSubscription.objects.filter(id=subscription_id).exists()

    # -------------------------------------------------------------------------
    # Toggle Action
    # -------------------------------------------------------------------------

    def test_toggle_subscription(self):
        """Test toggling subscription active status."""
        alert_group = AlertGroupFactory(owner=self.user)
        target_group = WalletGroupFactory(owner=self.user)
        subscription = GroupSubscriptionFactory(
            alert_group=alert_group,
            target_group=target_group,
            owner=self.user,
            is_active=True
        )

        url = reverse('alerts:subscriptions-toggle', args=[subscription.id])
        response = self.client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_active'] is False

        # Toggle back
        response = self.client.post(url)
        assert response.data['is_active'] is True

    # -------------------------------------------------------------------------
    # By Alert Group Action
    # -------------------------------------------------------------------------

    def test_by_alert_group_action(self):
        """Test filtering subscriptions by alert group."""
        alert_group = AlertGroupFactory(owner=self.user)
        target1 = WalletGroupFactory(owner=self.user)
        target2 = WalletGroupFactory(owner=self.user)

        GroupSubscriptionFactory(alert_group=alert_group, target_group=target1, owner=self.user)
        GroupSubscriptionFactory(alert_group=alert_group, target_group=target2, owner=self.user)

        # Another alert group
        other_alert = AlertGroupFactory(owner=self.user)
        other_target = WalletGroupFactory(owner=self.user)
        GroupSubscriptionFactory(alert_group=other_alert, target_group=other_target, owner=self.user)

        url = reverse('alerts:subscriptions-by-alert-group')
        response = self.client.get(url, {'alert_group_id': str(alert_group.id)})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_by_alert_group_action_missing_param(self):
        """Test by_alert_group action without parameter."""
        url = reverse('alerts:subscriptions-by-alert-group')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # -------------------------------------------------------------------------
    # By Target Group Action
    # -------------------------------------------------------------------------

    def test_by_target_group_action(self):
        """Test filtering subscriptions by target group."""
        target_group = WalletGroupFactory(owner=self.user)
        alert1 = AlertGroupFactory(owner=self.user)
        alert2 = AlertGroupFactory(owner=self.user)

        GroupSubscriptionFactory(alert_group=alert1, target_group=target_group, owner=self.user)
        GroupSubscriptionFactory(alert_group=alert2, target_group=target_group, owner=self.user)

        url = reverse('alerts:subscriptions-by-target-group')
        response = self.client.get(url, {'target_group_id': str(target_group.id)})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2


@pytest.mark.django_db
class TestGroupAPIAuthentication:
    """Tests for API authentication requirements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = APIClient()

    def test_list_groups_requires_auth(self):
        """Test that listing groups requires authentication."""
        url = reverse('alerts:groups-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_group_requires_auth(self):
        """Test that creating groups requires authentication."""
        url = reverse('alerts:groups-list')
        data = {'group_type': GroupType.WALLET, 'name': 'Test'}
        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_subscriptions_requires_auth(self):
        """Test that listing subscriptions requires authentication."""
        url = reverse('alerts:subscriptions-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
