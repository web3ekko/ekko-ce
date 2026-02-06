"""
Notification models for Ekko platform notification system.

This module defines Django models for managing user and group notification settings,
along with delivery tracking and cache management.

ARCHITECTURE NOTE:
Django's role in notification system is METADATA-ONLY:
- Manages notification settings via REST API
- Caches settings in Redis for wasmCloud access
- NO direct NATS messaging - wasmCloud handles all message flow
- wasmCloud components read settings from Redis cache (via capability providers)
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from django.contrib.auth import get_user_model
from django.db import models
from django.core.cache import cache
from django.utils import timezone
from django.core.validators import EmailValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from organizations.models import Team  # Import Team model from organizations

logger = logging.getLogger(__name__)
User = get_user_model()

# Import Alert model for ForeignKey reference
# This avoids the string reference issue with Django's app resolution
# Temporarily disabled due to import issues
# from .alerts import Alert


# ===================================================================
# Channel Preferences Model (Enable/Disable Toggles)
# ===================================================================

class NotificationChannelPreferences(models.Model):
    """
    User's enable/disable preferences per notification channel.

    Separated from credentials (NotificationChannelEndpoint) for channels like Push
    where user just toggles on/off (device tokens handled in UserDevice model).

    This model stores ONLY the preference toggles - actual credentials like webhook URLs,
    phone numbers, etc. are stored in NotificationChannelEndpoint.
    """

    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('telegram', 'Telegram'),
        ('discord', 'Discord'),
        ('webhook', 'Webhook'),
        ('websocket', 'WebSocket'),
        ('sms', 'SMS'),
        ('push', 'Push'),
        ('whatsapp', 'WhatsApp'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='channel_preferences'
    )
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        db_index=True,
        help_text="Notification channel type"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether notifications are enabled for this channel"
    )

    # Priority-based filtering (optional)
    priority_filter = models.JSONField(
        default=list,
        blank=True,
        help_text="Priority levels to receive on this channel (e.g., ['critical', 'high']). Empty = all priorities."
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_channel_preferences'
        verbose_name = 'Notification Channel Preference'
        verbose_name_plural = 'Notification Channel Preferences'
        unique_together = ['user', 'channel']
        indexes = [
            models.Index(fields=['user', 'enabled']),
            models.Index(fields=['channel', 'enabled']),
        ]

    def __str__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"{self.user.email} - {self.channel} ({status})"

    def save(self, *args, **kwargs):
        """Override save to warm Redis cache."""
        super().save(*args, **kwargs)
        self.warm_cache()

    def warm_cache(self):
        """Warm Redis cache with this preference for wasmCloud access."""
        cache_key = f"user:channel_preferences:{self.user_id}"
        # Get all preferences for this user and cache them
        all_prefs = NotificationChannelPreferences.objects.filter(
            user_id=self.user_id
        )

        # Build preferences list
        preferences = [pref.to_cache_format() for pref in all_prefs]

        # Also build channel lookup dict for fast access
        channel_lookup = {
            pref.channel: {
                'enabled': pref.enabled,
                'priority_filter': pref.priority_filter,
            }
            for pref in all_prefs
        }

        cache_data = {
            'user_id': str(self.user_id),
            'preferences': preferences,
            'channel_lookup': channel_lookup,
            'cached_at': timezone.now().isoformat(),
        }

        # Cache for 1 hour
        cache.set(cache_key, cache_data, timeout=3600)
        logger.info(f"Warmed channel preferences cache for user {self.user_id}")

    def to_cache_format(self) -> Dict[str, Any]:
        """Convert model to format suitable for Redis caching."""
        return {
            'id': str(self.id),
            'channel': self.channel,
            'enabled': self.enabled,
            'priority_filter': self.priority_filter,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_cached_preferences(cls, user_id) -> Dict[str, Any]:
        """Get user's channel preferences from Redis cache."""
        cache_key = f"user:channel_preferences:{user_id}"
        cached_data = cache.get(cache_key)

        if cached_data and 'user_id' in cached_data:
            logger.debug(f"Retrieved cached channel preferences for user {user_id}")
            return cached_data

        # Cache miss - fetch from database and cache
        prefs = cls.objects.filter(user_id=user_id)

        # Build preferences list
        preferences = [pref.to_cache_format() for pref in prefs]

        # Also build channel lookup dict for fast access
        channel_lookup = {
            pref.channel: {
                'enabled': pref.enabled,
                'priority_filter': pref.priority_filter,
            }
            for pref in prefs
        }

        cache_data = {
            'user_id': str(user_id),
            'preferences': preferences,
            'channel_lookup': channel_lookup,
            'cached_at': timezone.now().isoformat(),
        }

        cache.set(cache_key, cache_data, timeout=3600)
        logger.info(f"Cached channel preferences for user {user_id}")

        return cache_data

    @classmethod
    def is_channel_enabled(cls, user_id, channel: str) -> bool:
        """Check if a specific channel is enabled for a user.

        Returns True if:
        - Channel has a preference record with enabled=True
        - Channel has no preference record (default: enabled for all channels)

        Returns False only if channel has preference with enabled=False.
        """
        cached = cls.get_cached_preferences(user_id)
        channel_lookup = cached.get('channel_lookup', {})

        if not channel_lookup:
            # No preferences set - default to enabled
            return True

        channel_pref = channel_lookup.get(channel)
        if channel_pref is None:
            # Channel not configured - default to enabled
            return True

        return channel_pref.get('enabled', True)


