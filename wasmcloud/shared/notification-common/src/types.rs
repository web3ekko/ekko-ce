//! Core types for notification system
//!
//! This module defines the shared types used across all notification providers,
//! building on the existing WebSocket provider patterns.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Notification channels supported by the system
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "lowercase")]
pub enum NotificationChannel {
    Email,
    Slack,
    Sms,
    Telegram,
    Discord,
    Webhook,
    WebSocket,
}

impl NotificationChannel {
    /// Get NATS subject for immediate delivery on this channel
    /// PRD pattern: notifications.send.immediate.{channel}
    pub fn nats_subject(&self) -> String {
        format!("notifications.send.immediate.{}", self.as_str())
    }

    /// Get NATS subject for digest delivery on this channel
    /// PRD pattern: notifications.send.digest.{channel}
    pub fn nats_subject_digest(&self) -> String {
        format!("notifications.send.digest.{}", self.as_str())
    }

    /// Get channel name as lowercase string
    pub fn as_str(&self) -> &'static str {
        match self {
            NotificationChannel::Email => "email",
            NotificationChannel::Slack => "slack",
            NotificationChannel::Sms => "sms",
            NotificationChannel::Telegram => "telegram",
            NotificationChannel::Discord => "discord",
            NotificationChannel::Webhook => "webhook",
            NotificationChannel::WebSocket => "websocket",
        }
    }

    /// Check if channel supports rich formatting
    pub fn supports_rich_format(&self) -> bool {
        matches!(
            self,
            NotificationChannel::Email
                | NotificationChannel::Slack
                | NotificationChannel::Discord
                | NotificationChannel::WebSocket
        )
    }
}

impl std::fmt::Display for NotificationChannel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            NotificationChannel::Email => write!(f, "Email"),
            NotificationChannel::Slack => write!(f, "Slack"),
            NotificationChannel::Sms => write!(f, "SMS"),
            NotificationChannel::Telegram => write!(f, "Telegram"),
            NotificationChannel::Discord => write!(f, "Discord"),
            NotificationChannel::Webhook => write!(f, "Webhook"),
            NotificationChannel::WebSocket => write!(f, "WebSocket"),
        }
    }
}

/// Notification priority levels (reusing from WebSocket provider)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[serde(rename_all = "lowercase")]
pub enum NotificationPriority {
    Critical,
    High,
    Medium,
    Normal,
    Low,
}

impl NotificationPriority {
    /// Get numeric priority for routing decisions
    pub fn numeric_value(&self) -> u8 {
        match self {
            NotificationPriority::Critical => 5,
            NotificationPriority::High => 4,
            NotificationPriority::Medium => 3,
            NotificationPriority::Normal => 2,
            NotificationPriority::Low => 1,
        }
    }

    /// Determine if priority requires immediate delivery
    pub fn requires_immediate_delivery(&self) -> bool {
        matches!(
            self,
            NotificationPriority::Critical
                | NotificationPriority::High
                | NotificationPriority::Medium
        )
    }
}

/// Device types that can connect (from WebSocket provider)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "lowercase")]
pub enum DeviceType {
    Dashboard,
    IOs,
    Android,
}

impl std::fmt::Display for DeviceType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DeviceType::Dashboard => write!(f, "Dashboard"),
            DeviceType::IOs => write!(f, "iOS"),
            DeviceType::Android => write!(f, "Android"),
        }
    }
}

/// User notification settings from Django/Redis cache
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserNotificationSettings {
    pub user_id: String,
    pub websocket_enabled: bool,
    pub notifications_enabled: bool,
    pub channels: HashMap<String, ChannelSettings>,
    pub priority_routing: HashMap<String, Vec<NotificationChannel>>,
    pub quiet_hours: Option<QuietHours>,
    pub personalization: Option<PersonalizationData>,
    pub cached_at: DateTime<Utc>,
}

impl Default for UserNotificationSettings {
    fn default() -> Self {
        Self {
            user_id: String::new(),
            websocket_enabled: true, // Default enabled as per PRD
            notifications_enabled: true,
            channels: HashMap::new(),
            priority_routing: HashMap::new(),
            quiet_hours: None,
            personalization: None,
            cached_at: Utc::now(),
        }
    }
}

/// Group notification settings from Django/Redis cache
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupNotificationSettings {
    pub group_id: String,
    pub group_name: String,
    pub mandatory_channels: Vec<NotificationChannel>,
    pub escalation_rules: HashMap<String, EscalationRule>,
    pub shared_channels: HashMap<String, ChannelSettings>,
    pub member_overrides_allowed: bool,
    pub cached_at: DateTime<Utc>,
}

