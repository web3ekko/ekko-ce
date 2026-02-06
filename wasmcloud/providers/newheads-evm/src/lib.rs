//! # Newheads EVM Provider
//!
//! **Standalone service** for streaming EVM blockchain newheads (new block headers)
//! from a single EVM-compatible network in real-time.
//!
//! ## Features:
//! - Real-time streaming via WebSocket connection
//! - Auto-reconnection with exponential backoff
//! - Health monitoring and connection status
//! - NATS messaging - publishes newheads to structured topics
//!
//! ## Architecture:
//! This provider runs as a standalone service with a single WebSocket connection
//! to one EVM blockchain node. Configuration is loaded from Redis at startup
//! using the provider-specific key: `provider:config:newheads-evm`

use anyhow::{anyhow, Result};
use async_nats::Client as NatsClient;
use std::sync::Arc;
use tracing::{debug, error, info, warn};

// Provider status tracking with Redis + OTEL
use provider_status_common::{
    ProviderStatusTracker, ProviderType as StatusProviderType, StatusTracker, StatusTrackerConfig,
};

pub mod config;
pub mod django_integration;
pub mod ethereum;
pub mod traits; // Keep for backwards compatibility, not used

use config::{load_provider_config, ProviderConfig};
use traits::{BlockchainClient, SubscriptionStatus};

/// Provider name constant - used for Redis key lookup
pub const PROVIDER_NAME: &str = "newheads-evm";

/// Newheads EVM Provider
///
/// Streams EVM blockchain newheads from a single chain and publishes to NATS.
/// Configuration is loaded from Redis key: `provider:config:newheads-evm`
pub struct NewheadsProvider {
    /// Provider configuration loaded from Redis
    config: ProviderConfig,

    /// NATS client for publishing
    nats_client: NatsClient,

    /// Blockchain client for WebSocket subscription
    client: Option<Arc<dyn BlockchainClient + Send + Sync>>,

    /// Current subscription status
    subscription_status: SubscriptionStatus,

    /// Provider status tracker for Redis persistence and OTEL metrics
    status_tracker: Option<Arc<ProviderStatusTracker>>,
}

impl std::fmt::Debug for NewheadsProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("NewheadsProvider")
            .field("provider_name", &PROVIDER_NAME)
            .field("chain_id", &self.config.chain_id)
            .field("chain_name", &self.config.chain_name)
            .field("ws_url", &self.config.ws_url)
            .field("subscription_status", &self.subscription_status)
            .field("status_tracker", &self.status_tracker.is_some())
            .finish()
    }
}

impl NewheadsProvider {
    /// Initialize the provider with NATS and Redis connections
    ///
    /// Loads configuration from Redis key: `provider:config:newheads-evm`
    /// Exits with error if configuration is not found.
    pub async fn new(nats_url: &str, redis_url: &str) -> Result<Self> {
        info!("Initializing {} provider", PROVIDER_NAME);

        // Load provider-specific config from Redis
        let config = load_provider_config(redis_url, PROVIDER_NAME).await?;

        info!(
            "Loaded config for chain: {} ({}) at {}",
            config.chain_name, config.chain_id, config.ws_url
        );

        // Connect to NATS
        let nats_client = async_nats::connect(nats_url).await?;
        info!("Connected to NATS at {}", nats_url);

        // Initialize status tracker for Redis persistence and OTEL metrics
        let hostname = std::env::var("HOSTNAME")
            .or_else(|_| std::env::var("POD_NAME"))
            .unwrap_or_else(|_| format!("local-{}", std::process::id()));
        let provider_id = format!("{}-{}", PROVIDER_NAME, hostname);

        let tracker_config = StatusTrackerConfig::new(
            provider_id,
            StatusProviderType::Evm,
            env!("CARGO_PKG_VERSION"),
            redis_url,
        );

        let status_tracker = match ProviderStatusTracker::new(tracker_config).await {
            Ok(tracker) => {
                info!("Status tracker initialized");
                Some(tracker)
            }
            Err(e) => {
                warn!(
                    "Failed to initialize status tracker (continuing without): {}",
                    e
                );
                None
            }
        };

        Ok(Self {
            config,
            nats_client,
            client: None,
            subscription_status: SubscriptionStatus::Disconnected,
            status_tracker,
        })
    }

