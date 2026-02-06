"""
Billing API views.
"""

from __future__ import annotations

from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.alerts import AlertInstance
from ..models.groups import GenericGroup, GroupType, SYSTEM_GROUP_ACCOUNTS
from ..models.notifications import NotificationDelivery
from ..models.billing import BillingPlan, BillingSubscription, BillingInvoice
from ..models.developer import ApiUsageRecord
from ..serializers.billing_serializers import (
    BillingPlanSerializer,
    BillingSubscriptionSerializer,
    BillingInvoiceSerializer,
    BillingUsageSerializer,
)


def _get_default_plan() -> BillingPlan | None:
    return BillingPlan.objects.filter(is_default=True, is_active=True).first()


def _get_or_create_subscription(user) -> BillingSubscription:
    subscription = BillingSubscription.objects.filter(user=user).order_by("-created_at").first()
    if subscription:
        return subscription

    plan = _get_default_plan() or BillingPlan.objects.filter(is_active=True).order_by("price_usd").first()
    if not plan:
        raise ValueError("No billing plans configured")

    now = timezone.now()
    if plan.billing_cycle == "yearly":
        period_end = now + timedelta(days=365)
    else:
        period_end = now + timedelta(days=30)

    return BillingSubscription.objects.create(
        user=user,
        plan=plan,
        status="active",
        current_period_start=now,
        current_period_end=period_end,
    )


def _usage_bucket(used: int, limit: int) -> dict:
    unlimited = limit == 0
    percent = 0.0 if unlimited else (used / limit * 100 if limit > 0 else 0.0)
    return {
        "used": used,
        "limit": limit,
        "percent": round(percent, 1),
        "unlimited": unlimited,
    }


class BillingOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        subscription = _get_or_create_subscription(user)
        plan = subscription.plan
        period_start = subscription.current_period_start
        period_end = subscription.current_period_end

        alerts_used = AlertInstance.objects.filter(user=user, created_at__gte=period_start).count()

        accounts_group = GenericGroup.objects.filter(
            owner=user,
            group_type=GroupType.WALLET,
            settings__system_key=SYSTEM_GROUP_ACCOUNTS,
        ).first()
        wallets_used = accounts_group.member_count if accounts_group else 0

        api_calls_used = ApiUsageRecord.objects.filter(
            user=user,
            date__gte=period_start.date(),
            date__lte=period_end.date(),
        ).aggregate(total=Sum("requests"))["total"] or 0

        notifications_used = NotificationDelivery.objects.filter(
            user=user,
            created_at__gte=period_start,
            created_at__lte=period_end,
        ).count()

        usage_payload = {
            "alerts": _usage_bucket(alerts_used, plan.max_alerts),
            "wallets": _usage_bucket(wallets_used, plan.max_wallets),
            "api_calls": _usage_bucket(api_calls_used, plan.max_api_calls),
            "notifications": _usage_bucket(notifications_used, plan.max_notifications),
        }

        invoices = BillingInvoice.objects.filter(subscription=subscription).order_by("-billed_at")[:12]

        return Response({
            "subscription": BillingSubscriptionSerializer(subscription).data,
            "plans": BillingPlanSerializer(BillingPlan.objects.filter(is_active=True), many=True).data,
            "usage": BillingUsageSerializer(usage_payload).data,
            "invoices": BillingInvoiceSerializer(invoices, many=True).data,
        })


class BillingSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        subscription = _get_or_create_subscription(user)
        plan_id = request.data.get("plan_id")

        if not plan_id:
            return Response({"error": "plan_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        plan = BillingPlan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            return Response({"error": "Plan not found"}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if plan.billing_cycle == "yearly":
            period_end = now + timedelta(days=365)
        else:
            period_end = now + timedelta(days=30)

        subscription.plan = plan
        subscription.status = "active"
        subscription.current_period_start = now
        subscription.current_period_end = period_end
        subscription.cancel_at_period_end = False
        subscription.save(update_fields=[
            "plan",
            "status",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
            "updated_at",
        ])

        return Response(BillingSubscriptionSerializer(subscription).data)
