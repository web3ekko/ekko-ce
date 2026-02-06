import pytest

from app.models.groups import GenericGroup, GroupType, SYSTEM_GROUP_ACCOUNTS
from blockchain.models import Blockchain, Wallet


pytestmark = pytest.mark.django_db


class TestAccountsBulkAddWallets:
    def test_bulk_add_creates_accounts_and_returns_partial_errors(self, api_client, user):
        api_client.force_authenticate(user=user)

        resp = api_client.post(
            "/api/groups/accounts/add_wallets/",
            data={
                "wallets": [
                    {"member_key": "eth:mainnet:0xAbC", "label": "", "owner_verified": True},
                    {"member_key": "ETH:mainnet:0xdef", "label": "Ops", "owner_verified": False},
                    {"member_key": "not-a-wallet-key", "label": "Bad"},
                ]
            },
            format="json",
        )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["created"] is True
        assert payload["added"] == 2
        assert payload["wallet_rows_created"] == 2
        assert len(payload["errors"]) == 1
        assert payload["total_members"] == 2

        accounts = GenericGroup.objects.get(
            owner=user,
            group_type=GroupType.WALLET,
            settings__system_key=SYSTEM_GROUP_ACCOUNTS,
        )

        assert accounts.member_data["members"]["ETH:mainnet:0xabc"]["metadata"]["owner_verified"] is True
        assert accounts.member_data["members"]["ETH:mainnet:0xdef"]["label"] == "Ops"

        assert Blockchain.objects.filter(symbol="ETH").exists()
        assert Wallet.objects.filter(blockchain__symbol="ETH", subnet="mainnet", address="0xabc").exists()
        assert Wallet.objects.filter(blockchain__symbol="ETH", subnet="mainnet", address="0xdef").exists()

    def test_bulk_add_reports_existing_members(self, api_client, user):
        api_client.force_authenticate(user=user)

        GenericGroup.get_or_create_accounts_group(user).add_member_local(
            member_key="ETH:mainnet:0xabc",
            added_by=str(user.id),
            label="",
            metadata={"owner_verified": False},
        )

        resp = api_client.post(
            "/api/groups/accounts/add_wallets/",
            data={"wallets": [{"member_key": "ETH:mainnet:0xAbC", "label": "Ignored"}]},
            format="json",
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["created"] is False
        assert payload["added"] == 0
        assert payload["already_exists"] == ["ETH:mainnet:0xabc"]
