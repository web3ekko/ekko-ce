//! Core types for provider status tracking.
//!
//! These types are serialized to Redis for persistence and exposed via OTEL metrics.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Type of blockchain provider
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ProviderType {
    /// EVM-compatible chains (Ethereum, Polygon, BSC, etc.)
    Evm,
    /// UTXO-based chains (Bitcoin, Litecoin, etc.)
    Utxo,
    /// Solana Virtual Machine
    Svm,
    /// Cosmos SDK chains
    Cosmos,
    /// Unknown/other provider types
    Other,
}

impl std::fmt::Display for ProviderType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProviderType::Evm => write!(f, "evm"),
            ProviderType::Utxo => write!(f, "utxo"),
            ProviderType::Svm => write!(f, "svm"),
            ProviderType::Cosmos => write!(f, "cosmos"),
            ProviderType::Other => write!(f, "other"),
        }
    }
}

/// Overall health state of a provider
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum HealthState {
    /// All subscriptions healthy
    Healthy,
    /// Some subscriptions degraded but still functional
    Degraded,
    /// Provider is unhealthy (no working subscriptions)
    Unhealthy,
    /// Provider is starting up
    Starting,
    /// Provider is shutting down
    Stopping,
}

impl Default for HealthState {
    fn default() -> Self {
        HealthState::Starting
    }
}

/// State of an individual chain subscription
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SubscriptionState {
    /// Connected and receiving data
    Active,
    /// Currently establishing connection
    Connecting,
    /// Lost connection, attempting to reconnect
    Reconnecting,
    /// Subscription has failed and is not recovering
    Error,
    /// Subscription has been intentionally stopped
    Stopped,
}

impl Default for SubscriptionState {
    fn default() -> Self {
        SubscriptionState::Connecting
    }
}

/// Connection status details
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ConnectionStatus {
    /// Whether currently connected
    pub connected: bool,
    /// Time of last successful connection
    #[serde(skip_serializing_if = "Option::is_none")]
    pub connected_at: Option<DateTime<Utc>>,
    /// Time of last disconnection
    #[serde(skip_serializing_if = "Option::is_none")]
    pub disconnected_at: Option<DateTime<Utc>>,
    /// Number of reconnection attempts since last stable connection
    pub reconnect_attempts: u32,
    /// Current RPC/WS endpoint being used
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current_endpoint: Option<String>,
}

/// Information about the last received block
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockInfo {
    /// Block number/height
    pub number: u64,
    /// Block hash (hex-encoded)
    pub hash: String,
    /// Block timestamp
    pub timestamp: DateTime<Utc>,
    /// Time when we received this block
    pub received_at: DateTime<Utc>,
    /// Latency in milliseconds from block timestamp to receipt
    pub latency_ms: u32,
}

/// Error record for tracking error history
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorRecord {
    /// Error message
    pub message: String,
    /// Whether this error is considered recoverable
    pub recoverable: bool,
    /// When the error occurred
    pub occurred_at: DateTime<Utc>,
    /// Error code if available
    #[serde(skip_serializing_if = "Option::is_none")]
    pub code: Option<String>,
    /// Chain ID if error is chain-specific
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chain_id: Option<String>,
}

/// Error history with bounded storage
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ErrorHistory {
    /// Recent errors (bounded, oldest removed first)
    pub recent_errors: Vec<ErrorRecord>,
    /// Total error count since start
    pub total_errors: u64,
    /// Recoverable error count
    pub recoverable_errors: u64,
    /// Fatal error count
    pub fatal_errors: u64,
}

impl ErrorHistory {
    /// Maximum number of recent errors to keep
    pub const MAX_RECENT_ERRORS: usize = 100;

    /// Add an error to history
    pub fn add_error(&mut self, error: ErrorRecord) {
        self.total_errors += 1;
        if error.recoverable {
            self.recoverable_errors += 1;
        } else {
            self.fatal_errors += 1;
        }

        self.recent_errors.push(error);
        if self.recent_errors.len() > Self::MAX_RECENT_ERRORS {
            self.recent_errors.remove(0);
        }
    }
}

/// Metrics for a single chain subscription
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ChainMetrics {
    /// Total blocks received
    pub blocks_received: u64,
    /// Blocks received in last minute
    pub blocks_last_minute: u64,
    /// Average block latency in milliseconds
    pub avg_latency_ms: f64,
    /// P99 block latency in milliseconds
    pub p99_latency_ms: f64,
    /// Total connection errors
    pub connection_errors: u64,
    /// Total processing errors
    pub processing_errors: u64,
    /// Last metric update time
    pub updated_at: DateTime<Utc>,
}

