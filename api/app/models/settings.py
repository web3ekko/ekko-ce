from typing import Optional, List
from pydantic import BaseModel, validator, Field
import re

class GeneralSettings(BaseModel):
    api_endpoint: str
    refresh_interval: int
    time_format: str
    debug_mode: bool = False

class NotificationChannel(BaseModel):
    type: str
    url: str
    enabled: bool = True
    
    @validator('url')
    def validate_url(cls, v, values):
        channel_type = values.get('type')
        
        if channel_type == 'email':
            # Basic email validation
            if not re.match(r'^mailto://[^@]+@[^@]+\.[^@]+$', v):
                raise ValueError('Invalid email URL format. Must be mailto://user:password@domain.com')
        
        elif channel_type == 'slack':
            # Basic Slack webhook validation
            if not v.startswith('https://hooks.slack.com/') and not v.startswith('slack://'):
                raise ValueError('Invalid Slack webhook URL format')
        
        elif channel_type == 'telegram':
            # Basic Telegram validation
            if not v.startswith('tgram://') and not v.startswith('telegram://'):
                raise ValueError('Invalid Telegram URL format. Must start with tgram:// or telegram://')
        
        return v

class NotificationSettings(BaseModel):
    channels: List[NotificationChannel] = Field(default_factory=list)
    alert_threshold: str = "medium"

class APISettings(BaseModel):
    api_key: str

class NodeSettings(BaseModel):
    default_network: str
    node_timeout: int
    max_retries: int
    auto_switch_nodes: bool = True
    health_monitoring: bool = True

class AppearanceSettings(BaseModel):
    theme_color: str = "#228be6"
    layout_type: str = "sidebar"
    theme_mode: str = "light"
    compact_mode: bool = False

class AccountSettings(BaseModel):
    username: str
    email: str
    
class Settings(BaseModel):
    id: str = "user_settings"
    general: GeneralSettings
    notifications: NotificationSettings
    api: APISettings
    nodes: NodeSettings
    appearance: AppearanceSettings
    account: AccountSettings
