# Transaction DuckLake Writer Actor

A wasmCloud actor that persists processed blockchain transactions to DuckLake by publishing write requests to the `ducklake-write` provider over NATS.

## 🎯 Purpose

This actor implements the data persistence bridge in the Ekko blockchain processing pipeline. It receives processed transactions from VM-specific processing actors and forwards them to DuckLake as structured write requests for long-term analytics.

## 🏗️ Architecture

### Data Flow
```
Processing Actors → NATS (blockchain.*.*.transactions.processed) → DuckLake Writer → NATS (ducklake.*.write) → ducklake-write Provider → S3/MinIO (DuckLake)
                                      ↓
                             Parquet Files + DuckLake Catalog
```

### DuckLake Storage Layout
```
s3://ekko-ducklake/ekko/ducklake/
├── transactions_evm/                    # EVM transactions (Ethereum, Polygon, etc.)
│   ├── network=ethereum/subnet=mainnet/year=2024/month=06/day=23/hour=17/
│   │   ├── part-00000.snappy.parquet
│   │   ├── part-00001.snappy.parquet
│   │   └── ...
│   └── network=polygon/subnet=mainnet/...
├── transactions_utxo/                  # UTXO transactions (Bitcoin, Litecoin, etc.)
├── transactions_svm/                   # SVM transactions (Solana)
└── notifications/                      # Human-readable notifications
```

## 📊 Schema Design

### EVM Transactions
- **Partition Columns**: `network`, `subnet`, `year`, `month`, `day`, `hour`
- **Z-Order Columns**: `block_number`, `transaction_hash`, `from_address`, `to_address`
- **Key Fields**: Transaction data, gas analysis, value analysis, method decoding

### UTXO Transactions
- **Partition Columns**: `network`, `subnet`, `year`, `month`, `day`, `hour`
- **Z-Order Columns**: `block_number`, `transaction_hash`, `total_input_value`, `fee_satoshis`
- **Key Fields**: Input/output analysis, fee analysis, privacy scoring

### SVM Transactions
- **Partition Columns**: `network`, `subnet`, `year`, `month`, `day`, `hour`
- **Z-Order Columns**: `block_number`, `transaction_hash`, `fee_lamports`, `instruction_count`
- **Key Fields**: Instruction analysis, program interactions, compute units

## 🔧 Features

### Batch Processing
- **Configurable Batch Sizes**: EVM (1000), UTXO (500), SVM (1000)
- **Time-based Flushing**: 5-minute intervals
- **Memory Management**: In-memory buffers with overflow protection

### DuckLake Operations
- **ACID Transactions**: Atomic writes with consistency guarantees
- **Schema Evolution**: Automatic schema merging for new fields
- **Time Travel**: Query historical data at any point in time
- **Optimization**: Z-ordering and compaction for query performance

### Performance Optimizations
- **Hive-style Partitioning**: Efficient data organization by network/time
- **Snappy Compression**: Optimal balance of compression and query speed
- **Columnar Storage**: Parquet format for analytical workloads
- **Concurrent Writes**: Multiple replicas for high throughput

## 🚀 Usage

### Subscription Pattern
The actor subscribes to processed transactions from all VM types:
- `blockchain.{network}.{subnet}.transactions.processed`
- `blockchain.{network}.{subnet}.contracts.decoded`

### Configuration
```yaml
# In wasmCloud manifest
- name: transaction-ducklake-writer
  type: actor
  traits:
    - type: link
      properties:
        target: nats-messaging
        namespace: wasmcloud
        package: messaging
        interfaces: [consumer]
        values:
          subscriptions: "blockchain.>.>.transactions.processed,blockchain.>.>.contracts.decoded"
```

### Environment Variables (ducklake-write provider)
```bash
# S3/MinIO Configuration
DUCKLAKE_S3_ENDPOINT=http://localhost:9000
DUCKLAKE_S3_BUCKET=ekko-ducklake
DUCKLAKE_S3_ACCESS_KEY_ID=minioadmin
DUCKLAKE_S3_SECRET_ACCESS_KEY=minioadmin
DUCKLAKE_S3_REGION=us-east-1

# DuckLake Configuration
DUCKLAKE_WAREHOUSE_PATH=ekko/ducklake
DUCKLAKE_MAX_BATCH_SIZE=10000
DUCKLAKE_ENABLE_OPTIMIZATION=true
DUCKLAKE_ENABLE_METRICS=true
```

