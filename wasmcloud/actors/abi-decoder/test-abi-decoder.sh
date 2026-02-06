#!/bin/bash
# =============================================================================
# ABI Decoder Actor Integration Test
# =============================================================================
# Tests the abi-decoder actor's ability to:
# 1. Receive contract transactions from NATS
# 2. Look up ABIs from Redis
# 3. Decode function calls using custom ABI decoder
# 4. Publish decoded transactions to output subject
#
# PREREQUISITES:
# - kubectl configured for cluster access
# - Port-forwards established (see setup below)
# - NATS and Redis accessible
# - abi-decoder actor deployed and linked
#
# USAGE:
#   ./test-abi-decoder.sh [--setup] [--skip-abi-setup]
#
# =============================================================================

set -e

# Configuration
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6380}"  # Port-forwarded Redis
REDIS_PASSWORD="${REDIS_PASSWORD:-redis123}"
NATS_URL="${NATS_URL:-nats://localhost:4222}"
NAMESPACE="${NAMESPACE:-ekko}"

# USDT contract address (well-known for testing)
CONTRACT_ADDRESS="0xdac17f958d2ee523a2206206994597c13d831ec7"
NETWORK="ethereum"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Setup Functions
# =============================================================================

setup_port_forwards() {
    log_info "Setting up port-forwards..."

    # Check if Redis port-forward is already running
    if ! nc -z localhost "$REDIS_PORT" 2>/dev/null; then
        log_info "Starting Redis port-forward on port $REDIS_PORT..."
        kubectl port-forward -n "$NAMESPACE" svc/redis-master "$REDIS_PORT:6379" &
        sleep 2
    else
        log_info "Redis port-forward already active on port $REDIS_PORT"
    fi

    # Check if NATS port-forward is already running
    if ! nc -z localhost 4222 2>/dev/null; then
        log_info "Starting NATS port-forward on port 4222..."
        kubectl port-forward -n "$NAMESPACE" svc/nats 4222:4222 &
        sleep 2
    else
        log_info "NATS port-forward already active on port 4222"
    fi
}

setup_abi_in_redis() {
    log_info "Storing ABI in Redis (correct AbiInfo format)..."

    # CRITICAL: ABI must be stored as AbiInfo struct with abi_json as escaped JSON string
    # See: docs/prd/wasmcloud/actors/PRD-ABI-Decoder-Actor-USDT.md - Appendix B

    local abi_json='[{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]'

    # Escape the ABI JSON for embedding in AbiInfo struct
    local escaped_abi_json=$(echo "$abi_json" | sed 's/"/\\"/g')

    # Create AbiInfo struct (CORRECT FORMAT)
    local abi_info="{\"address\":\"$CONTRACT_ADDRESS\",\"network\":\"$NETWORK\",\"abi_json\":\"$escaped_abi_json\",\"source\":\"manual\",\"verified\":true,\"cached_at\":\"2025-01-01T00:00:00Z\"}"

    local redis_key="abi:$NETWORK:$CONTRACT_ADDRESS"

    log_info "Redis key: $redis_key"
    log_info "AbiInfo struct format (with escaped abi_json)"

    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" \
        SET "$redis_key" "$abi_info"

    log_info "Verifying ABI stored correctly..."
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" \
        GET "$redis_key" | head -c 200
    echo "..."

    log_info "ABI stored successfully"
}

# =============================================================================
# Test Functions
# =============================================================================

