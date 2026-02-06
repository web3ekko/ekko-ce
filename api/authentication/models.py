"""
Authentication Models for Passwordless Authentication System

Implements the passwordless authentication flow:
Passkeys → Email Magic Links → Optional TOTP
"""

import logging
import uuid
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


class CustomUserManager(UserManager):
    """Custom user manager for passwordless authentication"""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a user with the given email"""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        # Set username to email to avoid unique constraint issues
        extra_fields.setdefault('username', email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()  # Passwordless authentication
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_email_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model for passwordless authentication

    Uses email as the primary identifier, no passwords required
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name='Email Address')
    first_name = models.CharField(max_length=150, verbose_name='First Name')
    last_name = models.CharField(max_length=150, verbose_name='Last Name')

    # Authentication preferences
    preferred_auth_method = models.CharField(
        max_length=20,
        choices=[
            ('passkey', 'Passkey'),
            ('email', 'Email Magic Link'),
        ],
        default='passkey',
        verbose_name='Preferred Authentication Method'
    )

    # Firebase integration
    firebase_uid = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        unique=True,
        help_text='Firebase user ID for cross-platform authentication'
    )

    # Account status
    is_email_verified = models.BooleanField(default=False, verbose_name='Email Verified')
    has_passkey = models.BooleanField(default=False, verbose_name='Has Passkey')
    has_2fa = models.BooleanField(default=False, verbose_name='Has 2FA Enabled')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_method = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Last Login Method'
    )

    # Use email as username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    # Use custom manager
    objects = CustomUserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def has_passkey_via_allauth(self):
        """Check if user has any registered passkeys via Django Allauth"""
        try:
            from allauth.mfa.models import Authenticator
            return Authenticator.objects.filter(
                user=self,
                type=Authenticator.Type.WEBAUTHN
            ).exists()
        except ImportError:
            return False

    def update_passkey_status(self):
        """Update has_passkey field based on Allauth Authenticator records"""
        self.has_passkey = self.has_passkey_via_allauth
        self.save(update_fields=['has_passkey'])


class UserDevice(models.Model):
    """
    Track user devices for cross-device authentication and trust management
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')

    # Device information
    device_name = models.CharField(max_length=255, verbose_name='Device Name')
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('ios', 'iOS'),
            ('android', 'Android'),
            ('web', 'Web Browser'),
            ('desktop', 'Desktop'),
        ],
        verbose_name='Device Type'
    )
    device_id = models.CharField(max_length=255, unique=True, verbose_name='Device ID')
    device_fingerprint = models.TextField(blank=True, verbose_name='Device Fingerprint')

    # Authentication capabilities
    supports_passkey = models.BooleanField(default=False, verbose_name='Supports Passkey')
    supports_biometric = models.BooleanField(default=False, verbose_name='Supports Biometric')

    # Trust and status
    is_trusted = models.BooleanField(default=False, verbose_name='Is Trusted')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    trust_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Trust Expires At')

    # Usage tracking
    last_used = models.DateTimeField(auto_now=True, verbose_name='Last Used')
    created_at = models.DateTimeField(auto_now_add=True)

    # Push notification token fields
    device_token = models.CharField(
        max_length=512,
        blank=True,
        null=True,
        verbose_name='Push Token',
        help_text="FCM/APNs device token for push notifications"
    )
    token_type = models.CharField(
        max_length=10,
        choices=[
            ('fcm', 'FCM'),
            ('apns', 'APNs'),
        ],
        blank=True,
        null=True,
        verbose_name='Token Type',
        help_text="Push notification provider type"
    )
    token_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Token Updated At',
        help_text="Timestamp when device token was last updated"
    )
    token_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        verbose_name='Token Hash',
        help_text="SHA256 hash of device token for DuckLake storage (PII protection)"
    )
    push_enabled = models.BooleanField(
        default=True,
        verbose_name='Push Enabled',
        help_text="User can disable push notifications for this specific device"
    )

    class Meta:
        verbose_name = 'User Device'
        verbose_name_plural = 'User Devices'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_id']),
            models.Index(fields=['last_used']),
            models.Index(fields=['user', 'push_enabled']),
        ]

    def __str__(self):
        return f"{self.device_name} ({self.user.email})"

    @property
    def is_trust_expired(self):
        if not self.trust_expires_at:
            return False
        return timezone.now() > self.trust_expires_at

    def register_push_token(self, token: str, token_type: str = 'fcm') -> None:
        """
        Register or update push notification token for this device.

        Args:
            token: FCM or APNs device token
            token_type: 'fcm' or 'apns'
        """
        import hashlib
        from django.core.cache import cache

        self.device_token = token
        self.token_type = token_type
        self.token_updated_at = timezone.now()
        self.token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.push_enabled = True
        self.save(update_fields=[
            'device_token', 'token_type', 'token_updated_at',
            'token_hash', 'push_enabled'
        ])

        # Warm Redis cache for wasmCloud
        self._warm_push_cache()

    def revoke_push_token(self) -> None:
        """Revoke push notification token for this device."""
        from django.core.cache import cache

        self.device_token = None
        self.token_type = None
        self.token_hash = None
        self.push_enabled = False
        self.save(update_fields=[
            'device_token', 'token_type', 'token_hash', 'push_enabled'
        ])

        # Update Redis cache
        self._warm_push_cache()

    def set_push_enabled(self, enabled: bool) -> None:
        """Enable or disable push notifications for this device."""
        from django.core.cache import cache

        self.push_enabled = enabled
        self.save(update_fields=['push_enabled'])

        # Update Redis cache
        self._warm_push_cache()

    def _warm_push_cache(self) -> None:
        """Warm Redis cache with all push-enabled devices for this user."""
        from django.core.cache import cache

        cache_key = f"user:push_devices:{self.user_id}"

        # Get all push-enabled devices for this user
        push_devices = UserDevice.objects.filter(
            user_id=self.user_id,
            is_active=True,
            push_enabled=True,
            device_token__isnull=False,
        ).values(
            'id', 'device_name', 'device_type', 'device_token',
            'token_type', 'token_hash', 'token_updated_at'
        )

        cache_data = {
            'user_id': str(self.user_id),
            'devices': [
                {
                    'id': str(d['id']),
                    'device_name': d['device_name'],
                    'device_type': d['device_type'],
                    'device_token': d['device_token'],
                    'token_type': d['token_type'],
                    'token_hash': d['token_hash'],
                    'token_updated_at': d['token_updated_at'].isoformat() if d['token_updated_at'] else None,
                }
                for d in push_devices
            ],
            'cached_at': timezone.now().isoformat(),
        }

        # Cache for 1 hour
        cache.set(cache_key, cache_data, timeout=3600)

    @classmethod
    def get_push_devices_cached(cls, user_id) -> dict:
        """Get cached push-enabled devices for a user (for wasmCloud)."""
        from django.core.cache import cache

        cache_key = f"user:push_devices:{user_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        # Cache miss - fetch and cache
        push_devices = cls.objects.filter(
            user_id=user_id,
            is_active=True,
            push_enabled=True,
            device_token__isnull=False,
        ).values(
            'id', 'device_name', 'device_type', 'device_token',
            'token_type', 'token_hash', 'token_updated_at'
        )

        cache_data = {
            'user_id': str(user_id),
            'devices': [
                {
                    'id': str(d['id']),
                    'device_name': d['device_name'],
                    'device_type': d['device_type'],
                    'device_token': d['device_token'],
                    'token_type': d['token_type'],
                    'token_hash': d['token_hash'],
                    'token_updated_at': d['token_updated_at'].isoformat() if d['token_updated_at'] else None,
                }
                for d in push_devices
            ],
            'cached_at': timezone.now().isoformat(),
        }

        cache.set(cache_key, cache_data, timeout=3600)
        return cache_data






