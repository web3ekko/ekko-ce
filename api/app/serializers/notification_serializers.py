"""
Serializers for notification system API endpoints.

This module provides Django REST framework serializers for user and group
notification settings, delivery tracking, and template management.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from app.models.notifications import (
    UserNotificationSettings, GroupNotificationSettings,
    NotificationDelivery, NotificationTemplate,
    NotificationChannelEndpoint, TeamMemberNotificationOverride,
    NotificationChannelVerification
)
from organizations.models import Team, TeamMember, TeamMemberRole

User = get_user_model()


class ChannelSettingsSerializer(serializers.Serializer):
    """Serializer for individual channel settings."""
    enabled = serializers.BooleanField()
    config = serializers.DictField(
        child=serializers.CharField(),
        allow_empty=True
    )


class QuietHoursSerializer(serializers.Serializer):
    """Serializer for quiet hours configuration."""
    start_time = serializers.RegexField(
        regex=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
        help_text="Start time in HH:MM format"
    )
    end_time = serializers.RegexField(
        regex=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
        help_text="End time in HH:MM format"
    )
    timezone = serializers.CharField(max_length=50)
    enabled = serializers.BooleanField()
    priority_override = serializers.ListField(
        child=serializers.ChoiceField(choices=['critical', 'high', 'normal', 'low']),
        allow_empty=True,
        help_text="Priority levels that ignore quiet hours"
    )


class UserNotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user notification settings."""
    
    channels = serializers.DictField(
        child=ChannelSettingsSerializer(),
        allow_empty=True
    )
    priority_routing = serializers.DictField(
        child=serializers.ListField(
            child=serializers.ChoiceField(choices=[
                'email', 'slack', 'sms', 'telegram', 'discord', 'webhook', 'websocket'
            ])
        ),
        allow_empty=True
    )
    quiet_hours = QuietHoursSerializer(allow_null=True, required=False)
    
    class Meta:
        model = UserNotificationSettings
        fields = [
            'id', 'websocket_enabled', 'notifications_enabled',
            'channels', 'priority_routing', 'quiet_hours',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_channels(self, channels):
        """Validate channel configurations."""
        valid_channels = ['email', 'slack', 'sms', 'telegram', 'discord', 'webhook', 'websocket']
        
        for channel_name, settings in channels.items():
            if channel_name not in valid_channels:
                raise serializers.ValidationError(f"Invalid channel: {channel_name}")
            
            # Channel-specific validation
            if settings.get('enabled', False):
                config = settings.get('config', {})
                
                if channel_name == 'email' and 'address' not in config:
                    raise serializers.ValidationError(
                        f"Email channel requires 'address' in config"
                    )
                elif channel_name == 'sms' and 'phone' not in config:
                    raise serializers.ValidationError(
                        f"SMS channel requires 'phone' in config"
                    )
                elif channel_name == 'slack' and 'channel' not in config:
                    raise serializers.ValidationError(
                        f"Slack channel requires 'channel' in config"
                    )
                elif channel_name in ['webhook', 'discord']:
                    url_key = 'webhook_url' if 'webhook_url' in config else 'url'
                    if url_key not in config:
                        raise serializers.ValidationError(
                            f"{channel_name.title()} channel requires '{url_key}' in config"
                        )
        
        return channels
    
    def create(self, validated_data):
        """Create notification settings for the authenticated user."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class GroupNotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for group notification settings."""
    
    group_name = serializers.CharField(source='group.name', read_only=True)
    mandatory_channels = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'email', 'slack', 'sms', 'telegram', 'discord', 'webhook', 'websocket'
        ]),
        allow_empty=True
    )
    shared_channels = serializers.DictField(
        child=ChannelSettingsSerializer(),
        allow_empty=True
    )
    
    class Meta:
        model = GroupNotificationSettings
        fields = [
            'id', 'group_name', 'mandatory_channels', 'escalation_rules',
            'shared_channels', 'member_overrides_allowed',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'group_name', 'created_at', 'updated_at']


class NotificationDeliverySerializer(serializers.ModelSerializer):
    """Serializer for notification delivery tracking."""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    alert_name = serializers.CharField(source='alert.name', read_only=True)
    
    class Meta:
        model = NotificationDelivery
        fields = [
            'id', 'notification_id', 'user_username', 'alert_name',
            'channel', 'status', 'external_message_id', 'provider_response',
            'error_code', 'error_message', 'retry_count',
            'created_at', 'delivered_at', 'retry_after'
        ]
        read_only_fields = ['id', 'user_username', 'alert_name']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for notification templates."""
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'template_type', 'channel',
            'subject_template', 'text_template', 'html_template',
            'structured_template', 'required_variables', 'active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate template data."""
        # Ensure required templates are present
        if not data.get('text_template'):
            raise serializers.ValidationError("text_template is required")
        
        # Channel-specific validation
        channel = data.get('channel')
        if channel in ['email', 'slack', 'websocket'] and not data.get('subject_template'):
            raise serializers.ValidationError(
                f"subject_template is required for {channel} channel"
            )
        
        return data


