use crate::types::TelegramChannelConfig;
use anyhow::{Context, Result};
use redis::aio::Connection;
use redis::{AsyncCommands, Client};
use tracing::{debug, error, info};

/// Redis client for Telegram configuration and stats
pub struct RedisClient {
    client: Client,
}

impl RedisClient {
    pub fn new(redis_url: &str) -> Result<Self> {
        let client = Client::open(redis_url).context("Failed to create Redis client")?;
        Ok(Self { client })
    }

    async fn conn(&self) -> Result<Connection> {
        self.client
            .get_async_connection()
            .await
            .context("Failed to get Redis connection")
    }

    /// Get Telegram configuration for a user
    pub async fn get_telegram_config(
        &mut self,
        user_id: &str,
    ) -> Result<Option<TelegramChannelConfig>> {
        let key = format!("telegram:config:{}", user_id);
        let config_json: Option<String> = self.conn().await?.get(&key).await?;

        match config_json {
            Some(json) => {
                let config: TelegramChannelConfig =
                    serde_json::from_str(&json).context("Failed to deserialize Telegram config")?;
                debug!("Retrieved Telegram config for user {}", user_id);
                Ok(Some(config))
            }
            None => {
                debug!("No Telegram config found for user {}", user_id);
                Ok(None)
            }
        }
    }

    /// Check if Telegram is enabled for a user
    pub async fn is_telegram_enabled_for_user(&mut self, user_id: &str) -> Result<bool> {
        match self.get_telegram_config(user_id).await? {
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
        let success_key = format!("telegram:stats:{}:success", user_id);
        let mut conn = self.conn().await?;

        // Increment success counter
        conn.incr::<_, _, ()>(&success_key, 1).await?;

        // Set expiry to 30 days
        conn.expire::<_, ()>(&success_key, 2592000).await?;

        info!(
            "Recorded Telegram delivery success for user {} (notification {})",
            user_id, notification_id
        );

        Ok(())
    }

    /// Record failed delivery
    pub async fn record_delivery_failure(
        &mut self,
        user_id: &str,
        notification_id: &str,
        error_message: &str,
    ) -> Result<()> {
        let failure_key = format!("telegram:stats:{}:failure", user_id);
        let mut conn = self.conn().await?;

        // Increment failure counter
        conn.incr::<_, _, ()>(&failure_key, 1).await?;

        // Set expiry to 30 days
        conn.expire::<_, ()>(&failure_key, 2592000).await?;

        error!(
            "Recorded Telegram delivery failure for user {} (notification {}): {}",
            user_id, notification_id, error_message
        );

        Ok(())
    }

    /// Store verification code for Telegram channel
    pub async fn store_verification_code(
        &mut self,
        user_id: &str,
        chat_id: &str,
        code: &str,
    ) -> Result<()> {
        let key = format!("telegram:verification:{}:{}", user_id, chat_id);
        let mut conn = self.conn().await?;

        // Store code with 15 minute expiry
        conn.set_ex::<_, _, ()>(&key, code, 900).await?;

        info!(
            "Stored Telegram verification code for user {} (chat_id: {})",
            user_id, chat_id
        );

        Ok(())
    }

    /// Get verification code for Telegram channel
    pub async fn get_verification_code(
        &mut self,
        user_id: &str,
        chat_id: &str,
    ) -> Result<Option<String>> {
        let key = format!("telegram:verification:{}:{}", user_id, chat_id);
        let code: Option<String> = self.conn().await?.get(&key).await?;

        if code.is_some() {
            debug!(
                "Retrieved Telegram verification code for user {} (chat_id: {})",
                user_id, chat_id
            );
        }

        Ok(code)
    }

    /// Delete verification code after successful verification
    pub async fn delete_verification_code(&mut self, user_id: &str, chat_id: &str) -> Result<()> {
        let key = format!("telegram:verification:{}:{}", user_id, chat_id);
        self.conn().await?.del::<_, ()>(&key).await?;

        info!(
            "Deleted Telegram verification code for user {} (chat_id: {})",
            user_id, chat_id
        );

        Ok(())
    }

    /// Store chat_id mapping for username
    pub async fn store_chat_mapping(&mut self, username: &str, chat_id: i64) -> Result<()> {
        let key = format!("telegram:chat:username:{}", username);
        let mut conn = self.conn().await?;

        // Store mapping with 30 day expiry
        conn.set_ex::<_, _, ()>(&key, chat_id, 2592000).await?;

        info!("Stored Telegram chat mapping: {} -> {}", username, chat_id);

        Ok(())
    }

    /// Get chat_id for username
    pub async fn get_chat_id_for_username(&mut self, username: &str) -> Result<Option<i64>> {
        let key = format!("telegram:chat:username:{}", username);
        let chat_id: Option<i64> = self.conn().await?.get(&key).await?;

        if let Some(id) = chat_id {
            debug!("Retrieved chat_id {} for username {}", id, username);
        }

        Ok(chat_id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_redis_client_creation() {
        let result = RedisClient::new("redis://localhost:6379");
        assert!(result.is_ok());
    }
}
