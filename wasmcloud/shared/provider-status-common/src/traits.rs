//! Traits for provider status tracking.
//!
//! The `StatusTracker` trait defines the interface that providers implement
//! to report their status, which is then persisted to Redis and exported
//! via OpenTelemetry metrics.

use crate::types::{ProviderStatus, ProviderType, SubscriptionStatus};
use async_trait::async_trait;

/// Trait for tracking provider status with Redis persistence and OTEL metrics.
///
/// Providers implement this trait to report their operational status.
/// The tracker handles:
/// - In-memory state management
/// - Batched Redis persistence (every 5 seconds for high-frequency updates)
/// - Immediate Redis writes for critical state changes
/// - OTEL metric emission (when enabled)
///
/// # Example
///
/// ```ignore
/// use provider_status_common::{StatusTracker, ProviderStatusTracker};
///
/// let tracker = ProviderStatusTracker::new(
///     "newheads-evm-instance-1",
///     ProviderType::Evm,
///     "1.0.0",
///     redis_url,
/// ).await?;
///
/// // Record block received
/// tracker.record_block_received("ethereum-mainnet", 19000000, 150).await;
///
/// // Record connection change
/// tracker.record_connection_change("ethereum-mainnet", true).await;
///
/// // Record error
/// tracker.record_error(
///     Some("ethereum-mainnet"),
///     "WebSocket connection timeout",
///     true // recoverable
/// ).await;
/// ```
#[async_trait]
pub trait StatusTracker: Send + Sync {
    /// Record that a block was received from a chain.
    ///
    /// This is a high-frequency operation. Updates are buffered in memory
    /// and batched to Redis every 5 seconds to minimize overhead.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier (e.g., "ethereum-mainnet")
    /// * `block_number` - Block number/height
    /// * `latency_ms` - Latency from block timestamp to receipt in milliseconds
    async fn record_block_received(&self, chain_id: &str, block_number: u64, latency_ms: u32);

    /// Record a connection state change.
    ///
    /// This is a critical operation. Updates are written to Redis immediately
    /// to ensure accurate state visibility.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier
    /// * `connected` - Whether now connected (true) or disconnected (false)
    async fn record_connection_change(&self, chain_id: &str, connected: bool);

    /// Record an error occurrence.
    ///
    /// Errors are written to Redis immediately and added to error history.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier if error is chain-specific, None for provider-level errors
    /// * `error` - Error message
    /// * `recoverable` - Whether this error is considered recoverable
    async fn record_error(&self, chain_id: Option<&str>, error: &str, recoverable: bool);

    /// Record that a reconnection attempt is starting.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier
    /// * `attempt` - Reconnection attempt number
    async fn record_reconnect_attempt(&self, chain_id: &str, attempt: u32);

    /// Register a new chain subscription.
    ///
    /// Called when a provider starts monitoring a new chain.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier
    /// * `chain_name` - Human-readable chain name
    async fn register_subscription(&self, chain_id: &str, chain_name: &str);

    /// Unregister a chain subscription.
    ///
    /// Called when a provider stops monitoring a chain.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier
    async fn unregister_subscription(&self, chain_id: &str);

    /// Get the current provider status snapshot.
    ///
    /// Returns the current in-memory status. Note that Redis may have
    /// slightly stale data due to batched writes.
    fn get_status(&self) -> ProviderStatus;

    /// Get status for a specific subscription.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier
    fn get_subscription_status(&self, chain_id: &str) -> Option<SubscriptionStatus>;

    /// Check if the provider is healthy.
    ///
    /// A provider is healthy if at least one subscription is active.
    fn is_healthy(&self) -> bool;

    /// Check if a specific chain subscription is connected.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier
    fn is_chain_connected(&self, chain_id: &str) -> bool;

    /// Force an immediate flush of buffered updates to Redis.
    ///
    /// Normally updates are batched, but this forces immediate persistence.
    /// Useful before shutdown or when immediate consistency is required.
    async fn flush(&self) -> anyhow::Result<()>;

    /// Shutdown the tracker gracefully.
    ///
    /// Flushes pending updates and releases resources.
    async fn shutdown(&self) -> anyhow::Result<()>;
}

/// Configuration for StatusTracker initialization
#[derive(Debug, Clone)]
pub struct StatusTrackerConfig {
    /// Unique provider instance ID
    pub provider_id: String,
    /// Provider type
    pub provider_type: ProviderType,
    /// Provider version string
    pub version: String,
    /// Redis connection URL
    pub redis_url: String,
    /// Batch flush interval in seconds (default: 5)
    pub flush_interval_secs: u64,
    /// TTL for status keys in Redis (default: 300 seconds / 5 minutes)
    pub status_ttl_secs: u64,
    /// TTL for error history in Redis (default: 86400 seconds / 24 hours)
    pub error_ttl_secs: u64,
    /// Enable OTEL metrics export
    pub enable_otel: bool,
    /// wasmCloud lattice ID (optional)
    pub lattice_id: Option<String>,
}

impl StatusTrackerConfig {
    /// Create a new configuration with defaults
    pub fn new(
        provider_id: impl Into<String>,
        provider_type: ProviderType,
        version: impl Into<String>,
        redis_url: impl Into<String>,
    ) -> Self {
        Self {
            provider_id: provider_id.into(),
            provider_type,
            version: version.into(),
            redis_url: redis_url.into(),
            flush_interval_secs: 5,
            status_ttl_secs: 300,
            error_ttl_secs: 86400,
            enable_otel: std::env::var("WASMCLOUD_OBSERVABILITY_ENABLED")
                .map(|v| v == "true")
                .unwrap_or(false),
            lattice_id: None,
        }
    }

    /// Set the batch flush interval
    pub fn with_flush_interval(mut self, secs: u64) -> Self {
        self.flush_interval_secs = secs;
        self
    }

    /// Set the status TTL
    pub fn with_status_ttl(mut self, secs: u64) -> Self {
        self.status_ttl_secs = secs;
        self
    }

    /// Set the error history TTL
    pub fn with_error_ttl(mut self, secs: u64) -> Self {
        self.error_ttl_secs = secs;
        self
    }

    /// Enable or disable OTEL metrics
    pub fn with_otel(mut self, enable: bool) -> Self {
        self.enable_otel = enable;
        self
    }

    /// Set the wasmCloud lattice ID
    pub fn with_lattice_id(mut self, lattice_id: impl Into<String>) -> Self {
        self.lattice_id = Some(lattice_id.into());
        self
    }
}

impl Default for StatusTrackerConfig {
    fn default() -> Self {
        Self {
            provider_id: String::new(),
            provider_type: ProviderType::Other,
            version: "0.0.0".to_string(),
            redis_url: "redis://localhost:6379".to_string(),
            flush_interval_secs: 5,
            status_ttl_secs: 300,
            error_ttl_secs: 86400,
            enable_otel: false,
            lattice_id: None,
        }
    }
}