/// Channel-specific settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChannelSettings {
    pub enabled: bool,
    pub config: HashMap<String, serde_json::Value>,
}

/// Quiet hours configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuietHours {
    pub start_time: String, // HH:MM format
    pub end_time: String,   // HH:MM format
    pub timezone: String,
    pub enabled: bool,
    pub priority_override: Vec<NotificationPriority>, // These priorities ignore quiet hours
}

/// Escalation rule for group notifications
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EscalationRule {
    pub delay_minutes: u32,
    pub channels: Vec<NotificationChannel>,
    pub condition: String, // JSON condition for when to escalate
}

/// Personalization data for customizing notification messages
///
/// This struct contains user-specific customization preferences for notifications,
/// including custom nicknames for wallet addresses and display preferences.
///
/// # Examples
///
/// ```rust
/// use notification_common::types::{PersonalizationData, UserDisplayPreferences, AddressDisplayFormat};
/// use std::collections::HashMap;
///
/// let mut personalization = PersonalizationData::default();
/// personalization.wallet_nicknames.insert(
///     "0x1234567890abcdef:1".to_string(),
///     "My Trading Wallet".to_string()
/// );
/// personalization.language = Some("en".to_string());
/// personalization.timezone = Some("America/New_York".to_string());
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PersonalizationData {
    /// Mapping of "address:chain_id" to custom nickname
    ///
    /// Key format: "{address}:{chain_id}" (e.g., "0x1234...abcd:1")
    /// Value: User-defined nickname (e.g., "My Trading Wallet")
    ///
    /// # Examples
    ///
    /// ```
    /// # use std::collections::HashMap;
    /// let mut nicknames = HashMap::new();
    /// nicknames.insert("0x1234567890abcdef:1".to_string(), "My Trading Wallet".to_string());
    /// nicknames.insert("0xabcdef1234567890:137".to_string(), "Polygon Savings".to_string());
    /// ```
    pub wallet_nicknames: HashMap<String, String>,

    /// User's display preferences for addresses and notifications
    pub display_preferences: UserDisplayPreferences,

    /// ISO 639-1 language code (e.g., "en", "es", "fr", "de", "ja", "zh")
    ///
    /// Used for notification message localization when available.
    /// Falls back to English if not specified or unsupported.
    pub language: Option<String>,

    /// IANA timezone identifier (e.g., "America/New_York", "Europe/London", "Asia/Tokyo")
    ///
    /// Used for formatting timestamps in notifications according to user's local time.
    pub timezone: Option<String>,
}

impl Default for PersonalizationData {
    fn default() -> Self {
        Self {
            wallet_nicknames: HashMap::new(),
            display_preferences: UserDisplayPreferences::default(),
            language: None,
            timezone: None,
        }
    }
}

/// User preferences for how addresses should be displayed in notifications
///
/// # Examples
///
/// ```rust
/// use notification_common::types::{UserDisplayPreferences, AddressDisplayFormat};
///
/// let preferences = UserDisplayPreferences {
///     address_format: AddressDisplayFormat::NicknameWithTruncated,
/// };
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserDisplayPreferences {
    /// Format to use when displaying blockchain addresses
    pub address_format: AddressDisplayFormat,
}

impl Default for UserDisplayPreferences {
    fn default() -> Self {
        Self {
            address_format: AddressDisplayFormat::default(),
        }
    }
}

/// Format options for displaying blockchain addresses in notifications
///
/// This enum defines how wallet addresses should be formatted when displayed
/// to users in notifications, allowing for personalization and readability.
///
/// # Examples
///
/// ```rust
/// use notification_common::types::AddressDisplayFormat;
///
/// // Using nicknames with truncated addresses
/// let format = AddressDisplayFormat::NicknameWithTruncated;
///
/// // Example outputs based on format:
/// // NicknameWithTruncated: "My Wallet (0x1234...5678)"
/// // TruncatedOnly: "0x1234...5678"
/// // FullAddress: "0x1234567890abcdef1234567890abcdef12345678"
/// // NicknameOrTruncated: "My Wallet" (if nickname exists) or "0x1234...5678"
/// ```
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AddressDisplayFormat {
    /// Display as "CustomName (0x1234...5678)" - shows nickname with truncated address
    ///
    /// This is the recommended default as it provides context while remaining concise.
    /// Falls back to `TruncatedOnly` if no nickname is available.
    NicknameWithTruncated,

    /// Display as "0x1234...5678" - truncated address only
    ///
    /// Shows only the first 6 and last 4 characters of the address.
    /// Useful for users who prefer minimal display or don't use nicknames.
    TruncatedOnly,

    /// Display as "0x1234567890abcdef..." - full blockchain address
    ///
    /// Shows the complete address without truncation.
    /// Useful for users who need to verify exact addresses or copy them.
    FullAddress,

    /// Show only nickname if available, otherwise truncated address
    ///
    /// Format: "My Wallet" or "0x1234...5678" (if no nickname)
    /// Most concise option when nicknames are consistently used.
    NicknameOrTruncated,
}

