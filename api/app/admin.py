"""
Django Admin Configuration for Alert Models
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
import json

# Unfold admin imports
from unfold.admin import ModelAdmin, TabularInline, StackedInline

from .models.alerts import (
    AlertInstance, AlertChangeLog, AlertExecution,
    DefaultNetworkAlert
)
from .models.alert_templates import AlertTemplate, AlertTemplateVersion
from .models.groups import (
    GenericGroup, GroupSubscription, UserWalletGroup
)
from .models.blockchain import BlockchainNode
from .models.nlp import NLPPipeline, NLPPipelineVersion


class AlertExecutionInline(TabularInline):
    """Inline admin for Alert Executions"""
    model = AlertExecution
    extra = 0
    readonly_fields = ['started_at', 'completed_at', 'status', 'attempt_number']
    fields = ['attempt_number', 'status', 'result', 'started_at', 'completed_at']

    def has_add_permission(self, request, obj=None):
        return False  # Executions are created automatically


class AlertChangeLogInline(TabularInline):
    """Inline admin for Alert Change Logs"""
    model = AlertChangeLog
    extra = 0
    readonly_fields = ['created_at', 'changed_by', 'change_type', 'from_version', 'to_version']
    fields = ['change_type', 'from_version', 'to_version', 'changed_by', 'created_at']

    def has_add_permission(self, request, obj=None):
        return False  # Change logs are auto-generated


class AlertTemplateVersionInline(TabularInline):
    """Inline admin for AlertTemplate versions (vNext)."""

    model = AlertTemplateVersion
    extra = 0
    can_delete = False
    readonly_fields = [
        "template_version",
        "spec_hash",
        "executable_id",
        "registry_snapshot_kind",
        "registry_snapshot_version",
        "registry_snapshot_hash",
        "created_at",
    ]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False  # Versions are created via the API save flow.


@admin.register(AlertTemplate)
class AlertTemplateAdmin(ModelAdmin):
    """Admin for Alert Templates (vNext)."""
    list_display = [
        "name",
        "target_kind",
        "fingerprint_short",
        "is_public",
        "is_verified",
        "created_by",
        "latest_version",
        "created_at",
    ]
    list_filter = ["is_public", "is_verified", "target_kind", "created_at"]
    search_fields = ["name", "description", "fingerprint", "created_by__email"]
    readonly_fields = ["created_at", "updated_at", "fingerprint"]
    ordering = ["-created_at"]
    inlines = [AlertTemplateVersionInline]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "description", "created_by", "target_kind", "fingerprint")},
        ),
        ("Publishing", {"fields": ("is_public", "is_verified")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def fingerprint_short(self, obj):
        if not obj.fingerprint:
            return ""
        if obj.fingerprint.startswith("sha256:"):
            return obj.fingerprint[:14] + "..." + obj.fingerprint[-6:]
        return obj.fingerprint[:8] + "..." + obj.fingerprint[-6:]

    fingerprint_short.short_description = "Fingerprint"

    def latest_version(self, obj):
        latest = obj.versions.order_by("-template_version").only("template_version").first()
        return latest.template_version if latest else "-"

    latest_version.short_description = "Latest Version"

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("created_by")


@admin.register(AlertInstance)
class AlertInstanceAdmin(ModelAdmin):
    """Admin for Alert Instances - User subscriptions to alerts"""
    list_display = [
        'name', 'version', 'user', 'enabled', 'event_type', 'sub_event',
        'template_name', 'has_executions', 'created_at'
    ]
    list_filter = ['enabled', 'version', 'event_type', 'sub_event', 'created_at', 'template']
    search_fields = ['name', 'nl_description', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at', 'nl_description_preview', 'spec_preview']
    ordering = ['-created_at', '-version']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'nl_description', 'nl_description_preview', 'version', 'enabled', 'user', 'author')
        }),
        ('Event Classification', {
            'fields': ('event_type', 'sub_event', 'sub_event_confidence', 'sub_event_proposed')
        }),
        ('Template Configuration', {
            'fields': ('template', 'template_params'),
            'description': 'Template-based alert configuration (leave empty for standalone)'
        }),
        ('Standalone Configuration', {
            'fields': ('_standalone_spec',),
            'description': 'For standalone alerts without templates',
            'classes': ('collapse',)
        }),
        ('Computed Specification', {
            'fields': ('spec_preview',),
            'description': 'Computed spec from template + params or standalone spec'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [AlertExecutionInline, AlertChangeLogInline]

    def spec_preview(self, obj):
        """Show a preview of the computed alert specification"""
        spec = obj.spec
        if not spec:
            return "No specification"

        try:
            formatted = json.dumps(spec, indent=2)
            if len(formatted) > 500:
                formatted = formatted[:500] + "..."
            return format_html('<pre style="white-space: pre-wrap;">{}</pre>', formatted)
        except:
            return "Invalid JSON"
    spec_preview.short_description = 'Computed Spec Preview'

    def nl_description_preview(self, obj):
        """Show a preview of the natural language description"""
        if len(obj.nl_description) > 100:
            return obj.nl_description[:100] + "..."
        return obj.nl_description
    nl_description_preview.short_description = 'Description Preview'

    def template_name(self, obj):
        """Display template name"""
        if obj.template:
            return obj.template.name
        return "Standalone"
    template_name.short_description = 'Template'

    def has_executions(self, obj):
        """Check if alert has any executions"""
        return obj.executions.exists()
    has_executions.boolean = True
    has_executions.short_description = 'Has Executions'

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user', 'template')


@admin.register(AlertChangeLog)
class AlertChangeLogAdmin(ModelAdmin):
    """Admin for Alert Change Logs"""
    list_display = [
        'alert_instance_name', 'change_type', 'version_change', 'changed_by', 'created_at'
    ]
    list_filter = ['change_type', 'created_at', 'changed_by']
    search_fields = ['alert_instance__name', 'changed_by__email', 'change_reason']
    readonly_fields = [
        'created_at', 'changed_fields_display', 'old_values_display',
        'new_values_display'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Change Information', {
            'fields': ('alert_instance', 'change_type', 'version_change', 'changed_by', 'change_reason')
        }),
        ('Change Details', {
            'fields': ('changed_fields_display', 'old_values_display', 'new_values_display'),
            'classes': ('collapse',)
        }),
        ('Raw Data', {
            'fields': ('changed_fields', 'old_values', 'new_values'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )

    def alert_instance_name(self, obj):
        """Display alert instance name with link"""
        url = reverse('admin:app_alertinstance_change', args=[obj.alert_instance.pk])
        return format_html('<a href="{}">{}</a>', url, obj.alert_instance.name)
    alert_instance_name.short_description = 'Alert Instance'

    def version_change(self, obj):
        """Display version change"""
        if obj.from_version:
            return f"v{obj.from_version} → v{obj.to_version}"
        return f"Created v{obj.to_version}"
    version_change.short_description = 'Version Change'

    def changed_fields_display(self, obj):
        """Display changed fields in a readable format"""
        if not obj.changed_fields:
            return "No fields changed"

        try:
            formatted = json.dumps(obj.changed_fields, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except:
            return "Invalid format"
    changed_fields_display.short_description = 'Changed Fields'

    def old_values_display(self, obj):
        """Display old values in a readable format"""
        if not obj.old_values:
            return "No old values"

        try:
            formatted = json.dumps(obj.old_values, indent=2)
            return format_html('<pre style="color: #666;">{}</pre>', formatted)
        except:
            return "Invalid format"
    old_values_display.short_description = 'Old Values'

    def new_values_display(self, obj):
        """Display new values in a readable format"""
        if not obj.new_values:
            return "No new values"

        try:
            formatted = json.dumps(obj.new_values, indent=2)
            return format_html('<pre style="color: #0a0;">{}</pre>', formatted)
        except:
            return "Invalid format"
    new_values_display.short_description = 'New Values'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('alert_instance', 'changed_by')


@admin.register(AlertExecution)
class AlertExecutionAdmin(ModelAdmin):
    """Admin for Alert Executions - Consolidated execution and retry tracking"""
    list_display = [
        'alert_instance_name', 'attempt_number', 'max_retries', 'status', 'result',
        'execution_time_ms', 'started_at', 'completed_at'
    ]
    list_filter = ['status', 'result', 'started_at', 'attempt_number']
    search_fields = ['alert_instance__name', 'error_message']
    readonly_fields = [
        'started_at', 'created_at', 'updated_at', 'frozen_spec_display',
        'result_metadata_display', 'result_data_display', 'error_details_display'
    ]
    ordering = ['-started_at']

    fieldsets = (
        ('Execution Information', {
            'fields': ('alert_instance', 'attempt_number', 'max_retries', 'status')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'execution_time_ms')
        }),
        ('Frozen Specification', {
            'fields': ('frozen_spec_display', 'frozen_spec'),
            'description': 'Alert spec frozen at execution time for version safety',
            'classes': ('collapse',)
        }),
        ('Results', {
            'fields': ('result', 'result_data_display', 'result_data', 'result_metadata_display', 'result_metadata')
        }),
        ('Performance', {
            'fields': ('rows_processed', 'data_sources_used'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message', 'error_details_display', 'error_details'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def alert_instance_name(self, obj):
        """Display alert instance name with link"""
        url = reverse('admin:app_alertinstance_change', args=[obj.alert_instance.pk])
        return format_html('<a href="{}">{}</a>', url, obj.alert_instance.name)
    alert_instance_name.short_description = 'Alert Instance'

    def frozen_spec_display(self, obj):
        """Display frozen spec in a readable format"""
        if not obj.frozen_spec:
            return "No frozen spec"

        try:
            formatted = json.dumps(obj.frozen_spec, indent=2)
            if len(formatted) > 500:
                formatted = formatted[:500] + "..."
            return format_html('<pre style="background: #f0f0f0; padding: 10px;">{}</pre>', formatted)
        except:
            return "Invalid format"
    frozen_spec_display.short_description = 'Frozen Spec'

    def result_data_display(self, obj):
        """Display result data in a readable format"""
        if not obj.result_data:
            return "No result data"

        try:
            formatted = json.dumps(obj.result_data, indent=2)
            if len(formatted) > 500:
                formatted = formatted[:500] + "..."
            return format_html('<pre>{}</pre>', formatted)
        except:
            return "Invalid format"
    result_data_display.short_description = 'Result Data'

    def result_metadata_display(self, obj):
        """Display result metadata in a readable format"""
        if not obj.result_metadata:
            return "No metadata"

        try:
            formatted = json.dumps(obj.result_metadata, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except:
            return "Invalid format"
    result_metadata_display.short_description = 'Result Metadata'

    def error_details_display(self, obj):
        """Display error details in a readable format"""
        if not obj.error_details:
            return "No error details"

        try:
            formatted = json.dumps(obj.error_details, indent=2)
            return format_html('<pre style="color: red;">{}</pre>', formatted)
        except:
            return "Invalid format"
    error_details_display.short_description = 'Error Details'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('alert_instance')


@admin.register(BlockchainNode)
class BlockchainNodeAdmin(ModelAdmin):
    list_display = [
        'chain_name', 'network', 'subnet', 'vm_type', 'enabled',
        'is_primary', 'health_status', 'latency_display', 'success_rate_display'
    ]
    list_filter = ['enabled', 'vm_type', 'network', 'is_primary']
    search_fields = ['chain_name', 'chain_id', 'network']
    readonly_fields = ['created_at', 'updated_at', 'last_health_check', 'health_status_detail']
    ordering = ['network', 'priority']

    fieldsets = (
        ('Basic Information', {
            'fields': ('chain_id', 'chain_name', 'network', 'subnet', 'vm_type')
        }),
        ('Connection Details', {
            'fields': ('rpc_url', 'ws_url'),
            'description': 'RPC and WebSocket URLs for node connection'
        }),
        ('Configuration', {
            'fields': ('enabled', 'is_primary', 'priority')
        }),
        ('Health Metrics', {
            'fields': ('latency_ms', 'success_rate', 'last_health_check', 'health_status_detail'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['enable_nodes', 'disable_nodes', 'run_health_check', 'export_to_nats', 'sync_to_redis']

    def health_status(self, obj):
        """Display health status with visual indicator"""
        if obj.is_healthy:
            return format_html('<span style="color: {};">●</span> {}', 'green', 'Healthy')
        return format_html('<span style="color: {};">●</span> {}', 'red', 'Unhealthy')
    health_status.short_description = 'Health'

    def latency_display(self, obj):
        """Display latency with color coding"""
        if not obj.latency_ms:
            return '-'

        color = 'green'
        if obj.latency_ms > 500:
            color = 'orange'
        if obj.latency_ms > 1000:
            color = 'red'

        return format_html(
            '<span style="color: {};">{} ms</span>',
            color, obj.latency_ms
        )
    latency_display.short_description = 'Latency'

    def success_rate_display(self, obj):
        """Display success rate with color coding"""
        if not obj.success_rate:
            return '-'

        color = 'green'
        if obj.success_rate < 95:
            color = 'orange'
        if obj.success_rate < 90:
            color = 'red'

        return format_html(
            '<span style="color: {};">{}%</span>',
            color, obj.success_rate
        )
    success_rate_display.short_description = 'Success Rate'

    def health_status_detail(self, obj):
        """Detailed health status information"""
        if not obj.last_health_check:
            return "Never checked"

        status_parts = []
        if obj.latency_ms:
            status_parts.append(f"Latency: {obj.latency_ms}ms")
        if obj.success_rate:
            status_parts.append(f"Success Rate: {obj.success_rate}%")
        status_parts.append(f"Last Check: {obj.last_health_check}")

        return format_html('<br>'.join(status_parts))
    health_status_detail.short_description = 'Health Details'

    def enable_nodes(self, request, queryset):
        """Enable selected nodes"""
        updated = queryset.update(enabled=True)
        self.message_user(request, f'{updated} nodes enabled.')
    enable_nodes.short_description = 'Enable selected nodes'

    def disable_nodes(self, request, queryset):
        """Disable selected nodes"""
        updated = queryset.update(enabled=False)
        self.message_user(request, f'{updated} nodes disabled.')
    disable_nodes.short_description = 'Disable selected nodes'

    def run_health_check(self, request, queryset):
        """Trigger health check for selected nodes"""
        # This would normally trigger an async task via NATS
        self.message_user(request, f'Health check initiated for {queryset.count()} nodes.')
    run_health_check.short_description = 'Run health check'

    def export_to_nats(self, request, queryset):
        """Export node configuration to NATS for wasmCloud actors"""
        # This would publish configuration to NATS
        configs = [node.get_connection_config() for node in queryset if node.enabled]
        self.message_user(request, f'Exported {len(configs)} node configurations to NATS.')
    export_to_nats.short_description = 'Export to NATS'

    def sync_to_redis(self, request, queryset):
        """Sync selected node configurations to Redis for wasmCloud providers"""
        from app.services.blockchain_sync_service import BlockchainSyncService

        synced = 0
        failed = 0
        skipped = 0

        for node in queryset:
            if not node.enabled:
                skipped += 1
                continue

            if BlockchainSyncService.sync_node_to_redis(node):
                synced += 1
            else:
                failed += 1

        message_parts = []
        if synced > 0:
            message_parts.append(f'{synced} synced')
        if failed > 0:
            message_parts.append(f'{failed} failed')
        if skipped > 0:
            message_parts.append(f'{skipped} skipped (disabled)')

        self.message_user(request, f'Redis sync: {", ".join(message_parts)}.')
    sync_to_redis.short_description = 'Sync to Redis (provider config)'


# ===================================================================
# Group Model Admin
# ===================================================================

@admin.register(GenericGroup)
class GenericGroupAdmin(ModelAdmin):
    """Admin for Generic Groups - Unified group model"""
    list_display = [
        'name', 'group_type', 'owner', 'member_count', 'visibility_display',
        'alert_type_display', 'created_at'
    ]
    list_filter = ['group_type', 'created_at']
    search_fields = ['name', 'description', 'owner__email']
    readonly_fields = ['created_at', 'updated_at', 'member_count', 'member_preview', 'settings_display']
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'group_type', 'owner')
        }),
        ('Settings', {
            'fields': ('settings', 'settings_display'),
            'description': 'Group-specific settings (visibility, alert_type, etc.)'
        }),
        ('Members', {
            'fields': ('member_count', 'member_data', 'member_preview'),
            'description': 'Group members in JSONB format'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def visibility_display(self, obj):
        """Display visibility setting"""
        visibility = obj.get_visibility()
        if visibility == 'public':
            return format_html('<span style="color: {};">{}</span>', 'green', 'Public')
        return format_html('<span style="color: {};">{}</span>', 'gray', 'Private')
    visibility_display.short_description = 'Visibility'

    def alert_type_display(self, obj):
        """Display alert_type for AlertGroups"""
        alert_type = obj.get_alert_type()
        if alert_type:
            return alert_type
        return '-'
    alert_type_display.short_description = 'Alert Type'

    def settings_display(self, obj):
        """Display settings in readable format"""
        if not obj.settings:
            return "No settings"
        try:
            formatted = json.dumps(obj.settings, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except:
            return "Invalid format"
    settings_display.short_description = 'Settings Preview'

    def member_preview(self, obj):
        """Show a preview of member data"""
        members = obj.member_data.get('members', {})
        if not members:
            return "No members"

        preview_keys = list(members.keys())[:5]
        preview_text = '\n'.join(preview_keys)
        if len(members) > 5:
            preview_text += f'\n... and {len(members) - 5} more'
        return format_html('<pre>{}</pre>', preview_text)
    member_preview.short_description = 'Members Preview'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('owner')


@admin.register(GroupSubscription)
class GroupSubscriptionAdmin(ModelAdmin):
    """Admin for Group Subscriptions - Links AlertGroups to target groups"""
    list_display = [
        'subscription_display', 'owner', 'is_active', 'alert_type_display',
        'target_type_display', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['alert_group__name', 'target_group__name', 'target_key', 'owner__email']
    readonly_fields = ['created_at', 'updated_at', 'settings_display']
    ordering = ['-created_at']

    fieldsets = (
        ('Subscription Details', {
            'fields': ('alert_group', 'target_group', 'target_key', 'owner', 'is_active')
        }),
        ('Settings Override', {
            'fields': ('settings', 'settings_display'),
            'description': 'Override settings for this subscription'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def subscription_display(self, obj):
        """Display subscription as arrow notation"""
        target = obj.target_group.name if obj.target_group else (obj.target_key or "<missing target>")
        return f"{obj.alert_group.name} → {target}"
    subscription_display.short_description = 'Subscription'

    def alert_type_display(self, obj):
        """Display alert type from alert group"""
        alert_type = obj.alert_group.get_alert_type() if obj.alert_group else None
        return alert_type or '-'
    alert_type_display.short_description = 'Alert Type'

    def target_type_display(self, obj):
        """Display target group type"""
        if obj.target_group:
            return obj.target_group.group_type
        return obj.alert_group.get_alert_type() if obj.alert_group else '-'
    target_type_display.short_description = 'Target Type'

    def settings_display(self, obj):
        """Display settings in readable format"""
        if not obj.settings:
            return "No overrides"
        try:
            formatted = json.dumps(obj.settings, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except:
            return "Invalid format"
    settings_display.short_description = 'Settings Preview'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'alert_group', 'target_group', 'owner'
        )


@admin.register(DefaultNetworkAlert)
class DefaultNetworkAlertAdmin(ModelAdmin):
    """Admin for Default Network Alerts - Fallback alerts per chain/subnet"""
    list_display = [
        'chain_display', 'subnet', 'alert_template', 'enabled', 'created_at'
    ]
    list_filter = ['enabled', 'subnet', 'created_at']
    search_fields = ['chain__name', 'chain__symbol', 'alert_template__name']
    readonly_fields = ['created_at', 'updated_at', 'settings_display']
    ordering = ['chain__name', 'subnet']

    fieldsets = (
        ('Network Identification', {
            'fields': ('chain', 'subnet')
        }),
        ('Alert Template', {
            'fields': ('alert_template', 'enabled'),
            'description': 'The fallback template for this network'
        }),
        ('Settings', {
            'fields': ('settings', 'settings_display'),
            'description': 'Default settings for alerts using this template'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def chain_display(self, obj):
        """Display chain name with symbol"""
        return f"{obj.chain.name} ({obj.chain.symbol})"
    chain_display.short_description = 'Chain'

    def settings_display(self, obj):
        """Display settings in readable format"""
        if not obj.settings:
            return "No settings"
        try:
            formatted = json.dumps(obj.settings, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except:
            return "Invalid format"
    settings_display.short_description = 'Settings Preview'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('chain', 'alert_template')


@admin.register(UserWalletGroup)
class UserWalletGroupAdmin(ModelAdmin):
    """Admin for User Wallet Groups - Provider-managed wallet associations"""
    list_display = [
        'user', 'wallet_group', 'provider', 'wallet_count_display',
        'notification_routing', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'notification_routing', 'created_at']
    search_fields = ['user__email', 'wallet_group__name', 'provider__email']
    readonly_fields = [
        'created_at', 'updated_at', 'wallet_keys_display',
        'access_control_display'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Relationships', {
            'fields': ('user', 'wallet_group', 'provider', 'callback')
        }),
        ('Wallet Keys', {
            'fields': ('wallet_keys', 'wallet_keys_display'),
            'description': 'Wallet addresses managed by the provider for this user'
        }),
        ('Notification Settings', {
            'fields': ('auto_subscribe_alerts', 'notification_routing'),
            'description': 'How notifications are routed for this user'
        }),
        ('Access Control', {
            'fields': ('access_control', 'access_control_display', 'is_active'),
            'description': 'Who can edit this membership'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def wallet_count_display(self, obj):
        """Display wallet count"""
        count = obj.get_wallet_count()
        return f"{count} wallets"
    wallet_count_display.short_description = 'Wallets'

    def wallet_keys_display(self, obj):
        """Display wallet keys preview"""
        if not obj.wallet_keys:
            return "No wallets"

        preview = obj.wallet_keys[:5]
        text = '\n'.join(preview)
        if len(obj.wallet_keys) > 5:
            text += f'\n... and {len(obj.wallet_keys) - 5} more'
        return format_html('<pre>{}</pre>', text)
    wallet_keys_display.short_description = 'Wallet Keys Preview'

    def access_control_display(self, obj):
        """Display access control in readable format"""
        if not obj.access_control:
            return "No access control set"
        try:
            formatted = json.dumps(obj.access_control, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except:
            return "Invalid format"
    access_control_display.short_description = 'Access Control Preview'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'user', 'wallet_group', 'provider', 'callback'
        )


class NLPPipelineVersionInline(TabularInline):
    model = NLPPipelineVersion
    extra = 0
    fields = [
        "version",
        "system_prompt_suffix",
        "user_prompt_context",
        "examples",
        "created_at",
        "updated_at",
    ]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(NLPPipeline)
class NLPPipelineAdmin(ModelAdmin):
    list_display = ["pipeline_id", "name", "active_version", "updated_at"]
    search_fields = ["pipeline_id", "name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [NLPPipelineVersionInline]

    fieldsets = (
        ("Pipeline", {"fields": ("pipeline_id", "name", "description")}),
        ("Active Version", {"fields": ("active_version",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(NLPPipelineVersion)
class NLPPipelineVersionAdmin(ModelAdmin):
    list_display = ["pipeline", "version", "updated_at"]
    list_filter = ["pipeline", "version"]
    search_fields = ["pipeline__pipeline_id", "version"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Version", {"fields": ("pipeline", "version")}),
        ("Prompt Configuration", {"fields": ("system_prompt_suffix", "user_prompt_context")}),
        ("Few-Shot Examples", {"fields": ("examples",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
