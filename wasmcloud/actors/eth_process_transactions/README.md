# Ethereum Process Transactions Actor (wasmCloud 1.0)

A wasmCloud 1.0 actor that processes raw EVM transactions and routes them based on transaction type through three distinct scenarios.

## Architecture

This actor implements a sophisticated transaction processing pipeline:
- **Scenario-based routing** - Different transaction types follow different paths
- **Internal transaction processing** - Handles complex multi-call transactions
- **wasmCloud 1.0 ready** - Structured for WIT interface integration
- **Comprehensive testing** - 23 passing tests covering all functionality

## Transaction Processing Flow

```
evm_raw_transactions → transactions.{network}.{subnet}.evm.raw → eth_process_transactions → Multiple Destinations
                                                        ↓
                                              ┌─────────┼─────────┐
                                              ▼         ▼         ▼
                                         Transfer  Contract   Function
                                                  Creation    Call
                                              ▼         ▼         ▼
                                         DuckLake  DuckLake  ABI Decode
                                                   Contracts
```

## Three Processing Scenarios

### Scenario 1: Transfer Transactions
- **Detection**: `to_address` exists, `input_data` is empty or "0x"
- **Processing**: Extract transfer details (amount, recipient)
- **Routing**: Direct to DuckLake → `transfer-transactions.{network}.{subnet}.{vm_type}.raw`

### Scenario 2: Contract Creation
- **Detection**: `to_address` is null/empty, `input_data` contains bytecode
- **Processing**: Extract creation details (bytecode size, gas estimation)
- **Routing**: To contract indexing and DuckLake → `contract-creations.{network}.{subnet}.{vm_type}.raw`

### Scenario 3: Function Calls
- **Detection**: `to_address` exists, `input_data` contains function call data
- **Processing**: Extract function signature and call data
- **Routing**: To ABI decoding → `contract-transactions.{network}.{subnet}.{vm_type}.raw`

## Internal Transaction Processing

The actor automatically detects and processes internal transactions:
- **Extraction**: Identifies internal calls within main transactions
- **Processing**: Each internal call goes through the same 3 scenarios
- **Inheritance**: Internal transactions inherit network/block data from parent
- **Identification**: Unique hash suffixes for internal transactions

## Data Structure

### ProcessedTransaction with Flexible Details
```json
{
  "transaction_hash": "0x...",
  "network": "ethereum",
  "subnet": "mainnet",
  "vm_type": "evm",
  "transaction_category": "Transfer",
  "gas_analysis": {
    "price_gwei": 20.0,
    "category": "Standard"
  },
  "details": {
    "type": "transfer",
    "amount_wei": "1000000000000000000",
    "amount_eth": "1.0",
    "recipient": "0x..."
  }
}
```

## Configuration

### Environment Variables
- `NATS_URL`: NATS server URL (default: `nats://127.0.0.1:4222`)
- `REDIS_URL`: Redis server URL (default: `redis://127.0.0.1:6379`)

## Running

### Development
```bash
# From wasmcloud directory
cargo run --package eth_process_transactions --bin eth_process_transactions
```

### Production
```bash
# Build release binary
cargo build --release --package eth_process_transactions --bin eth_process_transactions

# Run binary
./target/release/eth_process_transactions
```

### Docker
```dockerfile
FROM rust:1.75 as builder
WORKDIR /app
COPY . .
RUN cargo build --release --package eth_process_transactions --bin eth_process_transactions

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/eth_process_transactions /usr/local/bin/
CMD ["eth_process_transactions"]
```

## NATS Subjects

### Subscribes To
- `transactions.*.*.evm.raw` - Raw transaction data from evm_raw_transactions (wildcard pattern for all EVM chains)
  - Examples: `transactions.ethereum.mainnet.evm.raw`, `transactions.polygon.mainnet.evm.raw`

### Publishes To  
- `transfer-transactions.{network}.{subnet}.{vm_type}.raw` - Transfer transactions to DuckLake
- `contract-creations.{network}.{subnet}.{vm_type}.raw` - Contract creation transactions
- `contract-transactions.{network}.{subnet}.{vm_type}.raw` - Function call transactions for ABI decoding

## Gas Price Categories

- **Low**: < 10 Gwei
- **Standard**: 10-50 Gwei  
- **High**: 50-100 Gwei
- **Extreme**: > 100 Gwei

## Transaction Types

- **Transfer**: Simple ETH transfers (empty input_data)
- **ContractCall**: Calls to existing contracts
- **ContractDeployment**: Contract creation transactions
- **Unknown**: Unrecognized patterns

## Scaling

- **Horizontal**: Run multiple instances
- **Load balancing**: NATS consumer groups
- **High availability**: Multiple instances across zones
- **Performance**: Native execution for high throughput

## Monitoring

The service uses `tracing` for structured logging:
- Info: Transaction processing counts, performance metrics
- Error: Processing failures, NATS/Redis connection issues
- Debug: Detailed transaction analysis

## Migration Notes

This service was migrated from wasmCloud actor to native Rust service:
- ✅ Removed wasmbus-rpc dependency
- ✅ Direct NATS/Redis connections
- ✅ Eliminated nuid conflicts
- ✅ Better performance and debugging
- ✅ Standard Rust ecosystem tools
