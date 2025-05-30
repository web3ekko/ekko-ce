from fastapi import Request, HTTPException
from typing import Any

async def get_jetstream_context(request: Request) -> Any:
    """Dependency to get the NATS JetStream context from app.state."""
    print(f"DEPENDENCY: Checking request.app.state.js. hasattr: {hasattr(request.app.state, 'js')}")
    retrieved_js = getattr(request.app.state, 'js', 'NOT_FOUND')
    print(f"DEPENDENCY: request.app.state.js is: {retrieved_js} (type: {type(retrieved_js)})")

    if not hasattr(request.app.state, 'js') or request.app.state.js is None:
        print("DEPENDENCY: NATS JetStream context not available or None. Raising 503.")
        raise HTTPException(
            status_code=503,
            detail="NATS JetStream context not available. The service may be starting up or NATS is down."
        )
    print(f"DEPENDENCY: Returning request.app.state.js: {request.app.state.js} (type: {type(request.app.state.js)})")
    return request.app.state.js
