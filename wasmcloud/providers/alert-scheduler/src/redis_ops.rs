//! Redis operations manager with connection pooling and retry logic

use crate::{AlertSchedulerConfig, AlertSchedulerError, Result};
use deadpool_redis::{Config, Pool, Runtime};
use std::time::Duration;
use tracing::{debug, error, info};

/// Redis connection manager with pooling
pub struct RedisManager {
    pool: Pool,
    config: AlertSchedulerConfig,
}

impl RedisManager {
    /// Create new Redis manager with connection pool
    pub async fn new(config: AlertSchedulerConfig) -> Result<Self> {
        let redis_config = Config::from_url(&config.redis_url);
        let pool = redis_config
            .create_pool(Some(Runtime::Tokio1))
            .map_err(|e| {
                AlertSchedulerError::Configuration(format!("Failed to create pool: {}", e))
            })?;

        // Test connection
        let mut conn = pool.get().await.map_err(|e| {
            AlertSchedulerError::RedisConnection(redis::RedisError::from((
                redis::ErrorKind::IoError,
                "Pool connection failed",
                e.to_string(),
            )))
        })?;

        // Ping to verify connection
        let _: String = redis::cmd("PING")
            .query_async(&mut conn)
            .await
            .map_err(|e| AlertSchedulerError::RedisConnection(e))?;

        info!(
            "Redis connection pool initialized with {} connections",
            config.redis_pool_size
        );

        Ok(Self { pool, config })
    }

    /// Get connection from pool
    pub async fn get_connection(&self) -> Result<deadpool_redis::Connection> {
        self.pool.get().await.map_err(|e| {
            AlertSchedulerError::RedisConnection(redis::RedisError::from((
                redis::ErrorKind::IoError,
                "Failed to get connection from pool",
                e.to_string(),
            )))
        })
    }

    /// Execute command with retry logic
    pub async fn execute_with_retry<T, F, Fut>(
        &self,
        mut operation: F,
        max_retries: u32,
    ) -> Result<T>
    where
        F: FnMut(deadpool_redis::Connection) -> Fut,
        Fut: std::future::Future<Output = redis::RedisResult<T>>,
    {
        let mut last_error = None;

        for attempt in 0..=max_retries {
            if attempt > 0 {
                let delay = Duration::from_millis(100 * 2_u64.pow(attempt - 1));
                debug!("Retry attempt {} after {:?}", attempt, delay);
                tokio::time::sleep(delay).await;
            }

            match self.get_connection().await {
                Ok(conn) => {
                    match operation(conn).await {
                        Ok(result) => return Ok(result),
                        Err(e) => {
                            error!("Redis operation failed on attempt {}: {}", attempt + 1, e);
                            last_error = Some(AlertSchedulerError::RedisConnection(e));

                            // Don't retry on certain errors
                            if !self.is_retryable_error(&last_error.as_ref().unwrap()) {
                                break;
                            }
                        }
                    }
                }
                Err(e) => {
                    error!("Failed to get connection on attempt {}: {}", attempt + 1, e);
                    last_error = Some(e);
                }
            }
        }

        Err(last_error.unwrap_or_else(|| {
            AlertSchedulerError::RedisConnection(redis::RedisError::from((
                redis::ErrorKind::IoError,
                "All retry attempts exhausted",
            )))
        }))
    }

    fn is_retryable_error(&self, error: &AlertSchedulerError) -> bool {
        matches!(
            error,
            AlertSchedulerError::RedisConnection(_) | AlertSchedulerError::Timeout { .. }
        )
    }

    /// Get pool statistics
    pub fn pool_status(&self) -> PoolStatus {
        let status = self.pool.status();
        PoolStatus {
            size: status.size,
            available: status.available,
            waiting: status.waiting,
        }
    }
}

/// Pool status information
#[derive(Debug, Clone)]
pub struct PoolStatus {
    pub size: usize,
    pub available: usize,
    pub waiting: usize,
}
