import pytest
import json
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.app import app
from app.models import Workflow, WorkflowStep, User

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
    
    with patch("app.workflows.get_current_user", return_value=user):
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
    
    with patch("app.workflows.js", mock_js):
        with patch("app.workflows.nc", mock_nc):
            yield mock_js, mock_kv

@pytest.mark.asyncio
async def test_create_workflow(test_client, mock_auth, mock_nats_js):
    """Test creating a workflow."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    step = WorkflowStep(
        name="Test Step",
        type="trigger",
        config={"condition": "balance > 1.0"}
    )
    
    workflow_data = {
        "id": str(uuid.uuid4()),
        "name": "Test Workflow",
        "description": "Test workflow description",
        "enabled": True,
        "steps": [step.dict()],
        "created_by": mock_auth.id
    }
    
    # Mock the KV put method
    mock_kv.put = MagicMock()
    
    # Send request to create workflow
    with patch("app.workflows.publish_event"):
        response = test_client.post(
            "/api/workflows",
            json=workflow_data
        )
    
    # Check response
    assert response.status_code == 200
    assert response.json()["name"] == "Test Workflow"
    assert response.json()["description"] == "Test workflow description"
    assert response.json()["enabled"] is True
    assert len(response.json()["steps"]) == 1
    assert response.json()["steps"][0]["name"] == "Test Step"
    
    # Verify KV store was called
    mock_kv.put.assert_called_once()

@pytest.mark.asyncio
async def test_get_workflows(test_client, mock_auth, mock_nats_js):
    """Test getting all workflows."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    workflow_id = str(uuid.uuid4())
    workflow = Workflow(
        id=workflow_id,
        name="Test Workflow",
        description="Test workflow description",
        enabled=True,
        steps=[
            WorkflowStep(
                name="Test Step",
                type="trigger",
                config={"condition": "balance > 1.0"}
            )
        ],
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Mock the KV keys and get methods
    mock_kv.keys.return_value = [workflow_id]
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(workflow.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Send request to get workflows
    response = test_client.get("/api/workflows")
    
    # Check response
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == workflow_id
    assert response.json()[0]["name"] == "Test Workflow"
    
    # Verify KV store was called
    mock_kv.keys.assert_called_once()
    mock_kv.get.assert_called_once_with(workflow_id)

@pytest.mark.asyncio
async def test_get_workflow(test_client, mock_auth, mock_nats_js):
    """Test getting a specific workflow."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    workflow_id = str(uuid.uuid4())
    workflow = Workflow(
        id=workflow_id,
        name="Test Workflow",
        description="Test workflow description",
        enabled=True,
        steps=[
            WorkflowStep(
                name="Test Step",
                type="trigger",
                config={"condition": "balance > 1.0"}
            )
        ],
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(workflow.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Send request to get workflow
    response = test_client.get(f"/api/workflows/{workflow_id}")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["id"] == workflow_id
    assert response.json()["name"] == "Test Workflow"
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(workflow_id)

@pytest.mark.asyncio
async def test_update_workflow(test_client, mock_auth, mock_nats_js):
    """Test updating a workflow."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    workflow_id = str(uuid.uuid4())
    workflow = Workflow(
        id=workflow_id,
        name="Test Workflow",
        description="Test workflow description",
        enabled=True,
        steps=[
            WorkflowStep(
                name="Test Step",
                type="trigger",
                config={"condition": "balance > 1.0"}
            )
        ],
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object for the existing workflow
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(workflow.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Updated workflow data
    updated_workflow = workflow.dict()
    updated_workflow["name"] = "Updated Workflow"
    updated_workflow["description"] = "Updated description"
    
    # Mock the KV put method
    mock_kv.put = MagicMock()
    
    # Send request to update workflow
    with patch("app.workflows.publish_event"):
        response = test_client.put(
            f"/api/workflows/{workflow_id}",
            json=updated_workflow
        )
    
    # Check response
    assert response.status_code == 200
    assert response.json()["id"] == workflow_id
    assert response.json()["name"] == "Updated Workflow"
    assert response.json()["description"] == "Updated description"
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(workflow_id)
    mock_kv.put.assert_called_once()

@pytest.mark.asyncio
async def test_delete_workflow(test_client, mock_auth, mock_nats_js):
    """Test deleting a workflow."""
    mock_js, mock_kv = mock_nats_js
    
    # Prepare test data
    workflow_id = str(uuid.uuid4())
    workflow = Workflow(
        id=workflow_id,
        name="Test Workflow",
        description="Test workflow description",
        enabled=True,
        steps=[
            WorkflowStep(
                name="Test Step",
                type="trigger",
                config={"condition": "balance > 1.0"}
            )
        ],
        created_by=mock_auth.id,
        created_at=datetime.now().isoformat()
    )
    
    # Create a mock entry object
    mock_entry = MagicMock()
    mock_entry.value = json.dumps(workflow.dict()).encode()
    mock_kv.get.return_value = mock_entry
    
    # Mock the KV delete method
    mock_kv.delete = MagicMock()
    
    # Send request to delete workflow
    with patch("app.workflows.publish_event"):
        response = test_client.delete(f"/api/workflows/{workflow_id}")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["id"] == workflow_id
    
    # Verify KV store was called
    mock_kv.get.assert_called_once_with(workflow_id)
    mock_kv.delete.assert_called_once_with(workflow_id)
