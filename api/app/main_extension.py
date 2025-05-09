import asyncio
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import nats
from nats.js.api import StreamConfig, ConsumerConfig
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Import models and auth utilities
from .models import (
    User, UserCreate, UserUpdate, UserInDB, 
    Wallet, Alert, WalletBalance,
    Token, TokenData
)
from .auth import (
    get_password_hash, verify_password, authenticate_user,
    create_access_token, get_current_user, get_admin_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# User routes
@app.post("/users", response_model=User)
async def create_user(user: UserCreate, background_tasks: BackgroundTasks, current_user: User = Depends(get_admin_user)):
    """
    Create a new user (admin only).
    """
    try:
        # Check if email already exists
        existing_user = await get_user_by_email(user.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        kv = await js.key_value(bucket="users")
        
        # Create new user with hashed password
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(user.password)
        
        user_data = {
            "id": user_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": None,
            "hashed_password": hashed_password
        }
        
        # Store user in KV store
        await kv.put(user_id, json.dumps(user_data))
        
        # Publish event
        background_tasks.add_task(publish_event, "user.created", {
            "id": user_id,
            "email": user.email,
            "role": user.role
        })
        
        # Return user without password
        return User(
            id=user_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=True,
            created_at=user_data["created_at"],
            updated_at=None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

@app.get("/users", response_model=List[User])
async def get_users(current_user: User = Depends(get_admin_user)):
    """
    Get all users (admin only).
    """
    try:
        kv = await js.key_value(bucket="users")
        keys = await kv.keys()
        users = []
        
        for key in keys:
            data = await kv.get(key)
            user_data = json.loads(data.value)
            # Remove hashed_password from response
            if "hashed_password" in user_data:
                del user_data["hashed_password"]
            users.append(User(**user_data))
        
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")

@app.get("/users/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information.
    """
    return current_user

@app.get("/users/{user_id}", response_model=User)
async def get_user_by_id(user_id: str, current_user: User = Depends(get_admin_user)):
    """
    Get user by ID (admin only).
    """
    try:
        kv = await js.key_value(bucket="users")
        data = await kv.get(user_id)
        user_data = json.loads(data.value)
        
        # Remove hashed_password from response
        if "hashed_password" in user_data:
            del user_data["hashed_password"]
            
        return User(**user_data)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")

@app.put("/users/{user_id}", response_model=User)
async def update_user(
    user_id: str, 
    user_update: UserUpdate, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_admin_user)
):
    """
    Update user (admin only).
    """
    try:
        kv = await js.key_value(bucket="users")
        
        # Check if user exists
        try:
            data = await kv.get(user_id)
            user_data = json.loads(data.value)
        except Exception:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update fields if provided
        if user_update.email is not None:
            user_data["email"] = user_update.email
        if user_update.full_name is not None:
            user_data["full_name"] = user_update.full_name
        if user_update.role is not None:
            user_data["role"] = user_update.role
            
        user_data["updated_at"] = datetime.now().isoformat()
        
        # Save updated user
        await kv.put(user_id, json.dumps(user_data))
        
        # Publish event
        background_tasks.add_task(publish_event, "user.updated", {
            "id": user_id,
            "email": user_data["email"],
            "role": user_data["role"]
        })
        
        # Return updated user without password
        if "hashed_password" in user_data:
            del user_data["hashed_password"]
            
        return User(**user_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")

@app.delete("/users/{user_id}")
async def delete_user(user_id: str, background_tasks: BackgroundTasks, current_user: User = Depends(get_admin_user)):
    """
    Delete user (admin only).
    """
    try:
        # Prevent deleting yourself
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
            
        kv = await js.key_value(bucket="users")
        
        # Check if user exists
        try:
            data = await kv.get(user_id)
            user_data = json.loads(data.value)
        except Exception:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete user
        await kv.delete(user_id)
        
        # Publish event
        background_tasks.add_task(publish_event, "user.deleted", {"id": user_id})
        
        return {"status": "deleted", "id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")

# Authentication routes
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user and return JWT token.
    """
    user = await authenticate_user(js, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# Helper function to get user by email
async def get_user_by_email(email: str) -> Optional[User]:
    try:
        kv = await js.key_value(bucket="users")
        keys = await kv.keys()
        
        for key in keys:
            data = await kv.get(key)
            user_data = json.loads(data.value)
            if user_data.get("email") == email:
                # Remove hashed_password from response
                if "hashed_password" in user_data:
                    del user_data["hashed_password"]
                return User(**user_data)
        
        return None
    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None

# Wallet balance routes
@app.post("/wallet-balances", response_model=WalletBalance)
async def create_wallet_balance(
    wallet_balance: WalletBalance, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new wallet balance record.
    """
    try:
        kv = await js.key_value(bucket="wallet_balances")
        
        # Check if wallet exists
        wallet_kv = await js.key_value(bucket="wallets")
        try:
            await wallet_kv.get(wallet_balance.wallet_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Store wallet balance
        balance_id = wallet_balance.id
        await kv.put(balance_id, json.dumps(wallet_balance.dict()))
        
        # Publish event
        background_tasks.add_task(publish_event, "wallet_balance.created", wallet_balance.dict())
        
        return wallet_balance
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating wallet balance: {str(e)}")

@app.get("/wallet-balances/{wallet_id}", response_model=List[WalletBalance])
async def get_wallet_balances(
    wallet_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """
    Get wallet balance history for a specific wallet.
    """
    try:
        kv = await js.key_value(bucket="wallet_balances")
        keys = await kv.keys()
        balances = []
        
        # Filter balances by wallet_id and sort by timestamp (newest first)
        for key in keys:
            data = await kv.get(key)
            balance_data = json.loads(data.value)
            if balance_data.get("wallet_id") == wallet_id:
                balances.append(WalletBalance(**balance_data))
        
        # Sort by timestamp (newest first)
        balances.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply limit
        return balances[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching wallet balances: {str(e)}")

# Ensure streams and KV stores exist for new features
async def ensure_additional_streams():
    """
    Ensure all required JetStream streams and KV stores exist.
    """
    global js
    
    # Create KV stores if they don't exist
    try:
        await js.key_value(bucket="users")
    except Exception:
        await js.create_key_value(bucket="users")
    
    try:
        await js.key_value(bucket="wallet_balances")
    except Exception:
        await js.create_key_value(bucket="wallet_balances")
    
    try:
        await js.key_value(bucket="workflows")
    except Exception:
        await js.create_key_value(bucket="workflows")
    
    try:
        await js.key_value(bucket="workflow_executions")
    except Exception:
        await js.create_key_value(bucket="workflow_executions")
    
    try:
        await js.key_value(bucket="agents")
    except Exception:
        await js.create_key_value(bucket="agents")
    
    try:
        await js.key_value(bucket="alert_rules")
    except Exception:
        await js.create_key_value(bucket="alert_rules")
    
    # Create streams if they don't exist
    try:
        await js.stream_info("users")
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name="users",
                subjects=["user.*"],
                retention="limits",
                max_msgs=-1,
                storage="file",
                discard="old",
            )
        )
    
    try:
        await js.stream_info("wallet_balances")
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name="wallet_balances",
                subjects=["wallet_balance.*"],
                retention="limits",
                max_msgs=-1,
                storage="file",
                discard="old",
            )
        )
        
    try:
        await js.stream_info("workflows")
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name="workflows",
                subjects=["workflow.*"],
                retention="limits",
                max_msgs=-1,
                storage="file",
                discard="old",
            )
        )
    
    try:
        await js.stream_info("agents")
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name="agents",
                subjects=["agent.*"],
                retention="limits",
                max_msgs=-1,
                storage="file",
                discard="old",
            )
        )
    
    try:
        await js.stream_info("alert_rules")
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name="alert_rules",
                subjects=["alert_rule.*"],
                retention="limits",
                max_msgs=-1,
                storage="file",
                discard="old",
            )
        )

# Update the ensure_streams function to include the new streams
async def ensure_streams():
    global js
    
    # Create KV stores if they don't exist
    try:
        await js.key_value(bucket="wallets")
    except Exception:
        await js.create_key_value(bucket="wallets")
    
    try:
        await js.key_value(bucket="alerts")
    except Exception:
        await js.create_key_value(bucket="alerts")
    
    try:
        await js.key_value(bucket="users")
    except Exception:
        await js.create_key_value(bucket="users")
    
    try:
        await js.key_value(bucket="wallet_balances")
    except Exception:
        await js.create_key_value(bucket="wallet_balances")
    
    # Create streams if they don't exist
    try:
        await js.stream_info("transactions")
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name="transactions",
                subjects=["tx.*"],
                retention="limits",
                max_msgs=-1,
                storage="file",
                discard="old",
            )
        )
    
    try:
        await js.stream_info("users")
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name="users",
                subjects=["user.*"],
                retention="limits",
                max_msgs=-1,
                storage="file",
                discard="old",
            )
        )
    
    try:
        await js.stream_info("wallet_balances")
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name="wallet_balances",
                subjects=["wallet_balance.*"],
                retention="limits",
                max_msgs=-1,
                storage="file",
                discard="old",
            )
        )

# Create admin user on startup if none exists
async def ensure_admin_user():
    """
    Ensure at least one admin user exists.
    """
    try:
        kv = await js.key_value(bucket="users")
        keys = await kv.keys()
        
        # Check if any admin users exist
        admin_exists = False
        for key in keys:
            data = await kv.get(key)
            user_data = json.loads(data.value)
            if user_data.get("role") == "admin":
                admin_exists = True
                break
        
        # Create default admin if none exists
        if not admin_exists:
            admin_email = os.getenv("ADMIN_EMAIL", "admin@ekko.com")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")  # Change in production!
            
            user_id = str(uuid.uuid4())
            hashed_password = get_password_hash(admin_password)
            
            user_data = {
                "id": user_id,
                "email": admin_email,
                "full_name": "Admin User",
                "role": "admin",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": None,
                "hashed_password": hashed_password
            }
            
            await kv.put(user_id, json.dumps(user_data))
            print(f"Created default admin user: {admin_email}")
    except Exception as e:
        print(f"Error ensuring admin user: {e}")

# Update lifespan to include admin user creation
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to NATS and start background processing
    global nc, js, running
    
    # Get NATS URL from environment variable
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    
    try:
        # Connect to NATS
        print(f"Connecting to NATS at {nats_url}")
        nc = await nats.connect(nats_url)
        js = nc.jetstream()
        
        # Ensure streams exist
        await ensure_streams()
        
        # Ensure admin user exists
        await ensure_admin_user()
        
        # Start background task for processing messages
        asyncio.create_task(process_messages())
        
        print("FastAPI service started successfully")
        yield
    finally:
        # Shutdown: stop background processing and close NATS connection
        running = False
        if nc:
            await nc.close()
        print("FastAPI service shut down")
