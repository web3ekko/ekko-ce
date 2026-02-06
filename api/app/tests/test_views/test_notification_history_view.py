from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from rest_framework.test import APIRequestFactory, force_authenticate

from app.views.notification_views import UserNotificationHistoryAPIView


def test_notification_history_falls_back_to_alert_name():
    factory = APIRequestFactory()
    request = factory.get("/api/v1/notifications/history/")
    user = SimpleNamespace(is_authenticated=True, id="user-1", pk="user-1")
    force_authenticate(request, user=user)

    history = SimpleNamespace(
        count=1,
        items=[
            SimpleNamespace(
                notification_id="notif-1",
                alert_id="alert-1",
                alert_name="Alert Name",
                title="",
                message="",
                priority="normal",
                delivery_status="delivered",
                channels_delivered=1,
                channels_failed=0,
                created_at=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
                transaction_hash=None,
                chain_id=None,
                block_number=None,
                value_usd=None,
                target_channels=[],
            )
        ],
    )

    with patch("app.views.notification_views.DuckLakeClient") as client_factory:
        client = client_factory.return_value
        client.get_user_notifications = AsyncMock(return_value=history)
        client.close = AsyncMock()

        with patch("rest_framework.views.APIView.check_throttles", return_value=None):
            response = UserNotificationHistoryAPIView.as_view()(request)

    assert response.status_code == 200
    assert response.data["results"][0]["title"] == "Alert Name"
    assert response.data["results"][0]["message"] == "Alert Name"
