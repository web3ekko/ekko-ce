from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import uuid

class Wallet(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    blockchain_symbol: str
    address: str
    name: str
    balance: float = 0.0
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

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
