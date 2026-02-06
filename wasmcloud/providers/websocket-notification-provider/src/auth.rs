use crate::redis_client::RedisClient;
use crate::types::{Connection, DeviceType, KnoxToken};
use anyhow::{anyhow, Result};
use chrono::Utc;
use std::sync::Arc;
use tracing::{debug, error, info, warn};

#[cfg(test)]
use mockall::{automock, predicate::*};

/// Authentication service for WebSocket connections
pub struct AuthService {
    redis_client: Arc<dyn RedisClientTrait>,
    max_connections_per_user: usize,
}

/// Trait for Redis operations (for mocking in tests)
#[cfg_attr(test, automock)]
#[async_trait::async_trait]
pub trait RedisClientTrait: Send + Sync {
    async fn get_knox_token(&self, token_key: &str) -> Result<Option<KnoxToken>>;
    async fn get_user_connections(&self, user_id: &str) -> Result<Vec<String>>;
    async fn add_user_connection(&self, user_id: &str, connection_id: &str) -> Result<()>;
    async fn remove_user_connection(&self, user_id: &str, connection_id: &str) -> Result<()>;
}

#[async_trait::async_trait]
impl RedisClientTrait for RedisClient {
    async fn get_knox_token(&self, token_key: &str) -> Result<Option<KnoxToken>> {
        self.get_knox_token(token_key).await
    }

    async fn get_user_connections(&self, user_id: &str) -> Result<Vec<String>> {
        self.get_user_connections(user_id).await
    }

    async fn add_user_connection(&self, user_id: &str, connection_id: &str) -> Result<()> {
        self.add_user_connection(user_id, connection_id).await
    }

    async fn remove_user_connection(&self, user_id: &str, connection_id: &str) -> Result<()> {
        self.remove_user_connection(user_id, connection_id).await
    }
}

impl AuthService {
    pub fn new(redis_client: Arc<dyn RedisClientTrait>, max_connections_per_user: usize) -> Self {
        Self {
            redis_client,
            max_connections_per_user,
        }
    }

    /// Validate Knox token and authenticate connection
    pub async fn authenticate(
        &self,
        connection: &mut Connection,
        token: &str,
        device: DeviceType,
    ) -> Result<()> {
        // Extract token key (first 8 characters for Knox)
        if token.len() < 8 {
            warn!("Invalid token format: too short");
            return Err(anyhow!("Invalid token format"));
        }

        let token_key = &token[..8];
        debug!("Validating Knox token with key: {}", token_key);

        // Look up token in Redis
        let knox_token = self
            .redis_client
            .get_knox_token(token_key)
            .await?
            .ok_or_else(|| {
                warn!("Knox token not found: {}", token_key);
                anyhow!("Invalid or expired token")
            })?;

        // Check token expiry
        if knox_token.expiry < Utc::now() {
            warn!("Knox token expired for user: {}", knox_token.user_id);
            return Err(anyhow!("Token expired"));
        }

        // Check connection limit
        let existing_connections = self
            .redis_client
            .get_user_connections(&knox_token.user_id)
            .await?;

        if existing_connections.len() >= self.max_connections_per_user {
            warn!(
                "User {} exceeded max connections: {}",
                knox_token.user_id, self.max_connections_per_user
            );
            return Err(anyhow!("Maximum connections exceeded"));
        }

        // Update connection state
        connection.user_id = knox_token.user_id.clone();
        connection.device = device;
        connection.last_ping = Utc::now();

        // Add connection to user's active connections
        self.redis_client
            .add_user_connection(&knox_token.user_id, &connection.id)
            .await?;

        info!(
            "Successfully authenticated user {} on device {:?}",
            knox_token.user_id, connection.device
        );

        Ok(())
    }

