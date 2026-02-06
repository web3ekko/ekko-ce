//! Retry logic and backoff strategies for notification providers
//!
//! This module provides standardized retry mechanisms with exponential backoff
//! for handling transient failures in notification delivery.

use backoff::{backoff::Backoff, ExponentialBackoff};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, warn};

/// Configuration for retry behavior
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetryConfig {
    pub max_attempts: u32,
    pub initial_delay_ms: u64,
    pub max_delay_ms: u64,
    pub exponential_base: f64,
    pub jitter: bool,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            initial_delay_ms: 1000, // 1 second
            max_delay_ms: 30000,    // 30 seconds
            exponential_base: 2.0,
            jitter: true,
        }
    }
}

impl RetryConfig {
    /// Create a new retry config with custom settings
    pub fn new(max_attempts: u32, initial_delay_ms: u64, max_delay_ms: u64) -> Self {
        Self {
            max_attempts,
            initial_delay_ms,
            max_delay_ms,
            exponential_base: 2.0,
            jitter: true,
        }
    }

    /// Create a config for critical notifications (more aggressive retries)
    pub fn critical() -> Self {
        Self {
            max_attempts: 5,
            initial_delay_ms: 500, // 0.5 seconds
            max_delay_ms: 60000,   // 1 minute
            exponential_base: 1.5,
            jitter: true,
        }
    }

    /// Create a config for low-priority notifications (fewer retries)
    pub fn low_priority() -> Self {
        Self {
            max_attempts: 2,
            initial_delay_ms: 5000, // 5 seconds
            max_delay_ms: 15000,    // 15 seconds
            exponential_base: 2.0,
            jitter: true,
        }
    }

    /// Create a config with no retries (fire-and-forget)
    pub fn no_retry() -> Self {
        Self {
            max_attempts: 1,
            initial_delay_ms: 0,
            max_delay_ms: 0,
            exponential_base: 1.0,
            jitter: false,
        }
    }

    /// Get the appropriate retry config based on notification priority
    pub fn for_priority(priority: &crate::NotificationPriority) -> Self {
        match priority {
            crate::NotificationPriority::Critical => Self::critical(),
            crate::NotificationPriority::High => Self::default(),
            crate::NotificationPriority::Medium => Self::default(),
            crate::NotificationPriority::Normal => Self::default(),
            crate::NotificationPriority::Low => Self::low_priority(),
        }
    }

    /// Convert to exponential backoff configuration
    fn to_exponential_backoff(&self) -> ExponentialBackoff {
        let mut backoff = ExponentialBackoff {
            initial_interval: Duration::from_millis(self.initial_delay_ms),
            max_interval: Duration::from_millis(self.max_delay_ms),
            multiplier: self.exponential_base,
            max_elapsed_time: None,
            ..Default::default()
        };

        if !self.jitter {
            backoff.randomization_factor = 0.0;
        }

        backoff
    }
}

/// Retry an async operation with exponential backoff
pub async fn retry_with_backoff<F, T, E>(config: &RetryConfig, operation: F) -> Result<T, E>
where
    F: Fn() -> futures::future::BoxFuture<'static, Result<T, E>>,
    E: std::fmt::Debug + IsRetryable,
{
    if config.max_attempts <= 1 {
        debug!("No retry configured, executing operation once");
        return operation().await;
    }

    let mut backoff = config.to_exponential_backoff();
    let mut attempt = 1;

    loop {
        debug!("Retry attempt {} of {}", attempt, config.max_attempts);

        match operation().await {
            Ok(result) => {
                if attempt > 1 {
                    debug!("Operation succeeded after {} attempts", attempt);
                }
                return Ok(result);
            }
            Err(error) => {
                // Check if we should retry
                if attempt >= config.max_attempts || !error.is_retryable() {
                    warn!(
                        "Operation failed after {} attempts, error: {:?}",
                        attempt, error
                    );
                    return Err(error);
                }

                // Calculate delay for next attempt
                if let Some(delay) = backoff.next_backoff() {
                    warn!(
                        "Operation failed (attempt {}/{}), retrying in {:?}. Error: {:?}",
                        attempt, config.max_attempts, delay, error
                    );

                    tokio::time::sleep(delay).await;
                    attempt += 1;
                } else {
                    warn!("Backoff exhausted after {} attempts", attempt);
                    return Err(error);
                }
            }
        }
    }
}

