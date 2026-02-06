"""
Serializers for billing models.
"""

from rest_framework import serializers
from ..models.billing import BillingPlan, BillingSubscription, BillingInvoice


class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = [
            "id",
            "name",
            "slug",
            "price_usd",
            "billing_cycle",
            "features",
            "not_included",
            "max_wallets",
            "max_alerts",
            "max_api_calls",
            "max_notifications",
            "is_active",
            "is_default",
        ]


class BillingSubscriptionSerializer(serializers.ModelSerializer):
    plan = BillingPlanSerializer(read_only=True)
    plan_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = BillingSubscription
        fields = [
            "id",
            "plan",
            "plan_id",
            "status",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "current_period_start",
            "current_period_end",
            "created_at",
            "updated_at",
        ]


class BillingInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingInvoice
        fields = [
            "id",
            "amount_usd",
            "status",
            "billed_at",
            "paid_at",
        ]


class BillingUsageSerializer(serializers.Serializer):
    alerts = serializers.DictField()
    wallets = serializers.DictField()
    api_calls = serializers.DictField()
    notifications = serializers.DictField()
