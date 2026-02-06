"""
Serializers for Alert Job Configuration API

Used by actors (blockchain transaction processors) and Alert Scheduler Provider
to query active alerts and record job creation.
"""
from rest_framework import serializers
from django.utils import timezone
from app.models import AlertInstance


class AlertJobConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for AlertInstance configuration returned to actors/provider.

    Includes only the fields needed for job creation decision-making.
    """
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    trigger_type = serializers.CharField(read_only=True)
    trigger_config = serializers.JSONField(read_only=True)
    template_id = serializers.UUIDField(read_only=True, allow_null=True)
    template_params = serializers.JSONField(read_only=True)
    alert_type = serializers.CharField(read_only=True)
    target_keys = serializers.JSONField(read_only=True)
    spec = serializers.SerializerMethodField()
    job_creation_count = serializers.IntegerField(read_only=True)
    last_job_created_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = AlertInstance
        fields = [
            'id',
            'name',
            'trigger_type',
            'trigger_config',
            'template_id',
            'template_params',
            'alert_type',
            'target_keys',
            'spec',
            'job_creation_count',
            'last_job_created_at',
        ]

    def get_spec(self, obj):
        """Return execution spec (AlertTemplateIR v1) without pre-rendering placeholders."""
        template = getattr(obj, "template", None)
        template_spec = getattr(template, "spec", None) if template is not None else None
        if isinstance(template_spec, dict) and template_spec:
            return template_spec

        standalone = getattr(obj, "_standalone_spec", None)
        if isinstance(standalone, dict) and standalone:
            return standalone

        # Fallback to computed spec (may have rendered placeholders)
        return getattr(obj, "spec", {}) or {}


class RecordJobCreationSerializer(serializers.Serializer):
    """
    Serializer for recording when an AlertJob was created for an alert.

    Used by actors and Alert Scheduler Provider to increment job_creation_count
    and update last_job_created_at.
    """
    alert_id = serializers.UUIDField(required=True)
    created_at = serializers.DateTimeField(required=True)

    def validate_alert_id(self, value):
        """Validate that alert_id exists"""
        try:
            AlertInstance.objects.get(id=value)
        except AlertInstance.DoesNotExist:
            raise serializers.ValidationError(f"Alert with ID {value} does not exist")
        return value

    def validate_created_at(self, value):
        """Validate that created_at is not too far in the future"""
        # Allow up to 10 minutes in the future to account for clock skew between systems
        from datetime import timedelta
        max_future = timezone.now() + timedelta(minutes=10)
        if value > max_future:
            raise serializers.ValidationError("created_at cannot be more than 10 minutes in the future")
        return value
