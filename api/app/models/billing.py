"""
Billing models for subscription plans and invoices.
"""

import uuid
from django.conf import settings
from django.db import models


class BillingPlan(models.Model):
    """Subscription plan definition."""

    BILLING_CYCLE_CHOICES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES)
    features = models.JSONField(default=list)
    not_included = models.JSONField(default=list)

    max_wallets = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    max_alerts = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    max_api_calls = models.PositiveIntegerField(default=0, help_text="0 means unlimited")
    max_notifications = models.PositiveIntegerField(default=0, help_text="0 means unlimited")

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_plans"
        verbose_name = "Billing Plan"
        verbose_name_plural = "Billing Plans"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.billing_cycle})"


class BillingSubscription(models.Model):
    """User subscription record."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("trialing", "Trialing"),
        ("canceled", "Canceled"),
        ("past_due", "Past Due"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="billing_subscriptions")
    plan = models.ForeignKey(BillingPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_subscriptions"
        verbose_name = "Billing Subscription"
        verbose_name_plural = "Billing Subscriptions"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.plan.slug} ({self.status})"


class BillingInvoice(models.Model):
    """Invoice for a billing subscription."""

    STATUS_CHOICES = [
        ("paid", "Paid"),
        ("open", "Open"),
        ("void", "Void"),
        ("uncollectible", "Uncollectible"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(BillingSubscription, on_delete=models.CASCADE, related_name="invoices")
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    billed_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_invoices"
        verbose_name = "Billing Invoice"
        verbose_name_plural = "Billing Invoices"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["billed_at"]),
        ]

    def __str__(self) -> str:
        return f"Invoice {self.id} ({self.status})"
