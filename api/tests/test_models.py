import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError

from app.models import (
    Wallet, Alert, WalletBalance, User, UserCreate, UserUpdate, UserInDB,
    Token, TokenData, WorkflowStep, Workflow, WorkflowExecution, Agent, AlertRule
)

# Test Wallet model
def test_wallet_model():
    # Test with minimum required fields
    wallet_data = {
        "blockchain_symbol": "ETH",
        "address": "0x123456789",
        "name": "Test Wallet"
    }
    wallet = Wallet(**wallet_data)
    
    assert wallet.blockchain_symbol == "ETH"
    assert wallet.address == "0x123456789"
    assert wallet.name == "Test Wallet"
    assert wallet.balance == 0.0  # Default value
    assert wallet.status == "active"  # Default value
    assert wallet.created_at is None  # Default value
    assert wallet.updated_at is None  # Default value
    
    # Test with all fields
    wallet_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    wallet_data = {
        "id": wallet_id,
        "blockchain_symbol": "BTC",
        "address": "bc1q123456789",
        "name": "Bitcoin Wallet",
        "balance": 2.5,
        "status": "inactive",
        "created_at": created_at,
        "updated_at": created_at
    }
    wallet = Wallet(**wallet_data)
    
    assert wallet.id == wallet_id
    assert wallet.blockchain_symbol == "BTC"
    assert wallet.address == "bc1q123456789"
    assert wallet.name == "Bitcoin Wallet"
    assert wallet.balance == 2.5
    assert wallet.status == "inactive"
    assert wallet.created_at == created_at
    assert wallet.updated_at == created_at
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        Wallet(address="0x123", name="Test")  # Missing blockchain_symbol
    
    with pytest.raises(ValidationError):
        Wallet(blockchain_symbol="ETH", name="Test")  # Missing address
    
    with pytest.raises(ValidationError):
        Wallet(blockchain_symbol="ETH", address="0x123")  # Missing name

# Test Alert model
def test_alert_model():
    # Test with minimum required fields
    alert_data = {
        "type": "transaction",
        "message": "Test alert",
        "time": "2025-05-09T08:00:00",
        "status": "new"
    }
    alert = Alert(**alert_data)
    
    assert alert.type == "transaction"
    assert alert.message == "Test alert"
    assert alert.time == "2025-05-09T08:00:00"
    assert alert.status == "new"
    assert alert.icon is None  # Default value
    assert alert.priority is None  # Default value
    assert alert.related_wallet_id is None  # Default value
    
    # Test with all fields
    alert_id = str(uuid.uuid4())
    wallet_id = str(uuid.uuid4())
    alert_data = {
        "id": alert_id,
        "type": "price",
        "message": "Price alert",
        "time": "2025-05-09T09:00:00",
        "status": "read",
        "icon": "warning",
        "priority": "high",
        "related_wallet_id": wallet_id
    }
    alert = Alert(**alert_data)
    
    assert alert.id == alert_id
    assert alert.type == "price"
    assert alert.message == "Price alert"
    assert alert.time == "2025-05-09T09:00:00"
    assert alert.status == "read"
    assert alert.icon == "warning"
    assert alert.priority == "high"
    assert alert.related_wallet_id == wallet_id
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        Alert(message="Test", time="2025-05-09T08:00:00", status="new")  # Missing type
    
    with pytest.raises(ValidationError):
        Alert(type="transaction", time="2025-05-09T08:00:00", status="new")  # Missing message
    
    with pytest.raises(ValidationError):
        Alert(type="transaction", message="Test", status="new")  # Missing time
    
    with pytest.raises(ValidationError):
        Alert(type="transaction", message="Test", time="2025-05-09T08:00:00")  # Missing status

