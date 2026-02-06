//! HTTP RPC Provider for WasmCloud
//!
//! This provider handles all HTTP RPC operations for WasmCloud actors,
//! specifically designed for blockchain RPC calls without direct dependencies.
//!
//! Features:
//! - Multi-endpoint rotation with failover
//! - Redis-backed response caching
//! - Circuit breaker pattern per endpoint
//! - Automatic retry with exponential backoff

use anyhow::{anyhow, Result};
use reqwest::Client as HttpClient;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{debug, info};
use wasmcloud_provider_sdk::Provider;

// New modules for enhanced functionality
pub mod cache;
pub mod circuit_breaker;
pub mod endpoint_pool;

use cache::CacheConfig;
use circuit_breaker::CircuitBreakerConfig;
use endpoint_pool::{EndpointPool, EndpointPoolConfig, PoolHealthStatus, RpcRequest};

/// HTTP RPC Provider
///
/// Provides HTTP RPC capabilities to WasmCloud actors for blockchain calls
/// with multi-endpoint failover, caching, and circuit breakers
pub struct HttpRpcProvider {
    /// Endpoint pools per network (ethereum, polygon, etc.)
    endpoint_pools: Arc<RwLock<HashMap<String, Arc<EndpointPool>>>>,

    /// Configuration
    config: Arc<RwLock<ProviderConfig>>,
}

/// Provider configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderConfig {
    pub timeout_seconds: u64,
    pub max_retries: u32,
    pub retry_delay_ms: u64,
    pub user_agent: String,

    // Circuit breaker settings
    pub circuit_breaker_failure_threshold: u32,
    pub circuit_breaker_success_threshold: u32,
    pub circuit_breaker_timeout_seconds: u64,

    // Cache settings
    pub cache_enabled: bool,
    pub cache_redis_url: String,
    pub cache_default_ttl: u64,
    pub cache_block_ttl: u64,
    pub cache_tx_ttl: u64,
}

impl Default for ProviderConfig {
    fn default() -> Self {
        Self {
            timeout_seconds: 30,
            max_retries: 3,
            retry_delay_ms: 1000,
            user_agent: "WasmCloud-HTTP-RPC-Provider/1.0.0".to_string(),

            // Circuit breaker defaults
            circuit_breaker_failure_threshold: 5,
            circuit_breaker_success_threshold: 2,
            circuit_breaker_timeout_seconds: 30,

            // Cache defaults
            cache_enabled: true,
            cache_redis_url: "redis://redis.ekko.svc.cluster.local:6379".to_string(),
            cache_default_ttl: 60,
            cache_block_ttl: 300,
            cache_tx_ttl: 3600,
        }
    }
}

