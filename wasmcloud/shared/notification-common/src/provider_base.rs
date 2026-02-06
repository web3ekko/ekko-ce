use async_trait::async_trait;
use chrono::{DateTime, Duration, Utc};
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use thiserror::Error;

use crate::payloads::{DeliveryStatus, NotificationRequest};
use crate::types::{NotificationChannel, NotificationPriority, UserNotificationSettings};

/// Base trait that all notification providers must implement
#[async_trait]
pub trait NotificationProvider: Send + Sync {
    /// Get the channel this provider handles
    fn channel(&self) -> NotificationChannel;

    /// Send a notification through this provider
    async fn send_notification(
        &self,
        request: NotificationRequest,
    ) -> Result<DeliveryStatus, ProviderError>;

    /// Check if the provider is healthy
    async fn health_check(&self) -> Result<bool, ProviderError>;

    /// Get provider metrics
    fn get_metrics(&self) -> ProviderMetrics;
}

/// External service client trait that providers use to send notifications
#[async_trait]
pub trait ExternalClient: Send + Sync {
    type Payload: Send + Sync;
    type Response: Send + Sync;

    /// Send a notification to the external service
    async fn send(&self, payload: Self::Payload) -> Result<Self::Response, ProviderError>;

    /// Check if the external service is healthy
    async fn health_check(&self) -> Result<bool, ProviderError>;

    /// Check if the service supports batch sending
    fn supports_batch(&self) -> bool {
        false
    }

    /// Send multiple notifications in a batch
    async fn send_batch(
        &self,
        payloads: Vec<Self::Payload>,
    ) -> Result<Vec<Self::Response>, ProviderError> {
        // Default implementation sends individually
        let mut responses = Vec::new();
        for payload in payloads {
            responses.push(self.send(payload).await?);
        }
        Ok(responses)
    }
}

/// Message formatter trait for converting notifications to provider-specific formats
pub trait MessageFormatter<T> {
    /// Format a notification request into provider-specific payload
    fn format_message(
        &self,
        request: &NotificationRequest,
        settings: &UserNotificationSettings,
    ) -> Result<T, ProviderError>;

    /// Validate that a payload is valid for sending
    fn validate_payload(&self, payload: &T) -> Result<(), ProviderError>;

    /// Get the channel this formatter is for
    fn channel(&self) -> NotificationChannel;
}

/// Circuit breaker for handling provider failures
#[derive(Debug, Clone)]
pub struct CircuitBreaker {
    state: Arc<Mutex<CircuitBreakerState>>,
    config: CircuitBreakerConfig,
}

#[derive(Debug, Clone)]
enum CircuitBreakerState {
    Closed { failure_count: u32 },
    Open { opened_at: DateTime<Utc> },
    HalfOpen { success_count: u32 },
}

#[derive(Debug, Clone, Deserialize)]
pub struct CircuitBreakerConfig {
    /// Number of failures before opening the circuit
    pub failure_threshold: u32,
    /// How long to wait before trying again (milliseconds)
    pub timeout_ms: u64,
    /// Number of successes needed to close from half-open
    pub success_threshold: u32,
}

impl Default for CircuitBreakerConfig {
    fn default() -> Self {
        Self {
            failure_threshold: 5,
            timeout_ms: 60000, // 1 minute
            success_threshold: 3,
        }
    }
}

impl CircuitBreaker {
    pub fn new(config: CircuitBreakerConfig) -> Self {
        Self {
            state: Arc::new(Mutex::new(CircuitBreakerState::Closed { failure_count: 0 })),
            config,
        }
    }

    /// Check if the circuit breaker allows execution
    pub fn can_execute(&self) -> bool {
        let mut state = self.state.lock();

        match *state {
            CircuitBreakerState::Closed { .. } => true,
            CircuitBreakerState::Open { opened_at } => {
                let timeout = Duration::milliseconds(self.config.timeout_ms as i64);
                if Utc::now() - opened_at > timeout {
                    *state = CircuitBreakerState::HalfOpen { success_count: 0 };
                    true
                } else {
                    false
                }
            }
            CircuitBreakerState::HalfOpen { .. } => true,
        }
    }

    /// Record a successful execution
    pub fn record_success(&self) {
        let mut state = self.state.lock();

        match *state {
            CircuitBreakerState::HalfOpen { success_count } => {
                if success_count + 1 >= self.config.success_threshold {
                    *state = CircuitBreakerState::Closed { failure_count: 0 };
                } else {
                    *state = CircuitBreakerState::HalfOpen {
                        success_count: success_count + 1,
                    };
                }
            }
            CircuitBreakerState::Closed { .. } => {
                *state = CircuitBreakerState::Closed { failure_count: 0 };
            }
            _ => {}
        }
    }

