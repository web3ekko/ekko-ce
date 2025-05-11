"""
Event publishing module for Ekko application.
Centralizes all event publishing functionality to ensure consistency.
"""
import json
from typing import Dict, Any, Optional

# Global NATS JetStream reference - will be set during application startup
js = None

def set_js(jetstream):
    """Set the global JetStream reference"""
    global js
    js = jetstream

async def publish_event(subject: str, data: Dict[str, Any], ignore_errors: bool = False) -> bool:
    """
    Publish an event to NATS with proper error handling.
    
    Args:
        subject: The subject/topic to publish to
        data: The data dictionary to publish
        ignore_errors: If True, exceptions will be caught and logged but not raised
        
    Returns:
        bool: True if publishing succeeded, False if it failed and ignore_errors=True
        
    Raises:
        Exception: Any NATS publishing exception if ignore_errors=False
    """
    global js
    
    # Convert any f-strings to plain strings first to avoid concatenation issues
    # This is crucial as subject must be a string, not a concatenation of string + bytes
    subject_plain = str(subject)
    
    if js is None:
        error_msg = "NATS JetStream not initialized for event publishing"
        print(f"ERROR: {error_msg} - Subject: {subject_plain}")
        if not ignore_errors:
            raise RuntimeError(error_msg)
        return False
        
    try:        
        # First serialize the data to a JSON string
        json_str = json.dumps(data)
        
        # Then encode to UTF-8 bytes
        data_bytes = json_str.encode('utf-8')
        
        # Ensure we have valid data_bytes
        if not isinstance(data_bytes, bytes):
            raise TypeError(f"Data must be bytes, got {type(data_bytes)}")
        
        # Publish to NATS with explicit string and bytes types
        await js.publish(subject_plain, data_bytes)
        print(f"Published event to {subject_plain}")
        return True
    except Exception as e:
        print(f"ERROR publishing event to {subject_plain}: {str(e)}")
        print(f"Event data: {str(data)[:100]}...")
        if not ignore_errors:
            raise
        return False
