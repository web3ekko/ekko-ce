"""
URL Configuration for Enhanced Alert API
"""

from django.conf import settings
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlertTemplateViewSet, AlertInstanceViewSet,
    DefaultNetworkAlertViewSet,
    ChainViewSet,
    NotificationChannelEndpointViewSet, TeamNotificationChannelEndpointViewSet,
    TeamMemberNotificationOverrideViewSet,
    GenericGroupViewSet, GroupSubscriptionViewSet,
    WalletNicknameViewSet,
)
from .views.notification_views import (
    UserNotificationSettingsViewSet, GroupNotificationSettingsViewSet,
    NotificationDeliveryViewSet, NotificationTemplateViewSet,
    BulkNotificationAPIView, NotificationCacheAPIView, NotificationHealthAPIView,
    PlatformHealthMetricsAPIView, ChannelHealthMetricsAPIView,
    UserNotificationHistoryAPIView
)
from .views.alert_job_views import (
    GetActiveAlertsByTriggerTypeView,
    GetMatchingEventDrivenAlertsView,
    RecordJobCreationView,
)
from .views.profile_views import (
    ProfileView, PreferencesView, AvatarView,
    ConnectedServicesView, ConnectedServiceDetailView,
    SessionsView, SessionDetailView, RevokeAllSessionsView,
    ExportDataView, DeleteAccountView
)
from .views.search_views import (
    GlobalSearchView, SearchAlertsView, SearchWalletsView,
    SearchTransactionsView, SearchSuggestionsView
)
from .views.dashboard_views import (
    DashboardStatsView, DashboardActivityView, DashboardChainStatsView,
    DashboardNetworkStatusView
)
from .views.billing_views import BillingOverviewView, BillingSubscriptionView
from .views.developer_views import (
    ApiKeyListCreateView, ApiKeyDetailView, ApiKeyRevokeView,
    ApiUsageView, ApiEndpointsView
)
from .views.team_views import (
    TeamListView, TeamMembersView, TeamInviteView,
    TeamMemberDetailView, TeamMemberResendInviteView
)
from .views.analytics_views import (
    analytics_health, analytics_snapshots, analytics_tables,
    analytics_table_schema, wallet_transactions, wallet_token_transfers,
    wallet_balances, block_info, token_prices, newsfeed_transactions
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'alert-templates', AlertTemplateViewSet, basename='alerttemplate')
router.register(r'alerts/default-network', DefaultNetworkAlertViewSet, basename='default-network-alert')
router.register(r'alerts', AlertInstanceViewSet, basename='alert')
# Alias for clarity in the UI/PRDs: "alert instances" are the concrete, target-bound alerts.
router.register(r'alert-instances', AlertInstanceViewSet, basename='alert-instance')
router.register(r'chains', ChainViewSet, basename='chains')
router.register(r'notification-settings', UserNotificationSettingsViewSet, basename='notification-settings')
router.register(r'notifications/channels', NotificationChannelEndpointViewSet, basename='notification-channels')
router.register(r'team-notification-endpoints', TeamNotificationChannelEndpointViewSet, basename='team-notification-endpoints')
router.register(r'team-notification-overrides', TeamMemberNotificationOverrideViewSet, basename='team-notification-overrides')
router.register(r'group-notification-settings', GroupNotificationSettingsViewSet, basename='group-notification-settings')
router.register(r'notification-deliveries', NotificationDeliveryViewSet, basename='notification-deliveries')
router.register(r'notification-templates', NotificationTemplateViewSet, basename='notification-templates')
router.register(r'groups', GenericGroupViewSet, basename='groups')
router.register(r'subscriptions', GroupSubscriptionViewSet, basename='subscriptions')
router.register(r'wallet-nicknames', WalletNicknameViewSet, basename='wallet-nicknames')

app_name = 'alerts'

