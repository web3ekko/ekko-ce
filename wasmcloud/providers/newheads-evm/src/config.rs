//! # Configuration Management for Newheads Provider
//!
//! Simple provider-specific configuration loaded from Redis.
//! Each provider instance has its own unique config key.

use crate::django_integration::{DjangoBlockchainNode, DjangoConfigManager};
use crate::traits::ChainConfig;
use anyhow::{anyhow, Result};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use tracing::{debug, info, warn};

/// Provider configuration loaded from Redis
///
/// Redis key format: `provider:config:{provider_name}`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderConfig {
    /// Provider identifier (must match the provider name constant)
    pub provider_name: String,

    /// Unique chain identifier (e.g., "ethereum-mainnet")
    pub chain_id: String,

    /// Human-readable chain name
    pub chain_name: String,

    /// Network name (e.g., "ethereum", "avalanche")
    pub network: String,

    /// Subnet/environment (e.g., "mainnet", "testnet", "goerli")
    pub subnet: String,

    /// VM type - must be "evm" for this provider
    pub vm_type: String,

    /// HTTP RPC endpoint URL
    pub rpc_url: String,

    /// WebSocket endpoint URL for subscriptions
    pub ws_url: String,

    /// Whether this configuration is enabled
    pub enabled: bool,
}

impl ProviderConfig {
    /// Validate that this config is suitable for the newheads-evm provider
    pub fn validate(&self) -> Result<()> {
        if self.vm_type.to_lowercase() != "evm" {
            return Err(anyhow!(
                "Invalid vm_type '{}' for newheads-evm provider. Expected 'evm'",
                self.vm_type
            ));
        }

        if self.ws_url.is_empty() {
            return Err(anyhow!("ws_url is required for newheads subscriptions"));
        }

        if !self.enabled {
            return Err(anyhow!("Provider config is disabled"));
        }

        Ok(())
    }

    /// Generate the NATS subject for publishing newheads
    /// Format: newheads.{network}.{subnet}.evm
    pub fn nats_subject(&self) -> String {
        format!("newheads.{}.{}.evm", self.network, self.subnet)
    }
}

/// Load provider configuration from Redis
///
/// Looks up: `provider:config:{provider_name}`
///
/// # Arguments
/// * `redis_url` - Redis connection URL
/// * `provider_name` - The provider name constant (e.g., "newheads-evm")
///
/// # Returns
/// * `Ok(ProviderConfig)` - Successfully loaded and validated config
/// * `Err` - Config not found or invalid
pub async fn load_provider_config(redis_url: &str, provider_name: &str) -> Result<ProviderConfig> {
    let redis_client = redis::Client::open(redis_url)?;
    let mut conn = redis_client.get_multiplexed_async_connection().await?;

    let key = format!("provider:config:{}", provider_name);
    debug!("Loading provider config from Redis key: {}", key);

    let config_json: Option<String> = conn.get(&key).await?;

    let config_json = config_json.ok_or_else(|| {
        anyhow!(
            "Provider config not found in Redis. Expected key: '{}'\n\
             Please create the config with the following format:\n\
             {{\n\
               \"provider_name\": \"{}\",\n\
               \"chain_id\": \"ethereum-mainnet\",\n\
               \"chain_name\": \"Ethereum Mainnet\",\n\
               \"network\": \"ethereum\",\n\
               \"subnet\": \"mainnet\",\n\
               \"vm_type\": \"evm\",\n\
               \"rpc_url\": \"https://mainnet.infura.io/v3/YOUR_KEY\",\n\
               \"ws_url\": \"wss://mainnet.infura.io/ws/v3/YOUR_KEY\",\n\
               \"enabled\": true\n\
             }}",
            key,
            provider_name
        )
    })?;

    let config: ProviderConfig = serde_json::from_str(&config_json).map_err(|e| {
        anyhow!(
            "Failed to parse provider config from Redis key '{}': {}",
            key,
            e
        )
    })?;

    // Validate the config
    config.validate()?;

    info!(
        "Loaded provider config: {} -> {} ({})",
        config.provider_name, config.chain_name, config.ws_url
    );

    Ok(config)
}

/// Load all enabled chain configs from Django Redis keys, with env fallback.
pub async fn load_chain_configs(redis_url: &str) -> Result<Vec<ChainConfig>> {
    let manager = DjangoConfigManager::new(redis_url)?;

    match manager.load_all_nodes().await {
        Ok(configs) if !configs.is_empty() => {
            let mut values: Vec<ChainConfig> = configs.into_values().collect();
            values.sort_by(|a, b| a.chain_id.cmp(&b.chain_id));
            info!(
                "Loaded {} enabled EVM chain configs from Django Redis keys",
                values.len()
            );
            return Ok(values);
        }
        Ok(_) => {
            warn!(
                "No enabled Django blockchain nodes found in Redis, falling back to env defaults"
            );
        }
        Err(e) => {
            warn!("Failed to load Django blockchain nodes from Redis: {}. Falling back to env defaults", e);
        }
    }

    let defaults = load_default_chain_configs_from_env()?;
    if defaults.is_empty() {
        return Err(anyhow!(
            "No EVM chain configs found in Redis or environment. \
             Configure Django BlockchainNode entries or set EVM_NEWHEADS_DEFAULT_* env vars."
        ));
    }

    Ok(defaults)
}

