"""
Developer API models for API keys and usage.
"""

import secrets
import uuid
import hashlib
from django.conf import settings
from django.db import models
from django.utils import timezone


class ApiKey(models.Model):
    """API key for developer access."""

    ACCESS_LEVEL_CHOICES = [
        ("full", "Full"),
        ("read_only", "Read Only"),
        ("limited", "Limited"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("expires_soon", "Expires Soon"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=100)
    key_prefix = models.CharField(max_length=32, unique=True)
    key_hash = models.CharField(max_length=64)
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default="full")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    rate_limit_per_day = models.PositiveIntegerField(default=10000)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "developer_api_keys"
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.name}"

    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Generate raw API key and prefix."""
        raw_key = secrets.token_urlsafe(32)
        prefix = f"ek_{raw_key[:10]}"
        return raw_key, prefix

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Hash the raw API key for storage."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at


class ApiUsageRecord(models.Model):
    """Daily API usage summary."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_usage_records")
    api_key = models.ForeignKey(ApiKey, on_delete=models.SET_NULL, null=True, blank=True, related_name="usage_records")
    date = models.DateField()
    requests = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "developer_api_usage"
        verbose_name = "API Usage Record"
        verbose_name_plural = "API Usage Records"
        unique_together = [["user", "date", "api_key"]]
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.date} ({self.requests} requests)"


class ApiEndpoint(models.Model):
    """Documented API endpoint metadata."""

    METHOD_CHOICES = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("PATCH", "PATCH"),
        ("DELETE", "DELETE"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    description = models.TextField()
    parameters = models.JSONField(default=list, blank=True)
    example_request = models.JSONField(null=True, blank=True)
    example_response = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "developer_api_endpoints"
        verbose_name = "API Endpoint"
        verbose_name_plural = "API Endpoints"
        unique_together = [["path", "method"]]
        indexes = [
            models.Index(fields=["path"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.path}"
