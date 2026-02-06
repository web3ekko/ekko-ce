"""
Serializers for developer API models.
"""

from rest_framework import serializers
from ..models.developer import ApiKey, ApiUsageRecord, ApiEndpoint


class ApiKeySerializer(serializers.ModelSerializer):
    rate_limit = serializers.SerializerMethodField()

    class Meta:
        model = ApiKey
        fields = [
            "id",
            "name",
            "key_prefix",
            "access_level",
            "status",
            "expires_at",
            "last_used_at",
            "usage_count",
            "rate_limit",
            "created_at",
        ]

    def get_rate_limit(self, obj):
        return {
            "requests_per_minute": obj.rate_limit_per_minute,
            "requests_per_day": obj.rate_limit_per_day,
        }


class ApiKeyCreateSerializer(serializers.ModelSerializer):
    rate_limit = serializers.DictField(required=False)

    class Meta:
        model = ApiKey
        fields = [
            "name",
            "access_level",
            "expires_at",
            "rate_limit",
        ]

    def validate_rate_limit(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("rate_limit must be an object")
        return value


class ApiUsageRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiUsageRecord
        fields = [
            "date",
            "requests",
            "errors",
        ]


class ApiEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiEndpoint
        fields = [
            "id",
            "path",
            "method",
            "description",
            "parameters",
            "example_request",
            "example_response",
        ]
