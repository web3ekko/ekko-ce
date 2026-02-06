"""
Django test configuration and fixtures
Uses docker-compose services for PostgreSQL, Redis, and NATS
"""
import os
import time
from typing import Generator

import pytest

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ekko_api.settings.test")

from django.contrib.auth import get_user_model
# Import Django modules
from django.test import Client
from rest_framework.test import APIClient


def pytest_configure(config):
    """
    Called before test collection. Check that docker-compose services are running.
    """
    import psycopg2
    import redis

    # Check PostgreSQL is running
    max_retries = 30
    retry_count = 0

    print("Checking PostgreSQL connection...")
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                user="ekko",
                password="ekko123",
                database="ekko_dev",
            )
            conn.close()
            print("✓ PostgreSQL is ready")
            break
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                raise RuntimeError(
                    "PostgreSQL is not running. Please start it with:\n"
                    "docker-compose up -d postgres"
                )
            time.sleep(1)

    # Check Redis is running
    print("Checking Redis connection...")
    try:
        r = redis.Redis(host="localhost", port=6379, password="redis123")
        r.ping()
        print("✓ Redis is ready")
    except Exception:
        raise RuntimeError(
            "Redis is not running. Please start it with:\n" "docker-compose up -d redis"
        )


@pytest.fixture
def client():
    """Django test client"""
    return Client()


@pytest.fixture
def api_client():
    """Django REST Framework API client"""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a test user"""
    User = get_user_model()
    user = User.objects.create_user(
        email="test@example.com", first_name="Test", last_name="User"
    )
    return user


@pytest.fixture
def test_admin_user(db):
    """Create a test admin user"""
    User = get_user_model()
    user = User.objects.create_user(
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        is_staff=True,
        is_superuser=True,
    )
    return user


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Authenticated API client"""
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def admin_client(api_client, test_admin_user):
    """Admin authenticated API client"""
    api_client.force_authenticate(user=test_admin_user)
    return api_client


# Authentication-specific fixtures
@pytest.fixture
def test_device(test_user, db):
    """Create a test user device"""
    from authentication.models import UserDevice

    device = UserDevice.objects.create(
        user=test_user,
        device_name="Test Device",
        device_type="web",
        supports_passkey=True,
        device_fingerprint="test-fingerprint",
    )
    return device


@pytest.fixture
def test_passkey_credential(test_user, db):
    """Create a test passkey credential"""
    from authentication.models import PasskeyCredential

    credential = PasskeyCredential.objects.create(
        user=test_user,
        credential_id=b"test-credential-id",
        public_key_pem="test-public-key",
        device_type="platform",
        device_name="Test Device",
    )
    return credential


@pytest.fixture
def test_magic_link(test_user, db):
    """Create a test magic link"""
    from authentication.models import EmailMagicLink

    magic_link = EmailMagicLink.objects.create(
        user=test_user, token="test-magic-link-token", purpose="login"
    )
    return magic_link


@pytest.fixture
def test_recovery_codes(test_user, db):
    """Create test recovery codes"""
    from authentication.models import RecoveryCode

    codes = []
    for i in range(3):
        code = RecoveryCode.objects.create(user=test_user, code=f"TEST-CODE-{i:02d}")
        codes.append(code)
    return codes


# Blockchain-specific fixtures
@pytest.fixture
def test_blockchain(db):
    """Create a test blockchain"""
    from blockchain.models import Blockchain

    blockchain = Blockchain.objects.create(
        name="Ethereum", symbol="eth", chain_type="EVM"
    )
    return blockchain


@pytest.fixture
def test_wallet(test_blockchain, db):
    """Create a test wallet"""
    from blockchain.models import Wallet

    wallet = Wallet.objects.create(
        blockchain=test_blockchain,
        address="0x1234567890123456789012345678901234567890",
        name="Test Wallet",
        balance="1000000000000000000",  # 1 ETH in wei
    )
    return wallet


# Organization-specific fixtures
@pytest.fixture
def test_organization(db):
    """Create a test organization"""
    from organizations.models import Organization

    org = Organization.objects.create(
        name="Test Organization", slug="test-org", description="A test organization"
    )
    return org


@pytest.fixture
def test_team(test_organization, db):
    """Create a test team"""
    from organizations.models import Team

    team = Team.objects.create(
        organization=test_organization,
        name="Test Team",
        slug="test-team",
        description="A test team",
    )
    return team


@pytest.fixture
def test_team_member(test_team, test_user, db):
    """Create a test team member"""
    from organizations.models import TeamMember

    member = TeamMember.objects.create(team=test_team, user=test_user, role="member")
    return member


# Utility fixtures
@pytest.fixture
def mock_email_backend():
    """Mock email backend for testing"""
    from django.core.mail import get_connection
    from django.test import override_settings

    with override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    ):
        yield get_connection()


@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache for testing"""
    from django.core.cache import cache

    yield cache


@pytest.fixture
def transactional_db(db):
    """Database fixture that allows transactions"""
    # This fixture allows testing code that uses transactions
    yield


@pytest.fixture(autouse=True, scope='function')
def reset_factory_sequences():
    """
    Reset factory Faker seed before each test to ensure unique data generation.
    This prevents factory collisions when using --reuse-db.
    """
    from faker import Faker
    fake = Faker()
    # Reseed with current time to ensure uniqueness across test runs
    import time
    fake.seed_instance(int(time.time() * 1000000))
    yield
