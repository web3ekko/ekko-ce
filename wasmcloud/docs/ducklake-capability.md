# DuckLake Capability Provider

The DuckLake capability provider enables wasmCloud actors to store and query blockchain transaction data using DuckLake format with ACID transactions, time travel, and optimized analytics.

## Overview

The DuckLake capability provides:

- **ACID Transactions**: Reliable data consistency for blockchain transaction storage
- **Time Travel**: Query historical versions of data for auditing and analysis
- **Schema Evolution**: Safely evolve table schemas as requirements change
- **Optimized Analytics**: Z-ordering and compaction for fast queries
- **S3 Compatibility**: Works with AWS S3, MinIO, and other S3-compatible storage

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Transaction     │    │ DuckLake       │    │ S3/MinIO        │
│ Processing      │───▶│ Capability       │───▶│ Storage         │
│ Actors          │    │ Provider         │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ DataFusion       │
                       │ Query Engine     │
                       └──────────────────┘
```

## Table Schemas

### EVM Transactions (`transactions_evm`)

Stores Ethereum and EVM-compatible blockchain transactions with gas analysis and method decoding.

**Partition Columns**: `network`, `subnet`, `year`, `month`, `day`, `hour`
**Z-Order Columns**: `block_number`, `transaction_hash`, `from_address`, `to_address`

Key fields:
- Transaction identifiers (hash, block number, index)
- Gas analysis (price, limit, used, categories)
- Method decoding (signature, name, parameters)
- Value analysis (ETH, USD, categories)
- Processing metadata

### UTXO Transactions (`transactions_utxo`)

Stores Bitcoin and UTXO-based blockchain transactions with privacy analysis.

**Partition Columns**: `network`, `subnet`, `year`, `month`, `day`, `hour`
**Z-Order Columns**: `block_number`, `transaction_hash`, `total_input_value`, `fee_satoshis`

Key fields:
- Input/output analysis (addresses, script types, values)
- Fee analysis (rate, categories)
- Privacy scoring (mixing detection, CoinJoin probability)
- Transaction characteristics (RBF, SegWit, Coinbase)

### SVM Transactions (`transactions_svm`)

Stores Solana and SVM-based blockchain transactions with program interaction analysis.

**Partition Columns**: `network`, `subnet`, `year`, `month`, `day`, `hour`
**Z-Order Columns**: `block_number`, `transaction_hash`, `fee_lamports`, `instruction_count`

Key fields:
- Instruction analysis (programs, accounts, data)
- Compute unit consumption and limits
- Token and NFT transfers
- Program interaction patterns

### Notifications (`notifications`)

Stores human-readable notifications generated from transaction analysis.

**Partition Columns**: `network`, `notification_type`, `year`, `month`, `day`, `hour`
**Z-Order Columns**: `timestamp`, `transaction_hash`, `severity`

Key fields:
- Notification metadata (type, severity, confidence)
- Human-readable title and message
- Context data (addresses, values, methods)
- Categorization and tagging

## Configuration

### Environment Variables

```bash
# S3/MinIO Configuration
S3_ENDPOINT=http://localhost:9000
S3_REGION=us-east-1
S3_BUCKET=ekko-ducklake
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin

# DuckLake Configuration
DUCKLAKE_S3_ENDPOINT=http://localhost:9000
DUCKLAKE_S3_REGION=us-east-1
DUCKLAKE_S3_BUCKET=ekko-ducklake
DUCKLAKE_S3_ACCESS_KEY_ID=minioadmin
DUCKLAKE_S3_SECRET_ACCESS_KEY=minioadmin
DUCKLAKE_WAREHOUSE_PATH=/ekko/ducklake
DUCKLAKE_MAX_BATCH_SIZE=10000
DUCKLAKE_ENABLE_METRICS=false

# Provider Configuration
PROVIDER_INSTANCE_ID=ducklake-write-provider-1
```

### wasmCloud Manifest

```yaml
components:
  - name: ducklake-write
    type: capability
    properties:
      image: ghcr.io/ekko-zone/ducklake-write:v0.1.0
    traits:
      - type: config
        properties:
          config:
            ducklake_s3_endpoint: "http://localhost:9000"
            ducklake_s3_bucket: "ekko-ducklake"
            ducklake_s3_access_key_id: "minioadmin"
            ducklake_s3_secret_access_key: "minioadmin"
            ducklake_s3_region: "us-east-1"
            ducklake_postgres_host: "postgres"
            ducklake_postgres_port: "5432"
            ducklake_postgres_user: "ekko"
            ducklake_postgres_password: "ekko123"
            ducklake_postgres_database: "ducklake_catalog"
            ducklake_write_subject: "ducklake.>"
            ducklake_warehouse_path: "ekko/ducklake"

  - name: transaction-ducklake-writer
    type: actor
    properties:
      image: ghcr.io/ekko-zone/transaction-ducklake-writer:v0.1.0
