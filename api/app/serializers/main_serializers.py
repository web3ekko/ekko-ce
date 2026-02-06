"""
Django REST Framework Serializers for Enhanced Alert System
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models.alerts import (
    AlertInstance, AlertChangeLog, AlertExecution, DefaultNetworkAlert
)

User = get_user_model()


class AlertChangeLogSerializer(serializers.ModelSerializer):
    """Serializer for Alert Change Logs"""
    changed_by_email = serializers.EmailField(source='changed_by.email', read_only=True)
    alert_instance_name = serializers.CharField(source='alert_instance.name', read_only=True)

    class Meta:
        model = AlertChangeLog
        fields = [
            'id', 'alert_instance', 'alert_instance_name', 'from_version', 'to_version',
            'change_type', 'changed_fields', 'old_values', 'new_values',
            'changed_by', 'changed_by_email', 'change_reason', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'changed_by_email', 'alert_instance_name']


class AlertExecutionSerializer(serializers.ModelSerializer):
    """Serializer for Alert Executions - Consolidated model tracking execution and retries"""

    alert_instance_name = serializers.CharField(source='alert_instance.name', read_only=True)
    execution_time = serializers.SerializerMethodField()

    class Meta:
        model = AlertExecution
        fields = [
            'id', 'alert_instance', 'alert_instance_name', 'attempt_number', 'max_retries',
            'frozen_spec', 'started_at', 'completed_at', 'status', 'result',
            'result_data', 'result_metadata', 'execution_time_ms', 'rows_processed',
            'data_sources_used', 'error_message', 'error_details', 'execution_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'started_at', 'created_at', 'updated_at', 'alert_instance_name', 'execution_time']

    def get_execution_time(self, obj):
        """Get execution time in seconds"""
        return obj.execution_time


class AlertInstanceSerializer(serializers.ModelSerializer):
    """Serializer for AlertInstance model - User's subscription to a template or standalone alert"""

    user_email = serializers.EmailField(source='user.email', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True, allow_null=True)
    spec = serializers.SerializerMethodField(read_only=True)
    chains = serializers.SerializerMethodField()
    trigger_mode = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    target_group_name = serializers.SerializerMethodField()
    target_group_type = serializers.SerializerMethodField()

    class Meta:
        model = AlertInstance
        fields = [
            'id', 'name', 'nl_description', 'spec', 'event_type', 'sub_event',
            'sub_event_confidence', 'sub_event_proposed',
            'template', 'template_version', 'template_name',
            'trigger_type', 'trigger_config',
            'template_params', 'alert_type', 'target_group', 'target_keys',
            'target_group_name', 'target_group_type',
            'version', 'enabled', 'user', 'user_email', 'author',
            'chains', 'trigger_mode', 'priority', 'processing_status', 'processing_error',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'created_at', 'updated_at', 'user', 'spec', 'processing_status', 'processing_error']

    def get_spec(self, obj):
        """Get computed spec from template or standalone"""
        return obj.spec

    def get_chains(self, obj):
        """Get chain names from spec"""
        return obj.get_chains()

    def get_trigger_mode(self, obj):
        """Get trigger mode"""
        return obj.get_trigger_mode()

    def get_priority(self, obj):
        """Get alert priority"""
        return obj.get_priority()

    def get_target_group_name(self, obj):
        """Get target group name (if targeting a group)."""
        if getattr(obj, 'target_group', None) is None:
            return None
        return getattr(obj.target_group, 'name', None)

    def get_target_group_type(self, obj):
        """Get target group type (if targeting a group)."""
        if getattr(obj, 'target_group', None) is None:
            return None
        return getattr(obj.target_group, 'group_type', None)

    def validate(self, data):
        """
        Validate update payload.

        Notes:
        - Alert creation uses AlertInstanceCreateSerializer, not this serializer.
        - PATCH requests may update name/enabled without resending template/spec.
        - Targeting must use exactly one mechanism: target_group OR target_keys.
        """
        instance = getattr(self, 'instance', None)
        effective_alert_type = data.get('alert_type') or getattr(instance, 'alert_type', None) or 'wallet'

        target_group = data.get('target_group', getattr(instance, 'target_group', None))
        target_keys = data.get('target_keys', getattr(instance, 'target_keys', None))

        if target_group and target_keys:
            raise serializers.ValidationError({
                'target_group': "Cannot set target_group when target_keys are provided",
                'target_keys': "Cannot set target_keys when target_group is provided",
            })

        if target_group is not None:
            from app.models.groups import ALERT_TYPE_TO_GROUP_TYPE

            valid_group_types = ALERT_TYPE_TO_GROUP_TYPE.get(effective_alert_type, [])
            if target_group and target_group.group_type not in valid_group_types:
                raise serializers.ValidationError({
                    'target_group': (
                        f"Alert type '{effective_alert_type}' requires a target group of type {valid_group_types}, "
                        f"got '{target_group.group_type}'"
                    )
                })

        if 'target_keys' in data and data.get('target_keys'):
            from app.services.group_service import AlertValidationService
            AlertValidationService.validate_targets(effective_alert_type, data['target_keys'])

        return data

    def create(self, validated_data):
        """Create a new alert instance"""
        validated_data['user'] = self.context['request'].user
        alert_instance = super().create(validated_data)

        # Create initial change log entry
        AlertChangeLog.objects.create(
            alert_instance=alert_instance,
            from_version=None,
            to_version=1,
            change_type='created',
            changed_fields=['name', 'nl_description', 'enabled'],
            old_values=None,
            new_values={
                'name': alert_instance.name,
                'nl_description': alert_instance.nl_description,
                'enabled': alert_instance.enabled,
            },
            changed_by=self.context['request'].user
        )

        return alert_instance

    def update(self, instance, validated_data):
        """Update an alert instance and increment version"""
        # Create change log entry
        old_values = {
            'name': instance.name,
            'nl_description': instance.nl_description,
            'enabled': instance.enabled,
        }

        # Update the instance
        updated_instance = super().update(instance, validated_data)

        # Create change log
        changed_fields = []
        new_values = {}

        for field, old_value in old_values.items():
            new_value = getattr(updated_instance, field)
            if old_value != new_value:
                changed_fields.append(field)
                new_values[field] = new_value

        if changed_fields:
            AlertChangeLog.objects.create(
                alert_instance=updated_instance,
                from_version=instance.version,
                to_version=instance.version + 1,
                change_type='updated',
                changed_fields=changed_fields,
                old_values=old_values,
                new_values=new_values,
                changed_by=self.context['request'].user
            )

            # Increment version
            updated_instance.version += 1
            updated_instance.save(update_fields=['version'])

        return updated_instance


