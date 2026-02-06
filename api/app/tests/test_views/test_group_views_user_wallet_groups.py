import pytest
from django.contrib.auth import get_user_model

from app.models.groups import GenericGroup, GroupType, UserWalletGroup, SYSTEM_GROUP_ACCOUNTS


User = get_user_model()


@pytest.mark.django_db
class TestGroupViewsUserWalletGroups:
    def test_user_wallet_groups_crud(self, api_client, user):
        provider = User.objects.create_user(
            email='provider@example.com',
            first_name='Provider',
            last_name='User',
            password='providerpass123',
        )

        provider_wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=provider,
            settings={'visibility': 'private'},
            member_data={'members': {}},
            member_count=0,
        )

        uwg = UserWalletGroup.objects.create(
            user=user,
            wallet_group=provider_wallet_group,
            provider=provider,
            wallet_keys=['ETH:mainnet:0xabc'],
        )

        api_client.force_authenticate(user=user)

        list_resp = api_client.get('/api/groups/user-wallet-groups/')
        assert list_resp.status_code == 200
        payload = list_resp.json()
        assert payload['count'] == 1
        assert len(payload['results']) == 1
        assert payload['results'][0]['id'] == str(uwg.id)
        assert payload['results'][0]['wallet_group_name'] == 'Provider Wallets'

        detail_resp = api_client.get(f'/api/groups/user-wallet-groups/{uwg.id}/')
        assert detail_resp.status_code == 200
        assert detail_resp.json()['id'] == str(uwg.id)

        patch_resp = api_client.patch(
            f'/api/groups/user-wallet-groups/{uwg.id}/',
            data={'notification_routing': 'both', 'auto_subscribe_alerts': False, 'is_active': False},
            format='json',
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data['notification_routing'] == 'both'
        assert data['auto_subscribe_alerts'] is False
        assert data['is_active'] is False

        uwg.refresh_from_db()
        assert uwg.notification_routing == 'both'
        assert uwg.auto_subscribe_alerts is False
        assert uwg.is_active is False
        assert uwg.wallet_keys == ['ETH:mainnet:0xabc']

        delete_resp = api_client.delete(f'/api/groups/user-wallet-groups/{uwg.id}/')
        assert delete_resp.status_code == 204
        assert UserWalletGroup.objects.filter(id=uwg.id).count() == 0

    def test_update_members_updates_accounts_label_and_owner_verified(self, api_client, user):
        accounts = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Accounts',
            owner=user,
            settings={'system_key': SYSTEM_GROUP_ACCOUNTS, 'visibility': 'private'},
            member_data={
                'members': {
                    'ETH:mainnet:0xabc': {
                        'added_at': '2025-01-01T00:00:00Z',
                        'added_by': str(user.id),
                        'label': 'Old',
                        'tags': [],
                        'metadata': {'owner_verified': False, 'source': 'seed'},
                    }
                }
            },
            member_count=1,
        )

        api_client.force_authenticate(user=user)

        resp = api_client.post(
            f'/api/groups/{accounts.id}/update_members/',
            data={
                'members': [
                    {
                        'member_key': 'ETH:mainnet:0xAbC',
                        'label': 'Treasury',
                        'metadata': {'owner_verified': True},
                    }
                ]
            },
            format='json',
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body['updated'] == 1
        assert body['not_found'] == []

        accounts.refresh_from_db()
        member = accounts.member_data['members']['ETH:mainnet:0xabc']
        assert member['label'] == 'Treasury'
        assert member['metadata']['owner_verified'] is True
        assert member['metadata']['source'] == 'seed'

    def test_user_wallet_group_create_and_wallet_ops(self, api_client, user):
        wallet_group = GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Provider Wallets',
            owner=user,
            settings={'visibility': 'private'},
            member_data={'members': {}},
            member_count=0,
        )

        api_client.force_authenticate(user=user)

        create_resp = api_client.post(
            '/api/groups/user-wallet-groups/',
            data={
                'wallet_group': str(wallet_group.id),
                'wallet_keys': ['eth:MainNet:0xABC'],
                'notification_routing': 'callback_only',
                'auto_subscribe_alerts': True,
            },
            format='json',
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created['wallet_group'] == str(wallet_group.id)
        assert created['wallet_keys'] == ['ETH:mainnet:0xabc']

        uwg_id = created['id']

        add_resp = api_client.post(
            f'/api/groups/user-wallet-groups/{uwg_id}/add_wallets/',
            data={'wallet_keys': ['ETH:mainnet:0xDEF']},
            format='json',
        )
        assert add_resp.status_code == 200
        add_payload = add_resp.json()
        assert 'ETH:mainnet:0xdef' in add_payload['added']

        remove_resp = api_client.post(
            f'/api/groups/user-wallet-groups/{uwg_id}/remove_wallets/',
            data={'wallet_keys': ['ETH:mainnet:0xABC']},
            format='json',
        )
        assert remove_resp.status_code == 200
        remove_payload = remove_resp.json()
        assert remove_payload['removed'] == ['ETH:mainnet:0xabc']

        import_resp = api_client.post(
            f'/api/groups/user-wallet-groups/{uwg_id}/import_wallets/',
            data={
                'format': 'csv',
                'payload': 'network,subnet,address\nETH,mainnet,0x111\nbadrow',
                'merge_mode': 'append',
                'dedupe': True,
            },
            format='json',
        )
        assert import_resp.status_code == 200
        import_payload = import_resp.json()
        assert import_payload['added'] == ['ETH:mainnet:0x111']
        assert 2 in import_payload['invalid_rows']
