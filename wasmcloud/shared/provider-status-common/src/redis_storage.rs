//! Redis storage layer for provider status persistence.
//!
//! This module handles all Redis interactions for persisting provider status.
//! It uses connection pooling and pipelining for efficient batch writes.

use crate::types::{ErrorRecord, ProviderStatus, ProviderType, SubscriptionStatus};
use anyhow::{Context, Result};
use bb8_redis::{
    bb8::Pool,
    redis::{self, AsyncCommands},
    RedisConnectionManager,
};
use tracing::{debug, info};

/// Redis key prefixes
const KEY_PREFIX_STATUS: &str = "provider:status";
const KEY_PREFIX_SUBSCRIPTION: &str = "provider:subscription";
const KEY_PREFIX_ERRORS: &str = "provider:errors";
const KEY_REGISTRY: &str = "provider:registry";

/// Maximum errors to keep per provider
const MAX_ERRORS: isize = 100;

/// Redis storage for provider status.
pub struct RedisStorage {
    pool: Pool<RedisConnectionManager>,
}

impl RedisStorage {
    /// Create a new Redis storage instance.
    ///
    /// # Arguments
    /// * `redis_url` - Redis connection URL (e.g., "redis://localhost:6379")
    pub async fn new(redis_url: &str) -> Result<Self> {
        info!("Connecting to Redis: {}", redis_url);

        let manager = RedisConnectionManager::new(redis_url)
            .context("Failed to create Redis connection manager")?;

        let pool = Pool::builder()
            .max_size(5)
            .build(manager)
            .await
            .context("Failed to create Redis connection pool")?;

        // Test connection
        {
            let mut conn = pool.get().await.context("Failed to get Redis connection")?;
            let _: String = redis::cmd("PING")
                .query_async(&mut *conn)
                .await
                .context("Failed to ping Redis")?;
        }

        info!("Redis connection established");
        Ok(Self { pool })
    }

    /// Register a provider in the global registry.
    ///
    /// The registry is a hash map: provider_id -> provider_type
    pub async fn register_provider(
        &self,
        provider_id: &str,
        provider_type: ProviderType,
    ) -> Result<()> {
        let mut conn = self.pool.get().await?;

        let _: () = conn
            .hset(KEY_REGISTRY, provider_id, provider_type.to_string())
            .await
            .context("Failed to register provider")?;

        debug!("Registered provider {} in registry", provider_id);
        Ok(())
    }

    /// Unregister a provider from the registry.
    pub async fn unregister_provider(&self, provider_id: &str) -> Result<()> {
        let mut conn = self.pool.get().await?;

        let _: () = conn
            .hdel(KEY_REGISTRY, provider_id)
            .await
            .context("Failed to unregister provider")?;

        // Also clean up status keys
        let status_key = format!("{}:{}", KEY_PREFIX_STATUS, provider_id);
        let errors_key = format!("{}:{}", KEY_PREFIX_ERRORS, provider_id);

        let _: () = conn.del(&status_key).await?;
        let _: () = conn.del(&errors_key).await?;

        debug!("Unregistered provider {} from registry", provider_id);
        Ok(())
    }

    /// Write provider status to Redis with TTL.
    ///
    /// This writes the full provider status and individual subscription statuses.
    pub async fn write_provider_status(
        &self,
        status: &ProviderStatus,
        ttl_secs: u64,
    ) -> Result<()> {
        let mut conn = self.pool.get().await?;

        // Serialize status
        let status_json = serde_json::to_string(status)?;
        let status_key = format!("{}:{}", KEY_PREFIX_STATUS, status.provider_id);

        // Use pipeline for atomic batch write
        let mut pipe = redis::pipe();

        // Write main status
        pipe.set_ex(&status_key, &status_json, ttl_secs);

        // Write individual subscription statuses
        for (chain_id, sub) in &status.subscriptions {
            let sub_key = format!(
                "{}:{}:{}",
                KEY_PREFIX_SUBSCRIPTION, status.provider_id, chain_id
            );
            let sub_json = serde_json::to_string(sub)?;
            pipe.set_ex(&sub_key, &sub_json, ttl_secs);
        }

        // Execute pipeline
        let _: () = pipe
            .query_async(&mut *conn)
            .await
            .context("Failed to write provider status to Redis")?;

        debug!("Wrote status for {} to Redis", status.provider_id);
        Ok(())
    }