/// Trait to determine if an error is retryable
pub trait IsRetryable {
    fn is_retryable(&self) -> bool;
}

impl IsRetryable for crate::provider::LegacyProviderError {
    fn is_retryable(&self) -> bool {
        match self {
            crate::provider::LegacyProviderError::ConnectionError(_) => true,
            crate::provider::LegacyProviderError::TimeoutError(_) => true,
            crate::provider::LegacyProviderError::ExternalServiceError(_) => true,
            crate::provider::LegacyProviderError::HttpError(_) => true,
            crate::provider::LegacyProviderError::RedisError(_) => true,
            crate::provider::LegacyProviderError::NatsError(_) => true,
            crate::provider::LegacyProviderError::RateLimitExceeded(_) => true,
            // These errors are not retryable
            crate::provider::LegacyProviderError::ConfigurationError(_) => false,
            crate::provider::LegacyProviderError::AuthenticationError(_) => false,
            crate::provider::LegacyProviderError::InvalidChannel { .. } => false,
            crate::provider::LegacyProviderError::ValidationFailed(_) => false,
            crate::provider::LegacyProviderError::SerializationError(_) => false,
            crate::provider::LegacyProviderError::TemplateError(_) => false,
            crate::provider::LegacyProviderError::Unknown(_) => false,
        }
    }
}

/// Retry with custom condition checking
pub async fn retry_with_condition<F, T, E, C>(
    config: &RetryConfig,
    operation: F,
    should_retry: C,
) -> Result<T, E>
where
    F: Fn() -> futures::future::BoxFuture<'static, Result<T, E>>,
    C: Fn(&E) -> bool,
    E: std::fmt::Debug,
{
    if config.max_attempts <= 1 {
        debug!("No retry configured, executing operation once");
        return operation().await;
    }

    let mut backoff = config.to_exponential_backoff();
    let mut attempt = 1;

    loop {
        debug!("Retry attempt {} of {}", attempt, config.max_attempts);

        match operation().await {
            Ok(result) => {
                if attempt > 1 {
                    debug!("Operation succeeded after {} attempts", attempt);
                }
                return Ok(result);
            }
            Err(error) => {
                // Check if we should retry using custom condition
                if attempt >= config.max_attempts || !should_retry(&error) {
                    warn!(
                        "Operation failed after {} attempts, error: {:?}",
                        attempt, error
                    );
                    return Err(error);
                }

                // Calculate delay for next attempt
                if let Some(delay) = backoff.next_backoff() {
                    warn!(
                        "Operation failed (attempt {}/{}), retrying in {:?}. Error: {:?}",
                        attempt, config.max_attempts, delay, error
                    );

                    tokio::time::sleep(delay).await;
                    attempt += 1;
                } else {
                    warn!("Backoff exhausted after {} attempts", attempt);
                    return Err(error);
                }
            }
        }
    }
}

/// Circuit breaker state for preventing cascading failures
#[derive(Debug, Clone)]
pub struct CircuitBreakerConfig {
    pub failure_threshold: u32,
    pub success_threshold: u32,
    pub timeout_ms: u64,
}

