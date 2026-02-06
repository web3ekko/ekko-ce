from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class PasskeyDevice(models.Model):
    """
    Represents a registered WebAuthn device (passkey) for a user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkey_devices')
    
    # Credential identification
    credential_id = models.TextField(unique=True, db_index=True)
    
    # Public key in COSE format (stored as base64)
    public_key = models.TextField()
    
    # Device metadata
    name = models.CharField(max_length=255, blank=True)
    aaguid = models.CharField(max_length=36, blank=True)  # Authenticator Attestation GUID
    
    # Security counters
    sign_count = models.PositiveBigIntegerField(default=0)
    
    # Device type and capabilities
    backup_eligible = models.BooleanField(default=False)
    backup_state = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'passkey_devices'
        ordering = ['-last_used_at', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['credential_id']),
        ]
    
    def __str__(self):
        return f"{self.name or 'Unnamed Device'} - {self.user.email}"
    
    def update_usage(self, sign_count: int):
        """Update device usage statistics."""
        self.sign_count = sign_count
        self.last_used_at = timezone.now()
        self.save(update_fields=['sign_count', 'last_used_at'])


class PasskeyChallenge(models.Model):
    """
    Temporary storage for WebAuthn challenges during registration/authentication.
    Uses Redis in production but provides DB fallback.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.CharField(max_length=255, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Operation type
    operation = models.CharField(max_length=20, choices=[
        ('register', 'Registration'),
        ('authenticate', 'Authentication'),
    ])
    
    # Additional data (JSON)
    data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'passkey_challenges'
        indexes = [
            models.Index(fields=['challenge']),
            models.Index(fields=['expires_at']),
        ]
    
    def is_valid(self):
        """Check if challenge is still valid."""
        return timezone.now() < self.expires_at
    
    @classmethod
    def cleanup_expired(cls):
        """Remove expired challenges."""
        cls.objects.filter(expires_at__lt=timezone.now()).delete()