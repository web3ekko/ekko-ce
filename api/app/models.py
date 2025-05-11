from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
import uuid
import re

class Wallet(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    blockchain_symbol: str
    address: str
    name: str
    balance: float = 0.0
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    class Config:
        # This is metadata for the API documentation and validation
        schema_extra = {
            "description": "Wallet information with unique address per blockchain"
        }
    
    @validator('address')
    def address_valid_for_blockchain(cls, v, values):
        # Basic validation based on blockchain
        blockchain = values.get('blockchain_symbol', '')
        
        if blockchain in ['ETH', 'MATIC', 'AVAX']:
            # Ethereum-style address for ETH, MATIC, and AVAX C-Chain
            if not re.match(r'^0x[a-fA-F0-9]{40}$', v):
                raise ValueError(f'Invalid address format for {blockchain}')
        elif blockchain == 'BTC':
            # Basic Bitcoin address format
            if not re.match(r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$', v):
                raise ValueError('Invalid Bitcoin address format')
                
        return v

class Alert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    message: str
    time: str
    status: str
    icon: Optional[str] = None
    priority: Optional[str] = None
    related_wallet_id: Optional[str] = None

class WalletBalance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wallet_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    balance: float
    token_price: Optional[float] = None
    fiat_value: Optional[float] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "user"  # Default role is 'user'

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    full_name: str
    role: str = "user"  # Can be 'user', 'admin', etc.
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "email": "user@example.com",
                "full_name": "John Doe",
                "role": "user",
                "is_active": True,
                "created_at": "2025-05-09T08:15:00.000Z",
                "updated_at": None
            }
        }

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

# Workflow models
class WorkflowStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str  # "trigger", "condition", "action"
    config: Dict[str, Any]
    next_steps: List[str] = []

class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    enabled: bool = True
    steps: List[WorkflowStep]
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None
    created_by: str  # user_id

class WorkflowExecution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    status: str  # "running", "completed", "failed"
    start_time: str = Field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Agent models
class Agent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str  # "monitor", "trader", "analyzer"
    config: Dict[str, Any]
    status: str = "inactive"  # "inactive", "active", "error"
    last_run: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None
    created_by: str  # user_id

# Alert rule model
class AlertRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    condition: Dict[str, Any]  # Condition configuration
    action: Dict[str, Any]  # Action to take when condition is met
    enabled: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None
    created_by: str  # user_id

# Settings models
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
