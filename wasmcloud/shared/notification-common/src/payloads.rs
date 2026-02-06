//! Notification payload structures and conversions
//!
//! This module defines the standardized payload structures sent from actors to providers,
//! and provides conversion methods for different notification channels.

use crate::{
    NotificationChannel, NotificationContext, NotificationPriority, PersonalizationData,
    UserNotificationSettings,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Primary notification request sent from actors to providers via NATS
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationRequest {
    pub notification_id: Uuid,
    pub user_id: String,
    pub group_id: Option<String>,
    pub alert_id: String,
    pub alert_name: String,
    pub channel: NotificationChannel,
    pub priority: NotificationPriority,
    pub title: String,
    pub message: String,
    pub details: HashMap<String, serde_json::Value>,
    pub template_name: Option<String>,
    pub template_variables: HashMap<String, String>,
    pub actions: Vec<NotificationAction>,
    pub delivery_options: DeliveryOptions,
    pub timestamp: DateTime<Utc>,

    // Personalization data for custom wallet names and display preferences
    pub personalization: PersonalizationData,

    // Transaction address fields with personalized display versions
    /// Raw blockchain address of the sender (e.g., "0x1234567890abcdef...")
    pub from_address: Option<String>,
    /// Personalized display version of from_address (e.g., "My Wallet (0x1234...5678)")
    pub from_address_display: Option<String>,

    /// Raw blockchain address of the recipient (e.g., "0xabcdef1234567890...")
    pub to_address: Option<String>,
    /// Personalized display version of to_address (e.g., "Trading Account (0xabcd...7890)")
    pub to_address_display: Option<String>,

    /// Raw blockchain contract address (e.g., "0x0000000000000000...")
    pub contract_address: Option<String>,
    /// Personalized display version of contract_address (e.g., "USDT Contract (0x0000...0000)")
    pub contract_address_display: Option<String>,

    // Legacy fields (kept for compatibility)
    pub context: Option<NotificationContext>,
    pub content: Option<NotificationContent>,
    pub target_channels: Vec<NotificationChannel>,
}

impl NotificationRequest {
    pub fn new(
        notification_id: Uuid,
        user_id: String,
        alert_id: String,
        alert_name: String,
        channel: NotificationChannel,
        title: String,
        message: String,
    ) -> Self {
        Self {
            notification_id,
            user_id,
            group_id: None,
            alert_id,
            alert_name,
            channel: channel.clone(),
            priority: NotificationPriority::Medium,
            title,
            message,
            details: HashMap::new(),
            template_name: None,
            template_variables: HashMap::new(),
            actions: vec![],
            delivery_options: DeliveryOptions::default(),
            timestamp: Utc::now(),

            // Personalization fields
            personalization: PersonalizationData::default(),
            from_address: None,
            from_address_display: None,
            to_address: None,
            to_address_display: None,
            contract_address: None,
            contract_address_display: None,

            // Legacy fields
            context: None,
            content: None,
            target_channels: vec![channel],
        }
    }

    /// Add personalization data to the notification
    ///
    /// This method allows setting user-specific customization preferences for notifications,
    /// including custom wallet nicknames and display preferences.
    ///
    /// # Examples
    ///
    /// ```rust
    /// use notification_common::payloads::NotificationRequest;
    /// use notification_common::NotificationChannel;
    /// use notification_common::types::PersonalizationData;
    /// use uuid::Uuid;
    ///
    /// let personalization = PersonalizationData::default();
    /// let notification = NotificationRequest::new(
    ///     Uuid::new_v4(),
    ///     "user123".to_string(),
    ///     "alert456".to_string(),
    ///     "Price Alert".to_string(),
    ///     NotificationChannel::WebSocket,
    ///     "ETH Price Alert".to_string(),
    ///     "Price exceeded threshold".to_string(),
    /// ).with_personalization(personalization);
    /// ```
    pub fn with_personalization(mut self, personalization: PersonalizationData) -> Self {
        self.personalization = personalization;
        self
    }

    /// Add transaction addresses to the notification
    ///
    /// This method sets the raw blockchain addresses for transaction participants.
    /// These addresses will be later personalized using the user's display preferences.
    ///
    /// # Arguments
    ///
    /// * `from_address` - The sender's blockchain address
    /// * `to_address` - The recipient's blockchain address
    /// * `contract_address` - The contract address (for token transfers)
    ///
    /// # Examples
    ///
    /// ```rust
    /// use notification_common::payloads::NotificationRequest;
    /// use notification_common::NotificationChannel;
    /// use uuid::Uuid;
    ///
    /// let notification = NotificationRequest::new(
    ///     Uuid::new_v4(),
    ///     "user123".to_string(),
    ///     "alert456".to_string(),
    ///     "Price Alert".to_string(),
    ///     NotificationChannel::WebSocket,
    ///     "ETH Price Alert".to_string(),
    ///     "Price exceeded threshold".to_string(),
    /// )
    ///     .with_addresses(
    ///         Some("0x1234567890abcdef...".to_string()),
    ///         Some("0xabcdef1234567890...".to_string()),
    ///         Some("0x0000000000000000...".to_string()),
    ///     );
    /// ```
    pub fn with_addresses(
        mut self,
        from_address: Option<String>,
        to_address: Option<String>,
        contract_address: Option<String>,
    ) -> Self {
        self.from_address = from_address;
        self.to_address = to_address;
        self.contract_address = contract_address;
        self
    }

    /// Add personalized display versions of transaction addresses
    ///
    /// This method sets the user-friendly display versions of addresses,
    /// which include custom nicknames if available (e.g., "My Wallet (0x1234...5678)").
    ///
    /// # Arguments
    ///
    /// * `from_display` - Personalized display version of the sender address
    /// * `to_display` - Personalized display version of the recipient address
    /// * `contract_display` - Personalized display version of the contract address
    ///
    /// # Examples
    ///
    /// ```rust
    /// use notification_common::payloads::NotificationRequest;
    /// use notification_common::NotificationChannel;
    /// use uuid::Uuid;
    ///
    /// let notification = NotificationRequest::new(
    ///     Uuid::new_v4(),
    ///     "user123".to_string(),
    ///     "alert456".to_string(),
    ///     "Price Alert".to_string(),
    ///     NotificationChannel::WebSocket,
    ///     "ETH Price Alert".to_string(),
    ///     "Price exceeded threshold".to_string(),
    /// )
    ///     .with_address_displays(
    ///         Some("My Wallet (0x1234...5678)".to_string()),
    ///         Some("Trading Account (0xabcd...7890)".to_string()),
    ///         Some("USDT Contract (0x0000...0000)".to_string()),
    ///     );
    /// ```
    pub fn with_address_displays(
        mut self,
        from_display: Option<String>,
        to_display: Option<String>,
        contract_display: Option<String>,
    ) -> Self {
        self.from_address_display = from_display;
        self.to_address_display = to_display;
        self.contract_address_display = contract_display;
        self
    }

    pub fn with_variables(mut self, variables: HashMap<String, String>) -> Self {
        self.template_variables = variables;
        self
    }

    pub fn with_channels(mut self, channels: Vec<NotificationChannel>) -> Self {
        self.target_channels = channels;
        self
    }

    pub fn with_delivery_options(mut self, options: DeliveryOptions) -> Self {
        self.delivery_options = options;
        self
    }

    /// Convert to channel-specific payload
    pub fn to_email_payload(
        &self,
        settings: &UserNotificationSettings,
    ) -> Result<EmailPayload, crate::ValidationError> {
        let channel_config = settings
            .channels
            .get("email")
            .ok_or_else(|| crate::ValidationError::MissingChannelConfig("email".to_string()))?;

        if !channel_config.enabled {
            return Err(crate::ValidationError::ChannelDisabled("email".to_string()));
        }

        Ok(EmailPayload {
            to: channel_config
                .config
                .get("address")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            subject: self
                .content
                .as_ref()
                .map(|c| c.subject.clone())
                .unwrap_or_default(),
            html_body: self.content.as_ref().and_then(|c| c.html_content.clone()),
            text_body: self
                .content
                .as_ref()
                .map(|c| c.text_content.clone())
                .unwrap_or_default(),
            from_name: self.delivery_options.sender_name.clone(),
            from_email: self.delivery_options.sender_email.clone(),
            reply_to: self.delivery_options.reply_to.clone(),
            attachments: Vec::new(),
            headers: HashMap::new(),
            template_id: self.template_name.clone().unwrap_or_default(),
            template_variables: self
                .template_variables
                .iter()
                .map(|(k, v)| (k.clone(), serde_json::Value::String(v.clone())))
                .collect(),
        })
    }

    pub fn to_slack_payload(
        &self,
        settings: &UserNotificationSettings,
    ) -> Result<SlackPayload, crate::ValidationError> {
        let channel_config = settings
            .channels
            .get("slack")
            .ok_or_else(|| crate::ValidationError::MissingChannelConfig("slack".to_string()))?;

        if !channel_config.enabled {
            return Err(crate::ValidationError::ChannelDisabled("slack".to_string()));
        }

        let channel = channel_config
            .config
            .get("channel")
            .and_then(|v| v.as_str())
            .unwrap_or("#general")
            .to_string();

        Ok(SlackPayload {
            channel,
            text: self
                .content
                .as_ref()
                .map(|c| c.text_content.clone())
                .unwrap_or_default(),
            blocks: self
                .content
                .as_ref()
                .and_then(|c| c.structured_content.clone()),
            username: self.delivery_options.sender_name.clone(),
            icon_emoji: Some(":bell:".to_string()),
            thread_ts: None,
            unfurl_links: true,
            unfurl_media: true,
        })
    }

    pub fn to_sms_payload(
        &self,
        settings: &UserNotificationSettings,
    ) -> Result<SmsPayload, crate::ValidationError> {
        let channel_config = settings
            .channels
            .get("sms")
            .ok_or_else(|| crate::ValidationError::MissingChannelConfig("sms".to_string()))?;

        if !channel_config.enabled {
            return Err(crate::ValidationError::ChannelDisabled("sms".to_string()));
        }

        let phone = channel_config
            .config
            .get("phone")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        // SMS has character limits, so we truncate
        let mut message = self
            .content
            .as_ref()
            .map(|c| c.text_content.clone())
            .unwrap_or_default();
        if message.len() > 160 {
            message = format!("{}...", &message[..157]);
        }

        Ok(SmsPayload {
            to: phone,
            message,
            from: self.delivery_options.sender_phone.clone(),
        })
    }

    pub fn to_telegram_payload(
        &self,
        settings: &UserNotificationSettings,
    ) -> Result<TelegramPayload, crate::ValidationError> {
        let channel_config = settings
            .channels
            .get("telegram")
            .ok_or_else(|| crate::ValidationError::MissingChannelConfig("telegram".to_string()))?;

        if !channel_config.enabled {
            return Err(crate::ValidationError::ChannelDisabled(
                "telegram".to_string(),
            ));
        }

        let chat_id = channel_config
            .config
            .get("chat_id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        Ok(TelegramPayload {
            chat_id,
            text: self
                .content
                .as_ref()
                .map(|c| c.text_content.clone())
                .unwrap_or_default(),
            parse_mode: Some("HTML".to_string()),
            disable_web_page_preview: false,
            disable_notification: self
                .context
                .as_ref()
                .map(|c| c.priority == NotificationPriority::Low)
                .unwrap_or(false),
        })
    }

    pub fn to_discord_payload(
        &self,
        settings: &UserNotificationSettings,
    ) -> Result<DiscordPayload, crate::ValidationError> {
        let channel_config = settings
            .channels
            .get("discord")
            .ok_or_else(|| crate::ValidationError::MissingChannelConfig("discord".to_string()))?;

        if !channel_config.enabled {
            return Err(crate::ValidationError::ChannelDisabled(
                "discord".to_string(),
            ));
        }

        let webhook_url = channel_config
            .config
            .get("webhook_url")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        Ok(DiscordPayload {
            webhook_url,
            content: self
                .content
                .as_ref()
                .map(|c| c.text_content.clone())
                .unwrap_or_default(),
            username: self.delivery_options.sender_name.clone(),
            avatar_url: None,
            embeds: self
                .content
                .as_ref()
                .and_then(|c| c.embeds.clone())
                .unwrap_or_default(),
            tts: self
                .context
                .as_ref()
                .map(|c| c.priority == NotificationPriority::Critical)
                .unwrap_or(false),
        })
    }

    pub fn to_webhook_payload(
        &self,
        settings: &UserNotificationSettings,
    ) -> Result<WebhookPayload, crate::ValidationError> {
        let channel_config = settings
            .channels
            .get("webhook")
            .ok_or_else(|| crate::ValidationError::MissingChannelConfig("webhook".to_string()))?;

        if !channel_config.enabled {
            return Err(crate::ValidationError::ChannelDisabled(
                "webhook".to_string(),
            ));
        }

        let url = channel_config
            .config
            .get("url")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let mut headers = HashMap::new();
        if let Some(auth_header) = channel_config.config.get("auth_header") {
            if let Some(auth_value) = auth_header.as_str() {
                headers.insert("Authorization".to_string(), auth_value.to_string());
            }
        }

        Ok(WebhookPayload {
            url,
            method: "POST".to_string(),
            headers,
            body: serde_json::json!({
                "notification_id": self.context.as_ref().map(|c| c.request_id.clone()).unwrap_or_default(),
                "user_id": self.context.as_ref().map(|c| c.user_id.clone()).unwrap_or_default(),
                "alert_id": self.context.as_ref().map(|c| c.alert_id.clone()).unwrap_or_default(),
                "priority": self.context.as_ref().map(|c| c.priority.clone()).unwrap_or(NotificationPriority::Normal),
                "timestamp": self.context.as_ref().map(|c| c.timestamp).unwrap_or_else(Utc::now),
                "content": self.content,
                "template_variables": self.template_variables
            }),
        })
    }

    /// Convert to WebSocket payload with personalized address display fields
    ///
    /// This method creates a WebSocket-specific payload that includes both raw addresses
    /// and their personalized display versions for real-time notifications.
    ///
    /// # Returns
    ///
    /// A `WebSocketPayload` containing the notification data with personalized address fields.
    pub fn to_websocket_payload(&self) -> WebSocketPayload {
        WebSocketPayload {
            notification_id: self
                .context
                .as_ref()
                .map(|c| c.request_id.clone())
                .unwrap_or_default(),
            alert_id: self
                .context
                .as_ref()
                .map(|c| c.alert_id.clone())
                .unwrap_or_default(),
            alert_name: self
                .template_variables
                .get("alert_name")
                .map(|v| v.clone())
                .unwrap_or_else(|| "Alert".to_string()),
            priority: self
                .context
                .as_ref()
                .map(|c| c.priority.clone())
                .unwrap_or(NotificationPriority::Normal),
            message: self
                .content
                .as_ref()
                .map(|c| c.text_content.clone())
                .unwrap_or_default(),
            details: self
                .template_variables
                .iter()
                .map(|(k, v)| (k.clone(), serde_json::Value::String(v.clone())))
                .collect(),
            timestamp: self
                .context
                .as_ref()
                .map(|c| c.timestamp)
                .unwrap_or_else(Utc::now),
            actions: self
                .content
                .as_ref()
                .and_then(|c| c.actions.clone())
                .unwrap_or_default(),

            // Personalized address display fields
            from_address_display: self.from_address_display.clone(),
            to_address_display: self.to_address_display.clone(),
            contract_address_display: self.contract_address_display.clone(),
        }
    }
}

