"""
Simplified Alert System Models
Refactored design with template system and consolidated execution tracking
"""

import uuid
import json
import logging
import re
from typing import List
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .groups import (
    GenericGroup,
    GroupType,
    AlertType,
    ALERT_TYPE_TO_GROUP_TYPE,
    normalize_network_subnet_key,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# Event Type Choices
EVENT_TYPE_CHOICES = [
    ('ACCOUNT_EVENT', 'Account Event'),
    ('ASSET_EVENT', 'Asset Event'),
    ('CONTRACT_INTERACTION', 'Contract Interaction'),
    ('PROTOCOL_EVENT', 'Protocol Event'),
    ('DEFI_EVENT', 'DeFi Event'),
    ('ANOMALY_EVENT', 'Anomaly Event'),
]

# UI-friendly template type derived from event_type.
EVENT_TYPE_TO_TEMPLATE_TYPE = {
    'ACCOUNT_EVENT': 'wallet',
    'ASSET_EVENT': 'token',
    # Blockchain protocol / network-wide events.
    'PROTOCOL_EVENT': 'network',
    # Application protocols (e.g., Aave, Uniswap) scoped to a network.
    'DEFI_EVENT': 'protocol',
    'CONTRACT_INTERACTION': 'contract',
    'ANOMALY_EVENT': 'anomaly',
}

# Targeting type derived from event_type/template_type.
# This is used to determine what kind of group/key a subscription should target.
EVENT_TYPE_TO_TARGET_ALERT_TYPE = {
    'ACCOUNT_EVENT': AlertType.WALLET,
    'ASSET_EVENT': AlertType.TOKEN,
    # Blockchain protocol events are network-scoped (e.g. blocks, reorgs).
    'PROTOCOL_EVENT': AlertType.NETWORK,
    # DeFi/application protocol events are protocol-scoped (e.g. Aave health factor).
    'DEFI_EVENT': AlertType.PROTOCOL,
    'CONTRACT_INTERACTION': AlertType.CONTRACT,
    # Anomalies are network-scoped today.
    'ANOMALY_EVENT': AlertType.NETWORK,
}

# Common Sub-Event Choices (extensible)
SUB_EVENT_CHOICES = [
    # Account Events
    ('ACCOUNT_CREATED', 'Account Created'),
    ('NATIVE_SEND', 'Native Send'),
    ('NATIVE_RECEIVE', 'Native Receive'),
    ('TOKEN_ALLOWANCE_CHANGED', 'Token Allowance Changed'),
    ('BALANCE_THRESHOLD', 'Balance Threshold'),
    ('GAS_USAGE_SPIKE', 'Gas Usage Spike'),

    # Asset Events
    ('TOKEN_MINT', 'Token Mint'),
    ('TOKEN_BURN', 'Token Burn'),
    ('TOKEN_TRANSFER', 'Token Transfer'),
    ('TOKEN_METADATA_UPDATE', 'Token Metadata Update'),

    # Contract Interactions
    ('DEPOSIT', 'Deposit'),
    ('WITHDRAW', 'Withdraw'),
    ('BORROW', 'Borrow'),
    ('REPAY', 'Repay'),
    ('LIQUIDATION', 'Liquidation'),
    ('SWAP', 'Swap'),
    ('ADD_LIQUIDITY', 'Add Liquidity'),
    ('REMOVE_LIQUIDITY', 'Remove Liquidity'),

    # Protocol Events
    ('BLOCK_PRODUCED', 'Block Produced'),
    ('CHAIN_REORG', 'Chain Reorg'),
    ('VALIDATOR_SLASHED', 'Validator Slashed'),

    # Anomaly Events
    ('LARGE_TRANSFER_OUTLIER', 'Large Transfer Outlier'),
    ('PRIVILEGED_FUNCTION_CALLED', 'Privileged Function Called'),

    # Custom
    ('CUSTOM', 'Custom'),
]

# Priority Choices
PRIORITY_CHOICES = [
    ('high', 'High'),
    ('normal', 'Normal'),
    ('low', 'Low'),
]

# Trigger Mode Choices
TRIGGER_MODE_CHOICES = [
    ('event', 'Event'),
    ('schedule', 'Schedule'),
]

# Template Source Choices
SOURCE_CHOICES = [
    ('manual', 'Manual'),
    ('nlp_generated', 'NLP Generated'),
    ('system', 'System Default'),
]


def render_template_spec(template_spec: dict, params: dict) -> dict:
    """
    Render template placeholders with actual parameters.

    Supports {{placeholder}} syntax (Jinja2-like).

    Example:
        Template: {"threshold": "{{amount}}", "wallet": "{{address}}"}
        Params: {"amount": 1000, "address": "0x123..."}
        Result: {"threshold": 1000, "wallet": "0x123..."}

    Args:
        template_spec: Template specification with {{placeholder}} variables
        params: Dictionary of parameter values

    Returns:
        Rendered specification with placeholders replaced
    """
    try:
        # Convert spec to JSON string
        template_str = json.dumps(template_spec)

        # Replace {{placeholder}} patterns with actual values
        def replace_placeholder(match):
            placeholder = match.group(1)
            if placeholder in params:
                value = params[placeholder]
                # Return proper JSON representation
                return json.dumps(value) if not isinstance(value, str) else value
            else:
                # Keep original if not in params
                return match.group(0)

        rendered_str = re.sub(r'\{\{(\w+)\}\}', replace_placeholder, template_str)

        # Convert back to dict
        return json.loads(rendered_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error rendering template spec: {e}")
        return template_spec


# NOTE: Legacy AlertTemplate v1 has been removed.
# vNext templates are persisted in `app.models.alert_templates.AlertTemplate` and compiled into AlertExecutable.

class AlertInstance(models.Model):
    """
    User's active subscription to a template (or standalone alert).
    This represents a user's specific alert configuration, either based on a template
    or created independently.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    nl_description = models.TextField(help_text="Original user prompt or description")

    # vNext template relationship (optional - None for standalone alerts)
    template = models.ForeignKey(
        "app.AlertTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="instances",
        help_text="Pinned AlertTemplate identity for executable-backed alerts (vNext).",
    )
    template_version = models.IntegerField(
        null=True,
        blank=True,
        help_text="Pinned template_version for executable-backed alerts (vNext).",
    )
    template_params = models.JSONField(
        null=True,
        blank=True,
        help_text="Variable bindings for this alert instance (used at evaluation time)."
    )

    # Standalone alert specification (only used if template is None)
    _standalone_spec = models.JSONField(
        null=True,
        blank=True,
        help_text="Complete alert specification for standalone alerts"
    )

    # Event classification (denormalized for query performance)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    sub_event = models.CharField(max_length=50, choices=SUB_EVENT_CHOICES)
    sub_event_confidence = models.FloatField(
        default=1.0,
        help_text="Confidence score for sub-event classification"
    )
    sub_event_proposed = models.CharField(
        max_length=50,
        blank=True,
        help_text="Proposed sub-event if confidence < 0.8"
    )

    # State
    enabled = models.BooleanField(default=True)
    version = models.IntegerField(default=1)

    # NLP Processing Status (for async NL processing)
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pending'),        # Just created, waiting for NLP
        ('processing', 'Processing'),  # NLP is working on it
        ('completed', 'Completed'),    # NLP finished successfully
        ('failed', 'Failed'),          # NLP processing failed
        ('skipped', 'Skipped'),        # No NLP processing needed (template-based)
    ]
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS_CHOICES,
        default='skipped',
        help_text="NLP processing status for NL-to-spec conversion"
    )
    processing_error = models.TextField(
        blank=True,
        help_text="Error message if NLP processing failed"
    )

    # Trigger configuration for AlertJob creation
    trigger_type = models.CharField(
        max_length=20,
        choices=[
            ('event_driven', 'Event-Driven'),
            ('one_time', 'One-Time'),
            ('periodic', 'Periodic')
        ],
        default='event_driven',
        help_text="Determines how AlertJobs are created for this alert"
    )
    trigger_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="""Configuration for job creation based on trigger_type:
        event_driven: {"chains": ["ethereum"], "event_types": ["transfer"]} - created by blockchain actors
        one_time: {"reset_allowed": true} - created once by Alert Scheduler Provider
        periodic: {"interval_seconds": 300, "schedule": "*/5 * * * *"} - created on schedule by provider"""
    )

    # Job creation tracking (managed by actors/provider)
    last_job_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last AlertJob creation (used for periodic scheduling)"
    )
    job_creation_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of AlertJobs created for this alert (debugging/analytics)"
    )

    # Alert Type and Target Group (Unified Group Model integration)
    alert_type = models.CharField(
        max_length=20,
        choices=AlertType.choices,
        default=AlertType.WALLET,
        help_text="Type of alert: wallet, network, or token - determines valid target types"
    )
    target_group = models.ForeignKey(
        GenericGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='alert_instances',
        help_text="Optional: Target group (wallet/network/token group) for this alert"
    )

    # Individual target keys for fine-grained targeting
    # When set, overrides target_group for targeting resolution
    target_keys = models.JSONField(
        default=list,
        blank=True,
        help_text='''Individual target keys for fine-grained targeting.
        Format: ["ETH:mainnet:0x123...", "SOL:mainnet:ABC..."]

        Targeting Resolution:
        1. If target_keys is set → use individual keys (specific wallets)
        2. Else if target_group is set → use all members in group
        3. Else → alert applies globally (based on spec.scope)
        '''
    )

    # If set, this alert instance was materialized from a GroupSubscription
    # (used for AlertGroup template subscriptions that clone instances per subscriber)
    source_subscription = models.ForeignKey(
        'app.GroupSubscription',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='alert_instances',
        help_text="If set, this alert was created/managed by a GroupSubscription"
    )
    disabled_by_subscription = models.BooleanField(
        default=False,
        help_text="True if this alert was disabled by its GroupSubscription (not a user override)."
    )

    # Ownership
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alert_instances')
    author = models.CharField(max_length=42, blank=True, help_text="Blockchain address of author")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'alert_instances'
        verbose_name = 'Alert Instance'
        verbose_name_plural = 'Alert Instances'
        unique_together = ['id', 'version']
        indexes = [
            models.Index(fields=['user', 'enabled']),
            models.Index(fields=['event_type', 'sub_event']),
            models.Index(fields=['template']),
            models.Index(fields=['created_at']),
            models.Index(fields=['version']),
            models.Index(fields=['trigger_type', 'enabled']),  # For actor/provider queries
            models.Index(fields=['processing_status']),  # For NLP processing queries
            models.Index(fields=['alert_type', 'enabled']),  # For unified group queries
            models.Index(fields=['target_group', 'enabled']),  # For group-based lookups
            GinIndex(fields=['target_keys'], name='alert_instance_target_keys_gin'),  # For individual targeting
        ]

    def __str__(self):
        return f"{self.name} (v{self.version})"

    @property
    def spec(self) -> dict:
        """
        Dynamically compute alert specification.

        For template-based alerts: renders template with parameters
        For standalone alerts: returns the stored specification

        Returns:
            Complete alert specification dictionary
        """
        if self.template is not None and self.template_version is not None:
            # Executable-backed alerts execute via pinned AlertExecutable, not legacy spec.
            return {}
        elif self._standalone_spec:
            # Standalone alert: return stored spec
            return self._standalone_spec
        else:
            # Fallback: empty spec
            logger.warning(f"Alert instance {self.id} has no valid spec configuration")
            return {}

    def validate_spec_completeness(self):
        """Validate that either template+params or standalone spec is provided"""
        # Use is not None for template_params since {} is valid for NLP-generated alerts
        has_template = (
            self.template is not None
            and self.template_version is not None
            and self.template_params is not None
        )
        has_standalone = self._standalone_spec

        if not has_template and not has_standalone:
            raise ValidationError(
                "Alert instance must have either (template + template_version + template_params) or _standalone_spec"
            )

        if sum([bool(has_template), bool(has_standalone)]) > 1:
            raise ValidationError(
                "Alert instance cannot have multiple spec sources configured"
            )

    def validate_spec_structure(self):
        """Validate AlertTemplateIR v1 spec structure."""
        if self.template is not None and self.template_version is not None:
            # vNext executable-backed alerts do not store a legacy v1 spec in Django.
            return
        spec = self.spec
        if not isinstance(spec, dict) or not spec:
            raise ValidationError("Alert spec must be a non-empty dictionary")

        if spec.get("version") != "v1":
            raise ValidationError(f"Unsupported alert spec version: {spec.get('version')}")

        required_fields = ["trigger", "conditions", "action"]
        for field in required_fields:
            if field not in spec:
                raise ValidationError(f"Alert spec missing required field: {field}")

    def get_chains(self):
        """
        Get canonical network keys for this alert.

        Returns a list of `{NETWORK}:{subnet}` keys (e.g., `ETH:mainnet`).
        """
        keys: list[str] = []

        if self.target_keys:
            for raw in self.target_keys:
                if not isinstance(raw, str):
                    continue
                parts = [p.strip() for p in raw.split(":")]
                if len(parts) < 2:
                    continue
                keys.append(normalize_network_subnet_key(f"{parts[0]}:{parts[1]}"))

        if not keys and self.template_id and self.template_version:
            # Template-v2 scope is stored in the pinned template_spec bundle.
            try:
                from app.models.alert_templates import AlertTemplateVersion

                tmpl_ver = AlertTemplateVersion.objects.filter(
                    template_id=self.template_id,
                    template_version=int(self.template_version),
                ).first()
                spec = tmpl_ver.template_spec if tmpl_ver is not None and isinstance(tmpl_ver.template_spec, dict) else {}
                scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
                networks = scope.get("networks")
                if isinstance(networks, list):
                    for n in networks:
                        if isinstance(n, str) and n.strip():
                            keys.append(normalize_network_subnet_key(n.strip()))
            except Exception:
                # Best-effort only; chain derivation should not break list endpoints.
                pass

        return sorted(set(keys))

    def get_addresses(self):
        """Get address strings derived from explicit target_keys (if present)."""
        addresses: list[str] = []
        if not self.target_keys:
            return addresses

        for raw in self.target_keys:
            if not isinstance(raw, str):
                continue
            parts = [p.strip() for p in raw.split(":")]
            if len(parts) < 3:
                continue
            addresses.append(parts[2])

        # Preserve order but remove duplicates
        deduped: list[str] = []
        seen: set[str] = set()
        for addr in addresses:
            key = addr.lower() if addr.lower().startswith("0x") else addr
            if key in seen:
                continue
            seen.add(key)
            deduped.append(addr)
        return deduped

    def get_trigger_mode(self):
        """Get legacy trigger mode label for API clients."""
        mapping = {
            "event_driven": "event",
            "periodic": "schedule",
            "one_time": "one_time",
        }
        return mapping.get(self.trigger_type, "event")

    def get_priority(self):
        """Get alert priority from trigger_config (defaults to 'normal')."""
        if isinstance(self.trigger_config, dict):
            value = self.trigger_config.get("priority")
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return "normal"

    def validate_target_group_type(self):
        """
        Validate that target_group type matches alert_type.

        Alert types map to valid group types:
        - wallet alerts → wallet groups
        - network alerts → network groups
        - token alerts → token groups
        """
        if not self.target_group:
            return  # No target group is valid

        valid_group_types = ALERT_TYPE_TO_GROUP_TYPE.get(self.alert_type, [])

        if self.target_group.group_type not in valid_group_types:
            valid_types_str = ', '.join(valid_group_types)
            raise ValidationError({
                'target_group': f"Alert type '{self.alert_type}' requires target group of type "
                               f"[{valid_types_str}], but got '{self.target_group.group_type}'"
            })

    def validate_target_keys_format(self):
        """
        Validate target_keys format based on alert_type.

        Key formats:
        - wallet: {network}:{subnet}:{address} (e.g., ETH:mainnet:0x123...)
        - network: {network}:{subnet} (e.g., ETH:mainnet)
        - protocol: {network}:{subnet}:{protocol} (e.g., ETH:mainnet:aave)
        - token: {network}:{subnet}:{contract} (e.g., ETH:mainnet:0xUSDC...)
        """
        if not self.target_keys:
            return

        if not isinstance(self.target_keys, list):
            raise ValidationError({
                'target_keys': "target_keys must be a list of strings"
            })

        for i, key in enumerate(self.target_keys):
            if not isinstance(key, str):
                raise ValidationError({
                    'target_keys': f"target_keys[{i}] must be a string, got {type(key).__name__}"
                })

            parts = key.split(':')

            # Validate based on alert_type
            if self.alert_type == AlertType.NETWORK:
                # Network keys: {network}:{subnet}
                if len(parts) < 2:
                    raise ValidationError({
                        'target_keys': f"Network key '{key}' must be in format 'network:subnet' "
                                       f"(e.g., 'ETH:mainnet')"
                    })
            elif self.alert_type == AlertType.PROTOCOL:
                # Protocol keys: {network}:{subnet}:{protocol}
                if len(parts) < 3:
                    raise ValidationError({
                        'target_keys': f"Protocol key '{key}' must be in format 'network:subnet:protocol' "
                                       f"(e.g., 'ETH:mainnet:aave')"
                    })
            else:
                # Wallet and token keys: {network}:{subnet}:{address}
                if len(parts) < 3:
                    raise ValidationError({
                        'target_keys': f"Key '{key}' must be in format 'network:subnet:address' "
                                       f"(e.g., 'ETH:mainnet:0x123...')"
                    })

    def get_effective_targets(self) -> List[str]:
        """
        Get all targets for this alert.

        Targeting Resolution:
        1. If target_keys is set → use individual keys (specific wallets)
        2. Else if target_group is set → use all members in group
        3. Else → empty list (alert applies globally based on spec.scope)

        Returns:
            List of target keys (e.g., ["ETH:mainnet:0x123...", ...])
        """
        if self.target_keys:
            return self.target_keys
        elif self.target_group:
            return self.target_group.get_member_keys()
        return []

    def has_explicit_targets(self) -> bool:
        """Check if alert has explicit targets (either keys or group)."""
        return bool(self.target_keys) or self.target_group is not None

    def clean(self):
        """Validate alert instance"""
        super().clean()
        self.validate_spec_completeness()
        if self.spec:
            self.validate_spec_structure()
        self.validate_target_group_type()
        self.validate_target_keys_format()

        # Enforce a single targeting mechanism to avoid double-indexing:
        # an alert instance must target either a group or explicit keys, but not both.
        if self.target_group and self.target_keys:
            raise ValidationError({
                'target_group': "Cannot set target_group when target_keys are provided",
                'target_keys': "Cannot set target_keys when target_group is provided",
            })

    @classmethod
    def get_latest_versions(cls, user=None):
        """Get latest version of each alert instance"""
        queryset = cls.objects.values('id').annotate(
            latest_version=models.Max('version')
        )

        if user:
            queryset = queryset.filter(user=user)

        # Get the actual alert objects
        latest_alerts = []
        for item in queryset:
            alert = cls.objects.get(
                id=item['id'],
                version=item['latest_version']
            )
            latest_alerts.append(alert)

        return latest_alerts


class AlertExecution(models.Model):
    """
    Consolidated model for alert execution tracking.
    Combines job queuing, execution runs, and retry logic into a single model.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alert_instance = models.ForeignKey(AlertInstance, on_delete=models.CASCADE, related_name='executions')
    alert_version = models.IntegerField(help_text="Version of alert at execution time")

    # Execution context
    trigger_mode = models.CharField(max_length=20, choices=TRIGGER_MODE_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')

    # Retry tracking (consolidated from JobRun)
    attempt_number = models.IntegerField(default=1, help_text="Retry attempt number (1, 2, 3...)")
    max_retries = models.IntegerField(default=3, help_text="Maximum retry attempts")

    # Status lifecycle
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')

    # Frozen execution context (for versioning safety)
    frozen_spec = models.JSONField(help_text="Alert spec frozen at execution time")
    execution_context = models.JSONField(
        null=True,
        blank=True,
        help_text="Event data, block number, timestamp, etc."
    )

    # Execution details (from NATS)
    execution_id = models.CharField(max_length=255, blank=True, help_text="NATS execution ID")

    # Results
    result = models.BooleanField(null=True, blank=True, help_text="Alert condition result (True/False)")
    result_value = models.CharField(max_length=255, blank=True, help_text="Actual value that triggered alert")
    result_metadata = models.JSONField(null=True, blank=True, help_text="Additional result context")

    # Performance metrics
    execution_time_ms = models.IntegerField(null=True, blank=True)
    rows_processed = models.IntegerField(null=True, blank=True)
    data_sources_used = models.JSONField(default=list, help_text="Data sources accessed during execution")

    # Error handling
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(null=True, blank=True)

    # Timing
    queued_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField(null=True, blank=True, help_text="When job should execute")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'alert_executions'
        verbose_name = 'Alert Execution'
        verbose_name_plural = 'Alert Executions'
        indexes = [
            models.Index(fields=['alert_instance', 'alert_version']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['trigger_mode']),
            models.Index(fields=['queued_at']),
            models.Index(fields=['started_at']),
            models.Index(fields=['due_at']),
            models.Index(fields=['result']),
        ]

    def __str__(self):
        return f"{self.alert_instance.name} execution {self.execution_id or self.id} (attempt {self.attempt_number})"

    def mark_started(self):
        """Mark execution as started"""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])

    def mark_completed(self, result_data=None):
        """Mark execution as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if result_data:
            self.result = result_data.get('result')
            self.result_value = result_data.get('result_value', '')
            self.result_metadata = result_data.get('metadata')
        self.save(update_fields=['status', 'completed_at', 'result', 'result_value', 'result_metadata', 'updated_at'])

    def mark_failed(self, error_message, error_details=None):
        """Mark execution as failed"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.error_details = error_details
        self.save(update_fields=['status', 'completed_at', 'error_message', 'error_details', 'updated_at'])

    def should_retry(self) -> bool:
        """Check if execution should be retried"""
        return self.status == 'failed' and self.attempt_number < self.max_retries

    def create_retry(self):
        """Create a retry execution"""
        if not self.should_retry():
            return None

        retry = AlertExecution.objects.create(
            alert_instance=self.alert_instance,
            alert_version=self.alert_version,
            trigger_mode=self.trigger_mode,
            priority=self.priority,
            attempt_number=self.attempt_number + 1,
            max_retries=self.max_retries,
            frozen_spec=self.frozen_spec,
            execution_context=self.execution_context,
            due_at=timezone.now() + timezone.timedelta(minutes=self.attempt_number * 5)  # Exponential backoff
        )
        return retry

    @property
    def execution_time(self):
        """Get execution time in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_retry(self):
        """Check if this is a retry attempt"""
        return self.attempt_number > 1


class AlertChangeLog(models.Model):
    """
    Audit trail for alert instance changes.
    Tracks all modifications to alert instances for compliance and debugging.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alert_instance = models.ForeignKey(AlertInstance, on_delete=models.CASCADE, related_name='change_logs')

    # Version tracking
    from_version = models.IntegerField(null=True, blank=True, help_text="NULL for creation")
    to_version = models.IntegerField()

    # Change details
    CHANGE_TYPE_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('enabled', 'Enabled'),
        ('disabled', 'Disabled'),
        ('template_instantiated', 'Template Instantiated'),
        ('params_updated', 'Parameters Updated'),
    ]
    change_type = models.CharField(max_length=25, choices=CHANGE_TYPE_CHOICES)
    changed_fields = models.JSONField(help_text="List of field names that changed")
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField()

    # Change metadata
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    change_reason = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alert_change_logs'
        verbose_name = 'Alert Change Log'
        verbose_name_plural = 'Alert Change Logs'
        indexes = [
            models.Index(fields=['alert_instance', 'to_version']),
            models.Index(fields=['created_at']),
            models.Index(fields=['change_type']),
        ]

    def __str__(self):
        return f"{self.alert_instance.name} - {self.change_type} (v{self.from_version} → v{self.to_version})"


