//! Circuit breaker implementation for endpoint health tracking
//!
//! Implements the circuit breaker pattern to prevent cascading failures when RPC endpoints
//! are unhealthy. The circuit can be in one of three states:
//! - Closed: Normal operation, requests flow through
//! - Open: Too many failures, reject requests immediately
//! - HalfOpen: Testing if endpoint has recovered
//!
//! Based on the classic pattern from Michael Nygard's "Release It!"

use anyhow::{anyhow, Result};
use parking_lot::RwLock;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tracing::{debug, info, warn};

/// Circuit breaker states
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CircuitState {
    /// Circuit is closed - requests flow normally
    Closed,
    /// Circuit is open - reject requests immediately to protect endpoint
    Open,
    /// Circuit is half-open - testing if endpoint has recovered
    HalfOpen,
}

/// Circuit breaker configuration
#[derive(Debug, Clone)]
pub struct CircuitBreakerConfig {
    /// Number of failures before opening the circuit
    pub failure_threshold: u32,

    /// Number of successes in half-open state before closing circuit
    pub success_threshold: u32,

    /// Duration to wait before transitioning from open to half-open
    pub timeout: Duration,

    /// Rolling window duration for failure counting
    pub window_duration: Duration,
}

impl Default for CircuitBreakerConfig {
    fn default() -> Self {
        Self {
            failure_threshold: 5,
            success_threshold: 2,
            timeout: Duration::from_secs(30),
            window_duration: Duration::from_secs(60),
        }
    }
}

/// Circuit breaker state tracking
#[derive(Debug)]
struct CircuitBreakerState {
    /// Current state
    state: CircuitState,

    /// Number of consecutive failures in current window
    failure_count: u32,

    /// Number of consecutive successes in half-open state
    success_count: u32,

    /// Last state transition time
    last_transition: Instant,

    /// Window start time for failure counting
    window_start: Instant,
}

impl Default for CircuitBreakerState {
    fn default() -> Self {
        let now = Instant::now();
        Self {
            state: CircuitState::Closed,
            failure_count: 0,
            success_count: 0,
            last_transition: now,
            window_start: now,
        }
    }
}

/// Circuit breaker for endpoint health management
pub struct CircuitBreaker {
    /// Endpoint URL
    endpoint: String,

    /// Configuration
    config: CircuitBreakerConfig,

    /// Internal state
    state: Arc<RwLock<CircuitBreakerState>>,
}

impl CircuitBreaker {
    /// Create a new circuit breaker for an endpoint
    pub fn new(endpoint: String, config: CircuitBreakerConfig) -> Self {
        Self {
            endpoint,
            config,
            state: Arc::new(RwLock::new(CircuitBreakerState::default())),
        }
    }

    /// Check if a request can proceed
    pub fn can_execute(&self) -> Result<()> {
        let mut state = self.state.write();

        match state.state {
            CircuitState::Closed => {
                // Reset window if expired
                if state.window_start.elapsed() > self.config.window_duration {
                    state.failure_count = 0;
                    state.window_start = Instant::now();
                }
                Ok(())
            }
            CircuitState::Open => {
                // Check if timeout has elapsed
                if state.last_transition.elapsed() > self.config.timeout {
                    // Transition to half-open for testing
                    state.state = CircuitState::HalfOpen;
                    state.success_count = 0;
                    state.last_transition = Instant::now();
                    info!(
                        "Circuit breaker for {} transitioning to HALF_OPEN",
                        self.endpoint
                    );
                    Ok(())
                } else {
                    Err(anyhow!(
                        "Circuit breaker is OPEN for endpoint: {}",
                        self.endpoint
                    ))
                }
            }
            CircuitState::HalfOpen => {
                // Allow limited testing traffic
                Ok(())
            }
        }
    }

    /// Record a successful request
    pub fn record_success(&self) {
        let mut state = self.state.write();

        match state.state {
            CircuitState::Closed => {
                // Reset failure count on success
                state.failure_count = 0;
            }
            CircuitState::HalfOpen => {
                state.success_count += 1;

                // Transition to closed if enough successes
                if state.success_count >= self.config.success_threshold {
                    state.state = CircuitState::Closed;
                    state.failure_count = 0;
                    state.success_count = 0;
                    state.last_transition = Instant::now();
                    state.window_start = Instant::now();
                    info!(
                        "Circuit breaker for {} transitioning to CLOSED (recovered)",
                        self.endpoint
                    );
                }
            }
            CircuitState::Open => {
                // Should not happen (can_execute should have blocked)
                warn!(
                    "Recorded success while circuit is OPEN for {}",
                    self.endpoint
                );
            }
        }
    }

