from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class AlertTemplate(models.Model):
    """
    Persisted, shareable alert template identity (vNext).

    IMPORTANT:
    - This replaces the legacy AlertTemplate v1 model entirely.
    - Versioned template content and the pinned executable live in AlertTemplateVersion.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fingerprint = models.CharField(max_length=80, db_index=True, help_text="sha256:... semantic fingerprint")

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_kind = models.CharField(max_length=32, default="wallet")

    # Visibility:
    # - is_public: marketplace
    # - is_verified: org-shared (retained for consistency across the app)
    is_public = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_alert_templates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "alert_templates"
        indexes = [
            models.Index(fields=["created_by"], name="at2_created_by_idx"),
            models.Index(fields=["is_public", "is_verified"], name="at2_visibility_idx"),
            models.Index(fields=["fingerprint"], name="at2_fingerprint_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    # ---------------------------------------------------------------------
    # Compatibility helpers
    #
    # A number of older services/views still expect AlertTemplate v1-style
    # helper methods/fields. These are thin wrappers over v2 data.
    # ---------------------------------------------------------------------

    @property
    def alert_type(self) -> str:
        """Back-compat alias used by Group APIs."""
        return str(self.target_kind or "wallet")

    def get_target_alert_type(self) -> str:
        """
        Return the normalized alert_type used by the Unified Group Model.

        Valid values are the `AlertType` choices from `app.models.groups`.
        """
        try:
            from app.models.groups import AlertType
        except Exception:
            return str(self.target_kind or "wallet").strip().lower() or "wallet"

        raw = str(self.target_kind or AlertType.WALLET).strip().lower()
        valid = {choice[0] for choice in AlertType.choices}
        return raw if raw in valid else AlertType.WALLET

    def get_template_type(self) -> str:
        """
        UI-friendly template type (wallet/token/network/protocol/contract/nft).

        Back-compat: if the latest template_spec includes metadata.event_type (legacy),
        map it into the historical template_type categories.
        """
        latest = self._latest_version_obj()
        spec = latest.template_spec if latest is not None and isinstance(latest.template_spec, dict) else {}
        metadata = spec.get("metadata") if isinstance(spec.get("metadata"), dict) else {}
        event_type = str(metadata.get("event_type") or "").strip().upper()
        if event_type:
            mapping = {
                "ACCOUNT_EVENT": "wallet",
                "ASSET_EVENT": "token",
                "PROTOCOL_EVENT": "network",
                "DEFI_EVENT": "protocol",
                "CONTRACT_INTERACTION": "contract",
                "ANOMALY_EVENT": "network",
            }
            return mapping.get(event_type, self.get_target_alert_type())

        return self.get_target_alert_type()

    def _latest_version_obj(self) -> "AlertTemplateVersion | None":
        return self.versions.order_by("-template_version").first()

    def get_spec_variables(self) -> list[dict]:
        """Return variables[] from the latest pinned template_spec bundle."""
        latest = self._latest_version_obj()
        spec = latest.template_spec if latest is not None and isinstance(latest.template_spec, dict) else {}
        variables = spec.get("variables")
        return variables if isinstance(variables, list) else []

    def get_variable_names(self) -> list[str]:
        """Return variable ids from the latest pinned template_spec bundle."""
        out: list[str] = []
        for v in self.get_spec_variables():
            if not isinstance(v, dict):
                continue
            var_id = v.get("id") or v.get("name")
            if isinstance(var_id, str) and var_id.strip():
                out.append(var_id.strip())
        return out

    def get_targeting_variable_names(self) -> list[str]:
        """
        Return the set of variable names that are considered "targeting" inputs.

        Targets are instance-scoped in v2 (selected in the UI form), but legacy
        AlertGroup logic still treats some variable names as targeting and excludes
        them from "required template params" checks.
        """
        return [
            "wallet",
            "address",
            "network",
            "subnet",
            "chain",
            "token",
            "token_address",
            "contract",
            "contract_address",
            "protocol",
            "target",
            "target_key",
            "group_id",
            "group",
        ]

    def increment_usage(self) -> None:
        """
        Back-compat no-op.

        Usage is computed dynamically via `COUNT(instances)` in query annotations.
        """
        return None


class AlertTemplateVersion(models.Model):
    """
    Versioned AlertTemplate content + pinned AlertExecutable.

    We persist both the template JSON and executable JSON as authoritative artifacts
    to prevent silent drift from implicit recompilation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(AlertTemplate, on_delete=models.CASCADE, related_name="versions")
    template_version = models.IntegerField()

    template_spec = models.JSONField(help_text="AlertTemplate JSON (schema_version=alert_template_v2)")
    spec_hash = models.CharField(max_length=80, help_text="sha256:... canonical template spec hash")

    executable_id = models.UUIDField(help_text="Deterministic UUIDv5 for the pinned executable")
    executable = models.JSONField(help_text="AlertExecutable JSON (schema_version=alert_executable_v1)")

    registry_snapshot_kind = models.CharField(max_length=64, default="datasource_catalog")
    registry_snapshot_version = models.CharField(max_length=64, default="v1")
    registry_snapshot_hash = models.CharField(max_length=80)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "alert_template_versions"
        unique_together = [("template", "template_version")]
        indexes = [
            models.Index(fields=["template", "template_version"], name="atv_template_ver_idx"),
            models.Index(fields=["registry_snapshot_hash"], name="atv_snapshot_hash_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.template_id}@{self.template_version}"