# Signal handler for NotificationChannelPreferences deletion
@receiver(post_delete, sender=NotificationChannelPreferences)
def warm_channel_preferences_cache_on_delete(sender, instance, **kwargs):
    """
    Re-warm cache when a preference is deleted to ensure wasmCloud has accurate data.

    This ensures the Redis cache reflects the current state after deletion,
    preventing wasmCloud from reading stale preference data.
    """
    cache_key = f"user:channel_preferences:{instance.user_id}"

    # Get remaining preferences for this user
    remaining_prefs = NotificationChannelPreferences.objects.filter(
        user_id=instance.user_id
    )

    if remaining_prefs.exists():
        # Re-warm cache with remaining preferences
        preferences = [pref.to_cache_format() for pref in remaining_prefs]
        channel_lookup = {
            pref.channel: {
                'enabled': pref.enabled,
                'priority_filter': pref.priority_filter,
            }
            for pref in remaining_prefs
        }

        cache_data = {
            'user_id': str(instance.user_id),
            'preferences': preferences,
            'channel_lookup': channel_lookup,
            'cached_at': timezone.now().isoformat(),
        }
        cache.set(cache_key, cache_data, timeout=3600)
        logger.info(f"Re-warmed channel preferences cache for user {instance.user_id} (preference deleted)")
    else:
        # No preferences left - delete cache entry
        cache.delete(cache_key)
        logger.info(f"Deleted channel preferences cache for user {instance.user_id} (last preference deleted)")


