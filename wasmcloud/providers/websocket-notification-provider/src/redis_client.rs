use crate::types::{
    ConnectionMetadata, KnoxToken, UserNotificationSettings, UserNotificationStats,
};
use anyhow::{anyhow, Result};
use chrono::{DateTime, Utc};
use redis::aio::ConnectionManager;
use redis::{AsyncCommands, Client};
use serde::{Deserialize, Serialize};
use serde_json;
use std::collections::HashMap;
use std::time::Duration;
use tracing::{debug, error, info};

/// Redis client for session and token management
pub struct RedisClient {
    client: Client,
    connection: Option<ConnectionManager>,
}

impl RedisClient {
    /// Create a new Redis client
    pub fn new(redis_url: &str) -> Result<Self> {
        let client = Client::open(redis_url)?;
        Ok(Self {
            client,
            connection: None,
        })
    }

    /// Connect to Redis
    pub async fn connect(&mut self) -> Result<()> {
        let connection = self.client.get_connection_manager().await?;
        self.connection = Some(connection);
        info!("Connected to Redis");
        Ok(())
    }

    /// Get connection manager
    fn get_connection(&self) -> Result<&ConnectionManager> {
        self.connection
            .as_ref()
            .ok_or_else(|| anyhow!("Redis not connected"))
    }

    /// Get Knox token by token key
    pub async fn get_knox_token(&self, token_key: &str) -> Result<Option<KnoxToken>> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("knox:tokens:{}", token_key);

        let data: Option<String> = conn.get(&key).await?;

