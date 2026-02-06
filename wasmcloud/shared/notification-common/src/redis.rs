//! Redis client for notification settings and caching
//!
//! This module provides a standardized Redis client for accessing user and group
//! notification settings with proper caching and error handling.

use crate::provider::LegacyProviderError as ProviderError;
use crate::{GroupNotificationSettings, UserNotificationSettings};
use redis::{aio::ConnectionManager, AsyncCommands, Client, RedisError};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, error, warn};

/// Redis client wrapper with connection management
#[derive(Clone)]
pub struct RedisClient {
    connection_manager: ConnectionManager,
    default_ttl: u64,
}

impl RedisClient {
    /// Create a new Redis client with connection manager
    pub async fn new(redis_url: &str) -> Result<Self, ProviderError> {
        let client = Client::open(redis_url)
            .map_err(|e| ProviderError::ConfigurationError(format!("Invalid Redis URL: {}", e)))?;

        let connection_manager = ConnectionManager::new(client).await.map_err(|e| {
            ProviderError::ConnectionError(format!("Failed to connect to Redis: {}", e))
        })?;

        Ok(Self {
            connection_manager,
            default_ttl: 3600, // 1 hour default TTL as per PRD
        })
    }

    /// Get user notification settings with fallback to defaults
    pub async fn get_user_settings(
        &self,
        user_id: &str,
    ) -> Result<UserNotificationSettings, ProviderError> {
        let key = format!("user:notifications:{}", user_id);

        debug!("Fetching user notification settings for user: {}", user_id);

        let mut conn = self.connection_manager.clone();

        match conn.get::<_, Option<String>>(&key).await {
            Ok(Some(json_data)) => {
                match serde_json::from_str::<UserNotificationSettings>(&json_data) {
                    Ok(settings) => {
                        debug!("Retrieved user settings from cache for user: {}", user_id);
                        Ok(settings)
                    }
                    Err(e) => {
                        error!(
                            "Failed to deserialize user settings for user {}: {}",
                            user_id, e
                        );
                        // Return default settings if deserialization fails
                        Ok(Self::create_default_user_settings(user_id))
                    }
                }
            }
            Ok(None) => {
                debug!(
                    "No cached settings found for user: {}, returning defaults",
                    user_id
                );
                Ok(Self::create_default_user_settings(user_id))
            }
            Err(e) => {
                error!(
                    "Redis error fetching user settings for user {}: {}",
                    user_id, e
                );
                // Return defaults on Redis error to maintain service availability
                Ok(Self::create_default_user_settings(user_id))
            }
        }
    }

    /// Cache user notification settings
    pub async fn cache_user_settings(
        &self,
        settings: &UserNotificationSettings,
    ) -> Result<(), ProviderError> {
        let key = format!("user:notifications:{}", settings.user_id);

        debug!(
            "Caching user notification settings for user: {}",
            settings.user_id
        );

        let json_data =
            serde_json::to_string(settings).map_err(|e| ProviderError::SerializationError(e))?;

        let mut conn = self.connection_manager.clone();

        conn.set_ex::<_, _, ()>(&key, json_data, self.default_ttl)
            .await
            .map_err(|e| {
                error!(
                    "Failed to cache user settings for user {}: {}",
                    settings.user_id, e
                );
                ProviderError::RedisError(e)
            })?;

        debug!(
            "Cached user settings for user: {} with TTL: {}s",
            settings.user_id, self.default_ttl
        );
        Ok(())
    }

    /// Invalidate user settings cache
    pub async fn invalidate_user_cache(&self, user_id: &str) -> Result<(), ProviderError> {
        let key = format!("user:notifications:{}", user_id);

        debug!("Invalidating user notification cache for user: {}", user_id);

        let mut conn = self.connection_manager.clone();

        let deleted: u32 = conn.del(&key).await.map_err(|e| {
            error!(
                "Failed to invalidate user cache for user {}: {}",
                user_id, e
            );
            ProviderError::RedisError(e)
        })?;

        if deleted > 0 {
            debug!("Invalidated cache for user: {}", user_id);
        } else {
            debug!("No cache entry found to invalidate for user: {}", user_id);
        }

        Ok(())
    }