class UserNotificationSettings(models.Model):
    """User-specific notification preferences and channel configurations."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_settings'
    )

    # Global notification toggles
    websocket_enabled = models.BooleanField(
        default=True,
        help_text="Enable WebSocket real-time notifications (default enabled per PRD)"
    )
    notifications_enabled = models.BooleanField(
        default=True,
        help_text="Master toggle for all notifications"
    )

    # Channel configurations stored as JSON
    channels = models.JSONField(
        default=dict,
        help_text="Channel-specific settings (email, slack, sms, etc.)"
    )

    # Priority-based routing
    priority_routing = models.JSONField(
        default=dict,
        help_text="Mapping of priority levels to preferred notification channels"
    )

    # Quiet hours configuration
    quiet_hours = models.JSONField(
        null=True, blank=True,
        help_text="Quiet hours configuration with timezone and priority overrides"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_notification_settings'
        verbose_name = 'User Notification Settings'
        verbose_name_plural = 'User Notification Settings'

    def __str__(self):
        return f"Notification settings for {self.user.username}"

    def clean(self):
        """Validate notification settings data."""
        super().clean()

        # Validate channel configurations
        if self.channels:
            self._validate_channels()

        # Validate quiet hours if present
        if self.quiet_hours:
            self._validate_quiet_hours()

    def _validate_channels(self):
        """Validate channel configuration format."""
        valid_channels = ['email', 'slack', 'sms', 'telegram', 'discord', 'webhook', 'websocket']

        for channel_name, settings in self.channels.items():
            if channel_name not in valid_channels:
                raise ValidationError(f"Invalid channel: {channel_name}")

            if not isinstance(settings, dict):
                raise ValidationError(f"Channel settings must be a dictionary for {channel_name}")

            # Validate required settings per channel
            if settings.get('enabled', False):
                self._validate_channel_config(channel_name, settings.get('config', {}))

    def _validate_channel_config(self, channel: str, config: Dict[str, Any]):
        """Validate channel-specific configuration."""
        if channel == 'email':
            if 'address' not in config:
                raise ValidationError("Email channel requires 'address' in config")
            EmailValidator()(config['address'])

        elif channel == 'sms':
            if 'phone' not in config:
                raise ValidationError("SMS channel requires 'phone' in config")
            phone = config['phone']
            # Basic phone validation
            if not phone.replace('+', '').replace('-', '').replace(' ', '').isdigit():
                raise ValidationError("Invalid phone number format")

        elif channel == 'slack':
            if 'channel' not in config:
                raise ValidationError("Slack channel requires 'channel' in config")

        elif channel in ['webhook', 'discord']:
            if 'webhook_url' in config or 'url' in config:
                url = config.get('webhook_url') or config.get('url')
                if not url.startswith(('http://', 'https://')):
                    raise ValidationError(f"Invalid URL format for {channel}")

    def _validate_quiet_hours(self):
        """Validate quiet hours configuration."""
        required_fields = ['start_time', 'end_time', 'timezone', 'enabled']
        for field in required_fields:
            if field not in self.quiet_hours:
                raise ValidationError(f"Quiet hours missing required field: {field}")

        # Validate time format (HH:MM)
        time_regex = RegexValidator(
            regex=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
            message='Time must be in HH:MM format'
        )
        time_regex(self.quiet_hours['start_time'])
        time_regex(self.quiet_hours['end_time'])

    def get_channel_config(self, channel: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific channel."""
        return self.channels.get(channel)

    def is_channel_enabled(self, channel: str) -> bool:
        """Check if a specific channel is enabled."""
        if not self.notifications_enabled:
            return False

        # WebSocket is enabled by default per PRD
        if channel == 'websocket':
            return self.websocket_enabled

        channel_config = self.get_channel_config(channel)
        if not channel_config:
            return False

        return channel_config.get('enabled', False)

    def get_priority_channels(self, priority: str) -> List[str]:
        """Get preferred channels for a given priority level."""
        if not self.priority_routing:
            # Default routing
            if priority == 'critical':
                return ['websocket', 'email', 'sms']
            elif priority == 'high':
                return ['websocket', 'email']
            else:
                return ['websocket']

        return self.priority_routing.get(priority, ['websocket'])

    def is_in_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        if not self.quiet_hours or not self.quiet_hours.get('enabled'):
            return False

        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo  # For Python < 3.9

        try:
            tz = ZoneInfo(self.quiet_hours['timezone'])
            now = datetime.now(tz)

            start_time = datetime.strptime(self.quiet_hours['start_time'], '%H:%M').time()
            end_time = datetime.strptime(self.quiet_hours['end_time'], '%H:%M').time()
            current_time = now.time()

            if start_time <= end_time:
                # Same day (e.g., 09:00 to 17:00)
                return start_time <= current_time <= end_time
            else:
                # Crosses midnight (e.g., 22:00 to 08:00)
                return current_time >= start_time or current_time <= end_time
        except Exception as e:
            logger.warning(f"Error checking quiet hours for user {self.user.id}: {e}")
            return False

    def can_receive_priority_in_quiet_hours(self, priority: str) -> bool:
        """Check if a priority level overrides quiet hours."""
        if not self.quiet_hours:
            return True

        priority_overrides = self.quiet_hours.get('priority_override', [])
        return priority in priority_overrides

    def save(self, *args, **kwargs):
        """Override save to invalidate Redis cache."""
        super().save(*args, **kwargs)
        self.invalidate_cache()

    def invalidate_cache(self):
        """Invalidate Redis cache for this user's settings."""
        cache_key = f"user:notifications:{self.user.id}"
        cache.delete(cache_key)
        logger.info(f"Invalidated notification cache for user {self.user.id}")

    def to_cache_format(self) -> Dict[str, Any]:
        """Convert model to format suitable for Redis caching."""
        return {
            'user_id': str(self.user.id),
            'websocket_enabled': self.websocket_enabled,
            'notifications_enabled': self.notifications_enabled,
            'channels': self.channels,
            'priority_routing': self.priority_routing,
            'quiet_hours': self.quiet_hours,
            'cached_at': timezone.now().isoformat(),
        }

    @classmethod
    def get_cached_settings(cls, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user settings from Redis cache."""
        cache_key = f"user:notifications:{user_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug(f"Retrieved cached notification settings for user {user_id}")
            return cached_data

        # Cache miss - fetch from database and cache
        try:
            settings = cls.objects.select_related('user').get(user_id=user_id)
            cache_data = settings.to_cache_format()

            # Cache for 1 hour as per PRD
            cache.set(cache_key, cache_data, timeout=3600)
            logger.info(f"Cached notification settings for user {user_id}")

            return cache_data
        except cls.DoesNotExist:
            # Create default settings
            user = User.objects.get(id=user_id)
            settings = cls.create_default_settings(user)
            return settings.to_cache_format()

    @classmethod
    def create_default_settings(cls, user: User) -> 'UserNotificationSettings':
        """Create default notification settings for a user."""
        default_channels = {
            'websocket': {
                'enabled': True,
                'config': {}
            }
        }

        default_priority_routing = {
            'critical': ['websocket'],
            'high': ['websocket'],
            'normal': ['websocket'],
            'low': ['websocket']
        }

        settings = cls.objects.create(
            user=user,
            websocket_enabled=True,  # Default enabled per PRD
            notifications_enabled=True,
            channels=default_channels,
            priority_routing=default_priority_routing
        )

        logger.info(f"Created default notification settings for user {user.id}")
        return settings


class GroupNotificationSettings(models.Model):
    """Group/team-level notification preferences."""

    group = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='notification_settings'
    )

    # Mandatory channels that all group members must receive
    mandatory_channels = models.JSONField(
        default=list,
        help_text="Channels that all group members must receive notifications on"
    )

    # Escalation rules for different scenarios
    escalation_rules = models.JSONField(
        default=dict,
        help_text="Escalation paths and timing for different priority levels"
    )

    # Shared channels (e.g., team Slack channel)
    shared_channels = models.JSONField(
        default=dict,
        help_text="Shared notification channels for the entire group"
    )

    # Whether members can override group settings
    member_overrides_allowed = models.BooleanField(
        default=True,
        help_text="Allow group members to override certain settings"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'group_notification_settings'
        verbose_name = 'Group Notification Settings'
        verbose_name_plural = 'Group Notification Settings'

    def __str__(self):
        return f"Notification settings for {self.group.name}"

    def save(self, *args, **kwargs):
        """Override save to invalidate Redis cache."""
        super().save(*args, **kwargs)
        self.invalidate_cache()

    def invalidate_cache(self):
        """Invalidate Redis cache for this group's settings."""
        cache_key = f"group:notifications:{self.group.id}"
        cache.delete(cache_key)
        logger.info(f"Invalidated notification cache for group {self.group.id}")

    def to_cache_format(self) -> Dict[str, Any]:
        """Convert model to format suitable for Redis caching."""
        return {
            'group_id': str(self.group.id),
            'group_name': self.group.name,
            'mandatory_channels': self.mandatory_channels,
            'escalation_rules': self.escalation_rules,
            'shared_channels': self.shared_channels,
            'member_overrides_allowed': self.member_overrides_allowed,
            'cached_at': timezone.now().isoformat(),
        }

    @classmethod
    def get_cached_settings(cls, group_id: int) -> Optional[Dict[str, Any]]:
        """Get group settings from Redis cache."""
        cache_key = f"group:notifications:{group_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug(f"Retrieved cached notification settings for group {group_id}")
            return cached_data

        # Cache miss - fetch from database and cache
        try:
            settings = cls.objects.select_related('group').get(group_id=group_id)
            cache_data = settings.to_cache_format()

            # Cache for 1 hour as per PRD
            cache.set(cache_key, cache_data, timeout=3600)
            logger.info(f"Cached notification settings for group {group_id}")

            return cache_data
        except cls.DoesNotExist:
            return None


class NotificationDelivery(models.Model):
    """Track notification delivery status and history."""

    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('channel_disabled', 'Channel Disabled'),
        ('quiet_hours', 'Quiet Hours'),
        ('rate_limited', 'Rate Limited'),
    ]

    # Notification tracking
    notification_id = models.UUIDField(
        help_text="Unique identifier for the notification request"
    )

    # Related objects
    # Using lazy ForeignKey reference to avoid circular import
    alert = models.ForeignKey(
        'app.AlertInstance',
        on_delete=models.CASCADE,
        related_name='notification_deliveries'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notification_deliveries'
    )

    # Delivery details
    channel = models.CharField(
        max_length=50,
        help_text="Notification channel (email, slack, sms, etc.)"
    )
    status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='pending'
    )

    # External provider details
    external_message_id = models.CharField(
        max_length=255,
        null=True, blank=True,
        help_text="Message ID from external provider (SendGrid, Twilio, etc.)"
    )
    provider_response = models.JSONField(
        null=True, blank=True,
        help_text="Full response from external provider"
    )

    # Error tracking
    error_code = models.CharField(
        max_length=100,
        null=True, blank=True
    )
    error_message = models.TextField(
        null=True, blank=True
    )
    retry_count = models.PositiveIntegerField(default=0)

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    retry_after = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notification_deliveries'
        verbose_name = 'Notification Delivery'
        verbose_name_plural = 'Notification Deliveries'
        indexes = [
            models.Index(fields=['notification_id']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['alert', 'status']),
            models.Index(fields=['channel', 'status']),
        ]

    def __str__(self):
        return f"Delivery {self.notification_id} to {self.user.username} via {self.channel}"

    def mark_delivered(self, external_id: str = None, provider_response: Dict = None):
        """Mark notification as successfully delivered."""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        if external_id:
            self.external_message_id = external_id
        if provider_response:
            self.provider_response = provider_response
        self.save()

    def mark_failed(self, error_code: str = None, error_message: str = None, retryable: bool = True):
        """Mark notification as failed."""
        self.status = 'failed'
        self.error_code = error_code
        self.error_message = error_message

        if retryable:
            self.retry_count += 1
            # Exponential backoff: 1min, 5min, 15min
            delay_minutes = min(60, 1 * (3 ** self.retry_count))
            self.retry_after = timezone.now() + timedelta(minutes=delay_minutes)

        self.save()


