# Configuration Guide

## Environment Variables

### Core Configuration
- `REDIS_URL`: Redis connection URL (default: `redis://redis:6379`)
- `MINIO_ACCESS_KEY`: MinIO access key
- `MINIO_SECRET_KEY`: MinIO secret key
- `MINIO_BUCKET`: MinIO bucket name (default: `ekko`)
- `MINIO_URL`: MinIO server URL (default: `http://minio:9000`)

### Blockchain API Keys
- `SNOWTRACE_API_KEY`: API key for Avalanche C-Chain (required for transaction details)
- `AVALANCHE_NODE_URL`: Avalanche node URL for P-Chain interactions

## Bento Configuration

The Bento service is configured using `bento/config.yaml`:

```yaml
input:
  websocket:
    url: ${AVAX_WEBSOCKET_URL}
    open_message: '{
      "jsonrpc":"2.0",
      "method":"eth_subscribe",
      "params":["newPendingTransactions"],
      "id":1
    }'

pipeline:
  processors:
    - mapping:
        # Transaction data mapping
    - http:
        # Blockchain API integration
    - python:
        # Alert processing
    - log:
        # Logging configuration

output:
  broker:
    pattern: fan_out
    outputs:
      - redis_list:
          # Redis output configuration
      - aws_s3:
          # MinIO storage configuration
```

## Alert Configuration

Alerts are stored in Redis with the following structure:

```
Key: alert:{blockchain_symbol}:{wallet_id}
Value: Hash containing alert conditions and settings
```

### Alert Types
1. Transaction Value
2. Gas Price
3. Contract Interaction
4. Token Transfer
5. Custom Conditions

## Notification Configuration

Notifications are streamed to Redis with two types of streams:
1. Per-wallet stream: `notifications:{blockchain_symbol}:{wallet_id}`
2. Global stream: `notifications:all`

## Storage Configuration

### Redis
- Used for:
  - Alert rules
  - Real-time notifications
  - Transaction caching
  - Temporary data storage

### MinIO
- Used for:
  - Historical transaction data
  - Long-term storage
  - Data backup

### DuckDB
- Used for:
  - Wallet management
  - Alert configuration storage
  - Agent settings
  - System configuration
