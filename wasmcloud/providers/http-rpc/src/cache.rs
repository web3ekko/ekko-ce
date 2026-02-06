//! Redis-backed caching for RPC responses
//!
//! Provides caching capabilities to reduce RPC endpoint load and improve response times.
//! Supports configurable TTLs per cache key pattern.

use anyhow::{anyhow, Result};
use redis::{AsyncCommands, Client as RedisClient};
use serde_json::Value;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{debug, warn};

/// Cache configuration
#[derive(Debug, Clone)]
pub struct CacheConfig {
    /// Redis connection URL
    pub redis_url: String,

    /// Default TTL for cache entries (seconds)
    pub default_ttl: u64,

    /// TTL for block data (seconds) - longer because blocks are immutable
    pub block_ttl: u64,

    /// TTL for transaction data (seconds) - very long because txs are immutable
    pub tx_ttl: u64,

    /// Enable caching (can be disabled for testing)
    pub enabled: bool,
}

impl Default for CacheConfig {
    fn default() -> Self {
        //TODO: these should be environment variables with defaults
        Self {
            redis_url: "redis://redis.ekko.svc.cluster.local:6379".to_string(),
            default_ttl: 60, // 1 minute
            block_ttl: 300,  // 5 minutes (blocks finalize)
            tx_ttl: 3600,    // 1 hour (txs are immutable)
            enabled: true,
        }
    }
}

/// RPC response cache using Redis
pub struct RpcCache {
    /// Redis client
    client: Arc<RwLock<Option<RedisClient>>>,

    /// Cache configuration
    config: CacheConfig,

    /// Cache key prefix
    key_prefix: String,
}

impl RpcCache {
    /// Create a new RPC cache
    pub fn new(config: CacheConfig) -> Self {
        Self {
            client: Arc::new(RwLock::new(None)),
            config,
            key_prefix: "rpc:cache:".to_string(),
        }
    }

    /// Connect to Redis
    pub async fn connect(&self) -> Result<()> {
        if !self.config.enabled {
            debug!("Cache is disabled, skipping Redis connection");
            return Ok(());
        }

        match RedisClient::open(self.config.redis_url.as_str()) {
            Ok(client) => {
                *self.client.write().await = Some(client);
                debug!("Connected to Redis at {}", self.config.redis_url);
                Ok(())
            }
            Err(e) => {
                warn!("Failed to connect to Redis: {}. Cache will be disabled.", e);
                // Don't fail - just disable caching
                Ok(())
            }
        }
    }

    /// Get a cached RPC response
    pub async fn get(&self, key: &str) -> Result<Option<Value>> {
        if !self.config.enabled {
            return Ok(None);
        }

        let client_lock = self.client.read().await;
        if client_lock.is_none() {
            return Ok(None);
        }

        let client = client_lock.as_ref().unwrap();
        let full_key = format!("{}{}", self.key_prefix, key);

        match client.get_async_connection().await {
            Ok(mut conn) => match conn.get::<_, Option<String>>(&full_key).await {
                Ok(Some(cached_str)) => {
                    debug!("Cache HIT for key: {}", key);
                    match serde_json::from_str(&cached_str) {
                        Ok(value) => Ok(Some(value)),
                        Err(e) => {
                            warn!("Failed to deserialize cached value: {}", e);
                            Ok(None)
                        }
                    }
                }
                Ok(None) => {
                    debug!("Cache MISS for key: {}", key);
                    Ok(None)
                }
                Err(e) => {
                    warn!("Redis GET error: {}. Treating as cache miss.", e);
                    Ok(None)
                }
            },
            Err(e) => {
                warn!(
                    "Failed to get Redis connection: {}. Treating as cache miss.",
                    e
                );
                Ok(None)
            }
        }
    }