class NotificationTemplate(models.Model):
    """Notification message templates for different channels and alert types."""

    TEMPLATE_TYPES = [
        ('balance_alert', 'Balance Alert'),
        ('transaction_alert', 'Transaction Alert'),
        ('price_alert', 'Price Alert'),
        ('security_alert', 'Security Alert'),
        ('system_alert', 'System Alert'),
    ]

    CHANNELS = [
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('sms', 'SMS'),
        ('telegram', 'Telegram'),
        ('discord', 'Discord'),
        ('webhook', 'Webhook'),
        ('websocket', 'WebSocket'),
    ]

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique template identifier"
    )

    template_type = models.CharField(
        max_length=50,
        choices=TEMPLATE_TYPES
    )

    channel = models.CharField(
        max_length=20,
        choices=CHANNELS
    )

    # Template content
    subject_template = models.CharField(
        max_length=200,
        help_text="Subject line template (email/notifications)"
    )

    text_template = models.TextField(
        help_text="Plain text template"
    )

    html_template = models.TextField(
        null=True, blank=True,
        help_text="HTML template for rich content channels"
    )

    structured_template = models.JSONField(
        null=True, blank=True,
        help_text="Structured template for channels like Slack blocks"
    )

    # Template variables and validation
    required_variables = models.JSONField(
        default=list,
        help_text="List of required template variables"
    )

    # Settings
    active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_templates'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        unique_together = ['template_type', 'channel']

    def __str__(self):
        return f"{self.name} ({self.channel})"

    def render(self, variables: Dict[str, Any]) -> Dict[str, str]:
        """Render template with provided variables."""
        from django.template import Template, Context

        # Validate required variables
        missing_vars = [var for var in self.required_variables if var not in variables]
        if missing_vars:
            raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")

        context = Context(variables)

        result = {
            'subject': Template(self.subject_template).render(context),
            'text_content': Template(self.text_template).render(context),
        }

        if self.html_template:
            result['html_content'] = Template(self.html_template).render(context)

        if self.structured_template:
            # For structured templates (like Slack blocks), we need to process JSON
            import json
            structured_str = json.dumps(self.structured_template)
            rendered_structured = Template(structured_str).render(context)
            result['structured_content'] = json.loads(rendered_structured)

        return result


