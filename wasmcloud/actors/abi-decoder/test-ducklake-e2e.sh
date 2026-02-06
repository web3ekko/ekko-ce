#!/bin/bash
# =============================================================================
# DuckLake E2E Integration Test
# =============================================================================
# Tests the complete flow from decoded transactions to DuckLake storage:
#
# 1. blockchain.{network}.{subnet}.contracts.decoded
#    └─> transaction-ducklake-writer actor
#        └─> ducklake.{table}.{chain}.{subnet}.write
#            └─> ducklake provider (batched storage)
#
# PREREQUISITES:
# - kubectl configured for cluster access
# - Port-forwards established (nats: 4222)
# - transaction-ducklake-writer actor deployed and linked
# - ducklake provider deployed
#
# USAGE:
#   ./test-ducklake-e2e.sh [--setup] [--verbose]
#
# =============================================================================

set -e

# Configuration
NATS_URL="${NATS_URL:-nats://localhost:4222}"
NAMESPACE="${NAMESPACE:-ekko}"

# Test data
NETWORK="ethereum"
SUBNET="mainnet"
TX_HASH="0xtest_ducklake_e2e_$(date +%s)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_debug() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# =============================================================================
# Setup Functions
# =============================================================================

setup_port_forwards() {
    log_info "Setting up port-forwards..."

    # Check if NATS port-forward is already running
    if ! nc -z localhost 4222 2>/dev/null; then
        log_info "Starting NATS port-forward on port 4222..."
        kubectl port-forward -n "$NAMESPACE" svc/nats 4222:4222 &
        sleep 2
    else
        log_info "NATS port-forward already active on port 4222"
    fi
}

# =============================================================================
# Test Functions
# =============================================================================

test_ducklake_write_flow() {
    log_info "Testing DuckLake write flow..."
    log_info "Transaction hash: $TX_HASH"

    # Create decoded transaction payload (matches DecodedTransaction struct)
    local decoded_tx=$(cat <<EOF
{
    "transaction_hash": "$TX_HASH",
    "block_number": 19000001,
    "from_address": "0x1111111111111111111111111111111111111111",
    "to_address": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "network": "$NETWORK",
    "subnet": "$SUBNET",
    "value": "0",
    "decoding_status": "Success",
    "decoded_function": {
        "name": "transfer",
        "selector": "0xa9059cbb",
        "signature": "transfer(address,uint256)",
        "parameters": [
            {
                "name": "_to",
                "param_type": "address",
                "value": "0x742d35cc6634c0532925a3b844bc9e7595f8b0a3",
                "indexed": false
            },
            {
                "name": "_value",
                "param_type": "uint256",
                "value": "1000000",
                "indexed": false
            }
        ],
        "abi_source": "etherscan"
    },
    "input_data": "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b844bc9e7595f8b0a300000000000000000000000000000000000000000000000000000000000f4240",
    "abi_source": "etherscan",
    "processed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "processor_id": "abi-decoder-e2e-test"
}
EOF
)

    log_debug "Decoded transaction payload:"
    log_debug "$decoded_tx"

    # Step 1: Subscribe to DuckLake write subject to observe output
    log_info "Step 1: Starting subscriber on ducklake.>..."
    timeout 15 nats sub --server="$NATS_URL" "ducklake.>" &
    local ducklake_sub_pid=$!
    sleep 2

    # Step 2: Also subscribe to decoded contract outputs to verify input
    log_info "Step 2: Starting subscriber on blockchain.>.>.contracts.decoded..."
    timeout 15 nats sub --server="$NATS_URL" "blockchain.>.>.contracts.decoded" &
    local decoded_sub_pid=$!
    sleep 1

    # Step 3: Publish decoded transaction
    log_info "Step 3: Publishing decoded transaction to blockchain.$NETWORK.$SUBNET.contracts.decoded..."
    echo "$decoded_tx" | nats pub --server="$NATS_URL" \
        "blockchain.$NETWORK.$SUBNET.contracts.decoded" --read-stdin

    log_info "Step 4: Waiting for transaction-ducklake-writer to process (10s)..."
    sleep 10

    # Clean up subscribers
    kill $ducklake_sub_pid 2>/dev/null || true
    kill $decoded_sub_pid 2>/dev/null || true

    log_info "Test complete"
    echo ""
    log_info "Expected results:"
    log_info "  1. Message received on blockchain.$NETWORK.$SUBNET.contracts.decoded"
    log_info "  2. Message published to ducklake.decoded_transactions_evm.$NETWORK.$SUBNET.write"
    log_info "  3. DuckLake write request contains table_name, partition_values, record"
}