urlpatterns = [
    # Alert Job Configuration API (for actors and Alert Scheduler Provider)
    # IMPORTANT: These must come BEFORE router.urls to avoid router matching /alerts/*
    path('alert-jobs/by-trigger-type/', GetActiveAlertsByTriggerTypeView.as_view(), name='alerts-by-trigger-type'),
    path('alert-jobs/event-driven/', GetMatchingEventDrivenAlertsView.as_view(), name='event-driven-alerts'),
    path('alert-jobs/record-job/', RecordJobCreationView.as_view(), name='record-job-creation'),

    # Router patterns (includes /alerts/, /templates/, etc.)
    path('', include(router.urls)),

    # Non-router notification endpoints
    path('notifications/bulk/', BulkNotificationAPIView.as_view(), name='bulk-notifications'),
    path('notifications/cache/', NotificationCacheAPIView.as_view(), name='notification-cache'),
    path('notifications/health/', NotificationHealthAPIView.as_view(), name='notification-health'),
    path('notifications/platform-metrics/', PlatformHealthMetricsAPIView.as_view(), name='platform-health-metrics'),
    path('notifications/channel-metrics/<str:channel_id>/', ChannelHealthMetricsAPIView.as_view(), name='channel-health-metrics'),
    path('notifications/history/', UserNotificationHistoryAPIView.as_view(), name='notification-history'),

    # Profile API (v1)
    path('v1/profile/', ProfileView.as_view(), name='profile'),
    path('v1/profile/preferences/', PreferencesView.as_view(), name='profile-preferences'),
    path('v1/profile/avatar/', AvatarView.as_view(), name='profile-avatar'),
    path('v1/profile/connected-services/', ConnectedServicesView.as_view(), name='profile-connected-services'),
    path('v1/profile/connected-services/<uuid:service_id>/', ConnectedServiceDetailView.as_view(), name='profile-connected-service-detail'),
    path('v1/profile/sessions/', SessionsView.as_view(), name='profile-sessions'),
    path('v1/profile/sessions/revoke-all/', RevokeAllSessionsView.as_view(), name='profile-revoke-all-sessions'),
    path('v1/profile/sessions/<str:session_id>/', SessionDetailView.as_view(), name='profile-session-detail'),
    path('v1/profile/export/', ExportDataView.as_view(), name='profile-export'),
    path('v1/profile/delete/', DeleteAccountView.as_view(), name='profile-delete'),

    # Teams API (v1)
    path('v1/teams/', TeamListView.as_view(), name='teams-list'),
    path('v1/teams/<uuid:team_id>/members/', TeamMembersView.as_view(), name='team-members'),
    path('v1/teams/<uuid:team_id>/invite/', TeamInviteView.as_view(), name='team-invite'),
    path('v1/teams/<uuid:team_id>/members/<uuid:member_id>/', TeamMemberDetailView.as_view(), name='team-member-detail'),
    path('v1/teams/<uuid:team_id>/members/<uuid:member_id>/resend-invite/', TeamMemberResendInviteView.as_view(), name='team-member-resend-invite'),

    # Search API (v1)
    path('v1/search/', GlobalSearchView.as_view(), name='global-search'),
    path('v1/search/alerts/', SearchAlertsView.as_view(), name='search-alerts'),
    path('v1/search/wallets/', SearchWalletsView.as_view(), name='search-wallets'),
    path('v1/search/transactions/', SearchTransactionsView.as_view(), name='search-transactions'),
    path('v1/search/suggestions/', SearchSuggestionsView.as_view(), name='search-suggestions'),

    # Billing API (v1)
    path('v1/billing/overview/', BillingOverviewView.as_view(), name='billing-overview'),
    path('v1/billing/subscription/', BillingSubscriptionView.as_view(), name='billing-subscription'),

    # Developer API (v1)
    path('v1/developer/api-keys/', ApiKeyListCreateView.as_view(), name='developer-api-keys'),
    path('v1/developer/api-keys/<uuid:key_id>/', ApiKeyDetailView.as_view(), name='developer-api-key-detail'),
    path('v1/developer/api-keys/<uuid:key_id>/revoke/', ApiKeyRevokeView.as_view(), name='developer-api-key-revoke'),
    path('v1/developer/usage/', ApiUsageView.as_view(), name='developer-usage'),
    path('v1/developer/endpoints/', ApiEndpointsView.as_view(), name='developer-endpoints'),

    # Dashboard Stats API (v1)
    path('v1/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('v1/dashboard/activity/', DashboardActivityView.as_view(), name='dashboard-activity'),
    path('v1/dashboard/chain-stats/', DashboardChainStatsView.as_view(), name='dashboard-chain-stats'),
    path('v1/dashboard/network-status/', DashboardNetworkStatusView.as_view(), name='dashboard-network-status'),

    # Analytics API (v1) - Direct DuckLake queries
    path('v1/analytics/health/', analytics_health, name='analytics-health'),
    path('v1/analytics/snapshots/', analytics_snapshots, name='analytics-snapshots'),
    path('v1/analytics/tables/', analytics_tables, name='analytics-tables'),
    path('v1/analytics/tables/<str:table_name>/schema/', analytics_table_schema, name='analytics-table-schema'),
    path('v1/analytics/wallet/<str:address>/transactions/', wallet_transactions, name='analytics-wallet-transactions'),
    path('v1/analytics/wallet/<str:address>/transfers/', wallet_token_transfers, name='analytics-wallet-transfers'),
    path('v1/analytics/wallet/<str:address>/balances/', wallet_balances, name='analytics-wallet-balances'),
    path('v1/analytics/block/<int:block_number>/', block_info, name='analytics-block-info'),
    path('v1/analytics/token/<str:token_address>/prices/', token_prices, name='analytics-token-prices'),

    # Newsfeed API (v1) - Transaction feed for monitored wallets
    path('v1/analytics/newsfeed/transactions/', newsfeed_transactions, name='analytics-newsfeed-transactions'),
]

# Available endpoints:
#
# TEMPLATES:
# GET    /templates/                  - List accessible templates
# POST   /templates/                  - Create new template
# GET    /templates/{id}/             - Get specific template
# PUT    /templates/{id}/             - Update template
# DELETE /templates/{id}/             - Delete template
# POST   /templates/{id}/instantiate/ - Instantiate template to create alert
# GET    /templates/popular/          - Get most popular templates
# GET    /templates/by_event_type/?event_type=X - Get templates by event type
#
# ALERTS:
# GET    /alerts/                     - List user's alerts (latest versions by default)
# POST   /alerts/                     - Create new alert with complete specification
# GET    /alerts/{id}/                - Get specific alert
# PUT    /alerts/{id}/                - Update alert (increments version)
# PATCH  /alerts/{id}/                - Partial update alert
# DELETE /alerts/{id}/                - Delete alert
# GET    /alerts/{id}/versions/       - Get all versions of alert
# GET    /alerts/{id}/version/?version=N - Get specific version
# GET    /alerts/{id}/changelog/      - Get change log for alert
# GET    /alerts/{id}/jobs/           - Get jobs for alert
# GET    /alerts/{id}/executions/     - Get execution history
# POST   /alerts/{id}/enable/         - Enable alert
# POST   /alerts/{id}/disable/        - Disable alert
#
# NOTIFICATION SETTINGS:
# GET    /notification-settings/      - Get user's notification settings
# POST   /notification-settings/      - Create/update notification settings
# PUT    /notification-settings/      - Update notification settings
# POST   /notification-settings/test_notification/ - Validate notification settings
# GET    /notification-settings/channel_templates/ - Get channel configuration templates
# POST   /notification-settings/validate_channel_config/ - Validate channel config
# GET    /notification-settings/cache_status/ - Get cache status
# POST   /notification-settings/clear_cache/ - Clear user cache
# POST   /notification-settings/warm_cache/ - Warm cache for user
#
# NOTIFICATION CHANNELS (Multi-Address):
# GET    /notifications/channels/     - List user's notification channels
# POST   /notifications/channels/     - Create new notification channel
# GET    /notifications/channels/{id}/ - Get specific channel
# PATCH  /notifications/channels/{id}/ - Update channel
# DELETE /notifications/channels/{id}/ - Delete channel
# POST   /notifications/channels/{id}/request_verification/ - Request verification code
# POST   /notifications/channels/{id}/verify/ - Submit verification code
# POST   /notifications/channels/{id}/resend_verification/ - Resend verification code
# POST   /notifications/channels/warm_cache/ - Warm channel cache for user
# POST   /notifications/channels/clear_cache/ - Clear channel cache for user
#
# TEAM NOTIFICATION ENDPOINTS (Multi-Address):
# GET    /team-notification-endpoints/ - List team endpoints (for user's teams)
# POST   /team-notification-endpoints/ - Create new team endpoint (admin only)
# GET    /team-notification-endpoints/{id}/ - Get specific team endpoint
# PATCH  /team-notification-endpoints/{id}/ - Update team endpoint (admin only)
# DELETE /team-notification-endpoints/{id}/ - Delete team endpoint (admin only)
# POST   /team-notification-endpoints/warm_cache/ - Warm team endpoint cache (admin only)
# POST   /team-notification-endpoints/clear_cache/ - Clear team endpoint cache (admin only)
#
# TEAM NOTIFICATION OVERRIDES (Member Control):
# GET    /team-notification-overrides/ - List user's notification overrides for all teams
# POST   /team-notification-overrides/ - Create/update override for a team
# GET    /team-notification-overrides/{team_id}/ - Get override for specific team
# PATCH  /team-notification-overrides/{team_id}/ - Update override for team
# DELETE /team-notification-overrides/{team_id}/ - Reset override to defaults
# POST   /team-notification-overrides/disable_all_team_notifications/ - Disable all for team
# POST   /team-notification-overrides/enable_all_team_notifications/ - Enable all for team
#
# GROUP NOTIFICATION SETTINGS:
# GET    /group-notification-settings/ - List group settings for user's groups
# POST   /group-notification-settings/{id}/test_group_notification/ - Validate group notification settings
#
# NOTIFICATION DELIVERIES:
# GET    /notification-deliveries/    - List delivery history with filters
# GET    /notification-deliveries/statistics/ - Get delivery statistics
#
# NOTIFICATION TEMPLATES:
# GET    /notification-templates/     - List notification templates
# POST   /notification-templates/     - Create notification template
# GET    /notification-templates/{id}/ - Get specific template
# PUT    /notification-templates/{id}/ - Update template
# POST   /notification-templates/{id}/render/ - Render template with variables
# GET    /notification-templates/channels/ - Get channel statistics
#
# NOTIFICATION OPERATIONS:
# POST   /notifications/bulk/         - Validate bulk notification request
# GET    /notifications/cache/        - Get cache statistics
# POST   /notifications/cache/        - Warm cache for users
# DELETE /notifications/cache/        - Clear caches
# GET    /notifications/health/       - Health check endpoint
# GET    /notifications/history/      - User notification history from DuckLake
#        ?limit=50&offset=0           - Pagination (max 100 per page)
#        ?priority=critical|high|normal|low - Filter by priority
#        ?alert_id=<uuid>             - Filter by specific alert
#        ?start_date=<ISO8601>        - Filter by date range start
#        ?end_date=<ISO8601>          - Filter by date range end
#
# GROUPS (GenericGroup unified model):
# GET    /groups/                      - List user's groups
# POST   /groups/                      - Create new group with optional initial members
# GET    /groups/{id}/                 - Get group details including members
# PUT    /groups/{id}/                 - Update group
# PATCH  /groups/{id}/                 - Partial update group
# DELETE /groups/{id}/                 - Delete group
# POST   /groups/{id}/add_members/     - Add members to group (bulk)
# POST   /groups/{id}/remove_members/  - Remove members from group (bulk)
# GET    /groups/{id}/members/         - List all members with metadata
# GET    /groups/by_type/?type=wallet  - Filter groups by type
# GET    /groups/summary/              - Get summary of groups by type
#
# GROUP SUBSCRIPTIONS:
# GET    /subscriptions/               - List user's group subscriptions
# POST   /subscriptions/               - Create subscription (link alert group to target group)
# GET    /subscriptions/{id}/          - Get subscription details
# PUT    /subscriptions/{id}/          - Update subscription
# DELETE /subscriptions/{id}/          - Delete subscription
# POST   /subscriptions/{id}/toggle/   - Toggle subscription active status
# GET    /subscriptions/by_alert_group/?alert_group_id=X - Filter by alert group
# GET    /subscriptions/by_target_group/?target_group_id=X - Filter by target group
#
# Query parameters:
# ?latest_only=true/false             - Show only latest versions (default: true)
# ?chain=ethereum-mainnet             - Filter by chain name
# ?event_type=ACCOUNT_EVENT           - Filter by event type
# ?sub_event=TOKEN_TRANSFER           - Filter by sub-event
# ?enabled=true/false                 - Filter by enabled status
# ?search=query                       - Search in name and description
# ?status=delivered/failed/pending    - Filter deliveries by status
# ?channel=email/slack/sms            - Filter by notification channel
# ?days=30                            - Days back for delivery history

# Test-only endpoints (DEBUG mode only)
# These provide utilities for E2E tests to retrieve verification codes
if settings.DEBUG:
    from .views import test_views
    urlpatterns += [
        path('test/verification-code/', test_views.get_verification_code, name='test-verification-code'),
        path('test/health/', test_views.health_check, name='test-health'),
    ]