class NotificationTestSerializer(serializers.Serializer):
    """Serializer for testing notification delivery."""
    
    channel = serializers.ChoiceField(choices=[
        'email', 'slack', 'sms', 'telegram', 'discord', 'webhook', 'websocket'
    ])
    message = serializers.CharField(max_length=500)
    subject = serializers.CharField(max_length=200, required=False)
    
    def validate(self, data):
        """Validate test notification data."""
        channel = data.get('channel')
        
        # Email and WebSocket require subject
        if channel in ['email', 'websocket'] and not data.get('subject'):
            raise serializers.ValidationError(
                f"subject is required for {channel} channel"
            )
        
        return data


class BulkNotificationSerializer(serializers.Serializer):
    """Serializer for bulk notification operations."""
    
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=1000,
        help_text="List of user IDs to send notifications to"
    )
    template_name = serializers.CharField(max_length=100)
    template_variables = serializers.DictField(
        child=serializers.CharField(),
        allow_empty=True
    )
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'email', 'slack', 'sms', 'telegram', 'discord', 'webhook', 'websocket'
        ]),
        allow_empty=True,
        help_text="Channels to send on (empty means use user preferences)"
    )
    priority = serializers.ChoiceField(
        choices=['critical', 'high', 'normal', 'low'],
        default='normal'
    )


class CacheStatsSerializer(serializers.Serializer):
    """Serializer for cache statistics."""
    
    cache_hits = serializers.IntegerField(read_only=True)
    cache_misses = serializers.IntegerField(read_only=True)
    cached_users = serializers.IntegerField(read_only=True)
    cached_groups = serializers.IntegerField(read_only=True)
    last_updated = serializers.DateTimeField(read_only=True)


class NotificationChannelConfigSerializer(serializers.Serializer):
    """Serializer for channel configuration templates."""
    
    channel = serializers.ChoiceField(choices=[
        'email', 'slack', 'sms', 'telegram', 'discord', 'webhook', 'websocket'
    ])
    
    def to_representation(self, instance):
        """Return configuration template for the requested channel."""
        channel = self.context.get('channel', instance)
        
        templates = {
            'email': {
                'enabled': True,
                'config': {
                    'address': 'user@example.com'
                }
            },
            'slack': {
                'enabled': True,
                'config': {
                    'channel': '#alerts',
                    'webhook_url': 'https://hooks.slack.com/services/...'
                }
            },
            'sms': {
                'enabled': True,
                'config': {
                    'phone': '+1234567890'
                }
            },
            'telegram': {
                'enabled': True,
                'config': {
                    'chat_id': '123456789'
                }
            },
            'discord': {
                'enabled': True,
                'config': {
                    'webhook_url': 'https://discord.com/api/webhooks/...'
                }
            },
            'webhook': {
                'enabled': True,
                'config': {
                    'url': 'https://api.example.com/webhook',
                    'auth_header': 'Bearer token'
                }
            },
            'websocket': {
                'enabled': True,
                'config': {}
            }
        }
        
        return {
            'channel': channel,
            'template': templates.get(channel, {}),
            'description': self._get_channel_description(channel),
            'required_config': self._get_required_config(channel)
        }
    
    def _get_channel_description(self, channel: str) -> str:
        """Get human-readable description for channel."""
        descriptions = {
            'email': 'Email notifications sent to user\'s email address',
            'slack': 'Messages posted to Slack channels or via webhooks',
            'sms': 'Text messages sent to user\'s phone number',
            'telegram': 'Messages sent via Telegram bot',
            'discord': 'Messages posted to Discord channels via webhooks',
            'webhook': 'HTTP POST requests to custom webhook URLs',
            'websocket': 'Real-time notifications via WebSocket connection'
        }
        return descriptions.get(channel, '')
    
    def _get_required_config(self, channel: str) -> list:
        """Get list of required configuration fields."""
        required = {
            'email': ['address'],
            'slack': ['channel'],
            'sms': ['phone'],
            'telegram': ['chat_id'],
            'discord': ['webhook_url'],
            'webhook': ['url'],
            'websocket': []
        }
        return required.get(channel, [])


# ===================================================================
# Multi-Address Notification Endpoint Serializers
# ===================================================================

