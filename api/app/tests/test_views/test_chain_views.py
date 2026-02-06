import pytest

from blockchain.models import Chain


pytestmark = pytest.mark.django_db


class TestChainViews:
    def test_list_chains(self, api_client, user):
        api_client.force_authenticate(user=user)

        Chain.objects.create(
            name="ethereum",
            display_name="Ethereum",
            chain_id=1,
            native_token="ETH",
            enabled=True,
        )

        resp = api_client.get("/api/chains/")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["count"] == 1
        assert payload["results"][0]["name"] == "ethereum"
