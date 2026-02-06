# Alerts-Processor Actor

wasmCloud WASM component that processes blockchain alert jobs from NATS queues using capability providers.

## Overview

The Alerts-Processor Actor is a high-performance WASM component that processes blockchain alert jobs, evaluates alert conditions using Polars, and publishes results. It supports three trigger types with different latency targets:

- **Event-Driven**: Real-time alerts (<2s latency, 100+ jobs/sec)
- **Periodic**: Scheduled alerts (<5s latency, 50+ jobs/sec)
- **One-Off**: One-time alerts (<10s latency, 20+ jobs/sec)

## Architecture

```
NATS Queue → Actor → [DuckLake | RPC | HTTP] → Polars Provider → Redis → NATS Results
```

### Capability Providers

1. **NATS Messaging**: Job consumption from `alerts.jobs.*` and result publishing
2. **Redis KV**: Job state and alert instance state storage
3. **DuckLake Provider**: Time-series blockchain data queries
4. **RPC Provider**: Real-time blockchain RPC calls (Ethereum, Bitcoin, Solana)
5. **Polars Provider**: Alert evaluation code execution
6. **HTTP Client**: External API calls and webhooks

### Processing Pipeline

```
1. Validate Job
   ↓
2. Check Retry State
   ↓
3. Fetch Data Sources (DuckLake, RPC, HTTP)
   ↓
4. Evaluate Alert Condition (Polars)
   ↓
5. Update Instance State (Redis)
   ↓
6. Store Job Result (Redis)
   ↓
7. Publish Result (NATS)
   ↓
8. Cleanup Retry State
```

## Project Structure

```
alerts-processor/
├── Cargo.toml              # Package configuration
├── wasmcloud.toml          # wasmCloud metadata
├── wadm.yaml               # WADM deployment manifest
├── README.md               # This file
├── wit/                    # WIT interface definitions
│   ├── world.wit           # Main actor world
│   └── deps/               # Provider interface dependencies
├── src/
│   ├── lib.rs              # Main actor with WIT bindings
│   ├── types.rs            # Core type definitions
│   ├── pipeline.rs         # Common processing pipeline
│   ├── providers/          # Provider client modules
│   └── handlers/           # Trigger-specific handlers
└── tests/
    └── integration_tests.rs    # Integration tests
```

## Build

```bash
# Build WASM component
cargo build --target wasm32-wasip1 --release

# Or use wash
wash build

# Or use unified build script
cd ../../
./build.sh
```

The signed WASM will be at: `actors/alerts-processor/build/alerts-processor_s.wasm`

## Deploy

```bash
# Push to registry
wash push host.docker.internal:5001/alerts-processor:v1.0.0 \
  target/wasm32-wasip1/release/alerts_processor.wasm \
  --insecure --allow-latest

# Deploy with WADM
wash app deploy wadm.yaml

# Check status
wash app status alerts-processor
```

## Testing

```bash
# Run all tests
cargo test

# Run specific test suite
cargo test --test integration_tests

# Run with output
cargo test -- --nocapture
```

## Configuration

See `wadm.yaml` for provider link configuration including:
- NATS subscriptions
- Redis connection
- DuckLake connection
- RPC provider URLs
- Polars execution limits

## Performance Targets

| Trigger Type | Target (p95) | Throughput |
|--------------|--------------|------------|
| Event-Driven | <2s          | 100+ jobs/sec |
| Periodic     | <5s          | 50+ jobs/sec  |
| One-Off      | <10s         | 20+ jobs/sec  |

**Resource**: <50MB memory per instance

## Alert Job Format

### Example AlertJob
```json
{
  "job_id": "unique-job-id",
  "instance_id": "alert-instance-id",
  "template_id": "alert-template-id",
  "trigger_type": "event_driven",
  "polars_code": "import polars as pl\n...",
  "parameters": {
    "threshold": "1000"
  },
  "data_sources": [
    {
      "name": "transactions",
      "source_type": "ducklake",
      "config": {
        "table": "eth_transactions",
        "columns": "hash,from,to,value",
        "limit": "1000"
      }
    }
  ],
  "metadata": {
    "retry_count": 0,
    "max_retries": 3,
    "timeout_seconds": 10,
    "created_at": "2024-01-15T10:30:00Z",
    "scheduled_for": null
  }
}
```

### Data Source Examples

**DuckLake**:
```json
{
  "name": "transactions",
  "source_type": "ducklake",
  "config": {
    "table": "eth_transactions",
    "columns": "hash,from,to,value",
    "partition_filter": "network='ethereum'",
    "limit": "1000"
  }
}
```

**RPC (Ethereum)**:
```json
{
  "name": "balance",
  "source_type": "rpc",
  "config": {
    "network": "ethereum",
    "method": "getBalance",
    "address": "0x123..."
  }
}
```

**HTTP**:
```json
{
  "name": "external_api",
  "source_type": "http",
  "config": {
    "method": "GET",
    "url": "https://api.example.com/data"
  }
}
```

## Error Handling

### Transient Errors (Retryable)
- NATS/Redis/DuckLake connection failures
- RPC provider timeouts
- HTTP request failures

### Permanent Errors (Not Retryable)
- Invalid Polars code
- Invalid data source configuration
- Max retries exceeded
- Validation errors

## Monitoring

All operations emit structured logs:
```rust
tracing::info!(
    job_id = %job.job_id,
    triggered = result.triggered,
    execution_time_ms = execution_time_ms,
    "Alert job processing completed"
);
```

## Related Documentation

- **PRD**: `/docs/prd/wasmcloud/actors/PRD-Alerts-Processor-Actor-USDT.md`
- **Alert System**: `/docs/prd/apps/api/PRD-Alert-System-USDT.md`
- **wasmCloud Docs**: https://wasmcloud.com/docs

## License

Copyright © 2024 Ekko Team
