#!/bin/bash
# Build script for notification router actor

set -e

echo "Building notification router actor..."

# Check if wash is available
if ! command -v wash &> /dev/null; then
    echo "Error: wash CLI not found. Please install wasmCloud wash CLI"
    exit 1
fi

# Create build directory
mkdir -p build

# Build the actor with wash
wash build

# Sign the actor
if [ -f "build/notification_router.wasm" ]; then
    echo "Signing actor..."
    wash claims sign build/notification_router.wasm --name "notification-router" \
        --ver "1.0.0" \
        --rev "0" \
        --http_server \
        --logging \
        --output build/notification_router_s.wasm
    
    echo "Actor built and signed successfully!"
    echo "Signed actor: build/notification_router_s.wasm"
    
    # Show actor info
    wash claims inspect build/notification_router_s.wasm
else
    echo "Error: Actor build failed - notification_router.wasm not found"
    exit 1
fi