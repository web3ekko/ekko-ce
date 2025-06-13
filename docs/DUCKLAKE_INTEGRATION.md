# DuckLake Integration Guide

This guide explains how to integrate DuckLake into the Ekko pipeline for advanced transaction data storage with versioning, change tracking, and time travel capabilities.

## 🎯 Overview

DuckLake provides a modern data lakehouse solution that combines the benefits of data lakes and data warehouses:

- **Versioning & Snapshots**: Track all data changes with timestamps
- **Change Tracking**: See exactly what transactions were added/modified
- **Time Travel**: Query historical data at any point in time
- **Schema Evolution**: Add/modify columns without data rewrites
- **ACID Transactions**: Ensure data consistency
- **Distributed Storage**: Use MinIO/S3 for scalable storage

## 🏗️ Architecture

### Current Architecture
```
Pipeline → ArrowWriter → MinIO (Arrow files) → DuckDB API → Dashboard
```

### New Architecture with DuckLake
```
Pipeline → DuckLakeWriter → DuckLake (SQLite catalog + MinIO storage) → DuckLake API → Dashboard
```

### Key Components

1. **SQLite Catalog**: Stores DuckLake metadata (schemas, snapshots, file locations)
2. **MinIO Storage**: Stores actual Parquet data files
3. **DuckDB Extensions**: Provides DuckLake functionality and S3/MinIO access
4. **AWS Extension**: Better S3/MinIO authentication and credential management

## 🚀 Quick Start

### 1. Start Infrastructure

```bash
# Start MinIO, NATS, and Redis
docker-compose up -d minio nats redis

# Initialize MinIO buckets
docker-compose up minio-init
```

### 2. Run DuckLake Example

```bash
# Run the complete integration example
./scripts/run-ducklake-example.sh

# Or run individual steps
./scripts/run-ducklake-example.sh infrastructure
./scripts/run-ducklake-example.sh example
```

### 3. Run Integration Tests

```bash
# Run all DuckLake tests
./scripts/test-ducklake.sh

# Or run specific test types
./scripts/test-ducklake.sh unit
./scripts/test-ducklake.sh integration
./scripts/test-ducklake.sh minio
```

## ⚙️ Configuration

### Environment Variables

```bash
# DuckLake Configuration
DUCKLAKE_ENABLED=true
DUCKLAKE_CATALOG_TYPE=sqlite
DUCKLAKE_CATALOG_PATH=/data/ducklake/catalog.sqlite
DUCKLAKE_DATA_PATH=s3://ducklake-data/data
DUCKLAKE_BUCKET_NAME=ducklake-data
DUCKLAKE_BATCH_SIZE=1000
DUCKLAKE_FLUSH_INTERVAL=30s

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_REGION=us-east-1
MINIO_SECURE=false

# NATS Configuration
NATS_URL=nats://localhost:4222
NATS_STREAM=blockchain
NATS_SUBJECT=transactions
```

### Docker Compose

The `docker-compose.yml` includes:
- Shared volumes for SQLite catalog
- Environment variables for both pipeline and API
- MinIO initialization service

## 📊 Data Flow

### 1. Pipeline Writes Data

```go
// Create DuckLake writer
writer, err := persistence.NewDuckLakeWriter(config, natsConn)

// Write transaction
err = writer.WriteTransaction(ctx, transaction, nodeConfig)

// Flush data
err = writer.FlushAll(ctx)
```

### 2. API Reads Data

```python
# Create DuckLake service
service = DuckLakeService()

# Query transactions
transactions = await service.get_transactions(
    limit=100,
    network="Avalanche",
    subnet="Mainnet"
)

# Query with time travel
historical_transactions = await service.get_transactions(
    limit=100,
    snapshot_id=5  # Query data as of snapshot 5
)
```

## 🔍 Advanced Features

### Time Travel Queries

