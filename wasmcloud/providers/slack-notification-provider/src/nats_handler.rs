use crate::formatter::format_slack_message;
use crate::redis_client::RedisClient;
use crate::slack_client::SlackClient;
use crate::types::{DeliveryEvent, NatsNotification, NotificationPriority};
use anyhow::{Context, Result};
use async_nats::{Client, Message, Subscriber};
use chrono::Utc;
use futures_util::StreamExt;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

const NOTIFICATION_DUCKLAKE_SUBJECT: &str = "ducklake.notification_deliveries.ekko.default.write";

/// NATS handler for receiving notifications and sending to Slack
pub struct NatsHandler {
    nats_client: Client,
    slack_client: Arc<SlackClient>,
    redis_client: Arc<Mutex<RedisClient>>,
}

impl NatsHandler {
    pub fn new(
        nats_client: Client,
        slack_client: Arc<SlackClient>,
        redis_client: Arc<Mutex<RedisClient>>,
    ) -> Self {
        Self {
            nats_client,
            slack_client,
            redis_client,
        }
    }

    /// Start subscribing to notifications
    pub async fn start(&self) -> Result<()> {
        let subscriber = self
            .nats_client
            .subscribe("notifications.slack")
            .await
            .context("Failed to subscribe to notifications.slack")?;

        info!("Subscribed to notifications.slack");

        self.process_notifications(subscriber).await
    }

    /// Process incoming notifications from NATS
    async fn process_notifications(&self, mut subscriber: Subscriber) -> Result<()> {
        while let Some(message) = subscriber.next().await {
            if let Err(e) = self.handle_notification(message).await {
                error!("Error handling notification: {}", e);
            }
        }
        Ok(())
    }

    /// Handle a single notification message
    async fn handle_notification(&self, message: Message) -> Result<()> {
        // Parse NATS notification
        let notification: NatsNotification = serde_json::from_slice(&message.payload)
            .context("Failed to deserialize notification")?;

        debug!(
            "Received notification for user {} - alert {}",
            notification.user_id, notification.alert_id
        );

        // Check if Slack is enabled for this user
        let mut redis = self.redis_client.lock().await;
        let slack_enabled = redis
            .is_slack_enabled_for_user(&notification.user_id)
            .await
            .unwrap_or(false);

        if !slack_enabled {
            debug!(
                "Slack notifications disabled for user {}",
                notification.user_id
            );
            return Ok(());
        }

        // Get Slack configuration
        let slack_config = match redis.get_slack_config(&notification.user_id).await? {
            Some(config) => config,
            None => {
                warn!(
                    "No Slack config found for user {} despite enabled flag",
                    notification.user_id
                );
                return Ok(());
            }
        };

        drop(redis); // Release lock before making HTTP call

        // Format message with Slack Block Kit
        let slack_message = format_slack_message(&notification);

        // Send to Slack
        let notification_id = resolve_notification_id(&notification);
        let start = std::time::Instant::now();
        let result = self
            .slack_client
            .send_message(&slack_config.webhook_url, &slack_message)
            .await;
        let duration_ms = start.elapsed().as_millis() as u64;

        // Record delivery status and publish to DuckLake
        let mut redis = self.redis_client.lock().await;
        let (delivery_status, error_message, http_status_code) = match result {
            Ok(_) => {
                info!(
                    "Successfully sent notification to Slack for user {}",
                    notification.user_id
                );
                redis
                    .record_delivery_success(&notification.user_id, &notification_id)
                    .await?;
                ("DELIVERED".to_string(), None, Some(200))
            }
            Err(e) => {
                error!(
                    "Failed to send notification to Slack for user {}: {}",
                    notification.user_id, e
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
            &slack_config,
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
            "Published Slack delivery event to DuckLake for notification {}",
            notification_id
        );

        Ok(())
    }

    /// Create delivery event for DuckLake analytics
    fn create_delivery_event(
        notification: &NatsNotification,
        notification_id: &str,
        slack_config: &crate::types::SlackChannelConfig,
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
        let message_size = serde_json::to_string(&notification.payload)
            .map(|s| s.len() as i32)
            .ok();

        // Completed_at is now if delivered, None if failed
        let completed_at = if delivery_status == "DELIVERED" {
            Some(now_micros)
        } else {
            None
        };

        DeliveryEvent {
            // Partition columns
            delivery_date: now.format("%Y-%m-%d").to_string(),
            channel_type: "slack".to_string(),
            shard,

            // Primary identifiers
            notification_id: notification_id.to_string(),
            channel_id: slack_config.user_id.clone(),
            endpoint_url: Some(slack_config.webhook_url.clone()),

            // Delivery attempt tracking
            attempt_number: 1, // Slack provider doesn't retry yet
            max_attempts: 1,
            delivery_status,

            // Timing metrics
            started_at: now_micros - (duration_ms * 1000) as i64,
            completed_at,
            response_time_ms: Some(duration_ms as i64),

            // Response data
            http_status_code,
            response_body: None, // Slack doesn't return meaningful response body
            error_message,
            error_type,

            // Notification content metadata
            alert_id: Some(notification.alert_id.clone()),
            transaction_hash: notification.payload.transaction_hash.clone(),
            severity: Some(severity.to_string()),
            message_size_bytes: message_size,

            // Retry and fallback tracking
            used_fallback: false, // Slack provider doesn't have fallback yet
            fallback_url: None,
            retry_delay_ms: None,

            // Provider metadata
            provider_id: Some("slack-notification-provider".to_string()),
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
    use crate::types::{NotificationPayload, NotificationPriority};
    use chrono::Utc;

    #[test]
    fn resolves_notification_id_from_payload() {
        let notification = NatsNotification {
            notification_id: Some("notif-123".to_string()),
            user_id: "user1".to_string(),
            alert_id: "alert1".to_string(),
            alert_name: "alert".to_string(),
            notification_type: "alert".to_string(),
            priority: NotificationPriority::Normal,
            payload: NotificationPayload {
                triggered_value: "1".to_string(),
                threshold: "2".to_string(),
                transaction_hash: None,
                chain: "ethereum.mainnet".to_string(),
                wallet: "0xabc".to_string(),
                block_number: None,
            },
            timestamp: Utc::now(),
        };

        assert_eq!(resolve_notification_id(&notification), "notif-123");
    }

    #[test]
    fn generates_notification_id_when_missing() {
        let notification = NatsNotification {
            notification_id: None,
            user_id: "user1".to_string(),
            alert_id: "alert1".to_string(),
            alert_name: "alert".to_string(),
            notification_type: "alert".to_string(),
            priority: NotificationPriority::Normal,
            payload: NotificationPayload {
                triggered_value: "1".to_string(),
                threshold: "2".to_string(),
                transaction_hash: None,
                chain: "ethereum.mainnet".to_string(),
                wallet: "0xabc".to_string(),
                block_number: None,
            },
            timestamp: Utc::now(),
        };

        let id = resolve_notification_id(&notification);
        assert!(!id.is_empty());
        assert_ne!(id, "notif-123");
    }

    #[test]
    fn test_nats_handler_creation() {
        // Basic smoke test for module compilation.
        assert!(true);
    }
}
