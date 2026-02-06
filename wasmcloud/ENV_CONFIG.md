# Environment Configuration Guide

This document describes the environment variables used by the Ekko Cluster wasmCloud application.

## Quick Start

1. **Copy the environment file**:
   ```bash
   cp .env.example .env
   # or use the provided .env file
   ```

2. **Start the development environment**:
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

3. **Deploy the wasmCloud application**:
   ```bash
   wash app deploy manifests/dev.yaml
   ```

## Environment Variables

### S3/MinIO Configuration

These variables configure the S3-compatible storage (MinIO for local development):

| Variable | Default | Description |
|----------|---------|-------------|
| `S3_ENDPOINT` | `http://localhost:9000` | S3/MinIO endpoint URL |
| `S3_REGION` | `us-east-1` | S3 region |
| `S3_BUCKET` | `ekko-ducklake` | S3 bucket name |
| `S3_ACCESS_KEY_ID` | `minioadmin` | S3 access key ID |
| `S3_SECRET_ACCESS_KEY` | `minioadmin` | S3 secret access key |

### DuckLake Provider Configuration

These variables configure the DuckLake capability provider (DuckDB-based lakehouse):

| Variable | Default | Description |
|----------|---------|-------------|
| `DUCKLAKE_S3_ENDPOINT` | `http://localhost:9000` | S3 endpoint for DuckLake |
| `DUCKLAKE_S3_REGION` | `us-east-1` | S3 region for DuckLake |
| `DUCKLAKE_S3_BUCKET` | `ekko-ducklake` | S3 bucket for DuckLake |
| `DUCKLAKE_S3_ACCESS_KEY_ID` | `minioadmin` | S3 access key for DuckLake |
| `DUCKLAKE_S3_SECRET_ACCESS_KEY` | `minioadmin` | S3 secret key for DuckLake |
| `DUCKLAKE_WAREHOUSE_PATH` | `/ekko/ducklake` | Warehouse root path |
| `DUCKLAKE_MAX_CONNECTIONS` | `4` | Maximum concurrent connections |
| `DUCKLAKE_MEMORY_LIMIT_MB` | `512` | Memory limit in MB |
| `DUCKLAKE_THREADS` | `4` | Number of threads |
| `DUCKLAKE_TEMP_DIR` | `/tmp/ducklake` | Temporary directory path |
| `DUCKLAKE_ENABLE_OPTIMIZATION` | `true` | Enable automatic optimization |
| `DUCKLAKE_MAX_BATCH_SIZE` | `10000` | Maximum batch size for writes |
| `DUCKLAKE_ENABLE_METRICS` | `false` | Enable metrics collection |

### wasmCloud Configuration

These variables configure the wasmCloud runtime:

| Variable | Default | Description |
|----------|---------|-------------|
| `WASMCLOUD_LATTICE` | `ekko-dev` | wasmCloud lattice name |
| `WASMCLOUD_RPC_HOST` | `0.0.0.0` | RPC host address |
| `WASMCLOUD_RPC_PORT` | `4000` | RPC port |
| `WASMCLOUD_CTL_HOST` | `0.0.0.0` | Control interface host |
| `WASMCLOUD_CTL_PORT` | `4001` | Control interface port |
| `WASMCLOUD_NATS_HOST` | `localhost` | NATS host |
| `WASMCLOUD_NATS_PORT` | `4222` | NATS port |
| `WASMCLOUD_LOG_LEVEL` | `debug` | Log level |

### NATS Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `NATS_CLIENT_NAME` | `ekko-dev` | NATS client name |

### Redis Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis server URL |
| `REDIS_PASSWORD` | _(empty)_ | Redis password |

## Environment-Specific Configuration

### Development (.env)

The `.env` file contains development defaults suitable for local development with Docker Compose.

### Production

For production deployments, override these variables:

```bash
# Production S3 Configuration
S3_ENDPOINT=https://s3.amazonaws.com
S3_BUCKET=ekko-ducklake-prod
S3_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
S3_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}

# Production NATS Configuration
NATS_URL=${NATS_CLUSTER_URL}
NATS_TLS_REQUIRED=true

# Production wasmCloud Configuration
WASMCLOUD_LATTICE=ekko-prod
WASMCLOUD_LOG_LEVEL=info

# Production DuckLake Configuration
DUCKLAKE_MAX_CONNECTIONS=8
DUCKLAKE_MEMORY_LIMIT_MB=2048
DUCKLAKE_THREADS=8
DUCKLAKE_ENABLE_OPTIMIZATION=true
DUCKLAKE_MAX_BATCH_SIZE=50000
DUCKLAKE_ENABLE_METRICS=true
```

## Data Flow and Environment Variables

### Transaction Processing Pipeline

1. **Newheads Provider** → Publishes to NATS subjects
2. **Raw Transaction Actors** → Subscribe to newheads, publish processed transactions
3. **DuckLake Writer Actor** → Subscribes to processed transactions
4. **DuckLake Provider** → Writes to S3/MinIO using environment credentials

### Environment Variable Flow

```
Docker Compose (.env)
    ↓
wasmCloud Container (environment variables)
    ↓
DuckLake Provider (DUCKLAKE_* variables)
    ↓
S3/MinIO Storage (Parquet files)
```

## Troubleshooting

### Common Issues

1. **S3 Connection Errors**:
   - Check `DUCKLAKE_S3_ENDPOINT` is accessible
   - Verify `DUCKLAKE_S3_ACCESS_KEY_ID` and `DUCKLAKE_S3_SECRET_ACCESS_KEY`
   - Ensure bucket exists and has proper permissions

2. **NATS Connection Errors**:
   - Verify `NATS_URL` is correct
   - Check NATS server is running and accessible

3. **wasmCloud Startup Issues**:
   - Check `WASMCLOUD_NATS_HOST` and `WASMCLOUD_NATS_PORT`
   - Verify lattice name is unique

### Validation Commands

```bash
# Test MinIO connection
mc alias set local http://localhost:9000 minioadmin minioadmin
mc ls local/

# Test NATS connection
nats pub test.subject "hello world"

# Check wasmCloud status
wash ctl get hosts

# Test DuckLake provider
wash call <provider-id> ekko:ducklake/ducklake.list-tables
```

## Security Notes

- **Never commit `.env` files** with production credentials
- Use **environment-specific** credential management (AWS IAM, Kubernetes secrets, etc.)
- **Rotate credentials** regularly
- Use **least privilege** access for S3 buckets
- Enable **TLS** for production NATS connections

## Example .env File

See the provided `.env` file in the repository root for a complete example with all variables and their default values.
