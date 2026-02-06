import pytest

from app.models.groups import GenericGroup, GroupType, SYSTEM_GROUP_ACCOUNTS
from blockchain.models import Blockchain, Chain, Wallet
from blockchain.models_wallet_nicknames import WalletNickname


@pytest.mark.django_db
class TestWalletSearchAndStatsViews:
    def test_search_wallets_prefers_accounts_label_and_sets_url(self, api_client, user):
        chain = Blockchain.objects.create(symbol='ETH', name='Ethereum')
        wallet_in_accounts = Wallet.objects.create(blockchain=chain, subnet='mainnet', address='0xabc', name='Wallet A')
        wallet_not_in_accounts = Wallet.objects.create(blockchain=chain, subnet='mainnet', address='0xdef', name='Wallet B')

        GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Accounts',
            owner=user,
            settings={'system_key': SYSTEM_GROUP_ACCOUNTS, 'visibility': 'private'},
            member_data={
                'members': {
                    'ETH:mainnet:0xabc': {
                        'added_at': '2025-01-01T00:00:00Z',
                        'added_by': str(user.id),
                        'label': 'Treasury',
                        'tags': [],
                        'metadata': {'owner_verified': False},
                    }
                }
            },
            member_count=1,
        )

        api_client.force_authenticate(user=user)

        resp = api_client.get('/api/v1/search/wallets/', {'q': '0xabc', 'limit': 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data['total'] == 1
        assert len(data['results']) == 1
        result = data['results'][0]

        assert result['id'] == str(wallet_in_accounts.id)
        assert result['title'] == 'Treasury'
        assert result['metadata']['wallet_key'] == 'ETH:mainnet:0xabc'
        assert result['metadata']['in_accounts'] is True
        assert result['url'].endswith('/dashboard/wallets/ETH%3Amainnet%3A0xabc')

        resp2 = api_client.get('/api/v1/search/wallets/', {'q': '0xdef', 'limit': 10})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2['total'] == 1
        result2 = data2['results'][0]
        assert result2['id'] == str(wallet_not_in_accounts.id)
        assert result2['metadata']['in_accounts'] is False
        assert result2['url'] == '/dashboard/wallets'

    def test_dashboard_stats_wallet_count_uses_accounts_group(self, api_client, user):
        GenericGroup.objects.create(
            group_type=GroupType.WALLET,
            name='Accounts',
            owner=user,
            settings={'system_key': SYSTEM_GROUP_ACCOUNTS, 'visibility': 'private'},
            member_data={
                'members': {
                    'ETH:mainnet:0xabc': {'added_at': '2025-01-01T00:00:00Z', 'added_by': str(user.id)},
                    'ETH:mainnet:0xdef': {'added_at': '2025-01-01T00:00:00Z', 'added_by': str(user.id)},
                }
            },
            member_count=2,
        )

        api_client.force_authenticate(user=user)
        resp = api_client.get('/api/v1/dashboard/stats/')
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['wallets']['total'] == 2
        assert payload['wallets']['watched'] == 2

    def test_search_wallets_uses_wallet_nickname_when_no_accounts_label(self, api_client, user):
        chain = Blockchain.objects.create(symbol='ETH', name='Ethereum')
        Chain.objects.create(
            name='ethereum',
            display_name='Ethereum',
            chain_id=1,
            native_token='ETH',
            enabled=True,
        )

        wallet = Wallet.objects.create(
            blockchain=chain,
            subnet='mainnet',
            address='0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            name='USDC Holder',
        )

        WalletNickname.objects.create(
            user=user,
            wallet_address='0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            chain_id=1,
            custom_name='Cold Storage',
        )

        api_client.force_authenticate(user=user)
        resp = api_client.get('/api/v1/search/wallets/', {'q': '0xa0b8', 'limit': 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data['total'] == 1
        result = data['results'][0]

        assert result['id'] == str(wallet.id)
        assert result['title'] == 'Cold Storage'
        assert result['metadata']['nickname'] == 'Cold Storage'
