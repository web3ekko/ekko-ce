#!/bin/bash
set -euo pipefail

# Build script for individual WasmCloud providers
# Creates Provider Archive (PAR) files for deployment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
REGISTRY="${REGISTRY:-registry.kube-system.svc.cluster.local:80}"
PROVIDER_VERSION="${PROVIDER_VERSION:-v1.0.0}"
PUSH_TO_REGISTRY="${PUSH_TO_REGISTRY:-false}"
WASH_HOME="${WASH_HOME:-${SCRIPT_DIR}/.wash-home}"
mkdir -p "${WASH_HOME}"

wash_cmd() {
    HOME="${WASH_HOME}" wash "$@"
}

# Usage function
usage() {
    echo "Usage: $0 <provider-name> [options]"
    echo ""
    echo "Available providers:"
    echo "  alert-scheduler       - Alert scheduling and periodic evaluation"
    echo "  ducklake              - DuckLake storage integration"
    echo "  websocket-notification - WebSocket notification delivery"
    echo "  email-notification    - Email notification delivery (SendGrid/Firebase)"
    echo "  newheads-evm          - EVM blockchain newheads streaming"
    echo "  http-rpc              - HTTP RPC with failover and circuit breaker"
    echo "  abi-decoder           - EVM transaction ABI decoding"
    echo "  polars-eval           - High-performance DataFrame filter evaluation"
    echo ""
    echo "Options:"
    echo "  --version <version>   Set provider version (default: v1.0.0)"
    echo "  --registry <url>      Set OCI registry URL"
    echo "  --push                Push PAR to registry after build"
    echo "  --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 alert-scheduler"
    echo "  $0 http-rpc --version v1.1.0 --push"
    echo "  REGISTRY=localhost:5001 $0 ducklake --push"
    exit 1
}

# Parse arguments
if [ $# -eq 0 ]; then
    usage
fi

PROVIDER_DIR=$1
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            PROVIDER_VERSION="$2"
            shift 2
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --push)
            PUSH_TO_REGISTRY="true"
            shift
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate provider exists
if [ ! -d "providers/$PROVIDER_DIR" ]; then
    echo "❌ Provider directory not found: providers/$PROVIDER_DIR"
    exit 1
fi

if [ ! -f "providers/$PROVIDER_DIR/Cargo.toml" ]; then
    echo "❌ No Cargo.toml found in providers/$PROVIDER_DIR"
    exit 1
fi

# Determine package name (add -provider suffix if not present)
PACKAGE_NAME="${PROVIDER_DIR}"
if [[ ! "$PACKAGE_NAME" =~ -provider$ ]]; then
    PACKAGE_NAME="${PACKAGE_NAME}-provider"
fi

# Provider name for PAR (without -provider suffix)
PROVIDER_NAME="${PACKAGE_NAME%-provider}"
BINARY_NAME="${PROVIDER_BIN:-$PACKAGE_NAME}"

case "$PROVIDER_NAME" in
    websocket-notification)
        BINARY_NAME="websocket-provider-wasmcloud"
        ;;
esac

echo "🔨 Building Provider: $PROVIDER_NAME"
echo "================================"
echo "  Directory: providers/$PROVIDER_DIR"
echo "  Package: $PACKAGE_NAME"
echo "  Binary: $BINARY_NAME"
echo "  Version: $PROVIDER_VERSION"
echo "  Registry: $REGISTRY"
echo ""

# Step 1: Build native binary
echo "📦 Building native binary..."
if ! cargo build -p $PACKAGE_NAME --release --bin "$BINARY_NAME"; then
    echo "❌ Failed to build $PACKAGE_NAME"
    exit 1
fi
echo "✅ Native binary built"

# Step 2: Create PAR file
echo ""
echo "📦 Creating Provider Archive (PAR)..."

# Create build directory
mkdir -p providers/$PROVIDER_DIR/build

# Check if wash is available
if ! command -v wash &> /dev/null; then
    echo "❌ wash CLI not found. Install with: curl -s https://packagecloud.io/install/repositories/wasmcloud/core/script.deb.sh | sudo bash && sudo apt install wash"
    exit 1
fi

# Create PAR
if ! wash_cmd par create \
    --vendor ekko \
    --name $PROVIDER_NAME \
    --version $PROVIDER_VERSION \
    --binary target/release/$BINARY_NAME \
    --destination providers/$PROVIDER_DIR/build/${PROVIDER_NAME}.par.gz \
    --compress; then
    echo "❌ Failed to create PAR archive"
    exit 1
fi

echo "✅ PAR created: providers/$PROVIDER_DIR/build/${PROVIDER_NAME}.par.gz"

# Get file size
PAR_SIZE=$(ls -lh providers/$PROVIDER_DIR/build/${PROVIDER_NAME}.par.gz | awk '{print $5}')
echo "   Size: $PAR_SIZE"

# Step 3: Push to registry (if requested)
if [ "$PUSH_TO_REGISTRY" = "true" ]; then
    echo ""
    echo "☁️  Pushing to OCI registry..."
    echo "   Registry: $REGISTRY"
    echo "   Image: $PROVIDER_NAME:$PROVIDER_VERSION"

    if wash_cmd push \
        $REGISTRY/$PROVIDER_NAME:$PROVIDER_VERSION \
        providers/$PROVIDER_DIR/build/${PROVIDER_NAME}.par.gz \
        --insecure \
        --allow-latest; then
        echo "✅ Pushed to registry successfully"

        # Also tag as latest
        echo "   Tagging as latest..."
        wash_cmd push \
            $REGISTRY/$PROVIDER_NAME:latest \
            providers/$PROVIDER_DIR/build/${PROVIDER_NAME}.par.gz \
            --insecure \
            --allow-latest || echo "⚠️  Failed to push latest tag"
    else
        echo "❌ Failed to push to registry"
        exit 1
    fi
fi

echo ""
echo "✨ Provider build complete!"
echo ""
echo "Next steps:"
if [ "$PUSH_TO_REGISTRY" = "false" ]; then
    echo "  1. Push to registry: $0 $PROVIDER_DIR --push"
fi
echo "  2. Update WADM manifest with image: $REGISTRY/$PROVIDER_NAME:$PROVIDER_VERSION"
echo "  3. Deploy: wash app deploy wadm/ekko-cluster.yaml"
echo "  4. Verify: wash get providers"
