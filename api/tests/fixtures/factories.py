"""
Factory classes for creating test data
Uses factory_boy for consistent test data generation
"""
import factory
import uuid
from datetime import datetime, timedelta
from faker import Faker
from typing import Dict, Any

fake = Faker()


class UserProfileFactory(factory.DictFactory):
    """Factory for UserProfile model data"""

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.LazyAttribute(lambda obj: obj.email.split("@")[0])
    display_name = factory.Faker("name")
    full_name = factory.Faker("name")
    role = "user"
    is_active = True
    email_verified = True
    is_system_admin = False
    last_login = None
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class AdminUserFactory(UserProfileFactory):
    """Factory for admin users"""

    email = factory.Sequence(lambda n: f"admin{n}@example.com")
    role = "admin"
    is_system_admin = True


class BlockchainFactory(factory.DictFactory):
    """Factory for Blockchain model data"""

    name = factory.Faker("word")
    symbol = factory.LazyAttribute(lambda obj: obj.name.lower()[:10])
    chain_type = "EVM"


class WalletFactory(factory.DictFactory):
    """Factory for Wallet model data"""

    id = factory.LazyFunction(uuid.uuid4)
    blockchain_symbol = "eth"
    address = factory.LazyFunction(lambda: f"0x{fake.sha256()[:40]}")
    name = factory.Faker("word")
    derived_name = None
    domains = None
    recommended = False
    balance = factory.LazyFunction(
        lambda: str(fake.random_int(min=0, max=1000000000000000000))
    )
    status = "active"
    subnet = "mainnet"
    description = factory.Faker("text", max_nb_chars=200)
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class WalletBalanceFactory(factory.DictFactory):
    """Factory for WalletBalance model data"""

    id = factory.LazyFunction(uuid.uuid4)
    wallet_id = factory.LazyFunction(uuid.uuid4)
    balance = factory.LazyFunction(
        lambda: str(fake.random_int(min=0, max=1000000000000000000))
    )
    token_price = factory.LazyFunction(lambda: str(fake.random_int(min=1000, max=5000)))
    fiat_value = factory.LazyFunction(lambda: str(fake.random_int(min=100, max=10000)))
    timestamp = factory.LazyFunction(datetime.utcnow)
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class WalletSubscriptionFactory(factory.DictFactory):
    """Factory for WalletSubscription model data"""

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    wallet_id = factory.LazyFunction(uuid.uuid4)
    name = factory.Faker("word")
    notifications_count = 0
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class DaoFactory(factory.DictFactory):
    """Factory for Dao model data"""

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Faker("company")
    description = factory.Faker("text", max_nb_chars=500)
    recommended = False
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class AlertFactory(factory.DictFactory):
    """Factory for Alert model data"""

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    name = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("text", max_nb_chars=200)
    type = "wallet"
    category = "balance"
    priority = "medium"
    status = "active"
    condition_query = "Notify me when wallet balance is below 0.1 ETH"
    condition_parameters = None
    polars_code = None
    job_spec = None
    job_spec_generated_at = None
    enabled = True
    schedule_type = "real-time"
    schedule_interval_seconds = None
    schedule_cron_expression = None
    schedule_timezone = "UTC"
    data_sources = None
    estimated_frequency = "real-time"
    validation_rules = None
    related_wallet_id = None
    last_executed_at = None
    last_result = None
    execution_count = "0"
    error_count = "0"
    last_error = None
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class AlertExecutionFactory(factory.DictFactory):
    """Factory for AlertExecution model"""

    id = factory.LazyFunction(uuid.uuid4)
    alert_id = factory.LazyFunction(uuid.uuid4)
    execution_id = factory.LazyFunction(lambda: f"exec_{uuid.uuid4()}")
    started_at = factory.LazyFunction(datetime.utcnow)
    completed_at = factory.LazyFunction(
        lambda: datetime.utcnow() + timedelta(seconds=5)
    )
    status = "completed"
    result = True
    result_value = "1.5"
    result_metadata = None
    execution_time_ms = "150"
    rows_processed = "1000"
    data_sources_used = ["wallet_balances"]
    error_message = None
    error_details = None
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class UserSettingsFactory(factory.DictFactory):
    """Factory for UserSettings model"""

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    mute = False
    api_endpoint = "http://localhost:8000"
    refresh_interval = 30
    time_format = "24h"
    debug_mode = False
    notification_channels = None
    alert_threshold = "medium"
    email_notifications = True
    push_notifications = True
    api_key = None
    default_network = "avalanche"
    node_timeout = 10
    max_retries = 3
    auto_switch_nodes = True
    health_monitoring = True
    theme_color = "#228be6"
    layout_type = "sidebar"
    theme_mode = "light"
    compact_mode = False
    username = factory.Faker("user_name")
    display_email = factory.Faker("email")
    advanced_features = False
    beta_features = False
    analytics_enabled = True
    custom_settings = None
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class NodeFactory(factory.DictFactory):
    """Factory for Node model"""

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    name = factory.Faker("word")
    network = "Avalanche"
    subnet = "Mainnet"
    http_url = factory.LazyFunction(lambda: f"https://{fake.domain_name()}:8545")
    websocket_url = factory.LazyFunction(lambda: f"wss://{fake.domain_name()}:8546")
    vm_type = "EVM"
    node_type = "API"
    status = "Pending"
    is_enabled = True
    last_health_check = None
    response_time_ms = None
    error_count = 0
    success_count = 0
    timeout_seconds = 10
    max_retries = 3
    priority = 1
    description = factory.Faker("text", max_nb_chars=200)
    tags = None
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class NotificationChannelFactory(factory.DictFactory):
    """Factory for NotificationChannel model"""

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    name = factory.Faker("word")
    channel_type = "email"
    url = factory.Faker("email")
    enabled = True
    priority = 1
    settings = None
    credentials = None
    last_used = None
    success_count = 0
    error_count = 0
    last_error = None
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