/// Core notification content structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationContent {
    pub subject: String,
    pub text_content: String,
    pub html_content: Option<String>,
    pub structured_content: Option<serde_json::Value>, // For Slack blocks, etc.
    pub embeds: Option<Vec<serde_json::Value>>,        // For Discord embeds
    pub actions: Option<Vec<NotificationAction>>,
}

/// Notification action for interactive elements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationAction {
    pub id: String,
    pub label: String,
    pub url: String,
    pub style: Option<String>, // primary, secondary, danger
}

/// Status of a notification delivery attempt
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryStatus {
    pub notification_id: uuid::Uuid,
    pub channel: NotificationChannel,
    pub delivered: bool,
    pub delivered_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub provider_message_id: Option<String>,
    pub retry_count: u32,
}

/// Delivery options and metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryOptions {
    pub sender_name: Option<String>,
    pub sender_email: Option<String>,
    pub sender_phone: Option<String>,
    pub reply_to: Option<String>,
    pub urgency: bool,
    pub retry_policy: RetryPolicy,
}

impl Default for DeliveryOptions {
    fn default() -> Self {
        Self {
            sender_name: Some("Ekko Alerts".to_string()),
            sender_email: Some("alerts@ekko.zone".to_string()),
            sender_phone: None,
            reply_to: Some("support@ekko.zone".to_string()),
            urgency: false,
            retry_policy: RetryPolicy::default(),
        }
    }
}

