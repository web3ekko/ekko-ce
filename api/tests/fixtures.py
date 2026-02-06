"""
Shared test fixtures for Django admin tests
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage

from .factories import (
    UserFactory, AlertFactory, BlockchainNodeFactory,
)

User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create a superuser for admin tests"""
    return UserFactory(admin=True)


@pytest.fixture
def regular_user(db):
    """Create a regular user"""
    return UserFactory()


@pytest.fixture
def admin_client(client, admin_user):
    """Authenticated admin client"""
    client.force_login(admin_user)
    return client


@pytest.fixture
def request_factory():
    """Django request factory for admin tests"""
    return RequestFactory()


@pytest.fixture
def admin_request(request_factory, admin_user):
    """Mock admin request with user and messages"""
    request = request_factory.get('/admin/')
    request.user = admin_user

    # Add message framework support
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    return request


@pytest.fixture
def test_data(db):
    """Create basic test data"""
    data = {}

    # Users
    data['admin'] = UserFactory(admin=True)
    data['user1'] = UserFactory(username='testuser1')
    data['user2'] = UserFactory(username='testuser2', premium=True)

    # Alerts
    data['alert1'] = AlertFactory(user=data['user1'], name='Balance Alert')
    data['alert2'] = AlertFactory(user=data['user2'], name='Price Alert', disabled=True)

    # Blockchain nodes
    data['eth_node'] = BlockchainNodeFactory(ethereum=True, enabled=True, is_primary=True)
    data['btc_node'] = BlockchainNodeFactory(
        chain_id='bitcoin-mainnet',
        chain_name='Bitcoin',
        vm_type='UTXO',
        network='mainnet'
    )

    return data


@pytest.fixture
def large_dataset(db):
    """Create a larger dataset for performance testing"""
    data = {}

    # Create multiple users
    data['users'] = UserFactory.create_batch(10)

    # Create alerts for each user
    data['alerts'] = []
    for user in data['users']:
        alerts = AlertFactory.create_batch(5, user=user)
        data['alerts'].extend(alerts)

    return data
