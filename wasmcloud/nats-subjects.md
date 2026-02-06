# NATS Subject Patterns for Ekko Notification System

This document defines the NATS subject patterns used in the Ekko notification system.

## Subject Naming Convention

AlertTemplate v1 runtime uses the following canonical subjects:
```
notifications.send.immediate.{channel}
notifications.send.digest.{channel}
ws.events
```

## Channel-Specific Subjects

### Email Notifications
- `notifications.email.send` - Send email notification
- `notifications.email.bulk` - Bulk email notifications
- `notifications.email.template` - Template-based emails

### Slack Notifications
- `notifications.slack.send` - Send Slack message
- `notifications.slack.webhook` - Webhook-based Slack notifications
- `notifications.slack.channel` - Channel-specific notifications

### SMS Notifications
- `notifications.sms.send` - Send SMS message
- `notifications.sms.bulk` - Bulk SMS notifications

### Telegram Notifications
- `notifications.send.immediate.telegram` - Send Telegram notification (immediate)

### Discord Notifications
- `notifications.discord.send` - Send Discord message
- `notifications.discord.webhook` - Webhook-based Discord notifications

### Webhook Notifications
- `notifications.send.immediate.webhook` - Send webhook notification (immediate)

### WebSocket Notifications
- `notifications.send.immediate.websocket` - Send WebSocket notification (immediate)
- `ws.events` - Generic websocket events (e.g. NLP progress)

## Status and Control Subjects

### Delivery Status Tracking
- `notifications.status.delivered.{channel}` - Successful delivery confirmation
- `notifications.status.failed.{channel}` - Delivery failure notification  
- `notifications.status.pending.{channel}` - Pending delivery status
- `notifications.status.retry.{channel}` - Retry attempt notification

### Dead Letter Queue
- `notifications.dlq.{channel}` - Failed messages that exceeded retry limits
- `notifications.dlq.poison` - Messages that caused system errors

### Metrics and Monitoring
- `notifications.metrics.delivery` - Delivery metrics
- `notifications.metrics.performance` - Performance metrics
- `notifications.metrics.errors` - Error metrics
- `notifications.metrics.provider.{provider_name}` - Provider-specific metrics

## Control and Management Subjects

### Provider Control
- `notifications.control.{channel}.start` - Start provider
- `notifications.control.{channel}.stop` - Stop provider
- `notifications.control.{channel}.restart` - Restart provider
- `notifications.control.{channel}.health` - Health check request

### Cache Management
- `notifications.cache.invalidate.user.{user_id}` - Invalidate user cache
- `notifications.cache.warm.{type}` - Warm cache request
- `notifications.cache.stats` - Cache statistics request

### Testing and Debug
- `notifications.test.{channel}` - Test notification delivery
- `notifications.debug.{channel}` - Debug information
- `notifications.health.{channel}` - Health check responses

## Message Payload Formats

### Standard Notification Request
```json
{
  "context": {
    "request_id": "req_123456",
    "user_id": "user_789",
    "alert_id": "alert_456",
    "priority": "high",
    "timestamp": "2024-01-01T12:00:00Z"
  },
  "notification": {
    "subject": "Alert Triggered",
    "message": "Your blockchain alert has been triggered",
    "template": "alert_notification",
    "variables": {
      "alert_name": "High Gas Price",
      "threshold": "50 gwei",
      "current_value": "75 gwei"
    }
  },
  "delivery": {
    "channel_config": {
      "email": "user@example.com",
      "webhook_url": "https://api.example.com/webhook"
    },
    "retry_policy": {
      "max_retries": 3,
      "backoff_ms": [1000, 5000, 15000]
    }
  }
}
```

### Delivery Status Response
```json
{
  "status": "delivered|failed|pending",
  "request_id": "req_123456",
  "channel": "email",
  "timestamp": "2024-01-01T12:00:05Z",
  "message_id": "msg_external_123",
  "provider_response": {
    "code": 200,
    "message": "OK",
    "external_id": "sendgrid_12345"
  },
  "error": {
    "code": "RATE_LIMITED",
    "message": "API rate limit exceeded",
    "retryable": true,
    "retry_after": "2024-01-01T12:05:00Z"
  }
}
```

## Stream Configuration

### Notification Streams
Each channel has its own stream for better isolation and scaling:
- `notifications-email` → `notifications.email.>`
- `notifications-slack` → `notifications.slack.>`
- `notifications-sms` → `notifications.sms.>`
- `notifications-telegram` → `notifications.send.immediate.telegram`
- `notifications-discord` → `notifications.discord.>`
- `notifications-webhook` → `notifications.send.immediate.webhook`
- `notifications-websocket` → `notifications.send.immediate.websocket`

### Control Streams
- `notification-status` → `notifications.status.>`
- `notification-dlq` → `notifications.dlq.>`
- `notification-metrics` → `notifications.metrics.>`

## Best Practices

1. **Use specific subjects**: Avoid wildcards in publishing, use them only for subscribing
2. **Include context**: Add user_id, request_id for tracing
3. **Hierarchical organization**: Use dots to create logical hierarchies
4. **Consistent naming**: Follow the established patterns
5. **Avoid deep nesting**: Keep subject levels reasonable (3-5 levels max)
6. **Document changes**: Update this file when adding new subjects
