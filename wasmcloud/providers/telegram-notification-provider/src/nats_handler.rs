use crate::bot_commands::BotCommandHandler;
use crate::formatter::format_telegram_message;
use crate::redis_client::RedisClient;
use crate::telegram_client::TelegramClient;
use crate::types::{DeliveryEvent, NatsNotification, NotificationPriority};
use anyhow::{Context, Result};
use async_nats::{Client, Message, Subscriber};
use chrono::Utc;
use futures_util::StreamExt;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

const TELEGRAM_NOTIFICATION_SUBJECT: &str = "notifications.send.immediate.telegram";
const NOTIFICATION_DUCKLAKE_SUBJECT: &str = "ducklake.notification_deliveries.ekko.default.write";

/// NATS handler for Telegram notifications
pub struct NatsHandler {
    nats_client: Client,
    telegram_client: Arc<TelegramClient>,
    redis_client: Arc<Mutex<RedisClient>>,
    bot_command_handler: Arc<BotCommandHandler>,
}

impl NatsHandler {
    pub fn new(
        nats_client: Client,
        telegram_client: Arc<TelegramClient>,
        redis_client: Arc<Mutex<RedisClient>>,
    ) -> Self {
        let bot_command_handler = Arc::new(BotCommandHandler::new(
            telegram_client.clone(),
            redis_client.clone(),
        ));

        Self {
            nats_client,
            telegram_client,
            redis_client,
            bot_command_handler,
        }
    }

    /// Start listening for notifications on the NATS subject
    pub async fn start(&self) -> Result<()> {
        info!(
            "Subscribing to NATS subject: {}",
            TELEGRAM_NOTIFICATION_SUBJECT
        );

        let subscriber = self
            .nats_client
            .subscribe(TELEGRAM_NOTIFICATION_SUBJECT)
            .await
            .context("Failed to subscribe to NATS subject")?;

        info!(
            "Successfully subscribed to {}",
            TELEGRAM_NOTIFICATION_SUBJECT
        );

        self.process_notifications(subscriber).await
    }

    /// Process incoming notifications from NATS
    async fn process_notifications(&self, mut subscriber: Subscriber) -> Result<()> {
        while let Some(message) = subscriber.next().await {
            if let Err(e) = self.handle_notification(message).await {
                error!("Error handling notification: {}", e);
            }
        }

        warn!("NATS subscription ended unexpectedly");
        Ok(())
    }

    /// Handle incoming notification from NATS
    async fn handle_notification(&self, message: Message) -> Result<()> {
        let notification: NatsNotification = serde_json::from_slice(&message.payload)
            .context("Failed to deserialize NATS notification")?;

        info!(
            "Received Telegram notification for user_id: {}, alert: {}",
            notification.user_id, notification.alert_id
        );

        // Check if Telegram is enabled for this user
        let mut redis = self.redis_client.lock().await;
        let telegram_enabled = redis
            .is_telegram_enabled_for_user(&notification.user_id)
            .await?;

        if !telegram_enabled {
            info!(
                "Telegram not enabled for user_id: {}, skipping",
                notification.user_id
            );
            return Ok(());
        }

        // Get Telegram configuration
        let telegram_config = redis
            .get_telegram_config(&notification.user_id)
            .await?
            .ok_or_else(|| anyhow::anyhow!("No Telegram config found for user"))?;

        // Release the lock before making HTTP call
        drop(redis);

        // Format message
        let telegram_message = format_telegram_message(&notification);

        // Send to Telegram
        info!(
            "Sending Telegram notification to chat_id: {}",
            telegram_config.chat_id
        );

        let notification_id = resolve_notification_id(&notification);
        let start = std::time::Instant::now();
        let result = self
            .telegram_client
            .send_message(
                &telegram_config.bot_token,
                &telegram_config.chat_id,
                &telegram_message,
                Some("Markdown"),
            )
            .await;
        let duration_ms = start.elapsed().as_millis() as u64;

        // Track delivery status and publish to DuckLake
        let mut redis = self.redis_client.lock().await;
        let (delivery_status, error_message, http_status_code) = match result {
            Ok(_) => {
                info!(
                    "Successfully sent Telegram notification for alert: {}",
                    notification.alert_id
                );
                redis
                    .record_delivery_success(&notification.user_id, &notification_id)
                    .await?;
                ("DELIVERED".to_string(), None, Some(200))
            }
            Err(e) => {
                error!(
                    "Failed to send Telegram notification for alert {}: {}",
                    notification.alert_id, e
                );
                redis
                    .record_delivery_failure(
                        &notification.user_id,
                        &notification_id,
                        &e.to_string(),
                    )
                    .await?;
                let error_msg = e.to_string();
                ("FAILED".to_string(), Some(error_msg), None)
            }
        };
        drop(redis);

        // Create and publish delivery event to DuckLake
        let delivery_event = Self::create_delivery_event(
            &notification,
            &notification_id,
            &telegram_config,
            delivery_status,
            error_message,
            http_status_code,
            duration_ms,
        );

        let ducklake_payload =
            serde_json::to_vec(&delivery_event).context("Failed to serialize delivery event")?;

        self.nats_client
            .publish(NOTIFICATION_DUCKLAKE_SUBJECT, ducklake_payload.into())
            .await
            .context("Failed to publish delivery event to DuckLake")?;

        debug!(
            "Published Telegram delivery event to DuckLake for notification {}",
            notification_id
        );

        Ok(())
    }