/// Retry policy configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetryPolicy {
    pub max_attempts: u32,
    pub initial_delay_ms: u64,
    pub max_delay_ms: u64,
    pub exponential_base: f64,
}

impl Default for RetryPolicy {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            initial_delay_ms: 1000,
            max_delay_ms: 30000,
            exponential_base: 2.0,
        }
    }
}

// Channel-specific payload structures

/// Email-specific payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailPayload {
    pub to: String,
    pub subject: String,
    pub html_body: Option<String>,
    pub text_body: String,
    pub from_name: Option<String>,
    pub from_email: Option<String>,
    pub reply_to: Option<String>,
    pub attachments: Vec<EmailAttachment>,
    pub headers: HashMap<String, String>,
    pub template_id: String,
    pub template_variables: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailAttachment {
    pub filename: String,
    pub content_type: String,
    pub content: Vec<u8>,
}

/// Slack-specific payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackPayload {
    pub channel: String,
    pub text: String,
    pub blocks: Option<serde_json::Value>,
    pub username: Option<String>,
    pub icon_emoji: Option<String>,
    pub thread_ts: Option<String>,
    pub unfurl_links: bool,
    pub unfurl_media: bool,
}

/// SMS-specific payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SmsPayload {
    pub to: String,
    pub message: String,
    pub from: Option<String>,
}

