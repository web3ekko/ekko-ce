# Notification System Redis Cache Schema

**Version:** 1.0.0
**Last Updated:** 2025-10-24

## Overview

This document defines the Redis cache schema for the multi-address notification system. Django manages cache population and updates. wasmCloud actors access cache via Redis capability provider for read-only operations.

**Architecture Principle:** Django = Metadata Management | wasmCloud = Message Routing & Delivery

## Cache Access Pattern

```
┌─────────────┐         ┌──────────┐         ┌────────────────────┐
│   Django    │ ──SET──>│  Redis   │<──GET── │ wasmCloud Actors   │
│   (Write)   │         │  Cache   │         │  (Read-Only via    │
│             │         │          │         │   Capability       │
│             │         │          │         │   Provider)        │
└─────────────┘         └──────────┘         └────────────────────┘
```

**IMPORTANT:** wasmCloud actors MUST use Redis capability provider. Never use direct Redis connections.

## Cache Keys and TTL

All cache entries have a **1-hour TTL (3600 seconds)**.

| Cache Type | Key Pattern | TTL |
|------------|-------------|-----|
| User Endpoints | `user:notification:endpoints:{user_id}` | 3600s |
| Team Endpoints | `team:notification:endpoints:{team_id}` | 3600s |
| Member Override | `team:notification:override:{team_id}:{user_id}` | 3600s |
| Team Members (Bulk) | `team:notification:members:{team_id}` | 3600s |

## Data Structures

### 1. User Notification Endpoints

**Cache Key:** `user:notification:endpoints:{user_id}`

**Purpose:** Retrieve all notification endpoints configured by a user for personal alerts.

