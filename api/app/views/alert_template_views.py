from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Max
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from app.models.alert_templates import AlertTemplate, AlertTemplateVersion
from app.serializers import (
    AlertTemplateInlinePreviewSerializer,
    AlertTemplateSaveSerializer,
    AlertTemplateSerializer,
    AlertTemplateSummarySerializer,
)
from app.services.alert_templates import (
    AlertTemplateCompileError,
    AlertTemplatePreviewError,
    CompileContext,
    NatsDuckLakeQueryExecutor,
    compile_template_to_executable,
    compute_template_fingerprint,
    compute_template_spec_hash,
    get_registry_snapshot,
    TemplatePreviewInput,
    TemplatePreviewService,
)
from app.services.nlp.proposed_spec_validation import (
    ProposedSpecError,
    extract_compiled_executable_from_proposed_spec,
    extract_template_from_proposed_spec,
)


def _derive_template_identity_fields(template: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Extract identity/presentation fields for the AlertTemplate model.

    These do not impact semantic fingerprinting (fingerprint excludes them).
    """

    name = str(template.get("name") or "").strip() or "Untitled alert template"
    description = str(template.get("description") or "").strip()
    target_kind = str(template.get("target_kind") or "").strip().lower() or "wallet"
    return name, description, target_kind


def _latest_template_version(template: AlertTemplate) -> Optional[AlertTemplateVersion]:
    return template.versions.order_by("-template_version").first()


def _get_preview_service() -> TemplatePreviewService:
    return TemplatePreviewService(executor=NatsDuckLakeQueryExecutor())


class AlertTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for executable-backed AlertTemplate CRUD operations (vNext).

    Current implementation focuses on the PRD "Save Template" flow:
    - POST /api/alert-templates/ with job_id → persist AlertTemplate + pinned executable bundle
    """

    http_method_names = ["get", "post", "head", "options"]
    serializer_class = AlertTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["target_kind", "is_public", "is_verified"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name", "usage_count", "latest_template_version"]
    ordering = ["-updated_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return AlertTemplateSaveSerializer
        if self.action == "list":
            return AlertTemplateSummarySerializer
        return AlertTemplateSerializer

    def get_queryset(self):
        """Get templates accessible to the user (private + marketplace + org-shared)."""
        user = self.request.user
        # Visibility model (vNext):
        # - marketplace: is_public=True
        # - org-shared: is_verified=True (repurposed in v1; retained for consistency)
        # - owner: created_by=user
        base = AlertTemplate.objects.filter(created_by=user) | AlertTemplate.objects.filter(is_public=True)

        try:
            from organizations.models import TeamMember

            org_ids = TeamMember.objects.filter(user=user, is_active=True).values_list(
                "team__organization_id", flat=True
            )
            if org_ids:
                org_user_ids = TeamMember.objects.filter(
                    team__organization_id__in=list(org_ids), is_active=True
                ).values_list("user_id", flat=True)
                base = base | AlertTemplate.objects.filter(is_verified=True, created_by__in=list(org_user_ids))
        except Exception:
            # If org models are unavailable for any reason, fall back to private + marketplace.
            pass

        return (
            base.distinct()
            .select_related("created_by")
            .prefetch_related("versions")
            .annotate(latest_template_version=Max("versions__template_version"))
            .annotate(usage_count=Count("instances", distinct=True))
        )

    @action(detail=True, methods=["get"])
    def latest(self, request, pk=None):
        """
        Return the pinned latest template version bundle (template_spec + executable).

        The dashboard uses this to create an AlertInstance from a marketplace template without rerunning NLP.
        """

        template = self.get_object()
        serializer = AlertTemplateSerializer(template, context={"request": request})
        payload = serializer.data
        bundle = payload.get("latest_version_bundle")
        if not bundle:
            return Response(
                {
                    "success": False,
                    "code": "template_missing_version",
                    "message": "Template has no pinned version bundle.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"success": True, "template": payload, "bundle": bundle})

    def create(self, request, *args, **kwargs):
        """
        Save Template (vNext): job_id -> persisted AlertTemplateVersion bundle.

        POST /api/alert-templates/
        """

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job_id = str(serializer.validated_data["job_id"])
        publish_to_org = bool(serializer.validated_data.get("publish_to_org", False))
        publish_to_marketplace = bool(serializer.validated_data.get("publish_to_marketplace", False))

        user_id = str(request.user.id)
        cache_key = f"nlp:proposed_spec:{user_id}:{job_id}"
        proposed_spec = cache.get(cache_key)
        if not proposed_spec:
            return Response(
                {"success": False, "code": "proposed_spec_expired", "message": "Please re-run Parse."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template_spec, _required = extract_template_from_proposed_spec(proposed_spec, expected_job_id=job_id)
        except ProposedSpecError as e:
            return Response(
                {"success": False, "code": "proposed_spec_invalid", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        template_for_hashing = deepcopy(template_spec)
        fingerprint = compute_template_fingerprint(template_for_hashing)

        # 1) Owner idempotency: return existing template if the user already saved it.
        owner_candidate = AlertTemplate.objects.filter(created_by=request.user, fingerprint=fingerprint).first()
        if owner_candidate is not None:
            update_fields = []

            # Marketplace publication is irreversible.
            if publish_to_marketplace and not owner_candidate.is_public:
                owner_candidate.is_public = True
                update_fields.append("is_public")

            # Org publication can be toggled.
            if owner_candidate.is_verified != publish_to_org:
                owner_candidate.is_verified = publish_to_org
                update_fields.append("is_verified")

            if update_fields:
                owner_candidate.save(update_fields=sorted(set(update_fields + ["updated_at"])))

            latest = _latest_template_version(owner_candidate)
            if latest is None:
                return Response(
                    {
                        "success": False,
                        "code": "template_missing_version",
                        "message": "Saved template is missing a pinned version bundle.",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "success": True,
                    "template_id": str(owner_candidate.id),
                    "template_version": int(latest.template_version),
                    "fingerprint": str(owner_candidate.fingerprint),
                    "spec_hash": str(latest.spec_hash),
                    "executable_id": str(latest.executable_id),
                    "registry_snapshot": {
                        "kind": str(latest.registry_snapshot_kind),
                        "version": str(latest.registry_snapshot_version),
                        "hash": str(latest.registry_snapshot_hash),
                    },
                    "visibility": {
                        "publish_to_org": bool(owner_candidate.is_verified),
                        "publish_to_marketplace": bool(owner_candidate.is_public),
                    },
                },
                status=status.HTTP_200_OK,
            )

        # 2) Marketplace dedupe: never create duplicates of existing marketplace templates.
        marketplace_candidate = AlertTemplate.objects.filter(is_public=True, fingerprint=fingerprint).first()
        if marketplace_candidate is not None:
            latest = _latest_template_version(marketplace_candidate)
            return Response(
                {
                    "success": False,
                    "code": "marketplace_template_exists",
                    "existing_template": {
                        "template_id": str(marketplace_candidate.id),
                        "template_version": int(latest.template_version) if latest is not None else 1,
                        "fingerprint": fingerprint,
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 3) Create a new private template version bundle (optionally publish).
        template_id = uuid.uuid4()
        template_version = 1

        template_to_persist = deepcopy(template_spec)
        template_to_persist["schema_version"] = "alert_template_v2"
        template_to_persist["template_id"] = str(template_id)
        template_to_persist["template_version"] = template_version
        template_to_persist["fingerprint"] = fingerprint
        template_to_persist["spec_hash"] = ""  # filled after hashing

        spec_hash = compute_template_spec_hash(template_to_persist)
        template_to_persist["spec_hash"] = spec_hash

        snapshot = get_registry_snapshot()
        try:
            executable = compile_template_to_executable(
                template_to_persist,
                ctx=CompileContext(
                    template_id=template_id,
                    template_version=template_version,
                    registry_snapshot=snapshot,
                ),
            )
        except AlertTemplateCompileError as e:
            return Response(
                {"success": False, "code": "template_compile_error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exec_id = executable.get("executable_id")
        if not isinstance(exec_id, str) or not exec_id.strip():
            return Response(
                {"success": False, "code": "executable_invalid", "message": "Compiled executable missing id"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        with transaction.atomic():
            name, description, target_kind = _derive_template_identity_fields(template_to_persist)
            template = AlertTemplate.objects.create(
                id=template_id,
                fingerprint=fingerprint,
                name=name,
                description=description,
                target_kind=target_kind,
                is_public=bool(publish_to_marketplace),
                is_verified=bool(publish_to_org),
                created_by=request.user,
            )

            AlertTemplateVersion.objects.create(
                template=template,
                template_version=template_version,
                template_spec=template_to_persist,
                spec_hash=spec_hash,
                executable_id=uuid.UUID(exec_id),
                executable=executable,
                registry_snapshot_kind=str(snapshot.get("kind") or "datasource_catalog"),
                registry_snapshot_version=str(snapshot.get("version") or "v1"),
                registry_snapshot_hash=str(snapshot.get("hash") or ""),
            )

        return Response(
            {
                "success": True,
                "template_id": str(template.id),
                "template_version": template_version,
                "fingerprint": fingerprint,
                "spec_hash": spec_hash,
                "executable_id": exec_id,
                "registry_snapshot": dict(snapshot),
                "visibility": {
                    "publish_to_org": bool(template.is_verified),
                    "publish_to_marketplace": bool(template.is_public),
                },
                },
                status=status.HTTP_201_CREATED,
            )

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        """
        Preview a compiled executable derived from a cached ProposedSpec v2 (job_id).

        This supports Dashboard "Test Alert" before Save Template, while keeping the client untrusted:
        the server fetches ProposedSpec from Redis by job_id and uses its compiled_executable.
        """

        serializer = AlertTemplateInlinePreviewSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        job_id = str(serializer.validated_data["job_id"])
        target_selector = serializer.validated_data["target_selector"]
        variable_values = serializer.validated_data.get("variable_values") or {}
        sample_size = int(serializer.validated_data.get("sample_size") or 50)
        effective_as_of = serializer.validated_data.get("effective_as_of")

        user_id = str(request.user.id)
        cache_key = f"nlp:proposed_spec:{user_id}:{job_id}"
        proposed_spec = cache.get(cache_key)
        if not proposed_spec:
            return Response(
                {"success": False, "code": "proposed_spec_expired", "message": "Please re-run Parse."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template_spec, _required = extract_template_from_proposed_spec(proposed_spec, expected_job_id=job_id)
            executable = extract_compiled_executable_from_proposed_spec(proposed_spec, expected_job_id=job_id)
        except ProposedSpecError as e:
            return Response(
                {"success": False, "code": "proposed_spec_invalid", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from datetime import datetime, timezone

        from app.models.groups import (
            ALERT_TYPE_TO_GROUP_TYPE,
            AlertType,
            GenericGroup,
            normalize_network_subnet_address_key,
            normalize_network_subnet_address_token_id_key,
            normalize_network_subnet_key,
            normalize_network_subnet_protocol_key,
        )
        from app.services.alert_templates import AlertTemplateSpecError, validate_variable_values_against_template

        template_target_kind = str(template_spec.get("target_kind") or "wallet").strip().lower()
        alert_type = (
            template_target_kind
            if template_target_kind in {c[0] for c in AlertType.choices}
            else AlertType.WALLET
        )

        if not isinstance(target_selector, dict):
            return Response(
                {"success": False, "code": "invalid_target_selector", "message": "target_selector must be an object"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mode = target_selector.get("mode")
        if mode not in {"keys", "group"}:
            return Response(
                {
                    "success": False,
                    "code": "invalid_target_selector",
                    "message": "target_selector.mode must be 'keys' or 'group'",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resolved_variables = validate_variable_values_against_template(template_spec, variable_values)
        except AlertTemplateSpecError as e:
            return Response(
                {"success": False, "code": "invalid_variable_values", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_keys: list[str] = []
        if mode == "keys":
            raw_keys = target_selector.get("keys")
            if not isinstance(raw_keys, list) or not raw_keys:
                return Response(
                    {"success": False, "code": "invalid_target_selector", "message": "keys must be a non-empty list"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            normalized: list[str] = []
            for raw in raw_keys:
                if not isinstance(raw, str) or not raw.strip():
                    continue
                if alert_type == AlertType.NETWORK:
                    normalized.append(normalize_network_subnet_key(raw))
                elif alert_type == AlertType.PROTOCOL:
                    normalized.append(normalize_network_subnet_protocol_key(raw))
                elif alert_type == AlertType.NFT:
                    text = raw.strip()
                    if text.count(":") >= 3:
                        normalized.append(normalize_network_subnet_address_token_id_key(text))
                    else:
                        normalized.append(normalize_network_subnet_address_key(text))
                else:
                    normalized.append(normalize_network_subnet_address_key(raw))
            target_keys = normalized[:sample_size]

        if mode == "group":
            group_id = target_selector.get("group_id")
            if not group_id:
                return Response(
                    {"success": False, "code": "invalid_target_selector", "message": "group_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                group = GenericGroup.objects.get(id=group_id)
            except GenericGroup.DoesNotExist:
                return Response(
                    {"success": False, "code": "invalid_target_selector", "message": "Group not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if group.owner_id != request.user.id:
                return Response(
                    {"success": False, "code": "invalid_target_selector", "message": "Group not accessible"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            valid_group_types = ALERT_TYPE_TO_GROUP_TYPE.get(alert_type, [])
            if group.group_type not in valid_group_types:
                return Response(
                    {
                        "success": False,
                        "code": "invalid_target_selector",
                        "message": f"Group type '{group.group_type}' is not valid for alert_type '{alert_type}'",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Preview uses a small sample to avoid enumerating 10k+ members.
            target_keys = group.get_member_keys()[:sample_size]

        if not target_keys:
            return Response(
                {"success": False, "code": "no_targets", "message": "No targets available for preview."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Partition keys by {NETWORK, subnet} for correctness when groups contain mixed networks.
        partitions: dict[tuple[str, str], list[str]] = {}
        for k in target_keys:
            if not isinstance(k, str) or ":" not in k:
                continue
            network, _sep, rest = k.partition(":")
            subnet, _sep2, _rest2 = rest.partition(":")
            net = network.strip().upper()
            sub = subnet.strip().lower() or "mainnet"
            partitions.setdefault((net, sub), []).append(k)

        effective_as_of_rfc3339 = (
            effective_as_of.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            if effective_as_of is not None
            else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        service = _get_preview_service()
        merged_sample: list[dict[str, Any]] = []
        total_evaluated = 0
        total_matched = 0
        for (net, sub), keys in sorted(partitions.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            chain_id = 1 if net == "ETH" else 43114 if net == "AVAX" else 0
            if chain_id == 0:
                continue
            try:
                result = service.preview(
                    TemplatePreviewInput(
                        executable=executable,
                        network=net,
                        subnet=sub,
                        chain_id=chain_id,
                        target_keys=keys,
                        variables=resolved_variables,
                        effective_as_of_rfc3339=effective_as_of_rfc3339,
                        sample_matches=max(0, 10 - len(merged_sample)),
                    )
                )
            except AlertTemplatePreviewError as e:
                return Response(
                    {"success": False, "code": "preview_failed", "message": str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
            total_evaluated += int(summary.get("total_events_evaluated") or 0)
            total_matched += int(summary.get("would_have_triggered") or 0)
            for sample in result.get("sample_triggers") if isinstance(result.get("sample_triggers"), list) else []:
                if len(merged_sample) >= 10:
                    break
                merged_sample.append(sample)

        return Response(
            {
                "success": True,
                "summary": {
                    "total_events_evaluated": total_evaluated,
                    "would_have_triggered": total_matched,
                    "trigger_rate": round((total_matched / total_evaluated) if total_evaluated else 0.0, 4),
                    "estimated_daily_triggers": 0.0,
                    "evaluation_time_ms": 0.0,
                },
                "sample_triggers": merged_sample,
                "near_misses": [],
                "evaluation_mode": "aggregate",
                "requires_wasmcloud": False,
                "effective_as_of": effective_as_of_rfc3339,
            },
            status=status.HTTP_200_OK,
        )
