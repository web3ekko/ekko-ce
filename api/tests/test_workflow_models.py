import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError

from app.models import WorkflowStep, Workflow, WorkflowExecution

# Test WorkflowStep model
def test_workflow_step_model():
    # Test with minimum required fields
    step_data = {
        "name": "Test Step",
        "type": "trigger",
        "config": {"condition": "balance > 1.0"}
    }
    step = WorkflowStep(**step_data)
    
    assert step.name == "Test Step"
    assert step.type == "trigger"
    assert step.config == {"condition": "balance > 1.0"}
    assert step.next_steps == []  # Default value
    
    # Test with all fields
    step_id = str(uuid.uuid4())
    next_step_id = str(uuid.uuid4())
    step_data = {
        "id": step_id,
        "name": "Complex Step",
        "type": "condition",
        "config": {"operator": "and", "conditions": ["price > 1000", "volume > 1000000"]},
        "next_steps": [next_step_id]
    }
    step = WorkflowStep(**step_data)
    
    assert step.id == step_id
    assert step.name == "Complex Step"
    assert step.type == "condition"
    assert step.config == {"operator": "and", "conditions": ["price > 1000", "volume > 1000000"]}
    assert step.next_steps == [next_step_id]
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        WorkflowStep(type="trigger", config={"condition": "balance > 1.0"})  # Missing name
    
    with pytest.raises(ValidationError):
        WorkflowStep(name="Test Step", config={"condition": "balance > 1.0"})  # Missing type
    
    with pytest.raises(ValidationError):
        WorkflowStep(name="Test Step", type="trigger")  # Missing config

# Test Workflow model
def test_workflow_model():
    # Create a sample step for testing
    step = WorkflowStep(
        name="Test Step",
        type="trigger",
        config={"condition": "balance > 1.0"}
    )
    
    user_id = str(uuid.uuid4())
    
    # Test with minimum required fields
    workflow_data = {
        "name": "Test Workflow",
        "steps": [step],
        "created_by": user_id
    }
    workflow = Workflow(**workflow_data)
    
    assert workflow.name == "Test Workflow"
    assert len(workflow.steps) == 1
    assert workflow.steps[0].name == "Test Step"
    assert workflow.created_by == user_id
    assert workflow.description is None  # Default value
    assert workflow.enabled is True  # Default value
    assert workflow.updated_at is None  # Default value
    
    # Test with all fields
    workflow_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    updated_at = datetime.now().isoformat()
    
    workflow_data = {
        "id": workflow_id,
        "name": "Complete Workflow",
        "description": "A complete workflow with all fields",
        "enabled": False,
        "steps": [step],
        "created_at": created_at,
        "updated_at": updated_at,
        "created_by": user_id
    }
    workflow = Workflow(**workflow_data)
    
    assert workflow.id == workflow_id
    assert workflow.name == "Complete Workflow"
    assert workflow.description == "A complete workflow with all fields"
    assert workflow.enabled is False
    assert len(workflow.steps) == 1
    assert workflow.steps[0].name == "Test Step"
    assert workflow.created_at == created_at
    assert workflow.updated_at == updated_at
    assert workflow.created_by == user_id
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        Workflow(steps=[step], created_by=user_id)  # Missing name
    
    with pytest.raises(ValidationError):
        Workflow(name="Test Workflow", created_by=user_id)  # Missing steps
    
    with pytest.raises(ValidationError):
        Workflow(name="Test Workflow", steps=[step])  # Missing created_by

# Test WorkflowExecution model
def test_workflow_execution_model():
    workflow_id = str(uuid.uuid4())
    
    # Test with minimum required fields
    execution_data = {
        "workflow_id": workflow_id,
        "status": "running"
    }
    execution = WorkflowExecution(**execution_data)
    
    assert execution.workflow_id == workflow_id
    assert execution.status == "running"
    assert execution.end_time is None  # Default value
    assert execution.result is None  # Default value
    assert execution.error is None  # Default value
    
    # Test with all fields
    execution_id = str(uuid.uuid4())
    start_time = datetime.now().isoformat()
    end_time = datetime.now().isoformat()
    
    execution_data = {
        "id": execution_id,
        "workflow_id": workflow_id,
        "status": "completed",
        "start_time": start_time,
        "end_time": end_time,
        "result": {"output": "success", "data": {"value": 100}},
        "error": None
    }
    execution = WorkflowExecution(**execution_data)
    
    assert execution.id == execution_id
    assert execution.workflow_id == workflow_id
    assert execution.status == "completed"
    assert execution.start_time == start_time
    assert execution.end_time == end_time
    assert execution.result == {"output": "success", "data": {"value": 100}}
    assert execution.error is None
    
    # Test with error
    execution_data = {
        "id": execution_id,
        "workflow_id": workflow_id,
        "status": "failed",
        "start_time": start_time,
        "end_time": end_time,
        "result": None,
        "error": "Workflow execution failed: Invalid condition"
    }
    execution = WorkflowExecution(**execution_data)
    
    assert execution.status == "failed"
    assert execution.result is None
    assert execution.error == "Workflow execution failed: Invalid condition"
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        WorkflowExecution(status="running")  # Missing workflow_id
    
    with pytest.raises(ValidationError):
        WorkflowExecution(workflow_id=workflow_id)  # Missing status
