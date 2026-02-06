use crate::{client::ResendClient, config::EmailConfig, formatter::EmailFormatter};
use async_trait::async_trait;
use chrono::Utc;
use notification_common::{
    provider_base::{
        CircuitBreaker, CircuitBreakerConfig, NotificationProvider, ProviderError, ProviderMetrics,
        RateLimiter, RetryPolicy,
    },
    DeliveryStatus, NotificationChannel, NotificationRequest, UserNotificationSettings,
};
use redis::aio::ConnectionManager;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};
use wasmcloud_provider_sdk::Provider;

pub struct EmailProvider {
    client: Arc<ResendClient>,
    formatter: EmailFormatter,
    config: EmailConfig,
    metrics: Arc<RwLock<ProviderMetrics>>,
    circuit_breaker: Arc<CircuitBreaker>,
    rate_limiter: Arc<RateLimiter>,
    retry_policy: RetryPolicy,
    redis_conn: Arc<RwLock<ConnectionManager>>,
}

impl EmailProvider {
    pub async fn new(
        config: EmailConfig,
        redis_conn: ConnectionManager,
    ) -> Result<Self, ProviderError> {
        config.validate().map_err(|e| {
            ProviderError::InvalidConfiguration(format!("Config validation failed: {}", e))
        })?;

        let client = Arc::new(ResendClient::new(
            config.resend_api_key.clone(),
            config.resend_base_url.clone(),
            Some(config.default_from_name.clone()),
        ));

        let formatter = EmailFormatter::new();

        let circuit_breaker = Arc::new(CircuitBreaker::new(CircuitBreakerConfig {
            failure_threshold: 5,
            timeout_ms: 60000, // 60 seconds in milliseconds
            success_threshold: 3,
        }));

        let rate_limiter = Arc::new(RateLimiter::new(
            config.rate_limit_per_minute,
            config.rate_limit_per_minute / 2, // burst_capacity (half of requests_per_minute)
        ));

        let retry_policy = RetryPolicy::exponential(
            config.max_retries as usize,
            config.retry_delay_ms,
            5000, // max_delay_ms
        );

        let metrics = Arc::new(RwLock::new(ProviderMetrics {
            total_sent: 0,
            total_delivered: 0,
            total_failed: 0,
            total_retried: 0,
            avg_latency_ms: 0.0,
            p99_latency_ms: 0.0,
            circuit_breaker_trips: 0,
            last_error: None,
            last_error_time: None,
            last_activity: None,
            error_rate_percent: 0.0,
        }));

        Ok(Self {
            client,
            formatter,
            config,
            metrics,
            circuit_breaker,
            rate_limiter,
            retry_policy,
            redis_conn: Arc::new(RwLock::new(redis_conn)),
        })
    }

    /// Create provider from wasmCloud host data (for WADM deployment)
    ///
    /// Loads configuration from environment variables and creates provider instance.
    /// This is the entry point when deployed via wasmCloud/WADM.
    pub async fn from_host_data(
        _host_data: wasmcloud_provider_sdk::HostData,
    ) -> Result<Self, ProviderError> {
        info!("🌟 Creating Email Notification Provider from wasmCloud host data");

        // Load configuration from environment variables
        let config = EmailConfig::from_env().map_err(|e| {
            ProviderError::InvalidConfiguration(format!("Failed to load config: {}", e))
        })?;

        // Get Redis URL from environment
        let redis_url = std::env::var("REDIS_URL").map_err(|_| {
            ProviderError::InvalidConfiguration(
                "REDIS_URL environment variable is required".to_string(),
            )
        })?;

        // Create Redis connection
        let redis_client = redis::Client::open(redis_url.as_str()).map_err(|e| {
            ProviderError::InternalError(format!("Failed to create Redis client: {}", e))
        })?;

        let redis_conn = redis_client
            .get_tokio_connection_manager()
            .await
            .map_err(|e| {
                ProviderError::InternalError(format!("Failed to connect to Redis: {}", e))
            })?;

        // Create provider with loaded config
        Self::new(config, redis_conn).await
    }

    async fn load_user_settings(
        &self,
        user_id: &str,
    ) -> Result<UserNotificationSettings, ProviderError> {
        let mut conn = self.redis_conn.write().await;
        let key = format!("user_settings:{}", user_id);

        let data: String = redis::cmd("GET")
            .arg(&key)
            .query_async(&mut *conn)
            .await
            .map_err(|e| {
                error!("Failed to load user settings from Redis: {}", e);
                ProviderError::InternalError(format!("Redis error: {}", e))
            })?;

        serde_json::from_str(&data).map_err(|e| {
            error!("Failed to parse user settings: {}", e);
            ProviderError::InvalidConfiguration(format!("Invalid user settings: {}", e))
        })
    }