        match data {
            Some(json) => {
                debug!("Found Knox token for key: {}", token_key);
                let token: KnoxToken = serde_json::from_str(&json)?;
                Ok(Some(token))
            }
            None => {
                debug!("Knox token not found for key: {}", token_key);
                Ok(None)
            }
        }
    }

    /// Get user's active connections
    pub async fn get_user_connections(&self, user_id: &str) -> Result<Vec<String>> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("websocket:sessions:{}", user_id);

        let connections: Vec<String> = conn.smembers(&key).await?;
        debug!(
            "User {} has {} active connections",
            user_id,
            connections.len()
        );
        Ok(connections)
    }

    /// Add connection to user's active connections
    pub async fn add_user_connection(&self, user_id: &str, connection_id: &str) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("websocket:sessions:{}", user_id);

        conn.sadd::<_, _, ()>(&key, connection_id).await?;
        debug!("Added connection {} to user {}", connection_id, user_id);
        Ok(())
    }

    /// Remove connection from user's active connections
    pub async fn remove_user_connection(&self, user_id: &str, connection_id: &str) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("websocket:sessions:{}", user_id);

        conn.srem::<_, _, ()>(&key, connection_id).await?;
        debug!("Removed connection {} from user {}", connection_id, user_id);
        Ok(())
    }

    /// Store connection metadata
    pub async fn store_connection_metadata(&self, metadata: &ConnectionMetadata) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("websocket:connections:{}", metadata.connection_id);

        let json = serde_json::to_string(metadata)?;
        conn.set_ex::<_, _, ()>(&key, json, 86400).await?; // 24 hour TTL

        debug!("Stored metadata for connection {}", metadata.connection_id);
        Ok(())
    }

    /// Get connection metadata
    pub async fn get_connection_metadata(
        &self,
        connection_id: &str,
    ) -> Result<Option<ConnectionMetadata>> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("websocket:connections:{}", connection_id);

        let data: Option<String> = conn.get(&key).await?;

        match data {
            Some(json) => {
                let metadata: ConnectionMetadata = serde_json::from_str(&json)?;
                Ok(Some(metadata))
            }
            None => Ok(None),
        }
    }

    /// Remove connection metadata
    pub async fn remove_connection_metadata(&self, connection_id: &str) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("websocket:connections:{}", connection_id);

        conn.del::<_, ()>(&key).await?;
        debug!("Removed metadata for connection {}", connection_id);
        Ok(())
    }

    /// Store metrics
    pub async fn store_metrics(
        &self,
        total_connections: usize,
        messages_sent: usize,
        avg_latency_ms: u64,
    ) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let now = Utc::now();
        let key = format!(
            "websocket:metrics:{}:{}",
            now.format("%Y-%m-%d"),
            now.format("%H")
        );

        let metrics = serde_json::json!({
            "total_connections": total_connections,
            "messages_sent": messages_sent,
            "avg_latency_ms": avg_latency_ms,
            "timestamp": now.to_rfc3339(),
        });

        conn.set_ex::<_, _, ()>(&key, metrics.to_string(), 604800)
            .await?; // 7 day TTL
        debug!(
            "Stored metrics: {} connections, {} messages",
            total_connections, messages_sent
        );
        Ok(())
    }

    /// Queue missed messages for a user
    pub async fn queue_missed_message(
        &self,
        user_id: &str,
        message: &str,
        ttl_seconds: u64,
    ) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("websocket:queue:{}", user_id);

        // Add to list
        conn.lpush::<_, _, ()>(&key, message).await?;

        // Set TTL on the queue
        conn.expire::<_, ()>(&key, ttl_seconds as i64).await?;

        // Trim to max 100 messages
        conn.ltrim::<_, ()>(&key, 0, 99).await?;

        debug!("Queued message for user {}", user_id);
        Ok(())
    }

    /// Get queued messages for a user
    pub async fn get_queued_messages(&self, user_id: &str) -> Result<Vec<String>> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("websocket:queue:{}", user_id);

        let messages: Vec<String> = conn.lrange(&key, 0, -1).await?;

        // Clear the queue after retrieval
        if !messages.is_empty() {
            conn.del::<_, ()>(&key).await?;
            debug!(
                "Retrieved {} queued messages for user {}",
                messages.len(),
                user_id
            );
        }

        Ok(messages)
    }

    /// Check Redis health
    pub async fn ping(&self) -> Result<bool> {
        let mut conn = self.get_connection()?.clone();
        let pong: String = redis::cmd("PING").query_async(&mut conn).await?;
        Ok(pong == "PONG")
    }

    // NOTIFICATION SYSTEM INTEGRATION

    /// Get user notification settings from cache
    pub async fn get_user_notification_settings(
        &self,
        user_id: &str,
    ) -> Result<Option<UserNotificationSettings>> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("user:notifications:{}", user_id);

        let data: Option<String> = conn.get(&key).await?;

        match data {
            Some(json) => {
                debug!("Found notification settings for user: {}", user_id);
                let settings: UserNotificationSettings = serde_json::from_str(&json)?;
                Ok(Some(settings))
            }
            None => {
                debug!("Notification settings not found for user: {}", user_id);
                Ok(None)
            }
        }
    }

    /// Cache user notification settings
    pub async fn cache_user_notification_settings(
        &self,
        user_id: &str,
        settings: &UserNotificationSettings,
    ) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("user:notifications:{}", user_id);

        let json = serde_json::to_string(settings)?;
        conn.set_ex::<_, _, ()>(&key, json, 3600).await?; // 1 hour TTL

        debug!("Cached notification settings for user: {}", user_id);
        Ok(())
    }

    /// Invalidate user notification settings cache
    pub async fn invalidate_user_notification_settings(&self, user_id: &str) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("user:notifications:{}", user_id);

        conn.del::<_, ()>(&key).await?;
        debug!(
            "Invalidated notification settings cache for user: {}",
            user_id
        );
        Ok(())
    }

    /// Check if user has WebSocket notifications enabled
    pub async fn is_websocket_enabled_for_user(&self, user_id: &str) -> Result<bool> {
        match self.get_user_notification_settings(user_id).await? {
            Some(settings) => Ok(settings.websocket_enabled),
            None => {
                // Default to enabled if no settings found (per PRD)
                debug!(
                    "No notification settings found for user {}, defaulting WebSocket to enabled",
                    user_id
                );
                Ok(true)
            }
        }
    }

    /// Get WebSocket configuration for user
    pub async fn get_websocket_config_for_user(
        &self,
        user_id: &str,
    ) -> Result<Option<HashMap<String, serde_json::Value>>> {
        match self.get_user_notification_settings(user_id).await? {
            Some(settings) => {
                if let Some(websocket_channel) = settings.channels.get("websocket") {
                    // The websocket_channel is already a HashMap<String, serde_json::Value>
                    return Ok(Some(websocket_channel.clone()));
                }
                Ok(None)
            }
            None => Ok(None),
        }
    }

    /// Check if user is in quiet hours
    pub async fn is_user_in_quiet_hours(&self, user_id: &str) -> Result<bool> {
        match self.get_user_notification_settings(user_id).await? {
            Some(settings) => {
                if let Some(quiet_hours) = &settings.quiet_hours {
                    if quiet_hours.enabled {
                        // This is a simplified implementation - in production,
                        // you'd need to properly handle timezone conversion
                        let now = Utc::now().time();
                        let start_time = quiet_hours.start_time;
                        let end_time = quiet_hours.end_time;

                        // Simple comparison (assumes UTC time for now)
                        if start_time <= end_time {
                            return Ok(now >= start_time && now <= end_time);
                        } else {
                            // Quiet hours span midnight
                            return Ok(now >= start_time || now <= end_time);
                        }
                    }
                }
                Ok(false)
            }
            None => Ok(false),
        }
    }

    /// Check if notification priority overrides quiet hours
    pub async fn can_override_quiet_hours(&self, user_id: &str, priority: &str) -> Result<bool> {
        match self.get_user_notification_settings(user_id).await? {
            Some(settings) => {
                if let Some(quiet_hours) = &settings.quiet_hours {
                    return Ok(quiet_hours
                        .priority_override
                        .contains(&priority.to_string()));
                }
                Ok(false)
            }
            None => Ok(false),
        }
    }

    /// Get notification delivery statistics for user
    pub async fn get_user_notification_stats(
        &self,
        user_id: &str,
    ) -> Result<UserNotificationStats> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("user:notification_stats:{}", user_id);

        let data: Option<String> = conn.get(&key).await?;

        match data {
            Some(json) => {
                let stats: UserNotificationStats = serde_json::from_str(&json)?;
                Ok(stats)
            }
            None => Ok(UserNotificationStats::default()),
        }
    }

    /// Update notification delivery statistics
    pub async fn update_user_notification_stats(
        &self,
        user_id: &str,
        channel: &str,
        delivered: bool,
    ) -> Result<()> {
        let mut conn = self.get_connection()?.clone();
        let key = format!("user:notification_stats:{}", user_id);

        // Get current stats
        let mut stats = self.get_user_notification_stats(user_id).await?;

        // Update stats
        stats.total_notifications += 1;
        if delivered {
            stats.delivered_notifications += 1;
            *stats.channel_stats.entry(channel.to_string()).or_insert(0) += 1;
        } else {
            stats.failed_notifications += 1;
        }
        stats.last_notification = Some(Utc::now());

        // Save updated stats
        let json = serde_json::to_string(&stats)?;
        conn.set_ex::<_, _, ()>(&key, json, 86400 * 7).await?; // 7 day TTL

        debug!("Updated notification stats for user: {}", user_id);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{DeviceType, NotificationFilters};
    use chrono::Duration;
    use tempfile::tempdir;

    // Note: These tests require a Redis instance or would use a mock Redis client
    // For unit tests, we'll create tests that can run without Redis

    #[test]
    fn test_redis_client_creation() {
        let client = RedisClient::new("redis://localhost:6379");
        assert!(client.is_ok());
    }

    #[test]
    fn test_connection_metadata_serialization() {
        let metadata = ConnectionMetadata {
            user_id: "user_123".to_string(),
            connection_id: "conn_456".to_string(),
            device: DeviceType::Dashboard,
            connected_at: Utc::now(),
            last_ping: Utc::now(),
            ip_address: "127.0.0.1".to_string(),
            user_agent: Some("Mozilla/5.0".to_string()),
            filters: NotificationFilters::default(),
        };

        let json = serde_json::to_string(&metadata);
        assert!(json.is_ok());

        let deserialized: Result<ConnectionMetadata, _> = serde_json::from_str(&json.unwrap());
        assert!(deserialized.is_ok());

        let restored = deserialized.unwrap();
        assert_eq!(restored.user_id, metadata.user_id);
        assert_eq!(restored.connection_id, metadata.connection_id);
        assert_eq!(restored.device, metadata.device);
    }

    #[test]
    fn test_knox_token_serialization() {
        let token = KnoxToken {
            user_id: "user_123".to_string(),
            token_key: "12345678".to_string(),
            expiry: Utc::now() + Duration::hours(48),
            created_at: Utc::now(),
        };

        let json = serde_json::to_string(&token);
        assert!(json.is_ok());

        let deserialized: Result<KnoxToken, _> = serde_json::from_str(&json.unwrap());
        assert!(deserialized.is_ok());

        let restored = deserialized.unwrap();
        assert_eq!(restored.user_id, token.user_id);
        assert_eq!(restored.token_key, token.token_key);
    }

    #[test]
    fn test_redis_key_formatting() {
        // Test key formatting
        let user_id = "user_123";
        let connection_id = "conn_456";
        let token_key = "12345678";

        let sessions_key = format!("websocket:sessions:{}", user_id);
        assert_eq!(sessions_key, "websocket:sessions:user_123");

        let connections_key = format!("websocket:connections:{}", connection_id);
        assert_eq!(connections_key, "websocket:connections:conn_456");

        let knox_key = format!("knox:tokens:{}", token_key);
        assert_eq!(knox_key, "knox:tokens:12345678");

        let queue_key = format!("websocket:queue:{}", user_id);
        assert_eq!(queue_key, "websocket:queue:user_123");
    }

    #[test]
    fn test_metrics_key_formatting() {
        let now = chrono::DateTime::parse_from_rfc3339("2025-01-07T10:30:00Z")
            .unwrap()
            .with_timezone(&Utc);

        let key = format!(
            "websocket:metrics:{}:{}",
            now.format("%Y-%m-%d"),
            now.format("%H")
        );

        assert_eq!(key, "websocket:metrics:2025-01-07:10");
    }

    // Integration tests would go here with a real or mock Redis instance
    #[cfg(feature = "integration_tests")]
    mod integration_tests {
        use super::*;
        use tokio;

        #[tokio::test]
        async fn test_redis_connection() {
            let mut client = RedisClient::new("redis://localhost:6379").unwrap();
            let result = client.connect().await;
            assert!(result.is_ok());

            let ping_result = client.ping().await;
            assert!(ping_result.is_ok());
            assert!(ping_result.unwrap());
        }

        #[tokio::test]
        async fn test_user_connections_operations() {
            let mut client = RedisClient::new("redis://localhost:6379").unwrap();
            client.connect().await.unwrap();

            let user_id = "test_user_123";
            let connection_id = "test_conn_456";

            // Add connection
            client
                .add_user_connection(user_id, connection_id)
                .await
                .unwrap();

            // Get connections
            let connections = client.get_user_connections(user_id).await.unwrap();
            assert!(connections.contains(&connection_id.to_string()));

            // Remove connection
            client
                .remove_user_connection(user_id, connection_id)
                .await
                .unwrap();

            // Verify removed
            let connections = client.get_user_connections(user_id).await.unwrap();
            assert!(!connections.contains(&connection_id.to_string()));
        }

        #[tokio::test]
        async fn test_connection_metadata_operations() {
            let mut client = RedisClient::new("redis://localhost:6379").unwrap();
            client.connect().await.unwrap();

            let metadata = ConnectionMetadata {
                user_id: "test_user_123".to_string(),
                connection_id: "test_conn_456".to_string(),
                device: DeviceType::iOS,
                connected_at: Utc::now(),
                last_ping: Utc::now(),
                ip_address: "192.168.1.1".to_string(),
                user_agent: Some("TestAgent/1.0".to_string()),
                filters: NotificationFilters::default(),
            };

            // Store metadata
            client.store_connection_metadata(&metadata).await.unwrap();

            // Retrieve metadata
            let retrieved = client
                .get_connection_metadata("test_conn_456")
                .await
                .unwrap();
            assert!(retrieved.is_some());

            let retrieved_metadata = retrieved.unwrap();
            assert_eq!(retrieved_metadata.user_id, metadata.user_id);
            assert_eq!(retrieved_metadata.device, metadata.device);

            // Remove metadata
            client
                .remove_connection_metadata("test_conn_456")
                .await
                .unwrap();

            // Verify removed
            let retrieved = client
                .get_connection_metadata("test_conn_456")
                .await
                .unwrap();
            assert!(retrieved.is_none());
        }

        #[tokio::test]
        async fn test_message_queue_operations() {
            let mut client = RedisClient::new("redis://localhost:6379").unwrap();
            client.connect().await.unwrap();

            let user_id = "test_user_789";
            let message1 = r#"{"type":"notification","alert_id":"1"}"#;
            let message2 = r#"{"type":"notification","alert_id":"2"}"#;

            // Queue messages
            client
                .queue_missed_message(user_id, message1, 300)
                .await
                .unwrap();
            client
                .queue_missed_message(user_id, message2, 300)
                .await
                .unwrap();

            // Get queued messages
            let messages = client.get_queued_messages(user_id).await.unwrap();
            assert_eq!(messages.len(), 2);
            // Messages are in LIFO order due to LPUSH
            assert!(messages[0].contains("alert_id\":\"2"));
            assert!(messages[1].contains("alert_id\":\"1"));

            // Verify queue is cleared
            let messages = client.get_queued_messages(user_id).await.unwrap();
            assert_eq!(messages.len(), 0);
        }

        #[tokio::test]
        async fn test_metrics_storage() {
            let mut client = RedisClient::new("redis://localhost:6379").unwrap();
            client.connect().await.unwrap();

            let result = client.store_metrics(100, 5000, 45).await;
            assert!(result.is_ok());
        }
    }
}