    /// Push an error to the provider's error list.
    ///
    /// Errors are stored in a capped list with LPUSH/LTRIM.
    pub async fn push_error(
        &self,
        provider_id: &str,
        error: &ErrorRecord,
        ttl_secs: u64,
    ) -> Result<()> {
        let mut conn = self.pool.get().await?;

        let key = format!("{}:{}", KEY_PREFIX_ERRORS, provider_id);
        let error_json = serde_json::to_string(error)?;

        // Use pipeline for atomic operation
        let mut pipe = redis::pipe();
        pipe.lpush(&key, &error_json);
        pipe.ltrim(&key, 0, MAX_ERRORS - 1);
        pipe.expire(&key, ttl_secs as i64);

        let _: () = pipe
            .query_async(&mut *conn)
            .await
            .context("Failed to push error to Redis")?;

        debug!("Pushed error for {} to Redis", provider_id);
        Ok(())
    }

    /// Get provider status from Redis.
    pub async fn get_provider_status(&self, provider_id: &str) -> Result<Option<ProviderStatus>> {
        let mut conn = self.pool.get().await?;

        let key = format!("{}:{}", KEY_PREFIX_STATUS, provider_id);
        let result: Option<String> = conn.get(&key).await?;

        match result {
            Some(json) => {
                let status: ProviderStatus = serde_json::from_str(&json)?;
                Ok(Some(status))
            }
            None => Ok(None),
        }
    }

    /// Get subscription status from Redis.
    pub async fn get_subscription_status(
        &self,
        provider_id: &str,
        chain_id: &str,
    ) -> Result<Option<SubscriptionStatus>> {
        let mut conn = self.pool.get().await?;

        let key = format!("{}:{}:{}", KEY_PREFIX_SUBSCRIPTION, provider_id, chain_id);
        let result: Option<String> = conn.get(&key).await?;

        match result {
            Some(json) => {
                let status: SubscriptionStatus = serde_json::from_str(&json)?;
                Ok(Some(status))
            }
            None => Ok(None),
        }
    }

    /// Get recent errors for a provider.
    pub async fn get_errors(&self, provider_id: &str, limit: isize) -> Result<Vec<ErrorRecord>> {
        let mut conn = self.pool.get().await?;

        let key = format!("{}:{}", KEY_PREFIX_ERRORS, provider_id);
        let results: Vec<String> = conn.lrange(&key, 0, limit - 1).await?;

        let errors: Vec<ErrorRecord> = results
            .iter()
            .filter_map(|json| serde_json::from_str(json).ok())
            .collect();

        Ok(errors)
    }

    /// List all registered providers.
    pub async fn list_providers(&self) -> Result<Vec<(String, ProviderType)>> {
        let mut conn = self.pool.get().await?;

        let results: Vec<(String, String)> = conn.hgetall(KEY_REGISTRY).await?;

        let providers: Vec<(String, ProviderType)> = results
            .into_iter()
            .map(|(id, type_str)| {
                let ptype = match type_str.as_str() {
                    "evm" => ProviderType::Evm,
                    "utxo" => ProviderType::Utxo,
                    "svm" => ProviderType::Svm,
                    "cosmos" => ProviderType::Cosmos,
                    _ => ProviderType::Other,
                };
                (id, ptype)
            })
            .collect();

        Ok(providers)
    }

    /// Check if Redis is healthy.
    pub async fn health_check(&self) -> Result<bool> {
        match self.pool.get().await {
            Ok(mut conn) => {
                let result: Result<String, _> = redis::cmd("PING").query_async(&mut *conn).await;
                Ok(result.is_ok())
            }
            Err(_) => Ok(false),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Integration tests require Redis running
    // Run with: cargo test --features integration -- --ignored

    #[tokio::test]
    #[ignore]
    async fn test_redis_storage_basic() {
        let storage = RedisStorage::new("redis://localhost:6379")
            .await
            .expect("Failed to connect to Redis");

        // Test provider registration
        storage
            .register_provider("test-provider", ProviderType::Evm)
            .await
            .expect("Failed to register provider");

        // Test list providers
        let providers = storage
            .list_providers()
            .await
            .expect("Failed to list providers");
        assert!(providers.iter().any(|(id, _)| id == "test-provider"));

        // Cleanup
        storage
            .unregister_provider("test-provider")
            .await
            .expect("Failed to unregister provider");
    }
}