```sql
-- Query data as of a specific snapshot
SELECT * FROM transactions AT (VERSION => 5);

-- Query data as of a specific timestamp
SELECT * FROM transactions AT (TIMESTAMP => '2024-01-01 12:00:00+00');
```

### Change Tracking

```python
# Get recent changes
changes = await service.get_recent_changes(hours=24)

# Get table information
table_info = await service.get_table_info()

# Get all snapshots
snapshots = await service.get_snapshots()
```

### Schema Evolution

```sql
-- Add new column
ALTER TABLE transactions ADD COLUMN transaction_type VARCHAR DEFAULT 'transfer';

-- Rename column
ALTER TABLE transactions RENAME tx_hash TO transaction_hash;

-- Change column type
ALTER TABLE transactions ALTER block_number SET TYPE BIGINT;
```

### Maintenance Operations

```python
# Clean up old files
cleanup_result = await service.cleanup_old_files(dry_run=True)

# Expire old snapshots
expire_result = await service.expire_snapshots(older_than=datetime.now() - timedelta(days=30))
```

## 🧪 Testing

### Unit Tests

```bash
# Test DuckLake services
pytest tests/unit/test_ducklake_services.py -v
```

### Integration Tests

```bash
# Test complete DuckLake integration
pytest tests/integration/test_ducklake_integration.py -v
```

### Manual Testing

```bash
# Run example with sample data
go run pipeline/examples/ducklake_integration_example.go
```

## 🔧 Troubleshooting

### Common Issues

1. **SQLite Database Locked**
   - Ensure proper connection management
   - Use WAL mode for better concurrency
   - Check file permissions

2. **MinIO Connection Failed**
   - Verify MinIO is running: `curl http://localhost:9000/minio/health/live`
   - Check credentials and endpoint configuration
   - Ensure bucket exists

3. **DuckDB Extension Not Found**
   - Install required extensions: `INSTALL ducklake; LOAD ducklake;`
   - Check DuckDB version compatibility
   - Verify extension installation path

### Debug Commands

```bash
# Check MinIO buckets
docker run --rm --network ekko-ce_pipeline-network \
  -e MC_HOST_minio=http://minioadmin:minioadmin@minio:9000 \
  minio/mc ls minio/ducklake-data/

# Check SQLite catalog
sqlite3 /data/ducklake/catalog.sqlite ".tables"

# Test DuckDB connection
duckdb -c "INSTALL ducklake; LOAD ducklake; SELECT 1;"
```

## 📈 Performance Considerations

### Optimization Tips

1. **Batch Size**: Adjust `DUCKLAKE_BATCH_SIZE` based on memory and throughput requirements
2. **Flush Interval**: Balance between latency and efficiency
3. **Catalog Type**: SQLite for single-node, PostgreSQL for distributed
4. **Partitioning**: Use time-based partitioning for better query performance

### Monitoring

- Monitor SQLite catalog file size
- Track MinIO storage usage
- Monitor DuckLake snapshot growth
- Watch for failed writes and retries

## 🚀 Migration Strategy

### Phase 1: Parallel Implementation
- Run both Arrow and DuckLake writers simultaneously
- Compare data consistency and performance
- Validate DuckLake functionality

### Phase 2: API Migration
- Update API endpoints to use DuckLake service
- Implement fallback to Arrow data if needed
- Test dashboard functionality

### Phase 3: Full Migration
- Switch dashboard to DuckLake exclusively
- Deprecate Arrow writer
- Clean up legacy infrastructure

## 📚 Additional Resources

- [DuckLake Documentation](https://ducklake.select/docs/)
- [DuckDB Extensions](https://duckdb.org/docs/stable/core_extensions/)
- [MinIO Documentation](https://min.io/docs/)
- [NATS Documentation](https://docs.nats.io/)

## 🤝 Contributing

When contributing to DuckLake integration:

1. Run all tests: `./scripts/test-ducklake.sh`
2. Test with real MinIO: `./scripts/run-ducklake-example.sh`
3. Update documentation for new features
4. Follow existing code patterns and error handling