    /// Start the provider service
    ///
    /// Connects to the blockchain WebSocket and streams newheads to NATS.
    /// Runs indefinitely until stopped.
    pub async fn start(&mut self) -> Result<()> {
        info!(
            "Starting {} provider for {} ({})",
            PROVIDER_NAME, self.config.chain_name, self.config.chain_id
        );

        // Register subscription with status tracker
        if let Some(ref tracker) = self.status_tracker {
            tracker
                .register_subscription(&self.config.chain_id, &self.config.chain_name)
                .await;
        }

        // Create the blockchain client
        self.connect().await?;

        // Run the subscription loop with auto-reconnect
        loop {
            match self.run_subscription_loop().await {
                Ok(_) => {
                    warn!("Subscription loop ended unexpectedly, reconnecting...");
                }
                Err(e) => {
                    error!("Subscription error: {}, reconnecting in 5s...", e);
                    tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
                }
            }

            // Attempt to reconnect
            if let Err(e) = self.connect().await {
                error!("Failed to reconnect: {}, retrying in 10s...", e);
                tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
            }
        }
    }

    /// Connect to the blockchain WebSocket
    async fn connect(&mut self) -> Result<()> {
        info!("Connecting to WebSocket: {}", self.config.ws_url);

        // Create chain config for the ethereum client
        let chain_config = self.create_chain_config();

        // Create client with NATS integration
        let client = Arc::new(
            ethereum::EthereumClient::new_with_nats(chain_config, self.nats_client.clone()).await?,
        );

        self.client = Some(client);
        self.subscription_status = SubscriptionStatus::Active;

        // Track connection in status tracker
        if let Some(ref tracker) = self.status_tracker {
            tracker
                .record_connection_change(&self.config.chain_id, true)
                .await;
        }

        info!("Connected to {} successfully", self.config.chain_name);
        Ok(())
    }

    /// Run the subscription loop
    async fn run_subscription_loop(&mut self) -> Result<()> {
        let client = self
            .client
            .as_ref()
            .ok_or_else(|| anyhow!("No client connected"))?;

        info!(
            "Starting newheads subscription for {} (publishing to {})",
            self.config.chain_name,
            self.config.nats_subject()
        );

        // Start subscription
        let mut receiver = client.subscribe_newheads().await?;

        // Process incoming block headers
        while let Some(block_header) = receiver.recv().await {
            debug!(
                "Received block #{} for {}",
                block_header.block_number, self.config.chain_name
            );

            // Track block in status tracker with latency
            if let Some(ref tracker) = self.status_tracker {
                let now_ms = chrono::Utc::now().timestamp_millis();
                let block_timestamp_ms = block_header.timestamp as i64 * 1000;
                let latency_ms = (now_ms - block_timestamp_ms).max(0) as u32;

                tracker
                    .record_block_received(
                        &self.config.chain_id,
                        block_header.block_number,
                        latency_ms,
                    )
                    .await;
            }
        }

        // Connection closed
        self.subscription_status = SubscriptionStatus::Disconnected;

        if let Some(ref tracker) = self.status_tracker {
            tracker
                .record_connection_change(&self.config.chain_id, false)
                .await;
        }

        Err(anyhow!("WebSocket connection closed"))
    }

    /// Create a ChainConfig from ProviderConfig for the ethereum client
    fn create_chain_config(&self) -> traits::ChainConfig {
        let nats_subjects = traits::NatsSubjects::generate(
            &self.config.network,
            &self.config.subnet,
            &traits::VmType::Evm,
            &self.config.chain_id,
        );

        traits::ChainConfig {
            chain_id: self.config.chain_id.clone(),
            chain_name: self.config.chain_name.clone(),
            network: self.config.network.clone(),
            subnet: self.config.subnet.clone(),
            vm_type: traits::VmType::Evm,
            rpc_url: self.config.rpc_url.clone(),
            ws_url: self.config.ws_url.clone(),
            chain_type: traits::ChainType::Ethereum, // Default, can be extended
            network_id: None,                        // Optional, not needed for newheads
            enabled: self.config.enabled,
            nats_subjects,
        }
    }

    /// Get the current subscription status
    pub fn status(&self) -> &SubscriptionStatus {
        &self.subscription_status
    }

    /// Get the provider configuration
    pub fn config(&self) -> &ProviderConfig {
        &self.config
    }

    /// Shutdown the provider
    pub async fn shutdown(&mut self) -> Result<()> {
        info!("Shutting down {} provider", PROVIDER_NAME);

        // Clear client
        self.client = None;
        self.subscription_status = SubscriptionStatus::Disconnected;

        // Track disconnection
        if let Some(ref tracker) = self.status_tracker {
            tracker
                .record_connection_change(&self.config.chain_id, false)
                .await;
            tracker.unregister_subscription(&self.config.chain_id).await;

            if let Err(e) = tracker.shutdown().await {
                warn!("Failed to shutdown status tracker: {}", e);
            }
        }

        info!("Shutdown complete");
        Ok(())
    }
}
