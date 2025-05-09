import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .models import Agent, User
from .auth import get_current_user, get_admin_user

# Create router for agent endpoints
router = APIRouter(prefix="/agents", tags=["agents"])

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
async def publish_event(subject: str, data: Dict[str, Any]):
    """Publish an event to NATS"""
    try:
        await js.publish(subject, json.dumps(data).encode())
        print(f"Published event to {subject}")
    except Exception as e:
        print(f"Error publishing event to {subject}: {e}")

# Agent CRUD operations
@router.get("", response_model=List[Agent])
async def get_agents(
    skip: int = 0, 
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Get all agents with pagination.
    """
    try:
        kv = await jetstream.key_value(bucket="agents")
        keys = await kv.keys()
        agents = []
        
        # Apply pagination
        paginated_keys = keys[skip:skip + limit]
        
        for key in paginated_keys:
            data = await kv.get(key)
            agent_data = json.loads(data.value)
            
            # Filter by created_by if not admin
            if current_user.role != "admin" and agent_data.get("created_by") != current_user.id:
                continue
                
            agents.append(Agent(**agent_data))
        
        return agents
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching agents: {str(e)}")

@router.get("/{agent_id}", response_model=Agent)
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Get a specific agent by ID.
    """
    try:
        kv = await jetstream.key_value(bucket="agents")
        data = await kv.get(agent_id)
        agent_data = json.loads(data.value)
        
        # Check if user has access to this agent
        if current_user.role != "admin" and agent_data.get("created_by") != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this agent")
            
        return Agent(**agent_data)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Agent not found: {str(e)}")

@router.post("", response_model=Agent)
async def create_agent(
    agent: Agent,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Create a new agent.
    """
    try:
        kv = await jetstream.key_value(bucket="agents")
        
        # Set created_by to current user
        agent.created_by = current_user.id
        agent.created_at = datetime.now().isoformat()
        
        # Save to KV store
        await kv.put(agent.id, json.dumps(agent.model_dump()))
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "agent.created", 
            {"id": agent.id, "name": agent.name, "type": agent.type}
        )
        
        return agent
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating agent: {str(e)}")

@router.put("/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: str,
    agent: Agent,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Update an existing agent.
    """
    try:
        if agent_id != agent.id:
            raise HTTPException(status_code=400, detail="Agent ID mismatch")
            
        kv = await jetstream.key_value(bucket="agents")
        
        # Check if agent exists and user has access
        try:
            data = await kv.get(agent_id)
            existing_agent = json.loads(data.value)
            
            if current_user.role != "admin" and existing_agent.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to update this agent")
        except Exception:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Update agent
        agent.updated_at = datetime.now().isoformat()
        await kv.put(agent_id, json.dumps(agent.dict()))
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "agent.updated", 
            {"id": agent.id, "name": agent.name, "type": agent.type}
        )
        
        return agent
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating agent: {str(e)}")

@router.delete("/{agent_id}", response_model=Dict[str, Any])
async def delete_agent(
    agent_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Delete an agent.
    """
    try:
        kv = await js.key_value(bucket="agents")
        
        # Check if agent exists and user has access
        try:
            data = await kv.get(agent_id)
            existing_agent = json.loads(data.value)
            
            if current_user.role != "admin" and existing_agent.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this agent")
        except Exception:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Delete agent
        await kv.delete(agent_id)
        
        # Publish event
        background_tasks.add_task(
            publish_event, 
            "agent.deleted", 
            {"id": agent_id}
        )
        
        return {"status": "deleted", "id": agent_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting agent: {str(e)}")

# Agent control operations
@router.get("/{agent_id}/status", response_model=Dict[str, Any])
async def get_agent_status(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Get the current status of an agent.
    """
    try:
        kv = await js.key_value(bucket="agents")
        
        # Check if agent exists and user has access
        try:
            data = await kv.get(agent_id)
            agent_data = json.loads(data.value)
            
            if current_user.role != "admin" and agent_data.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to access this agent")
                
            # Return status information
            return {
                "id": agent_id,
                "status": agent_data.get("status", "inactive"),
                "last_run": agent_data.get("last_run"),
                "type": agent_data.get("type")
            }
        except Exception:
            raise HTTPException(status_code=404, detail="Agent not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting agent status: {str(e)}")

@router.post("/{agent_id}/start", response_model=Dict[str, Any])
async def start_agent(
    agent_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Start an agent.
    """
    try:
        kv = await js.key_value(bucket="agents")
        
        # Check if agent exists and user has access
        try:
            data = await kv.get(agent_id)
            agent_data = json.loads(data.value)
            
            if current_user.role != "admin" and agent_data.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to control this agent")
                
            # Update agent status
            agent_data["status"] = "active"
            agent_data["updated_at"] = datetime.now().isoformat()
            await kv.put(agent_id, json.dumps(agent_data))
            
            # Publish event to start agent
            background_tasks.add_task(
                publish_event,
                f"agent.start.{agent_id}",
                {
                    "id": agent_id,
                    "type": agent_data.get("type"),
                    "config": agent_data.get("config", {})
                }
            )
            
            return {"id": agent_id, "status": "active", "message": "Agent started successfully"}
        except Exception:
            raise HTTPException(status_code=404, detail="Agent not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting agent: {str(e)}")

@router.post("/{agent_id}/stop", response_model=Dict[str, Any])
async def stop_agent(
    agent_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    jetstream = Depends(get_jetstream)
):
    """
    Stop an agent.
    """
    try:
        kv = await js.key_value(bucket="agents")
        
        # Check if agent exists and user has access
        try:
            data = await kv.get(agent_id)
            agent_data = json.loads(data.value)
            
            if current_user.role != "admin" and agent_data.get("created_by") != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to control this agent")
                
            # Update agent status
            agent_data["status"] = "inactive"
            agent_data["updated_at"] = datetime.now().isoformat()
            await kv.put(agent_id, json.dumps(agent_data))
            
            # Publish event to stop agent
            background_tasks.add_task(
                publish_event,
                f"agent.stop.{agent_id}",
                {"id": agent_id}
            )
            
            return {"id": agent_id, "status": "inactive", "message": "Agent stopped successfully"}
        except Exception:
            raise HTTPException(status_code=404, detail="Agent not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping agent: {str(e)}")