    /// Record a failed request
    pub fn record_failure(&self) {
        let mut state = self.state.write();

        match state.state {
            CircuitState::Closed => {
                state.failure_count += 1;

                // Transition to open if threshold exceeded
                if state.failure_count >= self.config.failure_threshold {
                    state.state = CircuitState::Open;
                    state.last_transition = Instant::now();
                    warn!(
                        "Circuit breaker for {} transitioning to OPEN ({} failures)",
                        self.endpoint, state.failure_count
                    );
                }
            }
            CircuitState::HalfOpen => {
                // Single failure in half-open immediately opens circuit
                state.state = CircuitState::Open;
                state.failure_count = self.config.failure_threshold; // Ensure we stay open
                state.success_count = 0;
                state.last_transition = Instant::now();
                warn!(
                    "Circuit breaker for {} transitioning to OPEN (half-open test failed)",
                    self.endpoint
                );
            }
            CircuitState::Open => {
                // Already open, just increment failure count
                state.failure_count += 1;
            }
        }
    }

    /// Get current circuit state
    pub fn state(&self) -> CircuitState {
        self.state.read().state
    }

    /// Get endpoint URL
    pub fn endpoint(&self) -> &str {
        &self.endpoint
    }

    /// Force reset to closed state (for testing)
    pub fn reset(&self) {
        let mut state = self.state.write();
        *state = CircuitBreakerState::default();
        debug!(
            "Circuit breaker for {} has been reset to CLOSED",
            self.endpoint
        );
    }

    /// Get failure count
    pub fn failure_count(&self) -> u32 {
        self.state.read().failure_count
    }

    /// Get success count (relevant in half-open state)
    pub fn success_count(&self) -> u32 {
        self.state.read().success_count
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_circuit_breaker_creation() {
        let cb = CircuitBreaker::new(
            "http://example.com".to_string(),
            CircuitBreakerConfig::default(),
        );

        assert_eq!(cb.state(), CircuitState::Closed);
        assert_eq!(cb.failure_count(), 0);
        assert_eq!(cb.success_count(), 0);
    }

    #[test]
    fn test_circuit_opens_after_threshold() {
        let mut config = CircuitBreakerConfig::default();
        config.failure_threshold = 3;

        let cb = CircuitBreaker::new("http://example.com".to_string(), config);

        assert_eq!(cb.state(), CircuitState::Closed);

        // Record failures
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Closed);
        assert_eq!(cb.failure_count(), 1);

        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Closed);
        assert_eq!(cb.failure_count(), 2);

        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);
        assert_eq!(cb.failure_count(), 3);
    }

    #[test]
    fn test_circuit_rejects_when_open() {
        let mut config = CircuitBreakerConfig::default();
        config.failure_threshold = 1;

        let cb = CircuitBreaker::new("http://example.com".to_string(), config);

        // Trigger open state
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);

        // Should reject execution
        let result = cb.can_execute();
        assert!(result.is_err());
    }

    #[test]
    fn test_circuit_half_open_recovery() {
        let mut config = CircuitBreakerConfig::default();
        config.failure_threshold = 1;
        config.success_threshold = 2;

        let cb = CircuitBreaker::new("http://example.com".to_string(), config);

        // Open the circuit
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);

        // Force transition to half-open (in real code this happens after timeout)
        {
            let mut state = cb.state.write();
            state.state = CircuitState::HalfOpen;
            state.success_count = 0;
        }

        assert_eq!(cb.state(), CircuitState::HalfOpen);

        // Record successes
        cb.record_success();
        assert_eq!(cb.state(), CircuitState::HalfOpen);
        assert_eq!(cb.success_count(), 1);

        cb.record_success();
        assert_eq!(cb.state(), CircuitState::Closed); // Should close
        assert_eq!(cb.failure_count(), 0);
    }

    #[test]
    fn test_circuit_half_open_failure() {
        let mut config = CircuitBreakerConfig::default();
        config.failure_threshold = 1;

        let cb = CircuitBreaker::new("http://example.com".to_string(), config);

        // Open the circuit
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);

        // Force transition to half-open
        {
            let mut state = cb.state.write();
            state.state = CircuitState::HalfOpen;
        }

        assert_eq!(cb.state(), CircuitState::HalfOpen);

        // Record failure - should immediately open
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);
    }

    #[test]
    fn test_reset() {
        let cb = CircuitBreaker::new(
            "http://example.com".to_string(),
            CircuitBreakerConfig::default(),
        );

        // Open the circuit
        for _ in 0..5 {
            cb.record_failure();
        }
        assert_eq!(cb.state(), CircuitState::Open);

        // Reset
        cb.reset();
        assert_eq!(cb.state(), CircuitState::Closed);
        assert_eq!(cb.failure_count(), 0);
    }
}