/// Status of an individual chain subscription
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubscriptionStatus {
    /// Chain identifier (e.g., "ethereum-mainnet", "polygon-mainnet")
    pub chain_id: String,
    /// Human-readable chain name
    pub chain_name: String,
    /// Current subscription state
    pub state: SubscriptionState,
    /// Connection details
    pub connection: ConnectionStatus,
    /// Last received block
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_block: Option<BlockInfo>,
    /// Error history
    pub error_history: ErrorHistory,
    /// Chain-specific metrics
    pub metrics: ChainMetrics,
    /// When this subscription started
    pub started_at: DateTime<Utc>,
    /// Last state change time
    pub state_changed_at: DateTime<Utc>,
}

impl SubscriptionStatus {
    /// Create a new subscription status
    pub fn new(chain_id: impl Into<String>, chain_name: impl Into<String>) -> Self {
        let now = Utc::now();
        Self {
            chain_id: chain_id.into(),
            chain_name: chain_name.into(),
            state: SubscriptionState::Connecting,
            connection: ConnectionStatus::default(),
            last_block: None,
            error_history: ErrorHistory::default(),
            metrics: ChainMetrics {
                updated_at: now,
                ..Default::default()
            },
            started_at: now,
            state_changed_at: now,
        }
    }
}

/// Overall provider status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderStatus {
    /// Unique provider instance ID
    pub provider_id: String,
    /// Provider type (EVM, UTXO, etc.)
    pub provider_type: ProviderType,
    /// Overall health state
    pub overall_health: HealthState,
    /// All chain subscriptions
    pub subscriptions: HashMap<String, SubscriptionStatus>,
    /// When provider started
    pub started_at: DateTime<Utc>,
    /// Last heartbeat time
    pub last_heartbeat: DateTime<Utc>,
    /// Provider version
    pub version: String,
    /// Host lattice ID (from wasmCloud)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lattice_id: Option<String>,
}

impl ProviderStatus {
    /// Create a new provider status
    pub fn new(
        provider_id: impl Into<String>,
        provider_type: ProviderType,
        version: impl Into<String>,
    ) -> Self {
        let now = Utc::now();
        Self {
            provider_id: provider_id.into(),
            provider_type,
            overall_health: HealthState::Starting,
            subscriptions: HashMap::new(),
            started_at: now,
            last_heartbeat: now,
            version: version.into(),
            lattice_id: None,
        }
    }

    /// Calculate overall health based on subscription states
    pub fn calculate_health(&self) -> HealthState {
        if self.subscriptions.is_empty() {
            return HealthState::Starting;
        }

        let active_count = self
            .subscriptions
            .values()
            .filter(|s| s.state == SubscriptionState::Active)
            .count();

        let error_count = self
            .subscriptions
            .values()
            .filter(|s| s.state == SubscriptionState::Error)
            .count();

        let total = self.subscriptions.len();

        if active_count == total {
            HealthState::Healthy
        } else if error_count == total {
            HealthState::Unhealthy
        } else if active_count > 0 {
            HealthState::Degraded
        } else {
            HealthState::Unhealthy
        }
    }

    /// Update overall health state
    pub fn update_health(&mut self) {
        self.overall_health = self.calculate_health();
        self.last_heartbeat = Utc::now();
    }

    /// Check if provider is healthy
    pub fn is_healthy(&self) -> bool {
        matches!(
            self.overall_health,
            HealthState::Healthy | HealthState::Degraded
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_provider_status_new() {
        let status = ProviderStatus::new("test-provider", ProviderType::Evm, "1.0.0");
        assert_eq!(status.provider_id, "test-provider");
        assert_eq!(status.provider_type, ProviderType::Evm);
        assert_eq!(status.overall_health, HealthState::Starting);
        assert!(status.subscriptions.is_empty());
    }

    #[test]
    fn test_health_calculation() {
        let mut status = ProviderStatus::new("test", ProviderType::Evm, "1.0.0");

        // Empty subscriptions = Starting
        assert_eq!(status.calculate_health(), HealthState::Starting);

        // Add active subscription
        let mut sub = SubscriptionStatus::new("eth-mainnet", "Ethereum Mainnet");
        sub.state = SubscriptionState::Active;
        status.subscriptions.insert("eth-mainnet".to_string(), sub);

        assert_eq!(status.calculate_health(), HealthState::Healthy);

        // Add error subscription
        let mut sub2 = SubscriptionStatus::new("polygon-mainnet", "Polygon Mainnet");
        sub2.state = SubscriptionState::Error;
        status
            .subscriptions
            .insert("polygon-mainnet".to_string(), sub2);

        assert_eq!(status.calculate_health(), HealthState::Degraded);
    }

    #[test]
    fn test_error_history() {
        let mut history = ErrorHistory::default();

        for i in 0..150 {
            history.add_error(ErrorRecord {
                message: format!("Error {}", i),
                recoverable: i % 2 == 0,
                occurred_at: Utc::now(),
                code: None,
                chain_id: None,
            });
        }

        assert_eq!(history.total_errors, 150);
        assert_eq!(history.recent_errors.len(), ErrorHistory::MAX_RECENT_ERRORS);
        assert!(history.recent_errors[0].message.contains("50")); // Oldest kept is #50
    }
}
