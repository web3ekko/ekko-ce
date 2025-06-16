import asyncio
import os
import json
import uuid
import traceback
from typing import Dict, List, Optional, Any, Union
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
import nats
from datetime import datetime
from nats.js.api import StreamConfig, ConsumerConfig
from pydantic import BaseModel
from contextlib import asynccontextmanager
from app.routes.settings import router as settings_router, set_js as set_settings_js
from app.main_extension import auth_router, user_router, wallet_router
from app.events import set_js as set_events_js, publish_event

# Import transactions router
try:
    from app.real_transactions import router as transactions_router
    TRANSACTIONS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Real transactions router not available, falling back to simple: {e}")
    try:
        from app.simple_transactions import router as transactions_router
        TRANSACTIONS_AVAILABLE = True
    except ImportError as e2:
        print(f"Warning: No transactions router available: {e2}")
        TRANSACTIONS_AVAILABLE = False

# Import Delta events router
try:
    from app.delta_events import router as delta_events_router
    DELTA_EVENTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Delta events router not available: {e}")
    DELTA_EVENTS_AVAILABLE = False
from app.alert_processor import start_alert_processor, stop_alert_processor
from app.models import Node
from app.alert_job_utils import generate_job_spec_from_alert
from app.logging_config import alert_logger, api_logger, job_spec_logger
from app.startup import initialize_database_system, cleanup_database_system, get_database_status

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
    related_wallet_id: Optional[str] = None
    query: Optional[str] = None
    notifications_enabled: Optional[bool] = True

# Notification destination model
class NotificationDestination(BaseModel):
    id: str
    type: str  # 'email', 'telegram', 'discord'
    name: str
    address: str
    enabled: bool = True
    created_at: str

# Notification settings model
class NotificationSettings(BaseModel):
    destinations: List[NotificationDestination] = []

# Global NATS connection
nc = None
js = None

# Background task flags
running = True
alert_processor_task = None

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
        print(f"LIFESPAN: nc.jetstream() returned: {js} (type: {type(js)})")
        app.state.js = js
        print(f"LIFESPAN: app.state.js set to: {app.state.js} (type: {type(app.state.js)})") # Store js in app.state
        set_events_js(js) # Set js for events module
        set_settings_js(js) # Set js for settings routers

        # This is critical for event publishing to work properly
        print("Initializing event publishing system...")
        set_events_js(js)

        # Test event publishing
        try:
            await publish_event("system.startup", {"status": "initializing"}, ignore_errors=True)
            print("✅ Event system initialized successfully")
        except Exception as event_error:
            print(f"⚠️ Warning: Event system initialization issue: {event_error}")

        # Initialize database system
        print("Initializing database system...")
        try:
            await initialize_database_system(js)
            print("✅ Database system initialized successfully")
        except Exception as db_error:
            print(f"⚠️ Warning: Database initialization issue: {db_error}")

        # Ensure streams exist
        await ensure_streams()

        # Start background task for processing messages
        asyncio.create_task(process_messages())

        # Start alert processor as a background task
        global alert_processor_task
        alert_processor_task = asyncio.create_task(start_alert_processor(js, interval_seconds=60))
        print("Alert processor background task started")

        print("FastAPI service started successfully")
        yield
    finally:
        # Shutdown: stop background processing and close NATS connection
        running = False

        # Stop alert processor
        if alert_processor_task:
            await stop_alert_processor()
            try:
                alert_processor_task.cancel()
                await alert_processor_task
            except asyncio.CancelledError:
                print("Alert processor task cancelled successfully")
            except Exception as e:
                print(f"Error cancelling alert processor task: {e}")

        # Cleanup database system
        try:
            await cleanup_database_system()
            print("Database system cleanup completed")
        except Exception as e:
            print(f"Error during database cleanup: {e}")

        # Close NATS connection
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
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(auth_router)  # For /token endpoint
app.include_router(user_router)  # For /users endpoints
app.include_router(wallet_router) # For /wallet-balances endpoints



# Include transactions router if available
if TRANSACTIONS_AVAILABLE:
    app.include_router(transactions_router, prefix="/api", tags=["transactions"])
    print("✅ Transactions router included with /api prefix")
else:
    print("⚠️ Transactions router not available")

# Include Delta events router if available
if DELTA_EVENTS_AVAILABLE:
    app.include_router(delta_events_router, prefix="/api", tags=["delta-events"])
    print("✅ Delta events router included with /api prefix")