    /// Create delivery event for DuckLake analytics
    fn create_delivery_event(
        notification: &NatsNotification,
        notification_id: &str,
        telegram_config: &crate::types::TelegramChannelConfig,
        delivery_status: String,
        error_message: Option<String>,
        http_status_code: Option<i32>,
        duration_ms: u64,
    ) -> DeliveryEvent {
        let now = Utc::now();
        let now_micros = now.timestamp_micros();

        // Determine error type from error message
        let error_type = error_message.as_ref().and_then(|err| {
            let err_lower = err.to_lowercase();
            if err_lower.contains("timeout") {
                Some("TIMEOUT".to_string())
            } else if err_lower.contains("network") || err_lower.contains("connection") {
                Some("NETWORK".to_string())
            } else if err_lower.contains("auth")
                || err_lower.contains("unauthorized")
                || err_lower.contains("forbidden")
            {
                Some("AUTH".to_string())
            } else if err_lower.contains("rate") || err_lower.contains("429") {
                Some("RATE_LIMIT".to_string())
            } else {
                Some("UNKNOWN".to_string())
            }
        });

        // Calculate shard (simple hash-based sharding)
        let shard = (notification_id.len() % 16) as i32;

        // Determine severity from priority
        let severity = match notification.priority {
            NotificationPriority::Low => "INFO",
            NotificationPriority::Normal => "WARNING",
            NotificationPriority::High => "WARNING",
            NotificationPriority::Critical => "CRITICAL",
        };

        // Calculate message size
        let message_size = notification.message.len() as i32;

        // Completed_at is now if delivered, None if failed
        let completed_at = if delivery_status == "DELIVERED" {
            Some(now_micros)
        } else {
            None
        };

        // Telegram Bot API endpoint
        let endpoint_url = format!(
            "https://api.telegram.org/bot{}/sendMessage",
            telegram_config.bot_token
        );

        DeliveryEvent {
            // Partition columns
            delivery_date: now.format("%Y-%m-%d").to_string(),
            channel_type: "telegram".to_string(),
            shard,

            // Primary identifiers
            notification_id: notification_id.to_string(),
            channel_id: telegram_config.user_id.clone(),
            endpoint_url: Some(endpoint_url),

            // Delivery attempt tracking
            attempt_number: 1, // Telegram provider doesn't retry yet
            max_attempts: 1,
            delivery_status,

            // Timing metrics
            started_at: now_micros - (duration_ms * 1000) as i64,
            completed_at,
            response_time_ms: Some(duration_ms as i64),

            // Response data
            http_status_code,
            response_body: None, // Telegram API response is not stored
            error_message,
            error_type,

            // Notification content metadata
            alert_id: Some(notification.alert_id.clone()),
            transaction_hash: notification.transaction_hash.clone(),
            severity: Some(severity.to_string()),
            message_size_bytes: Some(message_size),

            // Retry and fallback tracking
            used_fallback: false, // Telegram provider doesn't have fallback yet
            fallback_url: None,
            retry_delay_ms: None,

            // Provider metadata
            provider_id: Some("telegram-notification-provider".to_string()),
            provider_version: Some(env!("CARGO_PKG_VERSION").to_string()),

            // Processing metadata
            ingested_at: now_micros,
        }
    }
}

fn resolve_notification_id(notification: &NatsNotification) -> String {
    notification
        .notification_id
        .clone()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| Uuid::new_v4().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn subscribes_to_prd_aligned_subject() {
        assert_eq!(
            TELEGRAM_NOTIFICATION_SUBJECT,
            "notifications.send.immediate.telegram"
        );
    }

    #[test]
    fn test_nats_handler_creation() {
        // Basic smoke test for module compilation.
        assert!(true);
    }

    #[test]
    fn resolves_notification_id_from_payload() {
        let notification = NatsNotification {
            notification_id: Some("notif-123".to_string()),
            user_id: "user1".to_string(),
            alert_id: "alert1".to_string(),
            alert_name: "alert".to_string(),
            priority: NotificationPriority::Normal,
            message: "msg".to_string(),
            chain: "ethereum.mainnet".to_string(),
            transaction_hash: None,
            wallet_address: None,
            block_number: None,
            timestamp: "2026-01-01T00:00:00Z".to_string(),
        };

        assert_eq!(resolve_notification_id(&notification), "notif-123");
    }
}