# Test WalletBalance model
def test_wallet_balance_model():
    # Test with minimum required fields
    wallet_id = str(uuid.uuid4())
    wallet_balance_data = {
        "wallet_id": wallet_id,
        "balance": 1.5
    }
    wallet_balance = WalletBalance(**wallet_balance_data)
    
    assert wallet_balance.wallet_id == wallet_id
    assert wallet_balance.balance == 1.5
    assert wallet_balance.token_price is None  # Default value
    assert wallet_balance.fiat_value is None  # Default value
    
    # Test with all fields
    balance_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    wallet_balance_data = {
        "id": balance_id,
        "wallet_id": wallet_id,
        "timestamp": timestamp,
        "balance": 2.0,
        "token_price": 1000.0,
        "fiat_value": 2000.0
    }
    wallet_balance = WalletBalance(**wallet_balance_data)
    
    assert wallet_balance.id == balance_id
    assert wallet_balance.wallet_id == wallet_id
    assert wallet_balance.timestamp == timestamp
    assert wallet_balance.balance == 2.0
    assert wallet_balance.token_price == 1000.0
    assert wallet_balance.fiat_value == 2000.0
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        WalletBalance(balance=1.5)  # Missing wallet_id
    
    with pytest.raises(ValidationError):
        WalletBalance(wallet_id=wallet_id)  # Missing balance

# Test User models
def test_user_models():
    # Test UserCreate
    user_create_data = {
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Test User"
    }
    user_create = UserCreate(**user_create_data)
    
    assert user_create.email == "test@example.com"
    assert user_create.password == "password123"
    assert user_create.full_name == "Test User"
    assert user_create.role == "user"  # Default value
    
    # Test UserUpdate
    user_update_data = {
        "email": "updated@example.com",
        "full_name": "Updated User",
        "role": "admin"
    }
    user_update = UserUpdate(**user_update_data)
    
    assert user_update.email == "updated@example.com"
    assert user_update.full_name == "Updated User"
    assert user_update.role == "admin"
    
    # Test User
    user_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    user_data = {
        "id": user_id,
        "email": "user@example.com",
        "full_name": "Regular User",
        "role": "user",
        "is_active": True,
        "created_at": created_at,
        "updated_at": None
    }
    user = User(**user_data)
    
    assert user.id == user_id
    assert user.email == "user@example.com"
    assert user.full_name == "Regular User"
    assert user.role == "user"
    assert user.is_active is True
    assert user.created_at == created_at
    assert user.updated_at is None
    
    # Test UserInDB
    user_in_db_data = {
        "id": user_id,
        "email": "user@example.com",
        "full_name": "Regular User",
        "role": "user",
        "is_active": True,
        "created_at": created_at,
        "updated_at": None,
        "hashed_password": "hashed_password_value"
    }
    user_in_db = UserInDB(**user_in_db_data)
    
    assert user_in_db.id == user_id
    assert user_in_db.email == "user@example.com"
    assert user_in_db.full_name == "Regular User"
    assert user_in_db.role == "user"
    assert user_in_db.is_active is True
    assert user_in_db.created_at == created_at
    assert user_in_db.updated_at is None
    assert user_in_db.hashed_password == "hashed_password_value"
    
    # Test validation - missing required fields
    with pytest.raises(ValidationError):
        UserCreate(password="password123", full_name="Test User")  # Missing email
    
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", full_name="Test User")  # Missing password
    
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", password="password123")  # Missing full_name
    
    with pytest.raises(ValidationError):
        User(email="user@example.com", role="user")  # Missing full_name
    
    with pytest.raises(ValidationError):
        UserInDB(id=user_id, email="user@example.com", full_name="User", role="user")  # Missing hashed_password

# Test Token models
def test_token_models():
    # Test Token
    token_data = {
        "access_token": "jwt_token_value"
    }
    token = Token(**token_data)
    
    assert token.access_token == "jwt_token_value"
    assert token.token_type == "bearer"  # Default value
    
    # Test TokenData
    token_data_obj = TokenData()
    assert token_data_obj.user_id is None
    assert token_data_obj.email is None
    assert token_data_obj.role is None
    
    token_data_with_values = {
        "user_id": "user_id_value",
        "email": "user@example.com",
        "role": "admin"
    }
    token_data_obj = TokenData(**token_data_with_values)
    
    assert token_data_obj.user_id == "user_id_value"
    assert token_data_obj.email == "user@example.com"
    assert token_data_obj.role == "admin"
