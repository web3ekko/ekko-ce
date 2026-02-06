"""
Serializers for vNext AlertTemplate (executable-backed templates).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from rest_framework import serializers

from app.models.alert_templates import AlertTemplate, AlertTemplateVersion


class AlertTemplateSaveSerializer(serializers.Serializer):
    """
    Save Template request payload (vNext).

    POST /api/alert-templates/
    """

    job_id = serializers.UUIDField()
    publish_to_org = serializers.BooleanField(default=False, required=False)
    publish_to_marketplace = serializers.BooleanField(default=False, required=False)


class AlertTemplateSerializer(serializers.ModelSerializer):
    """
    Read serializer for persisted AlertTemplates (detail shape).
    """

    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    latest_template_version = serializers.IntegerField(read_only=True)
    usage_count = serializers.IntegerField(read_only=True)
    variable_names = serializers.SerializerMethodField()
    scope_networks = serializers.SerializerMethodField()
    latest_version_bundle = serializers.SerializerMethodField()

    class Meta:
        model = AlertTemplate
        fields = [
            "id",
            "fingerprint",
            "name",
            "description",
            "target_kind",
            "is_public",
            "is_verified",
            "latest_template_version",
            "usage_count",
            "variable_names",
            "scope_networks",
            "latest_version_bundle",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "fingerprint",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def _get_latest_version_obj(self, obj: AlertTemplate) -> Optional[AlertTemplateVersion]:
        # Prefer prefetched versions to avoid N+1 on list endpoints.
        versions = getattr(obj, "versions", None)
        if versions is not None and hasattr(versions, "all"):
            items = list(versions.all())
            if not items:
                return None
            return max(items, key=lambda v: int(getattr(v, "template_version", 0) or 0))
        return obj.versions.order_by("-template_version").first()

    def _get_latest_template_spec(self, obj: AlertTemplate) -> Dict[str, Any]:
        latest = self._get_latest_version_obj(obj)
        spec = getattr(latest, "template_spec", None) if latest is not None else None
        return spec if isinstance(spec, dict) else {}

    def get_variable_names(self, obj: AlertTemplate) -> list[str]:
        spec = self._get_latest_template_spec(obj)
        variables = spec.get("variables")
        if not isinstance(variables, list):
            return []
        out: list[str] = []
        for v in variables:
            if not isinstance(v, dict):
                continue
            raw = v.get("id") or v.get("name")
            if isinstance(raw, str) and raw.strip():
                out.append(raw.strip())
        return out

    def get_scope_networks(self, obj: AlertTemplate) -> list[str]:
        spec = self._get_latest_template_spec(obj)
        scope = spec.get("scope")
        if not isinstance(scope, dict):
            return []
        networks = scope.get("networks")
        if not isinstance(networks, list):
            return []
        return [str(n) for n in networks if isinstance(n, str) and n.strip()]

    def get_latest_version_bundle(self, obj: AlertTemplate) -> Optional[Dict[str, Any]]:
        """
        Return the pinned latest version bundle (template_spec + executable).

        This is used by the Dashboard marketplace flow to "Use template" without rerunning NLP.
        """

        latest = self._get_latest_version_obj(obj)
        if latest is None:
            return None

        template_spec = latest.template_spec if isinstance(latest.template_spec, dict) else None
        executable = latest.executable if isinstance(latest.executable, dict) else None
        if template_spec is None or executable is None:
            return None

        return {
            "template_version": int(latest.template_version),
            "spec_hash": str(latest.spec_hash),
            "executable_id": str(latest.executable_id),
            "registry_snapshot": {
                "kind": str(latest.registry_snapshot_kind),
                "version": str(latest.registry_snapshot_version),
                "hash": str(latest.registry_snapshot_hash),
            },
            "template_spec": template_spec,
            "executable": executable,
        }


class AlertTemplateSummarySerializer(AlertTemplateSerializer):
    """
    Summary serializer for list views (keeps payload smaller than detail, but still includes enough to use a template).
    """

    class Meta(AlertTemplateSerializer.Meta):
        fields = [
            "id",
            "fingerprint",
            "name",
            "description",
            "target_kind",
            "is_public",
            "is_verified",
            "latest_template_version",
            "usage_count",
            "variable_names",
            "scope_networks",
            "created_by_email",
            "created_at",
            "updated_at",
        ]


class AlertTemplateInlinePreviewSerializer(serializers.Serializer):
    """
    Preview a compiled AlertExecutable derived from a cached ProposedSpec v2 (job_id).

    This supports "Test Alert" before Save Template while keeping the client untrusted:
    the server fetches ProposedSpec from Redis by job_id.
    """

    job_id = serializers.UUIDField()
    target_selector = serializers.DictField()
    variable_values = serializers.DictField(required=False, default=dict)
    sample_size = serializers.IntegerField(required=False, default=50, min_value=1, max_value=500)
    effective_as_of = serializers.DateTimeField(required=False, allow_null=True)
