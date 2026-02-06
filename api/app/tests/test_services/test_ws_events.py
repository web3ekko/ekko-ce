"""
Tests for ws.events NATS event publishing

Tests the WebSocket event publishing system used for NLP progress notifications.
Covers async publish_ws_event(), sync publish_ws_event_sync(), and rate limiting.
"""

import pytest
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.nats_service import (
    NATSService,
    publish_ws_event_sync,
    _check_ws_event_rate_limit,
    WS_EVENTS_RATE_LIMIT,
    WS_EVENTS_RATE_WINDOW,
)


@pytest.mark.asyncio
class TestPublishWsEvent:
    """Test async ws.events publishing via NATSService.publish_ws_event()"""

    async def test_publish_ws_event_success(self):
        """Test successful event publishing to ws.events subject"""
        service = NATSService()

        # Mock the NATS client
        mock_nc = AsyncMock()
        mock_nc.publish = AsyncMock()
        mock_nc.is_connected = True
        service._nc = mock_nc

        result = await service.publish_ws_event(
            user_id="user-123",
            event_type="nlp.status",
            payload={"stage": "processing", "progress": 50, "message": "Analyzing..."},
            job_id="job-456",
        )

        assert result.get("success") is True
        # Verify publish was called with ws.events subject
        mock_nc.publish.assert_called_once()
        call_args = mock_nc.publish.call_args
        assert call_args[0][0] == "ws.events"

        # Verify the event payload structure
        published_data = json.loads(call_args[0][1])
        assert published_data["user_id"] == "user-123"
        assert published_data["event_type"] == "nlp.status"
        assert published_data["job_id"] == "job-456"
        assert published_data["payload"]["progress"] == 50

    async def test_publish_ws_event_structure(self):
        """Test event structure has all required fields"""
        service = NATSService()

        mock_nc = AsyncMock()
        mock_nc.publish = AsyncMock()
        mock_nc.is_connected = True
        service._nc = mock_nc

        await service.publish_ws_event(
            user_id="user-123",
            event_type="nlp.complete",
            payload={"template_id": "tpl-1", "spec_ref": "spec-123"},
            job_id="job-456",
        )

        call_args = mock_nc.publish.call_args
        event = json.loads(call_args[0][1])

        # Verify all required fields present
        assert "user_id" in event
        assert "event_type" in event
        assert "job_id" in event
        assert "payload" in event
        assert "timestamp" in event

        # Verify field values
        assert event["user_id"] == "user-123"
        assert event["event_type"] == "nlp.complete"
        assert event["job_id"] == "job-456"
        assert event["payload"]["template_id"] == "tpl-1"

    async def test_publish_ws_event_timestamp_format(self):
        """Test event timestamp is ISO 8601 format"""
        service = NATSService()

        mock_nc = AsyncMock()
        mock_nc.publish = AsyncMock()
        mock_nc.is_connected = True
        service._nc = mock_nc

        await service.publish_ws_event(
            user_id="user-123",
            event_type="nlp.status",
            payload={"progress": 25},
        )

        call_args = mock_nc.publish.call_args
        event = json.loads(call_args[0][1])
        timestamp = event["timestamp"]

        # Should be parseable as ISO 8601
        assert "T" in timestamp  # ISO format has T separator
        assert len(timestamp) > 10  # Full datetime, not just date

    async def test_publish_ws_event_optional_job_id(self):
        """Test job_id can be None"""
        service = NATSService()

        mock_nc = AsyncMock()
        mock_nc.publish = AsyncMock()
        mock_nc.is_connected = True
        service._nc = mock_nc

        result = await service.publish_ws_event(
            user_id="user-123",
            event_type="nlp.status",
            payload={"stage": "init"},
            job_id=None,
        )

        assert result.get("success") is True
        call_args = mock_nc.publish.call_args
        event = json.loads(call_args[0][1])
        assert event["job_id"] is None

    async def test_publish_ws_event_not_connected(self):
        """Test returns failure when NATS not connected"""
        # Explicitly disable stub mode to test real connection failure
        service = NATSService(stub_mode=False)

        # Mock connect to always fail (simulates NATS server unavailable)
        service.connect = AsyncMock(return_value=False)

        result = await service.publish_ws_event(
            user_id="user-123",
            event_type="nlp.status",
            payload={"progress": 50},
        )

        # Should fail because not connected
        assert result.get("success") is False
        assert result.get("error") == "Not connected"

    async def test_publish_ws_event_nlp_status_payload(self):
        """Test nlp.status event has expected payload structure"""
        service = NATSService()

        mock_nc = AsyncMock()
        mock_nc.publish = AsyncMock()
        mock_nc.is_connected = True
        service._nc = mock_nc

        await service.publish_ws_event(
            user_id="user-123",
            event_type="nlp.status",
            payload={
                "stage": "classification",
                "progress": 30,
                "message": "Analyzing intent...",
            },
            job_id="job-456",
        )

        call_args = mock_nc.publish.call_args
        event = json.loads(call_args[0][1])
        payload = event["payload"]

        assert payload["stage"] == "classification"
        assert payload["progress"] == 30
        assert payload["message"] == "Analyzing intent..."

    async def test_publish_ws_event_nlp_complete_payload(self):
        """Test nlp.complete event has expected payload structure"""
        service = NATSService()

        mock_nc = AsyncMock()
        mock_nc.publish = AsyncMock()
        mock_nc.is_connected = True
        service._nc = mock_nc

        await service.publish_ws_event(
            user_id="user-123",
            event_type="nlp.complete",
            payload={
                "template_id": "tpl-abc",
                "template_name": "Balance Alert",
                "spec_ref": "job-456",
                "event_type": "ACCOUNT_EVENT",
                "sub_event": "BALANCE_THRESHOLD",
                "execution_time_seconds": 2.5,
            },
            job_id="job-456",
        )

        call_args = mock_nc.publish.call_args
        event = json.loads(call_args[0][1])
        payload = event["payload"]

        assert payload["template_id"] == "tpl-abc"
        assert payload["template_name"] == "Balance Alert"
        assert payload["spec_ref"] == "job-456"
        assert payload["execution_time_seconds"] == 2.5

    async def test_publish_ws_event_nlp_error_payload(self):
        """Test nlp.error event has expected payload structure"""
        service = NATSService()

        mock_nc = AsyncMock()
        mock_nc.publish = AsyncMock()
        mock_nc.is_connected = True
        service._nc = mock_nc

        await service.publish_ws_event(
            user_id="user-123",
            event_type="nlp.error",
            payload={
                "error": "Failed to classify intent",
                "stage": "classification",
            },
            job_id="job-456",
        )

        call_args = mock_nc.publish.call_args
        event = json.loads(call_args[0][1])

        assert event["event_type"] == "nlp.error"
        payload = event["payload"]
        assert payload["error"] == "Failed to classify intent"
        assert payload["stage"] == "classification"


