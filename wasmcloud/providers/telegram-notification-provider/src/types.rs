use serde::{Deserialize, Serialize};

/// Priority levels for notifications
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum NotificationPriority {
    Critical,
    High,
    Normal,
    Low,
}

impl NotificationPriority {
    /// Get Telegram emoji for priority level
    pub fn emoji(&self) -> &str {
        match self {
            NotificationPriority::Critical => "🚨",
            NotificationPriority::High => "⚠️",
            NotificationPriority::Normal => "ℹ️",
            NotificationPriority::Low => "📋",
        }
    }

    /// Get priority label
    pub fn label(&self) -> &str {
        match self {
            NotificationPriority::Critical => "CRITICAL",
            NotificationPriority::High => "HIGH",
            NotificationPriority::Normal => "NORMAL",
            NotificationPriority::Low => "LOW",
        }
    }
}

/// Notification payload from NATS
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NatsNotification {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub notification_id: Option<String>,
    pub user_id: String,
    pub alert_id: String,
    pub alert_name: String,
    pub priority: NotificationPriority,
    pub message: String,
    pub chain: String,
    pub transaction_hash: Option<String>,
    pub wallet_address: Option<String>,
    pub block_number: Option<u64>,
    pub timestamp: String,
}

/// Telegram configuration from Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelegramChannelConfig {
    pub user_id: String,
    pub bot_token: String,
    pub chat_id: String,
    pub username: Option<String>,
    pub enabled: bool,
}

/// Telegram sendMessage API request
#[derive(Debug, Serialize)]
pub struct TelegramSendMessageRequest {
    pub chat_id: String,
    pub text: String,
    pub parse_mode: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub disable_web_page_preview: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub disable_notification: Option<bool>,
}

/// Telegram API response
#[derive(Debug, Deserialize)]
pub struct TelegramApiResponse {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<TelegramMessage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

/// Telegram message object
#[derive(Debug, Deserialize)]
pub struct TelegramMessage {
    pub message_id: i64,
    pub date: i64,
    pub chat: TelegramChat,
}

/// Telegram chat object
#[derive(Debug, Deserialize)]
pub struct TelegramChat {
    pub id: i64,
    #[serde(rename = "type")]
    pub chat_type: String,
}

/// Telegram bot command
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelegramBotCommand {
    pub command: String,
    pub chat_id: i64,
    pub user_id: Option<i64>,
    pub username: Option<String>,
    pub text: String,
}

/// Telegram update (webhook payload)
#[derive(Debug, Deserialize)]
pub struct TelegramUpdate {
    pub update_id: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<TelegramUpdateMessage>,
}

/// Telegram update message
#[derive(Debug, Deserialize)]
pub struct TelegramUpdateMessage {
    pub message_id: i64,
    pub from: TelegramUser,
    pub chat: TelegramChat,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    pub date: i64,
}

/// Telegram user
#[derive(Debug, Deserialize)]
pub struct TelegramUser {
    pub id: i64,
    pub is_bot: bool,
    pub first_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub username: Option<String>,
}

/// Delivery event for DuckLake analytics (matches notification_deliveries schema)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryEvent {
    // Partition columns
    pub delivery_date: String, // YYYY-MM-DD format
    pub channel_type: String,  // "telegram"
    pub shard: i32,

    // Primary identifiers
    pub notification_id: String,
    pub channel_id: String,
    pub endpoint_url: Option<String>, // Telegram Bot API URL

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
