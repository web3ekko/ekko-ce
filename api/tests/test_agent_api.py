import pytest
import json
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.app import app
from app.models import Agent, User

# Mock authentication for tests
@pytest.fixture
def mock_auth():
    """Mock authentication for tests."""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="test@example.com",
        full_name="Test User",
        role="admin",
        is_active=True,
        created_at=datetime.now().isoformat()
    )
    
    with patch("app.agents.get_current_user", return_value=user):
        with patch("app.auth.get_current_user", return_value=user):
            yield user

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.fixture
def mock_nats_js():
    """Mock NATS JetStream for tests."""
    # Create a mock KV store
    mock_kv = MagicMock()
    mock_kv.keys.return_value = []
    
    # Create a mock JetStream
    mock_js = MagicMock()
    mock_js.key_value.return_value = mock_kv
    
    # Create a mock NATS connection
    mock_nc = MagicMock()
    mock_nc.jetstream.return_value = mock_js
    
    with patch("app.agents.js", mock_js):
        with patch("app.agents.nc", mock_nc):
            yield mock_js, mock_kv

@pytest.mark.asyncio
async def test_create_agent(test_client, mock_auth, mock_nats_js):
    """Test creating an agent."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    agent_data = {
        "id": str(uuid.uuid4()),
        "name": "Test Agent",
        "type": "monitor",
        "config": {"target": "ETH", "interval": 60},
        "status": "inactive",
        "created_by": mock_auth.id
    }
    
    # Mock the KV put method
    mock_kv.put = MagicMock()
    
    # Send request to create agent
    with patch("app.agents.publish_event"):
        response = test_client.post(
            "/api/agents",
            json=agent_data
        )
    
    # Check response
    assert response.status_code == 200
    assert response.json()["name"] == "Test Agent"
    assert response.json()["type"] == "monitor"
    assert response.json()["config"] == {"target": "ETH", "interval": 60}
    assert response.json()["status"] == "inactive"
    
    # Verify KV store was called
    mock_kv.put.assert_called_once()

@pytest.mark.asyncio
async def test_get_agents(test_client, mock_auth, mock_nats_js):
    """Test getting all agents."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        name="Test Agent",
        type="monitor",
        config={"target": "ETH", "interval": 60},
        status="inactive",
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Mock the KV keys and get methods
    mock_kv.keys.return_value = [agent_id]
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(agent.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Send request to get agents
    response = test_client.get("/api/agents")
    
    # Check response
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == agent_id
    assert response.json()[0]["name"] == "Test Agent"
    
    # Verify KV store was called
    mock_kv.keys.assert_called_once()
    mock_kv.get.assert_called_once_with(agent_id)

@pytest.mark.asyncio
async def test_get_agent(test_client, mock_auth, mock_nats_js):
    """Test getting a specific agent."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        name="Test Agent",
        type="monitor",
        config={"target": "ETH", "interval": 60},
        status="inactive",
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(agent.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Send request to get agent
    response = test_client.get(f"/api/agents/{agent_id}")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["id"] == agent_id
    assert response.json()["name"] == "Test Agent"
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(agent_id)

@pytest.mark.asyncio
async def test_update_agent(test_client, mock_auth, mock_nats_js):
    """Test updating an agent."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        name="Test Agent",
        type="monitor",
        config={"target": "ETH", "interval": 60},
        status="inactive",
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object for the existing agent
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(agent.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Updated agent data
    updated_agent = agent.dict()
    updated_agent["name"] = "Updated Agent"
    updated_agent["config"] = {"target": "BTC", "interval": 120}
    
    # Mock the KV put method
    mock_kv.put = MagicMock()
    
    # Send request to update agent
    with patch("app.agents.publish_event"):
        response = test_client.put(
            f"/api/agents/{agent_id}",
            json=updated_agent
        )
    
    # Check response
    assert response.status_code == 200
    assert response.json()["id"] == agent_id
    assert response.json()["name"] == "Updated Agent"
    assert response.json()["config"] == {"target": "BTC", "interval": 120}
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(agent_id)
    mock_kv.put.assert_called_once()

@pytest.mark.asyncio
async def test_delete_agent(test_client, mock_auth, mock_nats_js):
    """Test deleting an agent."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        name="Test Agent",
        type="monitor",
        config={"target": "ETH", "interval": 60},
        status="inactive",
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(agent.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Mock the KV delete method
    mock_kv.delete = MagicMock()
    
    # Send request to delete agent
    with patch("app.agents.publish_event"):
        response = test_client.delete(f"/api/agents/{agent_id}")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["id"] == agent_id
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(agent_id)
    mock_kv.delete.assert_called_once_with(agent_id)

@pytest.mark.asyncio
async def test_agent_status(test_client, mock_auth, mock_nats_js):
    """Test getting agent status."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        name="Test Agent",
        type="monitor",
        config={"target": "ETH", "interval": 60},
        status="active",
        last_run=datetime.now().isoformat(),
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(agent.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Send request to get agent status
    response = test_client.get(f"/api/agents/{agent_id}/status")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["id"] == agent_id
    assert response.json()["status"] == "active"
    assert response.json()["type"] == "monitor"
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(agent_id)

@pytest.mark.asyncio
async def test_start_agent(test_client, mock_auth, mock_nats_js):
    """Test starting an agent."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        name="Test Agent",
        type="monitor",
        config={"target": "ETH", "interval": 60},
        status="inactive",
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(agent.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Mock the KV put method
    mock_kv.put = MagicMock()
    
    # Send request to start agent
    with patch("app.agents.publish_event"):
        response = test_client.post(f"/api/agents/{agent_id}/start")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["id"] == agent_id
    assert response.json()["status"] == "active"
    assert response.json()["message"] == "Agent started successfully"
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(agent_id)
    mock_kv.put.assert_called_once()

@pytest.mark.asyncio
async def test_stop_agent(test_client, mock_auth, mock_nats_js):
    """Test stopping an agent."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        name="Test Agent",
        type="monitor",
        config={"target": "ETH", "interval": 60},
        status="active",
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(agent.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Mock the KV put method
    mock_kv.put = MagicMock()
    
    # Send request to stop agent
    with patch("app.agents.publish_event"):
        response = test_client.post(f"/api/agents/{agent_id}/stop")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["id"] == agent_id
    assert response.json()["status"] == "inactive"
    assert response.json()["message"] == "Agent stopped successfully"
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(agent_id)
    mock_kv.put.assert_called_once()
