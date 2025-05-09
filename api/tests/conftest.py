import asyncio
import os
import pytest
import nats
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

# Set test environment variables
os.environ["NATS_URL"] = "nats://localhost:4222"
os.environ["TEST_MODE"] = "true"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def nats_connection():
    """Create a NATS connection for testing."""
    nc = await nats.connect(os.environ["NATS_URL"])
    yield nc
    await nc.close()

@pytest.fixture(scope="session")
async def jetstream(nats_connection):
    """Create a JetStream context for testing."""
    js = nats_connection.jetstream()
    
    # Create test buckets
    test_buckets = [
        "test_users", 
        "test_wallets", 
        "test_alerts", 
        "test_wallet_balances",
        "test_workflows",
        "test_workflow_executions",
        "test_agents",
        "test_alert_rules"
    ]
    
    for bucket in test_buckets:
        try:
            await js.key_value(bucket=bucket)
        except Exception:
            await js.create_key_value(bucket=bucket)
    
    yield js
    
    # Clean up test data
    for bucket in test_buckets:
        try:
            kv = await js.key_value(bucket=bucket)
            keys = await kv.keys()
            for key in keys:
                await kv.delete(key)
        except Exception as e:
            print(f"Error cleaning up {bucket}: {e}")

@pytest.fixture
async def clean_test_data(jetstream):
    """Clean test data before and after each test."""
    test_buckets = [
        "test_users", 
        "test_wallets", 
        "test_alerts", 
        "test_wallet_balances",
        "test_workflows",
        "test_workflow_executions",
        "test_agents",
        "test_alert_rules"
    ]
    
    # Clean before test
    for bucket in test_buckets:
        try:
            kv = await jetstream.key_value(bucket=bucket)
            keys = await kv.keys()
            for key in keys:
                await kv.delete(key)
        except Exception as e:
            print(f"Error cleaning up {bucket}: {e}")
    
    yield
    
    # Clean after test
    for bucket in test_buckets:
        try:
            kv = await jetstream.key_value(bucket=bucket)
            keys = await kv.keys()
            for key in keys:
                await kv.delete(key)
        except Exception as e:
            print(f"Error cleaning up {bucket}: {e}")

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "email": f"test_{uuid.uuid4()}@example.com",
        "full_name": "Test User",
        "role": "user",
        "is_active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "hashed_password": "hashed_password"
    }

@pytest.fixture
def sample_wallet_data():
    """Sample wallet data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "blockchain_symbol": "ETH",
        "address": f"0x{uuid.uuid4().hex}",
        "name": "Test Wallet",
        "balance": 1.0,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "updated_at": None
    }

@pytest.fixture
def sample_alert_data():
    """Sample alert data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "type": "transaction",
        "message": "Test alert message",
        "time": datetime.now().isoformat(),
        "status": "new",
        "icon": "warning",
        "priority": "high",
        "related_wallet_id": str(uuid.uuid4())
    }

@pytest.fixture
def sample_wallet_balance_data(sample_wallet_data):
    """Sample wallet balance data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "wallet_id": sample_wallet_data["id"],
        "timestamp": datetime.now().isoformat(),
        "balance": 1.5,
        "token_price": 2000.0,
        "fiat_value": 3000.0
    }

@pytest.fixture
def sample_workflow_step_data():
    """Sample workflow step data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Step",
        "type": "trigger",
        "config": {"condition": "balance > 1.0"},
        "next_steps": []
    }

@pytest.fixture
def sample_workflow_data(sample_workflow_step_data, sample_user_data):
    """Sample workflow data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Workflow",
        "description": "Test workflow description",
        "enabled": True,
        "steps": [sample_workflow_step_data],
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "created_by": sample_user_data["id"]
    }

@pytest.fixture
def sample_workflow_execution_data(sample_workflow_data):
    """Sample workflow execution data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "workflow_id": sample_workflow_data["id"],
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "result": None,
        "error": None
    }

@pytest.fixture
def sample_agent_data(sample_user_data):
    """Sample agent data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Agent",
        "type": "monitor",
        "config": {"target": "ETH", "interval": 60},
        "status": "inactive",
        "last_run": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "created_by": sample_user_data["id"]
    }

@pytest.fixture
def sample_alert_rule_data(sample_user_data):
    """Sample alert rule data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Alert Rule",
        "description": "Test alert rule description",
        "condition": {"type": "balance", "threshold": 1.0, "operator": "gt"},
        "action": {"type": "notification", "channel": "email"},
        "enabled": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "created_by": sample_user_data["id"]
    }