class AlertInstanceCreateRequestSerializer(serializers.Serializer):
    """
    Create AlertInstance from a saved, pinned AlertTemplateVersion bundle (vNext).

    Instances bind:
    - targets (keys or group)
    - variable values
    - trigger config
    while remaining pinned to a specific template executable.
    """

    template_id = serializers.UUIDField()
    template_version = serializers.IntegerField(min_value=1)

    name = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    enabled = serializers.BooleanField(default=True, required=False)
    trigger_type = serializers.ChoiceField(choices=["event_driven", "periodic", "one_time"])
    trigger_config = serializers.DictField(required=False, default=dict)
    target_selector = serializers.DictField()
    variable_values = serializers.DictField(required=False, default=dict)
    notification_overrides = serializers.DictField(required=False, default=dict)

    def validate(self, data):
        from app.models.alert_templates import AlertTemplate, AlertTemplateVersion
        from app.models.groups import (
            ALERT_TYPE_TO_GROUP_TYPE,
            AlertType,
            GenericGroup,
            normalize_network_subnet_address_key,
            normalize_network_subnet_address_token_id_key,
            normalize_network_subnet_key,
            normalize_network_subnet_protocol_key,
        )
        from app.services.alert_templates.validation import (
            AlertTemplateSpecError,
            validate_variable_values_against_template,
        )

        request = self.context.get("request")
        if request is None or not hasattr(request, "user"):
            raise serializers.ValidationError("Request context required")

        user = request.user
        template_id = data.get("template_id")
        template_version = data.get("template_version")

        try:
            template = AlertTemplate.objects.select_related("created_by").get(id=template_id)
        except AlertTemplate.DoesNotExist as exc:
            raise serializers.ValidationError({"template_id": "Template not found"}) from exc

        # Access control: private + marketplace + org-shared.
        if template.created_by_id != user.id and not template.is_public:
            if not template.is_verified:
                raise serializers.ValidationError({"template_id": "Template not accessible"})
            try:
                from organizations.models import TeamMember

                org_ids = TeamMember.objects.filter(user=user, is_active=True).values_list(
                    "team__organization_id", flat=True
                )
                if not org_ids:
                    raise serializers.ValidationError({"template_id": "Template not accessible"})

                shares_org = TeamMember.objects.filter(
                    user=template.created_by,
                    is_active=True,
                    team__organization_id__in=list(org_ids),
                ).exists()
                if not shares_org:
                    raise serializers.ValidationError({"template_id": "Template not accessible"})
            except serializers.ValidationError:
                raise
            except Exception as exc:
                raise serializers.ValidationError({"template_id": "Template not accessible"}) from exc

        try:
            tmpl_ver = AlertTemplateVersion.objects.get(template=template, template_version=int(template_version))
        except AlertTemplateVersion.DoesNotExist as exc:
            raise serializers.ValidationError({"template_version": "Template version not found"}) from exc

        template_spec = tmpl_ver.template_spec if isinstance(tmpl_ver.template_spec, dict) else {}

        variable_values = data.get("variable_values") or {}
        try:
            resolved_variables = validate_variable_values_against_template(template_spec, variable_values)
        except AlertTemplateSpecError as exc:
            raise serializers.ValidationError({"variable_values": str(exc)}) from exc

        raw_overrides = data.get("notification_overrides") or {}
        if raw_overrides:
            if not isinstance(raw_overrides, dict):
                raise serializers.ValidationError({"notification_overrides": "notification_overrides must be an object"})
            cleaned_overrides: dict[str, str] = {}
            for key in ("title_template", "body_template"):
                if key not in raw_overrides:
                    continue
                value = raw_overrides.get(key)
                if value is None:
                    continue
                if not isinstance(value, str):
                    raise serializers.ValidationError({"notification_overrides": f"{key} must be a string"})
                trimmed = value.strip()
                if trimmed:
                    cleaned_overrides[key] = trimmed
            if cleaned_overrides:
                data["_notification_overrides"] = cleaned_overrides

        raw_kind = str(template.target_kind or "wallet").strip().lower()
        valid_alert_types = {choice[0] for choice in AlertType.choices}
        alert_type = raw_kind if raw_kind in valid_alert_types else AlertType.WALLET

        selector = data.get("target_selector")
        if not isinstance(selector, dict):
            raise serializers.ValidationError({"target_selector": "target_selector must be an object"})
        mode = selector.get("mode")
        if mode not in {"keys", "group"}:
            raise serializers.ValidationError({"target_selector": "mode must be 'keys' or 'group'"})

        target_keys = []
        target_group = None

        if mode == "keys":
            # Enforce a single targeting mechanism: keys mode cannot include group_id.
            if selector.get("group_id"):
                raise serializers.ValidationError({"target_selector": "group_id is not allowed when mode='keys'"})
            raw_keys = selector.get("keys")
            if not isinstance(raw_keys, list) or not raw_keys:
                raise serializers.ValidationError({"target_selector": "keys must be a non-empty list"})

            normalized = []
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

            if not normalized:
                raise serializers.ValidationError({"target_selector": "keys must include at least one valid key"})
            target_keys = normalized

        if mode == "group":
            # Enforce a single targeting mechanism: group mode cannot include keys.
            if selector.get("keys"):
                raise serializers.ValidationError({"target_selector": "keys is not allowed when mode='group'"})
            group_id = selector.get("group_id")
            if not group_id:
                raise serializers.ValidationError({"target_selector": "group_id is required when mode='group'"})
            try:
                target_group = GenericGroup.objects.get(id=group_id, owner=user)
            except GenericGroup.DoesNotExist as exc:
                raise serializers.ValidationError({"target_selector": "group_id not found"}) from exc

            valid_group_types = ALERT_TYPE_TO_GROUP_TYPE.get(alert_type, [])
            if target_group.group_type not in valid_group_types:
                raise serializers.ValidationError(
                    {"target_selector": f"Group type '{target_group.group_type}' is not valid for alert_type '{alert_type}'"}
                )

        data["_resolved_variable_values"] = resolved_variables
        data["_target_keys"] = target_keys
        data["_target_group"] = target_group
        data["_alert_type"] = alert_type
        data["_template_obj"] = template
        data["_template_version_obj"] = tmpl_ver

        return data


class AlertInstanceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for alert instance lists"""

    user_email = serializers.EmailField(source='user.email', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True, allow_null=True)
    chains = serializers.SerializerMethodField()
    trigger_mode = serializers.SerializerMethodField()

    class Meta:
        model = AlertInstance
        fields = [
            'id', 'name', 'event_type', 'sub_event', 'version', 'enabled',
            'user_email', 'template_name', 'template', 'template_version',
            'trigger_type', 'trigger_config',
            'chains', 'trigger_mode',
            'processing_status', 'created_at', 'updated_at'
        ]

    def get_chains(self, obj):
        """Get chain names from spec"""
        return obj.get_chains()

    def get_trigger_mode(self, obj):
        """Get trigger mode"""
        return obj.get_trigger_mode()


# ===================================================================
# Notification Endpoint Serializers
# ===================================================================

from ..models.notifications import (
    NotificationChannelEndpoint,
    TeamMemberNotificationOverride,
    NotificationChannelVerification,
)


class NotificationChannelEndpointSerializer(serializers.ModelSerializer):
    """Serializer for NotificationChannelEndpoint model"""

    owner_id = serializers.UUIDField(read_only=True)
    owner_type = serializers.CharField(read_only=True)

    class Meta:
        model = NotificationChannelEndpoint
        fields = [
            'id', 'owner_type', 'owner_id', 'channel_type', 'label',
            'config', 'enabled', 'verified', 'verified_at', 'routing_mode',
            'priority_filters', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner_type', 'owner_id', 'verified', 'verified_at', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create endpoint with current user as owner and creator"""
        request = self.context.get('request')
        validated_data['owner_type'] = 'user'
        validated_data['owner_id'] = request.user.id
        validated_data['created_by'] = request.user

        # Auto-verify webhook and slack channels
        if validated_data['channel_type'] in ['webhook', 'slack']:
            validated_data['verified'] = True
            from django.utils import timezone
            validated_data['verified_at'] = timezone.now()

        return super().create(validated_data)


