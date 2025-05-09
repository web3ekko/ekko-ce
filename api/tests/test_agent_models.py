import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError

from app.models import Agent

# Test Agent model
def test_agent_model():
    user_id = str(uuid.uuid4())
    
    # Test with minimum required fields
    agent_data = {
        "name": "Test Agent",
        "type": "monitor",
        "config": {"target": "ETH", "interval": 60},
        "created_by": user_id
    }
    agent = Agent(**agent_data)
    
    assert agent.name == "Test Agent"
    assert agent.type == "monitor"
    assert agent.config == {"target": "ETH", "interval": 60}
    assert agent.created_by == user_id
    assert agent.status == "inactive"  # Default value
    assert agent.last_run is None  # Default value
    assert agent.updated_at is None  # Default value
    
    # Test with all fields
    agent_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    updated_at = datetime.now().isoformat()
    last_run = datetime.now().isoformat()
    
    agent_data = {
        "id": agent_id,
        "name": "Complete Agent",
        "type": "trader",
        "config": {
            "strategy": "moving_average",
            "parameters": {"short": 10, "long": 50},
            "risk_level": "medium"
        },
        "status": "active",
        "last_run": last_run,
        "created_at": created_at,
        "updated_at": updated_at,
        "created_by": user_id
    }
    agent = Agent(**agent_data)
    
    assert agent.id == agent_id
    assert agent.name == "Complete Agent"
    assert agent.type == "trader"
    assert agent.config == {
        "strategy": "moving_average",
        "parameters": {"short": 10, "long": 50},
        "risk_level": "medium"
    }
    assert agent.status == "active"
    assert agent.last_run == last_run
    assert agent.created_at == created_at
    assert agent.updated_at == updated_at
    assert agent.created_by == user_id
    
    # Test with different status values
    for status in ["inactive", "active", "error"]:
        agent_data = {
            "name": "Status Test Agent",
            "type": "monitor",
            "config": {"target": "BTC"},
            "status": status,
            "created_by": user_id
        }
        agent = Agent(**agent_data)
        assert agent.status == status
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        Agent(type="monitor", config={"target": "ETH"}, created_by=user_id)  # Missing name
    
    with pytest.raises(ValidationError):
        Agent(name="Test Agent", config={"target": "ETH"}, created_by=user_id)  # Missing type
    
    with pytest.raises(ValidationError):
        Agent(name="Test Agent", type="monitor", created_by=user_id)  # Missing config
    
    with pytest.raises(ValidationError):
        Agent(name="Test Agent", type="monitor", config={"target": "ETH"})  # Missing created_by
