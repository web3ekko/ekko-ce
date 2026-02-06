"""
Developer API views.
"""

from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateTimeField
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.developer import ApiKey, ApiUsageRecord, ApiEndpoint
from ..serializers.developer_serializers import (
    ApiKeySerializer,
    ApiKeyCreateSerializer,
    ApiUsageRecordSerializer,
    ApiEndpointSerializer,
)


class ApiKeyListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        keys = ApiKey.objects.filter(user=request.user).order_by("-created_at")
        return Response({"keys": ApiKeySerializer(keys, many=True).data})

    def post(self, request):
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_key, prefix = ApiKey.generate_key()
        rate_limit = serializer.validated_data.get("rate_limit") or {}

        api_key = ApiKey.objects.create(
            user=request.user,
            name=serializer.validated_data["name"],
            key_prefix=prefix,
            key_hash=ApiKey.hash_key(raw_key),
            access_level=serializer.validated_data.get("access_level", "full"),
            expires_at=serializer.validated_data.get("expires_at"),
            rate_limit_per_minute=rate_limit.get("requests_per_minute", 60),
            rate_limit_per_day=rate_limit.get("requests_per_day", 10000),
            status="active",
        )

        return Response({
            "key": raw_key,
            "key_details": ApiKeySerializer(api_key).data,
        }, status=status.HTTP_201_CREATED)


class ApiKeyDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, key_id):
        api_key = ApiKey.objects.filter(user=request.user, id=key_id).first()
        if not api_key:
            return Response({"error": "API key not found"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        if "name" in data:
            api_key.name = data["name"]
        if "access_level" in data:
            api_key.access_level = data["access_level"]
        if "expires_at" in data:
            try:
                api_key.expires_at = DateTimeField().to_internal_value(data["expires_at"])
            except ValidationError as exc:
                return Response({"error": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        if "rate_limit" in data and isinstance(data["rate_limit"], dict):
            api_key.rate_limit_per_minute = data["rate_limit"].get("requests_per_minute", api_key.rate_limit_per_minute)
            api_key.rate_limit_per_day = data["rate_limit"].get("requests_per_day", api_key.rate_limit_per_day)

        api_key.save()
        return Response(ApiKeySerializer(api_key).data)

    def delete(self, request, key_id):
        api_key = ApiKey.objects.filter(user=request.user, id=key_id).first()
        if not api_key:
            return Response({"error": "API key not found"}, status=status.HTTP_404_NOT_FOUND)

        api_key.status = "revoked"
        api_key.save(update_fields=["status", "updated_at"])
        api_key.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApiKeyRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, key_id):
        api_key = ApiKey.objects.filter(user=request.user, id=key_id).first()
        if not api_key:
            return Response({"error": "API key not found"}, status=status.HTTP_404_NOT_FOUND)

        api_key.status = "revoked"
        api_key.save(update_fields=["status", "updated_at"])
        return Response(ApiKeySerializer(api_key).data)


class ApiUsageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 7))
        if days <= 0 or days > 90:
            return Response({"error": "days must be between 1 and 90"}, status=status.HTTP_400_BAD_REQUEST)

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)

        usage_records = ApiUsageRecord.objects.filter(
            user=request.user,
            date__range=[start_date, end_date],
        ).order_by("date")

        usage_by_date = {record.date: record for record in usage_records}
        results = []
        current_date = start_date
        while current_date <= end_date:
            record = usage_by_date.get(current_date)
            if record:
                results.append(record)
            else:
                results.append(ApiUsageRecord(user=request.user, date=current_date, requests=0, errors=0))
            current_date += timedelta(days=1)

        serialized = ApiUsageRecordSerializer(results, many=True).data
        totals = {
            "requests": sum(item["requests"] for item in serialized),
            "errors": sum(item["errors"] for item in serialized),
        }

        return Response({"usage": serialized, "totals": totals})


class ApiEndpointsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        endpoints = ApiEndpoint.objects.filter(is_active=True).order_by("path", "method")
        return Response({"endpoints": ApiEndpointSerializer(endpoints, many=True).data})