# Schema factories for API testing
class WalletCreateSchemaFactory(factory.DictFactory):
    """Factory for WalletCreateSchema"""

    blockchain_symbol = "eth"
    address = factory.LazyFunction(lambda: f"0x{fake.sha256()[:40]}")
    name = factory.Faker("word")
    domains = None
    balance = factory.LazyFunction(
        lambda: str(fake.random_int(min=0, max=1000000000000000000))
    )
    status = "active"
    subnet = "mainnet"
    description = factory.Faker("text", max_nb_chars=200)


class AlertCreateSchemaFactory(factory.DictFactory):
    """Factory for AlertCreateSchema"""

    name = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("text", max_nb_chars=200)
    type = "wallet"
    category = "balance"
    priority = "medium"
    condition_query = "Notify me when wallet balance is below 0.1 ETH"
    schedule = {
        "type": "real-time",
        "interval_seconds": None,
        "cron_expression": None,
        "timezone": "UTC",
    }
    related_wallet_id = None
    enabled = True


class UserSettingsUpdateSchemaFactory(factory.DictFactory):
    """Factory for UserSettingsUpdateSchema"""

    mute = False
    general = {
        "api_endpoint": "http://localhost:8000",
        "refresh_interval": 30,
        "time_format": "24h",
        "debug_mode": False,
    }
    notifications = {
        "alert_threshold": "medium",
        "email_notifications": True,
        "push_notifications": True,
        "channels": [],
    }
    appearance = {
        "theme_color": "#228be6",
        "layout_type": "sidebar",
        "theme_mode": "light",
        "compact_mode": False,
    }


# Utility functions for factories
def create_test_user_with_settings(session, **user_kwargs):
    """Create a user with default settings"""
    user_data = UserProfileFactory.build(**user_kwargs)
    # Convert to dict and create actual model instance
    # This would be used in actual test implementations
    return user_data


def create_test_wallet_with_balance(session, **wallet_kwargs):
    """Create a wallet with balance history"""
    wallet_data = WalletFactory.build(**wallet_kwargs)
    # This would create wallet and associated balance records
    return wallet_data


def create_test_alert_with_execution(session, **alert_kwargs):
    """Create an alert with execution history"""
    alert_data = AlertFactory.build(**alert_kwargs)
    # This would create alert and associated execution records
    return alert_data
