//! Django BlockchainNode integration
//!
//! This module handles the conversion between Django's BlockchainNode model
//! format and the provider's internal ChainConfig format.

use anyhow::{anyhow, Result};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::{debug, info, warn};

use crate::traits::{ChainConfig, ChainType, NatsSubjects, VmType};

/// Django BlockchainNode model representation
/// This matches the Python Django model in apps/api/app/models/blockchain.py
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DjangoBlockchainNode {
    pub chain_id: String,
    pub chain_name: String,
    pub network: String, // ethereum, polygon, bitcoin, solana
    pub subnet: String,  // mainnet, testnet, devnet
    pub vm_type: String, // EVM, UTXO, SVM, COSMOS
    pub rpc_url: String,
    pub ws_url: String,
    pub enabled: bool,
    pub is_primary: bool,
    pub priority: i32,

    // Health metrics (read-only for provider)
    pub latency_ms: Option<i32>,
    pub success_rate: Option<f64>,
    pub last_health_check: Option<String>,

    // Metadata
    pub created_at: String,
    pub updated_at: String,
}

impl DjangoBlockchainNode {
    /// Convert Django BlockchainNode to provider ChainConfig
    /// This EVM-specific provider only accepts EVM VM type
    pub fn to_chain_config(&self) -> Result<ChainConfig> {
        // Parse VM type - only accept EVM for this provider
        let vm_type = match self.vm_type.to_uppercase().as_str() {
            "EVM" => VmType::Evm,
            other => {
                return Err(anyhow!(
                    "This is an EVM-specific provider. VM type '{}' is not supported. \
                    Use the appropriate provider for {} chains.",
                    other,
                    other
                ));
            }
        };

        // Determine chain type from network and subnet
        let chain_type = determine_chain_type(&self.network, &self.subnet)?;

        // Generate NATS subjects based on network/subnet/vm_type
        let nats_subjects =
            NatsSubjects::generate(&self.network, &self.subnet, &vm_type, &self.chain_id);

        // Determine network_id if known
        let network_id = get_network_id(&self.network, &self.subnet);

        Ok(ChainConfig {
            chain_id: self.chain_id.clone(),
            chain_name: self.chain_name.clone(),
            network: self.network.clone(),
            subnet: self.subnet.clone(),
            vm_type,
            rpc_url: self.rpc_url.clone(),
            ws_url: self.ws_url.clone(),
            chain_type,
            network_id,
            enabled: self.enabled,
            nats_subjects,
        })
    }
}

/// Configuration manager for Django BlockchainNode integration
pub struct DjangoConfigManager {
    redis_client: redis::Client,
    redis_key_prefix: String,
}

impl DjangoConfigManager {
    /// Create a new Django configuration manager
    pub fn new(redis_url: &str) -> Result<Self> {
        let redis_client = redis::Client::open(redis_url)?;

        Ok(Self {
            redis_client,
            redis_key_prefix: "blockchain:nodes".to_string(), // Django's key pattern
        })
    }

    /// Load all blockchain node configurations from Django's Redis keys
    pub async fn load_all_nodes(&self) -> Result<HashMap<String, ChainConfig>> {
        let mut conn = self.redis_client.get_async_connection().await?;
        let pattern = format!("{}:*", self.redis_key_prefix);

        let keys: Vec<String> = conn.keys(pattern).await?;
        let mut configs = HashMap::new();

        for key in keys {
            // Extract chain_id from key (blockchain:nodes:{chain_id})
            let chain_id = key
                .split(':')
                .last()
                .ok_or_else(|| anyhow!("Invalid key format: {}", key))?;

            if let Ok(node_json) = conn.get::<_, String>(&key).await {
                match serde_json::from_str::<DjangoBlockchainNode>(&node_json) {
                    Ok(django_node) => match django_node.to_chain_config() {
                        Ok(config) => {
                            if config.enabled {
                                configs.insert(chain_id.to_string(), config);
                                debug!("Loaded enabled node: {}", chain_id);
                            } else {
                                debug!("Skipping disabled node: {}", chain_id);
                            }
                        }
                        Err(e) => {
                            warn!("Failed to convert Django node {}: {}", chain_id, e);
                        }
                    },
                    Err(e) => {
                        warn!("Failed to parse Django node from Redis key {}: {}", key, e);
                    }
                }
            }
        }

        info!(
            "Loaded {} enabled blockchain nodes from Django Redis keys",
            configs.len()
        );
        Ok(configs)
    }

    /// Load a specific blockchain node configuration
    pub async fn load_node(&self, chain_id: &str) -> Result<ChainConfig> {
        let mut conn = self.redis_client.get_async_connection().await?;
        let key = format!("{}:{}", self.redis_key_prefix, chain_id);

        let node_json: String = conn
            .get(&key)
            .await
            .map_err(|_| anyhow!("BlockchainNode not found for chain: {}", chain_id))?;

        let django_node: DjangoBlockchainNode = serde_json::from_str(&node_json)?;
        django_node.to_chain_config()
    }

