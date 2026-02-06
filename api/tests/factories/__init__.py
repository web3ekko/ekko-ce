"""
Django model factories for testing
"""

from .auth_factories import (
    UserFactory,
    AdminUserFactory,
    UserDeviceFactory,
    AuthenticationLogFactory,
    EmailVerificationCodeFactory,
    create_user_with_device,
    create_verification_code_flow,
)

from .blockchain_factories import (
    BlockchainFactory,
    WalletFactory,
    TokenFactory,
    DaoFactory,
    WalletSubscriptionFactory,
    DaoSubscriptionFactory,
    DaoWalletFactory,
    CategoryFactory,
    StoryFactory,
    TagFactory,
    WalletBalanceFactory,
)

from .organization_factories import (
    OrganizationFactory,
    TeamFactory,
    TeamMemberFactory,
    UserSettingsFactory,
)

# Import alert factories if they exist
try:
    from .alert_factories import (
        AlertTemplateFactory,
        PublicAlertTemplateFactory,
        AlertInstanceFactory,
        StandaloneAlertInstanceFactory,
        EventDrivenAlertInstanceFactory,
        OneTimeAlertInstanceFactory,
        PeriodicAlertInstanceFactory,
        AlertExecutionFactory,
        AlertChangeLogFactory,
        create_alert_instance_with_history,
        create_template_with_instances,
        create_complete_alert_workflow,
    )
    ALERT_FACTORIES_AVAILABLE = True
except ImportError:
    ALERT_FACTORIES_AVAILABLE = False

__all__ = [
    # Authentication factories
    'UserFactory',
    'AdminUserFactory',
    'UserDeviceFactory',
    'AuthenticationLogFactory',
    'EmailVerificationCodeFactory',
    'create_user_with_device',
    'create_verification_code_flow',
    
    # Blockchain factories
    'BlockchainFactory',
    'WalletFactory',
    'TokenFactory',
    'DaoFactory',
    'WalletSubscriptionFactory',
    'DaoSubscriptionFactory',
    'DaoWalletFactory',
    'CategoryFactory',
    'StoryFactory',
    'TagFactory',
    'WalletBalanceFactory',
    
    # Organization factories
    'OrganizationFactory',
    'TeamFactory',
    'TeamMemberFactory',
    'UserSettingsFactory',
]

# Add alert factories if available
if ALERT_FACTORIES_AVAILABLE:
    __all__.extend([
        'AlertTemplateFactory',
        'PublicAlertTemplateFactory',
        'AlertInstanceFactory',
        'StandaloneAlertInstanceFactory',
        'EventDrivenAlertInstanceFactory',
        'OneTimeAlertInstanceFactory',
        'PeriodicAlertInstanceFactory',
        'AlertExecutionFactory',
        'AlertChangeLogFactory',
        'create_alert_instance_with_history',
        'create_template_with_instances',
        'create_complete_alert_workflow',
    ])

# Import group factories
try:
    from .group_factories import (
        GenericGroupFactory,
        WalletGroupFactory,
        AlertGroupFactory,
        NetworkGroupFactory,
        TokenGroupFactory,
        GroupWithMembersFactory,
        GroupSubscriptionFactory,
        create_group_with_members,
        create_subscription_chain,
    )
    GROUP_FACTORIES_AVAILABLE = True
except ImportError:
    GROUP_FACTORIES_AVAILABLE = False

# Add group factories if available
if GROUP_FACTORIES_AVAILABLE:
    __all__.extend([
        'GenericGroupFactory',
        'WalletGroupFactory',
        'AlertGroupFactory',
        'NetworkGroupFactory',
        'TokenGroupFactory',
        'GroupWithMembersFactory',
        'GroupSubscriptionFactory',
        'create_group_with_members',
        'create_subscription_chain',
    ])