/// Telegram-specific payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelegramPayload {
    pub chat_id: String,
    pub text: String,
    pub parse_mode: Option<String>,
    pub disable_web_page_preview: bool,
    pub disable_notification: bool,
}

/// Discord-specific payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscordPayload {
    pub webhook_url: String,
    pub content: String,
    pub username: Option<String>,
    pub avatar_url: Option<String>,
    pub embeds: Vec<serde_json::Value>,
    pub tts: bool,
}

/// Generic webhook payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebhookPayload {
    pub url: String,
    pub method: String,
    pub headers: HashMap<String, String>,
    pub body: serde_json::Value,
}

/// WebSocket-specific payload (building on existing WebSocket provider)
///
/// This payload includes personalized display fields for wallet addresses,
/// allowing notifications to show user-friendly names like "My Wallet (0x1234...5678)".
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebSocketPayload {
    pub notification_id: String,
    pub alert_id: String,
    pub alert_name: String,
    pub priority: NotificationPriority,
    pub message: String,
    pub details: HashMap<String, serde_json::Value>,
    pub timestamp: DateTime<Utc>,
    pub actions: Vec<NotificationAction>,

    // Personalized address display fields
    /// Personalized display version of the sender address (e.g., "My Wallet (0x1234...5678)")
    ///
    /// This field is None if the sender address is not set or not personalized.
    pub from_address_display: Option<String>,

    /// Personalized display version of the recipient address (e.g., "Trading Account (0xabcd...7890)")
    ///
    /// This field is None if the recipient address is not set or not personalized.
    pub to_address_display: Option<String>,

    /// Personalized display version of the contract address (e.g., "USDT Contract (0x0000...0000)")
    ///
    /// This field is None if the contract address is not set or not personalized.
    pub contract_address_display: Option<String>,
}