    /// Subscribe to Django configuration updates
    pub async fn subscribe_to_updates(&self) -> Result<()> {
        let mut pubsub = self
            .redis_client
            .get_async_connection()
            .await?
            .into_pubsub();
        let channel = "blockchain:nodes:updates";

        // Subscribe to the Django update channel
        pubsub.subscribe(channel).await?;
        info!(
            "Subscribed to Django configuration updates on channel: {}",
            channel
        );

        // This would typically spawn a task to handle updates
        // For now, just return success
        Ok(())
    }
}

/// Determine ChainType from network and subnet strings
fn determine_chain_type(network: &str, subnet: &str) -> Result<ChainType> {
    let chain_type = match network.to_lowercase().as_str() {
        "ethereum" => match subnet.to_lowercase().as_str() {
            "mainnet" => ChainType::Ethereum,
            "goerli" => ChainType::EthereumGoerli,
            "sepolia" => ChainType::EthereumSepolia,
            _ => ChainType::Ethereum,
        },
        "polygon" => match subnet.to_lowercase().as_str() {
            "mumbai" => ChainType::PolygonMumbai,
            _ => ChainType::Polygon,
        },
        "arbitrum" => ChainType::Arbitrum,
        "optimism" => ChainType::Optimism,
        "bsc" | "binance" => ChainType::Bsc,
        "avalanche" => ChainType::Avalanche,
        "fantom" => ChainType::Fantom,
        "bitcoin" => match subnet.to_lowercase().as_str() {
            "testnet" => ChainType::BitcoinTestnet,
            _ => ChainType::Bitcoin,
        },
        "litecoin" => ChainType::Litecoin,
        "dogecoin" => ChainType::Dogecoin,
        "solana" => ChainType::Solana,
        "cardano" => ChainType::Cardano,
        "polkadot" => ChainType::Polkadot,
        "cosmos" => ChainType::Cosmos,
        "aptos" => ChainType::Aptos,
        "sui" => ChainType::Sui,
        "starknet" => ChainType::StarkNet,
        _ => {
            warn!("Unknown network type: {}, defaulting to Ethereum", network);
            ChainType::Ethereum
        }
    };

    Ok(chain_type)
}

/// Get known network IDs for chains
fn get_network_id(network: &str, subnet: &str) -> Option<u64> {
    match network.to_lowercase().as_str() {
        "ethereum" => match subnet.to_lowercase().as_str() {
            "mainnet" => Some(1),
            "goerli" => Some(5),
            "sepolia" => Some(11155111),
            _ => None,
        },
        "polygon" => match subnet.to_lowercase().as_str() {
            "mainnet" => Some(137),
            "mumbai" => Some(80001),
            _ => None,
        },
        "arbitrum" => match subnet.to_lowercase().as_str() {
            "mainnet" | "one" => Some(42161),
            "goerli" => Some(421613),
            _ => None,
        },
        "optimism" => match subnet.to_lowercase().as_str() {
            "mainnet" => Some(10),
            "goerli" => Some(420),
            _ => None,
        },
        "bsc" | "binance" => match subnet.to_lowercase().as_str() {
            "mainnet" => Some(56),
            "testnet" => Some(97),
            _ => None,
        },
        "avalanche" => match subnet.to_lowercase().as_str() {
            "mainnet" | "c-chain" => Some(43114),
            "fuji" => Some(43113),
            _ => None,
        },
        "fantom" => match subnet.to_lowercase().as_str() {
            "mainnet" | "opera" => Some(250),
            "testnet" => Some(4002),
            _ => None,
        },
        _ => None,
    }
}

/// Configuration update message from Django
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DjangoConfigUpdate {
    pub action: String, // "create", "update", "delete", "enable", "disable"
    pub chain_id: String,
    pub node: Option<DjangoBlockchainNode>,
    pub timestamp: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_django_node_to_chain_config() {
        let django_node = DjangoBlockchainNode {
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "EVM".to_string(),
            rpc_url: "https://mainnet.infura.io/v3/KEY".to_string(),
            ws_url: "wss://mainnet.infura.io/ws/v3/KEY".to_string(),
            enabled: true,
            is_primary: true,
            priority: 1,
            latency_ms: None,
            success_rate: None,
            last_health_check: None,
            created_at: "2025-01-14T00:00:00Z".to_string(),
            updated_at: "2025-01-14T00:00:00Z".to_string(),
        };

        let config = django_node.to_chain_config().unwrap();

        assert_eq!(config.chain_id, "ethereum-mainnet");
        assert_eq!(config.network, "ethereum");
        assert_eq!(config.subnet, "mainnet");
        assert_eq!(config.vm_type, VmType::Evm);
        assert_eq!(config.network_id, Some(1));
        assert_eq!(
            config.nats_subjects.newheads_output,
            "newheads.ethereum.mainnet.evm"
        );
        assert!(config.enabled);
    }

    #[test]
    fn test_network_id_mapping() {
        assert_eq!(get_network_id("ethereum", "mainnet"), Some(1));
        assert_eq!(get_network_id("ethereum", "goerli"), Some(5));
        assert_eq!(get_network_id("polygon", "mainnet"), Some(137));
        assert_eq!(get_network_id("polygon", "mumbai"), Some(80001));
        assert_eq!(get_network_id("avalanche", "mainnet"), Some(43114));
        assert_eq!(get_network_id("avalanche", "fuji"), Some(43113));
        assert_eq!(get_network_id("unknown", "mainnet"), None);
    }
}
