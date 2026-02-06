"""
API views for notification system management.

This module provides REST API endpoints for managing user and group notification
settings, delivery tracking, and template management.

ARCHITECTURE NOTE:
Django provides metadata management only - NO message publishing:
- Settings validation and CRUD operations  
- Redis cache population and management
- Channel configuration templates
- wasmCloud providers handle actual notification delivery
"""

import logging
from datetime import timedelta
from typing import Dict, Any

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from django.core.cache import cache
from django.http import HttpResponse

from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from app.models.notifications import (
    UserNotificationSettings, GroupNotificationSettings,
    NotificationDelivery, NotificationTemplate, NotificationCache,
    NotificationChannelEndpoint, TeamMemberNotificationOverride,
    NotificationChannelVerification
)
from organizations.models import Team, TeamMember, TeamMemberRole
from organizations.models import TeamMember, TeamMemberRole
from app.serializers.notification_serializers import (
    UserNotificationSettingsSerializer, GroupNotificationSettingsSerializer,
    NotificationDeliverySerializer, NotificationTemplateSerializer,
    NotificationTestSerializer, BulkNotificationSerializer, CacheStatsSerializer,
    NotificationChannelConfigSerializer, NotificationChannelEndpointSerializer,
    VerificationCodeRequestSerializer, VerificationCodeSubmitSerializer,
    TeamNotificationChannelEndpointSerializer, TeamMemberNotificationOverrideSerializer
)
from app.services.ducklake_client import (
    ChannelHealthMetrics,
    DeliveryMetrics,
    DuckLakeClient,
    NotificationHistoryResponse,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for notification endpoints."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class UserNotificationSettingsViewSet(ModelViewSet):
    """ViewSet for managing user notification settings."""
    
    serializer_class = UserNotificationSettingsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Settings are per-user, no pagination needed
    
    def get_queryset(self):
        """Return settings only for the authenticated user."""
        return UserNotificationSettings.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Get or create settings for the authenticated user."""
        try:
            return UserNotificationSettings.objects.get(user=self.request.user)
        except UserNotificationSettings.DoesNotExist:
            return UserNotificationSettings.create_default_settings(self.request.user)
    
    def list(self, request):
        """Get current user's notification settings."""
        settings = self.get_object()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    def create(self, request):
        """Create or update notification settings for current user."""
        # Check if settings already exist
        try:
            settings = UserNotificationSettings.objects.get(user=request.user)
            serializer = self.get_serializer(settings, data=request.data, partial=True)
        except UserNotificationSettings.DoesNotExist:
            serializer = self.get_serializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        settings = serializer.save()
        
        logger.info(f"Updated notification settings for user {request.user.id}")
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def update(self, request, pk=None):
        """Update notification settings."""
        settings = self.get_object()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        logger.info(f"Updated notification settings for user {request.user.id}")
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def test_notification(self, request):
        """Validate notification settings for current user."""
        serializer = NotificationTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        channel = serializer.validated_data['channel']
        message = serializer.validated_data['message']
        subject = serializer.validated_data.get('subject', 'Test Notification')
        
        # Check if user has this channel enabled
        settings = self.get_object()
        if not settings.is_channel_enabled(channel):
            return Response(
                {'error': f'{channel.title()} notifications are not enabled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate channel configuration
        channel_config = settings.channels.get(channel, {})
        if not channel_config.get('enabled', False):
            return Response(
                {'error': f'{channel.title()} channel is not properly configured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Notification settings validated for user {request.user.id} via {channel}")
        
        return Response({
            'message': f'Notification settings validated for {channel} delivery',
            'channel': channel,
            'subject': subject,
            'content': message,
            'status': 'validated'
        })
    
    @action(detail=False, methods=['get'])
    def channel_templates(self, request):
        """Get configuration templates for all notification channels."""
        channels = ['email', 'slack', 'sms', 'telegram', 'discord', 'webhook', 'websocket']
        templates = {}
        
        for channel in channels:
            serializer = NotificationChannelConfigSerializer()
            serializer.context = {'channel': channel}
            templates[channel] = serializer.to_representation(channel)
        
        return Response(templates)
    
    @action(detail=False, methods=['post'])
    def validate_channel_config(self, request):
        """Validate channel configuration without saving."""
        channel = request.data.get('channel')
        config = request.data.get('config', {})
        
        if not channel:
            return Response(
                {'error': 'Channel name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Create a temporary settings object for validation
            temp_settings = UserNotificationSettings(user=request.user)
            temp_settings.channels = {channel: {'enabled': True, 'config': config}}
            temp_settings.clean()
            
            return Response({'valid': True, 'message': 'Configuration is valid'})
        except Exception as e:
            return Response(
                {'valid': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def cache_status(self, request):
        """Get cache status for current user."""
        user_id = request.user.id
        cache_key = f"user:notifications:{user_id}"
        cached_data = cache.get(cache_key)
        
        return Response({
            'cached': cached_data is not None,
            'cache_key': cache_key,
            'cached_at': cached_data.get('cached_at') if cached_data else None,
            'ttl_seconds': cache.ttl(cache_key) if cached_data else 0
        })
    
    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """Clear cache for current user."""
        settings = self.get_object()
        settings.invalidate_cache()
        
        return Response({'message': 'Cache cleared successfully'})
    
    @action(detail=False, methods=['post'])
    def warm_cache(self, request):
        """Warm cache for current user."""
        user_id = request.user.id
        
        # Force cache population for current user
        try:
            settings = self.get_object()
            cache_key = f"user:notifications:{user_id}"
            
            # Create cache data
            cache_data = {
                'user_id': str(user_id),
                'websocket_enabled': settings.websocket_enabled,
                'notifications_enabled': settings.notifications_enabled,
                'channels': settings.channels,
                'priority_routing': settings.priority_routing,
                'quiet_hours': settings.quiet_hours,
                'cached_at': timezone.now().isoformat(),
            }
            
            # Cache with 1 hour TTL
            cache.set(cache_key, cache_data, 3600)
            
            return Response({
                'message': 'Cache warmed successfully',
                'cache_key': cache_key,
                'cached_at': cache_data['cached_at']
            })
            
        except Exception as e:
            logger.error(f"Failed to warm cache for user {user_id}: {e}")
            return Response(
                {'error': 'Failed to warm cache', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NotificationChannelEndpointViewSet(ModelViewSet):
    """
    ViewSet for managing user notification channel endpoints.

    Supports multi-address notification configuration with unlimited
    endpoints per channel type (email, telegram, slack, webhook, SMS).
    """

    serializer_class = NotificationChannelEndpointSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Return endpoints owned by the authenticated user."""
        return NotificationChannelEndpoint.objects.filter(
            owner_type='user',
            owner_id=self.request.user.id
        ).select_related('created_by').order_by('-created_at')

    def perform_create(self, serializer):
        """Create endpoint and set owner to current user."""
        serializer.save(
            owner_type='user',
            owner_id=self.request.user.id,
            created_by=self.request.user
        )

        # Invalidate user's notification cache
        self._invalidate_user_cache(self.request.user.id)

        logger.info(
            f"Created {serializer.validated_data['channel_type']} endpoint "
            f"'{serializer.validated_data['label']}' for user {self.request.user.id}"
        )

    def perform_update(self, serializer):
        """Update endpoint and invalidate cache."""
        instance = serializer.save()

        # Invalidate user's notification cache
        self._invalidate_user_cache(self.request.user.id)

        logger.info(
            f"Updated {instance.channel_type} endpoint '{instance.label}' "
            f"for user {self.request.user.id}"
        )

    def perform_destroy(self, instance):
        """Delete endpoint and invalidate cache."""
        channel_type = instance.channel_type
        label = instance.label
        user_id = instance.owner_id

        instance.delete()

        # Invalidate user's notification cache
        self._invalidate_user_cache(user_id)

        logger.info(
            f"Deleted {channel_type} endpoint '{label}' for user {user_id}"
        )

    @action(detail=True, methods=['post'])
    def request_verification(self, request, pk=None):
        """
        Request verification code for endpoint.

        Generates and sends a 6-digit verification code to the endpoint.
        Code expires in 15 minutes.

        For Telegram endpoints, the code is sent via the Telegram bot to the configured chat_id.
        """
        endpoint = self.get_object()

        # Check if endpoint requires verification
        if not endpoint.requires_reverification:
            return Response(
                {'error': f'{endpoint.channel_type} channels do not require verification'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if endpoint is already verified
        if endpoint.verified and endpoint.enabled:
            return Response(
                {'message': 'Endpoint is already verified'},
                status=status.HTTP_200_OK
            )

        # Generate verification code
        import random
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Create verification record
        verification = NotificationChannelVerification.objects.create(
            endpoint=endpoint,
            verification_code=code,
            verification_type='re_enable' if endpoint.verified else 'initial',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        # For Telegram, send verification code via bot
        if endpoint.channel_type == 'telegram':
            from app.services.telegram_cache_service import TelegramCacheService
            cache_service = TelegramCacheService()

            # Store verification code in Redis for Telegram provider access
            chat_id = endpoint.config.get('chat_id')
            if chat_id:
                cache_service.store_verification_code(
                    str(request.user.id),
                    chat_id,
                    code
                )

            # TODO: Trigger Telegram bot to send verification code
            # This will be handled by the Telegram provider via NATS or webhook

        logger.info(
            f"Generated verification code for {endpoint.channel_type} "
            f"endpoint '{endpoint.label}' (user {request.user.id})"
        )

        return Response({
            'message': f'Verification code sent to {endpoint.channel_type}',
            'verification_id': str(verification.id),
            'verification_code': code if endpoint.channel_type == 'telegram' else None,  # Return code for Telegram testing
            'expires_at': verification.expires_at.isoformat(),
            'verification_type': verification.verification_type
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Submit verification code to verify endpoint.

        Requires verification_code in request body.
        Marks endpoint as verified on success.
        """
        endpoint = self.get_object()
        serializer = VerificationCodeSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data['verification_code']

        # Find active verification record
        try:
            verification = NotificationChannelVerification.objects.get(
                endpoint=endpoint,
                verification_code=code,
                verified_at__isnull=True
            )
        except NotificationChannelVerification.DoesNotExist:
            return Response(
                {'error': 'Invalid verification code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if code is expired
        if verification.is_expired():
            return Response(
                {'error': 'Verification code has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update attempts
        verification.attempts += 1

        # Check max attempts
        if verification.attempts > 5:
            verification.save()
            return Response(
                {'error': 'Too many verification attempts. Please request a new code.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark verification as complete
        verification.verified_at = timezone.now()
        verification.save()

        # Mark endpoint as verified
        endpoint.verified = True
        endpoint.verified_at = timezone.now()
        endpoint.save()

        # Invalidate user's notification cache
        self._invalidate_user_cache(request.user.id)

        logger.info(
            f"Verified {endpoint.channel_type} endpoint '{endpoint.label}' "
            f"for user {request.user.id}"
        )

        return Response({
            'message': 'Endpoint verified successfully',
            'endpoint_id': str(endpoint.id),
            'verified_at': endpoint.verified_at.isoformat()
        })

    @action(detail=True, methods=['post'])
    def resend_verification(self, request, pk=None):
        """
        Resend verification code for endpoint.

        Invalidates previous codes and generates a new one.
        """
        endpoint = self.get_object()

        # Check if endpoint requires verification
        if not endpoint.requires_reverification:
            return Response(
                {'error': f'{endpoint.channel_type} channels do not require verification'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Invalidate previous verification codes
        NotificationChannelVerification.objects.filter(
            endpoint=endpoint,
            verified_at__isnull=True
        ).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        # Generate new verification code
        import random
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Create new verification record
        verification = NotificationChannelVerification.objects.create(
            endpoint=endpoint,
            verification_code=code,
            verification_type='re_enable' if endpoint.verified else 'initial',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        logger.info(
            f"Resent verification code for {endpoint.channel_type} "
            f"endpoint '{endpoint.label}' (user {request.user.id})"
        )

        return Response({
            'message': f'Verification code resent to {endpoint.channel_type}',
            'verification_id': str(verification.id),
            'expires_at': verification.expires_at.isoformat()
        })

    @action(detail=False, methods=['post'])
    def warm_cache(self, request):
        """
        Warm Redis cache for all user endpoints.

        Populates cache with endpoint configuration for wasmCloud access.
        Cache TTL: 1 hour.
        """
        user_id = request.user.id
        endpoints = self.get_queryset()

        # Build cache data structure
        cache_data = {
            'user_id': str(user_id),
            'endpoints': [ep.to_cache_format() for ep in endpoints],
            'cached_at': timezone.now().isoformat()
        }

        # Cache with 1 hour TTL (accessed by wasmCloud via Redis capability provider)
        cache_key = f"user:notification:endpoints:{user_id}"
        cache.set(cache_key, cache_data, 3600)

        logger.info(
            f"Warmed endpoint cache for user {user_id} "
            f"({endpoints.count()} endpoints)"
        )

        return Response({
            'message': 'Endpoint cache warmed successfully',
            'cache_key': cache_key,
            'endpoint_count': endpoints.count(),
            'cached_at': cache_data['cached_at'],
            'ttl_seconds': 3600
        })

    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """Clear Redis cache for user endpoints."""
        user_id = request.user.id
        self._invalidate_user_cache(user_id)

        return Response({'message': 'Endpoint cache cleared successfully'})

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Send a test message to the notification channel.

        Publishes a test notification to NATS with the configured endpoint.
        wasmCloud Slack provider will handle delivery.
        """
        endpoint = self.get_object()

        # Check if endpoint is enabled
        if not endpoint.enabled:
            return Response(
                {'error': 'Endpoint is disabled'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get optional test message from request
        test_message = request.data.get('message', 'Test notification from Ekko Dashboard')

        # For Slack and Telegram, publish test message to NATS
        if endpoint.channel_type in ['slack', 'telegram']:
            import json
            import asyncio
            from asgiref.sync import async_to_sync

            try:
                # Import NATS client (will be added via requirements.txt)
                import nats

                async def send_test_notification():
                    """Async function to send test notification via NATS."""
                    nc = await nats.connect("nats://localhost:4222")

                    # Build test notification payload
                    notification_payload = {
                        'user_id': str(request.user.id),
                        'alert_id': 'test-alert',
                        'alert_name': 'Test Alert',
                        'priority': 'normal',
                        'message': test_message,
                        'chain': 'ethereum',
                        'transaction_hash': '0x' + '0' * 64,  # Dummy transaction
                        'wallet_address': '0x' + '0' * 40,  # Dummy wallet
                        'timestamp': timezone.now().isoformat(),
                    }

                    # Publish to appropriate NATS subject
                    subject = f'notifications.{endpoint.channel_type}'
                    await nc.publish(
                        subject,
                        json.dumps(notification_payload).encode()
                    )

                    await nc.close()

                # Run async function
                async_to_sync(send_test_notification)()

                logger.info(
                    f"Sent test notification to {endpoint.channel_type} "
                    f"endpoint '{endpoint.label}' (user {request.user.id})"
                )

                return Response({
                    'success': True,
                    'message': f'Test message sent to {endpoint.channel_type}'
                })

            except Exception as e:
                logger.error(f"Failed to send test notification: {e}")
                return Response(
                    {'error': f'Failed to send test message: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # For other channel types, return not implemented
        return Response(
            {'error': f'Test messages not yet implemented for {endpoint.channel_type}'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Get delivery statistics for the notification channel.

        Retrieves success/failure counts from Redis cache.
        """
        endpoint = self.get_object()
        user_id = request.user.id

        # Get delivery stats from Redis based on channel type
        try:
            # Use channel-specific cache keys
            channel_type = endpoint.channel_type
            success_key = f"{channel_type}:stats:{user_id}:success"
            failure_key = f"{channel_type}:stats:{user_id}:failure"

            success_count = cache.get(success_key, 0)
            failure_count = cache.get(failure_key, 0)

            return Response({
                'channel_id': str(endpoint.id),
                'channel_type': channel_type,
                'success_count': success_count,
                'failure_count': failure_count,
                'total_count': success_count + failure_count,
                'success_rate': (success_count / (success_count + failure_count) * 100) if (success_count + failure_count) > 0 else 0
            })
        except Exception as e:
            logger.error(f"Failed to retrieve stats: {e}")
            return Response(
                {'error': f'Failed to retrieve statistics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def health(self, request, pk=None):
        """
        Get webhook health metrics for the endpoint.

        Only applicable for webhook endpoints. Returns health status including:
        - Success/failure counts
        - Average response time
        - Last success/failure timestamps
        - Consecutive failure count
        - Overall health status
        """
        endpoint = self.get_object()

        if endpoint.channel_type != 'webhook':
            return Response(
                {'error': 'Health metrics are only available for webhook endpoints'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get webhook URL from config
        webhook_url = endpoint.config.get('webhook_url')
        if not webhook_url:
            return Response(
                {'error': 'Webhook URL not configured'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Hash URL for Redis key (same logic as webhook provider)
        import hashlib
        url_hash = hashlib.md5(webhook_url.encode()).hexdigest()
        health_key = f"webhook:health:{url_hash}"

        try:
            # Get health metrics from Redis
            import json
            health_data = cache.get(health_key)

            if health_data:
                if isinstance(health_data, str):
                    health_metrics = json.loads(health_data)
                else:
                    health_metrics = health_data

                return Response({
                    'endpoint_url': webhook_url,
                    'success_count': health_metrics.get('success_count', 0),
                    'failure_count': health_metrics.get('failure_count', 0),
                    'avg_response_time_ms': health_metrics.get('avg_response_time_ms', 0),
                    'last_success_at': health_metrics.get('last_success_at'),
                    'last_failure_at': health_metrics.get('last_failure_at'),
                    'last_error': health_metrics.get('last_error'),
                    'consecutive_failures': health_metrics.get('consecutive_failures', 0),
                    'is_healthy': health_metrics.get('is_healthy', True),
                })
            else:
                # No metrics yet - return defaults
                return Response({
                    'endpoint_url': webhook_url,
                    'success_count': 0,
                    'failure_count': 0,
                    'avg_response_time_ms': 0,
                    'last_success_at': None,
                    'last_failure_at': None,
                    'last_error': None,
                    'consecutive_failures': 0,
                    'is_healthy': True,
                })
        except Exception as e:
            logger.error(f"Failed to retrieve webhook health metrics: {e}")
            return Response(
                {'error': f'Failed to retrieve health metrics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _invalidate_user_cache(self, user_id):
        """Helper to invalidate user's endpoint cache."""
        cache_key = f"user:notification:endpoints:{user_id}"
        cache.delete(cache_key)
        logger.debug(f"Invalidated endpoint cache for user {user_id}")


class TeamNotificationChannelEndpointViewSet(ModelViewSet):
    """
    ViewSet for managing team notification channel endpoints.

    Only team owners and admins can create, update, or delete team endpoints.
    Regular team members can view endpoints (with sensitive config masked).
    """

    serializer_class = TeamNotificationChannelEndpointSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Return endpoints for teams the user belongs to."""
        # Get teams where user is a member
        user_team_ids = TeamMember.objects.filter(
            user=self.request.user,
            is_active=True
        ).values_list('team_id', flat=True)

        return NotificationChannelEndpoint.objects.filter(
            owner_type='team',
            owner_id__in=user_team_ids
        ).select_related('created_by').order_by('-created_at')

    def _is_team_admin(self, team_id):
        """Check if current user is admin or owner of the team."""
        try:
            membership = TeamMember.objects.get(
                user=self.request.user,
                team_id=team_id,
                is_active=True
            )
            return membership.role in [TeamMemberRole.OWNER, TeamMemberRole.ADMIN]
        except TeamMember.DoesNotExist:
            return False

    def _check_team_admin_permission(self, team_id):
        """Verify user has admin permission for the team."""
        if not self._is_team_admin(team_id):
            return Response(
                {'error': 'Only team owners and admins can perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        return None

    def create(self, request, *args, **kwargs):
        """Create team endpoint - requires admin permission."""
        team_id = request.data.get('owner_id')

        if not team_id:
            return Response(
                {'error': 'owner_id (team ID) is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check admin permission
        error_response = self._check_team_admin_permission(team_id)
        if error_response:
            return error_response

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update team endpoint - requires admin permission."""
        endpoint = self.get_object()

        # Check admin permission
        error_response = self._check_team_admin_permission(endpoint.owner_id)
        if error_response:
            return error_response

        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Partial update team endpoint - requires admin permission."""
        endpoint = self.get_object()

        # Check admin permission
        error_response = self._check_team_admin_permission(endpoint.owner_id)
        if error_response:
            return error_response

        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete team endpoint - requires admin permission."""
        endpoint = self.get_object()

        # Check admin permission
        error_response = self._check_team_admin_permission(endpoint.owner_id)
        if error_response:
            return error_response

        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Create endpoint and set owner to team."""
        # owner_id comes from validated_data (user provides it in request)
        # owner_type is always 'team' for this ViewSet
        team_id = serializer.validated_data['owner_id']

        import sys
        print(f"XYZABC_TEAM_PERFORM_CREATE: team_id={team_id}", file=sys.stderr, flush=True)

        serializer.save(
            owner_type='team',
            owner_id=team_id,  # Explicitly set owner_id from validated data
            created_by=self.request.user
        )

        print(f"XYZABC_AFTER_SAVE", file=sys.stderr, flush=True)

        # Invalidate team's notification cache
        self._invalidate_team_cache(team_id)

        logger.info(
            f"Created {serializer.validated_data['channel_type']} endpoint "
            f"'{serializer.validated_data['label']}' for team {team_id} "
            f"by user {self.request.user.id}"
        )

    def perform_update(self, serializer):
        """Update endpoint and invalidate cache."""
        instance = serializer.save()

        # Invalidate team's notification cache
        self._invalidate_team_cache(instance.owner_id)

        logger.info(
            f"Updated {instance.channel_type} endpoint '{instance.label}' "
            f"for team {instance.owner_id} by user {self.request.user.id}"
        )

    def perform_destroy(self, instance):
        """Delete endpoint and invalidate cache."""
        channel_type = instance.channel_type
        label = instance.label
        team_id = instance.owner_id

        instance.delete()

        # Invalidate team's notification cache
        self._invalidate_team_cache(team_id)

        logger.info(
            f"Deleted {channel_type} endpoint '{label}' for team {team_id} "
            f"by user {self.request.user.id}"
        )

    @action(detail=False, methods=['post'])
    def warm_cache(self, request):
        """
        Warm Redis cache for team endpoints.

        Requires team_id parameter.
        Only team admins can warm cache.
        """
        team_id = request.data.get('team_id')

        if not team_id:
            return Response(
                {'error': 'team_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check admin permission
        error_response = self._check_team_admin_permission(team_id)
        if error_response:
            return error_response

        # Get team endpoints
        endpoints = NotificationChannelEndpoint.objects.filter(
            owner_type='team',
            owner_id=team_id
        )

        # Build cache data structure
        cache_data = {
            'team_id': str(team_id),
            'endpoints': [ep.to_cache_format() for ep in endpoints],
            'cached_at': timezone.now().isoformat()
        }

        # Cache with 1 hour TTL (accessed by wasmCloud via Redis capability provider)
        cache_key = f"team:notification:endpoints:{team_id}"
        cache.set(cache_key, cache_data, 3600)

        logger.info(
            f"Warmed endpoint cache for team {team_id} "
            f"({endpoints.count()} endpoints) by user {request.user.id}"
        )

        return Response({
            'message': 'Team endpoint cache warmed successfully',
            'cache_key': cache_key,
            'endpoint_count': endpoints.count(),
            'cached_at': cache_data['cached_at'],
            'ttl_seconds': 3600
        })

    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """
        Clear Redis cache for team endpoints.

        Requires team_id parameter.
        Only team admins can clear cache.
        """
        team_id = request.data.get('team_id')

        if not team_id:
            return Response(
                {'error': 'team_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check admin permission
        error_response = self._check_team_admin_permission(team_id)
        if error_response:
            return error_response

        self._invalidate_team_cache(team_id)

        return Response({'message': 'Team endpoint cache cleared successfully'})

    def _invalidate_team_cache(self, team_id):
        """Helper to invalidate team's endpoint cache."""
        cache_key = f"team:notification:endpoints:{team_id}"
        cache.delete(cache_key)
        logger.debug(f"Invalidated endpoint cache for team {team_id}")


class TeamMemberNotificationOverrideViewSet(ModelViewSet):
    """
    ViewSet for managing team member notification overrides.

    Allows team members to control their own notification preferences
    for team-level alerts. Members can only manage their own overrides.
    """

    serializer_class = TeamMemberNotificationOverrideSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Override settings are per-member, no pagination needed

    def get_queryset(self):
        """Return overrides for the authenticated user across all teams."""
        return TeamMemberNotificationOverride.objects.filter(
            member=self.request.user
        ).select_related('team', 'member')

    def get_object(self):
        """
        Get override for specific team.

        Supports lookup by 'team' query parameter or pk.
        Creates default override if none exists.
        """
        team_id = self.request.query_params.get('team') or self.kwargs.get('pk')

        if not team_id:
            raise ValueError("team ID is required")

        # Verify user is a member of the team
        try:
            TeamMember.objects.get(
                team_id=team_id,
                user=self.request.user,
                is_active=True
            )
        except TeamMember.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of this team")

        # Get or create override
        override, created = TeamMemberNotificationOverride.objects.get_or_create(
            team_id=team_id,
            member=self.request.user,
            defaults={
                'team_notifications_enabled': True,
                'disabled_endpoints': [],
                'disabled_priorities': []
            }
        )

        return override

    def list(self, request):
        """List all overrides for the authenticated user."""
        overrides = self.get_queryset()
        serializer = self.get_serializer(overrides, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Get override for specific team."""
        try:
            override = self.get_object()
            serializer = self.get_serializer(override)
            return Response(serializer.data)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def create(self, request):
        """Create or update override for a team."""
        team_id = request.data.get('team')

        if not team_id:
            return Response(
                {'error': 'team ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify user is a member of the team
        try:
            TeamMember.objects.get(
                team_id=team_id,
                user=request.user,
                is_active=True
            )
        except TeamMember.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this team'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get or create override
        override, created = TeamMemberNotificationOverride.objects.get_or_create(
            team_id=team_id,
            member=request.user,
            defaults={
                'team_notifications_enabled': True,
                'disabled_endpoints': [],
                'disabled_priorities': []
            }
        )

        # Update with provided data
        serializer = self.get_serializer(override, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Invalidate member's override cache
        self._invalidate_member_override_cache(request.user.id, team_id)

        logger.info(
            f"{'Created' if created else 'Updated'} notification override "
            f"for user {request.user.id} in team {team_id}"
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """Update override for a team."""
        try:
            override = self.get_object()
            # Use partial from kwargs (True for PATCH, False for PUT)
            partial = kwargs.get('partial', False)
            serializer = self.get_serializer(override, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            # Invalidate member's override cache
            self._invalidate_member_override_cache(request.user.id, override.team.id)

            logger.info(
                f"Updated notification override for user {request.user.id} "
                f"in team {override.team.id}"
            )

            return Response(serializer.data)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, pk=None):
        """Reset override to defaults (enable all notifications)."""
        try:
            override = self.get_object()
            team_id = override.team.id

            # Reset to defaults instead of deleting
            override.team_notifications_enabled = True
            override.disabled_endpoints = []
            override.disabled_priorities = []
            override.save()

            # Invalidate member's override cache
            self._invalidate_member_override_cache(request.user.id, team_id)

            logger.info(
                f"Reset notification override for user {request.user.id} "
                f"in team {team_id}"
            )

            return Response({
                'message': 'Notification override reset to defaults'
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def disable_all_team_notifications(self, request):
        """
        Disable all team notifications for a specific team.

        Master switch to turn off all team notifications.
        """
        team_id = request.data.get('team')

        if not team_id:
            return Response(
                {'error': 'team ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify user is a member of the team
        try:
            TeamMember.objects.get(
                team_id=team_id,
                user=request.user,
                is_active=True
            )
        except TeamMember.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this team'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get or create override and disable all notifications
        override, created = TeamMemberNotificationOverride.objects.get_or_create(
            team_id=team_id,
            member=request.user,
            defaults={'team_notifications_enabled': False}
        )

        if not created:
            override.team_notifications_enabled = False
            override.save()

        # Invalidate member's override cache
        self._invalidate_member_override_cache(request.user.id, team_id)

        logger.info(
            f"Disabled all team notifications for user {request.user.id} "
            f"in team {team_id}"
        )

        return Response({
            'message': 'All team notifications disabled',
            'team_id': str(team_id)
        })

    @action(detail=False, methods=['post'])
    def enable_all_team_notifications(self, request):
        """
        Enable all team notifications for a specific team.

        Master switch to turn on all team notifications.
        """
        team_id = request.data.get('team')

        if not team_id:
            return Response(
                {'error': 'team ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify user is a member of the team
        try:
            TeamMember.objects.get(
                team_id=team_id,
                user=request.user,
                is_active=True
            )
        except TeamMember.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this team'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get or create override and enable all notifications
        override, created = TeamMemberNotificationOverride.objects.get_or_create(
            team_id=team_id,
            member=request.user,
            defaults={'team_notifications_enabled': True}
        )

        if not created:
            override.team_notifications_enabled = True
            override.save()

        # Invalidate member's override cache
        self._invalidate_member_override_cache(request.user.id, team_id)

        logger.info(
            f"Enabled all team notifications for user {request.user.id} "
            f"in team {team_id}"
        )

        return Response({
            'message': 'All team notifications enabled',
            'team_id': str(team_id)
        })

    def _invalidate_member_override_cache(self, user_id, team_id):
        """Helper to invalidate member's override cache."""
        cache_key = f"team:notification:override:{team_id}:{user_id}"
        cache.delete(cache_key)
        logger.debug(
            f"Invalidated override cache for user {user_id} in team {team_id}"
        )


class GroupNotificationSettingsViewSet(ModelViewSet):
    """ViewSet for managing group notification settings."""
    
    serializer_class = GroupNotificationSettingsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    
    def get_queryset(self):
        """Return settings for groups the user belongs to."""
        # Get teams the user is a member of
        user_teams = Team.objects.filter(members=self.request.user)
        return GroupNotificationSettings.objects.filter(group__in=user_teams)
    
    @action(detail=True, methods=['post'])
    def test_group_notification(self, request, pk=None):
        """Validate group notification settings."""
        group_settings = self.get_object()
        serializer = NotificationTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        channel = serializer.validated_data['channel']
        
        # Check if group has shared channel configuration
        if channel not in group_settings.shared_channels:
            return Response(
                {'error': f'Group does not have {channel} configured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate channel configuration
        channel_config = group_settings.shared_channels.get(channel, {})
        if not channel_config.get('enabled', False):
            return Response(
                {'error': f'Group {channel} channel is not properly configured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Group notification settings validated for group {group_settings.group.id} via {channel}")
        
        return Response({
            'message': f'Group notification settings validated for {group_settings.group.name}',
            'channel': channel,
            'group': group_settings.group.name,
            'status': 'validated'
        })


class NotificationDeliveryViewSet(ReadOnlyModelViewSet):
    """ViewSet for viewing notification delivery history."""
    
    serializer_class = NotificationDeliverySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Return deliveries for current user's notifications."""
        queryset = NotificationDelivery.objects.filter(
            user=self.request.user
        ).select_related('alert', 'user').order_by('-created_at')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by channel
        channel_filter = self.request.query_params.get('channel')
        if channel_filter:
            queryset = queryset.filter(channel=channel_filter)
        
        # Filter by date range
        days_back = self.request.query_params.get('days', 30)
        try:
            days_back = int(days_back)
            since = timezone.now() - timedelta(days=days_back)
            queryset = queryset.filter(created_at__gte=since)
        except (ValueError, TypeError):
            pass
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get delivery statistics for current user."""
        queryset = self.get_queryset()
        
        stats = queryset.aggregate(
            total=Count('id'),
            delivered=Count('id', filter=Q(status='delivered')),
            failed=Count('id', filter=Q(status='failed')),
            pending=Count('id', filter=Q(status='pending'))
        )
        
        # Channel breakdown
        channel_stats = queryset.values('channel').annotate(
            count=Count('id'),
            success_rate=Count('id', filter=Q(status='delivered')) * 100.0 / Count('id')
        ).order_by('-count')
        
        # Recent activity (last 7 days)
        recent = queryset.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        return Response({
            'total_deliveries': stats['total'],
            'success_rate': (stats['delivered'] / stats['total'] * 100) if stats['total'] else 0,
            'delivery_breakdown': {
                'delivered': stats['delivered'],
                'failed': stats['failed'],
                'pending': stats['pending']
            },
            'channel_statistics': list(channel_stats),
            'recent_activity': recent
        })


class NotificationTemplateViewSet(ModelViewSet):
    """ViewSet for managing notification templates."""
    
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Return all active templates."""
        queryset = NotificationTemplate.objects.filter(active=True)
        
        # Filter by channel
        channel = self.request.query_params.get('channel')
        if channel:
            queryset = queryset.filter(channel=channel)
        
        # Filter by template type
        template_type = self.request.query_params.get('type')
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        
        return queryset.order_by('name')
    
    @action(detail=True, methods=['post'])
    def render(self, request, pk=None):
        """Render template with provided variables."""
        template = self.get_object()
        variables = request.data.get('variables', {})
        
        try:
            rendered = template.render(variables)
            return Response({
                'template_name': template.name,
                'variables': variables,
                'rendered': rendered
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def channels(self, request):
        """Get available channels and their template counts."""
        from django.db.models import Count
        
        channel_stats = NotificationTemplate.objects.filter(active=True).values(
            'channel'
        ).annotate(
            count=Count('id')
        ).order_by('channel')
        
        return Response(list(channel_stats))


class BulkNotificationAPIView(APIView):
    """API endpoint for sending bulk notifications."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Send notifications to multiple users."""
        serializer = BulkNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_ids = serializer.validated_data['user_ids']
        template_name = serializer.validated_data['template_name']
        template_variables = serializer.validated_data['template_variables']
        channels = serializer.validated_data.get('channels', [])
        priority = serializer.validated_data['priority']
        
        # Validate template exists
        try:
            template = NotificationTemplate.objects.get(name=template_name, active=True)
        except NotificationTemplate.DoesNotExist:
            return Response(
                {'error': f'Template {template_name} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate users exist
        existing_users = User.objects.filter(id__in=user_ids).values_list('id', flat=True)
        invalid_users = set(user_ids) - set(existing_users)
        
        if invalid_users:
            return Response(
                {'error': f'Invalid user IDs: {list(invalid_users)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that we can send to all users
        failed_users = []
        for user_id in existing_users:
            try:
                user_settings = UserNotificationSettings.objects.get(user_id=user_id)
                if not user_settings.notifications_enabled:
                    failed_users.append(user_id)
            except UserNotificationSettings.DoesNotExist:
                # User has default settings, which allow notifications
                pass
        
        logger.info(
            f"Bulk notification validated for {len(user_ids)} users "
            f"using template {template_name} with priority {priority}"
        )
        
        response_data = {
            'message': f'Bulk notification request validated for {len(user_ids)} users',
            'template': template_name,
            'priority': priority,
            'channels': channels or 'user preferences',
            'users_count': len(user_ids),
            'validated': True
        }
        
        if failed_users:
            response_data['warnings'] = {
                'disabled_users': failed_users,
                'message': f'{len(failed_users)} users have notifications disabled'
            }
        
        return Response(response_data)


class NotificationCacheAPIView(APIView):
    """API endpoint for cache management and statistics."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get cache statistics."""
        stats = NotificationCache.get_cache_stats()
        serializer = CacheStatsSerializer(stats)
        return Response(serializer.data)
    
    def post(self, request):
        """Warm cache for specified users."""
        user_ids = request.data.get('user_ids', [])
        
        if not user_ids:
            return Response(
                {'error': 'user_ids list is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cached_count = NotificationCache.warm_user_cache(user_ids)
        
        return Response({
            'message': f'Cache warmed for {cached_count}/{len(user_ids)} users',
            'cached_count': cached_count,
            'requested_count': len(user_ids)
        })
    
    def delete(self, request):
        """Clear notification caches."""
        cache_type = request.query_params.get('type', 'user')
        
        if cache_type == 'all':
            NotificationCache.clear_all_user_caches()
            message = 'All caches cleared'
        else:
            user_id = request.query_params.get('user_id')
            if user_id:
                try:
                    settings = UserNotificationSettings.objects.get(user_id=user_id)
                    settings.invalidate_cache()
                    message = f'Cache cleared for user {user_id}'
                except UserNotificationSettings.DoesNotExist:
                    return Response(
                        {'error': f'User {user_id} not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                return Response(
                    {'error': 'user_id is required for user cache clearing'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response({'message': message})


class NotificationHealthAPIView(APIView):
    """Health check endpoint for notification system."""
    
    permission_classes = []  # Allow unauthenticated access for health checks
    
    def get(self, request):
        """Check notification system health."""
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now(),
            'checks': {}
        }
        
        try:
            # Test database connectivity
            user_count = UserNotificationSettings.objects.count()
            health_status['checks']['database'] = {
                'status': 'healthy',
                'user_settings_count': user_count
            }
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['checks']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        try:
            # Test Redis connectivity
            cache.get('health_check_key')
            health_status['checks']['redis'] = {
                'status': 'healthy',
                'message': 'Cache accessible'
            }
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['checks']['redis'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # NATS connectivity handled by wasmCloud
        health_status['checks']['wasmcloud_integration'] = {
            'status': 'healthy',
            'message': 'Notification delivery handled by wasmCloud providers'
        }
        
        status_code = status.HTTP_200_OK if health_status['status'] == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(health_status, status=status_code)


class PlatformHealthMetricsAPIView(APIView):
    """
    Platform-wide notification delivery health metrics from DuckLake.

    Provides aggregated analytics on notification delivery performance,
    success rates, response times, and error patterns across all channels.
    Data is queried from DuckLake (DuckDB/DuckLake) via NATS.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get platform health metrics for a time period.

        Query Parameters:
            - time_range: Time range for metrics (24h, 7d, 30d, default: 24h)
            - channel_type: Optional filter by channel (slack, telegram, webhook)

        Returns:
            - total_deliveries: Total number of delivery attempts
            - successful_deliveries: Number of successful deliveries
            - failed_deliveries: Number of failed deliveries
            - success_rate: Overall success rate percentage
            - avg_response_time_ms: Average response time
            - p50_response_time_ms: Median response time
            - p95_response_time_ms: 95th percentile response time
            - p99_response_time_ms: 99th percentile response time
            - error_breakdown: Count of errors by type
            - hourly_volume: Hourly delivery volume trends
            - channel_breakdown: Per-channel statistics
        """
        from datetime import datetime, timedelta

        # Parse query parameters
        time_range = request.query_params.get('time_range', '24h')
        channel_type = request.query_params.get('channel_type')

        # Calculate time range
        end_date = datetime.utcnow()
        if time_range == '24h':
            start_date = end_date - timedelta(hours=24)
        elif time_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif time_range == '30d':
            start_date = end_date - timedelta(days=30)
        else:
            return Response(
                {'error': 'Invalid time_range. Use 24h, 7d, or 30d'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate channel_type if provided
        if channel_type and channel_type not in ['slack', 'telegram', 'webhook']:
            return Response(
                {'error': 'Invalid channel_type. Use slack, telegram, or webhook'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            async def run_query() -> DeliveryMetrics:
                client = DuckLakeClient()
                try:
                    return await client.get_platform_metrics(start_date, end_date, channel_type)
                finally:
                    await client.close()

            metrics = async_to_sync(run_query)()

            # Format response
            response_data = {
                'time_range': time_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'channel_type': channel_type or 'all',
                'metrics': {
                    'total_deliveries': metrics.total_deliveries,
                    'successful_deliveries': metrics.successful_deliveries,
                    'failed_deliveries': metrics.failed_deliveries,
                    'success_rate': round(metrics.success_rate, 2),
                    'performance': {
                        'avg_response_time_ms': round(metrics.avg_response_time_ms, 2),
                        'p50_response_time_ms': round(metrics.p50_response_time_ms, 2),
                        'p95_response_time_ms': round(metrics.p95_response_time_ms, 2),
                        'p99_response_time_ms': round(metrics.p99_response_time_ms, 2),
                    },
                    'errors': metrics.error_breakdown,
                    'hourly_volume': metrics.hourly_volume,
                    'channels': metrics.channel_breakdown
                }
            }

            logger.info(
                f"Platform health metrics retrieved for {time_range} "
                f"(channel: {channel_type or 'all'})"
            )

            return Response(response_data)

        except Exception as e:
            logger.error(f"Failed to retrieve platform health metrics: {e}")
            return Response(
                {'error': f'Failed to retrieve metrics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserNotificationHistoryAPIView(APIView):
    """
    User notification history from DuckLake.

    Provides paginated access to a user's notification history stored
    in the DuckLake notification_content table. Supports filtering by
    priority, alert, and date range.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get notification history for the authenticated user.

        Query Parameters:
            - limit: Maximum results to return (default: 50, max: 100)
            - offset: Number of results to skip for pagination (default: 0)
            - priority: Filter by priority (critical, high, normal, low)
            - alert_id: Filter by specific alert
            - start_date: Start of date range (ISO 8601 format)
            - end_date: End of date range (ISO 8601 format)

        Returns:
            - count: Total number of matching notifications
            - results: List of notification items
            - has_more: Whether there are more results available
        """
        from datetime import datetime

        # Parse query parameters
        try:
            limit = int(request.query_params.get('limit', 50))
            limit = min(max(1, limit), 100)  # Cap between 1 and 100
        except ValueError:
            limit = 50

        try:
            offset = int(request.query_params.get('offset', 0))
            offset = max(0, offset)  # Ensure non-negative
        except ValueError:
            offset = 0

        priority = request.query_params.get('priority')
        alert_id = request.query_params.get('alert_id')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        # Parse date strings
        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            except ValueError:
                return Response(
                    {'error': 'Invalid start_date format. Use ISO 8601 format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except ValueError:
                return Response(
                    {'error': 'Invalid end_date format. Use ISO 8601 format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validate priority if provided
        valid_priorities = ['critical', 'high', 'normal', 'low']
        if priority and priority.lower() not in valid_priorities:
            return Response(
                {'error': f'Invalid priority. Use one of: {", ".join(valid_priorities)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_id = str(request.user.id)

            async def run_query() -> NotificationHistoryResponse:
                client = DuckLakeClient()
                try:
                    return await client.get_user_notifications(
                        user_id=user_id,
                        limit=limit,
                        offset=offset,
                        priority=priority.lower() if priority else None,
                        alert_id=alert_id,
                        start_date=start_date,
                        end_date=end_date,
                    )
                finally:
                    await client.close()

            history = async_to_sync(run_query)()

            # Format response
            results = []
            for item in history.items:
                title = item.title or item.alert_name or ""
                message = item.message or item.title or item.alert_name or ""
                results.append({
                    'notification_id': item.notification_id,
                    'alert_id': item.alert_id,
                    'alert_name': item.alert_name,
                    'title': title,
                    'message': message,
                    'priority': item.priority,
                    'delivery_status': item.delivery_status,
                    'channels_delivered': item.channels_delivered,
                    'channels_failed': item.channels_failed,
                    'created_at': item.created_at.isoformat() if item.created_at else None,
                    'transaction_hash': item.transaction_hash,
                    'chain_id': item.chain_id,
                    'block_number': item.block_number,
                    'value_usd': item.value_usd,
                    'target_channels': item.target_channels,
                })

            logger.info(
                f"Retrieved {len(results)} notifications for user {user_id} "
                f"(total: {history.count})"
            )

            return Response({
                'count': history.count,
                'results': results,
                'has_more': history.has_more,
            })

        except Exception as e:
            logger.error(f"Failed to retrieve notification history: {e}")
            return Response(
                {'error': f'Failed to retrieve notification history: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChannelHealthMetricsAPIView(APIView):
    """
    Per-channel notification delivery health metrics from DuckLake.

    Provides detailed health metrics for a specific notification channel,
    including success rates, response times, and recent errors.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, channel_id):
        """
        Get health metrics for a specific notification channel.

        Path Parameters:
            - channel_id: Channel identifier (user_id)

        Query Parameters:
            - lookback_hours: Hours to look back (default: 24)

        Returns:
            - channel_id: Channel identifier
            - channel_type: Type of channel (slack, telegram, webhook)
            - total_deliveries: Total delivery attempts
            - successful_deliveries: Successful deliveries
            - failed_deliveries: Failed deliveries
            - success_rate: Success rate percentage
            - avg_response_time_ms: Average response time
            - last_success_at: Timestamp of last successful delivery
            - last_failure_at: Timestamp of last failed delivery
            - last_error: Last error message
            - consecutive_failures: Count of consecutive failures
            - is_healthy: Overall health status
        """
        # Parse query parameters
        lookback_hours = int(request.query_params.get('lookback_hours', 24))

        if lookback_hours < 1 or lookback_hours > 168:  # Max 7 days
            return Response(
                {'error': 'lookback_hours must be between 1 and 168'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            async def run_query() -> ChannelHealthMetrics:
                client = DuckLakeClient()
                try:
                    return await client.get_channel_health(channel_id, lookback_hours)
                finally:
                    await client.close()

            metrics = async_to_sync(run_query)()

            # Format response
            response_data = {
                'channel_id': metrics.channel_id,
                'channel_type': metrics.channel_type,
                'lookback_hours': lookback_hours,
                'metrics': {
                    'total_deliveries': metrics.total_deliveries,
                    'successful_deliveries': metrics.successful_deliveries,
                    'failed_deliveries': metrics.failed_deliveries,
                    'success_rate': round(metrics.success_rate, 2),
                    'avg_response_time_ms': round(metrics.avg_response_time_ms, 2),
                    'last_success_at': metrics.last_success_at.isoformat() if metrics.last_success_at else None,
                    'last_failure_at': metrics.last_failure_at.isoformat() if metrics.last_failure_at else None,
                    'last_error': metrics.last_error,
                    'consecutive_failures': metrics.consecutive_failures,
                    'is_healthy': metrics.is_healthy
                }
            }

            logger.info(f"Channel health metrics retrieved for {channel_id}")

            return Response(response_data)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to retrieve channel health metrics: {e}")
            return Response(
                {'error': f'Failed to retrieve metrics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
