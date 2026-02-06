//! Shared types and utilities for Ekko notification providers
//!
//! This library provides common types, interfaces, and utilities used across
//! all notification providers in the Ekko cluster system.

pub mod metrics;
pub mod nats;
pub mod payloads;
pub mod provider;
pub mod provider_base;
pub mod redis;
pub mod retry;
pub mod types;
pub mod validation;

#[cfg(test)]
pub mod test_utilities;

// Re-export commonly used types
pub use payloads::*;
pub use types::*;
// Export the modern provider interface (provider_base)
pub use provider_base::{
    retry_with_backoff as retry_with_backoff_v2, CircuitBreaker, CircuitBreakerConfig,
    ExternalClient, MessageFormatter, NotificationProvider, ProviderError, ProviderMetrics,
    RateLimiter, RetryPolicy,
};
// Legacy provider exports (kept for compatibility)
pub use metrics::*;
pub use nats::NatsHandler;
pub use provider::{
    LegacyNotificationProvider, LegacyProviderError, ProviderFactory, ProviderRegistry,
    ProviderUtils,
};
pub use redis::RedisClient;
pub use retry::{retry_with_backoff, RetryConfig};
pub use validation::*;