class TestPublishWsEventSync:
    """Test synchronous ws.events publishing via publish_ws_event_sync()"""

    @patch('app.services.nats_service.NATSService')
    @patch('app.services.nats_service._check_ws_event_rate_limit')
    def test_publish_ws_event_sync_success(self, mock_rate_limit, mock_service_class):
        """Test sync publishing returns True on success"""
        mock_rate_limit.return_value = True

        mock_service = MagicMock()
        mock_service.connect = AsyncMock()
        mock_service.publish_ws_event = AsyncMock(return_value={"success": True})
        mock_service.disconnect = AsyncMock()
        mock_service_class.return_value = mock_service

        result = publish_ws_event_sync(
            user_id="user-123",
            event_type="nlp.status",
            payload={"progress": 50},
            job_id="job-456",
        )

        assert result is True
        mock_service.publish_ws_event.assert_called_once_with(
            user_id="user-123",
            event_type="nlp.status",
            payload={"progress": 50},
            job_id="job-456",
        )

    @patch('app.services.nats_service.NATSService')
    @patch('app.services.nats_service._check_ws_event_rate_limit')
    def test_publish_ws_event_sync_returns_false_on_failure(
        self, mock_rate_limit, mock_service_class
    ):
        """Test sync publishing returns False when publish fails"""
        mock_rate_limit.return_value = True

        mock_service = MagicMock()
        mock_service.connect = AsyncMock()
        mock_service.publish_ws_event = AsyncMock(return_value={"success": False})
        mock_service.disconnect = AsyncMock()
        mock_service_class.return_value = mock_service

        result = publish_ws_event_sync(
            user_id="user-123",
            event_type="nlp.status",
            payload={"progress": 50},
        )

        assert result is False

    @patch('app.services.nats_service.NATSService')
    @patch('app.services.nats_service._check_ws_event_rate_limit')
    def test_publish_ws_event_sync_handles_exception(
        self, mock_rate_limit, mock_service_class
    ):
        """Test sync publishing returns False on exception"""
        mock_rate_limit.return_value = True

        mock_service = MagicMock()
        mock_service.connect = AsyncMock(side_effect=Exception("Connection failed"))
        mock_service_class.return_value = mock_service

        result = publish_ws_event_sync(
            user_id="user-123",
            event_type="nlp.status",
            payload={"progress": 50},
        )

        assert result is False


