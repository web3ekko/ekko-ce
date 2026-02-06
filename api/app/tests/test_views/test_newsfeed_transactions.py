from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from app.views.analytics_views import newsfeed_transactions


@override_settings(REST_FRAMEWORK={"DEFAULT_THROTTLE_CLASSES": []})
def test_newsfeed_transactions_uses_safe_alias():
    factory = APIRequestFactory()
    request = factory.get("/api/v1/analytics/newsfeed/transactions/")
    user = SimpleNamespace(is_authenticated=True, id="user-1", pk="user-1")
    force_authenticate(request, user=user)

    with patch("app.views.analytics_views._get_user_monitored_addresses", return_value=["ETH:mainnet:0xabc"]):
        with patch("app.views.analytics_views.DuckLakeClient") as client_factory:
            client = client_factory.return_value
            client.query_rows = AsyncMock(
                side_effect=[
                    [{"transaction_hash": "0x1"}],
                    [{"total": 1}],
                ]
            )
            client.close = AsyncMock()
            with patch("rest_framework.views.APIView.check_throttles", return_value=None):
                response = newsfeed_transactions(request)

    assert response.status_code == 200
    first_sql = client.query_rows.call_args_list[0][1]["query"]
    assert "address_transactions addr_tx" in first_sql


@override_settings(REST_FRAMEWORK={"DEFAULT_THROTTLE_CLASSES": []})
def test_newsfeed_transactions_returns_empty_when_ducklake_unavailable():
    factory = APIRequestFactory()
    request = factory.get("/api/v1/analytics/newsfeed/transactions/")
    user = SimpleNamespace(is_authenticated=True, id="user-1", pk="user-1")
    force_authenticate(request, user=user)

    with patch("app.views.analytics_views._get_user_monitored_addresses", return_value=["ETH:mainnet:0xabc"]):
        with patch("app.views.analytics_views.DuckLakeClient") as client_factory:
            client = client_factory.return_value
            client.query_rows = AsyncMock(
                side_effect=RuntimeError(
                    "Table with name address_transactions does not exist!"
                )
            )
            client.close = AsyncMock()
            with patch("rest_framework.views.APIView.check_throttles", return_value=None):
                response = newsfeed_transactions(request)

    assert response.status_code == 200
    assert response.data["transactions"] == []
    assert response.data["total"] == 0
    assert "warning" in response.data
