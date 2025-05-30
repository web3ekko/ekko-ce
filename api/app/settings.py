from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Optional

# Global NATS JetStream reference - will be set during application startup
js: Optional[Any] = None

settings_router = APIRouter()

def set_settings_js(jetstream_context: Any):
    """Set the global JetStream reference for the settings module."""
    global js
    js = jetstream_context
    print("NATS JetStream context set for settings module.")

@settings_router.get("/health")
async def get_settings_health():
    """Placeholder endpoint for settings health check."""
    if js is None:
        raise HTTPException(status_code=503, detail="NATS JetStream context not available in settings")
    return {"status": "ok", "jetstream_initialized": js is not None}

# Add other settings-related routes and logic here as needed
