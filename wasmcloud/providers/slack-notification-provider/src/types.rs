use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Notification priority levels
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum NotificationPriority {
    Critical,
    High,
    Normal,
    Low,
}

impl NotificationPriority {
    /// Get Slack color for priority level
    pub fn slack_color(&self) -> &str {
        match self {
            NotificationPriority::Critical => "#ff0000", // Red
            NotificationPriority::High => "#ff9900",     // Orange
            NotificationPriority::Normal => "#2eb886",   // Green
            NotificationPriority::Low => "#cccccc",      // Gray
        }
    }

    /// Get emoji for priority level
    pub fn emoji(&self) -> &str {
        match self {
            NotificationPriority::Critical => "🚨",
            NotificationPriority::High => "⚠️",
            NotificationPriority::Normal => "ℹ️",
            NotificationPriority::Low => "📋",
        }
    }
}

/// NATS notification message from wasmCloud actors
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NatsNotification {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub notification_id: Option<String>,
    pub user_id: String,
    pub alert_id: String,
    pub alert_name: String,
    pub notification_type: String,
    pub priority: NotificationPriority,
    pub payload: NotificationPayload,
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

/// Slack webhook configuration stored in Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackChannelConfig {
    pub user_id: String,
    pub webhook_url: String,
    pub channel_name: String,
    pub workspace_name: String,
    pub enabled: bool,
}

/// Slack Block Kit message structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackMessage {
    pub text: String, // Fallback text
    #[serde(skip_serializing_if = "Option::is_none")]
    pub blocks: Option<Vec<SlackBlock>>,
}

/// Slack Block Kit block types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum SlackBlock {
    Header {
        text: SlackText,
    },
    Section {
        text: SlackText,
        #[serde(skip_serializing_if = "Option::is_none")]
        fields: Option<Vec<SlackText>>,
    },
    Divider,
    Context {
        elements: Vec<SlackElement>,
    },
}

/// Slack text object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackText {
    #[serde(rename = "type")]
    pub text_type: String, // "plain_text" or "mrkdwn"
    pub text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub emoji: Option<bool>,
}

impl SlackText {
    pub fn plain_text(text: impl Into<String>) -> Self {
        Self {
            text_type: "plain_text".to_string(),
            text: text.into(),
            emoji: Some(true),
        }
    }

    pub fn markdown(text: impl Into<String>) -> Self {
        Self {
            text_type: "mrkdwn".to_string(),
            text: text.into(),
            emoji: None,
        }
    }
}

/// Slack context element
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum SlackElement {
    #[serde(rename = "mrkdwn")]
    Markdown { text: String },
    #[serde(rename = "plain_text")]
    PlainText { text: String, emoji: bool },
}

/// Delivery status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryStatus {
    pub notification_id: String,
    pub user_id: String,
    pub success: bool,
    pub error_message: Option<String>,
    pub timestamp: DateTime<Utc>,
}

/// Delivery event for DuckLake analytics (matches notification_deliveries schema)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryEvent {
    // Partition columns
    pub delivery_date: String, // YYYY-MM-DD format
    pub channel_type: String,  // "slack"
    pub shard: i32,

    // Primary identifiers
    pub notification_id: String,
    pub channel_id: String,
    pub endpoint_url: Option<String>, // Slack webhook URL

    // Delivery attempt tracking
    pub attempt_number: i32,
    pub max_attempts: i32,
    pub delivery_status: String, // DELIVERED, FAILED, PENDING, RETRYING

    // Timing metrics
    pub started_at: i64,           // Microseconds timestamp
    pub completed_at: Option<i64>, // Microseconds timestamp
    pub response_time_ms: Option<i64>,

    // Response data
    pub http_status_code: Option<i32>,
    pub response_body: Option<String>, // Truncated to 1KB
    pub error_message: Option<String>,
    pub error_type: Option<String>, // NETWORK, TIMEOUT, AUTH, RATE_LIMIT

    // Notification content metadata
    pub alert_id: Option<String>,
    pub transaction_hash: Option<String>,
    pub severity: Option<String>,
    pub message_size_bytes: Option<i32>,

    // Retry and fallback tracking
    pub used_fallback: bool,
    pub fallback_url: Option<String>,
    pub retry_delay_ms: Option<i64>,

    // Provider metadata
    pub provider_id: Option<String>,
    pub provider_version: Option<String>,

    // Processing metadata
    pub ingested_at: i64, // Microseconds timestamp
}