## 📈 Query Examples

### Time Travel Queries
```sql
-- Query data as of specific version
SELECT * FROM transactions_evm 
VERSION AS OF 1234567890
WHERE network = 'ethereum' AND block_number = 18500000;

-- Query data as of timestamp
SELECT * FROM transactions_evm 
TIMESTAMP AS OF '2024-06-23T17:00:00Z'
WHERE transaction_category = 'defi_interaction';
```

### Analytics Queries
```sql
-- Daily transaction volume by network
SELECT 
    network,
    subnet,
    DATE(from_unixtime(block_timestamp)) as date,
    COUNT(*) as tx_count,
    SUM(value_eth) as total_value_eth,
    AVG(gas_price_gwei) as avg_gas_price
FROM transactions_evm
WHERE year = 2024 AND month = 6
GROUP BY network, subnet, DATE(from_unixtime(block_timestamp))
ORDER BY date DESC;

-- Top gas consumers
SELECT 
    from_address,
    COUNT(*) as tx_count,
    SUM(gas_used * gas_price_gwei / 1e9) as total_gas_cost_eth
FROM transactions_evm
WHERE year = 2024 AND month = 6 AND day = 23
GROUP BY from_address
ORDER BY total_gas_cost_eth DESC
LIMIT 100;
```

### Cross-Chain Analysis
```sql
-- Compare transaction patterns across VM types
SELECT 
    'EVM' as vm_type,
    COUNT(*) as tx_count,
    AVG(processing_duration_ms) as avg_processing_time
FROM transactions_evm
WHERE year = 2024 AND month = 6 AND day = 23

UNION ALL

SELECT 
    'UTXO' as vm_type,
    COUNT(*) as tx_count,
    AVG(processing_duration_ms) as avg_processing_time
FROM transactions_utxo
WHERE year = 2024 AND month = 6 AND day = 23

UNION ALL

SELECT 
    'SVM' as vm_type,
    COUNT(*) as tx_count,
    AVG(processing_duration_ms) as avg_processing_time
FROM transactions_svm
WHERE year = 2024 AND month = 6 AND day = 23;
```

## 🔍 Monitoring

### Metrics
- **Batch Processing**: Records per batch, flush frequency, processing latency
- **Storage**: Data volume, partition count, file sizes
- **Performance**: Write throughput, query response times
- **Errors**: Failed writes, schema conflicts, storage issues

### Health Checks
- **Storage Connectivity**: S3/MinIO connection status
- **Catalog Integrity**: DuckLake catalog consistency validation
- **Batch Buffer Status**: Memory usage and overflow detection
- **Optimization Status**: Last optimization run, file count

## 🧪 Testing

### Unit Tests
```bash
cd wasmcloud/actors/transaction-ducklake-writer
cargo test
```

### Integration Tests
```bash
# Start test dependencies
docker-compose -f ../../../docker-compose.yml up -d minio

# Run integration tests
cargo test --features integration-tests
```

### End-to-End Testing
```bash
# Full pipeline test
cd wasmcloud
make test-e2e
```

## 📚 Dependencies

- **wasmcloud-component**: wasmCloud component SDK
- **wit-bindgen**: WIT bindings for wasmCloud interfaces
- **serde**: JSON serialization for DuckLake write requests
- **serde_json**: JSON handling and payload construction
- **anyhow**: Error handling utilities

## 🔧 Development

### Local Setup
```bash
# Start MinIO
make docker-deps

# Build actor
cargo build --target wasm32-wasip1

# Deploy to local wasmCloud
make deploy-dev
```

### Schema Evolution
When adding new fields to transaction records:
1. Update DuckLake schema definitions in `apps/wasmcloud/shared/ducklake-common/src/schemas.rs`
2. Update record mapping in `apps/wasmcloud/actors/transaction-ducklake-writer/src/lib.rs`
3. Run unit tests and provider schema validation
4. Deploy with schema merging enabled

### Performance Tuning
- **Batch Sizes**: Adjust via `DUCKLAKE_MAX_BATCH_SIZE` in the ducklake-write provider
- **Partition Strategy**: Consider different time granularities
- **Z-Ordering**: Add columns based on query patterns
- **Compaction**: Schedule optimizations based on write patterns