```

## Usage Examples

### Creating Tables

```rust
// Create EVM transactions table
let schema = TableSchema::evm_transactions();
ducklake_provider.create_table(&schema).await?;

// Create custom table
let custom_schema = TableSchema {
    name: "custom_events".to_string(),
    location: "s3://my-bucket/custom_events".to_string(),
    partitioning: PartitionSpec {
        columns: vec!["network".to_string(), "year".to_string()],
        z_order_columns: vec!["timestamp".to_string()],
    },
    version: "1.0".to_string(),
};
ducklake_provider.create_table(&custom_schema).await?;
```

### Writing Data

```rust
// Prepare transaction data
let transaction_data = json!({
    "network": "ethereum",
    "subnet": "mainnet",
    "transaction_hash": "0x123...",
    "block_number": 19000000,
    "value_eth": 1.5,
    // ... other fields
});

// Create batch write request
let batch_request = BatchWriteRequest {
    table: "transactions_evm".to_string(),
    records: vec![serde_json::to_string(&transaction_data)?],
    partition_values: Some(vec![
        ("network".to_string(), "ethereum".to_string()),
        ("year".to_string(), "2024".to_string()),
    ]),
};

// Write to DuckLake
let records_written = ducklake_provider.append_batch(&batch_request).await?;
```

### Querying Data

```rust
// Basic aggregation query
let sql = r#"
    SELECT 
        network,
        COUNT(*) as transaction_count,
        AVG(value_eth) as avg_value_eth,
        SUM(gas_used) as total_gas_used
    FROM transactions_evm 
    WHERE year = 2024 AND month = 6
    GROUP BY network
    ORDER BY transaction_count DESC
"#;

let result = ducklake_provider.query(sql).await?;
println!("Found {} rows in {}ms", result.row_count, result.execution_time_ms);

// Time travel query (specific version)
let sql = "SELECT * FROM transactions_evm VERSION AS OF 42";
let result = ducklake_provider.query_version(sql, 42).await?;

// Time travel query (timestamp)
let timestamp = Utc::now().timestamp() - 3600; // 1 hour ago
let sql = "SELECT * FROM transactions_evm";
let result = ducklake_provider.query_timestamp(sql, timestamp as u64).await?;
```

### Analytics Queries

```rust
// Gas price analysis
let sql = r#"
    SELECT 
        gas_price_category,
        COUNT(*) as tx_count,
        AVG(gas_price_gwei) as avg_gas_price,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gas_price_gwei) as median_gas_price
    FROM transactions_evm 
    WHERE network = 'ethereum' 
      AND year = 2024 AND month = 6
    GROUP BY gas_price_category
"#;

// High-value transaction detection
let sql = r#"
    SELECT 
        transaction_hash,
        from_address,
        to_address,
        value_eth,
        value_usd,
        block_timestamp
    FROM transactions_evm 
    WHERE value_usd > 1000000  -- $1M+ transactions
      AND year = 2024
    ORDER BY value_usd DESC
    LIMIT 100
"#;

// Contract interaction patterns
let sql = r#"
    SELECT 
        contract_address,
        method_name,
        COUNT(*) as call_count,
        COUNT(DISTINCT from_address) as unique_callers,
        AVG(gas_used) as avg_gas_used
    FROM transactions_evm 
    WHERE contract_address IS NOT NULL
      AND year = 2024 AND month = 6
    GROUP BY contract_address, method_name
    HAVING call_count > 1000
    ORDER BY call_count DESC
"#;
```

### Optimization Operations

```rust
// Optimize table (compaction and Z-ordering)
let result = ducklake_provider.optimize_table("transactions_evm").await?;
println!("Optimized {} files, removed {} files",
         result.files_compacted, result.files_removed);

// Vacuum old files (remove files older than retention period)
let retention_hours = 168; // 7 days
let result = ducklake_provider.vacuum_table("transactions_evm", retention_hours).await?;
println!("Vacuum removed {} files", result.files_removed);

// Get table statistics
let stats = ducklake_provider.get_table_stats("transactions_evm").await?;
println!("Table has {} files, {} bytes, {} partitions",
         stats.file_count, stats.size_bytes, stats.partition_count);
