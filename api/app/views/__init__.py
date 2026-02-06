"""
Views package for Ekko API
"""

# Import ViewSets from main_views
from .main_views import (
    AlertInstanceViewSet,
    DefaultNetworkAlertViewSet,
    ChainViewSet,
    NotificationChannelEndpointViewSet,
    TeamNotificationChannelEndpointViewSet,
    TeamMemberNotificationOverrideViewSet,
)

# vNext executable-backed templates
from .alert_template_views import AlertTemplateViewSet

# Import ViewSets from group_views
from .group_views import (
    GenericGroupViewSet,
    GroupSubscriptionViewSet,
)

# Wallet nickname CRUD
from .wallet_nickname_views import WalletNicknameViewSet

# Re-export for backward compatibility
__all__ = [
    'AlertTemplateViewSet',
    'AlertInstanceViewSet',
    'DefaultNetworkAlertViewSet',
    'ChainViewSet',
    'NotificationChannelEndpointViewSet',
    'TeamNotificationChannelEndpointViewSet',
    'TeamMemberNotificationOverrideViewSet',
    'GenericGroupViewSet',
    'GroupSubscriptionViewSet',
    'WalletNicknameViewSet',
]