    /// Get group notification settings
    pub async fn get_group_settings(
        &self,
        group_id: &str,
    ) -> Result<GroupNotificationSettings, ProviderError> {
        let key = format!("group:notifications:{}", group_id);

        debug!(
            "Fetching group notification settings for group: {}",
            group_id
        );

        let mut conn = self.connection_manager.clone();

        match conn.get::<_, Option<String>>(&key).await {
            Ok(Some(json_data)) => {
                match serde_json::from_str::<GroupNotificationSettings>(&json_data) {
                    Ok(settings) => {
                        debug!(
                            "Retrieved group settings from cache for group: {}",
                            group_id
                        );
                        Ok(settings)
                    }
                    Err(e) => {
                        error!(
                            "Failed to deserialize group settings for group {}: {}",
                            group_id, e
                        );
                        Ok(Self::create_default_group_settings(group_id))
                    }
                }
            }
            Ok(None) => {
                debug!(
                    "No cached settings found for group: {}, returning defaults",
                    group_id
                );
                Ok(Self::create_default_group_settings(group_id))
            }
            Err(e) => {
                error!(
                    "Redis error fetching group settings for group {}: {}",
                    group_id, e
                );
                Ok(Self::create_default_group_settings(group_id))
            }
        }
    }

    /// Cache group notification settings
    pub async fn cache_group_settings(
        &self,
        settings: &GroupNotificationSettings,
    ) -> Result<(), ProviderError> {
        let key = format!("group:notifications:{}", settings.group_id);

        debug!(
            "Caching group notification settings for group: {}",
            settings.group_id
        );

        let json_data =
            serde_json::to_string(settings).map_err(|e| ProviderError::SerializationError(e))?;

        let mut conn = self.connection_manager.clone();

        conn.set_ex::<_, _, ()>(&key, json_data, self.default_ttl)
            .await
            .map_err(|e| {
                error!(
                    "Failed to cache group settings for group {}: {}",
                    settings.group_id, e
                );
                ProviderError::RedisError(e)
            })?;

        debug!(
            "Cached group settings for group: {} with TTL: {}s",
            settings.group_id, self.default_ttl
        );
        Ok(())
    }

    /// Invalidate group settings cache
    pub async fn invalidate_group_cache(&self, group_id: &str) -> Result<(), ProviderError> {
        let key = format!("group:notifications:{}", group_id);

        debug!(
            "Invalidating group notification cache for group: {}",
            group_id
        );

        let mut conn = self.connection_manager.clone();

        let deleted: u32 = conn.del(&key).await.map_err(|e| {
            error!(
                "Failed to invalidate group cache for group {}: {}",
                group_id, e
            );
            ProviderError::RedisError(e)
        })?;

        if deleted > 0 {
            debug!("Invalidated cache for group: {}", group_id);
        } else {
            debug!("No cache entry found to invalidate for group: {}", group_id);
        }

        Ok(())
    }

    /// Store delivery status for tracking
    pub async fn store_delivery_status(
        &self,
        user_id: &str,
        notification_id: &str,
        status: &crate::DeliveryStatus,
    ) -> Result<(), ProviderError> {
        let key = format!("delivery:{}:{}", user_id, notification_id);

        debug!(
            "Storing delivery status for notification: {}",
            notification_id
        );

        let json_data =
            serde_json::to_string(status).map_err(|e| ProviderError::SerializationError(e))?;

        let mut conn = self.connection_manager.clone();

        // Store with shorter TTL for delivery tracking
        conn.set_ex::<_, _, ()>(&key, json_data, 86400) // 24 hours
            .await
            .map_err(|e| {
                error!(
                    "Failed to store delivery status for notification {}: {}",
                    notification_id, e
                );
                ProviderError::RedisError(e)
            })?;

        Ok(())
    }

    /// Get delivery status
    pub async fn get_delivery_status(
        &self,
        user_id: &str,
        notification_id: &str,
    ) -> Result<Option<crate::DeliveryStatus>, ProviderError> {
        let key = format!("delivery:{}:{}", user_id, notification_id);

        debug!(
            "Retrieving delivery status for notification: {}",
            notification_id
        );

        let mut conn = self.connection_manager.clone();

        match conn.get::<_, Option<String>>(&key).await {
            Ok(Some(json_data)) => {
                match serde_json::from_str::<crate::DeliveryStatus>(&json_data) {
                    Ok(status) => Ok(Some(status)),
                    Err(e) => {
                        error!(
                            "Failed to deserialize delivery status for notification {}: {}",
                            notification_id, e
                        );
                        Ok(None)
                    }
                }
            }
            Ok(None) => Ok(None),
            Err(e) => {
                error!(
                    "Redis error fetching delivery status for notification {}: {}",
                    notification_id, e
                );
                Err(ProviderError::RedisError(e))
            }
        }
    }