    async fn send_with_retry(
        &self,
        request: &NotificationRequest,
        settings: &UserNotificationSettings,
    ) -> Result<DeliveryStatus, ProviderError> {
        // Format the email
        let payload = self.formatter.format_message(request, settings)?;

        // Apply retry policy
        let mut last_error = None;
        for attempt in 0..=self.config.max_retries {
            if attempt > 0 {
                let delay = self.retry_policy.get_delay(attempt as usize);
                debug!("Retry attempt {} after {}ms delay", attempt, delay);
                tokio::time::sleep(tokio::time::Duration::from_millis(delay)).await;
            }

            match self.client.send(payload.clone()).await {
                Ok(response) => {
                    info!("Email sent successfully: {:?}", response.message_id);

                    return Ok(DeliveryStatus {
                        notification_id: request.notification_id,
                        channel: NotificationChannel::Email,
                        delivered: true,
                        delivered_at: Some(Utc::now()),
                        error_message: None,
                        provider_message_id: response.message_id,
                        retry_count: attempt,
                    });
                }
                Err(e) => {
                    warn!("Email send attempt {} failed: {:?}", attempt + 1, e);
                    last_error = Some(e);

                    // Don't retry on certain errors
                    if matches!(
                        last_error,
                        Some(ProviderError::InvalidAuthentication)
                            | Some(ProviderError::MalformedPayload(_))
                    ) {
                        break;
                    }
                }
            }
        }

        // All retries failed
        let error = last_error.unwrap_or(ProviderError::InternalError("Unknown error".to_string()));
        error!(
            "Email send failed after {} retries: {:?}",
            self.config.max_retries, error
        );

        Ok(DeliveryStatus {
            notification_id: request.notification_id,
            channel: NotificationChannel::Email,
            delivered: false,
            delivered_at: None,
            error_message: Some(error.to_string()),
            provider_message_id: None,
            retry_count: self.config.max_retries,
        })
    }
}

#[async_trait]
impl NotificationProvider for EmailProvider {
    fn channel(&self) -> NotificationChannel {
        NotificationChannel::Email
    }

    async fn send_notification(
        &self,
        request: NotificationRequest,
    ) -> Result<DeliveryStatus, ProviderError> {
        // Update metrics
        {
            let mut metrics = self.metrics.write().await;
            metrics.total_sent += 1;
        }

        // Check circuit breaker
        if !self.circuit_breaker.can_execute() {
            warn!("Circuit breaker is open, rejecting request");
            let mut metrics = self.metrics.write().await;
            metrics.total_failed += 1;
            metrics.circuit_breaker_trips += 1;
            return Err(ProviderError::ServiceUnavailable);
        }

        // Check rate limit
        if let Err(e) = self.rate_limiter.acquire_permit().await {
            warn!("Rate limit exceeded");
            let mut metrics = self.metrics.write().await;
            metrics.total_failed += 1;
            return Err(e);
        }

        // Load user settings
        let settings = self.load_user_settings(&request.user_id).await?;

        // Send with retry
        let start = Utc::now();
        let result = self.send_with_retry(&request, &settings).await;
        let duration = Utc::now().signed_duration_since(start).num_milliseconds() as f64;

        // Update metrics and circuit breaker
        {
            let mut metrics = self.metrics.write().await;

            // Update average latency
            let total_requests = metrics.total_sent;
            metrics.avg_latency_ms = (metrics.avg_latency_ms * (total_requests - 1) as f64
                + duration)
                / total_requests as f64;

            match &result {
                Ok(status) if status.delivered => {
                    metrics.total_delivered += 1;
                    self.circuit_breaker.record_success();
                }
                Ok(status) => {
                    metrics.total_failed += 1;
                    metrics.last_error = status.error_message.clone();
                    metrics.last_error_time = Some(Utc::now());
                    self.circuit_breaker.record_failure();
                }
                Err(e) => {
                    metrics.total_failed += 1;
                    metrics.last_error = Some(e.to_string());
                    metrics.last_error_time = Some(Utc::now());
                    self.circuit_breaker.record_failure();
                }
            }

            metrics.last_activity = Some(Utc::now());

            // Update error rate
            if metrics.total_sent > 0 {
                metrics.error_rate_percent =
                    (metrics.total_failed as f64 / metrics.total_sent as f64) * 100.0;
            }
        }

        result
    }

    async fn health_check(&self) -> Result<bool, ProviderError> {
        self.client.health_check().await
    }

    fn get_metrics(&self) -> ProviderMetrics {
        // This blocks briefly to get a consistent snapshot
        let metrics = self.metrics.blocking_read();
        metrics.clone()
    }
}

/// Provider trait implementation for wasmCloud SDK
///
/// Uses default implementations from the SDK since initialization happens in:
/// - from_host_data() - Called by wasmCloud deployment
/// - new() - Called for standalone usage
#[async_trait]
impl Provider for EmailProvider {
    // All methods use default implementations from wasmcloud-provider-sdk
    // The SDK manages the provider lifecycle automatically
}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider>() {}
        assert_provider::<EmailProvider>();
    }
}
