use anyhow::{Context, Result};
use async_nats::{Client, Message, Subscriber};
use chrono::Utc;
use futures_util::StreamExt;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};

use crate::redis_client::RedisClient;
use crate::types::{DeliveryEvent, DeliveryResult, WebhookNotificationRequest};
use crate::webhook_client::WebhookClient;

const NOTIFICATION_DUCKLAKE_SUBJECT: &str = "ducklake.notification_deliveries.ekko.default.write";

/// NATS message handler for webhook notifications
pub struct NatsHandler {
    nats_client: Client,
    redis_client: Arc<RwLock<RedisClient>>,
    webhook_client: Arc<WebhookClient>,
}

impl NatsHandler {
    /// Create new NATS handler
    pub fn new(
        nats_client: Client,
        redis_client: Arc<RwLock<RedisClient>>,
        webhook_client: Arc<WebhookClient>,
    ) -> Self {
        Self {
            nats_client,
            redis_client,
            webhook_client,
        }
    }

    /// Start listening for webhook notification requests
    pub async fn start(&self, subject: &str) -> Result<()> {
        info!("Starting NATS handler for subject: {}", subject);

        let subscriber = self
            .nats_client
            .subscribe(subject.to_string())
            .await
            .context("Failed to subscribe to NATS subject")?;

        info!("Successfully subscribed to {}", subject);

        self.process_notifications(subscriber).await
    }

    /// Process incoming notification messages
    async fn process_notifications(&self, mut subscriber: Subscriber) -> Result<()> {
        while let Some(message) = subscriber.next().await {
            let nats_client = self.nats_client.clone();
            let redis_client = self.redis_client.clone();
            let webhook_client = self.webhook_client.clone();

            // Spawn async task for each notification
            tokio::spawn(async move {
                if let Err(e) =
                    Self::handle_notification(message, nats_client, redis_client, webhook_client)
                        .await
                {
                    error!("Error handling notification: {}", e);
                }
            });
        }

        Ok(())
    }

    /// Handle individual notification
    async fn handle_notification(
        message: Message,
        nats_client: Client,
        redis_client: Arc<RwLock<RedisClient>>,
        webhook_client: Arc<WebhookClient>,
    ) -> Result<()> {
        // Parse notification request
        let request: WebhookNotificationRequest = serde_json::from_slice(&message.payload)
            .context("Failed to parse notification request")?;

        debug!(
            "Processing webhook notification {} for user {}",
            request.notification_id, request.user_id
        );

        // Get webhook configuration from Redis
        let config = {
            let mut redis = redis_client.write().await;
            redis.get_webhook_config(&request.user_id).await?
        };

        let Some(config) = config else {
            warn!(
                "No webhook configuration found for user {}",
                request.user_id
            );
            return Ok(());
        };

        // Check if webhook is enabled
        if !config.enabled {
            debug!("Webhook disabled for user {}", request.user_id);
            return Ok(());
        }

        // Get current health metrics for primary endpoint
        let mut health_metrics = {
            let mut redis = redis_client.write().await;
            redis.get_health_metrics(&config.webhook_url).await?
        };

        // Skip if endpoint is unhealthy and no fallback
        if !health_metrics.is_healthy && config.fallback_url.is_none() {
            warn!(
                "Skipping unhealthy endpoint {} (no fallback)",
                config.webhook_url
            );
            return Ok(());
        }

        // Send webhook with retry logic
        let start = std::time::Instant::now();
        let delivery_status = webhook_client.send_notification(&config, &request).await?;
        let duration_ms = start.elapsed().as_millis() as u64;

        // Update health metrics based on delivery result
        let timestamp = Utc::now().timestamp();
        match delivery_status.status {
            DeliveryResult::Delivered => {
                health_metrics.record_success(duration_ms, timestamp);

                // Increment success counter
                let mut redis = redis_client.write().await;
                redis.increment_success(&request.user_id).await?;
            }
            DeliveryResult::Failed => {
                let error = delivery_status.last_error.clone().unwrap_or_default();
                health_metrics.record_failure(error, timestamp);

                // Increment failure counter
                let mut redis = redis_client.write().await;
                redis.increment_failure(&request.user_id).await?;
            }
            _ => {}
        }

        // Store updated health metrics
        {
            let mut redis = redis_client.write().await;
            redis.store_health_metrics(&health_metrics).await?;
        }

        // Store delivery status
        {
            let mut redis = redis_client.write().await;
            redis
                .store_delivery_status(&request.notification_id, &delivery_status)
                .await?;
        }

        // Publish status update to NATS
        let status_subject = format!("notifications.status.webhook.{}", request.notification_id);
        let status_payload =
            serde_json::to_vec(&delivery_status).context("Failed to serialize delivery status")?;

        nats_client
            .publish(status_subject, status_payload.into())
            .await
            .context("Failed to publish status update")?;

        // Publish delivery event to DuckLake for analytics
        let delivery_event = Self::create_delivery_event(
            &request,
            &config.user_id,
            &config.webhook_url,
            &config.fallback_url,
            &delivery_status,
            duration_ms,
        );

        let ducklake_payload =
            serde_json::to_vec(&delivery_event).context("Failed to serialize delivery event")?;

        nats_client
            .publish(NOTIFICATION_DUCKLAKE_SUBJECT, ducklake_payload.into())
            .await
            .context("Failed to publish delivery event to DuckLake")?;

        debug!(
            "Published delivery event to DuckLake for notification {}",
            request.notification_id
        );

        info!(
            "Webhook notification {} processed: {:?}",
            request.notification_id, delivery_status.status
        );

        Ok(())
    }

