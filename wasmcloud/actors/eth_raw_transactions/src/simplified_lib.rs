//! # Simplified EVM Raw Transactions Actor (Core Logic)
//!
//! This is a simplified version that focuses on the Redis configuration logic
//! without wasmCloud interfaces (to avoid nuid dependency conflicts).
//!
//! ## Redis Configuration Structure
//! Network configurations are stored in Redis by the admin interface:
//!
//! **Key:** `nodes:{network}:{subnet}:{vm_type}`
//!
//! **Value Format:**
//! ```json
//! {
//!   "rpc_urls": ["https://...", "https://..."],
//!   "ws_urls": ["wss://...", "wss://..."],
//!   "chain_id": 1,
//!   "enabled": true
//! }
//! ```
//!
//! The actor extracts network/subnet/vm_type from incoming newheads packets
//! and uses that information to look up the appropriate configuration.

use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};

/// Enhanced block header with network context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockHeader {
    pub network: String,    // e.g., "ethereum", "polygon", "arbitrum"
    pub subnet: String,     // e.g., "mainnet", "goerli", "sepolia"
    pub vm_type: String,    // "evm"
    pub chain_id: String,   // e.g., "ethereum-mainnet"
    pub chain_name: String, // e.g., "Ethereum Mainnet"
    pub block_number: u64,
    pub block_hash: String,
    pub parent_hash: String,
    pub timestamp: u64,
    pub transaction_count: Option<u32>,
    pub received_at: String, // ISO timestamp
    pub provider_id: String,
}

/// Network configuration for RPC endpoints (managed by admin interface)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    pub rpc_urls: Vec<String>, // Array of HTTP RPC URLs
    pub ws_urls: Vec<String>,  // Array of WebSocket URLs
    pub chain_id: Option<u64>, // Optional chain ID
    pub enabled: bool,         // Whether this network is enabled
}

impl NetworkConfig {
    /// Get Redis key for network configuration using packet info
    /// Format: "nodes:{network}:{subnet}:{vm_type}"
    pub fn redis_key(network: &str, subnet: &str, vm_type: &str) -> String {
        format!("nodes:{}:{}:{}", network, subnet, vm_type)
    }

    /// Get a RPC URL from the available URLs (with basic load balancing)
    pub fn get_rpc_url(&self) -> Result<&String> {
        if self.rpc_urls.is_empty() {
            return Err(anyhow!("No RPC URLs configured"));
        }

        // For now, just return the first URL
        // TODO: Implement proper load balancing (round-robin, random, health-based)
        Ok(&self.rpc_urls[0])
    }

    /// Get a WebSocket URL from the available URLs (with basic load balancing)
    pub fn get_ws_url(&self) -> Result<&String> {
        if self.ws_urls.is_empty() {
            return Err(anyhow!("No WebSocket URLs configured"));
        }

        // For now, just return the first URL
        // TODO: Implement proper load balancing (round-robin, random, health-based)
        Ok(&self.ws_urls[0])
    }
}

/// Raw transaction payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransaction {
    // Network context (inherited from block header)
    pub network: String,
    pub subnet: String,
    pub vm_type: String,

    // Transaction data
    pub transaction_hash: String,
    pub block_number: u64,
    pub block_hash: String,
    pub block_timestamp: u64,
    pub transaction_index: u32,
    pub from_address: String,
    pub to_address: Option<String>,
    pub value: String,
    pub gas_limit: u64,
    pub gas_price: String,
    pub input_data: String,
    pub nonce: u64,
    pub chain_id: String,

    // EVM-specific data
    pub max_fee_per_gas: Option<String>,
    pub max_priority_fee_per_gas: Option<String>,
    pub transaction_type: Option<u8>,
    pub v: Option<String>,
    pub r: Option<String>,
    pub s: Option<String>,

    // Processing metadata
    pub processed_at: String, // ISO timestamp
    pub processor_id: String,
}

/// Simplified EVM Raw Transactions Processor (Core Logic)
pub struct EthRawTransactionsProcessor;

impl EthRawTransactionsProcessor {
    /// Create a new processor instance
    pub fn new() -> Self {
        Self
    }

    /// Process a block header and determine what RPC URL to use
    ///
    /// Flow:
    /// 1. Extract network/subnet/vm_type from incoming block header
    /// 2. Generate Redis key for configuration lookup
    /// 3. Return the key that would be used to fetch configuration
    pub fn get_config_key_for_block(&self, block_header: &BlockHeader) -> String {
        NetworkConfig::redis_key(
            &block_header.network,
            &block_header.subnet,
            &block_header.vm_type,
        )
    }

    /// Simulate processing a block header with a given network configuration
    pub fn process_block_with_config(
        &self,
        block_header: &BlockHeader,
        config: &NetworkConfig,
    ) -> Result<String> {
        if !config.enabled {
            return Err(anyhow!(
                "Network {}.{}.{} is disabled",
                block_header.network,
                block_header.subnet,
                block_header.vm_type
            ));
        }

        let rpc_url = config.get_rpc_url()?;

        // In a real implementation, this would make HTTP calls to fetch transactions
        // For now, just return the RPC URL that would be used
        Ok(rpc_url.clone())
    }

    /// Create example configurations that the admin interface would set up
    pub fn create_example_configs() -> Vec<(String, String, String, NetworkConfig)> {
        vec![
            // Ethereum Mainnet
            (
                "ethereum".to_string(),
                "mainnet".to_string(),
                "evm".to_string(),
                NetworkConfig {
                    rpc_urls: vec![
                        "https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY".to_string(),
                        "https://mainnet.infura.io/v3/YOUR_PROJECT_ID".to_string(),
                        "https://rpc.ankr.com/eth".to_string(),
                    ],
                    ws_urls: vec![
                        "wss://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY".to_string(),
                        "wss://mainnet.infura.io/ws/v3/YOUR_PROJECT_ID".to_string(),
                    ],
                    chain_id: Some(1),
                    enabled: true,
                },
            ),
            // Polygon Mainnet
            (
                "polygon".to_string(),
                "mainnet".to_string(),
                "evm".to_string(),
                NetworkConfig {
                    rpc_urls: vec![
                        "https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY".to_string(),
                        "https://polygon-rpc.com".to_string(),
                        "https://rpc.ankr.com/polygon".to_string(),
                    ],
                    ws_urls: vec!["wss://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY".to_string()],
                    chain_id: Some(137),
                    enabled: true,
                },
            ),
            // Arbitrum Mainnet
            (
                "arbitrum".to_string(),
                "mainnet".to_string(),
                "evm".to_string(),
                NetworkConfig {
                    rpc_urls: vec![
                        "https://arb-mainnet.g.alchemy.com/v2/YOUR_API_KEY".to_string(),
                        "https://arbitrum-one.publicnode.com".to_string(),
                    ],
                    ws_urls: vec!["wss://arb-mainnet.g.alchemy.com/v2/YOUR_API_KEY".to_string()],
                    chain_id: Some(42161),
                    enabled: true,
                },
            ),
        ]
    }
}

impl Default for EthRawTransactionsProcessor {
    fn default() -> Self {
        Self::new()
    }
}
