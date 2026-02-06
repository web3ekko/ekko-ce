"""
Unit tests for User Notification History API endpoint.

Tests the UserNotificationHistoryAPIView that returns notification history
from the DuckLake notification_content table.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from app.services.ducklake_client import (
    NotificationHistoryItem,
    NotificationHistoryResponse,
)
from tests.factories.auth_factories import UserFactory


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client):
    """Create an authenticated API client."""
    user = UserFactory()
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.fixture
def sample_notification_items():
    """Create sample notification history items."""
    now = timezone.now()
    return [
        NotificationHistoryItem(
            notification_id="notif-001",
            alert_id="alert-001",
            alert_name="Large Transfer Alert",
            title="Large ETH Transfer Detected",
            message="5.2 ETH transferred from 0x1234...5678",
            priority="high",
            delivery_status="delivered",
            channels_delivered=2,
            channels_failed=0,
            created_at=now - timedelta(hours=1),
            transaction_hash="0xabc123",
            chain_id="ethereum_mainnet",
            block_number=12345678,
            value_usd=12500.00,
            target_channels=["email", "push"],
        ),
        NotificationHistoryItem(
            notification_id="notif-002",
            alert_id="alert-002",
            alert_name="Whale Movement",
            title="Whale Activity Detected",
            message="Large wallet movement on Solana",
            priority="normal",
            delivery_status="delivered",
            channels_delivered=1,
            channels_failed=1,
            created_at=now - timedelta(hours=2),
            transaction_hash="Sol123abc",
            chain_id="solana_mainnet",
            block_number=None,
            value_usd=50000.00,
            target_channels=["webhook"],
        ),
    ]


# =============================================================================
# API Endpoint Tests
# =============================================================================


@pytest.mark.django_db
class TestUserNotificationHistoryAPI:
    """Tests for UserNotificationHistoryAPIView."""

    def test_requires_authentication(self, api_client):
        """Test that the endpoint requires authentication."""
        url = reverse("alerts:notification-history")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_get_notification_history_success(
        self, mock_get_client, authenticated_client, sample_notification_items
    ):
        """Test successful retrieval of notification history."""
        client, user = authenticated_client

        # Setup mock
        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        history_response = NotificationHistoryResponse(
            count=2,
            items=sample_notification_items,
            has_more=False,
        )

        # Create async mock for the coroutine
        async def mock_get_notifications(*args, **kwargs):
            return history_response

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2
        assert data["has_more"] is False

        # Check first notification
        first = data["results"][0]
        assert first["notification_id"] == "notif-001"
        assert first["alert_name"] == "Large Transfer Alert"
        assert first["priority"] == "high"
        assert first["delivery_status"] == "delivered"
        assert first["value_usd"] == 12500.00

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_pagination_parameters(self, mock_get_client, authenticated_client):
        """Test that pagination parameters are passed correctly."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        captured_kwargs = {}

        async def mock_get_notifications(**kwargs):
            captured_kwargs.update(kwargs)
            return NotificationHistoryResponse(count=0, items=[], has_more=False)

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url, {"limit": 25, "offset": 50})

        assert response.status_code == status.HTTP_200_OK
        assert captured_kwargs.get("limit") == 25
        assert captured_kwargs.get("offset") == 50

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_limit_capped_at_100(self, mock_get_client, authenticated_client):
        """Test that limit parameter is capped at 100."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        captured_kwargs = {}

        async def mock_get_notifications(**kwargs):
            captured_kwargs.update(kwargs)
            return NotificationHistoryResponse(count=0, items=[], has_more=False)

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url, {"limit": 500})

        assert response.status_code == status.HTTP_200_OK
        # The view should cap limit at 100
        assert captured_kwargs.get("limit") == 100

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_filter_by_priority(self, mock_get_client, authenticated_client):
        """Test filtering by priority."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        captured_kwargs = {}

        async def mock_get_notifications(**kwargs):
            captured_kwargs.update(kwargs)
            return NotificationHistoryResponse(count=0, items=[], has_more=False)

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url, {"priority": "HIGH"})

        assert response.status_code == status.HTTP_200_OK
        assert captured_kwargs.get("priority") == "high"

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_filter_by_alert_id(self, mock_get_client, authenticated_client):
        """Test filtering by alert_id."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        captured_kwargs = {}

        async def mock_get_notifications(**kwargs):
            captured_kwargs.update(kwargs)
            return NotificationHistoryResponse(count=0, items=[], has_more=False)

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url, {"alert_id": "alert-123"})

        assert response.status_code == status.HTTP_200_OK
        assert captured_kwargs.get("alert_id") == "alert-123"

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_filter_by_date_range(self, mock_get_client, authenticated_client):
        """Test filtering by date range."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        captured_kwargs = {}

        async def mock_get_notifications(**kwargs):
            captured_kwargs.update(kwargs)
            return NotificationHistoryResponse(count=0, items=[], has_more=False)

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url, {
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2026-01-07T23:59:59Z",
        })

        assert response.status_code == status.HTTP_200_OK
        assert captured_kwargs.get("start_date") is not None
        assert captured_kwargs.get("end_date") is not None

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_invalid_date_format(self, mock_get_client, authenticated_client):
        """Test handling of invalid date format."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        url = reverse("alerts:notification-history")
        response = client.get(url, {"start_date": "not-a-date"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error" in data
        assert "Invalid start_date format" in data["error"]

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_ducklake_error_handling(self, mock_get_client, authenticated_client):
        """Test handling of DuckLake query errors."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        async def mock_get_notifications(**kwargs):
            raise Exception("DuckLake connection failed")

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "error" in data

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_empty_results(self, mock_get_client, authenticated_client):
        """Test handling of empty results."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        async def mock_get_notifications(**kwargs):
            return NotificationHistoryResponse(count=0, items=[], has_more=False)

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []
        assert data["has_more"] is False

    @patch("app.services.ducklake_client.get_ducklake_client")
    def test_has_more_pagination(
        self, mock_get_client, authenticated_client, sample_notification_items
    ):
        """Test that has_more is correctly returned for pagination."""
        client, user = authenticated_client

        mock_ducklake = MagicMock()
        mock_get_client.return_value = mock_ducklake

        async def mock_get_notifications(**kwargs):
            return NotificationHistoryResponse(
                count=100,
                items=sample_notification_items,
                has_more=True,
            )

        mock_ducklake.get_user_notifications = mock_get_notifications

        url = reverse("alerts:notification-history")
        response = client.get(url, {"limit": 2})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 100
        assert data["has_more"] is True