@pytest.mark.django_db
class TestWsEventsRateLimiting:
    """Test rate limiting for ws.events"""

    def test_rate_limit_allows_under_limit(self):
        """Test events under limit are allowed"""
        from django.core.cache import cache

        user_id = f"test-user-{uuid.uuid4()}"
        cache.delete(f"ws_events_rate:{user_id}")

        # First event should be allowed
        assert _check_ws_event_rate_limit(user_id) is True

    def test_rate_limit_increments_counter(self):
        """Test rate limit counter increments with each call"""
        from django.core.cache import cache

        user_id = f"test-user-{uuid.uuid4()}"
        cache_key = f"ws_events_rate:{user_id}"
        cache.delete(cache_key)

        # First call
        _check_ws_event_rate_limit(user_id)
        assert cache.get(cache_key) == 1

        # Second call
        _check_ws_event_rate_limit(user_id)
        assert cache.get(cache_key) == 2

        # Third call
        _check_ws_event_rate_limit(user_id)
        assert cache.get(cache_key) == 3

    def test_rate_limit_blocks_over_limit(self):
        """Test rate limiting blocks events when limit exceeded (30/min per user)"""
        from django.core.cache import cache

        user_id = f"test-user-{uuid.uuid4()}"
        cache_key = f"ws_events_rate:{user_id}"

        # Set count at limit
        cache.set(cache_key, WS_EVENTS_RATE_LIMIT, timeout=60)

        # Should be blocked
        assert _check_ws_event_rate_limit(user_id) is False

    def test_rate_limit_per_user_independent(self):
        """Test each user has independent rate limit"""
        from django.core.cache import cache

        user_a = f"test-user-a-{uuid.uuid4()}"
        user_b = f"test-user-b-{uuid.uuid4()}"

        # Set user_a at limit
        cache.set(f"ws_events_rate:{user_a}", WS_EVENTS_RATE_LIMIT, timeout=60)
        cache.delete(f"ws_events_rate:{user_b}")

        # user_a blocked, user_b allowed
        assert _check_ws_event_rate_limit(user_a) is False
        assert _check_ws_event_rate_limit(user_b) is True

    @patch('app.services.nats_service._check_ws_event_rate_limit')
    def test_rate_limited_event_returns_false(self, mock_rate_limit):
        """Test publish_ws_event_sync returns False when rate limited"""
        mock_rate_limit.return_value = False

        result = publish_ws_event_sync(
            user_id="user-123",
            event_type="nlp.status",
            payload={"progress": 50},
        )

        assert result is False

    @patch('app.services.nats_service.NATSService')
    def test_error_events_bypass_rate_limit(self, mock_service_class):
        """Test nlp.error events bypass rate limiting"""
        from django.core.cache import cache

        user_id = f"test-user-{uuid.uuid4()}"
        cache.set(f"ws_events_rate:{user_id}", WS_EVENTS_RATE_LIMIT, timeout=60)

        # Mock successful publish
        mock_service = MagicMock()
        mock_service.connect = AsyncMock()
        mock_service.publish_ws_event = AsyncMock(return_value={"success": True})
        mock_service.disconnect = AsyncMock()
        mock_service_class.return_value = mock_service

        # Error event should bypass rate limit
        result = publish_ws_event_sync(
            user_id=user_id,
            event_type="nlp.error",  # Error events bypass rate limit
            payload={"error": "test error", "stage": "classification"},
        )

        assert result is True
        mock_service.publish_ws_event.assert_called_once()

    @patch('app.services.nats_service.NATSService')
    def test_non_error_events_blocked_by_rate_limit(self, mock_service_class):
        """Test non-error events are blocked by rate limit"""
        from django.core.cache import cache

        user_id = f"test-user-{uuid.uuid4()}"
        cache.set(f"ws_events_rate:{user_id}", WS_EVENTS_RATE_LIMIT, timeout=60)

        # Mock service (should never be called)
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Status event should be blocked
        result = publish_ws_event_sync(
            user_id=user_id,
            event_type="nlp.status",  # Not an error event
            payload={"progress": 50},
        )

        assert result is False
        # publish_ws_event should NOT have been called
        mock_service.publish_ws_event.assert_not_called()


class TestWsEventsConstants:
    """Test ws.events configuration constants"""

    def test_rate_limit_value(self):
        """Test rate limit is 30 events per minute"""
        assert WS_EVENTS_RATE_LIMIT == 30

    def test_rate_window_value(self):
        """Test rate window is 60 seconds"""
        assert WS_EVENTS_RATE_WINDOW == 60