# ===================================================================
# Django Signals for Redis Cache Management
# ===================================================================

@receiver(post_save, sender=AlertInstance)
def update_subscription_index_on_instance_save(sender, instance, created, **kwargs):
    """
    Update Redis subscription index when AlertInstance is created.

    When a user creates a new alert based on a template, we add them to the
    template's subscriber set in Redis for efficient notification routing.

    Args:
        sender: The model class (AlertInstance)
        instance: The AlertInstance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    if instance.template_id:
        try:
            from app.services.notification_cache import NotificationCacheManager
            cache_manager = NotificationCacheManager()

            has_enabled_instance = AlertInstance.objects.filter(
                template_id=instance.template_id,
                user_id=instance.user_id,
                enabled=True,
            ).exists()

            if has_enabled_instance:
                cache_manager.add_subscriber_to_template(
                    str(instance.template_id),
                    str(instance.user_id)
                )
                logger.info(
                    f"Ensured user {instance.user_id} is subscribed to template {instance.template_id} "
                    f"(alert instance: {instance.id}, enabled={instance.enabled})"
                )
            else:
                cache_manager.remove_subscriber_from_template(
                    str(instance.template_id),
                    str(instance.user_id)
                )
                logger.info(
                    f"Ensured user {instance.user_id} is unsubscribed from template {instance.template_id} "
                    f"(alert instance: {instance.id}, enabled={instance.enabled})"
                )
        except Exception as e:
            # Signal handlers should NOT raise exceptions that break model operations
            logger.error(
                f"Error updating subscription index for alert instance {instance.id}: {e}"
            )


@receiver(post_delete, sender=AlertInstance)
def update_subscription_index_on_instance_delete(sender, instance, **kwargs):
    """
    Update Redis subscription index when AlertInstance is deleted.

    When an alert instance is deleted, we check if the user has any other instances
    for the same template. If not, remove them from the subscription index.

    Args:
        sender: The model class (AlertInstance)
        instance: The AlertInstance being deleted
        **kwargs: Additional signal arguments
    """
    if instance.template_id:
        try:
            # Check if user has any other alert instances for this template
            has_other_instances = AlertInstance.objects.filter(
                template_id=instance.template_id,
                user_id=instance.user_id,
                enabled=True,
            ).exclude(id=instance.id).exists()

            # Only remove from subscription index if no other instances exist
            if not has_other_instances:
                from app.services.notification_cache import NotificationCacheManager
                cache_manager = NotificationCacheManager()
                cache_manager.remove_subscriber_from_template(
                    str(instance.template_id),
                    str(instance.user_id)
                )
                logger.info(
                    f"Removed user {instance.user_id} from template {instance.template_id} "
                    f"subscription index (last instance deleted: {instance.id})"
                )
        except Exception as e:
            # Signal handlers should NOT raise exceptions that break model operations
            logger.error(
                f"Error updating subscription index when deleting alert instance {instance.id}: {e}"
            )


@receiver(post_save, sender=AlertInstance)
def increment_template_usage_count(sender, instance, created, **kwargs):
    """
    Increment template usage count when a new instance is created.

    Args:
        sender: The model class (AlertInstance)
        instance: The AlertInstance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    if created and instance.template:
        try:
            instance.template.increment_usage()
            logger.info(
                f"Incremented usage count for template {instance.template_id} "
                f"(new instance: {instance.id})"
            )
        except Exception as e:
            logger.error(
                f"Error incrementing template usage count for instance {instance.id}: {e}"
            )


