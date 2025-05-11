import json
import os
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
# Import settings classes directly from the models.py file
from app.models import (
    Settings, GeneralSettings, NotificationSettings, NotificationChannel,
    APISettings, NodeSettings, AppearanceSettings, AccountSettings
)
from app.utils.notification import notification_service
from app.events import publish_event

# Create router
router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses={404: {"description": "Not found"}},
)

# Global reference to JS (JetStream) - will be set when adding the router to the app
js = None

# Set the JetStream reference
def set_js(jetstream):
    global js
    js = jetstream

# Helper function to get settings
async def get_settings_from_kv():
    try:
        kv = await js.key_value(bucket="settings")
        data = await kv.get("user_settings")
        return json.loads(data.value)
    except Exception:
        # Return default settings if not found
        return {
            "id": "user_settings",
            "general": {
                "api_endpoint": os.getenv("API_ENDPOINT", "http://localhost:8000"),
                "refresh_interval": os.getenv("REFRESH_INTERVAL", 30),
                "time_format": os.getenv("TIME_FORMAT", "24h"),
                "debug_mode": os.getenv("DEBUG_MODE", False)
            },
            "notifications": {
                "channels": [
                    {
                        "type": "email",
                        "url": "mailto://user:password@example.com",
                        "enabled": False
                    }
                ],
                "alert_threshold": "medium"
            },
            "api": {
                "api_key": "ekko_api_key_placeholder"
            },
            "nodes": {
                "default_network": "avalanche",
                "node_timeout": 10,
                "max_retries": 3,
                "auto_switch_nodes": True,
                "health_monitoring": True
            },
            "appearance": {
                "theme_color": "#228be6",
                "layout_type": "sidebar",
                "theme_mode": "light",
                "compact_mode": False
            },
            "account": {
                "username": "ekko_admin",
                "email": "admin@ekko.chain"
            }
        }

# Get all settings
@router.get("/", response_model=Settings)
async def get_settings():
    try:
        settings_data = await get_settings_from_kv()
        return Settings(**settings_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching settings: {str(e)}")

# Update all settings
@router.put("/", response_model=Settings)
async def update_settings(settings: Settings, background_tasks: BackgroundTasks):
    try:
        kv = await js.key_value(bucket="settings")
        await kv.put("user_settings", json.dumps(settings.dict()))
        
        # Publish event about settings update using centralized event system
        background_tasks.add_task(publish_event, "settings.updated", settings.dict(), ignore_errors=True)
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}")