fn load_default_chain_configs_from_env() -> Result<Vec<ChainConfig>> {
    let chain_ids = std::env::var("EVM_NEWHEADS_DEFAULT_CHAINS")
        .unwrap_or_default()
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>();

    if chain_ids.is_empty() {
        info!("EVM_NEWHEADS_DEFAULT_CHAINS is empty; no env fallback chains configured");
        return Ok(Vec::new());
    }

    info!(
        "Loading {} EVM chain configs from env defaults: {}",
        chain_ids.len(),
        chain_ids.join(", ")
    );

    let mut configs = Vec::new();
    for (index, chain_id) in chain_ids.iter().enumerate() {
        match build_chain_config_from_env(chain_id, index as i32) {
            Ok(Some(config)) => {
                info!(
                    "Loaded env chain {} ({}/{}) enabled={} ws_url={}",
                    config.chain_id, config.network, config.subnet, config.enabled, config.ws_url
                );
                configs.push(config)
            }
            Ok(None) => {}
            Err(e) => warn!("Skipping env chain {}: {}", chain_id, e),
        }
    }

    Ok(configs)
}

fn build_chain_config_from_env(chain_id: &str, priority: i32) -> Result<Option<ChainConfig>> {
    let chain_name = read_chain_env(chain_id, "CHAIN_NAME").unwrap_or_else(|| chain_id.to_string());
    let network = read_chain_env(chain_id, "NETWORK")
        .ok_or_else(|| anyhow!("Missing NETWORK env for {}", chain_id))?;
    let subnet = read_chain_env(chain_id, "SUBNET")
        .ok_or_else(|| anyhow!("Missing SUBNET env for {}", chain_id))?;
    let rpc_url = read_chain_env(chain_id, "RPC_URL")
        .ok_or_else(|| anyhow!("Missing RPC_URL env for {}", chain_id))?;
    let ws_url = read_chain_env(chain_id, "WS_URL")
        .ok_or_else(|| anyhow!("Missing WS_URL env for {}", chain_id))?;

    if ws_url.trim().is_empty() || rpc_url.trim().is_empty() {
        warn!("Skipping {}: RPC/WS URL empty", chain_id);
        return Ok(None);
    }

    let enabled = read_chain_env(chain_id, "ENABLED")
        .map(|value| parse_bool_flag(&value))
        .unwrap_or(true);

    if !enabled {
        debug!("Skipping disabled env chain {}", chain_id);
        return Ok(None);
    }

    let now = chrono::Utc::now().to_rfc3339();
    let node = DjangoBlockchainNode {
        chain_id: chain_id.to_string(),
        chain_name,
        network,
        subnet,
        vm_type: "EVM".to_string(),
        rpc_url,
        ws_url,
        enabled,
        is_primary: priority == 0,
        priority,
        latency_ms: None,
        success_rate: None,
        last_health_check: None,
        created_at: now.clone(),
        updated_at: now,
    };

    let config = node.to_chain_config()?;
    Ok(Some(config))
}

fn read_chain_env(chain_id: &str, suffix: &str) -> Option<String> {
    let key = chain_env_key(chain_id, suffix);
    std::env::var(key)
        .ok()
        .map(|value| value.trim().to_string())
}

fn chain_env_key(chain_id: &str, suffix: &str) -> String {
    let normalized = chain_id
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() {
                c.to_ascii_uppercase()
            } else {
                '_'
            }
        })
        .collect::<String>();
    format!("EVM_NEWHEADS_CHAIN_{}_{}", normalized, suffix)
}

fn parse_bool_flag(value: &str) -> bool {
    matches!(
        value.trim().to_lowercase().as_str(),
        "1" | "true" | "yes" | "y" | "on"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nats_subject_generation() {
        let config = ProviderConfig {
            provider_name: "newheads-evm".to_string(),
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            rpc_url: "https://example.com".to_string(),
            ws_url: "wss://example.com".to_string(),
            enabled: true,
        };

        assert_eq!(config.nats_subject(), "newheads.ethereum.mainnet.evm");
    }

    #[test]
    fn test_config_validation_valid() {
        let config = ProviderConfig {
            provider_name: "newheads-evm".to_string(),
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            rpc_url: "https://example.com".to_string(),
            ws_url: "wss://example.com".to_string(),
            enabled: true,
        };

        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_config_validation_wrong_vm_type() {
        let config = ProviderConfig {
            provider_name: "newheads-evm".to_string(),
            chain_id: "bitcoin-mainnet".to_string(),
            chain_name: "Bitcoin".to_string(),
            network: "bitcoin".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "utxo".to_string(),
            rpc_url: "https://example.com".to_string(),
            ws_url: "wss://example.com".to_string(),
            enabled: true,
        };

        assert!(config.validate().is_err());
    }

    #[test]
    fn test_config_validation_disabled() {
        let config = ProviderConfig {
            provider_name: "newheads-evm".to_string(),
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            rpc_url: "https://example.com".to_string(),
            ws_url: "wss://example.com".to_string(),
            enabled: false,
        };

        assert!(config.validate().is_err());
    }
}
