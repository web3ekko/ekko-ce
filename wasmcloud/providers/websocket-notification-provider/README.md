# WebSocket Notification Provider

A wasmCloud provider for real-time WebSocket notifications in the Ekko Cluster platform.

## Overview

This provider enables real-time notification delivery to web dashboards, iOS, and Android applications through WebSocket connections. It integrates with the Ekko platform's Knox authentication system and receives notifications from wasmCloud actors via NATS.

## Features

- **Knox Token Authentication**: Secure authentication using existing Knox tokens stored in Redis
- **Multi-Device Support**: Users can connect from multiple devices simultaneously
- **Real-Time Notifications**: Instant delivery of blockchain alerts and notifications
- **Connection Resilience**: Automatic reconnection with exponential backoff
- **Notification Filtering**: Client-side filtering by priority, alert ID, and blockchain
- **Session Management**: Redis-backed session persistence
- **Heartbeat Mechanism**: Connection health monitoring with configurable timeouts

## Architecture

```
wasmCloud Actors
      ↓
   NATS JetStream
      ↓
WebSocket Provider ← → Redis (Knox tokens & sessions)
      ↓
WebSocket Clients (Dashboard, iOS, Android)
```

## Configuration

Configuration is passed via WADM `config` properties (lowercase keys), with environment
variable fallbacks for local runs.

| WADM Key | Env Fallback | Default | Description |
|----------|--------------|---------|-------------|
| `websocket_port` | `WEBSOCKET_PORT` | 8080 | WebSocket server port |
| `max_connections` | `MAX_CONNECTIONS` | 10000 | Maximum total connections |
| `max_connections_per_user` | `MAX_CONNECTIONS_PER_USER` | 10 | Maximum connections per user |
| `redis_url` | `REDIS_URL` | redis://localhost:6379 | Redis connection URL |
| `nats_url` | `NATS_URL` | nats://localhost:4222 | NATS connection URL |
| `heartbeat_interval_secs` | `HEARTBEAT_INTERVAL_SECS` | 30 | Heartbeat ping interval |
| `connection_timeout_secs` | `CONNECTION_TIMEOUT_SECS` | 300 | Connection timeout |

## Running Locally

### Prerequisites

- Rust 1.74+
- Redis and NATS available locally or via port-forward

### Using Cargo

```bash
# Build
cargo build --bin websocket-notification-provider

# Run the provider (env vars are optional when using WADM config)
REDIS_URL="redis://localhost:6379" \\
NATS_URL="nats://localhost:4222" \\
WEBSOCKET_PORT=8080 \\
RUST_LOG=info \\
cargo run --bin websocket-notification-provider
```

## WADM Deployment

```bash
cd apps/wasmcloud
./build-provider.sh websocket-notification-provider
MANIFEST_VERSION=v1.0.1 ./generate-manifest.sh
wash app put manifests/ekko-actors-generated.yaml
wash app deploy ekko-platform v1.0.1
```

## Testing

### Unit Tests

```bash
# Run all unit tests
cargo test

# Run with output
cargo test -- --nocapture

# Run specific test
cargo test test_authentication
```

### Integration Tests

```bash
# Enable integration tests (requires Redis and NATS)
cargo test --features integration_tests
```

### Test Coverage

The provider includes 42+ unit tests covering:
- Knox token authentication
- Multi-device connection management
- Real-time notification delivery
- Connection resilience and heartbeat
- Session management
- Notification filtering
- Redis integration
- NATS message handling
- Concurrent operations
- Exponential backoff

## WebSocket API

### Client Messages

#### Authenticate
```json
{
  "type": "Authenticate",
  "token": "knox_token_here",
  "device": "Dashboard|iOS|Android"
}
```

#### Subscribe with Filters
```json
{
  "type": "Subscribe",
  "filters": {
    "priorities": ["High", "Critical"],
    "alert_ids": ["alert_123"],
    "chains": ["ethereum", "avalanche"]
  }
}
```

#### Ping
```json
{
  "type": "Ping"
}
```

#### Get Status
```json
{
  "type": "GetStatus"
}
```