class NotificationChannelEndpointSerializer(serializers.ModelSerializer):
    """Serializer for NotificationChannelEndpoint model."""

    requires_reverification = serializers.ReadOnlyField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = NotificationChannelEndpoint
        fields = [
            'id', 'owner_type', 'owner_id', 'channel_type', 'label',
            'config', 'enabled', 'verified', 'verified_at',
            'routing_mode', 'priority_filters', 'requires_reverification',
            'created_at', 'updated_at', 'created_by_email'
        ]
        read_only_fields = [
            'id', 'verified', 'verified_at', 'created_at',
            'updated_at', 'requires_reverification'
        ]


    def validate_label(self, value):
        """Validate label format and uniqueness."""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Label cannot be empty")

        if len(value) > 100:
            raise serializers.ValidationError("Label cannot exceed 100 characters")

        # Check label uniqueness for owner+channel
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            owner_type = self.initial_data.get('owner_type', 'user')
            owner_id = self.initial_data.get('owner_id', request.user.id)
            channel_type = self.initial_data.get('channel_type')

            # Exclude current instance if updating
            queryset = NotificationChannelEndpoint.objects.filter(
                owner_type=owner_type,
                owner_id=owner_id,
                channel_type=channel_type,
                label__iexact=value  # Case-insensitive comparison
            )

            if self.instance:
                queryset = queryset.exclude(id=self.instance.id)

            if queryset.exists():
                raise serializers.ValidationError(
                    f"Label '{value}' already exists for this {channel_type} channel"
                )

        return value.strip()

    def validate_config(self, value):
        """Validate channel-specific configuration."""
        channel_type = self.initial_data.get('channel_type')

        if channel_type == 'email':
            if 'address' not in value:
                raise serializers.ValidationError("Email channel requires 'address' in config")
            # Validate email format
            email_validator = serializers.EmailField()
            email_validator.run_validation(value['address'])

        elif channel_type == 'sms':
            if 'phone_number' not in value:
                raise serializers.ValidationError("SMS channel requires 'phone_number' in config")

        elif channel_type == 'telegram':
            if 'chat_id' not in value:
                raise serializers.ValidationError("Telegram channel requires 'chat_id' in config")

        elif channel_type == 'slack':
            if 'webhook_url' not in value:
                raise serializers.ValidationError("Slack channel requires 'webhook_url' in config")
            if not value['webhook_url'].startswith('https://'):
                raise serializers.ValidationError("Slack webhook URL must use HTTPS")

        elif channel_type == 'webhook':
            if 'url' not in value:
                raise serializers.ValidationError("Webhook channel requires 'url' in config")
            if not value['url'].startswith(('http://', 'https://')):
                raise serializers.ValidationError("Webhook URL must start with http:// or https://")

        return value

    def validate_priority_filters(self, value):
        """Validate priority filters."""
        valid_priorities = ['critical', 'high', 'normal', 'low']

        if not isinstance(value, list):
            raise serializers.ValidationError("Priority filters must be a list")

        for priority in value:
            if priority not in valid_priorities:
                raise serializers.ValidationError(
                    f"Invalid priority '{priority}'. Must be one of: {', '.join(valid_priorities)}"
                )

        return value

    def create(self, validated_data):
        """Create endpoint and set created_by from request user."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user

        # Auto-verify webhook and slack channels
        if validated_data.get('channel_type') in ['webhook', 'slack']:
            validated_data['verified'] = True
            validated_data['verified_at'] = serializers.timezone.now()

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Handle re-verification when re-enabling security-sensitive channels."""
        # Check if enabling a previously disabled security-sensitive channel
        was_disabled = not instance.enabled
        will_be_enabled = validated_data.get('enabled', instance.enabled)

        if was_disabled and will_be_enabled and instance.requires_reverification:
            # Mark as unverified, requiring re-verification
            validated_data['verified'] = False
            validated_data['verified_at'] = None

        return super().update(instance, validated_data)


