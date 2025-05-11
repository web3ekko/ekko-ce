import json
import uuid
from datetime import datetime
from typing import Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .models import AlertRule, User
from .auth import get_current_user, get_admin_user
from .events import publish_event

# Create router for alert rule endpoints
router = APIRouter(prefix="/alert-rules", tags=["alert-rules"])

# Global variables for NATS access
# These will be set when the module is imported
nc = None
js = None

def init_nats(nats_connection, jetstream):
    """Initialize NATS connection for this module"""
    global nc, js
    nc = nats_connection
    js = jetstream

# Helper function to publish events
# Helper function to publish events is now imported from app.events

# Alert Rule CRUD operations
@router.get("", response_model=List[AlertRule])
async def get_alert_rules(
    skip: int = 0, 
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """
    Get all alert rules with pagination.
    """
    try:
        kv = await js.key_value(bucket="alert_rules")
        keys = await kv.keys()
        alert_rules = []
        
        # Apply pagination
        paginated_keys = keys[skip:skip + limit]
        
        for key in paginated_keys:
            data = await kv.get(key)
            rule_data = json.loads(data.value)
            
            # Filter by created_by if not admin
            if current_user.role != "admin" and rule_data.get("created_by") != current_user.id:
                continue
                
            alert_rules.append(AlertRule(**rule_data))
        
        return alert_rules
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alert rules: {str(e)}")

@router.get("/{rule_id}", response_model=AlertRule)
async def get_alert_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific alert rule by ID.
    """
    try:
        kv = await js.key_value(bucket="alert_rules")
        data = await kv.get(rule_id)
        rule_data = json.loads(data.value)
        
        # Check if user has access to this rule
        if current_user.role != "admin" and rule_data.get("created_by") != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this alert rule")
            
        return AlertRule(**rule_data)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Alert rule not found: {str(e)}")

@router.post("", response_model=AlertRule)
async def create_alert_rule(
    alert_rule: AlertRule,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new alert rule.
    """
    try:
        kv = await js.key_value(bucket="alert_rules")
        
        # Set created_by to current user
        alert_rule.created_by = current_user.id
        alert_rule.created_at = datetime.now().isoformat()
        
        # Save to KV store
        await kv.put(alert_rule.id, json.dumps(alert_rule.dict()))
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "alert_rule.created", 
            {"id": alert_rule.id, "name": alert_rule.name}
        )
        
        return alert_rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating alert rule: {str(e)}")

@router.put("/{rule_id}", response_model=AlertRule)
async def update_alert_rule(
    rule_id: str,
    alert_rule: AlertRule,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing alert rule.
    """
    try:
        if rule_id != alert_rule.id:
            raise HTTPException(status_code=400, detail="Alert rule ID mismatch")
            
        kv = await js.key_value(bucket="alert_rules")
        
        # Check if rule exists and user has access
        try:
            data = await kv.get(rule_id)
            existing_rule = json.loads(data.value)
            
            if current_user.role != "admin" and existing_rule.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to update this alert rule")
        except Exception:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        # Update rule
        alert_rule.updated_at = datetime.now().isoformat()
        await kv.put(rule_id, json.dumps(alert_rule.dict()))
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "alert_rule.updated", 
            {"id": alert_rule.id, "name": alert_rule.name}
        )
        
        return alert_rule
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating alert rule: {str(e)}")

@router.delete("/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Delete an alert rule.
    """
    try:
        kv = await js.key_value(bucket="alert_rules")
        
        # Check if rule exists and user has access
        try:
            data = await kv.get(rule_id)
            existing_rule = json.loads(data.value)
            
            if current_user.role != "admin" and existing_rule.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this alert rule")
        except Exception:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        # Delete rule
        await kv.delete(rule_id)
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "alert_rule.deleted", 
            {"id": rule_id}
        )
        
        return {"status": "deleted", "id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting alert rule: {str(e)}")

# Alert rule testing
@router.post("/{rule_id}/test", response_model=Dict[str, Any])
async def test_alert_rule(
    rule_id: str,
    test_data: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Test an alert rule with sample data.
    """
    try:
        kv = await js.key_value(bucket="alert_rules")
        
        # Check if rule exists and user has access
        try:
            data = await kv.get(rule_id)
            rule_data = json.loads(data.value)
            
            if current_user.role != "admin" and rule_data.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to test this alert rule")
                
            # Simulate rule evaluation
            rule = AlertRule(**rule_data)
            
            # In a real implementation, this would evaluate the rule against test_data
            # For now, we'll just return a mock result
            return {
                "id": rule_id,
                "name": rule.name,
                "test_result": {
                    "condition_met": True,
                    "action_simulated": True,
                    "details": "Rule test completed successfully"
                }
            }
        except Exception:
            raise HTTPException(status_code=404, detail="Alert rule not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing alert rule: {str(e)}")
