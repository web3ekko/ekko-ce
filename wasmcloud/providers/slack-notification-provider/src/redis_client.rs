use crate::types::SlackChannelConfig;
use anyhow::{Context, Result};
use redis::aio::MultiplexedConnection;
use redis::{AsyncCommands, Client};
use tracing::{debug, error, info};

/// Redis client for Slack provider
pub struct RedisClient {
    client: Client,
    connection: Option<MultiplexedConnection>,
}

impl RedisClient {
    /// Create new Redis client
    pub fn new(redis_url: &str) -> Result<Self> {
        let client = Client::open(redis_url).context("Failed to create Redis client")?;
        Ok(Self {
            client,
            connection: None,
        })
    }

    /// Connect to Redis
    pub async fn connect(&mut self) -> Result<()> {
        let connection = self
            .client
            .get_multiplexed_async_connection()
            .await
            .context("Failed to connect to Redis")?;

        self.connection = Some(connection);
        info!("Connected to Redis");
        Ok(())
    }

    /// Get connection or panic
    fn conn(&mut self) -> &mut MultiplexedConnection {
        self.connection
            .as_mut()
            .expect("Redis connection not established")
    }

    /// Get Slack channel configuration for a user
    pub async fn get_slack_config(&mut self, user_id: &str) -> Result<Option<SlackChannelConfig>> {
        let key = format!("slack:config:{}", user_id);

        let config_json: Option<String> = self
            .conn()
            .get(&key)
            .await
            .context("Failed to get Slack config from Redis")?;

        match config_json {
            Some(json) => {
                let config: SlackChannelConfig =
                    serde_json::from_str(&json).context("Failed to deserialize Slack config")?;
                debug!("Found Slack config for user {}", user_id);
                Ok(Some(config))
            }
            None => {
                debug!("No Slack config found for user {}", user_id);
                Ok(None)
            }
        }
    }

    /// Check if Slack notifications are enabled for user
    pub async fn is_slack_enabled_for_user(&mut self, user_id: &str) -> Result<bool> {
        match self.get_slack_config(user_id).await? {
            Some(config) => Ok(config.enabled),
            None => Ok(false),
        }
    }

    /// Record successful delivery
    pub async fn record_delivery_success(
        &mut self,
        user_id: &str,
        notification_id: &str,
    ) -> Result<()> {
        let key = format!("slack:delivery:{}:{}", user_id, notification_id);
        let timestamp = chrono::Utc::now().to_rfc3339();

        self.conn()
            .set_ex::<_, _, ()>(&key, &timestamp, 86400) // Expire after 24 hours
            .await
            .context("Failed to record delivery success")?;

        // Increment success counter
        let counter_key = format!("slack:stats:{}:success", user_id);
        self.conn().incr::<_, _, ()>(&counter_key, 1).await.ok(); // Don't fail on stats update

        debug!("Recorded successful delivery for user {}", user_id);
        Ok(())
    }

    /// Record failed delivery
    pub async fn record_delivery_failure(
        &mut self,
        user_id: &str,
        notification_id: &str,
        error_message: &str,
    ) -> Result<()> {
        let key = format!("slack:failure:{}:{}", user_id, notification_id);
        let data = serde_json::json!({
            "error": error_message,
            "timestamp": chrono::Utc::now().to_rfc3339()
        });

        self.conn()
            .set_ex::<_, _, ()>(&key, data.to_string(), 86400) // Expire after 24 hours
            .await
            .context("Failed to record delivery failure")?;

        // Increment failure counter
        let counter_key = format!("slack:stats:{}:failure", user_id);
        self.conn().incr::<_, _, ()>(&counter_key, 1).await.ok(); // Don't fail on stats update

        error!(
            "Recorded failed delivery for user {}: {}",
            user_id, error_message
        );
        Ok(())
    }

    /// Get delivery statistics for user
    pub async fn get_delivery_stats(&mut self, user_id: &str) -> Result<(u64, u64)> {
        let success_key = format!("slack:stats:{}:success", user_id);
        let failure_key = format!("slack:stats:{}:failure", user_id);

        let success: u64 = self.conn().get(&success_key).await.unwrap_or(0);
        let failure: u64 = self.conn().get(&failure_key).await.unwrap_or(0);

        Ok((success, failure))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_redis_client_creation() {
        let client = RedisClient::new("redis://localhost:6379");
        assert!(client.is_ok());
    }
}