    /// Record a failed execution
    pub fn record_failure(&self) {
        let mut state = self.state.lock();

        match *state {
            CircuitBreakerState::Closed { failure_count } => {
                if failure_count + 1 >= self.config.failure_threshold {
                    *state = CircuitBreakerState::Open {
                        opened_at: Utc::now(),
                    };
                } else {
                    *state = CircuitBreakerState::Closed {
                        failure_count: failure_count + 1,
                    };
                }
            }
            CircuitBreakerState::HalfOpen { .. } => {
                *state = CircuitBreakerState::Open {
                    opened_at: Utc::now(),
                };
            }
            _ => {}
        }
    }

    /// Get the current state
    pub fn get_state(&self) -> String {
        let state = self.state.lock();
        match *state {
            CircuitBreakerState::Closed { failure_count } => {
                format!("closed (failures: {})", failure_count)
            }
            CircuitBreakerState::Open { opened_at } => {
                format!("open (since: {})", opened_at)
            }
            CircuitBreakerState::HalfOpen { success_count } => {
                format!("half-open (successes: {})", success_count)
            }
        }
    }
}

/// Retry configuration for providers
#[derive(Debug, Clone, Deserialize)]
pub struct RetryConfig {
    /// Maximum number of retry attempts
    pub max_attempts: u32,
    /// Initial delay in milliseconds
    pub initial_delay_ms: u64,
    /// Maximum delay in milliseconds
    pub max_delay_ms: u64,
    /// Exponential backoff multiplier
    pub backoff_multiplier: f32,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            initial_delay_ms: 1000,
            max_delay_ms: 30000,
            backoff_multiplier: 2.0,
        }
    }
}

/// Provider error types
#[derive(Debug, Error)]
pub enum ProviderError {
    // Retryable errors
    #[error("Rate limit exceeded, retry after {retry_after:?}")]
    RateLimitExceeded { retry_after: Duration },

    #[error("Network timeout")]
    NetworkTimeout,

    #[error("Service unavailable")]
    ServiceUnavailable,

    #[error("Temporary failure: {message}")]
    TemporaryFailure { message: String },

    // Non-retryable errors
    #[error("Invalid API key or authentication")]
    InvalidAuthentication,

    #[error("Malformed payload: {0}")]
    MalformedPayload(String),

    #[error("Invalid configuration: {0}")]
    InvalidConfiguration(String),

    #[error("Channel disabled for user")]
    ChannelDisabled,

    #[error("Permanent failure: {message}")]
    PermanentFailure { message: String },

    // System errors
    #[error("Redis error: {0}")]
    RedisError(String),

    #[error("NATS error: {0}")]
    NatsError(String),

    #[error("Circuit breaker open")]
    CircuitBreakerOpen,

    #[error("Network error: {0}")]
    NetworkError(String),

    #[error("Internal error: {0}")]
    InternalError(String),

    #[error("External service error: {0}")]
    ExternalServiceError(String),

    #[error("Unknown error: {0}")]
    Unknown(String),
}

impl ProviderError {
    /// Check if this error is retryable
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            ProviderError::RateLimitExceeded { .. }
                | ProviderError::NetworkTimeout
                | ProviderError::ServiceUnavailable
                | ProviderError::TemporaryFailure { .. }
        )
    }

    /// Get retry delay if applicable
    pub fn retry_delay(&self) -> Option<Duration> {
        match self {
            ProviderError::RateLimitExceeded { retry_after } => Some(*retry_after),
            ProviderError::NetworkTimeout | ProviderError::ServiceUnavailable => {
                Some(Duration::seconds(5))
            }
            ProviderError::TemporaryFailure { .. } => Some(Duration::seconds(10)),
            _ => None,
        }
    }
}

/// Provider metrics for monitoring
#[derive(Debug, Clone, Default, Serialize)]
pub struct ProviderMetrics {
    pub total_sent: u64,
    pub total_delivered: u64,
    pub total_failed: u64,
    pub total_retried: u64,
    pub avg_latency_ms: f64,
    pub p99_latency_ms: f64,
    pub circuit_breaker_trips: u64,
    pub last_error: Option<String>,
    pub last_error_time: Option<DateTime<Utc>>,
    pub last_activity: Option<DateTime<Utc>>,
    pub error_rate_percent: f64,
}

/// Retry policy for handling failures
#[derive(Debug, Clone)]
pub struct RetryPolicy {
    pub max_retries: usize,
    pub initial_delay_ms: u64,
    pub max_delay_ms: u64,
    pub exponential_base: f64,
}

impl RetryPolicy {
    pub fn exponential(max_retries: usize, initial_delay_ms: u64, max_delay_ms: u64) -> Self {
        Self {
            max_retries,
            initial_delay_ms,
            max_delay_ms,
            exponential_base: 2.0,
        }
    }

    pub fn get_delay(&self, attempt: usize) -> u64 {
        let exponential_delay =
            self.initial_delay_ms * (self.exponential_base.powi(attempt as i32) as u64);
        exponential_delay.min(self.max_delay_ms)
    }
}