### Server Messages

#### Authenticated
```json
{
  "type": "Authenticated",
  "connection_id": "uuid",
  "user_id": "user_123",
  "device": "Dashboard"
}
```

#### Notification
```json
{
  "type": "Notification",
  "id": "notif_uuid",
  "alert_id": "alert_456",
  "alert_name": "AVAX Balance Alert",
  "priority": "High",
  "message": "Alert triggered: 15.5 exceeded 10",
  "details": {
    "current_value": "15.5",
    "threshold": "10",
    "chain": "avalanche",
    "wallet": "0x...",
    "transaction_hash": "0x...",
    "transaction_url": "https://snowtrace.io/tx/0x...",
    "block_number": 12345678
  },
  "timestamp": "2025-01-07T10:30:00Z",
  "actions": [
    {
      "label": "View Transaction",
      "url": "/alerts/alert_456/transactions"
    },
    {
      "label": "Adjust Alert",
      "url": "/alerts/alert_456/edit"
    }
  ]
}
```

#### Error
```json
{
  "type": "Error",
  "message": "Authentication failed: Invalid token"
}
```

## Redis Schema

### Knox Tokens
```
knox:tokens:{token_key} → JSON {
  user_id: string,
  token_key: string,
  expiry: datetime,
  created_at: datetime
}
```

### WebSocket Sessions
```
websocket:sessions:{user_id} → SET of connection_ids
```

### Connection Metadata
```
websocket:connections:{connection_id} → JSON {
  user_id: string,
  connection_id: string,
  device: "Dashboard|iOS|Android",
  connected_at: datetime,
  last_ping: datetime,
  ip_address: string,
  user_agent: string,
  filters: { priorities, alert_ids, chains }
}
```

### Metrics
```
websocket:metrics:{date}:{hour} → JSON {
  total_connections: number,
  messages_sent: number,
  avg_latency_ms: number,
  timestamp: datetime
}
```

### Missed Messages Queue
```
websocket:queue:{user_id} → LIST of messages (max 100, TTL configurable)
```

## NATS Integration

The provider subscribes to `notifications.websocket` subject and expects messages in this format:

```json
{
  "user_id": "user_123",
  "alert_id": "alert_456",
  "alert_name": "AVAX Balance Alert",
  "notification_type": "alert_triggered",
  "priority": "High|Medium|Low|Critical",
  "payload": {
    "triggered_value": "15.5",
    "threshold": "10",
    "transaction_hash": "0x...",
    "chain": "avalanche",
    "wallet": "0x...",
    "block_number": 12345678
  },
  "timestamp": "2025-01-07T10:30:00Z"
}
```

## Deployment

### wasmCloud Deployment

```bash
# Build the provider
wash build

# Push to registry
wash push registry.wasmcloud.com/v2/websocket-notification-provider:0.1.0

# Deploy with wash
wash start provider registry.wasmcloud.com/v2/websocket-notification-provider:0.1.0
```

### Kubernetes Deployment

See `/deployments/kubernetes/websocket-provider.yaml` for Kubernetes manifests.

## Monitoring

The provider exposes metrics through Redis and includes health checks at `/health`.

### Key Metrics
- Total active connections
- Messages sent per hour
- Average message latency
- Connection success/failure rates
- Authentication attempts

## Security Considerations

1. **Token Security**: Knox tokens are never logged or exposed
2. **Connection Limits**: Per-user and global connection limits prevent abuse
3. **Input Validation**: All client messages are validated before processing
4. **Rate Limiting**: Built-in protection against message flooding
5. **TLS Support**: WebSocket connections should use WSS in production

## Troubleshooting

### Common Issues

**Authentication Failures**
- Verify Knox token exists in Redis
- Check token expiry
- Ensure correct token format (8+ characters)

**Connection Drops**
- Check heartbeat configuration
- Verify network stability
- Review connection timeout settings

**Missing Notifications**
- Check NATS subscription status
- Verify notification filters
- Review Redis queue for missed messages

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for development guidelines.

## License

Copyright (c) 2025 Ekko Platform