    /// Set a cached RPC response with TTL
    pub async fn set(&self, key: &str, value: &Value, ttl: Duration) -> Result<()> {
        if !self.config.enabled {
            return Ok(());
        }

        let client_lock = self.client.read().await;
        if client_lock.is_none() {
            return Ok(());
        }

        let client = client_lock.as_ref().unwrap();
        let full_key = format!("{}{}", self.key_prefix, key);

        let value_str = serde_json::to_string(value)
            .map_err(|e| anyhow!("Failed to serialize value: {}", e))?;

        match client.get_async_connection().await {
            Ok(mut conn) => {
                match conn
                    .set_ex::<_, _, ()>(&full_key, value_str, ttl.as_secs())
                    .await
                {
                    Ok(_) => {
                        debug!("Cached value for key: {} (TTL: {}s)", key, ttl.as_secs());
                        Ok(())
                    }
                    Err(e) => {
                        warn!("Redis SET error: {}. Cache write failed.", e);
                        // Don't fail - just log the error
                        Ok(())
                    }
                }
            }
            Err(e) => {
                warn!("Failed to get Redis connection: {}. Cache write failed.", e);
                Ok(())
            }
        }
    }

    /// Set with default TTL
    pub async fn set_default(&self, key: &str, value: &Value) -> Result<()> {
        self.set(key, value, Duration::from_secs(self.config.default_ttl))
            .await
    }

    /// Set block data with longer TTL (blocks are immutable once finalized)
    pub async fn set_block(&self, key: &str, value: &Value) -> Result<()> {
        self.set(key, value, Duration::from_secs(self.config.block_ttl))
            .await
    }

    /// Set transaction data with very long TTL (txs are immutable)
    pub async fn set_transaction(&self, key: &str, value: &Value) -> Result<()> {
        self.set(key, value, Duration::from_secs(self.config.tx_ttl))
            .await
    }

    /// Generate cache key for an RPC request
    pub fn make_key(&self, network: &str, method: &str, params: &[Value]) -> String {
        // Create deterministic key from method and params
        let params_str = serde_json::to_string(params).unwrap_or_default();
        format!("{}:{}:{}", network, method, params_str)
    }

    /// Clear all cache entries (useful for testing)
    pub async fn clear_all(&self) -> Result<()> {
        if !self.config.enabled {
            return Ok(());
        }

        let client_lock = self.client.read().await;
        if let Some(client) = client_lock.as_ref() {
            match client.get_async_connection().await {
                Ok(mut conn) => {
                    let pattern = format!("{}*", self.key_prefix);
                    match redis::cmd("KEYS")
                        .arg(&pattern)
                        .query_async::<_, Vec<String>>(&mut conn)
                        .await
                    {
                        Ok(keys) => {
                            if !keys.is_empty() {
                                match conn.del::<_, ()>(keys).await {
                                    Ok(_) => {
                                        debug!("Cleared all cache entries");
                                        Ok(())
                                    }
                                    Err(e) => {
                                        warn!("Failed to delete cache keys: {}", e);
                                        Ok(())
                                    }
                                }
                            } else {
                                Ok(())
                            }
                        }
                        Err(e) => {
                            warn!("Failed to list cache keys: {}", e);
                            Ok(())
                        }
                    }
                }
                Err(e) => {
                    warn!("Failed to get Redis connection for clear: {}", e);
                    Ok(())
                }
            }
        } else {
            Ok(())
        }
    }

    /// Check if caching is enabled and connected
    pub async fn is_available(&self) -> bool {
        self.config.enabled && self.client.read().await.is_some()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_config_default() {
        let config = CacheConfig::default();
        assert_eq!(config.default_ttl, 60);
        assert_eq!(config.block_ttl, 300);
        assert_eq!(config.tx_ttl, 3600);
        assert!(config.enabled);
    }

    #[test]
    fn test_make_cache_key() {
        let config = CacheConfig::default();
        let cache = RpcCache::new(config);

        let key1 = cache.make_key("ethereum", "eth_blockNumber", &[]);
        let key2 = cache.make_key(
            "ethereum",
            "eth_getBlockByNumber",
            &[Value::String("0x1".to_string())],
        );

        assert!(key1.contains("ethereum"));
        assert!(key1.contains("eth_blockNumber"));
        assert!(key2.contains("eth_getBlockByNumber"));
        assert_ne!(key1, key2);
    }

    #[tokio::test]
    async fn test_cache_disabled() {
        let mut config = CacheConfig::default();
        config.enabled = false;

        let cache = RpcCache::new(config);

        // Cache operations should not fail when disabled
        let result = cache.get("test-key").await;
        assert!(result.is_ok());
        assert!(result.unwrap().is_none());

        let set_result = cache
            .set_default("test-key", &Value::String("test".to_string()))
            .await;
        assert!(set_result.is_ok());
    }
}
