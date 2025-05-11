import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .models import Workflow, WorkflowStep, WorkflowExecution, User
from .auth import get_current_user, get_admin_user
from .events import publish_event

# Create router for workflow endpoints
router = APIRouter(prefix="/workflows", tags=["workflows"])

# Global variables for NATS access
# These will be set when the module is imported
nc = None
js = None

# Dependency to get JetStream instance
def get_jetstream():
    """Dependency to get JetStream instance"""
    # Return the global JetStream instance without requiring a query parameter
    from fastapi import Query
    _ = Query(None, include_in_schema=False)  # This prevents FastAPI from expecting a query parameter
    return js

def init_nats(nats_connection, jetstream):
    """Initialize NATS connection for this module"""
    global nc, js
    nc = nats_connection
    js = jetstream

# Helper function to publish events
# Helper function to publish events is now imported from app.events

# Workflow CRUD operations
@router.get("", response_model=List[Workflow])
async def get_workflows(
    skip: int = 0, 
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Get all workflows with pagination.
    """
    try:
        kv = await jetstream.key_value(bucket="workflows")
        keys = await kv.keys()
        workflows = []
        
        # Apply pagination
        paginated_keys = keys[skip:skip + limit]
        
        for key in paginated_keys:
            data = await kv.get(key)
            workflow_data = json.loads(data.value)
            
            # Filter by created_by if not admin
            if current_user.role != "admin" and workflow_data.get("created_by") != current_user.id:
                continue
                
            workflows.append(Workflow(**workflow_data))
        
        return workflows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching workflows: {str(e)}")

@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Get a specific workflow by ID.
    """
    try:
        kv = await jetstream.key_value(bucket="workflows")
        data = await kv.get(workflow_id)
        workflow_data = json.loads(data.value)
        
        # Check if user has access to this workflow
        if current_user.role != "admin" and workflow_data.get("created_by") != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this workflow")
            
        return Workflow(**workflow_data)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {str(e)}")

@router.post("", response_model=Workflow)
async def create_workflow(
    workflow: Workflow,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Create a new workflow.
    """
    try:
        kv = await jetstream.key_value(bucket="workflows")
        
        # Set created_by to current user
        workflow.created_by = current_user.id
        workflow.created_at = datetime.now().isoformat()
        
        # Save to KV store
        await kv.put(workflow.id, json.dumps(workflow.model_dump()))
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "workflow.created", 
            {"id": workflow.id, "name": workflow.name}
        )
        
        return workflow
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating workflow: {str(e)}")

@router.put("/{workflow_id}", response_model=Workflow)
async def update_workflow(
    workflow_id: str,
    workflow: Workflow,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Update an existing workflow.
    """
    try:
        if workflow_id != workflow.id:
            raise HTTPException(status_code=400, detail="Workflow ID mismatch")
            
        kv = await jetstream.key_value(bucket="workflows")
        
        # Check if workflow exists and user has access
        try:
            data = await kv.get(workflow_id)
            existing_workflow = json.loads(data.value)
            
            if current_user.role != "admin" and existing_workflow.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to update this workflow")
        except Exception:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Update workflow
        workflow.updated_at = datetime.now().isoformat()
        await kv.put(workflow_id, json.dumps(workflow.dict()))
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "workflow.updated", 
            {"id": workflow.id, "name": workflow.name}
        )
        
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating workflow: {str(e)}")

@router.delete("/{workflow_id}", response_model=Dict[str, Any])
async def delete_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Delete a workflow.
    """
    try:
        kv = await jetstream.key_value(bucket="workflows")
        
        # Check if workflow exists and user has access
        try:
            data = await kv.get(workflow_id)
            existing_workflow = json.loads(data.value)
            
            if current_user.role != "admin" and existing_workflow.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this workflow")
        except Exception:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Delete workflow
        await kv.delete(workflow_id)
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "workflow.deleted", 
            {"id": workflow_id}
        )
        
        return {"status": "deleted", "id": workflow_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting workflow: {str(e)}")

# Workflow execution
@router.post("/{workflow_id}/execute", response_model=WorkflowExecution)
async def execute_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Execute a workflow.
    """
    try:
        # Get the workflow
        workflow_kv = await jetstream.key_value(bucket="workflows")
        
        try:
            data = await workflow_kv.get(workflow_id)
            workflow_data = json.loads(data.value)
            
            # Check if user has access
            if current_user.role != "admin" and workflow_data.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to execute this workflow")
                
            # Check if workflow is enabled
            if not workflow_data.get("enabled", True):
                raise HTTPException(status_code=400, detail="Workflow is disabled")
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Workflow not found: {str(e)}")
        
        # Create execution record
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            status="running",
            start_time=datetime.now().isoformat()
        )
        
        # Save execution record
        executions_kv = await jetstream.key_value(bucket="workflow_executions")
        await executions_kv.put(execution_id, json.dumps(execution.model_dump()))
        
        # Publish event to trigger workflow execution
        background_tasks.add_task(
            publish_event,
            f"workflow.execute.{workflow_id}",
            {
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "user_id": current_user.id
            }
        )
        
        return execution
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing workflow: {str(e)}")

@router.get("/{workflow_id}/executions", response_model=List[WorkflowExecution])
async def get_workflow_executions(
    workflow_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Get execution history for a workflow.
    """
    try:
        # Check if user has access to the workflow
        workflow_kv = await js.key_value(bucket="workflows")
        
        try:
            data = await workflow_kv.get(workflow_id)
            workflow_data = json.loads(data.value)
            
            if current_user.role != "admin" and workflow_data.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to access this workflow")
        except Exception:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Get executions
        executions_kv = await jetstream.key_value(bucket="workflow_executions")
        keys = await executions_kv.keys()
        executions = []
        
        # Filter and paginate
        for key in keys:
            data = await executions_kv.get(key)
            execution_data = json.loads(data.value)
            
            if execution_data.get("workflow_id") == workflow_id:
                executions.append(WorkflowExecution(**execution_data))
        
        # Sort by start_time descending
        executions.sort(key=lambda x: x.start_time, reverse=True)
        
        # Apply pagination
        paginated_executions = executions[skip:skip + limit]
        
        return paginated_executions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching workflow executions: {str(e)}")

@router.get("/{workflow_id}/executions/{execution_id}", response_model=WorkflowExecution)
async def get_workflow_execution(
    workflow_id: str,
    execution_id: str,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Get details of a specific workflow execution.
    """
    try:
        # Check if user has access to the workflow
        workflow_kv = await js.key_value(bucket="workflows")
        
        try:
            data = await workflow_kv.get(workflow_id)
            workflow_data = json.loads(data.value)
            
            if current_user.role != "admin" and workflow_data.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to access this workflow")
        except Exception:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # Get execution
        executions_kv = await jetstream.key_value(bucket="workflow_executions")
        
        try:
            data = await executions_kv.get(execution_id)
            execution_data = json.loads(data.value)
            
            # Verify this execution belongs to the specified workflow
            if execution_data.get("workflow_id") != workflow_id:
                raise HTTPException(status_code=404, detail="Execution not found for this workflow")
                
            return WorkflowExecution(**execution_data)
        except Exception:
            raise HTTPException(status_code=404, detail="Execution not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching workflow execution: {str(e)}")
