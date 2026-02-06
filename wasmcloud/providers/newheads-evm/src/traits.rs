//! # Blockchain Traits and Common Types
//!
//! Defines common interfaces and data structures for different blockchain types.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::fmt;
use tokio::sync::mpsc;

/// Enhanced block header structure with network context for wasmCloud lattice
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockHeader {
    // Network identification (for wildcard subscription support)
    pub network: String, // e.g., "ethereum", "polygon", "arbitrum"
    pub subnet: String,  // e.g., "mainnet", "goerli", "sepolia"
    pub vm_type: VmType, // e.g., "evm", "utxo", "svm"

    // Legacy fields (for backward compatibility)
    pub chain_id: String,   // e.g., "ethereum-mainnet"
    pub chain_name: String, // e.g., "Ethereum Mainnet"

    // Block data
    pub block_number: u64,
    pub block_hash: String,
    pub parent_hash: String,
    pub timestamp: u64,

    // Optional fields (not all chains have these)
    pub difficulty: Option<String>,
    pub gas_limit: Option<u64>,
    pub gas_used: Option<u64>,
    pub miner: Option<String>,
    pub extra_data: Option<String>,

    // Network-specific data (for chain-specific processing)
    pub network_specific: serde_json::Value,

    // Metadata
    pub received_at: chrono::DateTime<chrono::Utc>,
    pub provider_id: String,

    // Raw data for debugging/analysis
    pub raw_data: Option<String>,

    // Node endpoint information
    pub rpc_url: Option<String>, // HTTP RPC endpoint used by this node
    pub ws_url: Option<String>,  // WebSocket endpoint used by this node
}

impl BlockHeader {
    /// Get the NATS subject for this block header
    pub fn nats_subject(&self) -> String {
        format!("newheads.{}.{}.{}", self.network, self.subnet, self.vm_type)
    }

    /// Create a new block header with network context
    pub fn new(
        network: String,
        subnet: String,
        vm_type: VmType,
        chain_id: String,
        chain_name: String,
        provider_id: String,
    ) -> Self {
        Self {
            network,
            subnet,
            vm_type,
            chain_id,
            chain_name,
            block_number: 0,
            block_hash: String::new(),
            parent_hash: String::new(),
            timestamp: 0,
            difficulty: None,
            gas_limit: None,
            gas_used: None,
            miner: None,
            extra_data: None,
            network_specific: serde_json::Value::Null,
            received_at: chrono::Utc::now(),
            provider_id,
            raw_data: None,
            rpc_url: None,
            ws_url: None,
        }
    }
}

/// Chain configuration for connecting to blockchain nodes (legacy single-node)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChainConfig {
    pub chain_id: String,
    pub chain_name: String,
    pub network: String, // e.g., "ethereum", "polygon", "bitcoin"
    pub subnet: String,  // e.g., "mainnet", "goerli", "testnet"
    pub vm_type: VmType, // e.g., "evm", "utxo", "svm"
    pub rpc_url: String,
    pub ws_url: String,
    pub chain_type: ChainType,
    pub network_id: Option<u64>,
    pub enabled: bool,

    // NATS subject configuration
    pub nats_subjects: NatsSubjects,
}

/// Enhanced node configuration with multiple endpoints (for Redis storage)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeConfiguration {
    pub network: String,    // e.g., "ethereum", "polygon", "bitcoin"
    pub subnet: String,     // e.g., "mainnet", "goerli", "testnet"
    pub chain_id: String,   // e.g., "ethereum-mainnet"
    pub chain_name: String, // e.g., "Ethereum Mainnet"
    pub vm_type: VmType,    // e.g., "evm", "utxo", "svm"
    pub chain_type: ChainType,
    pub network_id: Option<u64>,
    pub enabled: bool,
    pub nodes: Vec<NodeEndpoint>,
    pub node_strategy: NodeSelectionStrategy,
    pub nats_subjects: NatsSubjects,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: chrono::DateTime<chrono::Utc>,
}

impl NodeConfiguration {
    /// Get the unique key for this configuration (network.subnet)
    pub fn key(&self) -> String {
        format!("{}.{}", self.network, self.subnet)
    }

    /// Get the Redis key for storage
    pub fn redis_key(&self) -> String {
        format!("node:config:{}", self.key())
    }
}

