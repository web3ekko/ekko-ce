import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.routes.settings import router as settings_router, set_js
from app.models import Settings, GeneralSettings, NotificationSettings, NotificationChannel, APISettings, NodeSettings, AppearanceSettings, AccountSettings

# Mock data
MOCK_SETTINGS = {
    "id": "user_settings",
    "general": {
        "api_endpoint": "http://localhost:8000",
        "refresh_interval": 30,
        "time_format": "24h",
        "debug_mode": False
    },
    "notifications": {
        "channels": [
            {
                "type": "email",
                "url": "mailto://user:password@example.com",
                "enabled": True
            },
            {
                "type": "slack",
                "url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
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

# Mock JetStream and KV store
class MockKV:
    def __init__(self, data=None):
        self.data = data or {}
        
    async def get(self, key):
        if key in self.data:
            return AsyncMock(value=json.dumps(self.data[key]).encode())
        raise Exception(f"Key {key} not found")
        
    async def put(self, key, value):
        self.data[key] = json.loads(value)
        return True
        
    async def keys(self):
        return list(self.data.keys())
        
    async def delete(self, key):
        if key in self.data:
            del self.data[key]
            return True
        return False

class MockJS:
    def __init__(self, kv_data=None):
        self.kv_data = kv_data or {}
        self.kv_stores = {}
        
    async def key_value(self, bucket):
        if bucket not in self.kv_stores:
            self.kv_stores[bucket] = MockKV({
                "user_settings": MOCK_SETTINGS
            } if bucket == "settings" else {})
        return self.kv_stores[bucket]
        
    async def create_key_value(self, bucket):
        self.kv_stores[bucket] = MockKV()
        return self.kv_stores[bucket]
        
    async def publish(self, subject, data):
        return True

@pytest.fixture
def client():
    # Set up mock JetStream
    mock_js = MockJS()
    set_js(mock_js)
    
    # Return test client
    with TestClient(app) as client:
        yield client

# Test getting all settings
def test_get_settings(client):
    response = client.get("/settings/")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user_settings"
    assert data["general"]["api_endpoint"] == "http://localhost:8000"
    assert data["notifications"]["email_notifications"] is True
    assert data["api"]["api_key"] == "ekko_api_key_placeholder"
    assert data["nodes"]["default_network"] == "avalanche"
    assert data["appearance"]["theme_color"] == "#228be6"
    assert data["account"]["username"] == "ekko_admin"

# Test updating all settings
def test_update_settings(client):
    updated_settings = MOCK_SETTINGS.copy()
    updated_settings["general"]["api_endpoint"] = "http://api.ekko.chain"
    updated_settings["general"]["refresh_interval"] = 60
    
    response = client.put("/settings/", json=updated_settings)
    assert response.status_code == 200
    data = response.json()
    assert data["general"]["api_endpoint"] == "http://api.ekko.chain"
    assert data["general"]["refresh_interval"] == 60

# Test getting general settings
def test_get_general_settings(client):
    response = client.get("/settings/general")
    assert response.status_code == 200
    data = response.json()
    assert data["api_endpoint"] == "http://localhost:8000"
    assert data["refresh_interval"] == 30
    assert data["time_format"] == "24h"
    assert data["debug_mode"] is False

# Test updating general settings
def test_update_general_settings(client):
    updated_general = {
        "api_endpoint": "http://api.ekko.chain",
        "refresh_interval": 60,
        "time_format": "12h",
        "debug_mode": True
    }
    
    response = client.put("/settings/general", json=updated_general)
    assert response.status_code == 200
    data = response.json()
    assert data["api_endpoint"] == "http://api.ekko.chain"
    assert data["refresh_interval"] == 60
    assert data["time_format"] == "12h"
    assert data["debug_mode"] is True

# Test getting notification settings
def test_get_notification_settings(client):
    response = client.get("/settings/notifications")
    assert response.status_code == 200
    data = response.json()
    assert len(data["channels"]) == 2
    assert data["channels"][0]["type"] == "email"
    assert data["channels"][0]["enabled"] is True
    assert data["alert_threshold"] == "medium"

# Test updating notification settings
def test_update_notification_settings(client):
    updated_notifications = {
        "channels": [
            {
                "type": "email",
                "url": "mailto://new_user:new_password@example.com",
                "enabled": True
            },
            {
                "type": "slack",
                "url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
                "enabled": True
            },
            {
                "type": "telegram",
                "url": "tgram://123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "enabled": True
            }
        ],
        "alert_threshold": "high"
    }
    
    response = client.put("/settings/notifications", json=updated_notifications)
    assert response.status_code == 200
    data = response.json()
    assert len(data["channels"]) == 3
    assert data["channels"][0]["url"] == "mailto://new_user:new_password@example.com"
    assert data["channels"][1]["enabled"] is True
    assert data["channels"][2]["type"] == "telegram"
    assert data["alert_threshold"] == "high"

# Test notification channel testing
@patch('app.utils.notification.notification_service.test_channels')
def test_notification_channel_testing(mock_test_channels, client):
    # Setup mock
    mock_test_channels.return_value = {
        "mailto://user:password@example.com": {"success": True},
        "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX": {"success": False, "error": "Invalid webhook"}
    }
    
    test_request = {
        "channels": [
            {
                "type": "email",
                "url": "mailto://user:password@example.com",
                "enabled": True
            },
            {
                "type": "slack",
                "url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
                "enabled": True
            }
        ]
    }
    
    response = client.post("/settings/notifications/test", json=test_request)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    assert data["results"]["mailto://user:password@example.com"]["success"] is True

# Test sending notifications
@patch('app.utils.notification.notification_service.send_notification')
def test_send_notification(mock_send_notification, client):
    # Setup mock
    mock_send_notification.return_value = {
        "success": True,
        "channels_count": 2,
        "title": "Test Notification",
        "body": "This is a test notification"
    }
    
    notification_request = {
        "title": "Test Notification",
        "body": "This is a test notification",
        "channels": [
            {
                "type": "email",
                "url": "mailto://user:password@example.com",
                "enabled": True
            }
        ]
    }
    
    response = client.post("/settings/notifications/send", json=notification_request)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["title"] == "Test Notification"

# Test getting API settings
def test_get_api_settings(client):
    response = client.get("/settings/api")
    assert response.status_code == 200
    data = response.json()
    assert data["api_key"] == "ekko_api_key_placeholder"

# Test updating API settings
def test_update_api_settings(client):
    updated_api = {
        "api_key": "new_api_key_123456"
    }
    
    response = client.put("/settings/api", json=updated_api)
    assert response.status_code == 200
    data = response.json()
    assert data["api_key"] == "new_api_key_123456"

# Test getting node settings
def test_get_node_settings(client):
    response = client.get("/settings/nodes")
    assert response.status_code == 200
    data = response.json()
    assert data["default_network"] == "avalanche"
    assert data["node_timeout"] == 10
    assert data["max_retries"] == 3
    assert data["auto_switch_nodes"] is True
    assert data["health_monitoring"] is True

# Test updating node settings
def test_update_node_settings(client):
    updated_nodes = {
        "default_network": "ethereum",
        "node_timeout": 15,
        "max_retries": 5,
        "auto_switch_nodes": False,
        "health_monitoring": False
    }
    
    response = client.put("/settings/nodes", json=updated_nodes)
    assert response.status_code == 200
    data = response.json()
    assert data["default_network"] == "ethereum"
    assert data["node_timeout"] == 15
    assert data["max_retries"] == 5
    assert data["auto_switch_nodes"] is False
    assert data["health_monitoring"] is False

# Test getting appearance settings
def test_get_appearance_settings(client):
    response = client.get("/settings/appearance")
    assert response.status_code == 200
    data = response.json()
    assert data["theme_color"] == "#228be6"
    assert data["layout_type"] == "sidebar"
    assert data["theme_mode"] == "light"
    assert data["compact_mode"] is False

# Test updating appearance settings
def test_update_appearance_settings(client):
    updated_appearance = {
        "theme_color": "#FF5733",
        "layout_type": "decked",
        "theme_mode": "dark",
        "compact_mode": True
    }
    
    response = client.put("/settings/appearance", json=updated_appearance)
    assert response.status_code == 200
    data = response.json()
    assert data["theme_color"] == "#FF5733"
    assert data["layout_type"] == "decked"
    assert data["theme_mode"] == "dark"
    assert data["compact_mode"] is True

# Test getting account settings
def test_get_account_settings(client):
    response = client.get("/settings/account")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "ekko_admin"
    assert data["email"] == "admin@ekko.chain"

# Test updating account settings
def test_update_account_settings(client):
    updated_account = {
        "username": "new_admin",
        "email": "new_admin@ekko.chain"
    }
    
    response = client.put("/settings/account", json=updated_account)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "new_admin"
    assert data["email"] == "new_admin@ekko.chain"

# Test error handling
def test_error_handling(client):
    # Test with invalid data
    invalid_settings = {
        "id": "user_settings",
        "general": {
            "api_endpoint": "http://localhost:8000",
            "refresh_interval": "invalid",  # Should be an integer
            "time_format": "24h"
        }
    }
    
    response = client.put("/settings/general", json=invalid_settings["general"])
    assert response.status_code == 422  # Validation error