    /// Create delivery event for DuckLake analytics
    fn create_delivery_event(
        request: &WebhookNotificationRequest,
        channel_id: &str,
        endpoint_url: &str,
        fallback_url: &Option<String>,
        delivery_status: &crate::types::DeliveryStatus,
        duration_ms: u64,
    ) -> DeliveryEvent {
        let now = Utc::now();
        let now_micros = now.timestamp_micros();

        // Determine error type from error message
        let error_type = delivery_status.last_error.as_ref().and_then(|err| {
            let err_lower = err.to_lowercase();
            if err_lower.contains("timeout") {
                Some("TIMEOUT".to_string())
            } else if err_lower.contains("network") || err_lower.contains("connection") {
                Some("NETWORK".to_string())
            } else if err_lower.contains("auth") || err_lower.contains("unauthorized") {
                Some("AUTH".to_string())
            } else if err_lower.contains("rate") || err_lower.contains("429") {
                Some("RATE_LIMIT".to_string())
            } else {
                Some("UNKNOWN".to_string())
            }
        });

        // Calculate shard (simple hash-based sharding)
        let shard = (request.notification_id.len() % 16) as i32;

        // Determine severity from priority
        let severity = match request.priority {
            crate::types::AlertPriority::Low => "INFO",
            crate::types::AlertPriority::Normal => "WARNING",
            crate::types::AlertPriority::High => "WARNING",
            crate::types::AlertPriority::Critical => "CRITICAL",
        };

        // Truncate response body to 1KB
        let response_body = delivery_status.response_body.as_ref().map(|body| {
            if body.len() > 1024 {
                format!("{}... [truncated]", &body[..1024])
            } else {
                body.clone()
            }
        });

        // Calculate message size
        let message_size = serde_json::to_string(&request.payload)
            .map(|s| s.len() as i32)
            .ok();

        DeliveryEvent {
            // Partition columns
            delivery_date: now.format("%Y-%m-%d").to_string(),
            channel_type: "webhook".to_string(),
            shard,

            // Primary identifiers
            notification_id: request.notification_id.clone(),
            channel_id: channel_id.to_string(),
            endpoint_url: Some(endpoint_url.to_string()),

            // Delivery attempt tracking
            attempt_number: delivery_status.attempts as i32,
            max_attempts: 3, // From RetryConfig default
            delivery_status: format!("{:?}", delivery_status.status).to_uppercase(),

            // Timing metrics
            started_at: now_micros - (duration_ms * 1000) as i64,
            completed_at: delivery_status.delivered_at.map(|ts| ts * 1_000_000),
            response_time_ms: Some(duration_ms as i64),

            // Response data
            http_status_code: delivery_status.response_code.map(|c| c as i32),
            response_body,
            error_message: delivery_status.last_error.clone(),
            error_type,

            // Notification content metadata
            alert_id: Some(request.alert_id.clone()),
            transaction_hash: None, // Extract from payload if available
            severity: Some(severity.to_string()),
            message_size_bytes: message_size,

            // Retry and fallback tracking
            used_fallback: delivery_status
                .last_error
                .as_ref()
                .map(|e| e.contains("fallback"))
                .unwrap_or(false),
            fallback_url: fallback_url.clone(),
            retry_delay_ms: None, // Could be extracted from retry logic if needed

            // Provider metadata
            provider_id: Some("webhook-notification-provider".to_string()),
            provider_version: Some(env!("CARGO_PKG_VERSION").to_string()),

            // Processing metadata
            ingested_at: now_micros,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ducklake_subject_is_expected() {
        assert_eq!(
            NOTIFICATION_DUCKLAKE_SUBJECT,
            "ducklake.notification_deliveries.ekko.default.write"
        );
    }
}