class AuthenticationLog(models.Model):
    """
    Audit trail for authentication events
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_logs', null=True, blank=True)

    # Authentication details
    method = models.CharField(
        max_length=20,
        choices=[
            ('passkey', 'Passkey'),
            ('email_magic_link', 'Email Magic Link'),
            ('email_code', 'Email Code'),
            ('totp', 'TOTP'),
            ('recovery_code', 'Recovery Code'),
            ('cross_device', 'Cross-Device'),
        ],
        verbose_name='Authentication Method'
    )
    success = models.BooleanField(verbose_name='Success')
    failure_reason = models.CharField(max_length=255, blank=True, verbose_name='Failure Reason')

    # Request details
    ip_address = models.GenericIPAddressField(verbose_name='IP Address')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    device_info = models.JSONField(default=dict, verbose_name='Device Info')

    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Authentication Log'
        verbose_name_plural = 'Authentication Logs'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['method', 'success']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]

    def __str__(self):
        status = "Success" if self.success else "Failed"
        user_email = self.user.email if self.user else "Unknown"
        return f"{status} {self.method} for {user_email} at {self.timestamp}"






class EmailVerificationCode(models.Model):
    """
    Manage 6-digit verification codes for email authentication
    
    Replaces magic links with codes that users enter in the app
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='verification_codes')
    email = models.EmailField(verbose_name='Email Address')
    code = models.CharField(max_length=6, verbose_name='Verification Code')
    
    # Code details
    purpose = models.CharField(
        max_length=20,
        choices=[
            ('signup', 'Signup'),
            ('signin', 'Sign In'),
            ('recovery', 'Account Recovery'),
        ],
        verbose_name='Purpose'
    )
    
    # Security
    ip_address = models.GenericIPAddressField(verbose_name='Requesting IP Address')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    
    # Status
    used_at = models.DateTimeField(null=True, blank=True, verbose_name='Used At')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name='Expires At')
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name='Verification Attempts')
    
    class Meta:
        verbose_name = 'Email Verification Code'
        verbose_name_plural = 'Email Verification Codes'
        indexes = [
            models.Index(fields=['email', 'purpose', 'created_at']),
            models.Index(fields=['code', 'email']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['user', 'purpose']),
        ]
    
    def __str__(self):
        return f"Code for {self.email} ({self.purpose})"
    
    @property
    def is_used(self):
        return self.used_at is not None
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired
    
    def mark_as_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])