class TeamNotificationChannelEndpointSerializer(NotificationChannelEndpointSerializer):
    """Serializer for team-owned notification endpoints"""

    owner_id = serializers.UUIDField(required=True, write_only=True)

    class Meta(NotificationChannelEndpointSerializer.Meta):
        fields = NotificationChannelEndpointSerializer.Meta.fields
        read_only_fields = ['id', 'owner_type', 'verified', 'verified_at', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create endpoint with team as owner"""
        request = self.context.get('request')
        validated_data['owner_type'] = 'team'
        validated_data['created_by'] = request.user

        # Auto-verify webhook and slack channels
        if validated_data['channel_type'] in ['webhook', 'slack']:
            validated_data['verified'] = True
            from django.utils import timezone
            validated_data['verified_at'] = timezone.now()

        return NotificationChannelEndpoint.objects.create(**validated_data)

    def to_representation(self, instance):
        """Mask sensitive config for non-admin users"""
        representation = super().to_representation(instance)
        request = self.context.get('request')

        # Check if user is admin/owner of the team
        from organizations.models import TeamMember, TeamMemberRole
        try:
            member = TeamMember.objects.get(team_id=instance.owner_id, user=request.user)
            is_admin = member.role in [TeamMemberRole.OWNER, TeamMemberRole.ADMIN]
        except TeamMember.DoesNotExist:
            is_admin = False

        # Mask config for non-admins
        if not is_admin and representation.get('config'):
            masked_config = {}
            for key in representation['config'].keys():
                masked_config[key] = '***'
            representation['config'] = masked_config

        return representation


class NotificationChannelVerificationSerializer(serializers.ModelSerializer):
    """Serializer for NotificationChannelVerification model"""

    class Meta:
        model = NotificationChannelVerification
        fields = ['id', 'verification_code', 'verification_type', 'expires_at', 'verified_at', 'created_at', 'attempts']
        read_only_fields = ['id', 'verification_code', 'verified_at', 'created_at', 'attempts']


class TeamMemberNotificationOverrideSerializer(serializers.ModelSerializer):
    """Serializer for TeamMemberNotificationOverride model"""

    team_id = serializers.UUIDField(source='team.id', read_only=True)
    member_id = serializers.UUIDField(source='member.id', read_only=True)

    class Meta:
        model = TeamMemberNotificationOverride
        fields = [
            'id', 'team_id', 'member_id', 'team_notifications_enabled',
            'disabled_endpoints', 'disabled_priorities', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'team_id', 'member_id', 'created_at', 'updated_at']


# ===================================================================
# Alert Preview/Dry-Run Serializers
# ===================================================================


class PreviewConfigSerializer(serializers.Serializer):
    """
    Serializer for alert preview/dry-run request configuration.

    Used for both template preview and instance preview endpoints.
    """

    # Template parameters (required for template preview, optional for instance)
    parameters = serializers.DictField(
        required=False,
        default=dict,
        help_text="Template parameters to use for rendering spec (required for template preview)"
    )

    # Preview configuration
    time_range = serializers.ChoiceField(
        choices=['1h', '24h', '7d', '30d'],
        default='7d',
        help_text="Time range for historical data query"
    )

    limit = serializers.IntegerField(
        min_value=1,
        max_value=10000,
        default=1000,
        help_text="Maximum number of rows to evaluate"
    )

    include_near_misses = serializers.BooleanField(
        default=False,
        help_text="Include transactions that nearly matched the condition"
    )

    explain_mode = serializers.BooleanField(
        default=False,
        help_text="Include detailed explanation of condition matching"
    )

    # Optional filters
    addresses = serializers.ListField(
        child=serializers.CharField(max_length=128),
        required=False,
        default=list,
        help_text="Override target addresses for preview"
    )

    chain = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        help_text="Override chain filter for preview"
    )


class PreviewTriggerSerializer(serializers.Serializer):
    """Serializer for individual preview trigger/match results."""

    timestamp = serializers.DateTimeField(help_text="When the condition would have triggered")
    data = serializers.DictField(help_text="Row data that matched the condition")
    matched_condition = serializers.CharField(help_text="Expression that matched")


class PreviewNearMissSerializer(serializers.Serializer):
    """Serializer for near-miss results."""

    timestamp = serializers.DateTimeField(required=False)
    data = serializers.DictField()
    threshold_distance = serializers.FloatField(
        help_text="Percentage distance from threshold"
    )
    explanation = serializers.CharField(
        required=False,
        help_text="Human-readable explanation of the near-miss"
    )


class PreviewSummarySerializer(serializers.Serializer):
    """Serializer for preview summary statistics."""

    total_events_evaluated = serializers.IntegerField()
    would_have_triggered = serializers.IntegerField()
    trigger_rate = serializers.FloatField(
        help_text="Ratio of triggers to total events"
    )
    estimated_daily_triggers = serializers.FloatField(
        help_text="Estimated triggers per day based on sample"
    )
    evaluation_time_ms = serializers.FloatField(
        help_text="Time taken to evaluate in milliseconds"
    )


class PreviewResultSerializer(serializers.Serializer):
    """
    Serializer for alert preview/dry-run results.

    Returns comprehensive preview data including:
    - Summary statistics
    - Sample triggers
    - Near-miss results (optional)
    - Evaluation metadata
    """

    success = serializers.BooleanField()
    preview_id = serializers.UUIDField(required=False)

    # Summary statistics
    summary = PreviewSummarySerializer()

    # Sample matching rows
    sample_triggers = PreviewTriggerSerializer(many=True, default=list)

    # Near-miss results (if requested)
    near_misses = PreviewNearMissSerializer(many=True, default=list)

    # Evaluation metadata
    evaluation_mode = serializers.ChoiceField(
        choices=['per_row', 'aggregate', 'window', 'unknown'],
        help_text="How the expression was evaluated"
    )
    expression = serializers.CharField(
        required=False,
        help_text="The condition expression that was evaluated"
    )
    data_source = serializers.CharField(
        required=False,
        help_text="Data source used for preview (transactions, wallet_balances, etc.)"
    )
    time_range = serializers.CharField(
        required=False,
        help_text="Time range queried"
    )

    # Routing info
    requires_wasmcloud = serializers.BooleanField(
        default=False,
        help_text="Whether evaluation required wasmCloud (aggregate/window functions)"
    )
    wasmcloud_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Reason wasmCloud was required"
    )

    # Error handling
    error = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Error message if preview failed"
    )


# ===================================================================
# NLP Pipeline Clarification Serializers
# ===================================================================


class InlineSuggestionSerializer(serializers.Serializer):
    """
    Serializer for inline suggestions in progressive refinement.

    Represents a single interpretation option for ambiguous input.
    """

    field = serializers.CharField(help_text="The field this suggestion applies to")
    label = serializers.CharField(help_text="User-friendly label for this option")
    description = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Explanation of this interpretation"
    )
    value = serializers.JSONField(help_text="The suggested value")
    selected = serializers.BooleanField(
        default=False, help_text="Whether this is the auto-selected default"
    )
    confidence = serializers.IntegerField(
        min_value=0, max_value=100,
        help_text="Confidence percentage (0-100)"
    )


class ClarificationQuestionSerializer(serializers.Serializer):
    """
    Serializer for clarification questions.

    Used when confidence is too low for auto-selection.
    """

    field = serializers.CharField(help_text="Field requiring clarification")
    question = serializers.CharField(help_text="User-friendly question text")
    type = serializers.ChoiceField(
        choices=[
            'chain_ambiguity', 'threshold_missing', 'direction_ambiguous',
            'address_missing', 'token_ambiguous', 'time_window_missing',
            'event_type_ambiguous'
        ],
        help_text="Type of clarification needed"
    )
    priority = serializers.ChoiceField(
        choices=['critical', 'high', 'medium', 'low'],
        default='medium',
        help_text="Priority level"
    )
    options = InlineSuggestionSerializer(many=True, default=list)
    default = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Default value if user doesn't respond"
    )


class ProgressiveRefinementSerializer(serializers.Serializer):
    """
    Serializer for progressive refinement state.

    Tracks resolved fields, pending clarifications, and inline suggestions
    to enable the pipeline to proceed with partial information.
    """

    status = serializers.ChoiceField(
        choices=['ready', 'needs_clarification'],
        help_text="Current refinement status"
    )
    confidence = serializers.IntegerField(
        min_value=0, max_value=100,
        help_text="Overall confidence percentage"
    )
    can_proceed = serializers.BooleanField(
        help_text="Whether pipeline can proceed with current state"
    )
    resolved_fields = serializers.DictField(
        required=False, default=dict,
        help_text="Fields that have been resolved with values"
    )
    auto_selected_defaults = serializers.DictField(
        required=False, default=dict,
        help_text="Defaults that were auto-selected based on confidence"
    )
    inline_suggestions = InlineSuggestionSerializer(
        many=True, default=list,
        help_text="Inline suggestions for ambiguous fields"
    )
    questions = ClarificationQuestionSerializer(
        many=True, default=list,
        help_text="Clarification questions (only if confidence < 0.5)"
    )
    critical_questions = ClarificationQuestionSerializer(
        many=True, default=list,
        help_text="Critical questions that block progress"
    )


class NLPParseResponseSerializer(serializers.Serializer):
    """
    Serializer for NLP pipeline parse response.

    Supports both successful template generation and partial results
    with progressive refinement when clarification is needed.
    """

    success = serializers.BooleanField()
    status = serializers.ChoiceField(
        choices=['complete', 'needs_clarification', 'error'],
        default='complete',
        help_text="Pipeline completion status"
    )
    request_id = serializers.UUIDField()
    execution_time_seconds = serializers.FloatField(required=False)

    # Template data (present when status='complete')
    template = serializers.DictField(
        required=False, allow_null=True,
        help_text="Generated template JSON"
    )
    template_id = serializers.CharField(
        required=False, allow_null=True,
        help_text="Generated template ID"
    )
    template_name = serializers.CharField(
        required=False, allow_null=True,
        help_text="Human-readable template name"
    )
    variable_schema = serializers.DictField(
        required=False, allow_null=True,
        help_text="JSON schema for template variables"
    )
    similarity_hash = serializers.CharField(
        required=False, allow_null=True,
        help_text="Hash for similarity matching"
    )

    # Classification data
    classification = serializers.DictField(
        required=False,
        help_text="Classification results (event_type, sub_event, confidence)"
    )

    # Entity data (present when status='needs_clarification')
    entities = serializers.DictField(
        required=False,
        help_text="Extracted entities (when paused for clarification)"
    )

    # Pipeline metadata
    pipeline_metadata = serializers.DictField(required=False)

    # Progressive refinement data
    progressive_refinement = ProgressiveRefinementSerializer(
        required=False,
        help_text="Progressive refinement state with suggestions and clarifications"
    )

    # Error handling
    error = serializers.CharField(
        required=False, allow_null=True,
        help_text="Error message if pipeline failed"
    )
    failed_stage = serializers.CharField(
        required=False, allow_null=True,
        help_text="Stage where pipeline failed"
    )


class ClarificationSelectionSerializer(serializers.Serializer):
    """
    Serializer for user's clarification selection input.

    Used when user selects from inline suggestions or answers questions.
    """

    request_id = serializers.UUIDField(
        help_text="Original request ID from the parse response"
    )
    selections = serializers.DictField(
        help_text="Map of field_name -> selected_value",
        child=serializers.JSONField()
    )
    force_proceed = serializers.BooleanField(
        default=False,
        help_text="Force pipeline to proceed even with unresolved clarifications"
    )


class DefaultNetworkAlertSerializer(serializers.ModelSerializer):
    """Serializer for default network alerts (system fallback)."""

    chain = serializers.CharField(source='chain.name', read_only=True)
    chain_name = serializers.CharField(source='chain.display_name', read_only=True)
    chain_symbol = serializers.CharField(source='chain.native_token', read_only=True)
    alert_template = serializers.CharField(source='alert_template.id', read_only=True)
    alert_template_name = serializers.CharField(source='alert_template.name', read_only=True)

    class Meta:
        model = DefaultNetworkAlert
        fields = [
            'id',
            'chain',
            'chain_name',
            'chain_symbol',
            'subnet',
            'alert_template',
            'alert_template_name',
            'enabled',
            'settings',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'chain',
            'chain_name',
            'chain_symbol',
            'subnet',
            'alert_template',
            'alert_template_name',
            'settings',
            'created_at',
            'updated_at',
        ]