test_abi_decoding() {
    log_info "Testing ABI decoding..."

    # Create test transaction payload
    # This is an ERC20 transfer: transfer(0x742d35cc6634c0532925a3b844bc9e7595f8b0a3, 1000000)
    local tx_hash="0x$(openssl rand -hex 32)"
    local input_data="0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b844bc9e7595f8b0a300000000000000000000000000000000000000000000000000000000000f4240"

    local test_payload=$(cat <<EOF
{
    "transaction_hash": "$tx_hash",
    "block_number": 12345678,
    "from_address": "0x1111111111111111111111111111111111111111",
    "to_address": "$CONTRACT_ADDRESS",
    "network": "$NETWORK",
    "subnet": "mainnet",
    "vm_type": "evm",
    "value": "0x0",
    "gas": "0x5208",
    "gas_price": "0x3b9aca00",
    "input_data": "$input_data"
}
EOF
)

    log_info "Starting subscriber on blockchain.>.>.contracts.decoded..."

    # Subscribe to output subject in background
    timeout 10 nats sub --server="$NATS_URL" "blockchain.>.>.contracts.decoded" &
    local sub_pid=$!
    sleep 2

    log_info "Sending test transaction to contract-transactions.$NETWORK.mainnet.Evm.raw..."
    echo "$test_payload" | nats pub --server="$NATS_URL" \
        "contract-transactions.$NETWORK.mainnet.Evm.raw" --read-stdin

    log_info "Waiting for response..."
    wait $sub_pid 2>/dev/null || true

    log_info "Test complete"
}

test_abi_not_found() {
    log_info "Testing ABI not found scenario..."

    # Use unknown contract address
    local unknown_address="0x0000000000000000000000000000000000000001"
    local tx_hash="0x$(openssl rand -hex 32)"

    local test_payload=$(cat <<EOF
{
    "transaction_hash": "$tx_hash",
    "block_number": 12345678,
    "from_address": "0x1111111111111111111111111111111111111111",
    "to_address": "$unknown_address",
    "network": "$NETWORK",
    "subnet": "mainnet",
    "vm_type": "evm",
    "value": "0x0",
    "gas": "0x5208",
    "gas_price": "0x3b9aca00",
    "input_data": "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b844bc9e7595f8b0a300000000000000000000000000000000000000000000000000000000000f4240"
}
EOF
)

    log_info "Starting subscriber..."
    timeout 5 nats sub --server="$NATS_URL" "blockchain.>.>.contracts.decoded" &
    local sub_pid=$!
    sleep 1

    log_info "Sending transaction to unknown contract..."
    echo "$test_payload" | nats pub --server="$NATS_URL" \
        "contract-transactions.$NETWORK.mainnet.Evm.raw" --read-stdin

    wait $sub_pid 2>/dev/null || true

    log_info "Expected result: decoding_status = 'AbiNotFound'"
}

# =============================================================================
# Main
# =============================================================================

main() {
    local skip_abi_setup=false

    for arg in "$@"; do
        case $arg in
            --setup)
                setup_port_forwards
                exit 0
                ;;
            --skip-abi-setup)
                skip_abi_setup=true
                ;;
            --help)
                echo "Usage: $0 [--setup] [--skip-abi-setup]"
                echo ""
                echo "Options:"
                echo "  --setup          Setup port-forwards only"
                echo "  --skip-abi-setup Skip storing ABI in Redis"
                echo ""
                echo "Environment Variables:"
                echo "  REDIS_HOST       Redis host (default: localhost)"
                echo "  REDIS_PORT       Redis port (default: 6380, port-forwarded)"
                echo "  REDIS_PASSWORD   Redis password (default: redis123)"
                echo "  NATS_URL         NATS URL (default: nats://localhost:4222)"
                echo "  NAMESPACE        Kubernetes namespace (default: ekko)"
                exit 0
                ;;
        esac
    done

    echo "=============================================="
    echo "  ABI Decoder Actor Integration Test"
    echo "=============================================="
    echo ""

    # Step 1: Setup ABI in Redis (unless skipped)
    if [ "$skip_abi_setup" = false ]; then
        log_info "Step 1: Setting up ABI in Redis..."
        setup_abi_in_redis
        echo ""
    fi

    # Step 2: Test successful ABI decoding
    log_info "Step 2: Testing successful ABI decoding..."
    test_abi_decoding
    echo ""

    # Step 3: Test ABI not found scenario
    log_info "Step 3: Testing ABI not found scenario..."
    test_abi_not_found
    echo ""

    echo "=============================================="
    echo "  Tests Complete"
    echo "=============================================="
    echo ""
    log_info "Check the output above for:"
    log_info "  - decoding_status: 'Success' for known contracts"
    log_info "  - decoding_status: 'AbiNotFound' for unknown contracts"
    log_info "  - decoded_function with name, selector, parameters for successful decoding"
}

main "$@"