# ===================================================================
# Default Network Alert Model
# ===================================================================

class DefaultNetworkAlert(models.Model):
    """
    System-managed default "All Transactions" alert per network/subnet.

    Created for each Chain+SubChain combination. Used as FALLBACK ONLY -
    applied when user subscribes to a WalletGroup WITHOUT specifying their
    own alerts. NOT auto-applied.

    Usage Flow:
    1. System creates DefaultNetworkAlert for each chain+subnet (e.g., ETH+mainnet)
    2. Each DefaultNetworkAlert links to an AlertTemplate (type: ALL_TRANSACTIONS)
    3. When user creates AlertInstance without template:
       - Service layer looks up DefaultNetworkAlert for the chain
       - Uses the linked alert_template as the fallback
    4. User can always override by specifying their own template

    Example:
        ethereum_mainnet_default = DefaultNetworkAlert.objects.get(
            chain__symbol='ETH',
            subnet='mainnet'
        )
        fallback_template = ethereum_mainnet_default.alert_template
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Network identification - uses string reference to avoid circular import
    # Chain model is in blockchain.models
    chain = models.ForeignKey(
        'blockchain.Chain',
        on_delete=models.CASCADE,
        related_name='default_alerts',
        help_text="The blockchain chain (e.g., Ethereum, Solana)"
    )
    subnet = models.CharField(
        max_length=50,
        default='mainnet',
        help_text="Network subnet (mainnet, testnet, etc.)"
    )

    # Link to system AlertTemplate (type: ALL_TRANSACTIONS)
    alert_template = models.OneToOneField(
        "app.AlertTemplate",
        on_delete=models.PROTECT,
        related_name='default_network_alert',
        help_text="The fallback AlertTemplate for 'All Transactions' alerts"
    )

    # Configuration
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this default alert is active"
    )
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="""Default settings applied to alerts using this template:
        {
            "default_priority": "normal",
            "cooldown_minutes": 5,
            "max_notifications_per_hour": 100
        }"""
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'default_network_alerts'
        verbose_name = 'Default Network Alert'
        verbose_name_plural = 'Default Network Alerts'
        unique_together = ['chain', 'subnet']
        indexes = [
            models.Index(fields=['chain', 'subnet']),
            models.Index(fields=['enabled']),
        ]

    def __str__(self):
        return f"Default Alert: {self.chain.display_name} ({self.subnet})"

    def clean(self):
        """Validate the model."""
        super().clean()
        # Ensure the linked template exists and is appropriate
        if self.alert_template_id:
            if not self.alert_template.is_public:
                raise ValidationError({
                    'alert_template': "Default network alert must use a public template"
                })

    @classmethod
    def get_for_chain(cls, chain_name: str, subnet: str = 'mainnet'):
        """
        Get the default alert for a specific chain and subnet.

        Args:
            chain_name: Chain name (e.g., 'ethereum', 'solana', 'bitcoin')
            subnet: Network subnet (default: 'mainnet')

        Returns:
            DefaultNetworkAlert instance or None if not found
        """
        try:
            return cls.objects.select_related('alert_template', 'chain').get(
                chain__name=chain_name,
                subnet=subnet,
                enabled=True
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_fallback_template(cls, chain_name: str, subnet: str = 'mainnet'):
        """
        Get the fallback AlertTemplate for a chain.

        Convenience method for service layer to get the template directly.

        Args:
            chain_name: Chain name (e.g., 'ethereum', 'solana', 'bitcoin')
            subnet: Network subnet (default: 'mainnet')

        Returns:
            AlertTemplate instance or None if not found
        """
        default_alert = cls.get_for_chain(chain_name, subnet)
        return default_alert.alert_template if default_alert else None
