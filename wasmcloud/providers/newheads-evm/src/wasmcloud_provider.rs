//! # wasmCloud Newheads Provider
//!
//! A wasmCloud capability provider that streams blockchain newheads from multiple EVM chains.
//!
//! ## Configuration
//!
//! The provider loads its configuration from Redis using the provider-specific key:
//! `blockchain:nodes:{chain_id}` (Django admin) with env fallback
//!
//! Environment variables:
//! - `NATS_URL` - NATS server URL (optional, uses lattice RPC URL by default)
//! - `REDIS_URL` - Redis server URL (default: redis://localhost:6379)

use anyhow::{anyhow, Context as AnyhowContext, Result};
use async_trait::async_trait;
use futures_util::StreamExt;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};
use tracing::{debug, error, info, warn};

// wasmCloud provider SDK v0.16
use wasmcloud_provider_sdk::{load_host_data, run_provider, HostData, Provider};

// Use the newheads_evm_provider module imports
use newheads_evm_provider::config::load_chain_configs;
use newheads_evm_provider::django_integration::{DjangoBlockchainNode, DjangoConfigManager};
use newheads_evm_provider::ethereum::EthereumClient;
use newheads_evm_provider::traits::{BlockchainClient, ChainConfig};
use newheads_evm_provider::PROVIDER_NAME;

/// The capability contract ID for the newheads provider
const CAPABILITY_ID: &str = "wasmcloud:newheads";

/// wasmCloud Newheads Provider - Multi-chain newheads streaming
///
/// Connects to multiple EVM blockchains and streams newheads to NATS.
/// Configuration is loaded from Django Redis keys with env fallback.
pub struct NewheadsProvider {
    /// Chain configurations loaded from Redis or env
    chain_configs: Arc<RwLock<HashMap<String, ChainConfig>>>,

    /// NATS client for publishing messages
    nats_client: async_nats::Client,

    /// Active connection task handles
    connection_handles: Arc<Mutex<HashMap<String, tokio::task::JoinHandle<()>>>>,

    /// Host data from wasmCloud
    host_data: HostData,
}

fn parse_bool_flag(value: &str) -> bool {
    matches!(
        value.trim().to_lowercase().as_str(),
        "1" | "true" | "yes" | "y" | "on"
    )
}

fn config_enabled(config: &std::collections::HashMap<String, String>) -> bool {
    config
        .get("enabled")
        .map(|value| parse_bool_flag(value))
        .unwrap_or(true)
}

struct DisabledProvider;

impl Provider for DisabledProvider {}

impl NewheadsProvider {
    /// Create a new provider instance
    ///
    /// Loads configuration from Django Redis keys with env fallback
    /// and connects to the configured blockchain.
    pub async fn new(host_data: HostData, chain_configs: Vec<ChainConfig>) -> Result<Self> {
        info!(
            "Initializing Newheads Provider for {} chains",
            chain_configs.len()
        );

        // Get NATS URL from host data or use default
        let nats_url = if !host_data.lattice_rpc_url.is_empty() {
            host_data.lattice_rpc_url.clone()
        } else {
            std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string())
        };

        // Connect to NATS
        let nats_client = async_nats::connect(&nats_url)
            .await
            .context("Failed to connect to NATS")?;

        info!("Connected to NATS at {}", nats_url);

        let configs_map = chain_configs
            .into_iter()
            .map(|config| (config.chain_id.clone(), config))
            .collect::<HashMap<_, _>>();

        let mut provider = Self {
            chain_configs: Arc::new(RwLock::new(configs_map)),
            nats_client,
            connection_handles: Arc::new(Mutex::new(HashMap::new())),
            host_data,
        };

        // Start blockchain connections
        provider.start_blockchain_connections().await?;