impl Default for AddressDisplayFormat {
    fn default() -> Self {
        Self::NicknameWithTruncated
    }
}

/// Delivery status returned by providers
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum LegacyDeliveryStatus {
    Delivered {
        channel: String,
        message_id: String,
        timestamp: DateTime<Utc>,
        provider_response: Option<serde_json::Value>,
    },
    Failed {
        channel: String,
        error_code: Option<String>,
        error_message: String,
        retryable: bool,
        retry_after: Option<DateTime<Utc>>,
    },
    ChannelDisabled {
        channel: String,
        reason: String,
    },
    QuietHours {
        channel: String,
        quiet_until: DateTime<Utc>,
    },
    RateLimited {
        channel: String,
        retry_after: DateTime<Utc>,
    },
}

/// Health status for provider health checks
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthStatus {
    pub healthy: bool,
    pub message: String,
    pub last_check: DateTime<Utc>,
    pub details: HashMap<String, serde_json::Value>,
}

/// Provider metrics for monitoring
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderMetrics {
    pub channel: NotificationChannel,
    pub total_sent: u64,
    pub successful_deliveries: u64,
    pub failed_deliveries: u64,
    pub average_latency_ms: f64,
    pub last_activity: DateTime<Utc>,
    pub error_rate_percent: f64,
}

impl ProviderMetrics {
    pub fn new(channel: NotificationChannel) -> Self {
        Self {
            channel,
            total_sent: 0,
            successful_deliveries: 0,
            failed_deliveries: 0,
            average_latency_ms: 0.0,
            last_activity: Utc::now(),
            error_rate_percent: 0.0,
        }
    }

    pub fn record_success(&mut self, latency_ms: f64) {
        self.total_sent += 1;
        self.successful_deliveries += 1;
        self.last_activity = Utc::now();
        self.update_average_latency(latency_ms);
        self.update_error_rate();
    }

    pub fn record_failure(&mut self) {
        self.total_sent += 1;
        self.failed_deliveries += 1;
        self.last_activity = Utc::now();
        self.update_error_rate();
    }

    fn update_average_latency(&mut self, new_latency: f64) {
        if self.successful_deliveries == 1 {
            self.average_latency_ms = new_latency;
        } else {
            // Simple moving average
            self.average_latency_ms =
                (self.average_latency_ms * ((self.successful_deliveries - 1) as f64) + new_latency)
                    / (self.successful_deliveries as f64);
        }
    }

    fn update_error_rate(&mut self) {
        if self.total_sent > 0 {
            self.error_rate_percent =
                (self.failed_deliveries as f64 / self.total_sent as f64) * 100.0;
        }
    }
}

/// Configuration for notification providers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderConfig {
    pub channel: NotificationChannel,
    pub redis_url: String,
    pub nats_url: String,
    pub provider_settings: HashMap<String, serde_json::Value>,
}

/// Context information passed to providers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationContext {
    pub request_id: String,
    pub user_id: String,
    pub group_id: Option<String>,
    pub alert_id: String,
    pub priority: NotificationPriority,
    pub timestamp: DateTime<Utc>,
    pub retry_count: u32,
    pub correlation_id: Option<String>,
}

impl NotificationContext {
    pub fn new(user_id: String, alert_id: String, priority: NotificationPriority) -> Self {
        Self {
            request_id: Uuid::new_v4().to_string(),
            user_id,
            group_id: None,
            alert_id,
            priority,
            timestamp: Utc::now(),
            retry_count: 0,
            correlation_id: None,
        }
    }

    pub fn with_group(mut self, group_id: String) -> Self {
        self.group_id = Some(group_id);
        self
    }

    pub fn with_correlation_id(mut self, correlation_id: String) -> Self {
        self.correlation_id = Some(correlation_id);
        self
    }

    pub fn increment_retry(&mut self) {
        self.retry_count += 1;
    }
}
