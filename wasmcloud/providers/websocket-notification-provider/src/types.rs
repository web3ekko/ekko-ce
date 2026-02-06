use chrono::{DateTime, NaiveTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Device types that can connect
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "lowercase")]
pub enum DeviceType {
    Dashboard,
    iOS,
    Android,
}

impl std::fmt::Display for DeviceType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DeviceType::Dashboard => write!(f, "Dashboard"),
            DeviceType::iOS => write!(f, "iOS"),
            DeviceType::Android => write!(f, "Android"),
        }
    }
}

/// WebSocket message types from client
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ClientMessage {
    Authenticate { token: String, device: DeviceType },
    Subscribe { filters: NotificationFilters },
    Ping,
    GetStatus,
}

/// WebSocket message types to client
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ServerMessage {
    Authenticated {
        connection_id: String,
        user_id: String,
        device: DeviceType,
    },
    Subscribed {
        filters: NotificationFilters,
    },
    Notification {
        id: String,
        alert_id: String,
        alert_name: String,
        priority: NotificationPriority,
        message: String,
        details: HashMap<String, serde_json::Value>,
        timestamp: DateTime<Utc>,
        actions: Vec<NotificationAction>,
    },
    /// Generic event from ws.events NATS subject (Phase 1: NLP progress, etc.)
    Event {
        event_type: String,
        job_id: Option<String>,
        payload: serde_json::Value,
        timestamp: DateTime<Utc>,
    },
    Pong {
        timestamp: DateTime<Utc>,
    },
    Status {
        connected: bool,
        authenticated: bool,
        connection_id: String,
        user_id: String,
        device: DeviceType,
        connected_at: DateTime<Utc>,
        filters: NotificationFilters,
    },
    Error {
        message: String,
    },
}

/// Notification priority levels
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum NotificationPriority {
    Critical,
    High,
    Normal,
    Low,
}

/// Notification action for client
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationAction {
    pub label: String,
    pub url: String,
}

/// Notification filters
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct NotificationFilters {
    pub priorities: Option<Vec<NotificationPriority>>,
    pub alert_ids: Option<Vec<String>>,
    pub chains: Option<Vec<String>>,
}

/// NATS notification message from wasmCloud actors
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NatsNotification {
    pub user_id: String,
    pub alert_id: String,
    pub alert_name: String,
    pub notification_type: String,
    pub priority: NotificationPriority,
    pub payload: NotificationPayload,
    pub timestamp: DateTime<Utc>,
}

/// Generic NATS event from ws.events subject (Phase 1: NLP progress, etc.)
/// Published by Django API for real-time WebSocket delivery
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NatsEvent {
    pub user_id: String,
    pub event_type: String,
    pub job_id: Option<String>,
    pub payload: serde_json::Value,
    pub timestamp: DateTime<Utc>,
}

/// Notification payload from NATS
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationPayload {
    pub triggered_value: String,
    pub threshold: String,
    pub transaction_hash: Option<String>,
    pub chain: String,
    pub wallet: String,
    pub block_number: Option<u64>,
}

/// Connection metadata stored in Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionMetadata {
    pub user_id: String,
    pub connection_id: String,
    pub device: DeviceType,
    pub connected_at: DateTime<Utc>,
    pub last_ping: DateTime<Utc>,
    pub ip_address: String,
    pub user_agent: Option<String>,
    pub filters: NotificationFilters,
}

/// Knox token data from Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KnoxToken {
    pub user_id: String,
    pub token_key: String,
    pub expiry: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
}

/// WebSocket connection state
#[derive(Debug, Clone)]
pub struct Connection {
    pub id: String,
    pub user_id: String,
    pub device: DeviceType,
    pub connected_at: DateTime<Utc>,
    pub last_ping: DateTime<Utc>,
    pub filters: NotificationFilters,
}

impl Connection {
    pub fn new(id: String, _ip_address: String) -> Self {
        let now = Utc::now();
        Self {
            id,
            user_id: String::new(),
            device: DeviceType::Dashboard,
            connected_at: now,
            last_ping: now,
            filters: NotificationFilters::default(),
        }
    }
}

// NOTIFICATION SYSTEM TYPES

/// User notification settings (matching Django model)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserNotificationSettings {
    pub user_id: String,
    pub websocket_enabled: bool,
    pub notifications_enabled: bool,
    pub channels: HashMap<String, HashMap<String, serde_json::Value>>,
    pub priority_routing: HashMap<String, Vec<String>>,
    pub quiet_hours: Option<QuietHours>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl Default for UserNotificationSettings {
    fn default() -> Self {
        let now = Utc::now();
        Self {
            user_id: String::new(),
            websocket_enabled: true, // Default enabled per PRD
            notifications_enabled: true,
            channels: HashMap::new(),
            priority_routing: HashMap::new(),
            quiet_hours: None,
            created_at: now,
            updated_at: now,
        }
    }
}

/// Quiet hours configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuietHours {
    pub start_time: NaiveTime,
    pub end_time: NaiveTime,
    pub timezone: String,
    pub enabled: bool,
    pub priority_override: Vec<String>,
}

/// User notification delivery statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserNotificationStats {
    pub total_notifications: u64,
    pub delivered_notifications: u64,
    pub failed_notifications: u64,
    pub channel_stats: HashMap<String, u64>,
    pub last_notification: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl Default for UserNotificationStats {
    fn default() -> Self {
        let now = Utc::now();
        Self {
            total_notifications: 0,
            delivered_notifications: 0,
            failed_notifications: 0,
            channel_stats: HashMap::new(),
            last_notification: None,
            created_at: now,
            updated_at: now,
        }
    }
}
