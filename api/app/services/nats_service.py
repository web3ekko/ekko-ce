"""
NATS Service - Real NATS Implementation with Stub Fallback

Provides async NATS pub/sub for Django alert events and WebSocket notifications.
Falls back to stub mode when NATS_ENABLED=False or connection fails.

Key subjects:
- alerts.created/updated/enabled/disabled: Alert lifecycle events
- ws.events: WebSocket events for real-time NLP progress (wasmCloud provider)
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional, Callable
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Try to import nats-py, fallback to stub if not available
try:
    import nats
    from nats.aio.client import Client as NATSClient
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False
    logger.warning("nats-py not installed, running in stub mode")


class NATSService:
    """
    NATS service for pub/sub messaging.

    Supports two modes:
    - Real mode: Connects to NATS server for actual messaging
    - Stub mode: Logs messages without actual NATS connection
    """

    def __init__(self, stub_mode: bool = False):
        self._nc: Optional['NATSClient'] = None
        self._stub_mode = stub_mode or not NATS_AVAILABLE
        self._connected = False
        self._subscriptions: Dict[str, Any] = {}

        if self._stub_mode:
            logger.info("NATSService initialized in STUB mode")
        else:
            logger.info("NATSService initialized in REAL mode")

    @property
    def is_connected(self) -> bool:
        """Check if connected to NATS"""
        if self._stub_mode:
            return True
        return self._nc is not None and self._nc.is_connected

    async def connect(self) -> bool:
        """
        Connect to NATS server.

        Returns:
            True if connected successfully, False otherwise
        """
        if self._stub_mode:
            self._connected = True
            logger.debug("NATS stub connection established")
            return True

        if self._nc and self._nc.is_connected:
            return True

        try:
            nats_url = getattr(settings, 'NATS_URL', 'nats://localhost:4222')
            max_reconnects = getattr(settings, 'NATS_MAX_RECONNECT_ATTEMPTS', 10)
            reconnect_wait = getattr(settings, 'NATS_RECONNECT_TIME_WAIT', 2)

            self._nc = await nats.connect(
                nats_url,
                max_reconnect_attempts=max_reconnects,
                reconnect_time_wait=reconnect_wait,
                error_cb=self._on_error,
                disconnected_cb=self._on_disconnected,
                reconnected_cb=self._on_reconnected,
            )
            self._connected = True
            logger.info(f"Connected to NATS at {nats_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from NATS server"""
        if self._stub_mode:
            self._connected = False
            return

        if self._nc:
            try:
                await self._nc.close()
                logger.info("Disconnected from NATS")
            except Exception as e:
                logger.error(f"Error disconnecting from NATS: {e}")
            finally:
                self._nc = None
                self._connected = False

    async def _on_error(self, e):
        """Handle NATS errors"""
        logger.error(f"NATS error: {e}")

    async def _on_disconnected(self):
        """Handle NATS disconnection"""
        logger.warning("Disconnected from NATS")
        self._connected = False

    async def _on_reconnected(self):
        """Handle NATS reconnection"""
        logger.info("Reconnected to NATS")
        self._connected = True

    async def publish(self, subject: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish message to NATS subject.

        Args:
            subject: NATS subject to publish to
            data: Dictionary payload to publish

        Returns:
            Publish result with success status
        """
        payload = json.dumps(data).encode('utf-8')

        if self._stub_mode:
            logger.info(f"[STUB] NATS publish to {subject}: {json.dumps(data, indent=2)}")
            return {'success': True, 'stub': True}

        if not self.is_connected:
            await self.connect()

        if not self.is_connected:
            logger.error(f"Cannot publish to {subject}: not connected to NATS")
            return {'success': False, 'error': 'Not connected'}

        try:
            await self._nc.publish(subject, payload)
            logger.debug(f"Published to {subject}: {len(payload)} bytes")
            return {'success': True}
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            return {'success': False, 'error': str(e)}

    async def subscribe(self, subject: str, callback: Callable) -> bool:
        """
        Subscribe to NATS subject.

        Args:
            subject: NATS subject to subscribe to
            callback: Async callback function for messages

        Returns:
            True if subscribed successfully
        """
        if self._stub_mode:
            logger.info(f"[STUB] NATS subscribe to {subject}")
            self._subscriptions[subject] = callback
            return True

        if not self.is_connected:
            await self.connect()

        if not self.is_connected:
            logger.error(f"Cannot subscribe to {subject}: not connected")
            return False

        try:
            sub = await self._nc.subscribe(subject, cb=callback)
            self._subscriptions[subject] = sub
            logger.info(f"Subscribed to {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")
            return False

    # ============================================================
    # Alert lifecycle methods
    # ============================================================

    async def publish_alert_message(self, subject: str, message: Dict[str, Any]) -> bool:
        """Publish alert message"""
        result = await self.publish(subject, message)
        return result.get('success', False)

    # ============================================================
    # WebSocket event methods (Phase 1: ws.events subject)
    # ============================================================

    async def publish_ws_event(
        self,
        user_id: str,
        event_type: str,
        payload: Dict[str, Any],
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Publish WebSocket event to ws.events subject.

        wasmCloud WS provider subscribes and forwards to connected clients.

        Args:
            user_id: Target user ID for WebSocket routing
            event_type: Event type (e.g., nlp.status, nlp.complete, nlp.error)
            payload: Event payload data
            job_id: Optional job ID for tracking async operations

        Returns:
            Publish result
        """
        event = {
            "user_id": user_id,
            "event_type": event_type,
            "job_id": job_id,
            "payload": payload,
            "timestamp": timezone.now().isoformat(),
        }

        return await self.publish("ws.events", event)


# Singleton instance
_nats_service: Optional[NATSService] = None


def get_nats_service(stub_mode: Optional[bool] = None) -> NATSService:
    """
    Get or create global NATS service instance.

    Args:
        stub_mode: Force stub mode if True, auto-detect if None

    Returns:
        NATSService singleton instance
    """
    global _nats_service

    if _nats_service is None:
        # Auto-detect stub mode from settings
        if stub_mode is None:
            stub_mode = not getattr(settings, 'NATS_ENABLED', True)
        _nats_service = NATSService(stub_mode=stub_mode)

    return _nats_service


def reset_nats_service():
    """Reset the singleton (useful for testing)"""
    global _nats_service
    _nats_service = None


# ============================================================
# Synchronous wrapper functions for Django views
# ============================================================

def publish_alert_created_sync(alert):
    """
    Publish alert created event synchronously.

    Args:
        alert: Alert instance that was created
    """
    async def _publish():
        service = get_nats_service()
        await service.connect()

        message = {
            'id': str(uuid.uuid4()),
            'timestamp': timezone.now().isoformat(),
            'user_id': str(alert.user.id),
            'alert': {
                'id': str(alert.id),
                'name': alert.name,
                'nl_description': alert.nl_description,
                'event_type': alert.event_type,
                'sub_event': alert.sub_event,
                'template_id': str(alert.template.id) if alert.template else None,
                'enabled': alert.enabled,
                'version': alert.version,
                'processing_status': getattr(alert, 'processing_status', 'skipped'),
            },
            'correlation_id': f'alert-created-{alert.id}'
        }

        await service.publish('alerts.created', message)

    try:
        asyncio.run(_publish())
    except Exception as e:
        logger.error(f"Failed to publish alert created (sync): {e}")


def publish_alert_updated_sync(alert):
    """
    Publish alert updated event synchronously.

    Args:
        alert: Alert instance that was updated
    """
    async def _publish():
        service = get_nats_service()
        await service.connect()

        message = {
            'id': str(uuid.uuid4()),
            'timestamp': timezone.now().isoformat(),
            'user_id': str(alert.user.id),
            'alert': {
                'id': str(alert.id),
                'name': alert.name,
                'nl_description': alert.nl_description,
                'event_type': alert.event_type,
                'sub_event': alert.sub_event,
                'spec': alert.spec,
                'enabled': alert.enabled,
                'version': alert.version,
                'processing_status': getattr(alert, 'processing_status', 'skipped'),
            },
            'correlation_id': f'alert-updated-{alert.id}'
        }

        await service.publish('alerts.updated', message)

    try:
        asyncio.run(_publish())
    except Exception as e:
        logger.error(f"Failed to publish alert updated (sync): {e}")


def publish_alert_enabled_sync(alert):
    """
    Publish alert enabled event synchronously.

    Args:
        alert: Alert instance that was enabled
    """
    async def _publish():
        service = get_nats_service()
        await service.connect()

        message = {
            'id': str(uuid.uuid4()),
            'timestamp': timezone.now().isoformat(),
            'user_id': str(alert.user.id),
            'alert': {
                'id': str(alert.id),
                'name': alert.name,
                'enabled': True,
                'version': alert.version
            },
            'correlation_id': f'alert-enabled-{alert.id}'
        }

        await service.publish('alerts.enabled', message)

    try:
        asyncio.run(_publish())
    except Exception as e:
        logger.error(f"Failed to publish alert enabled (sync): {e}")


def publish_alert_disabled_sync(alert):
    """
    Publish alert disabled event synchronously.

    Args:
        alert: Alert instance that was disabled
    """
    async def _publish():
        service = get_nats_service()
        await service.connect()

        message = {
            'id': str(uuid.uuid4()),
            'timestamp': timezone.now().isoformat(),
            'user_id': str(alert.user.id),
            'alert': {
                'id': str(alert.id),
                'name': alert.name,
                'enabled': False,
                'version': alert.version
            },
            'correlation_id': f'alert-disabled-{alert.id}'
        }

        await service.publish('alerts.disabled', message)

    try:
        asyncio.run(_publish())
    except Exception as e:
        logger.error(f"Failed to publish alert disabled (sync): {e}")


# ============================================================
# WebSocket event sync wrappers (Phase 1: ws.events subject)
# ============================================================

# Rate limiting for ws.events (per-user)
WS_EVENTS_RATE_LIMIT = 30  # events per minute per user
WS_EVENTS_RATE_WINDOW = 60  # seconds


def _check_ws_event_rate_limit(user_id: str) -> bool:
    """
    Check if user is within ws.events rate limit.

    Uses a simple counter with TTL for rate limiting.
    Allows WS_EVENTS_RATE_LIMIT events per WS_EVENTS_RATE_WINDOW seconds.

    Args:
        user_id: User ID to check

    Returns:
        True if within rate limit, False if exceeded
    """
    from django.core.cache import cache

    cache_key = f"ws_events_rate:{user_id}"
    current_count = cache.get(cache_key, 0)

    if current_count >= WS_EVENTS_RATE_LIMIT:
        logger.warning(f"WS events rate limit exceeded for user {user_id}")
        return False

    # Increment counter (set TTL on first event)
    if current_count == 0:
        cache.set(cache_key, 1, timeout=WS_EVENTS_RATE_WINDOW)
    else:
        cache.incr(cache_key)

    return True


def publish_ws_event_sync(
    user_id: str,
    event_type: str,
    payload: Dict[str, Any],
    job_id: Optional[str] = None,
) -> bool:
    """
    Synchronous wrapper for publishing WebSocket events.

    Used from Django views and background tasks to send real-time
    updates to connected clients via wasmCloud WS provider.

    IMPORTANT: Creates a fresh NATS client per call to avoid event loop issues.
    asyncio.run() creates a new event loop, so we cannot reuse a client
    that was connected on a different loop.

    Rate limited to WS_EVENTS_RATE_LIMIT events per minute per user.

    Args:
        user_id: Target user ID for WebSocket routing
        event_type: Event type (e.g., nlp.status, nlp.complete, nlp.error)
        payload: Event payload data
        job_id: Optional job ID for tracking async operations

    Returns:
        True if published successfully, False if rate limited or failed
    """
    # Check rate limit first (skip for error events to ensure delivery)
    if event_type != "nlp.error" and not _check_ws_event_rate_limit(user_id):
        logger.warning(f"WS event dropped due to rate limit: user={user_id}, type={event_type}")
        return False

    async def _publish():
        # Create a fresh client for this call to avoid event loop issues
        # (asyncio.run creates a new loop each time)
        stub_mode = not getattr(settings, 'NATS_ENABLED', True)
        service = NATSService(stub_mode=stub_mode)
        try:
            await service.connect()
            result = await service.publish_ws_event(
                user_id=user_id,
                event_type=event_type,
                payload=payload,
                job_id=job_id,
            )
            return result.get('success', False)
        finally:
            # Always disconnect to clean up resources
            await service.disconnect()

    try:
        return asyncio.run(_publish())
    except Exception as e:
        logger.error(f"Failed to publish WS event (sync): {e}")
        return False
