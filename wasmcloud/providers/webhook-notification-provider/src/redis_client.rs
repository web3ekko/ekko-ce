use anyhow::{Context, Result};
use redis::aio::ConnectionManager;
use redis::AsyncCommands;
use tracing::{debug, error, info};

use crate::types::{HealthMetrics, WebhookConfig};

/// Redis client for webhook configuration and metrics
pub struct RedisClient {
    conn: ConnectionManager,
}

impl RedisClient {
    /// Create new Redis client
    pub async fn new(redis_url: &str) -> Result<Self> {
        let client = redis::Client::open(redis_url).context("Failed to create Redis client")?;

        let conn = ConnectionManager::new(client)
            .await
            .context("Failed to connect to Redis")?;

        info!("Connected to Redis at {}", redis_url);

        Ok(Self { conn })
    }

    /// Get webhook configuration for a user
    pub async fn get_webhook_config(&mut self, user_id: &str) -> Result<Option<WebhookConfig>> {
        let key = format!("webhook:config:{}", user_id);

        match self.conn.get::<_, Option<String>>(&key).await {
            Ok(Some(data)) => {
                let config: WebhookConfig =
                    serde_json::from_str(&data).context("Failed to parse webhook config")?;

                debug!("Retrieved webhook config for user {}", user_id);
                Ok(Some(config))
            }
            Ok(None) => {
                debug!("No webhook config found for user {}", user_id);
                Ok(None)
            }
            Err(e) => {
                error!("Failed to get webhook config for user {}: {}", user_id, e);
                Err(e.into())
            }
        }
    }

    /// Store delivery status in Redis
    pub async fn store_delivery_status(
        &mut self,
        notification_id: &str,
        status: &crate::types::DeliveryStatus,
    ) -> Result<()> {
        let key = format!("webhook:status:{}", notification_id);
        let data = serde_json::to_string(status).context("Failed to serialize delivery status")?;

        self.conn
            .set_ex::<_, _, ()>(&key, data, 86400)
            .await
            .context("Failed to store delivery status")?;

        debug!(
            "Stored delivery status for notification {}",
            notification_id
        );
        Ok(())
    }

    /// Get health metrics for an endpoint
    pub async fn get_health_metrics(&mut self, endpoint_url: &str) -> Result<HealthMetrics> {
        let key = format!("webhook:health:{}", Self::hash_url(endpoint_url));

        match self.conn.get::<_, Option<String>>(&key).await {
            Ok(Some(data)) => {
                let metrics: HealthMetrics =
                    serde_json::from_str(&data).context("Failed to parse health metrics")?;
                Ok(metrics)
            }
            Ok(None) => {
                // Return new metrics if not found
                Ok(HealthMetrics::new(endpoint_url.to_string()))
            }
            Err(e) => {
                error!("Failed to get health metrics for {}: {}", endpoint_url, e);
                Ok(HealthMetrics::new(endpoint_url.to_string()))
            }
        }
    }

    /// Store health metrics for an endpoint
    pub async fn store_health_metrics(&mut self, metrics: &HealthMetrics) -> Result<()> {
        let key = format!("webhook:health:{}", Self::hash_url(&metrics.endpoint_url));
        let data = serde_json::to_string(metrics).context("Failed to serialize health metrics")?;

        // Store for 30 days
        self.conn
            .set_ex::<_, _, ()>(&key, data, 2592000)
            .await
            .context("Failed to store health metrics")?;

        debug!("Stored health metrics for {}", metrics.endpoint_url);
        Ok(())
    }

    /// Increment success counter
    pub async fn increment_success(&mut self, user_id: &str) -> Result<()> {
        let key = format!("webhook:stats:{}:success", user_id);
        self.conn
            .incr::<_, _, ()>(&key, 1)
            .await
            .context("Failed to increment success counter")?;

        // Set expiry of 30 days
        self.conn.expire::<_, ()>(&key, 2592000).await?;

        Ok(())
    }

    /// Increment failure counter
    pub async fn increment_failure(&mut self, user_id: &str) -> Result<()> {
        let key = format!("webhook:stats:{}:failure", user_id);
        self.conn
            .incr::<_, _, ()>(&key, 1)
            .await
            .context("Failed to increment failure counter")?;

        // Set expiry of 30 days
        self.conn.expire::<_, ()>(&key, 2592000).await?;

        Ok(())
    }

    /// Get delivery statistics
    pub async fn get_stats(&mut self, user_id: &str) -> Result<(u64, u64)> {
        let success_key = format!("webhook:stats:{}:success", user_id);
        let failure_key = format!("webhook:stats:{}:failure", user_id);

        let success_count: u64 = self.conn.get(&success_key).await.unwrap_or(0);
        let failure_count: u64 = self.conn.get(&failure_key).await.unwrap_or(0);

        Ok((success_count, failure_count))
    }

    /// Hash URL for use as Redis key
    fn hash_url(url: &str) -> String {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        url.hash(&mut hasher);
        format!("{:x}", hasher.finish())
    }
}
