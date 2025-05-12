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
from app.events import set_js as set_events_js, publish_event

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
    related_wallet: Optional[str] = None
    query: Optional[str] = None

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
        
        # Initialize events module with JetStream reference first
        # This is critical for event publishing to work properly
        print("Initializing event publishing system...")
        set_events_js(js)
        
        # Test event publishing
        try:
            await publish_event("system.startup", {"status": "initializing"}, ignore_errors=True)
            print("✅ Event system initialized successfully")
        except Exception as event_error:
            print(f"⚠️ Warning: Event system initialization issue: {event_error}")
        
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
        # Try to get the wallets bucket
        try:
            kv = await js.key_value(bucket="wallets")
        except Exception as bucket_error:
            # If bucket doesn't exist, create it
            if "no bucket" in str(bucket_error).lower() or "not found" in str(bucket_error).lower():
                try:
                    await js.create_key_value(bucket="wallets")
                    kv = await js.key_value(bucket="wallets")
                except Exception as create_error:
                    print(f"Error creating wallets bucket: {create_error}")
                    return []  # Return empty list on error
            else:
                # Other bucket error
                print(f"Error accessing wallets bucket: {bucket_error}")
                return []  # Return empty list on error
                
        # Try to get keys from the bucket
        try:
            print("Getting wallet keys from bucket...")
            keys = await kv.keys()
            print(f"Found {len(keys)} wallet keys: {keys}")
            wallets = []
            
            for key in keys:
                print(f"Loading wallet with key: {key}")
                data = await kv.get(key)
                # KV store returns bytes, properly decode to string first
                if isinstance(data.value, bytes):
                    json_str = data.value.decode('utf-8')
                else:
                    json_str = data.value
                wallet_data = json.loads(json_str)
                print(f"Loaded wallet: {wallet_data.get('id')} - {wallet_data.get('name')}")
                wallets.append(wallet_data)
            
            print(f"Returning {len(wallets)} wallets")
            return wallets
        except Exception as keys_error:
            # Handle "no keys found" error by returning empty list
            if "no keys found" in str(keys_error).lower():
                print("No wallet keys found, returning empty list")
                return []  # Return empty list when no keys found
            else:
                print(f"Error getting wallet keys: {keys_error}")
                return []  # Return empty list on error
    except Exception as e:
        print(f"Unexpected error in get_wallets: {e}")
        return []  # Return empty list instead of error

@app.get("/wallets/{wallet_id}", response_model=Wallet)
async def get_wallet(wallet_id: str):
    try:
        kv = await js.key_value(bucket="wallets")
        data = await kv.get(wallet_id)
        
        # KV store returns bytes, properly decode to string first
        if isinstance(data.value, bytes):
            json_str = data.value.decode('utf-8')
        else:
            json_str = data.value
            
        return json.loads(json_str)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Wallet not found: {str(e)}")

# Input model for wallet creation that doesn't require an ID
class WalletCreate(BaseModel):
    blockchain_symbol: str
    address: str
    name: str
    balance: float = 0.0
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@app.post("/wallets", response_model=Wallet)
async def create_wallet(wallet: WalletCreate, background_tasks: BackgroundTasks):
    try:
        # Import UUID and Wallet model
        from app.models import Wallet as WalletModel
        import uuid
        
        # Create wallet dict from pydantic model and add UUID
        wallet_dict = wallet.dict()
        wallet_dict['id'] = str(uuid.uuid4())
            
        # Convert to full Wallet model for validation
        wallet_model = WalletModel(**wallet_dict)
        
        # Check for duplicate address for this blockchain
        kv = await js.key_value(bucket="wallets")
        
        try:
            keys = await kv.keys()
            
            # Check all existing wallets for duplicate address/blockchain
            for key in keys:
                existing_data = await kv.get(key)
                existing_wallet = json.loads(existing_data.value)
                
                if (existing_wallet['blockchain_symbol'] == wallet_model.blockchain_symbol and 
                    existing_wallet['address'].lower() == wallet_model.address.lower()):
                    raise HTTPException(
                        status_code=400, 
                        detail=f"A wallet with this address already exists for {wallet_model.blockchain_symbol}"
                    )
        except Exception as keys_error:
            # If "no keys found", this is the first wallet - proceed without error
            if "no keys found" in str(keys_error).lower():
                print("No wallet keys found, this will be the first wallet")
                # Continue with wallet creation
            else:
                # Unexpected error
                print(f"Error checking for duplicate wallets: {keys_error}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error checking for duplicate wallets: {str(keys_error)}"
                )
        
        # Store the new wallet - ENSURE the value is properly encoded to bytes
        json_data = json.dumps(wallet_model.dict())
        encoded_data = json_data.encode('utf-8')  # Convert string to bytes
        await kv.put(wallet_model.id, encoded_data)
        
        # TEMPORARY FIX: Completely bypass event publishing for now
        # This ensures wallet creation works without the concatenation error
        print(f"Wallet created successfully with ID: {wallet_model.id}")
        # NOTE: Event publishing is disabled until we resolve the string/bytes issue
        
        return wallet_model
    except HTTPException:
        # Pass through HTTP exceptions directly
        raise
    except Exception as e:
        # Add explicit traceback printing
        import traceback
        error_tb = traceback.format_exc()
        
        # Print full error details including stack trace
        print("====== WALLET CREATION ERROR ======")
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR MESSAGE: {str(e)}")
        print(f"TRACEBACK:\n{error_tb}")
        print("===================================")
        
        # Bypass event publishing if that's the issue
        if "concat str to bytes" in str(e):
            # Most likely related to event publishing, return the wallet directly
            print("String/bytes concatenation error detected - bypassing event publishing")
            try:
                return wallet_model
            except Exception as bypass_error:
                print(f"BYPASS ERROR: {bypass_error}")
        
        raise HTTPException(status_code=500, detail=f"Error creating wallet: {str(e)}")