/// Rate limiter for external API calls
pub struct RateLimiter {
    requests_per_minute: u32,
    burst_capacity: u32,
    tokens: Arc<Mutex<f32>>,
    last_refill: Arc<Mutex<DateTime<Utc>>>,
}

impl RateLimiter {
    pub fn new(requests_per_minute: u32, burst_capacity: u32) -> Self {
        Self {
            requests_per_minute,
            burst_capacity,
            tokens: Arc::new(Mutex::new(burst_capacity as f32)),
            last_refill: Arc::new(Mutex::new(Utc::now())),
        }
    }

    /// Try to acquire a permit to make a request
    pub async fn acquire_permit(&self) -> Result<(), ProviderError> {
        let mut tokens = self.tokens.lock();
        let mut last_refill = self.last_refill.lock();

        // Refill tokens based on elapsed time
        let now = Utc::now();
        let elapsed = (now - *last_refill).num_seconds() as f32;
        let refill_rate = self.requests_per_minute as f32 / 60.0;
        let new_tokens = elapsed * refill_rate;

        *tokens = (*tokens + new_tokens).min(self.burst_capacity as f32);
        *last_refill = now;

        if *tokens >= 1.0 {
            *tokens -= 1.0;
            Ok(())
        } else {
            let wait_time = (1.0 - *tokens) / refill_rate;
            Err(ProviderError::RateLimitExceeded {
                retry_after: Duration::seconds(wait_time.ceil() as i64),
            })
        }
    }
}

/// Helper function to perform exponential backoff retry
pub async fn retry_with_backoff<F, T, Fut>(
    operation: F,
    config: &RetryConfig,
) -> Result<T, ProviderError>
where
    F: Fn() -> Fut,
    Fut: std::future::Future<Output = Result<T, ProviderError>>,
{
    let mut attempt = 0;
    let mut delay = config.initial_delay_ms;

    loop {
        match operation().await {
            Ok(result) => return Ok(result),
            Err(err) if !err.is_retryable() => return Err(err),
            Err(err) if attempt >= config.max_attempts - 1 => return Err(err),
            Err(err) => {
                attempt += 1;

                // Use error-specific delay if available
                let sleep_duration = err
                    .retry_delay()
                    .unwrap_or_else(|| Duration::milliseconds(delay as i64));

                tokio::time::sleep(sleep_duration.to_std().unwrap()).await;

                // Calculate next delay with exponential backoff
                delay = (delay as f32 * config.backoff_multiplier) as u64;
                delay = delay.min(config.max_delay_ms);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_circuit_breaker_opens_after_threshold() {
        let config = CircuitBreakerConfig {
            failure_threshold: 3,
            timeout_ms: 1000,
            success_threshold: 2,
        };
        let breaker = CircuitBreaker::new(config);

        assert!(breaker.can_execute());

        // Record failures up to threshold
        breaker.record_failure();
        assert!(breaker.can_execute());
        breaker.record_failure();
        assert!(breaker.can_execute());
        breaker.record_failure();

        // Circuit should now be open
        assert!(!breaker.can_execute());
        assert!(breaker.get_state().starts_with("open"));
    }

    #[test]
    fn test_circuit_breaker_half_open_recovery() {
        let config = CircuitBreakerConfig {
            failure_threshold: 2,
            timeout_ms: 10, // Short timeout for testing
            success_threshold: 2,
        };
        let breaker = CircuitBreaker::new(config);

        // Open the circuit
        breaker.record_failure();
        breaker.record_failure();
        assert!(!breaker.can_execute());

        // Wait for timeout
        std::thread::sleep(std::time::Duration::from_millis(15));

        // Should be half-open now
        assert!(breaker.can_execute());
        assert!(breaker.get_state().starts_with("half-open"));

        // Record successes to close
        breaker.record_success();
        breaker.record_success();
        assert!(breaker.get_state().starts_with("closed"));
    }

    #[test]
    fn test_rate_limiter() {
        let limiter = RateLimiter::new(60, 10);

        // Should allow initial burst
        for _ in 0..10 {
            assert!(
                tokio_test::block_on(limiter.acquire_permit()).is_ok(),
                "Should allow burst capacity"
            );
        }

        // Should be rate limited after burst
        assert!(
            tokio_test::block_on(limiter.acquire_permit()).is_err(),
            "Should be rate limited after burst"
        );
    }

    #[test]
    fn test_error_retryable_classification() {
        assert!(ProviderError::NetworkTimeout.is_retryable());
        assert!(ProviderError::ServiceUnavailable.is_retryable());
        assert!(ProviderError::TemporaryFailure {
            message: "test".to_string()
        }
        .is_retryable());

        assert!(!ProviderError::InvalidAuthentication.is_retryable());
        assert!(!ProviderError::MalformedPayload("test".to_string()).is_retryable());
        assert!(!ProviderError::ChannelDisabled.is_retryable());
    }
}