        Ok(provider)
    }

    /// Start blockchain WebSocket connections for all configured chains
    async fn start_blockchain_connections(&mut self) -> Result<()> {
        info!("[CONN] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        info!("[CONN] Starting blockchain connection setup...");

        let configs = self.chain_configs.read().await;
        if configs.is_empty() {
            return Err(anyhow!(
                "No chain configurations available for newheads provider"
            ));
        }

        for config in configs.values() {
            self.ensure_chain_connection(config.clone()).await?;
        }

        info!(
            "[CONN] ✓ Spawned {} connection tasks",
            self.connection_handles.lock().await.len()
        );
        info!("[CONN] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Ok(())
    }

    async fn ensure_chain_connection(&self, config: ChainConfig) -> Result<()> {
        if !config.enabled {
            warn!("[CONN] Skipping disabled chain {}", config.chain_id);
            return Ok(());
        }

        if config.ws_url.is_empty() {
            warn!(
                "[CONN] Skipping {}: WebSocket URL is empty",
                config.chain_id
            );
            return Ok(());
        }

        let mut handles = self.connection_handles.lock().await;
        if handles.contains_key(&config.chain_id) {
            debug!("[CONN] Connection already active for {}", config.chain_id);
            return Ok(());
        }

        let nats_client = self.nats_client.clone();
        let chain_name = config.chain_name.clone();
        let chain_id = config.chain_id.clone();
        let subject = config.nats_subjects.newheads_output.clone();

        info!(
            "[CONN] Spawning connection task for {} ({}) -> {}",
            chain_name, chain_id, subject
        );

        let task_handle = tokio::spawn(async move {
            info!(
                "[TASK] Background connection task started for {}",
                chain_name
            );
            let mut reconnect_count: u32 = 0;

            loop {
                reconnect_count += 1;
                info!(
                    "[TASK] Connection attempt #{} for {}",
                    reconnect_count, chain_name
                );

                match blockchain_connection_loop(config.clone(), nats_client.clone()).await {
                    Ok(_) => {
                        warn!(
                            "[TASK] Blockchain connection ended for {}, reconnecting in 5s...",
                            chain_name
                        );
                    }
                    Err(e) => {
                        error!(
                            "[TASK] Blockchain connection error for {}: {}",
                            chain_name, e
                        );
                        error!("[TASK] Error details: {:?}", e);
                        error!("[TASK] Reconnecting in 5s...");
                    }
                }

                tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
            }
        });

        handles.insert(chain_id, task_handle);
        Ok(())
    }

    async fn stop_chain_connection(&self, chain_id: &str) {
        let mut handles = self.connection_handles.lock().await;
        if let Some(handle) = handles.remove(chain_id) {
            warn!("[CONN] Stopping connection for {}", chain_id);
            handle.abort();
        }
    }

    /// Stop the blockchain connection
    fn stop_blockchain_connection(&mut self) {
        info!("[STOP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        info!("[STOP] Stopping blockchain connections");

        let handles = std::mem::take(&mut *self.connection_handles.blocking_lock());
        for (_, handle) in handles {
            handle.abort();
        }

        info!("[STOP] ✓ All blockchain connections stopped");
        info!("[STOP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    }
}

impl Drop for NewheadsProvider {
    fn drop(&mut self) {
        warn!("[DROP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        warn!("[DROP] NewheadsProvider is being dropped!");
        warn!("[DROP] This should only happen during shutdown.");
        warn!("[DROP] If you see this unexpectedly, check for early returns or panics.");
        self.stop_blockchain_connection();
        warn!("[DROP] ✓ Drop complete");
        warn!("[DROP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    }
}

#[derive(Debug, serde::Deserialize)]
struct DjangoUpdateMessage {
    action: Option<String>,
    chain_id: Option<String>,
    node: Option<DjangoBlockchainNode>,
}

async fn start_django_update_listener(
    redis_url: String,
    chain_configs: Arc<RwLock<HashMap<String, ChainConfig>>>,
    connection_handles: Arc<Mutex<HashMap<String, tokio::task::JoinHandle<()>>>>,
    nats_client: async_nats::Client,
) {
    let manager = match DjangoConfigManager::new(&redis_url) {
        Ok(m) => m,
        Err(e) => {
            error!("[UPDATES] Failed to init DjangoConfigManager: {}", e);
            return;
        }
    };

    let redis_client = match redis::Client::open(redis_url.clone()) {
        Ok(c) => c,
        Err(e) => {
            error!("[UPDATES] Failed to create Redis client: {}", e);
            return;
        }
    };

    let mut pubsub = match redis_client.get_async_connection().await {
        Ok(conn) => conn.into_pubsub(),
        Err(e) => {
            error!("[UPDATES] Failed to connect to Redis for pubsub: {}", e);
            return;
        }
    };

    let channel = "blockchain:nodes:updates";
    if let Err(e) = pubsub.subscribe(channel).await {
        error!("[UPDATES] Failed to subscribe to {}: {}", channel, e);
        return;
    }

    info!("[UPDATES] Listening for Django updates on {}", channel);

    let mut message_stream = pubsub.on_message();
    while let Some(msg) = message_stream.next().await {
        let payload: String = match msg.get_payload() {
            Ok(p) => p,
            Err(e) => {
                warn!("[UPDATES] Failed to read update payload: {}", e);
                continue;
            }
        };

        let update: DjangoUpdateMessage = match serde_json::from_str(&payload) {
            Ok(u) => u,
            Err(e) => {
                warn!("[UPDATES] Failed to parse update payload: {}", e);
                continue;
            }
        };

        let chain_id = update
            .chain_id
            .or_else(|| update.node.as_ref().map(|n| n.chain_id.clone()));

        let chain_id = match chain_id {
            Some(id) => id,
            None => {
                warn!("[UPDATES] Update missing chain_id: {}", payload);
                continue;
            }
        };

        info!(
            "[UPDATES] Received update action={:?} chain_id={}",
            update.action, chain_id
        );

        match manager.load_node(&chain_id).await {
            Ok(config) => {
                {
                    let mut configs = chain_configs.write().await;
                    configs.insert(chain_id.clone(), config.clone());
                }

                if config.enabled && !config.ws_url.is_empty() {
                    let mut handles = connection_handles.lock().await;
                    if !handles.contains_key(&chain_id) {
                        drop(handles);
                        info!("[UPDATES] Enabling chain {}", chain_id);
                        let _ = ensure_chain_connection_for_update(
                            config,
                            nats_client.clone(),
                            connection_handles.clone(),
                        )
                        .await;
                    } else {
                        debug!("[UPDATES] Chain {} already active", chain_id);
                    }
                } else {
                    info!("[UPDATES] Disabling chain {}", chain_id);
                    let mut handles = connection_handles.lock().await;
                    if let Some(handle) = handles.remove(&chain_id) {
                        handle.abort();
                    }
                }
            }
            Err(_) => {
                info!("[UPDATES] Removing chain {} (not found in Redis)", chain_id);
                {
                    let mut configs = chain_configs.write().await;
                    configs.remove(&chain_id);
                }
                let mut handles = connection_handles.lock().await;
                if let Some(handle) = handles.remove(&chain_id) {
                    handle.abort();
                }
            }
        }
    }
}

async fn ensure_chain_connection_for_update(
    config: ChainConfig,
    nats_client: async_nats::Client,
    connection_handles: Arc<Mutex<HashMap<String, tokio::task::JoinHandle<()>>>>,
) -> Result<()> {
    if !config.enabled || config.ws_url.is_empty() {
        return Ok(());
    }

    let chain_id = config.chain_id.clone();
    let chain_name = config.chain_name.clone();
    let subject = config.nats_subjects.newheads_output.clone();

    let mut handles = connection_handles.lock().await;
    if handles.contains_key(&chain_id) {
        return Ok(());
    }

    info!(
        "[CONN] Spawning connection task for {} ({}) -> {} (update)",
        chain_name, chain_id, subject
    );

    let task_handle = tokio::spawn(async move {
        info!(
            "[TASK] Background connection task started for {}",
            chain_name
        );
        let mut reconnect_count: u32 = 0;

        loop {
            reconnect_count += 1;
            info!(
                "[TASK] Connection attempt #{} for {}",
                reconnect_count, chain_name
            );

            match blockchain_connection_loop(config.clone(), nats_client.clone()).await {
                Ok(_) => {
                    warn!(
                        "[TASK] Blockchain connection ended for {}, reconnecting in 5s...",
                        chain_name
                    );
                }
                Err(e) => {
                    error!(
                        "[TASK] Blockchain connection error for {}: {}",
                        chain_name, e
                    );
                    error!("[TASK] Error details: {:?}", e);
                    error!("[TASK] Reconnecting in 5s...");
                }
            }

            tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
        }
    });

    handles.insert(chain_id, task_handle);
    Ok(())
}

/// Blockchain connection loop that publishes newheads to NATS
///
/// Runs indefinitely until the WebSocket connection is closed or an error occurs.
async fn blockchain_connection_loop(
    config: ChainConfig,
    nats_client: async_nats::Client,
) -> Result<()> {
    info!("[WS-LOOP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    info!("[WS-LOOP] Starting blockchain connection loop");
    info!(
        "[WS-LOOP] Chain: {} ({})",
        config.chain_name, config.chain_id
    );
    info!("[WS-LOOP] WebSocket URL: {}", config.ws_url);
    info!(
        "[WS-LOOP] Target NATS subject: {}",
        config.nats_subjects.newheads_output
    );

    // Create EVM blockchain client
    debug!("[WS-LOOP] Creating EthereumClient...");
    let client: Box<dyn BlockchainClient> = match EthereumClient::new(config.clone()).await {
        Ok(c) => {
            info!("[WS-LOOP] ✓ EthereumClient created successfully");
            Box::new(c)
        }
        Err(e) => {
            error!("[WS-LOOP] ✗ Failed to create EthereumClient: {}", e);
            return Err(anyhow!("Failed to create EVM client: {}", e));
        }
    };

    // Subscribe to newheads
    debug!("[WS-LOOP] Subscribing to newheads...");
    let mut receiver = match client.subscribe_newheads().await {
        Ok(r) => {
            info!("[WS-LOOP] ✓ Subscribed to newheads stream");
            r
        }
        Err(e) => {
            error!("[WS-LOOP] ✗ Failed to subscribe to newheads: {}", e);
            return Err(e);
        }
    };

    info!("[WS-LOOP] ✓ Connected to {} blockchain", config.chain_id);
    info!(
        "[WS-LOOP] ✓ Streaming newheads to NATS subject: {}",
        config.nats_subjects.newheads_output
    );
    info!("[WS-LOOP] Entering block processing loop...");

    let mut block_count: u64 = 0;

    // Process incoming block headers
    while let Some(block_header) = receiver.recv().await {
        block_count += 1;
        let subject = &config.nats_subjects.newheads_output;

        debug!(
            "[WS-LOOP] Received block #{} (total: {})",
            block_header.block_number, block_count
        );

        // Serialize block header
        let payload = match serde_json::to_vec(&block_header) {
            Ok(p) => p,
            Err(e) => {
                error!(
                    "[WS-LOOP] Failed to serialize block #{}: {}",
                    block_header.block_number, e
                );
                continue;
            }
        };

        // Publish to NATS
        if let Err(e) = nats_client.publish(subject.clone(), payload.into()).await {
            error!(
                "[WS-LOOP] ✗ Failed to publish block #{} to NATS: {}",
                block_header.block_number, e
            );
        } else {
            if block_count <= 5 || block_count % 100 == 0 {
                info!(
                    "[WS-LOOP] ✓ Published block #{} to {} (total: {})",
                    block_header.block_number, subject, block_count
                );
            } else {
                debug!(
                    "[WS-LOOP] ✓ Published block #{} to {} (total: {})",
                    block_header.block_number, subject, block_count
                );
            }
        }
    }

    warn!(
        "[WS-LOOP] Block receiver channel closed after {} blocks",
        block_count
    );
    info!("[WS-LOOP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Err(anyhow!(
        "WebSocket connection closed after {} blocks",
        block_count
    ))
}

// Provider trait implementation for wasmCloud SDK v0.16
#[async_trait]
impl Provider for NewheadsProvider {
    // The Provider trait in SDK 0.16 has default implementations
    // Shutdown will be handled by dropping the provider
}

/// Main entry point for the wasmCloud provider
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging with DEBUG level for detailed tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("newheads_evm_provider=debug".parse().unwrap()),
        )
        .init();

    info!("═══════════════════════════════════════════════════════════════");
    info!("  NEWHEADS-EVM PROVIDER STARTUP - wasmCloud Mode");
    info!("═══════════════════════════════════════════════════════════════");
    info!("Provider name: {}", PROVIDER_NAME);
    info!("PID: {}", std::process::id());

    // Load host data from wasmCloud
    debug!("[TRACE] Loading host data from wasmCloud...");
    let host_data = match load_host_data() {
        Ok(data) => {
            info!("[TRACE] Host data loaded successfully");
            data
        }
        Err(e) => {
            error!("[TRACE] Failed to load host data: {}", e);
            return Err(e.into());
        }
    };

    info!("[HOST] Provider ID: {}", host_data.provider_key);
    info!("[HOST] Lattice RPC URL: {:?}", host_data.lattice_rpc_url);
    info!(
        "[HOST] Config keys: {:?}",
        host_data.config.keys().collect::<Vec<_>>()
    );
    info!(
        "[HOST] Link definitions count: {}",
        host_data.link_definitions.len()
    );
    for link in &host_data.link_definitions {
        debug!(
            "[HOST] Link: source={}, target={}, name={}",
            link.source_id, link.target, link.name
        );
    }

    let enabled_flag = config_enabled(&host_data.config);
    info!("[CONFIG] Enabled flag from host config: {}", enabled_flag);
    if !enabled_flag {
        warn!("[CONFIG] Provider disabled via host config (enabled=false). Skipping startup.");
        let handler = run_provider(DisabledProvider, "newheads-evm-provider")
            .await
            .context("Provider runtime error")?;
        handler.await;
        info!("[SHUTDOWN] Newheads Provider shutdown complete");
        return Ok(());
    }

    // Get Redis URL from wasmCloud config first, then environment variable
    let redis_url = host_data
        .config
        .get("redis_url")
        .cloned()
        .or_else(|| std::env::var("REDIS_URL").ok())
        .unwrap_or_else(|| "redis://localhost:6379".to_string());

    info!("[CONFIG] REDIS_URL: {}", redis_url);
    info!("[CONFIG] Looking for Django configs at Redis keys: blockchain:nodes:*");

    // Load multi-chain configs from Redis or env fallback
    debug!("[TRACE] Loading chain configs...");
    let chain_configs = load_chain_configs(&redis_url).await?;
    let enabled_count = chain_configs.iter().filter(|c| c.enabled).count();
    let disabled_count = chain_configs.len().saturating_sub(enabled_count);

    info!(
        "[CONFIG] Loaded {} chain configs (enabled: {}, disabled: {})",
        chain_configs.len(),
        enabled_count,
        disabled_count
    );

    for config in &chain_configs {
        info!(
            "[CONFIG] ✓ Chain: {} ({}) network={}/{} enabled={} subject={}",
            config.chain_name,
            config.chain_id,
            config.network,
            config.subnet,
            config.enabled,
            config.nats_subjects.newheads_output
        );
    }

    // Create provider instance
    info!("[TRACE] Creating NewheadsProvider instance...");
    let provider = match NewheadsProvider::new(host_data.clone(), chain_configs).await {
        Ok(p) => {
            info!("[TRACE] ✓ NewheadsProvider created successfully");
            p
        }
        Err(e) => {
            error!("[TRACE] ✗ Failed to create NewheadsProvider: {}", e);
            return Err(e);
        }
    };

    let updates_chain_configs = provider.chain_configs.clone();
    let updates_handles = provider.connection_handles.clone();
    let updates_nats = provider.nats_client.clone();
    let updates_redis = redis_url.clone();

    tokio::spawn(async move {
        start_django_update_listener(
            updates_redis,
            updates_chain_configs,
            updates_handles,
            updates_nats,
        )
        .await;
    });

    info!("═══════════════════════════════════════════════════════════════");
    info!("  PROVIDER READY - Entering main event loop");
    info!("═══════════════════════════════════════════════════════════════");
    info!("[MAIN] Background task is streaming blocks to NATS");

    let handler = run_provider(provider, "newheads-evm-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("[SHUTDOWN] Newheads Provider shutdown complete");
    info!("═══════════════════════════════════════════════════════════════");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider>() {}
        assert_provider::<NewheadsProvider>();
        assert_provider::<DisabledProvider>();
    }
}