# ===================================================================
# Multi-Address Notification Endpoint Models
# ===================================================================

class NotificationChannelEndpoint(models.Model):
    """
    Individual notification endpoint supporting multi-address configuration.

    Supports polymorphic ownership (user or team-owned) and allows unlimited
    notification addresses per channel type with individual enable/disable control.

    PRD Reference: /docs/prd/notifications/PRD-Multi-Address-Notification-System-USDT.md
    """

    OWNER_TYPE_CHOICES = [
        ('user', 'User'),
        ('team', 'Team'),
    ]

    CHANNEL_TYPE_CHOICES = [
        ('email', 'Email'),
        ('telegram', 'Telegram'),
        ('slack', 'Slack'),
        ('webhook', 'Webhook'),
        ('sms', 'SMS'),
        ('discord', 'Discord'),
        ('whatsapp', 'WhatsApp'),
        # Note: 'push' is NOT here - push device tokens are stored in UserDevice model
    ]

    ROUTING_MODE_CHOICES = [
        ('all_enabled', 'All Enabled'),
        ('priority_based', 'Priority Based'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Polymorphic ownership
    owner_type = models.CharField(
        max_length=10,
        choices=OWNER_TYPE_CHOICES,
        db_index=True,
        help_text="Owner type: 'user' or 'team'"
    )
    owner_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the owning user or team"
    )

    # Channel configuration
    channel_type = models.CharField(
        max_length=20,
        choices=CHANNEL_TYPE_CHOICES,
        db_index=True,
        help_text="Notification channel type"
    )

    label = models.CharField(
        max_length=100,
        help_text="User-friendly label (e.g., 'Work Email', 'Trading Telegram')"
    )

    config = models.JSONField(
        help_text="Channel-specific configuration (address, webhook_url, chat_id, etc.)"
    )
    # Config examples:
    # email: {"address": "user@example.com"}
    # telegram: {"chat_id": "123456789", "username": "@user"}
    # slack: {"webhook_url": "https://hooks.slack.com/...", "channel": "#alerts"}
    # webhook: {"url": "https://api.example.com/webhook", "headers": {...}}
    # sms: {"phone_number": "+1234567890"}

    # Endpoint controls
    enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this endpoint is currently enabled"
    )
    verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this endpoint has been verified"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last verification"
    )

    # Priority routing (hybrid approach)
    routing_mode = models.CharField(
        max_length=20,
        choices=ROUTING_MODE_CHOICES,
        default='all_enabled',
        help_text="Routing mode: 'all_enabled' or 'priority_based'"
    )
    priority_filters = models.JSONField(
        default=list,
        blank=True,
        help_text="Priority levels to receive in priority_based mode (e.g., ['critical', 'high'])"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_notification_endpoints',
        help_text="User who created this endpoint"
    )

    class Meta:
        db_table = 'notification_channel_endpoints'
        verbose_name = 'Notification Channel Endpoint'
        verbose_name_plural = 'Notification Channel Endpoints'
        indexes = [
            models.Index(fields=['owner_type', 'owner_id', 'enabled']),
            models.Index(fields=['channel_type', 'enabled', 'verified']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['owner_type', 'owner_id', 'channel_type', 'label'],
                name='unique_endpoint_label_per_owner_channel'
            )
        ]

    def __str__(self):
        return f"{self.owner_type}:{self.owner_id} - {self.channel_type} ({self.label})"

    @property
    def requires_reverification(self):
        """Security-sensitive channels require re-verification on re-enable."""
        return self.channel_type in ['email', 'telegram', 'sms']

    def get_owner(self):
        """Get the actual owner object (User or Team)."""
        if self.owner_type == 'user':
            return User.objects.get(id=self.owner_id)
        else:
            return Team.objects.get(id=self.owner_id)

    def clean(self):
        """Validate endpoint configuration."""
        super().clean()

        # Validate config based on channel type
        if self.channel_type == 'email':
            if 'address' not in self.config:
                raise ValidationError("Email channel requires 'address' in config")
            try:
                EmailValidator()(self.config['address'])
            except ValidationError:
                raise ValidationError(f"Invalid email address: {self.config['address']}")

        elif self.channel_type == 'sms':
            if 'phone_number' not in self.config:
                raise ValidationError("SMS channel requires 'phone_number' in config")

        elif self.channel_type == 'telegram':
            if 'chat_id' not in self.config:
                raise ValidationError("Telegram channel requires 'chat_id' in config")

        elif self.channel_type == 'slack':
            if 'webhook_url' not in self.config:
                raise ValidationError("Slack channel requires 'webhook_url' in config")

        elif self.channel_type == 'webhook':
            if 'url' not in self.config:
                raise ValidationError("Webhook channel requires 'url' in config")

        elif self.channel_type == 'discord':
            if 'webhook_url' not in self.config:
                raise ValidationError("Discord channel requires 'webhook_url' in config")
            webhook_url = self.config['webhook_url']
            if not webhook_url.startswith('https://discord.com/api/webhooks/'):
                raise ValidationError("Discord webhook URL must start with 'https://discord.com/api/webhooks/'")

        elif self.channel_type == 'whatsapp':
            if 'phone_number' not in self.config:
                raise ValidationError("WhatsApp channel requires 'phone_number' in config")

    def save(self, *args, **kwargs):
        """Override save to warm Redis cache for wasmCloud access."""
        super().save(*args, **kwargs)
        self.warm_cache()

    def warm_cache(self):
        """Warm Redis cache with all endpoints for this owner (for wasmCloud access)."""
        cache_key = f"notification:endpoints:{self.owner_type}:{self.owner_id}"

        # Get all endpoints for this owner and cache them
        all_endpoints = NotificationChannelEndpoint.objects.filter(
            owner_type=self.owner_type,
            owner_id=self.owner_id,
            enabled=True,
        )

        cache_data = {
            'owner_type': self.owner_type,
            'owner_id': str(self.owner_id),
            'endpoints': [ep.to_cache_format() for ep in all_endpoints],
            'cached_at': timezone.now().isoformat(),
        }

        # Cache for 1 hour
        cache.set(cache_key, cache_data, timeout=3600)
        logger.info(f"Warmed notification endpoint cache for {self.owner_type}:{self.owner_id}")

    def invalidate_cache(self):
        """Invalidate Redis cache for this endpoint's owner (legacy method)."""
        # Now just calls warm_cache to ensure data is available
        self.warm_cache()

    def to_cache_format(self) -> Dict[str, Any]:
        """Convert model to format suitable for Redis caching (for wasmCloud access)."""
        return {
            'id': str(self.id),
            'channel_type': self.channel_type,
            'label': self.label,
            'config': self.config,
            'enabled': self.enabled,
            'verified': self.verified,
            'routing_mode': self.routing_mode,
            'priority_filters': self.priority_filters,
        }


