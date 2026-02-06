//! Provider Status Common - Shared status tracking for wasmCloud providers
//!
//! This crate provides status tracking functionality for wasmCloud data ingestion
//! providers with:
//!
//! - **Redis persistence**: Status is persisted to Redis for Django Admin visibility
//! - **OpenTelemetry metrics**: Integrates with wasmCloud's built-in OTEL infrastructure
//! - **Batched writes**: High-frequency updates are batched to minimize overhead
//!
//! # Quick Start
//!
//! ```ignore
//! use provider_status_common::{
//!     ProviderStatusTracker, StatusTracker, StatusTrackerConfig, ProviderType
//! };
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     // Configure tracker
//!     let config = StatusTrackerConfig::new(
//!         "newheads-evm-instance-1",
//!         ProviderType::Evm,
//!         "1.0.0",
//!         "redis://localhost:6379",
//!     )
//!     .with_otel(true);
//!
//!     // Create tracker
//!     let tracker = ProviderStatusTracker::new(config).await?;
//!
//!     // Register subscriptions
//!     tracker.register_subscription("ethereum-mainnet", "Ethereum Mainnet").await;
//!
//!     // Track status
//!     tracker.record_connection_change("ethereum-mainnet", true).await;
//!     tracker.record_block_received("ethereum-mainnet", 19000000, 150).await;
//!
//!     // Check health
//!     assert!(tracker.is_healthy());
//!
//!     // Shutdown
//!     tracker.shutdown().await?;
//!     Ok(())
//! }
//! ```
//!
//! # Redis Key Schema
//!
//! ```text
//! provider:status:{provider_id}                    # ProviderStatus JSON (5min TTL)
//! provider:subscription:{provider_id}:{chain_id}   # SubscriptionStatus JSON (5min TTL)
//! provider:errors:{provider_id}                    # List of ErrorRecord (24hr TTL, max 100)
//! provider:registry                                # HASH: provider_id -> provider_type
//! ```
//!
//! # OTEL Metrics
//!
//! When `WASMCLOUD_OBSERVABILITY_ENABLED=true`, the following metrics are exported:
//!
//! - `provider_blocks_received_total{chain, provider}` - Total blocks received
//! - `provider_block_latency_seconds{chain, provider}` - Block latency histogram
//! - `provider_connection_state{chain, provider}` - Connection state (1=connected)
//! - `provider_errors_total{chain, provider, recoverable}` - Total errors
//! - `provider_active_subscriptions{provider}` - Active subscription count
//! - `provider_healthy{provider}` - Health status (1=healthy)
//!
//! # Features
//!
//! - `otel` (default) - Enable OpenTelemetry integration
//!
//! Disable OTEL for testing:
//! ```toml
//! provider-status-common = { path = "...", default-features = false }
//! ```

#![warn(missing_docs)]
#![warn(rustdoc::missing_crate_level_docs)]

pub mod redis_storage;
pub mod tracker;
pub mod traits;
pub mod types;

#[cfg(feature = "otel")]
pub mod otel;

// Re-exports for convenient access
pub use redis_storage::RedisStorage;
pub use tracker::ProviderStatusTracker;
pub use traits::{StatusTracker, StatusTrackerConfig};
pub use types::{
    BlockInfo, ChainMetrics, ConnectionStatus, ErrorHistory, ErrorRecord, HealthState,
    ProviderStatus, ProviderType, SubscriptionState, SubscriptionStatus,
};

#[cfg(feature = "otel")]
pub use otel::{init_otel, shutdown_otel, OtelConfig, OtelMetrics};