    /// Get wallet nicknames for a user from Redis HASH
    ///
    /// Fetches the PERSISTENT Redis HASH at `user:wallet_names:{user_id}` containing
    /// mappings of "address:chain_id" to custom nickname.
    ///
    /// # Arguments
    /// * `user_id` - User ID to fetch nicknames for
    ///
    /// # Returns
    /// HashMap with keys in format "{address}:{chain_id}" and values as custom nicknames.
    /// Returns empty HashMap if no nicknames are cached or on error.
    ///
    /// # Example
    /// ```rust,no_run
    /// use notification_common::RedisClient;
    ///
    /// # async fn example() -> Result<(), Box<dyn std::error::Error>> {
    /// let client = RedisClient::new("redis://127.0.0.1:6379").await?;
    /// let nicknames = client.get_wallet_nicknames("user123").await?;
    /// // nicknames = {"0x1234...abcd:1": "My Trading Wallet", ...}
    /// # Ok(()) }
    /// ```
    pub async fn get_wallet_nicknames(
        &self,
        user_id: &str,
    ) -> Result<std::collections::HashMap<String, String>, ProviderError> {
        let key = format!("user:wallet_names:{}", user_id);

        debug!("Fetching wallet nicknames for user: {}", user_id);

        let mut conn = self.connection_manager.clone();

        match conn
            .hgetall::<_, std::collections::HashMap<String, String>>(&key)
            .await
        {
            Ok(nicknames) => {
                if nicknames.is_empty() {
                    debug!("No wallet nicknames found for user: {}", user_id);
                } else {
                    debug!(
                        "Retrieved {} wallet nicknames for user: {}",
                        nicknames.len(),
                        user_id
                    );
                }
                Ok(nicknames)
            }
            Err(e) => {
                error!(
                    "Redis error fetching wallet nicknames for user {}: {}",
                    user_id, e
                );
                // Return empty HashMap on error to maintain service availability
                warn!("Returning empty wallet nicknames due to Redis error");
                Ok(std::collections::HashMap::new())
            }
        }
    }

    /// Get all subscribers for an alert template from Redis SET
    ///
    /// Fetches the PERSISTENT Redis SET at `template:subscribers:{template_id}` containing
    /// all user IDs that have subscribed to this alert template.
    ///
    /// # Arguments
    /// * `template_id` - Alert template ID to fetch subscribers for
    ///
    /// # Returns
    /// Vec of user IDs subscribed to this template.
    /// Returns empty Vec if no subscribers are found or on error.
    ///
    /// # Example
    /// ```rust,no_run
    /// use notification_common::RedisClient;
    ///
    /// # async fn example() -> Result<(), Box<dyn std::error::Error>> {
    /// let client = RedisClient::new("redis://127.0.0.1:6379").await?;
    /// let subscribers = client.get_template_subscribers("template123").await?;
    /// // subscribers = ["user1", "user2", "user3"]
    /// # Ok(()) }
    /// ```
    pub async fn get_template_subscribers(
        &self,
        template_id: &str,
    ) -> Result<Vec<String>, ProviderError> {
        let key = format!("template:subscribers:{}", template_id);

        debug!("Fetching subscribers for template: {}", template_id);

        let mut conn = self.connection_manager.clone();

        match conn.smembers::<_, Vec<String>>(&key).await {
            Ok(subscriber_ids) => {
                if subscriber_ids.is_empty() {
                    debug!("No subscribers found for template: {}", template_id);
                } else {
                    debug!(
                        "Retrieved {} subscribers for template: {}",
                        subscriber_ids.len(),
                        template_id
                    );
                }
                Ok(subscriber_ids)
            }
            Err(e) => {
                error!(
                    "Redis error fetching subscribers for template {}: {}",
                    template_id, e
                );
                // Return empty Vec on error to maintain service availability
                warn!("Returning empty subscriber list due to Redis error");
                Ok(Vec::new())
            }
        }
    }

    /// Check if Redis connection is healthy
    pub async fn health_check(&self) -> Result<(), ProviderError> {
        let mut conn = self.connection_manager.clone();

        // Use the info command as a health check since ping isn't available
        match redis::cmd("PING").query_async::<_, String>(&mut conn).await {
            Ok(_) => {
                debug!("Redis health check passed");
                Ok(())
            }
            Err(e) => {
                error!("Redis health check failed: {}", e);
                Err(ProviderError::ConnectionError(format!(
                    "Redis health check failed: {}",
                    e
                )))
            }
        }
    }