class TeamMemberNotificationOverride(models.Model):
    """
    Allows team members to disable specific team notifications for themselves.

    Provides full opt-out control without affecting other team members.

    PRD Reference: /docs/prd/notifications/PRD-Multi-Address-Notification-System-USDT.md
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='member_notification_overrides',
        help_text="Team for which this override applies"
    )
    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_notification_overrides',
        help_text="Team member who created this override"
    )

    # Master switch for all team notifications
    team_notifications_enabled = models.BooleanField(
        default=True,
        help_text="Master switch - disables ALL team notifications if False"
    )

    # Endpoint-specific overrides
    disabled_endpoints = models.JSONField(
        default=list,
        help_text="List of NotificationChannelEndpoint UUIDs disabled for this member"
    )

    # Priority-level overrides
    disabled_priorities = models.JSONField(
        default=list,
        help_text="Priority levels disabled across ALL team endpoints (e.g., ['low', 'normal'])"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'team_member_notification_overrides'
        verbose_name = 'Team Member Notification Override'
        verbose_name_plural = 'Team Member Notification Overrides'
        unique_together = [('team', 'member')]
        indexes = [
            models.Index(fields=['team', 'member', 'team_notifications_enabled']),
        ]

    def __str__(self):
        return f"{self.member.email} overrides for team {self.team.name}"

    def save(self, *args, **kwargs):
        """Override save to invalidate Redis cache."""
        super().save(*args, **kwargs)
        self.invalidate_cache()

    def invalidate_cache(self):
        """Invalidate Redis cache for this member's team overrides."""
        cache_key = f"notification:overrides:team:{self.team.id}:member:{self.member.id}"
        cache.delete(cache_key)
        logger.info(f"Invalidated notification override cache for team {self.team.id}, member {self.member.id}")

    def to_cache_format(self) -> Dict[str, Any]:
        """Convert model to format suitable for Redis caching (for wasmCloud access)."""
        return {
            'team_id': str(self.team.id),
            'member_id': str(self.member.id),
            'team_notifications_enabled': self.team_notifications_enabled,
            'disabled_endpoints': [str(ep_id) for ep_id in self.disabled_endpoints],
            'disabled_priorities': self.disabled_priorities,
            'updated_at': self.updated_at.isoformat(),
        }