/// Individual node endpoint configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeEndpoint {
    pub id: String,                      // Unique identifier for this node
    pub name: String,                    // Human-readable name (e.g., "Infura", "Alchemy")
    pub provider: String,                // Provider name (e.g., "infura", "alchemy", "quicknode")
    pub rpc_url: String,                 // HTTP RPC endpoint
    pub ws_url: String,                  // WebSocket endpoint
    pub priority: u8,                    // Priority (1 = highest, 255 = lowest)
    pub weight: u8,                      // Weight for load balancing (1-100)
    pub enabled: bool,                   // Whether this node is active
    pub rate_limit: Option<RateLimit>,   // Rate limiting configuration
    pub health_check: HealthCheckConfig, // Health check settings
}

/// Rate limiting configuration for a node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimit {
    pub requests_per_second: u32,
    pub burst_size: u32,
}

/// Health check configuration for a node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheckConfig {
    pub interval_seconds: u32,
    pub timeout_seconds: u32,
    pub failure_threshold: u32,
    pub recovery_threshold: u32,
}

impl Default for HealthCheckConfig {
    fn default() -> Self {
        Self {
            interval_seconds: 30,
            timeout_seconds: 5,
            failure_threshold: 3,
            recovery_threshold: 2,
        }
    }
}

/// Node selection strategy
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NodeSelectionStrategy {
    Priority,       // Use highest priority available node
    RoundRobin,     // Rotate through all enabled nodes
    WeightedRandom, // Random selection based on weights
    HealthBased,    // Select based on health metrics
    LoadBalanced,   // Balance based on current load
}

/// Virtual Machine / Execution Environment Types
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum VmType {
    Evm,            // Ethereum Virtual Machine (Ethereum, Polygon, BSC, etc.)
    Utxo,           // UTXO model (Bitcoin, Litecoin, etc.)
    Svm,            // Solana Virtual Machine
    Wasm,           // WebAssembly (Polkadot, Cosmos, etc.)
    Move,           // Move VM (Aptos, Sui)
    Cairo,          // Cairo VM (StarkNet)
    Custom(String), // Custom VM type
}

impl fmt::Display for VmType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let name = match self {
            VmType::Evm => "evm",
            VmType::Utxo => "utxo",
            VmType::Svm => "svm",
            VmType::Wasm => "wasm",
            VmType::Move => "move",
            VmType::Cairo => "cairo",
            VmType::Custom(name) => name,
        };
        write!(f, "{}", name)
    }
}

/// NATS subject configuration for a chain
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NatsSubjects {
    /// Subject for publishing newheads: newheads.{network}.{subnet}.{vm_type}
    pub newheads_output: String,

    /// Subject for receiving configuration commands
    pub config_input: String,

    /// Subject for publishing status updates
    pub status_output: String,

    /// Subject for receiving control commands (start/stop/restart)
    pub control_input: String,
}

impl NatsSubjects {
    /// Generate NATS subjects for a chain configuration
    pub fn generate(network: &str, subnet: &str, vm_type: &VmType, chain_id: &str) -> Self {
        Self {
            newheads_output: format!("newheads.{}.{}.{}", network, subnet, vm_type),
            config_input: format!("config.{}.input", chain_id),
            status_output: format!("status.{}.output", chain_id),
            control_input: format!("control.{}.input", chain_id),
        }
    }
}

/// Supported blockchain types and VM families
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ChainType {
    // Ethereum Virtual Machine (EVM) based chains
    Ethereum,
    Polygon,
    Arbitrum,
    Optimism,
    Bsc,
    Avalanche,
    Fantom,

    // Bitcoin and Bitcoin-like chains
    Bitcoin,
    BitcoinTestnet,
    Litecoin,
    Dogecoin,

    // Other blockchain types
    Solana,
    Cardano,
    Polkadot,
    Cosmos,
    Aptos,
    Sui,
    StarkNet,

    // Testnets
    EthereumGoerli,
    EthereumSepolia,
    PolygonMumbai,
}

impl fmt::Display for ChainType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let name = match self {
            ChainType::Ethereum => "ethereum",
            ChainType::Polygon => "polygon",
            ChainType::Arbitrum => "arbitrum",
            ChainType::Optimism => "optimism",
            ChainType::Bsc => "bsc",
            ChainType::Avalanche => "avalanche",
            ChainType::Fantom => "fantom",
            ChainType::Bitcoin => "bitcoin",
            ChainType::BitcoinTestnet => "bitcoin-testnet",
            ChainType::Litecoin => "litecoin",
            ChainType::Dogecoin => "dogecoin",
            ChainType::Solana => "solana",
            ChainType::Cardano => "cardano",
            ChainType::Polkadot => "polkadot",
            ChainType::Cosmos => "cosmos",
            ChainType::EthereumGoerli => "ethereum-goerli",
            ChainType::EthereumSepolia => "ethereum-sepolia",
            ChainType::PolygonMumbai => "polygon-mumbai",
            ChainType::Aptos => "aptos",
            ChainType::Sui => "sui",
            ChainType::StarkNet => "starknet",
        };
        write!(f, "{}", name)
    }
}