# =============================================================================
# Signal Handlers for Redis Cache Management
# =============================================================================

@receiver(post_delete, sender=UserDevice)
def warm_push_cache_on_device_delete(sender, instance, **kwargs):
    """
    Re-warm push device cache when a device is deleted.

    This ensures wasmCloud has an accurate list of push-enabled devices
    after a device is removed from the system.
    """
    from django.core.cache import cache

    cache_key = f"user:push_devices:{instance.user_id}"

    # Get remaining push-enabled devices for this user
    remaining_devices = UserDevice.objects.filter(
        user_id=instance.user_id,
        is_active=True,
        push_enabled=True,
        device_token__isnull=False,
    ).values(
        'id', 'device_name', 'device_type', 'device_token',
        'token_type', 'token_hash', 'token_updated_at'
    )

    cache_data = {
        'user_id': str(instance.user_id),
        'devices': [
            {
                'id': str(d['id']),
                'device_name': d['device_name'],
                'device_type': d['device_type'],
                'device_token': d['device_token'],
                'token_type': d['token_type'],
                'token_hash': d['token_hash'],
                'token_updated_at': d['token_updated_at'].isoformat() if d['token_updated_at'] else None,
            }
            for d in remaining_devices
        ],
        'cached_at': timezone.now().isoformat(),
    }

    # Always set cache (empty list is valid - means no push devices)
    cache.set(cache_key, cache_data, timeout=3600)
    logger.info(f"Updated push devices cache for user {instance.user_id} (device deleted)")
