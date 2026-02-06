# ETH Transfers Processor Actor

wasmCloud actor that processes ETH transfer transactions with balance tracking, transfer categorization, and alert routing.

## Overview

This actor receives transfer transactions from the `eth_process_transactions` actor and enriches them with:
- Balance tracking and updates
- Transfer size categorization (Micro/Small/Medium/Large/Whale)
- Address type detection (EOA/Contract)
- Standardized enrichment fields for cross-actor consistency
- Multi-destination routing (alerts, balances, DuckLake)

## Architecture

- **Runtime**: wasmCloud WebAssembly actor
- **Language**: Rust 2021 Edition
- **Target**: wasm32-wasip1
- **Interfaces**: WIT-based wasmCloud 1.0 patterns

## Message Flow

### Input
- **Subscribe**: `transfer-transactions.*.*.evm.raw`
- **Format**: `RawTransferTransaction` from eth_process_transactions

### Outputs
- **Processed Transfers**: `transfers.processed.evm`
- **Alert Evaluation**: `alerts.evaluate.{chain}.{subnet}`
- **Balance Updates**: `balances.updated.{chain}.{subnet}`
- **Historical Storage**: `ducklake.transactions.{chain}.{subnet}.write`

## Data Structures

### ProcessedTransfer
```rust
pub struct ProcessedTransfer {
    // Network context
    pub network: String,
    pub subnet: String,
    pub vm_type: String,

    // Transfer data
    pub from_address: String,
    pub to_address: String,
    pub amount_wei: String,
    pub amount_eth: f64,

    // Enrichment
    pub transfer_category: TransferCategory,
    pub sender_type: AddressType,
    pub recipient_type: AddressType,

    // Balance context
    pub sender_balance_before: Option<String>,
    pub sender_balance_after: Option<String>,
    pub recipient_balance_before: Option<String>,
    pub recipient_balance_after: Option<String>,

    // Standardized enrichment (7 required fields)
    pub transaction_type: String,        // "transfer"
    pub transaction_currency: String,    // "ETH", "MATIC", etc.
    pub transaction_value: String,       // "1.5 ETH"
    pub transaction_subtype: String,     // "native", "erc20", "internal"
    pub protocol: Option<String>,        // None or "ERC20"
    pub category: String,                // "value_transfer"
    pub decoded: serde_json::Value,      // Transfer details
}
```

## Features

### Transfer Categorization
- **Micro**: < 0.01 ETH
- **Small**: 0.01 - 1 ETH
- **Medium**: 1 - 10 ETH
- **Large**: 10 - 100 ETH
- **Whale**: > 100 ETH

### Network Support
- Ethereum (ETH)
- Polygon (MATIC)
- Binance Smart Chain (BNB)
- Avalanche (AVAX)

### Enrichment Fields
All transfers include 7 standardized enrichment fields for cross-actor consistency:
1. `transaction_type`: Always "transfer"
2. `transaction_currency`: Native currency symbol
3. `transaction_value`: Formatted amount with symbol
4. `transaction_subtype`: "native", "erc20", or "internal"
5. `protocol`: None for native, "ERC20" for tokens
6. `category`: Always "value_transfer"
7. `decoded`: JSON object with transfer details

## Building

```bash
# Check compilation
cargo check --target wasm32-wasip1

# Run tests
cargo test --lib

# Build WASM component
cargo build --release --target wasm32-wasip1

# Build with wasmCloud
wash build
```

## Testing

```bash
# Run unit tests
cargo test --lib

# Run all tests
cargo test

# Check coverage
cargo tarpaulin --lib --ignore-tests
```

### Test Coverage
- **Unit Tests**: 10 tests covering core functionality
- **Coverage Target**: 95%
- **Test Files**: Inline tests in `src/lib.rs`

## Configuration

Configuration via `wasmcloud.toml`:

```toml
[component.config]
# Transfer categorization thresholds (in ETH)
micro_threshold = "0.01"
small_threshold = "1.0"
medium_threshold = "10.0"
large_threshold = "100.0"

# Routing configuration
subscribe_pattern = "transfer-transactions.*.*.evm.raw"
processed_subject = "transfers.processed.evm"
alert_subject_pattern = "alerts.evaluate.{chain}"
balance_subject_pattern = "balances.updated.{chain}"
ducklake_subject = "ducklake.transactions"
```

## Performance

- **Target Latency**: < 10ms p95
- **Throughput**: > 5,000 transfers/second
- **Memory**: < 128MB per instance
- **WASM Size**: ~231KB

## Dependencies

- `wit-bindgen`: wasmCloud WIT interface generation
- `serde`/`serde_json`: Serialization
- `chrono`: Timestamp handling
- `anyhow`: Error handling

## Integration

Part of the Ekko blockchain monitoring platform:
- **Upstream**: `eth_process_transactions` actor
- **Downstream**: Alert evaluator, balance tracker, DuckLake
- **State**: Redis for balance caching (future)

## License

Copyright (c) 2025 Ekko