class NotificationChannelVerification(models.Model):
    """
    Manages verification codes for notification channels.

    Supports both initial verification and re-verification on re-enable.

    PRD Reference: /docs/prd/notifications/PRD-Multi-Address-Notification-System-USDT.md
    """

    VERIFICATION_TYPE_CHOICES = [
        ('initial', 'Initial Verification'),
        ('re_enable', 'Re-Enable Verification'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    endpoint = models.ForeignKey(
        NotificationChannelEndpoint,
        on_delete=models.CASCADE,
        related_name='verifications',
        help_text="Endpoint being verified"
    )

    verification_code = models.CharField(
        max_length=6,
        help_text="6-digit verification code"
    )
    verification_type = models.CharField(
        max_length=20,
        choices=VERIFICATION_TYPE_CHOICES,
        help_text="Type of verification: initial or re-enable"
    )

    # Expiration
    expires_at = models.DateTimeField(
        help_text="Expiration timestamp for verification code"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when verification was completed"
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(
        default=0,
        help_text="Number of verification attempts"
    )

    class Meta:
        db_table = 'notification_channel_verifications'
        verbose_name = 'Notification Channel Verification'
        verbose_name_plural = 'Notification Channel Verifications'
        indexes = [
            models.Index(fields=['endpoint', 'expires_at']),
        ]

    def __str__(self):
        return f"Verification for {self.endpoint.label} ({self.verification_type})"

    def is_expired(self):
        """Check if verification code has expired."""
        return timezone.now() > self.expires_at

    def increment_attempts(self):
        """Increment verification attempt counter."""
        self.attempts += 1
        self.save(update_fields=['attempts'])


# Cache management utilities
class NotificationCache:
    """Utility class for managing notification-related caching."""

    @staticmethod
    def warm_user_cache(user_ids: List[int]) -> int:
        """Pre-warm cache for multiple users."""
        cached_count = 0
        for user_id in user_ids:
            try:
                UserNotificationSettings.get_cached_settings(user_id)
                cached_count += 1
            except Exception as e:
                logger.warning(f"Failed to cache settings for user {user_id}: {e}")

        logger.info(f"Warmed notification cache for {cached_count}/{len(user_ids)} users")
        return cached_count

    @staticmethod
    def clear_all_user_caches():
        """Clear all user notification caches (for maintenance)."""
        # This would need Redis SCAN or pattern deletion
        # For now, we'll implement a simple approach
        logger.warning("Clearing all user notification caches - implement with Redis SCAN")

    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Get cache usage statistics."""
        # This would require Redis INFO and SCAN commands
        # Placeholder for now
        return {
            'cache_hits': 0,
            'cache_misses': 0,
            'cached_users': 0,
            'cached_groups': 0,
        }


# ===================================================================
# Django Signals for Redis Cache Invalidation
# ===================================================================

@receiver(post_delete, sender=UserNotificationSettings)
def invalidate_user_settings_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate user notification settings cache when settings are deleted.

    Note: The save() signal is not needed here because UserNotificationSettings.save()
    already calls invalidate_cache() internally.

    Args:
        sender: The model class (UserNotificationSettings)
        instance: The UserNotificationSettings instance being deleted
        **kwargs: Additional signal arguments
    """
    try:
        from app.services.notification_cache import NotificationCacheManager
        cache_manager = NotificationCacheManager()
        cache_manager.invalidate_user_cache(str(instance.user_id))
        logger.info(f"Invalidated notification settings cache for user {instance.user_id} (deleted)")
    except Exception as e:
        # Signal handlers should NOT raise exceptions that break model operations
        logger.error(f"Error invalidating notification settings cache for user {instance.user_id}: {e}")