/// Subscription status for blockchain connections
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SubscriptionStatus {
    Active,
    Connecting,
    Disconnected,
    Error(String),
}

impl fmt::Display for SubscriptionStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SubscriptionStatus::Active => write!(f, "active"),
            SubscriptionStatus::Connecting => write!(f, "connecting"),
            SubscriptionStatus::Disconnected => write!(f, "disconnected"),
            SubscriptionStatus::Error(msg) => write!(f, "error: {}", msg),
        }
    }
}

/// Subscription information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubscriptionInfo {
    pub chain_id: String,
    pub status: SubscriptionStatus,
    pub last_block: Option<u64>,
    pub connected_at: Option<u64>,
    pub error_message: Option<String>,
}

/// Common trait for all blockchain clients
#[async_trait::async_trait]
pub trait BlockchainClient: Send + Sync {
    /// Subscribe to new block headers
    /// Returns a receiver channel that will receive new block headers
    async fn subscribe_newheads(&self) -> Result<mpsc::UnboundedReceiver<BlockHeader>>;

    /// Get the latest block header via RPC call
    async fn get_latest_header(&self) -> Result<BlockHeader>;

    /// Test connection to the blockchain node
    async fn test_connection(&self) -> Result<()>;

    /// Get the chain configuration
    fn get_config(&self) -> &ChainConfig;

    /// Check if the client is connected
    fn is_connected(&self) -> bool;

    /// Get connection statistics
    fn get_stats(&self) -> ConnectionStats;
}

/// Connection statistics for monitoring
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionStats {
    pub connected: bool,
    pub connected_at: Option<u64>,
    pub last_block_received: Option<u64>,
    pub total_blocks_received: u64,
    pub connection_errors: u64,
    pub last_error: Option<String>,
    pub last_error_at: Option<u64>,
}

impl Default for ConnectionStats {
    fn default() -> Self {
        Self {
            connected: false,
            connected_at: None,
            last_block_received: None,
            total_blocks_received: 0,
            connection_errors: 0,
            last_error: None,
            last_error_at: None,
        }
    }
}

/// Helper function to get current Unix timestamp
pub fn current_timestamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

/// Helper function to parse hex string to u64
pub fn parse_hex_u64(hex_str: &str) -> Result<u64> {
    let hex_str = hex_str.strip_prefix("0x").unwrap_or(hex_str);
    u64::from_str_radix(hex_str, 16)
        .map_err(|e| anyhow::anyhow!("Failed to parse hex string '{}': {}", hex_str, e))
}

/// Helper function to format u64 as hex string
pub fn format_hex_u64(value: u64) -> String {
    format!("0x{:x}", value)
}

/// Configuration management commands
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ConfigCommand {
    /// Add a new chain configuration
    AddChain(ChainConfig),

    /// Update an existing chain configuration
    UpdateChain {
        chain_id: String,
        config: ChainConfig,
    },

    /// Remove a chain configuration
    RemoveChain { chain_id: String },

    /// Enable a chain (start subscription)
    EnableChain { chain_id: String },

    /// Disable a chain (stop subscription)
    DisableChain { chain_id: String },

    /// Get chain configuration
    GetChain { chain_id: String },

    /// List all chains
    ListChains,

    /// Get provider health status
    HealthCheck,
}

/// Control commands for managing subscriptions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ControlCommand {
    /// Start subscription for a chain
    Start { chain_id: String },

    /// Stop subscription for a chain
    Stop { chain_id: String },

    /// Restart subscription for a chain
    Restart { chain_id: String },

    /// Pause subscription (keep connection but don't publish)
    Pause { chain_id: String },

    /// Resume paused subscription
    Resume { chain_id: String },

    /// Get subscription status
    Status { chain_id: String },

    /// Get statistics for all subscriptions
    Stats,
}

/// Response types for commands
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CommandResponse {
    /// Success response
    Success {
        message: String,
        data: Option<serde_json::Value>,
    },

    /// Error response
    Error { message: String, code: String },

    /// Chain configuration response
    ChainConfig(ChainConfig),

    /// List of chain configurations
    ChainList(Vec<ChainConfig>),

    /// Subscription status response
    SubscriptionStatus(SubscriptionInfo),

    /// Statistics response
    Statistics(Vec<SubscriptionInfo>),
}
