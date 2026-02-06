#!/bin/bash

# Build all WasmCloud actors
# This script compiles all actors to WASM and copies them to the chart directory

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ACTORS_DIR="${SCRIPT_DIR}/actors"
TARGET_DIR="${SCRIPT_DIR}/target/wasm32-wasip1/release"
CHART_ACTORS_DIR="${SCRIPT_DIR}/chart/actors"

echo "Building all WasmCloud actors..."

# List of all actors
ACTORS=(
    "abi-decoder"
    "alerts-processor"
    "btc_raw_transactions"
    "evm_logs_ingestion"
    "eth_contract_creation_processor"
    "eth_contract_transaction_processor"
    "eth_process_transactions"
    "eth_raw_transactions"
    "eth_transfers_processor"
    "health-check"
    "notification-router"
    "sol_raw_transactions"
    "transaction-ducklake-writer"
    "transaction-processor"
)

# Build all actors
echo "Compiling actors to WASM..."
cargo build --release --target wasm32-wasip1 \
    -p abi-decoder \
    -p alerts-processor \
    -p btc_raw_transactions \
    -p evm_logs_ingestion \
    -p eth_contract_creation_processor \
    -p eth_contract_transaction_processor \
    -p eth_process_transactions \
    -p eth_raw_transactions \
    -p eth_transfers_processor \
    -p health-check \
    -p notification-router \
    -p sol_raw_transactions \
    -p transaction-ducklake-writer \
    -p transaction-processor

echo "Copying WASM binaries to actor directories..."

# Copy each actor's WASM to its build directory and chart directory
for actor in "${ACTORS[@]}"; do
    # Convert actor name to underscore format for the compiled file
    wasm_name=$(echo "$actor" | tr '-' '_')

    # Source and destination paths
    src="${TARGET_DIR}/${wasm_name}.wasm"
    actor_build_dir="${ACTORS_DIR}/${actor}/build"
    chart_build_dir="${CHART_ACTORS_DIR}/${actor}/build"

    # Create build directories if they don't exist
    mkdir -p "${actor_build_dir}"
    mkdir -p "${chart_build_dir}"

    # Copy to actor's build directory with _s suffix (signed)
    if [[ -f "$src" ]]; then
        dst_actor="${actor_build_dir}/${actor}_s.wasm"
        dst_chart="${chart_build_dir}/${actor}_s.wasm"

        cp "$src" "$dst_actor"
        cp "$src" "$dst_chart"

        echo "✅ ${actor}: $(du -h "$dst_actor" | cut -f1)"
    else
        echo "❌ ${actor}: WASM file not found at $src"
    fi
done

echo ""
echo "Build complete! WASM actors are ready for deployment."
echo ""
echo "To deploy to Kubernetes, run:"
echo "  helm upgrade --install wasmcloud ./chart -n ekko"