# Get general settings
@router.get("/general", response_model=GeneralSettings)
async def get_general_settings():
    try:
        settings_data = await get_settings_from_kv()
        return GeneralSettings(**settings_data["general"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching general settings: {str(e)}")

# Update general settings
@router.put("/general", response_model=GeneralSettings)
async def update_general_settings(settings: GeneralSettings, background_tasks: BackgroundTasks):
    try:
        settings_data = await get_settings_from_kv()
        settings_data["general"] = settings.dict()
        
        kv = await js.key_value(bucket="settings")
        await kv.put("user_settings", json.dumps(settings_data))
        
        # Publish event about settings update
        background_tasks.add_task(publish_event, "settings.general.updated", settings.dict(), ignore_errors=True)
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating general settings: {str(e)}")

# Models for notification endpoints
class NotificationTestRequest(BaseModel):
    channels: List[NotificationChannel]

class NotificationSendRequest(BaseModel):
    title: str
    body: str
    channels: List[NotificationChannel] = None

# Get notification settings
@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings():
    try:
        settings_data = await get_settings_from_kv()
        return NotificationSettings(**settings_data["notifications"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notification settings: {str(e)}")

# Update notification settings
@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(settings: NotificationSettings, background_tasks: BackgroundTasks):
    try:
        settings_data = await get_settings_from_kv()
        settings_data["notifications"] = settings.dict()
        
        kv = await js.key_value(bucket="settings")
        await kv.put("user_settings", json.dumps(settings_data))
        
        # Update notification service with new channels
        notification_service.add_channels(settings.channels)
        
        # Publish event about settings update
        background_tasks.add_task(publish_event, "settings.notifications.updated", settings.dict(), ignore_errors=True)
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating notification settings: {str(e)}")

# Test notification channels
@router.post("/notifications/test")
async def test_notification_channels(request: NotificationTestRequest):
    try:
        # Test the provided channels
        results = notification_service.test_channels(request.channels)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing notification channels: {str(e)}")

# Send a notification
@router.post("/notifications/send")
async def send_notification(request: NotificationSendRequest):
    try:
        # If channels are provided, use them; otherwise use configured channels
        if request.channels:
            result = notification_service.send_notification(
                title=request.title,
                body=request.body,
                channels=request.channels
            )
        else:
            # Get channels from settings
            settings_data = await get_settings_from_kv()
            channels = NotificationSettings(**settings_data["notifications"]).channels
            
            # Send notification
            result = notification_service.send_notification(
                title=request.title,
                body=request.body,
                channels=channels
            )
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending notification: {str(e)}")

# Get API settings
@router.get("/api", response_model=APISettings)
async def get_api_settings():
    try:
        settings_data = await get_settings_from_kv()
        return APISettings(**settings_data["api"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching API settings: {str(e)}")

# Update API settings
@router.put("/api", response_model=APISettings)
async def update_api_settings(settings: APISettings, background_tasks: BackgroundTasks):
    try:
        settings_data = await get_settings_from_kv()
        settings_data["api"] = settings.dict()
        
        kv = await js.key_value(bucket="settings")
        await kv.put("user_settings", json.dumps(settings_data))
        
        # Publish event about settings update
        background_tasks.add_task(publish_event, "settings.api.updated", settings.dict(), ignore_errors=True)
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating API settings: {str(e)}")

# Get node settings
@router.get("/nodes", response_model=NodeSettings)
async def get_node_settings():
    try:
        settings_data = await get_settings_from_kv()
        return NodeSettings(**settings_data["nodes"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching node settings: {str(e)}")

# Update node settings
@router.put("/nodes", response_model=NodeSettings)
async def update_node_settings(settings: NodeSettings, background_tasks: BackgroundTasks):
    try:
        settings_data = await get_settings_from_kv()
        settings_data["nodes"] = settings.dict()
        
        kv = await js.key_value(bucket="settings")
        await kv.put("user_settings", json.dumps(settings_data))
        
        # Publish event about settings update
        background_tasks.add_task(publish_event, "settings.nodes.updated", settings.dict(), ignore_errors=True)
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating node settings: {str(e)}")

# Get appearance settings
@router.get("/appearance", response_model=AppearanceSettings)
async def get_appearance_settings():
    try:
        settings_data = await get_settings_from_kv()
        return AppearanceSettings(**settings_data["appearance"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching appearance settings: {str(e)}")

# Update appearance settings
@router.put("/appearance", response_model=AppearanceSettings)
async def update_appearance_settings(settings: AppearanceSettings, background_tasks: BackgroundTasks):
    try:
        settings_data = await get_settings_from_kv()
        settings_data["appearance"] = settings.dict()
        
        kv = await js.key_value(bucket="settings")
        await kv.put("user_settings", json.dumps(settings_data))
        
        # Publish event about settings update
        background_tasks.add_task(publish_event, "settings.appearance.updated", settings.dict(), ignore_errors=True)
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating appearance settings: {str(e)}")

# Get account settings
@router.get("/account", response_model=AccountSettings)
async def get_account_settings():
    try:
        settings_data = await get_settings_from_kv()
        return AccountSettings(**settings_data["account"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching account settings: {str(e)}")

# Update account settings
@router.put("/account", response_model=AccountSettings)
async def update_account_settings(settings: AccountSettings, background_tasks: BackgroundTasks):
    try:
        settings_data = await get_settings_from_kv()
        settings_data["account"] = settings.dict()
        
        kv = await js.key_value(bucket="settings")
        await kv.put("user_settings", json.dumps(settings_data))
        
        # Publish event about settings update
        background_tasks.add_task(publish_event, "settings.account.updated", settings.dict(), ignore_errors=True)
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating account settings: {str(e)}")

# Helper function to publish events is now imported from app.events