impl ProviderConfig {
    /// Load configuration from environment variables with fallback to defaults
    pub fn from_env() -> Self {
        let default = Self::default();

        Self {
            timeout_seconds: std::env::var("HTTP_RPC_TIMEOUT_SECONDS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.timeout_seconds),
            max_retries: std::env::var("HTTP_RPC_MAX_RETRIES")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.max_retries),
            retry_delay_ms: std::env::var("HTTP_RPC_RETRY_DELAY_MS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.retry_delay_ms),
            user_agent: std::env::var("HTTP_RPC_USER_AGENT").unwrap_or(default.user_agent),

            circuit_breaker_failure_threshold: std::env::var("HTTP_RPC_CB_FAILURE_THRESHOLD")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.circuit_breaker_failure_threshold),
            circuit_breaker_success_threshold: std::env::var("HTTP_RPC_CB_SUCCESS_THRESHOLD")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.circuit_breaker_success_threshold),
            circuit_breaker_timeout_seconds: std::env::var("HTTP_RPC_CB_TIMEOUT_SECONDS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.circuit_breaker_timeout_seconds),

            cache_enabled: std::env::var("HTTP_RPC_CACHE_ENABLED")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.cache_enabled),
            cache_redis_url: std::env::var("HTTP_RPC_CACHE_REDIS_URL")
                .unwrap_or(default.cache_redis_url),
            cache_default_ttl: std::env::var("HTTP_RPC_CACHE_DEFAULT_TTL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.cache_default_ttl),
            cache_block_ttl: std::env::var("HTTP_RPC_CACHE_BLOCK_TTL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.cache_block_ttl),
            cache_tx_ttl: std::env::var("HTTP_RPC_CACHE_TX_TTL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default.cache_tx_ttl),
        }
    }
}

// RpcRequest, RpcResponse, and RpcError are now defined in endpoint_pool module

impl HttpRpcProvider {
    /// Create provider from wasmCloud host data (for WADM deployment)
    ///
    /// Loads configuration from environment variables and creates provider instance.
    /// This is the entry point when deployed via wasmCloud/WADM.
    pub fn from_host_data(_host_data: wasmcloud_provider_sdk::HostData) -> Result<Self> {
        info!("🌟 Creating HTTP RPC Provider from wasmCloud host data");

        // Load configuration from environment variables
        let config = ProviderConfig::from_env();

        Ok(Self::with_config(config))
    }

    /// Create a new HTTP RPC provider with custom configuration
    pub fn with_config(config: ProviderConfig) -> Self {
        Self {
            endpoint_pools: Arc::new(RwLock::new(HashMap::new())),
            config: Arc::new(RwLock::new(config)),
        }
    }

    /// Create a new HTTP RPC provider with default configuration
    pub fn new() -> Self {
        Self::with_config(ProviderConfig::default())
    }

    /// Register RPC endpoints for a network
    pub async fn register_endpoints(&self, network: &str, endpoints: Vec<String>) -> Result<()> {
        let config = self.config.read().await;

        // Create endpoint pool configuration
        let pool_config = EndpointPoolConfig {
            endpoints,
            request_timeout: Duration::from_secs(config.timeout_seconds),
            max_retries: config.max_retries,
            circuit_breaker: CircuitBreakerConfig {
                failure_threshold: config.circuit_breaker_failure_threshold,
                success_threshold: config.circuit_breaker_success_threshold,
                timeout: Duration::from_secs(config.circuit_breaker_timeout_seconds),
                window_duration: Duration::from_secs(60),
            },
            cache: CacheConfig {
                redis_url: config.cache_redis_url.clone(),
                default_ttl: config.cache_default_ttl,
                block_ttl: config.cache_block_ttl,
                tx_ttl: config.cache_tx_ttl,
                enabled: config.cache_enabled,
            },
        };

        drop(config);

        // Create and initialize endpoint pool
        let pool = Arc::new(EndpointPool::new(network.to_string(), pool_config)?);
        pool.init().await?;

        // Store in registry
        let mut pools = self.endpoint_pools.write().await;
        pools.insert(network.to_string(), pool);

        info!("Registered endpoint pool for network: {}", network);
        Ok(())
    }

    /// Get endpoint pool for a network
    async fn get_pool(&self, network: &str) -> Result<Arc<EndpointPool>> {
        let pools = self.endpoint_pools.read().await;

        pools
            .get(network)
            .cloned()
            .ok_or_else(|| anyhow!("No endpoint pool configured for network: {}", network))
    }

    /// Make a blockchain-specific RPC call with failover and caching
    pub async fn blockchain_rpc(
        &self,
        network: &str,
        method: &str,
        params: Vec<Value>,
    ) -> Result<Value> {
        let pool = self.get_pool(network).await?;
        let request = RpcRequest::new(method, params);

        debug!("Making RPC call to {}: {}", network, method);

        let response = pool.call_with_failover(&request).await?;

        response
            .result
            .ok_or_else(|| anyhow!("No result in RPC response"))
    }

    /// Get health status for a network's endpoint pool
    pub async fn get_health_status(&self, network: &str) -> Result<PoolHealthStatus> {
        let pool = self.get_pool(network).await?;
        Ok(pool.health_status())
    }

    /// Get health status for all networks
    pub async fn get_all_health_status(&self) -> Vec<PoolHealthStatus> {
        let pools = self.endpoint_pools.read().await;

        pools.values().map(|pool| pool.health_status()).collect()
    }
}

/// Provider implementation for WasmCloud
impl Provider for HttpRpcProvider {
    /// Initialize the provider
    fn init(
        &self,
        _init_config: impl wasmcloud_provider_sdk::ProviderInitConfig,
    ) -> impl std::future::Future<Output = Result<()>> + Send {
        async move {
            info!("Initializing HTTP RPC provider with enhanced failover and caching");

            // Load configuration from environment variables
            let mut config = ProviderConfig::default();

            // Override with environment variables if present
            if let Ok(timeout) = std::env::var("RPC_TIMEOUT_SECONDS") {
                if let Ok(val) = timeout.parse() {
                    config.timeout_seconds = val;
                }
            }

            if let Ok(redis_url) = std::env::var("CACHE_REDIS_URL") {
                config.cache_redis_url = redis_url;
            }

            if let Ok(enabled) = std::env::var("CACHE_ENABLED") {
                config.cache_enabled = enabled.parse().unwrap_or(true);
            }

            *self.config.write().await = config;

            // Register default network endpoints from environment
            // Example: ETH_RPC_ENDPOINTS=https://endpoint1.com,https://endpoint2.com
            if let Ok(eth_endpoints) = std::env::var("ETH_RPC_ENDPOINTS") {
                let endpoints: Vec<String> =
                    eth_endpoints.split(',').map(|s| s.to_string()).collect();
                if !endpoints.is_empty() {
                    self.register_endpoints("ethereum", endpoints).await?;
                }
            } else {
                // Fallback to demo endpoints
                self.register_endpoints(
                    "ethereum",
                    vec![
                        "https://eth-mainnet.g.alchemy.com/v2/demo".to_string(),
                        "https://cloudflare-eth.com".to_string(),
                    ],
                )
                .await?;
            }

            if let Ok(btc_endpoints) = std::env::var("BTC_RPC_ENDPOINTS") {
                let endpoints: Vec<String> =
                    btc_endpoints.split(',').map(|s| s.to_string()).collect();
                if !endpoints.is_empty() {
                    self.register_endpoints("bitcoin", endpoints).await?;
                }
            }

            if let Ok(sol_endpoints) = std::env::var("SOL_RPC_ENDPOINTS") {
                let endpoints: Vec<String> =
                    sol_endpoints.split(',').map(|s| s.to_string()).collect();
                if !endpoints.is_empty() {
                    self.register_endpoints("solana", endpoints).await?;
                }
            }

            // Register Avalanche C-Chain endpoints
            if let Ok(avax_endpoints) = std::env::var("AVALANCHE_RPC_ENDPOINTS") {
                let endpoints: Vec<String> =
                    avax_endpoints.split(',').map(|s| s.to_string()).collect();
                if !endpoints.is_empty() {
                    self.register_endpoints("avalanche", endpoints).await?;
                }
            } else {
                // Fallback to public Avalanche endpoints
                self.register_endpoints(
                    "avalanche",
                    vec![
                        "https://api.avax.network/ext/bc/C/rpc".to_string(),
                        "https://avalanche-c-chain-rpc.publicnode.com".to_string(),
                    ],
                )
                .await?;
            }

            // Register Avalanche Fuji testnet endpoints if configured
            if let Ok(fuji_endpoints) = std::env::var("AVALANCHE_FUJI_RPC_ENDPOINTS") {
                let endpoints: Vec<String> =
                    fuji_endpoints.split(',').map(|s| s.to_string()).collect();
                if !endpoints.is_empty() {
                    self.register_endpoints("avalanche-fuji", endpoints).await?;
                }
            }

            info!("HTTP RPC provider initialized successfully");
            Ok(())
        }
    }

    /// Shutdown the provider
    fn shutdown(&self) -> impl std::future::Future<Output = Result<()>> + Send {
        async move {
            info!("Shutting down HTTP RPC provider");
            self.endpoint_pools.write().await.clear();
            Ok(())
        }
    }
}

/// HTTP handler implementation
/// This is what actors will call to make HTTP/RPC requests
pub struct HttpHandler {
    provider: Arc<HttpRpcProvider>,
    http_client: HttpClient,
}

impl HttpHandler {
    pub fn new(provider: Arc<HttpRpcProvider>) -> Self {
        let http_client = HttpClient::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to build HTTP client");

        Self {
            provider,
            http_client,
        }
    }

    /// Handle RPC request from actor
    pub async fn handle_rpc(
        &self,
        network: &str,
        method: &str,
        params: Vec<Value>,
    ) -> Result<Value> {
        self.provider.blockchain_rpc(network, method, params).await
    }

    /// Get health status for a network
    pub async fn get_health(&self, network: &str) -> Result<PoolHealthStatus> {
        self.provider.get_health_status(network).await
    }

    /// Get health status for all networks
    pub async fn get_all_health(&self) -> Vec<PoolHealthStatus> {
        self.provider.get_all_health_status().await
    }

    /// Handle raw HTTP POST request from actor (non-RPC)
    pub async fn handle_post(&self, url: &str, body: &str) -> Result<String> {
        let response = self
            .http_client
            .post(url)
            .header("Content-Type", "application/json")
            .body(body.to_string())
            .send()
            .await
            .map_err(|e| anyhow!("HTTP POST failed: {}", e))?;

        let text = response
            .text()
            .await
            .map_err(|e| anyhow!("Failed to read response: {}", e))?;

        Ok(text)
    }

    /// Handle raw HTTP GET request from actor (non-RPC)
    pub async fn handle_get(&self, url: &str) -> Result<String> {
        let response = self
            .http_client
            .get(url)
            .send()
            .await
            .map_err(|e| anyhow!("HTTP GET failed: {}", e))?;

        let text = response
            .text()
            .await
            .map_err(|e| anyhow!("Failed to read response: {}", e))?;

        Ok(text)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider>() {}
        assert_provider::<HttpRpcProvider>();
    }

    #[tokio::test]
    async fn test_provider_creation() {
        let provider = HttpRpcProvider::new();
        let pools = provider.endpoint_pools.read().await;
        assert_eq!(pools.len(), 0);
    }

    #[tokio::test]
    async fn test_config_default() {
        let config = ProviderConfig::default();
        assert_eq!(config.timeout_seconds, 30);
        assert_eq!(config.max_retries, 3);
        assert_eq!(config.circuit_breaker_failure_threshold, 5);
        assert_eq!(config.circuit_breaker_success_threshold, 2);
        assert!(config.cache_enabled);
    }

    #[tokio::test]
    async fn test_endpoint_registration() {
        let provider = HttpRpcProvider::new();

        let result = provider
            .register_endpoints("ethereum", vec!["http://localhost:8545".to_string()])
            .await;

        assert!(result.is_ok());

        let pools = provider.endpoint_pools.read().await;
        assert_eq!(pools.len(), 1);
        assert!(pools.contains_key("ethereum"));
    }

    #[tokio::test]
    async fn test_get_pool_not_found() {
        let provider = HttpRpcProvider::new();

        let result = provider.get_pool("nonexistent").await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_health_status_empty() {
        let provider = HttpRpcProvider::new();

        let statuses = provider.get_all_health_status().await;
        assert_eq!(statuses.len(), 0);
    }
}