@app.put("/wallets/{wallet_id}", response_model=Wallet)
async def update_wallet(wallet_id: str, wallet: Wallet, background_tasks: BackgroundTasks):
    try:
        if wallet_id != wallet.id:
            raise HTTPException(status_code=400, detail="Wallet ID mismatch")
            
        kv = await js.key_value(bucket="wallets")
        
        # Check if wallet exists
        try:
            current_data = await kv.get(wallet_id)
            current_wallet = json.loads(current_data.value)
        except Exception:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # If address or blockchain changed, check for uniqueness
        if (wallet.address.lower() != current_wallet['address'].lower() or 
            wallet.blockchain_symbol != current_wallet['blockchain_symbol']):
            
            # Check all existing wallets for duplicate address/blockchain
            try:
                keys = await kv.keys()
                
                for key in keys:
                    # Skip checking against the current wallet
                    if key == wallet_id:
                        continue
                        
                    existing_data = await kv.get(key)
                    existing_wallet = json.loads(existing_data.value)
                    
                    if (existing_wallet['blockchain_symbol'] == wallet.blockchain_symbol and 
                        existing_wallet['address'].lower() == wallet.address.lower()):
                        raise HTTPException(
                            status_code=400, 
                            detail=f"A wallet with this address already exists for {wallet.blockchain_symbol}"
                        )
            except Exception as keys_error:
                # If "no keys found", there are no other wallets to check against
                if "no keys found" in str(keys_error).lower():
                    print("No other wallet keys found, proceeding with update")
                    # Continue with wallet update
                else:
                    # Unexpected error
                    print(f"Error checking for duplicate wallets during update: {keys_error}")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Error checking for duplicate wallets: {str(keys_error)}"
                    )
        
        # Update wallet - properly encode to bytes
        json_data = json.dumps(wallet.dict())
        encoded_data = json_data.encode('utf-8')  # Convert string to bytes
        await kv.put(wallet_id, encoded_data)
        
        # Publish event using centralized event module
        # Ignore any publishing errors to ensure wallet update succeeds
        await publish_event("wallet.updated", wallet.dict(), ignore_errors=True)
        
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
        
        # Publish event using centralized event module
        # Ignore any publishing errors to ensure wallet deletion succeeds
        await publish_event("wallet.deleted", {"id": wallet_id}, ignore_errors=True)
        
        return {"status": "deleted", "id": wallet_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting wallet: {str(e)}")

# Alert routes
@app.get("/alerts", response_model=List[Alert])
async def get_alerts():
    try:
        # Try to get the alerts bucket
        try:
            kv = await js.key_value(bucket="alerts")
        except Exception as bucket_error:
            # If bucket doesn't exist, create it
            if "no bucket" in str(bucket_error).lower() or "not found" in str(bucket_error).lower():
                try:
                    await js.create_key_value(bucket="alerts")
                    kv = await js.key_value(bucket="alerts")
                except Exception as create_error:
                    print(f"Error creating alerts bucket: {create_error}")
                    return []  # Return empty list on error
            else:
                # Other bucket error
                print(f"Error accessing alerts bucket: {bucket_error}")
                return []  # Return empty list on error
                
        # Try to get keys from the bucket
        try:
            print("Getting alert keys from bucket...")
            keys = await kv.keys()
            print(f"Found {len(keys)} alert keys: {keys}")
            alerts = []
            
            for key in keys:
                print(f"Loading alert with key: {key}")
                data = await kv.get(key)
                # Properly decode bytes data
                if isinstance(data.value, bytes):
                    json_str = data.value.decode('utf-8')
                else:
                    json_str = data.value
                alert_data = json.loads(json_str)
                print(f"Loaded alert: {alert_data.get('id')} - {alert_data.get('type')}")
                alerts.append(alert_data)
            
            print(f"Returning {len(alerts)} alerts")
            return alerts
        except Exception as keys_error:
            # Handle "no keys found" error by returning empty list
            if "no keys found" in str(keys_error).lower():
                print("No alert keys found, returning empty list")
                return []  # Return empty list when no keys found
            else:
                print(f"Error getting alert keys: {keys_error}")
                return []  # Return empty list on error
    except Exception as e:
        print(f"Unexpected error in get_alerts: {e}")
        return []  # Return empty list instead of error

@app.get("/alerts/{alert_id}", response_model=Alert)
async def get_alert(alert_id: str):
    try:
        kv = await js.key_value(bucket="alerts")
        data = await kv.get(alert_id)
        # Properly decode bytes data
        if isinstance(data.value, bytes):
            json_str = data.value.decode('utf-8')
        else:
            json_str = data.value
        return json.loads(json_str)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Alert not found: {str(e)}")

@app.post("/alerts", response_model=Alert)
async def create_alert(alert: Alert, background_tasks: BackgroundTasks):
    try:
        kv = await js.key_value(bucket="alerts")
        # Store the new alert - properly encode to bytes
        json_data = json.dumps(alert.dict())
        encoded_data = json_data.encode('utf-8')  # Convert string to bytes
        await kv.put(alert.id, encoded_data)
        
        # Publish event about new alert using centralized system
        background_tasks.add_task(publish_event, "alert.created", alert.dict(), ignore_errors=True)
        
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
        
        # Update alert - properly encode to bytes
        json_data = json.dumps(alert.dict())
        encoded_data = json_data.encode('utf-8')  # Convert string to bytes
        await kv.put(alert_id, encoded_data)
        
        # Publish event using centralized system
        background_tasks.add_task(publish_event, "alert.updated", alert.dict(), ignore_errors=True)
        
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
        
        # Publish event using centralized system
        background_tasks.add_task(publish_event, "alert.deleted", {"id": alert_id}, ignore_errors=True)
        
        return {"status": "deleted", "id": alert_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting alert: {str(e)}")

# Helper functions for event publishing now centralized in app.events module

# Safe wallet event publisher to avoid string/bytes concatenation issues
async def _publish_wallet_event(wallet_data: Dict[str, Any]):
    """Special helper function to safely publish wallet events without string/bytes concatenation issues"""
    try:
        # Convert data to a plain JSON string first
        data_json = json.dumps(wallet_data)
        # Encode to bytes
        data_bytes = data_json.encode('utf-8')
        # Use direct JetStream API with plain string subject and bytes data
        await js.publish("wallet.created", data_bytes)
        print(f"Published wallet event for wallet ID: {wallet_data.get('id', 'unknown')}")
    except Exception as e:
        # Never raise exceptions here - just log them
        print(f"WARNING: Failed to publish wallet event: {str(e)}")
        print(f"Event data: {str(wallet_data)[:100]}...")
        # We still consider the wallet operation successful

# Debug endpoint to inspect wallets KV store directly
@app.get("/debug/wallets")
async def debug_wallets():
    try:
        print("\n======= DEBUG WALLETS KV STORE =======")
        
        # Check if NATS is connected
        if not (nc and nc.is_connected):
            print("NATS not connected!")
            return {"error": "NATS not connected"}
        
        # Get direct access to the KV store
        try:
            kv = await js.key_value(bucket="wallets")
            print(f"KV store accessed: {kv}")
        except Exception as e:
            print(f"Error accessing KV: {e}")
            # Try to create it
            try:
                await js.create_key_value(bucket="wallets")
                kv = await js.key_value(bucket="wallets")
                print(f"Created new KV store: {kv}")
            except Exception as e2:
                print(f"Error creating KV: {e2}")
                return {"error": f"Could not create KV store: {str(e2)}"}
        
        # Get all keys
        try:
            keys = await kv.keys()
            print(f"Found {len(keys)} keys: {keys}")
        except Exception as e:
            if "no keys found" in str(e).lower():
                print("No keys found in store")
                return {"keys": [], "details": "No keys found"}
            else:
                print(f"Error getting keys: {e}")
                return {"error": f"Error getting keys: {str(e)}"}
        
        # Try to get all values
        result = []
        for key in keys:
            try:
                data = await kv.get(key)
                # Properly decode bytes data
                if isinstance(data.value, bytes):
                    json_str = data.value.decode('utf-8')
                else:
                    json_str = data.value
                wallet = json.loads(json_str)
                print(f"Key {key}: {wallet}")
                result.append({"key": key, "data": wallet})
            except Exception as e:
                print(f"Error getting key {key}: {e}")
                result.append({"key": key, "error": str(e)})
        
        print("======= END DEBUG WALLETS KV STORE =======\n")
        return {"keys": keys, "data": result}
    except Exception as e:
        print(f"Overall debug error: {e}")
        return {"error": f"Debug failed: {str(e)}"}

# Health check endpoint
@app.get("/health")
async def health_check():
    if nc and nc.is_connected:
        return {"status": "healthy", "nats_connected": True}
    else:
        return {"status": "unhealthy", "nats_connected": False}, 503
