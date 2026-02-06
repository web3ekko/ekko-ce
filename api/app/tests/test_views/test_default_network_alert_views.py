import pytest

from app.models.alerts import DefaultNetworkAlert
from blockchain.models import Chain


pytestmark = pytest.mark.django_db


class TestDefaultNetworkAlertViews:
    def test_list_default_network_alerts(self, api_client, user, sample_alert_template):
        api_client.force_authenticate(user=user)

        chain = Chain.objects.create(
            name="ethereum",
            display_name="Ethereum",
            chain_id=1,
            native_token="ETH",
            enabled=True,
        )

        alert = DefaultNetworkAlert.objects.create(
            chain=chain,
            subnet="mainnet",
            alert_template=sample_alert_template,
            enabled=True,
        )

        resp = api_client.get("/api/alerts/default-network/")
        assert resp.status_code == 200

        payload = resp.json()
        assert payload["count"] == 1
        result = payload["results"][0]
        assert result["id"] == str(alert.id)
        assert result["chain"] == "ethereum"
        assert result["chain_name"] == "Ethereum"
        assert result["chain_symbol"] == "ETH"
        assert result["subnet"] == "mainnet"
        assert result["alert_template"] == str(sample_alert_template.id)
        assert result["enabled"] is True

    def test_toggle_default_network_alert(self, api_client, user, sample_alert_template):
        api_client.force_authenticate(user=user)

        chain = Chain.objects.create(
            name="ethereum",
            display_name="Ethereum",
            chain_id=1,
            native_token="ETH",
            enabled=True,
        )

        alert = DefaultNetworkAlert.objects.create(
            chain=chain,
            subnet="mainnet",
            alert_template=sample_alert_template,
            enabled=True,
        )

        resp = api_client.patch(
            f"/api/alerts/default-network/{alert.id}/",
            {"enabled": False},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        alert.refresh_from_db()
        assert alert.enabled is False