test_processed_transaction_flow() {
    log_info "Testing processed transaction flow..."

    # Create processed transaction payload (matches ProcessedTransaction struct)
    local processed_tx=$(cat <<EOF
{
    "network": "$NETWORK",
    "subnet": "$SUBNET",
    "vm_type": "evm",
    "transaction_hash": "$TX_HASH",
    "block_number": 19000002,
    "transaction_index": 42,
    "from_address": "0x2222222222222222222222222222222222222222",
    "to_address": "0x3333333333333333333333333333333333333333",
    "value": "1000000000000000000",
    "timestamp": $(date +%s),
    "processed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "processor_id": "eth-process-e2e-test",
    "processing_duration_ms": 15,
    "vm_specific_data": {
        "gas_used": "21000",
        "gas_price": "20000000000",
        "nonce": 5
    }
}
EOF
)

    log_info "Step 1: Starting subscriber on ducklake.>..."
    timeout 15 nats sub --server="$NATS_URL" "ducklake.>" &
    local sub_pid=$!
    sleep 2

    log_info "Step 2: Publishing processed transaction to blockchain.$NETWORK.$SUBNET.transactions.processed..."
    echo "$processed_tx" | nats pub --server="$NATS_URL" \
        "blockchain.$NETWORK.$SUBNET.transactions.processed" --read-stdin

    log_info "Step 3: Waiting for processing (10s)..."
    sleep 10

    kill $sub_pid 2>/dev/null || true

    log_info "Test complete"
    echo ""
    log_info "Expected results:"
    log_info "  1. Message published to ducklake.transactions_evm.$NETWORK.$SUBNET.write"
}

# =============================================================================
# Main
# =============================================================================

main() {
    VERBOSE=false

    for arg in "$@"; do
        case $arg in
            --setup)
                setup_port_forwards
                exit 0
                ;;
            --verbose|-v)
                VERBOSE=true
                ;;
            --help|-h)
                echo "Usage: $0 [--setup] [--verbose]"
                echo ""
                echo "Options:"
                echo "  --setup          Setup port-forwards only"
                echo "  --verbose, -v    Show debug output"
                echo ""
                echo "Environment Variables:"
                echo "  NATS_URL         NATS URL (default: nats://localhost:4222)"
                echo "  NAMESPACE        Kubernetes namespace (default: ekko)"
                exit 0
                ;;
        esac
    done

    echo "=============================================="
    echo "  DuckLake E2E Integration Test"
    echo "=============================================="
    echo ""

    # Step 1: Test decoded transaction flow
    log_info "Test 1: Decoded Transaction → DuckLake"
    test_ducklake_write_flow
    echo ""

    # Step 2: Test processed transaction flow
    log_info "Test 2: Processed Transaction → DuckLake"
    test_processed_transaction_flow
    echo ""

    echo "=============================================="
    echo "  Tests Complete"
    echo "=============================================="
    echo ""
    log_info "If you see messages on ducklake.> subjects, the flow is working!"
    log_info ""
    log_info "Next steps to verify full persistence:"
    log_info "  1. Wait 30s for micro-batch flush (if using batching)"
    log_info "  2. Check MinIO for Parquet files:"
    log_info "     mc ls myminio/ekko-data-lake/ --recursive | grep parquet"
    log_info "  3. Query DuckLake catalog in PostgreSQL"
}

main "$@"
