import asyncio
import os
import pytest
import nats
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

# Set test environment variables
os.environ["NATS_URL"] = os.getenv("NATS_URL", "nats://nats:4222")
os.environ["TEST_MODE"] = "true"

# Configure pytest to use asyncio
pytest_plugins = ["pytest_asyncio"]

# Note: We're not defining our own event_loop fixture anymore
# as pytest-asyncio provides one for us

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

@pytest.fixture(scope="session")
def nats_container():
    """Start a NATS container for testing."""
    from testcontainers.nats import NatsContainer
    
    # Start a NATS container with JetStream enabled
    with NatsContainer(image="nats:latest", command=["-js"]) as nats:
        yield nats

@pytest.fixture
def nats_client(nats_container):
    """Create a NATS client connected to the test container."""
    import nats
    import asyncio
    
    # Get the NATS URL from the container
    nats_url = nats_container.get_connection_url()
    
    # Run in an event loop to connect to NATS
    async def connect():
        nc = await nats.connect(nats_url)
        js = nc.jetstream()
        return nc, js
    
    # Connect to NATS
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    nc, js = loop.run_until_complete(connect())
    
    # Create test buckets
    async def setup_buckets():
        try:
            # Create test buckets if they don't exist
            await js.create_key_value(bucket="test_workflows")
            await js.create_key_value(bucket="test_workflow_executions")
            await js.create_key_value(bucket="test_agents")
        except Exception as e:
            # Bucket might already exist
            print(f"Note: {e}")
    
    loop.run_until_complete(setup_buckets())
    
    yield nc, js
    
    # Clean up
    async def cleanup():
        await nc.close()
        
    loop.run_until_complete(cleanup())
    loop.close()

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
