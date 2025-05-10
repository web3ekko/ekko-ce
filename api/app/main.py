import asyncio
import os
import json
from typing import Dict, List, Optional, Any, Union
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import nats
from nats.js.api import StreamConfig, ConsumerConfig
from pydantic import BaseModel
from contextlib import asynccontextmanager
from app.routes.settings import router as settings_router, set_js as set_settings_js

# Models
class Wallet(BaseModel):
    id: str
    blockchain_symbol: str
    address: str
    name: str
    balance: float
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class Alert(BaseModel):
    id: str
    type: str
    message: str
    time: str
    status: str
    icon: Optional[str] = None
    priority: Optional[str] = None

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
        await ensure_streams()
        
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

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(settings_router)

# Set JS reference for routers
set_settings_js(js)

# Ensure required JetStream streams and KV stores exist
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
        await js.key_value(bucket="settings")
    except Exception:
        await js.create_key_value(bucket="settings")
    
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

# Background task for processing NATS messages
async def process_messages():
    global nc, js, running
    
    # Create a durable consumer for transactions
    try:
        await js.add_consumer(
            "transactions",
            ConsumerConfig(
                durable_name="api-processor",
                ack_policy="explicit",
                max_deliver=1,
            ),
        )
    except Exception as e:
        print(f"Consumer already exists: {e}")
    
    # Subscribe to transaction messages
    sub = await js.pull_subscribe("tx.*", "api-processor")
    
    print("Started background NATS message processor")
    
    while running:
        try:
            # Fetch messages in batches
            messages = await sub.fetch(10, timeout=1)
            
            for msg in messages:
                # Process the message
                data = json.loads(msg.data.decode())
                print(f"Processing message: {msg.subject}")
                
                # Update wallet data based on transaction
                if msg.subject.startswith("tx."):
                    wallet_id = msg.subject.split(".")[1]
                    await update_wallet_from_tx(wallet_id, data)
                
                # Acknowledge the message
                await msg.ack()
                
        except Exception as e:
            if "timeout" not in str(e).lower():
                print(f"Error processing messages: {e}")
            await asyncio.sleep(1)  # Avoid tight loop on error

# Update wallet data from transaction
async def update_wallet_from_tx(wallet_id: str, tx_data: Dict[str, Any]):
    kv = await js.key_value(bucket="wallets")
    
    try:
        # Get existing wallet data
        data = await kv.get(wallet_id)
        wallet = json.loads(data.value)
        
        # Update wallet with transaction data
        # This is a simple example - customize based on your tx format
        if "amount" in tx_data:
            wallet["balance"] += float(tx_data["amount"])
        
        # Save updated wallet
        await kv.put(wallet_id, json.dumps(wallet))
        print(f"Updated wallet {wallet_id} with new transaction")
        
    except Exception as e:
        print(f"Error updating wallet {wallet_id}: {e}")

# API Routes
@app.get("/")
async def read_root():
    return {"status": "ok", "service": "Ekko API"}

# Wallet routes
@app.get("/wallets", response_model=List[Wallet])
async def get_wallets():
    try:
        kv = await js.key_value(bucket="wallets")
        keys = await kv.keys()
        wallets = []
        
        for key in keys:
            data = await kv.get(key)
            wallets.append(json.loads(data.value))
        
        return wallets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching wallets: {str(e)}")

@app.get("/wallets/{wallet_id}", response_model=Wallet)
async def get_wallet(wallet_id: str):
    try:
        kv = await js.key_value(bucket="wallets")
        data = await kv.get(wallet_id)
        return json.loads(data.value)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Wallet not found: {str(e)}")

@app.post("/wallets", response_model=Wallet)
async def create_wallet(wallet: Wallet, background_tasks: BackgroundTasks):
    try:
        kv = await js.key_value(bucket="wallets")
        await kv.put(wallet.id, json.dumps(wallet.dict()))
        
        # Publish event about new wallet
        background_tasks.add_task(publish_event, f"wallet.created", wallet.dict())
        
        return wallet
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating wallet: {str(e)}")