```

## Performance Optimization

### Partitioning Strategy

Tables are partitioned by:
1. **Network** - Isolate different blockchains
2. **Subnet** - Separate mainnet/testnet data
3. **Time** - Year/month/day/hour for time-based queries

### Z-Ordering

Z-ordering optimizes for common query patterns:
- **Block number** - Sequential access patterns
- **Transaction hash** - Point lookups
- **Addresses** - Address-based filtering
- **Values/fees** - Range queries on amounts

### Query Optimization Tips

1. **Use partition filters**: Always filter by network, subnet, and time
2. **Leverage Z-order columns**: Filter on block_number, addresses, values
3. **Batch operations**: Use large batch sizes for writes
4. **Regular optimization**: Run OPTIMIZE and VACUUM operations

```sql
-- Good: Uses partition and Z-order columns
SELECT * FROM transactions_evm
WHERE network = 'ethereum'
  AND year = 2024 AND month = 6
  AND block_number BETWEEN 19000000 AND 19100000
  AND from_address = '0x123...';

-- Avoid: No partition filters
SELECT * FROM transactions_evm
WHERE value_eth > 10;
```

## Monitoring and Metrics

### Table Health Checks

```rust
// Check table existence
let exists = ducklake_provider.table_exists("transactions_evm").await?;

// Get table history
let history = ducklake_provider.get_table_history("transactions_evm", Some(10)).await?;

// List all tables
let tables = ducklake_provider.list_tables().await?;
```

### Performance Metrics

When `DUCKLAKE_ENABLE_METRICS=true`:
- Write throughput (records/second)
- Query latency (milliseconds)
- Storage efficiency (compression ratio)
- Optimization frequency and effectiveness

## Development Setup

### Local Environment

1. **Start infrastructure**:
```bash
cd wasmcloud
docker-compose up -d
```

2. **Build provider**:
```bash
cd providers/ducklake-write
cargo build --release

cd ../ducklake-read
cargo build --release
```

3. **Build actor**:
```bash
cd actors/transaction-ducklake-writer
wash build
```

4. **Deploy application**:
```bash
wash app deploy manifests/dev.yaml
```

### Testing

```bash
# Run unit tests
cargo test --package ducklake-write-provider
cargo test --package ducklake-read-provider

# Run integration tests (requires Docker)
cargo test --package ducklake-provider --test integration_tests

# Test with real MinIO
S3_ENDPOINT=http://localhost:9000 \
S3_ACCESS_KEY_ID=minioadmin \
S3_SECRET_ACCESS_KEY=minioadmin \
cargo test --package ducklake-provider --test integration_tests
```

## Production Deployment

### AWS S3 Configuration

```yaml
# Production manifest
config:
  DUCKLAKE_S3_ENDPOINT: "https://s3.amazonaws.com"
  DUCKLAKE_S3_REGION: "${AWS_REGION}"
  DUCKLAKE_S3_BUCKET: "${DUCKLAKE_S3_BUCKET}"
  DUCKLAKE_S3_ACCESS_KEY_ID: "${AWS_ACCESS_KEY_ID}"
  DUCKLAKE_S3_SECRET_ACCESS_KEY: "${AWS_SECRET_ACCESS_KEY}"
  DUCKLAKE_ENABLE_OPTIMIZATION: "true"
  DUCKLAKE_MAX_BATCH_SIZE: "50000"
  DUCKLAKE_ENABLE_METRICS: "true"
```

### Scaling Considerations

- **Provider replicas**: Scale based on write throughput
- **Actor replicas**: Scale based on message processing load
- **Optimization frequency**: More frequent for high-write workloads
- **Retention policy**: Balance storage costs with query needs

### Security

- Use IAM roles for S3 access in production
- Enable S3 bucket encryption
- Implement network security groups
- Monitor access patterns and costs

## Troubleshooting

### Common Issues

1. **S3 Connection Errors**
   - Verify endpoint URL and credentials
   - Check network connectivity
   - Ensure bucket exists and has proper permissions

2. **Schema Errors**
   - Validate JSON record structure
   - Check for missing required fields
   - Verify data types match schema

3. **Performance Issues**
   - Run OPTIMIZE operations regularly
   - Check partition pruning in queries
   - Monitor file sizes and counts

### Debug Logging

```bash
RUST_LOG=debug ./ducklake-provider
```

### Health Checks

```rust
// Verify provider health
let tables = ducklake_provider.list_tables().await?;
let stats = ducklake_provider.get_table_stats("transactions_evm").await?;
```
