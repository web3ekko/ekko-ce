import asyncio
import os
import json
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
import nats
from nats.js.api import StreamConfig, ConsumerConfig

# Import models and auth utilities
from .models import Token, User
from .auth import authenticate_user, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

# Import routers
from .workflows import router as workflows_router, init_nats as init_workflows_nats
from .agents import router as agents_router, init_nats as init_agents_nats
from .alert_rules import router as alert_rules_router, init_nats as init_alert_rules_nats

# Global NATS connection
nc = None
js = None

# Background task flag
running = True

# Lifespan context manager to handle startup/shutdown
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
        from .main_extension import ensure_streams
        await ensure_streams()
        
        # Initialize NATS for routers
        init_workflows_nats(nc, js)
        init_agents_nats(nc, js)
        init_alert_rules_nats(nc, js)
        
        # Start background task for processing messages
        from .main import process_messages
        asyncio.create_task(process_messages())
        
        # Ensure admin user exists
        from .main_extension import ensure_admin_user
        await ensure_admin_user()
        
        print("FastAPI service started successfully")
        yield
    finally:
        # Shutdown: stop background processing and close NATS connection
        running = False
        if nc:
            await nc.close()
        print("FastAPI service shut down")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Ekko API",
    description="API for the Ekko blockchain monitoring and management platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication endpoint
@app.post("/api/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(js, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "role": user.role
        }, 
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# Health check endpoint
@app.get("/api/health")
async def health_check():
    if nc and nc.is_connected:
        return {"status": "healthy", "nats_connected": True}
    else:
        return {"status": "unhealthy", "nats_connected": False}, 503

# Include routers
app.include_router(workflows_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(alert_rules_router, prefix="/api")

# Import and include existing routers from main.py
# Note: In a real implementation, you would refactor these into separate files
from .main import app as main_app

# Include routes from main_app
for route in main_app.routes:
    if route.path != "/":  # Skip root path to avoid conflicts
        app.routes.append(route)

# Root endpoint
@app.get("/api")
async def read_root():
    return {"message": "Welcome to Ekko API", "version": "1.0.0"}