    /// Remove connection from user's active connections
    pub async fn disconnect(&self, connection_id: &str, user_id: &str) -> Result<()> {
        self.redis_client
            .remove_user_connection(user_id, connection_id)
            .await?;
        info!("Removed connection {} for user {}", connection_id, user_id);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;
    use mockall::predicate::eq;

    fn create_test_connection() -> Connection {
        Connection::new("conn_123".to_string(), "127.0.0.1".to_string())
    }

    fn create_valid_token() -> KnoxToken {
        KnoxToken {
            user_id: "user_123".to_string(),
            token_key: "12345678".to_string(),
            expiry: Utc::now() + Duration::hours(48),
            created_at: Utc::now(),
        }
    }

    fn create_expired_token() -> KnoxToken {
        KnoxToken {
            user_id: "user_123".to_string(),
            token_key: "12345678".to_string(),
            expiry: Utc::now() - Duration::hours(1),
            created_at: Utc::now() - Duration::hours(49),
        }
    }

    #[tokio::test]
    async fn test_knox_validation_success() {
        let mut mock_redis = MockRedisClientTrait::new();
        let valid_token = create_valid_token();

        mock_redis
            .expect_get_knox_token()
            .with(eq("12345678"))
            .times(1)
            .returning(move |_| Ok(Some(create_valid_token())));

        mock_redis
            .expect_get_user_connections()
            .with(eq("user_123"))
            .times(1)
            .returning(|_| Ok(vec![]));

        mock_redis
            .expect_add_user_connection()
            .with(eq("user_123"), eq("conn_123"))
            .times(1)
            .returning(|_, _| Ok(()));

        let auth_service = AuthService::new(Arc::new(mock_redis), 10);
        let mut connection = create_test_connection();

        let result = auth_service
            .authenticate(&mut connection, "12345678abcdef", DeviceType::Dashboard)
            .await;

        assert!(result.is_ok());
        assert_eq!(connection.user_id, "user_123");
        assert_eq!(connection.device, DeviceType::Dashboard);
    }

    #[tokio::test]
    async fn test_token_expiry() {
        let mut mock_redis = MockRedisClientTrait::new();
        let expired_token = create_expired_token();

        mock_redis
            .expect_get_knox_token()
            .with(eq("12345678"))
            .times(1)
            .returning(move |_| Ok(Some(create_expired_token())));

        let auth_service = AuthService::new(Arc::new(mock_redis), 10);
        let mut connection = create_test_connection();

        let result = auth_service
            .authenticate(&mut connection, "12345678abcdef", DeviceType::iOS)
            .await;

        assert!(result.is_err());
        assert_eq!(result.unwrap_err().to_string(), "Token expired");
    }

    #[tokio::test]
    async fn test_invalid_token_format() {
        let mock_redis = MockRedisClientTrait::new();
        let auth_service = AuthService::new(Arc::new(mock_redis), 10);
        let mut connection = create_test_connection();

        let result = auth_service
            .authenticate(&mut connection, "short", DeviceType::Android)
            .await;

        assert!(result.is_err());
        assert_eq!(result.unwrap_err().to_string(), "Invalid token format");
    }

    #[tokio::test]
    async fn test_token_not_found() {
        let mut mock_redis = MockRedisClientTrait::new();

        mock_redis
            .expect_get_knox_token()
            .with(eq("12345678"))
            .times(1)
            .returning(|_| Ok(None));

        let auth_service = AuthService::new(Arc::new(mock_redis), 10);
        let mut connection = create_test_connection();

        let result = auth_service
            .authenticate(&mut connection, "12345678abcdef", DeviceType::Dashboard)
            .await;

        assert!(result.is_err());
        assert_eq!(result.unwrap_err().to_string(), "Invalid or expired token");
    }

    #[tokio::test]
    async fn test_max_connections_exceeded() {
        let mut mock_redis = MockRedisClientTrait::new();

        mock_redis
            .expect_get_knox_token()
            .with(eq("12345678"))
            .times(1)
            .returning(move |_| Ok(Some(create_valid_token())));

        mock_redis
            .expect_get_user_connections()
            .with(eq("user_123"))
            .times(1)
            .returning(|_| Ok(vec!["conn_1".to_string(), "conn_2".to_string()]));

        let auth_service = AuthService::new(Arc::new(mock_redis), 2);
        let mut connection = create_test_connection();

        let result = auth_service
            .authenticate(&mut connection, "12345678abcdef", DeviceType::Dashboard)
            .await;

        assert!(result.is_err());
        assert_eq!(
            result.unwrap_err().to_string(),
            "Maximum connections exceeded"
        );
    }

    #[tokio::test]
    async fn test_disconnect() {
        let mut mock_redis = MockRedisClientTrait::new();

        mock_redis
            .expect_remove_user_connection()
            .with(eq("user_123"), eq("conn_123"))
            .times(1)
            .returning(|_, _| Ok(()));

        let auth_service = AuthService::new(Arc::new(mock_redis), 10);

        let result = auth_service.disconnect("conn_123", "user_123").await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_disconnect_unauthenticated() {
        let mut mock_redis = MockRedisClientTrait::new();

        mock_redis
            .expect_remove_user_connection()
            .with(eq("user_123"), eq("conn_123"))
            .times(1)
            .returning(|_, _| Ok(()));

        let auth_service = AuthService::new(Arc::new(mock_redis), 10);

        let result = auth_service.disconnect("conn_123", "user_123").await;
        assert!(result.is_ok());
    }
}