class TeamNotificationChannelEndpointSerializer(NotificationChannelEndpointSerializer):
    """Specialized serializer for team-owned endpoints with config masking for non-admins."""

    def to_representation(self, instance):
        """Mask sensitive config for non-admin users."""
        data = super().to_representation(instance)

        # Check if user is team admin or org admin
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            team = Team.objects.filter(id=instance.owner_id).first()

            if team:
                # Check if user is admin (either team admin or org admin)
                is_admin = (
                    user.is_team_admin(team) if hasattr(user, 'is_team_admin') else False
                ) or (
                    user.is_org_admin() if hasattr(user, 'is_org_admin') else False
                )

                # Mask config for non-admins
                if not is_admin:
                    data['config'] = self._mask_config(instance.channel_type, instance.config)

        return data

    def _mask_config(self, channel_type, config):
        """Mask sensitive configuration values for non-admin users."""
        masked_config = config.copy()

        if channel_type == 'email':
            address = config.get('address', '')
            if '@' in address:
                username, domain = address.split('@', 1)
                masked_config['address'] = f"{username[:2]}***@{domain}"

        elif channel_type == 'telegram':
            if 'chat_id' in masked_config:
                masked_config['chat_id'] = '***'

        elif channel_type == 'slack':
            webhook = config.get('webhook_url', '')
            if webhook:
                masked_config['webhook_url'] = 'https://*****.slack.com/***'

        elif channel_type == 'webhook':
            url = config.get('url', '')
            if url:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                masked_config['url'] = f"{parsed.scheme}://*****.{parsed.netloc.split('.')[-1]}/***"

        elif channel_type == 'sms':
            phone = config.get('phone_number', '')
            if phone:
                masked_config['phone_number'] = f"***{phone[-4:]}"

        return masked_config


class TeamMemberNotificationOverrideSerializer(serializers.ModelSerializer):
    """Serializer for TeamMemberNotificationOverride model."""

    team_name = serializers.CharField(source='team.name', read_only=True)
    member_email = serializers.EmailField(source='member.email', read_only=True)

    class Meta:
        model = TeamMemberNotificationOverride
        fields = [
            'id', 'team', 'team_name', 'member', 'member_email',
            'team_notifications_enabled', 'disabled_endpoints',
            'disabled_priorities', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_disabled_priorities(self, value):
        """Validate priority levels."""
        valid_priorities = ['critical', 'high', 'normal', 'low']

        if not isinstance(value, list):
            raise serializers.ValidationError("Disabled priorities must be a list")

        for priority in value:
            if priority not in valid_priorities:
                raise serializers.ValidationError(
                    f"Invalid priority '{priority}'. Must be one of: {', '.join(valid_priorities)}"
                )

        return value

    def validate_disabled_endpoints(self, value):
        """Validate that all endpoint UUIDs exist and belong to the team."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Disabled endpoints must be a list")

        team_id = self.initial_data.get('team')
        if team_id:
            # Verify all endpoints exist and belong to the team
            endpoint_count = NotificationChannelEndpoint.objects.filter(
                id__in=value,
                owner_type='team',
                owner_id=team_id
            ).count()

            if endpoint_count != len(value):
                raise serializers.ValidationError(
                    "One or more endpoint UUIDs are invalid or don't belong to this team"
                )

        return value


class NotificationChannelVerificationSerializer(serializers.ModelSerializer):
    """Serializer for NotificationChannelVerification model."""

    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_channel_type = serializers.CharField(source='endpoint.channel_type', read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = NotificationChannelVerification
        fields = [
            'id', 'endpoint', 'endpoint_label', 'endpoint_channel_type',
            'verification_code', 'verification_type', 'expires_at',
            'verified_at', 'is_expired', 'attempts', 'created_at'
        ]
        read_only_fields = [
            'id', 'verification_code', 'verified_at', 'is_expired',
            'attempts', 'created_at'
        ]

    def get_is_expired(self, obj):
        """Check if verification code is expired."""
        return obj.is_expired()


class VerificationCodeRequestSerializer(serializers.Serializer):
    """Serializer for verification code generation requests."""

    endpoint_id = serializers.UUIDField()

    def validate_endpoint_id(self, value):
        """Validate that endpoint exists and belongs to the user."""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("Authentication required")

        try:
            endpoint = NotificationChannelEndpoint.objects.get(id=value)

            # Verify ownership
            if endpoint.owner_type == 'user' and str(endpoint.owner_id) != str(request.user.id):
                raise serializers.ValidationError("You don't have permission to verify this endpoint")

            elif endpoint.owner_type == 'team':
                team = Team.objects.get(id=endpoint.owner_id)
                # Check if user is team admin
                is_admin = (
                    request.user.is_team_admin(team) if hasattr(request.user, 'is_team_admin') else False
                ) or (
                    request.user.is_org_admin() if hasattr(request.user, 'is_org_admin') else False
                )

                if not is_admin:
                    raise serializers.ValidationError("Only team admins can verify team endpoints")

        except NotificationChannelEndpoint.DoesNotExist:
            raise serializers.ValidationError("Endpoint not found")

        return value


class VerificationCodeSubmitSerializer(serializers.Serializer):
    """Serializer for verification code submission."""

    endpoint_id = serializers.UUIDField()
    verification_code = serializers.CharField(min_length=6, max_length=6)

    def validate_verification_code(self, value):
        """Validate code format."""
        if not value.isdigit():
            raise serializers.ValidationError("Verification code must be 6 digits")
        return value