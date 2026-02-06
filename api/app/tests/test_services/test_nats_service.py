"""
Unit tests for NATS service.

These tests avoid requiring a real NATS server (or Docker) by validating the
stub-mode behavior and a basic real-mode failure path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.nats_service import NATSService, get_nats_service, reset_nats_service


@pytest.mark.asyncio
class TestNATSServiceStubMode:
    async def test_connect_sets_connected_in_stub_mode(self):
        service = NATSService(stub_mode=True)
        assert await service.connect() is True
        assert service.is_connected is True

    async def test_publish_returns_success_in_stub_mode(self):
        service = NATSService(stub_mode=True)
        await service.connect()

        result = await service.publish("alerts.test.message", {"hello": "world"})
        assert result["success"] is True
        assert result.get("stub") is True

    async def test_publish_alert_message_in_stub_mode(self):
        service = NATSService(stub_mode=True)
        await service.connect()

        success = await service.publish_alert_message("alerts.test.message", {"test": "data"})
        assert success is True

    async def test_subscribe_registers_callback_in_stub_mode(self):
        service = NATSService(stub_mode=True)

        async def handler(_msg):
            return None

        assert await service.subscribe("alerts.test.subscribe", handler) is True


class TestNATSServiceSingleton:
    def test_get_nats_service_returns_singleton(self):
        reset_nats_service()
        service = get_nats_service(stub_mode=True)

        assert service is get_nats_service()
        assert service.is_connected is True  # stub mode reports connected
        reset_nats_service()


@pytest.mark.asyncio
class TestNATSServiceRealModeFailure:
    async def test_connect_failure_returns_false(self):
        service = NATSService(stub_mode=False)

        with patch(
            "app.services.nats_service.nats.connect",
            new=AsyncMock(side_effect=Exception("boom")),
        ):
            assert await service.connect() is False

        assert service.is_connected is False
