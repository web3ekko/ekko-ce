"""
Pytest configuration and fixtures for Django app tests
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from testcontainers.compose import DockerCompose
from testcontainers.redis import RedisContainer
import nats
import json


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def redis_container():
    """Start Redis container for testing"""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest.fixture(scope="session") 
def nats_container():
    """Start NATS container for testing"""
    with DockerCompose(".", compose_file_name="docker-compose.test.yml") as compose:
        # Wait for NATS to be ready
        nats_host = compose.get_service_host("nats", 4222)
        nats_port = compose.get_service_port("nats", 4222)
        yield f"nats://{nats_host}:{nats_port}"


@pytest.fixture
def test_settings(redis_container, nats_container):
    """Override Django settings for testing"""
    return override_settings(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        NATS_URL=nats_container,
        REDIS_URL=redis_container.get_connection_url(),
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
    )


@pytest.fixture
def user():
    """Create test user"""
    User = get_user_model()
    return User.objects.create_user(
        email='test@example.com',
        first_name='Test',
        last_name='User',
        password='testpass123'
    )


@pytest.fixture
def admin_user():
    """Create admin test user"""
    User = get_user_model()
    return User.objects.create_user(
        email='admin@example.com',
        first_name='Admin',
        last_name='User',
        password='adminpass123',
        is_staff=True,
        is_superuser=True
    )


@pytest.fixture
def sample_alert_template(user):
    """Create a sample vNext AlertTemplateVersion bundle."""
    import uuid

    from app.models.alert_templates import AlertTemplate, AlertTemplateVersion
    from app.services.alert_templates.compilation import CompileContext, compile_template_to_executable
    from app.services.alert_templates.hashing import compute_template_fingerprint, compute_template_spec_hash
    from app.services.alert_templates.registry_snapshot import get_registry_snapshot

    template_id = uuid.uuid4()
    template_version = 1
    snapshot = get_registry_snapshot()

    template_spec = {
        "schema_version": "alert_template_v2",
        "name": "Wallet Balance Alert",
        "description": "Monitor wallet balance thresholds",
        "target_kind": "wallet",
        "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
        "variables": [
            {
                "id": "threshold",
                "type": "decimal",
                "label": "Threshold",
                "description": "Threshold value for the condition",
                "required": True,
                "default": 0.5,
                "validation": {"min": 0},
            }
        ],
        "signals": {
            "principals": [],
            "factors": [
                {
                    "name": "balance_latest",
                    "unit": "WEI",
                    "update_sources": [{"ref": "ducklake.wallet_balance_window"}],
                }
            ],
        },
        "derivations": [],
        "trigger": {
            "evaluation_mode": "periodic",
            "condition_ast": {"op": "lt", "left": "balance_latest", "right": "{{threshold}}"},
            "cron_cadence_seconds": 300,
            "dedupe": {"cooldown_seconds": 300, "key_template": "{{instance_id}}:{{target.key}}"},
            "pruning_hints": {"evm": {"tx_type": "any"}},
        },
        "notification": {
            "title_template": "Balance alert: {{target.short}}",
            "body_template": "Balance: {{balance_latest}}",
        },
        "fallbacks": [],
        "assumptions": [],
    }

    fingerprint = compute_template_fingerprint(template_spec)
    template_spec.update(
        {
            "template_id": str(template_id),
            "template_version": template_version,
            "fingerprint": fingerprint,
            "spec_hash": "",
        }
    )
    template_spec["spec_hash"] = compute_template_spec_hash(template_spec)

    executable = compile_template_to_executable(
        template_spec,
        ctx=CompileContext(template_id=template_id, template_version=template_version, registry_snapshot=snapshot),
    )

    template = AlertTemplate.objects.create(
        id=template_id,
        fingerprint=fingerprint,
        name="Wallet Balance Alert",
        description="Monitor wallet balance thresholds",
        target_kind="wallet",
        is_public=True,
        is_verified=True,
        created_by=user,
    )
    AlertTemplateVersion.objects.create(
        template=template,
        template_version=template_version,
        template_spec=template_spec,
        spec_hash=template_spec["spec_hash"],
        executable_id=uuid.UUID(executable["executable_id"]),
        executable=executable,
        registry_snapshot_kind=str(snapshot.get("kind")),
        registry_snapshot_version=str(snapshot.get("version")),
        registry_snapshot_hash=str(snapshot.get("hash")),
    )
    return template


@pytest.fixture
def sample_alert(user, sample_alert_template):
    """Create sample alert instance"""
    from app.models.alerts import AlertInstance
    return AlertInstance.objects.create(
        name="My ETH Balance Alert",
        nl_description="Alert when my ETH balance drops below 0.5 ETH",
        template=sample_alert_template,
        template_version=1,
        template_params={
            "threshold": 0.5,
        },
        user=user,
        event_type="ACCOUNT_EVENT",
        sub_event="CUSTOM",
        sub_event_confidence=1.0,
        enabled=True,
        alert_type="wallet",
        target_keys=["ETH:mainnet:0x742d35cc6634c0532925a3b8d4c9db96c4b4d8b"],
        trigger_type="periodic",
        trigger_config={"cron": "*/5 * * * *", "timezone": "UTC", "data_lag_secs": 120},
        processing_status="skipped",
    )


@pytest.fixture
def sample_execution(sample_alert):
    """Create sample alert execution"""
    from app.models.alerts import AlertExecution
    return AlertExecution.objects.create(
        alert_instance=sample_alert,
        alert_version=sample_alert.version,
        trigger_mode="event",
        status="completed",
        frozen_spec=sample_alert.spec,
        result=True,
        result_metadata={
            "wallet_address": "0x742d35Cc6634C0532925a3b8D4C9db96c4b4d8b",
            "balance": "15.5",
            "token_symbol": "ETH"
        },
        execution_time_ms=5000,
        rows_processed=1000
    )


@pytest.fixture
async def nats_client(nats_container):
    """Create NATS client for testing"""
    nc = await nats.connect(nats_container)
    yield nc
    await nc.close()


@pytest.fixture
def mock_nats_message():
    """Create mock NATS message for testing"""
    return {
        "alert_id": "123e4567-e89b-12d3-a456-426614174000",
        "version": 1,
        "nl_description": "Alert when my ETH balance goes above 10",
        "chain_scope": [
            {
                "chain_id": "ethereum-uuid",
                "sub_chain_ids": ["mainnet-uuid"]
            }
        ],
        "user_id": "user-uuid",
        "change_type": "created",
        "enabled": True,
        "published_at": "2024-01-01T00:00:00Z",
        "source": "django-api"
    }


@pytest.fixture
def api_client():
    """Create API client for testing"""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Create authenticated API client"""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Create admin authenticated API client"""
    api_client.force_authenticate(user=admin_user)
    return api_client


# Test data factories
class AlertTemplateFactory:
    """Factory for creating test alert templates"""
    
    @staticmethod
    def create_balance_template(user, **kwargs):
        import uuid

        from app.models.alert_templates import AlertTemplate, AlertTemplateVersion
        from app.services.alert_templates.compilation import CompileContext, compile_template_to_executable
        from app.services.alert_templates.hashing import compute_template_fingerprint, compute_template_spec_hash
        from app.services.alert_templates.registry_snapshot import get_registry_snapshot

        template_id = kwargs.pop("id", uuid.uuid4())
        template_version = 1
        snapshot = get_registry_snapshot()

        template_spec = {
            "schema_version": "alert_template_v2",
            "name": kwargs.get("name", "Balance Alert Template"),
            "description": kwargs.get("description", "Alert when balance crosses threshold"),
            "target_kind": kwargs.get("target_kind", "wallet"),
            "scope": {"networks": ["ETH:mainnet"], "instrument_constraints": []},
            "variables": [
                {"id": "threshold", "type": "decimal", "label": "Threshold", "required": True, "default": 0.5}
            ],
            "signals": {"principals": [], "factors": [{"name": "balance_latest", "unit": "WEI", "update_sources": [{"ref": "ducklake.wallet_balance_window"}]}]},
            "derivations": [],
            "trigger": {
                "evaluation_mode": "periodic",
                "condition_ast": {"op": "lt", "left": "balance_latest", "right": "{{threshold}}"},
                "cron_cadence_seconds": 300,
                "dedupe": {"cooldown_seconds": 300, "key_template": "{{instance_id}}:{{target.key}}"},
                "pruning_hints": {"evm": {"tx_type": "any"}},
            },
            "notification": {"title_template": "Balance alert", "body_template": "Balance: {{balance_latest}}"},
            "fallbacks": [],
            "assumptions": [],
        }

        fingerprint = compute_template_fingerprint(template_spec)
        template_spec.update(
            {
                "template_id": str(template_id),
                "template_version": template_version,
                "fingerprint": fingerprint,
                "spec_hash": "",
            }
        )
        template_spec["spec_hash"] = compute_template_spec_hash(template_spec)
        executable = compile_template_to_executable(
            template_spec,
            ctx=CompileContext(template_id=uuid.UUID(str(template_id)), template_version=template_version, registry_snapshot=snapshot),
        )

        template = AlertTemplate.objects.create(
            id=template_id,
            fingerprint=fingerprint,
            name=str(template_spec["name"]),
            description=str(template_spec["description"]),
            target_kind=str(template_spec["target_kind"]),
            created_by=user,
            is_public=bool(kwargs.get("is_public", False)),
            is_verified=bool(kwargs.get("is_verified", False)),
        )
        AlertTemplateVersion.objects.create(
            template=template,
            template_version=template_version,
            template_spec=template_spec,
            spec_hash=template_spec["spec_hash"],
            executable_id=uuid.UUID(executable["executable_id"]),
            executable=executable,
            registry_snapshot_kind=str(snapshot.get("kind")),
            registry_snapshot_version=str(snapshot.get("version")),
            registry_snapshot_hash=str(snapshot.get("hash")),
        )
        return template
    
    @staticmethod
    def create_transfer_template(user, **kwargs):
        # For now, reuse the same minimal vNext shape as balance templates; callers can override fields.
        kwargs.setdefault("name", "Transfer Alert Template")
        kwargs.setdefault("description", "Alert on transfer-related condition")
        return AlertTemplateFactory.create_balance_template(user, **kwargs)


class AlertInstanceFactory:
    """Factory for creating test alert instances"""

    @staticmethod
    def create_balance_alert(user, template=None, **kwargs):
        from app.models.alerts import AlertInstance
        defaults = {
            "name": "Balance Alert",
            "nl_description": "Alert when balance goes above threshold",
            "user": user,
            "template": template,
            "template_version": 1 if template is not None else None,
            "event_type": "ACCOUNT_EVENT",
            "sub_event": "CUSTOM",
            "sub_event_confidence": 1.0,
        }
        defaults.update(kwargs)
        return AlertInstance.objects.create(**defaults)


@pytest.fixture
def alert_template_factory():
    return AlertTemplateFactory


@pytest.fixture
def alert_factory():
    return AlertInstanceFactory
