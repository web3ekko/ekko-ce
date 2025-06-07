# 🔄 JetStream to DuckDB Migration

This document describes the migration from JetStream-only storage to DuckDB with JetStream synchronization.

## 📋 Overview

**Before:** Models stored exclusively in NATS JetStream KV stores  
**After:** Models stored in DuckDB as primary storage, with JetStream KV sync on create/update operations

## 🏗️ Architecture Changes

### New Components

- **DuckDB Database**: Primary storage for all models
- **Repository Pattern**: Data access layer with automatic JetStream sync
- **Migration System**: Tools to migrate existing JetStream data
- **Connection Management**: Thread-safe DuckDB connection pooling

### Database Schema

The following tables are created in DuckDB:

- `users` - User accounts with authentication
- `wallets` - Blockchain wallet information
- `alerts` - Alert configurations and status
- `wallet_balances` - Historical balance data
- `alert_rules` - Alert rule definitions
- `workflows` - Workflow configurations
- `agents` - Agent configurations

## 🚀 Getting Started

### 1. Environment Variables

Add these environment variables to your `.env` file:

```bash
# Database configuration
DUCKDB_PATH=/app/data/ekko.db
DUCKDB_POOL_SIZE=10

# Migration settings
MIGRATION_MODE=false
ENABLE_JETSTREAM_SYNC=true
```

### 2. Docker Setup

The Docker Compose configuration has been updated to include:

- Volume mount for DuckDB persistence: `api_data:/app/data`
- Environment variables for database configuration
- Health checks that include database status

### 3. Automatic Migration

When `MIGRATION_MODE=true`, the system will automatically:

1. Initialize DuckDB schema
2. Check for existing JetStream data
3. Migrate data from JetStream KV stores to DuckDB
4. Create backups before migration
5. Validate data integrity

## 🔧 Manual Migration

### Check Migration Status

```bash
# Check current database status
docker-compose exec api python scripts/run_migration.py --check-only

# Verbose output
docker-compose exec api python scripts/run_migration.py --check-only --verbose
```

### Run Migration

```bash
# Run migration with backup
docker-compose exec api python scripts/run_migration.py

# Run migration without backup
docker-compose exec api python scripts/run_migration.py --no-backup

# Force migration (overwrite existing data)
docker-compose exec api python scripts/run_migration.py --force
```

### Test Database System

```bash
# Run comprehensive tests
docker-compose exec api python scripts/test_migration.py
```

## 📊 API Changes

### New Endpoints

- `GET /database/health` - Database system health status

### Repository Integration

The API now uses repository classes instead of direct JetStream access:

```python
# Before (JetStream only)
kv = await js.key_value(bucket="wallets")
data = await kv.get(wallet_id)
wallet = json.loads(data.value.decode('utf-8'))

# After (DuckDB + JetStream sync)
wallet_repo = WalletRepository()
wallet = await wallet_repo.get_by_id(wallet_id)
```

## 🔄 Synchronization Strategy

### Write Operations

1. **Primary**: Write to DuckDB first
2. **Secondary**: Sync to JetStream KV (async, non-blocking)
3. **Events**: Publish to JetStream streams for real-time updates
4. **Error Handling**: Log sync failures, don't block primary operations

### Read Operations

1. **Primary**: Read from DuckDB (faster, supports complex queries)
2. **Fallback**: JetStream KV remains available during transition

### Consistency

- **Eventually Consistent**: JetStream KV updated asynchronously
- **Source of Truth**: DuckDB is the authoritative data source
- **Conflict Resolution**: DuckDB data takes precedence

## 📈 Performance Benefits

### Query Performance

- **Complex Filtering**: Native SQL WHERE clauses
- **Joins**: Relational queries across entities
- **Aggregations**: SQL GROUP BY and aggregate functions
- **Indexing**: Database indexes for faster lookups

### Scalability

- **Connection Pooling**: Efficient resource management
- **Concurrent Access**: Database-level locking and transactions
- **Analytics**: SQL-based reporting capabilities

## 🛠️ Development

### Repository Pattern

All data access goes through repository classes:

```python
from app.repositories import UserRepository, WalletRepository

# Dependency injection in FastAPI
async def get_wallet(
    wallet_id: str,
    wallet_repo: WalletRepository = Depends(get_wallet_repository)
):
    return await wallet_repo.get_by_id(wallet_id)
```

### Adding New Models

1. Add table schema to `app/database/models.py`
2. Create repository class in `app/repositories/`
3. Add migration logic if needed
4. Update API endpoints to use repository

### Testing

```python
# Unit tests for repositories
pytest api/tests/test_repositories.py

# Integration tests
pytest api/tests/test_migration.py

# Manual testing
python api/scripts/test_migration.py
```

## 🔍 Monitoring

### Health Checks

```bash
# Check database health
curl http://localhost:8000/database/health

# Check overall API health
curl http://localhost:8000/api/health
```

### Logs

Monitor logs for:

- Database connection issues
- Migration progress
- JetStream sync failures
- Data integrity warnings

### Metrics

The system tracks:

- Database connection pool usage
- Query performance
- Sync success/failure rates
- Data integrity status

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Failures**
   - Check `DUCKDB_PATH` environment variable
   - Ensure data directory exists and is writable
   - Verify DuckDB dependency is installed

2. **Migration Failures**
   - Check NATS connectivity
   - Verify JetStream KV buckets exist
   - Review migration logs for specific errors

3. **Sync Issues**
   - JetStream sync failures are logged but don't block operations
   - Check NATS connection status
   - Verify JetStream bucket permissions

### Recovery

```bash
# Reset database (CAUTION: destroys all data)
docker-compose exec api python -c "
from app.database.migrations import MigrationManager
MigrationManager().reset_database()
"

# Restore from backup
docker-compose exec api python scripts/run_migration.py --restore-backup /path/to/backup
```

## 📚 Additional Resources

- [DuckDB Documentation](https://duckdb.org/docs/)
- [NATS JetStream Guide](https://docs.nats.io/jetstream)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)

## 🤝 Contributing

When contributing to the migration system:

1. Follow the repository pattern for data access
2. Add appropriate tests for new functionality
3. Update migration scripts for schema changes
4. Document any new environment variables
5. Test both DuckDB and JetStream sync functionality