    /// Set custom TTL for caching operations
    pub fn with_ttl(mut self, ttl_seconds: u64) -> Self {
        self.default_ttl = ttl_seconds;
        self
    }

    /// Create default user settings with WebSocket enabled (per PRD requirements)
    fn create_default_user_settings(user_id: &str) -> UserNotificationSettings {
        let mut settings = UserNotificationSettings::default();
        settings.user_id = user_id.to_string();
        settings.websocket_enabled = true; // Default enabled as per PRD
        settings.notifications_enabled = true;

        // Add default WebSocket channel settings
        let websocket_config = crate::ChannelSettings {
            enabled: true,
            config: std::collections::HashMap::new(),
        };
        settings
            .channels
            .insert("websocket".to_string(), websocket_config);

        debug!(
            "Created default user settings for user: {} with WebSocket enabled",
            user_id
        );
        settings
    }

    /// Create default group settings
    fn create_default_group_settings(group_id: &str) -> GroupNotificationSettings {
        GroupNotificationSettings {
            group_id: group_id.to_string(),
            group_name: format!("Group {}", group_id),
            mandatory_channels: vec![crate::NotificationChannel::WebSocket],
            escalation_rules: std::collections::HashMap::new(),
            shared_channels: std::collections::HashMap::new(),
            member_overrides_allowed: true,
            cached_at: chrono::Utc::now(),
        }
    }
}

/// Connection pool for high-throughput scenarios
pub struct RedisConnectionPool {
    pool: bb8::Pool<bb8_redis::RedisConnectionManager>,
}

impl RedisConnectionPool {
    pub async fn new(redis_url: &str, max_connections: u32) -> Result<Self, ProviderError> {
        let manager = bb8_redis::RedisConnectionManager::new(redis_url)
            .map_err(|e| ProviderError::ConfigurationError(format!("Invalid Redis URL: {}", e)))?;

        let pool = bb8::Pool::builder()
            .max_size(max_connections)
            .build(manager)
            .await
            .map_err(|e| {
                ProviderError::ConnectionError(format!("Failed to create Redis pool: {}", e))
            })?;

        Ok(Self { pool })
    }

    pub async fn get_connection(
        &self,
    ) -> Result<bb8::PooledConnection<'_, bb8_redis::RedisConnectionManager>, ProviderError> {
        self.pool.get().await.map_err(|e| {
            ProviderError::ConnectionError(format!(
                "Failed to get Redis connection from pool: {}",
                e
            ))
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::ContainerAsync;
    use testcontainers_modules::redis::Redis;

    async fn wait_for_redis(redis_url: &str) {
        let client = redis::Client::open(redis_url).expect("invalid redis url");
        for _ in 0..30 {
            if let Ok(mut conn) = client.get_async_connection().await {
                let pong: redis::RedisResult<String> =
                    redis::cmd("PING").query_async(&mut conn).await;
                if pong.is_ok() {
                    return;
                }
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        panic!("Redis did not become ready at {}", redis_url);
    }

    async fn setup_redis() -> (ContainerAsync<Redis>, String) {
        let redis_container = Redis::default().start().await.unwrap();
        let redis_port = redis_container.get_host_port_ipv4(6379).await.unwrap();
        let redis_url = format!("redis://127.0.0.1:{}", redis_port);
        wait_for_redis(&redis_url).await;
        (redis_container, redis_url)
    }

    #[tokio::test]
    async fn test_user_settings_cache() {
        let (_container, redis_url) = setup_redis().await;
        let client = RedisClient::new(&redis_url).await.unwrap();

        // Test getting default settings for non-existent user
        let settings = client.get_user_settings("test_user").await.unwrap();
        assert_eq!(settings.user_id, "test_user");
        assert!(settings.websocket_enabled);
        assert!(settings.notifications_enabled);

        // Test caching settings
        let mut new_settings = settings.clone();
        new_settings.websocket_enabled = false;
        client.cache_user_settings(&new_settings).await.unwrap();

        // Test retrieving cached settings
        let cached_settings = client.get_user_settings("test_user").await.unwrap();
        assert!(!cached_settings.websocket_enabled);

        // Test cache invalidation
        client.invalidate_user_cache("test_user").await.unwrap();
        let default_settings = client.get_user_settings("test_user").await.unwrap();
        assert!(default_settings.websocket_enabled); // Should be back to default
    }

    #[tokio::test]
    async fn test_health_check() {
        let (_container, redis_url) = setup_redis().await;
        let client = RedisClient::new(&redis_url).await.unwrap();

        assert!(client.health_check().await.is_ok());
    }
}
