# EVM Raw Transactions Service (wasmCloud 1.0)

A native Rust service that processes blockchain newheads and fetches raw transactions for all EVM-compatible chains.

## Architecture

This service has been migrated from a wasmCloud actor to a native Rust service for:
- **Better performance** - Native execution vs WASM
- **No dependency conflicts** - Eliminated nuid/wasmbus-rpc issues  
- **Easier development** - Standard Rust tooling
- **Direct connections** - NATS, Redis, HTTP without wasmCloud interfaces

## Flow

```
Newheads Provider → NATS → eth_raw_transactions → Redis Config → Blockchain RPC → NATS
                    ↓                              ↓                ↓              ↓
              newheads.*.*.evm          nodes:network:subnet:vm   HTTP Request   transactions.raw.evm
```

## Configuration

### Environment Variables

- `NATS_URL`: NATS server URL (default: `nats://127.0.0.1:4222`)
- `REDIS_URL`: Redis server URL (default: `redis://127.0.0.1:6379`)

### Redis Configuration

Network endpoints are stored in Redis with the key pattern:
```
nodes:{network}:{subnet}:{vm_type}
```

Example:
```json
{
  "rpc_urls": [
    "https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY",
    "https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
  ],
  "ws_urls": [
    "wss://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"
  ],
  "chain_id": 1,
  "enabled": true
}
```

## Running

### Development
```bash
# From wasmcloud directory
cargo run --package eth_raw_transactions --bin eth_raw_transactions
```

### Production
```bash
# Build release binary
cargo build --release --package eth_raw_transactions --bin eth_raw_transactions

# Run binary
./target/release/eth_raw_transactions
```

### Docker
```dockerfile
FROM rust:1.75 as builder
WORKDIR /app
COPY . .
RUN cargo build --release --package eth_raw_transactions --bin eth_raw_transactions

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/eth_raw_transactions /usr/local/bin/
CMD ["eth_raw_transactions"]
```

## NATS Subjects

### Subscribes To
- `newheads.*.*.evm` - Blockchain newheads from all EVM networks

### Publishes To  
- `transactions.raw.evm` - Raw transaction data for processing

## Scaling

- **Horizontal**: Run multiple instances
- **Load balancing**: NATS consumer groups
- **Network isolation**: Each instance can handle different networks
- **High availability**: Multiple instances across zones

## Monitoring

The service uses `tracing` for structured logging:
- Info: Block processing, transaction counts
- Error: RPC failures, Redis connection issues
- Debug: Detailed transaction processing

## Migration Notes

This service was migrated from wasmCloud actor to native Rust service:
- ✅ Removed wasmbus-rpc dependency
- ✅ Direct NATS/Redis connections
- ✅ Eliminated nuid conflicts
- ✅ Better performance and debugging
- ✅ Standard Rust ecosystem tools
