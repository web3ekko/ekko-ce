import asyncio
import os
import pytest
import nats
import json
import uuid
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional

# Set test environment variables
os.environ["TEST_MODE"] = "true"

# Configure pytest to use asyncio
pytest_plugins = ["pytest_asyncio"]

# Testcontainer fixtures
@pytest.fixture(scope="session")
def nats_container():
    """Start a NATS container with JetStream for testing."""
    from testcontainers.generic import GenericContainer

    container = GenericContainer("nats:2.10-alpine")
    container.with_command("-js -m 8222")
    container.with_exposed_ports(4222, 8222)

    with container as nats:
        # Set environment variable for other fixtures
        nats_url = f"nats://localhost:{nats.get_exposed_port(4222)}"
        os.environ["TEST_NATS_URL"] = nats_url
        yield nats

@pytest.fixture(scope="session")
def test_database():
    """Create a temporary DuckDB database for testing."""
    import tempfile
    import os

    # Create temporary database file path (but don't create the file)
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)  # Close the file descriptor
    os.unlink(db_path)  # Remove the empty file so DuckDB can create it properly

    # Set environment variable for database path
    os.environ["TEST_DUCKDB_PATH"] = db_path

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass

@pytest.fixture(scope="session")
async def nats_connection(nats_container):
    """Create a NATS connection for testing."""
    nats_url = nats_container.get_connection_url()
    nc = await nats.connect(nats_url)
    yield nc
    await nc.close()

@pytest.fixture(scope="session")
def db_manager(test_database):
    """Create a database manager for testing."""
    from app.database.connection import DatabaseManager

    # Override the database path for testing
    original_path = os.environ.get("DUCKDB_PATH")
    os.environ["DUCKDB_PATH"] = test_database

    # Create database manager
    manager = DatabaseManager()

    yield manager

    # Cleanup
    manager.close_all_connections()

    # Restore original path
    if original_path:
        os.environ["DUCKDB_PATH"] = original_path
    elif "DUCKDB_PATH" in os.environ:
        del os.environ["DUCKDB_PATH"]

@pytest.fixture(scope="session")
def db_schema(db_manager):
    """Initialize database schema for testing."""
    from app.database.migrations import MigrationManager

    migration_manager = MigrationManager()
    migration_manager.initialize_database()

    yield migration_manager

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

# Repository fixtures
@pytest.fixture
def user_repository(db_schema, jetstream):
    """Create a UserRepository for testing."""
    from app.repositories import UserRepository

    repo = UserRepository()
    repo.set_jetstream(jetstream)
    return repo

@pytest.fixture
def wallet_repository(db_schema, jetstream):
    """Create a WalletRepository for testing."""
    from app.repositories import WalletRepository

    repo = WalletRepository()
    repo.set_jetstream(jetstream)
    return repo

@pytest.fixture
def alert_repository(db_schema, jetstream):
    """Create an AlertRepository for testing."""
    from app.repositories import AlertRepository

    repo = AlertRepository()
    repo.set_jetstream(jetstream)
    return repo

@pytest.fixture
def wallet_balance_repository(db_schema, jetstream):
    """Create a WalletBalanceRepository for testing."""
    from app.repositories import WalletBalanceRepository

    repo = WalletBalanceRepository()
    repo.set_jetstream(jetstream)
    return repo

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
    import os
    from testcontainers.nats import NatsContainer

    # Set Docker socket path for macOS Docker Desktop
    docker_socket_path = os.path.expanduser("~/.docker/run/docker.sock")
    if os.path.exists(docker_socket_path):
        os.environ["DOCKER_HOST"] = f"unix://{docker_socket_path}"

    # Start a NATS container with JetStream enabled
    # Use the enable_jetstream() method as shown in the docs
    with NatsContainer().enable_jetstream() as nats:
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