else:
    print("⚠️ Delta events router not available")

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
        await js.key_value(bucket="nodes")
    except Exception:
        await js.create_key_value(bucket="nodes")
    
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
    subnet: str = "mainnet"  # Added subnet field
    description: Optional[str] = None  # Added description field
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

# Database health endpoint
@app.get("/database/health")
async def get_database_health():
    """Get database system health status."""
    try:
        status = get_database_status()
        return status
    except Exception as e:
        return {
            "database_healthy": False,
            "error": str(e),
            "status": "error"
        }

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

@app.get("/alerts/{alert_id}")
async def get_alert(alert_id: str):
    try:
        kv = await js.key_value(bucket="alerts")
        
        # Get alert data
        try:
            data = await kv.get(alert_id)
            # Handle both string and bytes values
            if isinstance(data.value, bytes):
                return json.loads(data.value.decode('utf-8'))
            else:
                return json.loads(data.value)
        except Exception as e:
            raise HTTPException(status_code=404, detail="Alert not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alert: {str(e)}")

@app.get("/alerts/{alert_id}/jobspec")
async def get_alert_jobspec(alert_id: str):
    try:
        kv = await js.key_value(bucket="alerts")
        
        # Get alert data
        try:
            data = await kv.get(alert_id)
            # Handle both string and bytes values
            if isinstance(data.value, bytes):
                alert_data = json.loads(data.value.decode('utf-8'))
            else:
                alert_data = json.loads(data.value)
        except Exception as e:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        # Generate jobspec from alert
        from app.alert_job_utils import generate_job_spec_from_alert
        jobspec = await generate_job_spec_from_alert(alert_data)
        
        if not jobspec:
            raise HTTPException(status_code=404, detail="Could not generate jobspec for this alert")
            
        return {
            "alert_id": alert_id,
            "jobspec": jobspec,
            "prettified": json.dumps(jobspec, indent=2)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating jobspec: {str(e)}")

@app.post("/alerts/{alert_id}/generate-jobspec")
async def generate_alert_jobspec(alert_id: str, background_tasks: BackgroundTasks):
    """
    Explicitly generate a job specification for an alert and store it with the alert.
    """
    try:
        kv = await js.key_value(bucket="alerts")
        
        # Check if alert exists and get its data
        try:
            data = await kv.get(alert_id)
            # Handle both string and bytes values
            if isinstance(data.value, bytes):
                alert_data = json.loads(data.value.decode('utf-8'))
            else:
                alert_data = json.loads(data.value)
        except Exception:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        # Generate jobspec immediately (not as a background task)
        from app.alert_job_utils import generate_job_spec_from_alert
        job_spec = await generate_job_spec_from_alert(alert_data)
        
        if not job_spec:
            raise HTTPException(status_code=422, detail="Failed to generate job specification")
            
        # Update the alert with the new job spec
        alert_data['job_spec'] = job_spec
        alert_data['job_spec_generated_at'] = datetime.now().isoformat()
        
        # Store updated alert
        json_data = json.dumps(alert_data)
        encoded_data = json_data.encode('utf-8')
        await kv.put(alert_id, encoded_data)
        
        # Publish event
        background_tasks.add_task(publish_event, "alert.jobspec.generated", {
            "alert_id": alert_id,
            "job_spec": job_spec
        }, ignore_errors=True)
        
        return {
            "status": "success",
            "alert_id": alert_id,
            "job_spec": job_spec,
            "prettified": json.dumps(job_spec, indent=2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating job specification: {str(e)}")

# Background task to generate job specification for an alert
async def generate_job_spec_for_alert(alert_id: str, alert_query: str):
    try:
        job_spec_logger.info(f"[ALERT:{alert_id}] Starting background task for job spec generation")
        job_spec_logger.debug(f"[ALERT:{alert_id}] Query: '{alert_query}'")
        
        start_time = datetime.now()
        
        # Get the alert from KV store
        try:
            kv = await js.key_value(bucket="alerts")
            job_spec_logger.debug(f"[ALERT:{alert_id}] Connected to alerts KV store")
            
            data = await kv.get(alert_id)
            job_spec_logger.debug(f"[ALERT:{alert_id}] Retrieved alert data from KV store")
            
            # Decode the alert data
            if isinstance(data.value, bytes):
                json_str = data.value.decode('utf-8')
            else:
                json_str = data.value
                
            alert_data = json.loads(json_str)
            job_spec_logger.debug(f"[ALERT:{alert_id}] Successfully parsed alert data JSON")
            
        except Exception as kv_error:
            job_spec_logger.error(f"[ALERT:{alert_id}] Error accessing KV store: {str(kv_error)}")
            job_spec_logger.debug(f"[ALERT:{alert_id}] KV error details: {traceback.format_exc()}")
            raise
        
        # Generate job spec
        job_spec_logger.info(f"[ALERT:{alert_id}] Calling job spec generator")
        job_spec = await generate_job_spec_from_alert({"id": alert_id, "query": alert_query})
        
        if job_spec:
            job_name = job_spec.get("job_name", "unnamed")
            job_spec_logger.info(f"[ALERT:{alert_id}] Successfully generated job spec '{job_name}'")
            
            # Update the alert with the job spec
            alert_data["job_spec"] = job_spec
            
            # Store the updated alert back to KV store
            try:
                json_data = json.dumps(alert_data)
                encoded_data = json_data.encode('utf-8')  # Convert string to bytes
                await kv.put(alert_id, encoded_data)
                job_spec_logger.info(f"[ALERT:{alert_id}] Updated alert with job spec in KV store")
            except Exception as update_error:
                job_spec_logger.error(f"[ALERT:{alert_id}] Error updating alert with job spec: {str(update_error)}")
                raise
            
            # Publish event about job spec creation
            try:
                await publish_event("alert.jobspec.created", 
                                  {"alert_id": alert_id, "job_name": job_name}, 
                                  ignore_errors=True)
                job_spec_logger.info(f"[ALERT:{alert_id}] Published job spec creation event")
            except Exception as event_error:
                job_spec_logger.warning(f"[ALERT:{alert_id}] Error publishing event: {str(event_error)}")
            
            # Calculate and log total processing time
            elapsed = (datetime.now() - start_time).total_seconds()
            job_spec_logger.info(f"[ALERT:{alert_id}] Total job spec generation time: {elapsed:.2f} seconds")
        else:
            job_spec_logger.warning(f"[ALERT:{alert_id}] Job spec generation failed, no job spec created")
            
    except Exception as e:
        job_spec_logger.error(f"[ALERT:{alert_id}] Unhandled error in job spec generation: {str(e)}")
        job_spec_logger.debug(f"[ALERT:{alert_id}] Exception details: {traceback.format_exc()}")


@app.post("/alerts", response_model=Alert)
async def create_alert(alert: Alert, background_tasks: BackgroundTasks):
    try:
        alert_logger.info(f"[ALERT:{alert.id}] Creating new alert of type '{alert.type}'")
        alert_logger.debug(f"[ALERT:{alert.id}] Full alert data: {alert.dict()}")
        
        start_time = datetime.now()
        
        # Store the alert first without waiting for job spec
        try:
            kv = await js.key_value(bucket="alerts")
            alert_logger.debug(f"[ALERT:{alert.id}] Connected to alerts KV store")
            
            # Store the new alert - properly encode to bytes
            json_data = json.dumps(alert.dict())
            encoded_data = json_data.encode('utf-8')  # Convert string to bytes
            await kv.put(alert.id, encoded_data)
            alert_logger.info(f"[ALERT:{alert.id}] Alert stored in KV store")
            
        except Exception as kv_error:
            alert_logger.error(f"[ALERT:{alert.id}] Error storing alert in KV store: {str(kv_error)}")
            alert_logger.debug(f"[ALERT:{alert.id}] KV error details: {traceback.format_exc()}")
            raise
        
        # Schedule job spec generation as a background task if query is provided
        if alert.query:
            alert_logger.info(f"[ALERT:{alert.id}] Alert has query, scheduling job spec generation")
            background_tasks.add_task(generate_job_spec_for_alert, alert.id, alert.query)
            alert_logger.debug(f"[ALERT:{alert.id}] Background task for job spec generation scheduled")
        else:
            alert_logger.debug(f"[ALERT:{alert.id}] No query provided, skipping job spec generation")
        
        # Publish event about new alert using centralized system
        try:
            background_tasks.add_task(publish_event, "alert.created", alert.dict(), ignore_errors=True)
            alert_logger.info(f"[ALERT:{alert.id}] Alert creation event scheduled for publishing")
        except Exception as event_error:
            alert_logger.warning(f"[ALERT:{alert.id}] Error scheduling event publication: {str(event_error)}")
        
        # Calculate and log total processing time
        elapsed = (datetime.now() - start_time).total_seconds()
        alert_logger.info(f"[ALERT:{alert.id}] Alert creation completed in {elapsed:.2f} seconds")
        
        return alert
    except Exception as e:
        alert_logger.error(f"Error creating alert: {str(e)}")
        alert_logger.debug(f"Alert creation exception details: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error creating alert: {str(e)}")




@app.put("/alerts/{alert_id}", response_model=Alert)
async def update_alert(alert_id: str, alert: Alert, background_tasks: BackgroundTasks):
    try:
        if alert_id != alert.id:
            raise HTTPException(status_code=400, detail="Alert ID mismatch")
            
        kv = await js.key_value(bucket="alerts")
        
        # Check if alert exists and get existing data
        try:
            existing = await kv.get(alert_id)
            # Handle byte or string data properly
            if isinstance(existing.value, bytes):
                json_str = existing.value.decode('utf-8')
            else:
                json_str = existing.value
            existing_alert = json.loads(json_str)
        except Exception as e:
            api_logger.error(f"Error getting existing alert: {str(e)}")
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Merge existing alert with update data
        # This preserves fields not included in the update
        updated_alert = {**existing_alert}
        update_data = alert.dict(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:  # Only update non-None values
                updated_alert[key] = value
        
        # Update alert - properly encode to bytes
        json_data = json.dumps(updated_alert)
        encoded_data = json_data.encode('utf-8')  # Convert string to bytes
        await kv.put(alert_id, encoded_data)
        
        # Publish event using centralized system
        background_tasks.add_task(publish_event, "alert.updated", updated_alert, ignore_errors=True)
        
        # Return updated alert as an Alert model instance
        return Alert(**updated_alert)
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

# Node routes
@app.get("/nodes")
async def get_nodes():
    try:
        # Access KV store
        kv = await js.key_value(bucket="nodes")
        
        # Get all keys
        try:
            keys = await kv.keys()
        except Exception as e:
            # Return empty array if no keys found
            if "no keys found" in str(e).lower():
                return {"data": [], "total": 0, "page": 1, "limit": 0, "totalPages": 0}
            raise
        
        # Get all nodes
        nodes = []
        for key in keys:
            try:
                data = await kv.get(key)
                # Properly decode bytes data
                if isinstance(data.value, bytes):
                    json_str = data.value.decode('utf-8')
                else:
                    json_str = data.value
                node = json.loads(json_str)
                nodes.append(node)
            except Exception as e:
                print(f"Error retrieving node {key}: {str(e)}")
        
        return {
            "data": nodes,
            "total": len(nodes),
            "page": 1,
            "limit": len(nodes) if len(nodes) > 0 else 10, # Avoid limit 0 if nodes empty, use a default
            "totalPages": 1
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching nodes: {str(e)}")

@app.get("/nodes/{node_id}")
async def get_node(node_id: str):
    try:
        # Access KV store
        kv = await js.key_value(bucket="nodes")
        
        # Get node by ID
        try:
            data = await kv.get(node_id)
            # Properly decode bytes data
            if isinstance(data.value, bytes):
                json_str = data.value.decode('utf-8')
            else:
                json_str = data.value
            node = json.loads(json_str)
            return node
        except Exception as e:
            if "no key exists" in str(e).lower():
                raise HTTPException(status_code=404, detail="Node not found")
            raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching node: {str(e)}")

@app.post("/nodes")
async def create_node(node: Node, background_tasks: BackgroundTasks):
    try:
        # Ensure the KV bucket exists
        try:
            kv = await js.key_value(bucket="nodes")
        except Exception:
            # Create the KV bucket if it doesn't exist
            await js.create_key_value(bucket="nodes")
            kv = await js.key_value(bucket="nodes")

        # Check for duplicate network + subnet + vmtype combination
        try:
            keys = await kv.keys()

            # Check all existing nodes for duplicate network/subnet/vmtype
            for key in keys:
                existing_data = await kv.get(key)
                if isinstance(existing_data.value, bytes):
                    json_str = existing_data.value.decode('utf-8')
                else:
                    json_str = existing_data.value
                existing_node = json.loads(json_str)

                # Check if the combination already exists
                if (existing_node.get("network", "").lower() == node.network.lower() and
                    existing_node.get("subnet", "").lower() == node.subnet.lower() and
                    existing_node.get("vm_type", "").lower() == node.vm_type.lower()):
                    raise HTTPException(
                        status_code=400,
                        detail=f"A node with network '{node.network}', subnet '{node.subnet}', and VM type '{node.vm_type}' already exists. Only one node per network/subnet/vmtype combination is allowed."
                    )
        except HTTPException:
            raise
        except Exception:
            # If there's an error reading existing nodes, continue with creation
            # This handles the case where the bucket is empty or has issues
            pass

        # Create a complete node object
        current_time = datetime.now().isoformat()
        node_data = node.dict()
        node_data["created_at"] = current_time
        node_data["updated_at"] = current_time

        # Convert node to JSON string
        node_json = json.dumps(node_data)

        # Store node in KV store
        await kv.put(node_data["id"], node_json.encode('utf-8'))

        # Publish event
        background_tasks.add_task(publish_event, "node.created", node_data, ignore_errors=True)

        return node_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating node: {str(e)}")

@app.put("/nodes/{node_id}")
async def update_node(node_id: str, node: Node, background_tasks: BackgroundTasks):
    try:
        # Access KV store
        kv = await js.key_value(bucket="nodes")

        # Check if node exists
        try:
            existing_data = await kv.get(node_id)
            # Properly decode bytes data
            if isinstance(existing_data.value, bytes):
                json_str = existing_data.value.decode('utf-8')
            else:
                json_str = existing_data.value
            existing_node = json.loads(json_str)
        except Exception as e:
            if "no key exists" in str(e).lower():
                raise HTTPException(status_code=404, detail="Node not found")
            raise

        # Check for duplicate network + subnet + vmtype combination (excluding current node)
        try:
            keys = await kv.keys()

            # Check all existing nodes for duplicate network/subnet/vmtype
            for key in keys:
                if key == node_id:  # Skip the current node being updated
                    continue

                other_data = await kv.get(key)
                if isinstance(other_data.value, bytes):
                    json_str = other_data.value.decode('utf-8')
                else:
                    json_str = other_data.value
                other_node = json.loads(json_str)

                # Check if the combination already exists in another node
                if (other_node.get("network", "").lower() == node.network.lower() and
                    other_node.get("subnet", "").lower() == node.subnet.lower() and
                    other_node.get("vm_type", "").lower() == node.vm_type.lower()):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Another node with network '{node.network}', subnet '{node.subnet}', and VM type '{node.vm_type}' already exists. Only one node per network/subnet/vmtype combination is allowed."
                    )
        except HTTPException:
            raise
        except Exception:
            # If there's an error reading existing nodes, continue with update
            pass

        # Update node data
        node_data = node.dict()
        node_data["id"] = node_id  # Ensure ID is set correctly
        node_data["created_at"] = existing_node.get("created_at")
        node_data["updated_at"] = datetime.now().isoformat()

        # Convert node to JSON string
        node_json = json.dumps(node_data)

        # Store updated node in KV store
        await kv.put(node_id, node_json.encode('utf-8'))

        # Publish event
        background_tasks.add_task(publish_event, "node.updated", node_data, ignore_errors=True)

        return node_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating node: {str(e)}")

@app.delete("/nodes/{node_id}")
async def delete_node(node_id: str, background_tasks: BackgroundTasks):
    try:
        # Access KV store
        kv = await js.key_value(bucket="nodes")
        
        # Check if node exists
        try:
            await kv.get(node_id)
        except Exception as e:
            if "no key exists" in str(e).lower():
                raise HTTPException(status_code=404, detail="Node not found")
            raise
        
        # Delete node
        await kv.delete(node_id)
        
        # Publish event
        background_tasks.add_task(publish_event, "node.deleted", {"id": node_id}, ignore_errors=True)
        
        return {"status": "deleted", "id": node_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting node: {str(e)}")

# Notification settings endpoints
@app.get("/api/notifications/settings", response_model=NotificationSettings)
async def get_notification_settings():
    """Get current notification settings"""
    try:
        kv = await js.key_value(bucket="settings")
        try:
            data = await kv.get("notification_settings")
            if isinstance(data.value, bytes):
                json_str = data.value.decode('utf-8')
            else:
                json_str = data.value
            return json.loads(json_str)
        except Exception:
            # Return default settings if none exist
            return NotificationSettings(destinations=[])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting notification settings: {str(e)}")

@app.post("/api/notifications/settings", response_model=NotificationSettings)
async def save_notification_settings(settings: NotificationSettings):
    """Save notification settings"""
    try:
        kv = await js.key_value(bucket="settings")
        json_data = json.dumps(settings.model_dump())
        encoded_data = json_data.encode('utf-8')
        await kv.put("notification_settings", encoded_data)
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving notification settings: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    if nc and nc.is_connected:
        return {"status": "healthy", "nats_connected": True}
    else:
        return {"status": "unhealthy", "nats_connected": False}, 503