**Structure:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "endpoints": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "channel_type": "email",
      "label": "Personal Gmail",
      "config": {
        "address": "user@gmail.com"
      },
      "enabled": true,
      "verified": true,
      "routing_mode": "all_enabled",
      "priority_filters": []
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440002",
      "channel_type": "telegram",
      "label": "Trading Alerts",
      "config": {
        "chat_id": "123456789"
      },
      "enabled": true,
      "verified": true,
      "routing_mode": "priority_based",
      "priority_filters": ["critical", "high"]
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440003",
      "channel_type": "webhook",
      "label": "Monitoring System",
      "config": {
        "url": "https://monitor.example.com/webhook/alerts"
      },
      "enabled": true,
      "verified": true,
      "routing_mode": "all_enabled",
      "priority_filters": []
    }
  ],
  "cached_at": "2025-10-24T10:30:00.000Z"
}
```

**Field Descriptions:**

- `user_id` (string): UUID of the user
- `endpoints` (array): List of notification endpoints
  - `id` (string): UUID of the endpoint
  - `channel_type` (string): One of: `email`, `telegram`, `slack`, `webhook`, `sms`
  - `label` (string): User-defined label (max 100 chars)
  - `config` (object): Channel-specific configuration
    - Email: `{ "address": "email@example.com" }`
    - Telegram: `{ "chat_id": "123456789" }`
    - Slack: `{ "webhook_url": "https://hooks.slack.com/..." }`
    - Webhook: `{ "url": "https://..." }`
    - SMS: `{ "phone_number": "+1234567890" }`
  - `enabled` (boolean): Whether endpoint is currently active
  - `verified` (boolean): Whether endpoint has been verified
  - `routing_mode` (string): `all_enabled` or `priority_based`
  - `priority_filters` (array): Priority levels to receive (only used when `routing_mode` is `priority_based`)
- `cached_at` (string): ISO 8601 timestamp of cache creation

**Routing Logic:**

```rust
// Example routing logic for user alerts
if endpoint.enabled && endpoint.verified {
    if endpoint.routing_mode == "all_enabled" {
        // Send to this endpoint regardless of priority
        send_notification(endpoint, alert);
    } else if endpoint.routing_mode == "priority_based" {
        // Only send if alert priority matches filters
        if endpoint.priority_filters.contains(&alert.priority) {
            send_notification(endpoint, alert);
        }
    }
}
```

### 2. Team Notification Endpoints

**Cache Key:** `team:notification:endpoints:{team_id}`

**Purpose:** Retrieve all notification endpoints configured for a team. Team alerts route ONLY to team endpoints (not individual member endpoints).

**Structure:**
```json
{
  "team_id": "770e8400-e29b-41d4-a716-446655440000",
  "endpoints": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440001",
      "channel_type": "slack",
      "label": "Team Channel",
      "config": {
        "webhook_url": "https://hooks.slack.com/services/..."
      },
      "enabled": true,
      "verified": true,
      "routing_mode": "all_enabled",
      "priority_filters": []
    },
    {
      "id": "880e8400-e29b-41d4-a716-446655440002",
      "channel_type": "webhook",
      "label": "Ops Dashboard",
      "config": {
        "url": "https://ops.example.com/webhook/team-alerts"
      },
      "enabled": true,
      "verified": true,
      "routing_mode": "priority_based",
      "priority_filters": ["critical"]
    }
  ],
  "cached_at": "2025-10-24T10:30:00.000Z"
}
```

**Field Descriptions:** Same as user endpoints, but `owner_type` is implicitly `team`.

**Routing Logic:**

```rust
// Team alerts route ONLY to team endpoints
// NOT to individual member personal endpoints
for endpoint in team_endpoints.endpoints {
    if endpoint.enabled && endpoint.verified {
        // Check member overrides before sending
        if !is_endpoint_disabled_by_member(team_id, member_id, endpoint.id) {
            if endpoint.routing_mode == "all_enabled" {
                send_notification(endpoint, alert);
            } else if endpoint.routing_mode == "priority_based" {
                if endpoint.priority_filters.contains(&alert.priority) {
                    send_notification(endpoint, alert);
                }
            }
        }
    }
}
```

### 3. Team Member Notification Override

**Cache Key:** `team:notification:override:{team_id}:{user_id}`

**Purpose:** Retrieve individual member's notification preferences for team alerts. Members can opt out of specific team endpoints or priority levels.

**Structure:**
```json
{
  "team_id": "770e8400-e29b-41d4-a716-446655440000",
  "member_id": "550e8400-e29b-41d4-a716-446655440000",
  "team_notifications_enabled": true,
  "disabled_endpoints": [
    "880e8400-e29b-41d4-a716-446655440002"
  ],
  "disabled_priorities": [
    "low",
    "normal"
  ],
  "updated_at": "2025-10-24T10:25:00.000Z"
}
```

**Field Descriptions:**

- `team_id` (string): UUID of the team
- `member_id` (string): UUID of the team member
- `team_notifications_enabled` (boolean): Master switch - if `false`, member receives NO team notifications
- `disabled_endpoints` (array): List of endpoint UUIDs the member has disabled
- `disabled_priorities` (array): Priority levels the member has disabled (one of: `critical`, `high`, `normal`, `low`)
- `updated_at` (string): ISO 8601 timestamp of last update

**Cache Miss Behavior:**

If cache key doesn't exist, assume defaults:
```json
{
  "team_notifications_enabled": true,
  "disabled_endpoints": [],
  "disabled_priorities": []
}
```

**Routing Logic:**

```rust
// Check member override before sending team notification
fn should_send_to_member(team_id: &str, member_id: &str, endpoint_id: &str, priority: &str) -> bool {
    let override = get_member_override(team_id, member_id);

    // Master switch check
    if !override.team_notifications_enabled {
        return false;
    }

    // Endpoint-specific disable check
    if override.disabled_endpoints.contains(&endpoint_id) {
        return false;
    }

    // Priority-level disable check
    if override.disabled_priorities.contains(&priority) {
        return false;
    }

    true
}
```

### 4. Team Members (Bulk Override Cache)

**Cache Key:** `team:notification:members:{team_id}`

**Purpose:** Efficiently retrieve ALL member overrides for a team in a single cache lookup. Useful when routing team alerts to avoid N+1 cache queries.

**Structure:**
```json
{
  "team_id": "770e8400-e29b-41d4-a716-446655440000",
  "members": {
    "550e8400-e29b-41d4-a716-446655440000": {
      "team_notifications_enabled": true,
      "disabled_endpoints": [],
      "disabled_priorities": ["low"]
    },
    "550e8400-e29b-41d4-a716-446655440001": {
      "team_notifications_enabled": false,
      "disabled_endpoints": [],
      "disabled_priorities": []
    },
    "550e8400-e29b-41d4-a716-446655440002": {
      "team_notifications_enabled": true,
      "disabled_endpoints": ["880e8400-e29b-41d4-a716-446655440002"],
      "disabled_priorities": []
    }
  },
  "cached_at": "2025-10-24T10:30:00.000Z"
}
```

**Field Descriptions:**

- `team_id` (string): UUID of the team
- `members` (object): Map of member_id to override settings
  - Key: member UUID
  - Value: Member override settings (same as individual override)
- `cached_at` (string): ISO 8601 timestamp of cache creation

**Usage Example:**

```rust
// Efficient team alert routing with bulk cache
let team_members = get_team_members_cache(team_id);
let team_endpoints = get_team_endpoints_cache(team_id);