@app.put("/wallets/{wallet_id}", response_model=Wallet)
async def update_wallet(wallet_id: str, wallet: Wallet, background_tasks: BackgroundTasks):
    try:
        if wallet_id != wallet.id:
            raise HTTPException(status_code=400, detail="Wallet ID mismatch")
            
        kv = await js.key_value(bucket="wallets")
        
        # Check if wallet exists
        try:
            await kv.get(wallet_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Update wallet
        await kv.put(wallet_id, json.dumps(wallet.dict()))
        
        # Publish event
        background_tasks.add_task(publish_event, f"wallet.updated", wallet.dict())
        
        return wallet
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating wallet: {str(e)}")

@app.delete("/wallets/{wallet_id}")
async def delete_wallet(wallet_id: str, background_tasks: BackgroundTasks):
    try:
        kv = await js.key_value(bucket="wallets")
        
        # Get wallet before deleting
        try:
            data = await kv.get(wallet_id)
            wallet = json.loads(data.value)
        except Exception:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Delete wallet
        await kv.delete(wallet_id)
        
        # Publish event
        background_tasks.add_task(publish_event, f"wallet.deleted", {"id": wallet_id})
        
        return {"status": "deleted", "id": wallet_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting wallet: {str(e)}")

# Alert routes
@app.get("/alerts", response_model=List[Alert])
async def get_alerts():
    try:
        kv = await js.key_value(bucket="alerts")
        keys = await kv.keys()
        alerts = []
        
        for key in keys:
            data = await kv.get(key)
            alerts.append(json.loads(data.value))
        
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")

@app.get("/alerts/{alert_id}", response_model=Alert)
async def get_alert(alert_id: str):
    try:
        kv = await js.key_value(bucket="alerts")
        data = await kv.get(alert_id)
        return json.loads(data.value)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Alert not found: {str(e)}")

@app.post("/alerts", response_model=Alert)
async def create_alert(alert: Alert, background_tasks: BackgroundTasks):
    try:
        kv = await js.key_value(bucket="alerts")
        await kv.put(alert.id, json.dumps(alert.dict()))
        
        # Publish event about new alert
        background_tasks.add_task(publish_event, f"alert.created", alert.dict())
        
        return alert
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating alert: {str(e)}")

@app.put("/alerts/{alert_id}", response_model=Alert)
async def update_alert(alert_id: str, alert: Alert, background_tasks: BackgroundTasks):
    try:
        if alert_id != alert.id:
            raise HTTPException(status_code=400, detail="Alert ID mismatch")
            
        kv = await js.key_value(bucket="alerts")
        
        # Check if alert exists
        try:
            await kv.get(alert_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Update alert
        await kv.put(alert_id, json.dumps(alert.dict()))
        
        # Publish event
        background_tasks.add_task(publish_event, f"alert.updated", alert.dict())
        
        return alert
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating alert: {str(e)}")

@app.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, background_tasks: BackgroundTasks):
    try:
        kv = await js.key_value(bucket="alerts")
        
        # Check if alert exists
        try:
            await kv.get(alert_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Delete alert
        await kv.delete(alert_id)
        
        # Publish event
        background_tasks.add_task(publish_event, f"alert.deleted", {"id": alert_id})
        
        return {"status": "deleted", "id": alert_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting alert: {str(e)}")

# Helper function to publish events
async def publish_event(subject: str, data: Dict[str, Any]):
    try:
        await js.publish(subject, json.dumps(data).encode())
        print(f"Published event to {subject}")
    except Exception as e:
        print(f"Error publishing event to {subject}: {e}")

# Health check endpoint
@app.get("/health")
async def health_check():
    if nc and nc.is_connected:
        return {"status": "healthy", "nats_connected": True}
    else:
        return {"status": "unhealthy", "nats_connected": False}, 503