impl Default for CircuitBreakerConfig {
    fn default() -> Self {
        Self {
            failure_threshold: 5, // Open circuit after 5 failures
            success_threshold: 3, // Close circuit after 3 successes
            timeout_ms: 60000,    // 1 minute timeout
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum CircuitState {
    Closed,
    Open,
    HalfOpen,
}

/// Simple circuit breaker implementation
pub struct CircuitBreaker {
    config: CircuitBreakerConfig,
    state: CircuitState,
    failure_count: u32,
    success_count: u32,
    last_failure_time: Option<std::time::Instant>,
}

impl CircuitBreaker {
    pub fn new(config: CircuitBreakerConfig) -> Self {
        Self {
            config,
            state: CircuitState::Closed,
            failure_count: 0,
            success_count: 0,
            last_failure_time: None,
        }
    }

    pub fn can_execute(&mut self) -> bool {
        match self.state {
            CircuitState::Closed => true,
            CircuitState::HalfOpen => true,
            CircuitState::Open => {
                // Check if timeout has elapsed
                if let Some(last_failure) = self.last_failure_time {
                    if last_failure.elapsed().as_millis() > self.config.timeout_ms as u128 {
                        debug!("Circuit breaker timeout elapsed, moving to half-open");
                        self.state = CircuitState::HalfOpen;
                        self.success_count = 0;
                        true
                    } else {
                        false
                    }
                } else {
                    false
                }
            }
        }
    }

    pub fn record_success(&mut self) {
        match self.state {
            CircuitState::Closed => {
                self.failure_count = 0;
            }
            CircuitState::HalfOpen => {
                self.success_count += 1;
                if self.success_count >= self.config.success_threshold {
                    debug!(
                        "Circuit breaker closing after {} successes",
                        self.success_count
                    );
                    self.state = CircuitState::Closed;
                    self.failure_count = 0;
                    self.success_count = 0;
                }
            }
            CircuitState::Open => {
                // Should not happen, but reset if it does
                self.state = CircuitState::Closed;
                self.failure_count = 0;
                self.success_count = 0;
            }
        }
    }

    pub fn record_failure(&mut self) {
        self.failure_count += 1;
        self.last_failure_time = Some(std::time::Instant::now());

        match self.state {
            CircuitState::Closed | CircuitState::HalfOpen => {
                if self.failure_count >= self.config.failure_threshold {
                    warn!(
                        "Circuit breaker opening after {} failures",
                        self.failure_count
                    );
                    self.state = CircuitState::Open;
                }
            }
            CircuitState::Open => {
                // Already open, do nothing
            }
        }
    }

    pub fn state(&self) -> &CircuitState {
        &self.state
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::Arc;
    use tokio_test;

    #[derive(Debug)]
    struct TestError {
        retryable: bool,
    }

    impl IsRetryable for TestError {
        fn is_retryable(&self) -> bool {
            self.retryable
        }
    }

    #[tokio::test]
    async fn test_retry_success_after_failure() {
        let config = RetryConfig::new(3, 10, 1000); // Fast retry for testing
        let attempt_count = Arc::new(AtomicU32::new(0));

        let operation = || {
            let count = attempt_count.clone();
            Box::pin(async move {
                let current = count.fetch_add(1, Ordering::SeqCst) + 1;
                if current < 3 {
                    Err(TestError { retryable: true })
                } else {
                    Ok(current)
                }
            }) as futures::future::BoxFuture<'static, Result<u32, TestError>>
        };

        let result = retry_with_backoff(&config, operation).await;
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 3);
        assert_eq!(attempt_count.load(Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn test_retry_failure_not_retryable() {
        let config = RetryConfig::new(3, 10, 1000);
        let attempt_count = Arc::new(AtomicU32::new(0));

        let operation = || {
            let count = attempt_count.clone();
            Box::pin(async move {
                count.fetch_add(1, Ordering::SeqCst);
                Err::<(), TestError>(TestError { retryable: false })
            }) as futures::future::BoxFuture<'static, Result<(), TestError>>
        };

        let result: Result<(), TestError> = retry_with_backoff(&config, operation).await;
        assert!(result.is_err());
        assert_eq!(attempt_count.load(Ordering::SeqCst), 1); // Only one attempt
    }

    #[tokio::test]
    async fn test_circuit_breaker() {
        let mut breaker = CircuitBreaker::new(CircuitBreakerConfig {
            failure_threshold: 2,
            success_threshold: 2,
            timeout_ms: 100,
        });

        // Should allow execution initially
        assert!(breaker.can_execute());
        assert_eq!(breaker.state(), &CircuitState::Closed);

        // Record failures to open circuit
        breaker.record_failure();
        assert!(breaker.can_execute());
        assert_eq!(breaker.state(), &CircuitState::Closed);

        breaker.record_failure();
        assert_eq!(breaker.state(), &CircuitState::Open);
        assert!(!breaker.can_execute());

        // Wait for timeout
        tokio::time::sleep(Duration::from_millis(150)).await;
        assert!(breaker.can_execute());
        assert_eq!(breaker.state(), &CircuitState::HalfOpen);

        // Record successes to close circuit
        breaker.record_success();
        assert_eq!(breaker.state(), &CircuitState::HalfOpen);

        breaker.record_success();
        assert_eq!(breaker.state(), &CircuitState::Closed);
    }
}