for member_id in team.members {
    let member_override = team_members.members.get(member_id).unwrap_or_default();

    if !member_override.team_notifications_enabled {
        continue; // Skip this member entirely
    }

    for endpoint in team_endpoints.endpoints {
        if should_send_to_member_with_override(endpoint, member_override, alert) {
            send_notification(endpoint, alert, member_id);
        }
    }
}
```

## Cache Warming Strategy

### Automatic Warming

Django automatically warms cache via signal handlers on:

1. **Endpoint Creation:** When `NotificationChannelEndpoint` is created
2. **Endpoint Update:** When `NotificationChannelEndpoint` is updated
3. **Override Creation:** When `TeamMemberNotificationOverride` is created
4. **Override Update:** When `TeamMemberNotificationOverride` is updated

### Manual Warming

API endpoints for manual cache warming (useful for initial setup or cache rebuilds):

- `POST /api/notification-endpoints/warm_cache/` - Warm user endpoint cache
- `POST /api/team-notification-endpoints/warm_cache/` - Warm team endpoint cache (admin only)
- `POST /api/team-notification-overrides/{team_id}/warm_members_cache/` - Warm team members bulk cache

## Cache Invalidation

Cache is automatically invalidated on:

1. **Endpoint Deletion:** User or team endpoint is deleted
2. **Override Deletion:** Member override is deleted
3. **Explicit Invalidation:** Via API endpoints

Cache invalidation is immediate. Next access will result in cache miss and require Django to populate cache again.

## Error Handling

### Cache Miss Behavior

When wasmCloud actors encounter cache miss:

1. **User Endpoints:** Assume no endpoints configured, skip user notification
2. **Team Endpoints:** Assume no endpoints configured, skip team notification
3. **Member Override:** Assume defaults (all enabled, no disabled endpoints/priorities)
4. **Team Members Bulk:** Assume all members enabled, no overrides

### Stale Cache Handling

Cache has 1-hour TTL. If cache is stale (older than 1 hour), Redis will automatically evict it.

wasmCloud actors should:
- Always check `cached_at` timestamp
- Consider cache older than 1 hour as potentially stale
- Log cache misses for monitoring

## Implementation Checklist for wasmCloud Actors

### notification-router Actor Updates

- [ ] Add Redis capability provider to actor manifest
- [ ] Implement cache key generation functions
- [ ] Implement cache retrieval with error handling
- [ ] Update routing logic to check user endpoint cache
- [ ] Update routing logic to check team endpoint cache
- [ ] Update routing logic to check member override cache
- [ ] Add cache miss logging for monitoring
- [ ] Test with various cache scenarios (hit, miss, stale)

### Sample Code Structure

```rust
// Example wasmCloud actor structure
use wasmcloud_provider_redis::*;

struct NotificationRouter {
    redis: RedisProvider,
}

impl NotificationRouter {
    async fn route_user_alert(&self, user_id: &str, alert: &Alert) {
        // Get user endpoints from cache
        let cache_key = format!("user:notification:endpoints:{}", user_id);
        let endpoints = match self.redis.get(&cache_key).await {
            Ok(data) => serde_json::from_str(&data)?,
            Err(_) => {
                warn!("Cache miss for user {}", user_id);
                return; // No endpoints configured
            }
        };

        // Route to enabled and verified endpoints
        for endpoint in endpoints.endpoints {
            if self.should_send(&endpoint, alert) {
                self.send_notification(&endpoint, alert).await;
            }
        }
    }

    async fn route_team_alert(&self, team_id: &str, alert: &Alert) {
        // Get team endpoints from cache
        let team_endpoints = self.get_team_endpoints_cache(team_id).await?;

        // Get all member overrides (bulk)
        let member_overrides = self.get_team_members_cache(team_id).await?;

        // Route to each team member respecting their overrides
        for member_id in team.members {
            let override = member_overrides.members.get(member_id).unwrap_or_default();

            if !override.team_notifications_enabled {
                continue;
            }

            for endpoint in &team_endpoints.endpoints {
                if self.should_send_to_member(&endpoint, &override, alert) {
                    self.send_notification(endpoint, alert).await;
                }
            }
        }
    }
}
```

## Monitoring and Observability

### Key Metrics to Track

1. **Cache Hit Rate:** Percentage of cache hits vs. misses
2. **Cache Age:** Distribution of cache age at access time
3. **Routing Decisions:** Count of notifications sent/skipped per endpoint type
4. **Override Usage:** Percentage of team members with active overrides

### Recommended Logging

```rust
// Log cache access patterns
info!("Cache hit: {} (age: {}s)", cache_key, cache_age);
warn!("Cache miss: {} (user: {})", cache_key, user_id);

// Log routing decisions
info!("Notification sent: endpoint={}, channel={}, user={}", endpoint_id, channel_type, user_id);
debug!("Notification skipped: endpoint={}, reason={}", endpoint_id, reason);

// Log override application
debug!("Member override applied: team={}, member={}, disabled_endpoints={}", team_id, member_id, disabled_count);
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-10-24 | Initial cache schema for multi-address notification system |

## Support

For questions or issues with cache schema:
1. Check Django API logs for cache population errors
2. Verify Redis connectivity via capability provider
3. Check signal handlers are loaded (Django startup logs)
4. Review cache warming API endpoints for manual refresh

---

**Architecture Reminder:** Django manages cache. wasmCloud reads cache via Redis capability provider. Never bypass this pattern.
