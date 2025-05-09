import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError

from app.models import AlertRule

# Test AlertRule model
def test_alert_rule_model():
    user_id = str(uuid.uuid4())
    
    # Test with minimum required fields
    rule_data = {
        "name": "Test Alert Rule",
        "condition": {"type": "balance", "threshold": 1.0, "operator": "gt"},
        "action": {"type": "notification", "channel": "email"},
        "created_by": user_id
    }
    rule = AlertRule(**rule_data)
    
    assert rule.name == "Test Alert Rule"
    assert rule.condition == {"type": "balance", "threshold": 1.0, "operator": "gt"}
    assert rule.action == {"type": "notification", "channel": "email"}
    assert rule.created_by == user_id
    assert rule.description is None  # Default value
    assert rule.enabled is True  # Default value
    assert rule.updated_at is None  # Default value
    
    # Test with all fields
    rule_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    updated_at = datetime.now().isoformat()
    
    rule_data = {
        "id": rule_id,
        "name": "Complete Alert Rule",
        "description": "A complete alert rule with all fields",
        "condition": {
            "type": "price",
            "asset": "ETH",
            "threshold": 2000.0,
            "operator": "lt",
            "timeframe": "1h"
        },
        "action": {
            "type": "multi",
            "actions": [
                {"type": "notification", "channel": "email"},
                {"type": "notification", "channel": "sms"}
            ]
        },
        "enabled": False,
        "created_at": created_at,
        "updated_at": updated_at,
        "created_by": user_id
    }
    rule = AlertRule(**rule_data)
    
    assert rule.id == rule_id
    assert rule.name == "Complete Alert Rule"
    assert rule.description == "A complete alert rule with all fields"
    assert rule.condition == {
        "type": "price",
        "asset": "ETH",
        "threshold": 2000.0,
        "operator": "lt",
        "timeframe": "1h"
    }
    assert rule.action == {
        "type": "multi",
        "actions": [
            {"type": "notification", "channel": "email"},
            {"type": "notification", "channel": "sms"}
        ]
    }
    assert rule.enabled is False
    assert rule.created_at == created_at
    assert rule.updated_at == updated_at
    assert rule.created_by == user_id
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        AlertRule(condition={"type": "balance"}, action={"type": "notification"}, created_by=user_id)  # Missing name
    
    with pytest.raises(ValidationError):
        AlertRule(name="Test Rule", action={"type": "notification"}, created_by=user_id)  # Missing condition
    
    with pytest.raises(ValidationError):
        AlertRule(name="Test Rule", condition={"type": "balance"}, created_by=user_id)  # Missing action
    
    with pytest.raises(ValidationError):
        AlertRule(name="Test Rule", condition={"type": "balance"}, action={"type": "notification"})  # Missing created_by
