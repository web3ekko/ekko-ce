//! Endpoint pool with multi-endpoint rotation and failover
//!
//! Manages multiple RPC endpoints with:
//! - Round-robin load balancing
//! - Circuit breaker per endpoint
//! - Automatic failover to healthy endpoints
//! - Redis caching for responses
//!
//! This provides resilient RPC access even when individual endpoints fail.

use crate::cache::{CacheConfig, RpcCache};
use crate::circuit_breaker::{CircuitBreaker, CircuitBreakerConfig, CircuitState};
use anyhow::{anyhow, Result};
use reqwest::Client as HttpClient;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tracing::{debug, info, warn};

/// RPC request structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcRequest {
    pub jsonrpc: String,
    pub method: String,
    pub params: Vec<Value>,
    pub id: u64,
}

impl RpcRequest {
    pub fn new(method: &str, params: Vec<Value>) -> Self {
        Self {
            jsonrpc: "2.0".to_string(),
            method: method.to_string(),
            params,
            id: 1,
        }
    }
}

/// RPC response structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcResponse {
    pub jsonrpc: String,
    pub result: Option<Value>,
    pub error: Option<RpcError>,
    pub id: u64,
}

/// RPC error structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcError {
    pub code: i32,
    pub message: String,
    pub data: Option<Value>,
}

/// Endpoint pool configuration
#[derive(Debug, Clone)]
pub struct EndpointPoolConfig {
    /// List of RPC endpoint URLs
    pub endpoints: Vec<String>,

    /// HTTP request timeout
    pub request_timeout: Duration,

    /// Maximum retry attempts across all endpoints
    pub max_retries: u32,

    /// Circuit breaker configuration
    pub circuit_breaker: CircuitBreakerConfig,

    /// Cache configuration
    pub cache: CacheConfig,
}

impl Default for EndpointPoolConfig {
    fn default() -> Self {
        Self {
            endpoints: vec!["http://localhost:8545".to_string()],
            request_timeout: Duration::from_secs(10),
            max_retries: 3,
            circuit_breaker: CircuitBreakerConfig::default(),
            cache: CacheConfig::default(),
        }
    }
}

/// Endpoint pool for load balancing and failover
pub struct EndpointPool {
    /// HTTP client
    client: HttpClient,

    /// Circuit breakers per endpoint
    circuit_breakers: Vec<Arc<CircuitBreaker>>,

    /// Round-robin counter
    counter: AtomicUsize,

    /// RPC cache
    cache: Arc<RpcCache>,

    /// Configuration
    config: EndpointPoolConfig,

    /// Network name (for cache keys)
    network: String,
}

impl EndpointPool {
    /// Create a new endpoint pool
    pub fn new(network: String, config: EndpointPoolConfig) -> Result<Self> {
        if config.endpoints.is_empty() {
            return Err(anyhow!("At least one endpoint must be configured"));
        }

        let client = HttpClient::builder()
            .timeout(config.request_timeout)
            .user_agent("WasmCloud-HTTP-RPC/1.0")
            .build()
            .map_err(|e| anyhow!("Failed to build HTTP client: {}", e))?;

        // Create circuit breakers for each endpoint
        let circuit_breakers: Vec<Arc<CircuitBreaker>> = config
            .endpoints
            .iter()
            .map(|endpoint| {
                Arc::new(CircuitBreaker::new(
                    endpoint.clone(),
                    config.circuit_breaker.clone(),
                ))
            })
            .collect();

        let cache = Arc::new(RpcCache::new(config.cache.clone()));

        Ok(Self {
            client,
            circuit_breakers,
            counter: AtomicUsize::new(0),
            cache,
            config,
            network,
        })
    }

    /// Initialize the pool (connect cache, etc.)
    pub async fn init(&self) -> Result<()> {
        self.cache.connect().await?;
        info!(
            "Endpoint pool initialized for {} with {} endpoints",
            self.network,
            self.config.endpoints.len()
        );
        Ok(())
    }

    /// Get next healthy endpoint (round-robin with circuit breaker check)
    fn get_next_endpoint(&self) -> Option<(usize, Arc<CircuitBreaker>)> {
        let total_endpoints = self.circuit_breakers.len();

        // Try all endpoints starting from round-robin position
        for i in 0..total_endpoints {
            let index = (self.counter.fetch_add(1, Ordering::Relaxed) + i) % total_endpoints;
            let cb = &self.circuit_breakers[index];

            if cb.can_execute().is_ok() {
                return Some((index, cb.clone()));
            }
        }

        None
    }

    /// Call RPC with failover across endpoints
    pub async fn call_with_failover(&self, request: &RpcRequest) -> Result<RpcResponse> {
        // Check cache first
        let cache_key = self
            .cache
            .make_key(&self.network, &request.method, &request.params);

        if let Some(cached_value) = self.cache.get(&cache_key).await? {
            debug!("Cache hit for {}/{}", self.network, request.method);
            return Ok(RpcResponse {
                jsonrpc: "2.0".to_string(),
                result: Some(cached_value),
                error: None,
                id: request.id,
            });
        }

        let mut last_error = None;
        let mut attempts = 0;

        // Try with failover
        while attempts < self.config.max_retries {
            attempts += 1;

            // Get next healthy endpoint
            let (endpoint_idx, circuit_breaker) = match self.get_next_endpoint() {
                Some(ep) => ep,
                None => {
                    warn!("No healthy endpoints available for {}", self.network);
                    return Err(anyhow!(
                        "All endpoints are unhealthy (circuit breakers open)"
                    ));
                }
            };

            let endpoint = &self.config.endpoints[endpoint_idx];

            debug!(
                "Attempt {}/{} - Calling {} (endpoint: {})",
                attempts, self.config.max_retries, request.method, endpoint
            );

            match self.make_request(endpoint, request).await {
                Ok(response) => {
                    // Record success
                    circuit_breaker.record_success();

                    // Cache successful response if it has a result
                    if let Some(ref result) = response.result {
                        self.cache_response(&cache_key, &request.method, result)
                            .await?;
                    }

                    return Ok(response);
                }
                Err(e) => {
                    // Record failure
                    circuit_breaker.record_failure();

                    warn!(
                        "RPC call to {} failed (attempt {}/{}): {}",
                        endpoint, attempts, self.config.max_retries, e
                    );
                    last_error = Some(e);

                    // Small delay before retry
                    if attempts < self.config.max_retries {
                        tokio::time::sleep(Duration::from_millis(100 * attempts as u64)).await;
                    }
                }
            }
        }

        Err(last_error.unwrap_or_else(|| anyhow!("All RPC attempts failed")))
    }

    /// Make a single RPC request to an endpoint
    async fn make_request(&self, endpoint: &str, request: &RpcRequest) -> Result<RpcResponse> {
        let response = self
            .client
            .post(endpoint)
            .header("Content-Type", "application/json")
            .json(request)
            .send()
            .await
            .map_err(|e| anyhow!("HTTP request failed: {}", e))?;

        if !response.status().is_success() {
            return Err(anyhow!("HTTP error: status {}", response.status()));
        }

        let rpc_response: RpcResponse = response
            .json()
            .await
            .map_err(|e| anyhow!("Failed to parse RPC response: {}", e))?;

        if let Some(error) = &rpc_response.error {
            return Err(anyhow!("RPC error {}: {}", error.code, error.message));
        }

        Ok(rpc_response)
    }

    /// Cache response with appropriate TTL based on method and network
    async fn cache_response(&self, key: &str, method: &str, value: &Value) -> Result<()> {
        // Avalanche has 2s blocks vs Ethereum's 12s - adjust TTLs accordingly
        if self.network == "avalanche" || self.network == "avalanche-fuji" {
            // Avalanche-specific caching strategy (2-second block times)
            let ttl = if method.contains("blockNumber") {
                Duration::from_secs(2) // Cache for 1 block
            } else if method.contains("getBalance") || method.contains("call") {
                Duration::from_secs(10) // Cache for 5 blocks
            } else if method.contains("getBlockBy") || method.contains("getBlock") {
                Duration::from_secs(60) // Finalized blocks - 30 blocks
            } else if method.contains("getTransaction") || method.contains("Transaction") {
                Duration::from_secs(1800) // Immutable transactions - 30 minutes
            } else if method.contains("gasPrice")
                || method.contains("baseFee")
                || method.contains("PriorityFee")
            {
                Duration::from_secs(2) // Dynamic fee data - 1 block
            } else {
                Duration::from_secs(10) // Default for other methods
            };

            self.cache.set(key, value, ttl).await
        } else {
            // Standard caching for Ethereum and other chains (12-second blocks)
            if method.contains("getBlockBy") || method.contains("getBlock") {
                // Block data - longer TTL (immutable once finalized)
                self.cache.set_block(key, value).await
            } else if method.contains("getTransaction") || method.contains("Transaction") {
                // Transaction data - very long TTL (immutable)
                self.cache.set_transaction(key, value).await
            } else {
                // Default TTL for other methods
                self.cache.set_default(key, value).await
            }
        }
    }

    /// Get pool health status
    pub fn health_status(&self) -> PoolHealthStatus {
        let mut healthy = 0;
        let mut unhealthy = 0;
        let mut half_open = 0;

        for cb in &self.circuit_breakers {
            match cb.state() {
                CircuitState::Closed => healthy += 1,
                CircuitState::Open => unhealthy += 1,
                CircuitState::HalfOpen => half_open += 1,
            }
        }

        PoolHealthStatus {
            network: self.network.clone(),
            total_endpoints: self.circuit_breakers.len(),
            healthy_endpoints: healthy,
            unhealthy_endpoints: unhealthy,
            half_open_endpoints: half_open,
        }
    }

    /// Get reference to cache (for testing)
    pub fn cache(&self) -> &Arc<RpcCache> {
        &self.cache
    }
}

/// Pool health status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolHealthStatus {
    pub network: String,
    pub total_endpoints: usize,
    pub healthy_endpoints: usize,
    pub unhealthy_endpoints: usize,
    pub half_open_endpoints: usize,
}

impl PoolHealthStatus {
    pub fn is_healthy(&self) -> bool {
        self.healthy_endpoints > 0
    }

    pub fn health_percentage(&self) -> f64 {
        if self.total_endpoints == 0 {
            0.0
        } else {
            (self.healthy_endpoints as f64 / self.total_endpoints as f64) * 100.0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pool_config_default() {
        let config = EndpointPoolConfig::default();
        assert_eq!(config.endpoints.len(), 1);
        assert_eq!(config.max_retries, 3);
    }

    #[test]
    fn test_rpc_request_creation() {
        let request = RpcRequest::new("eth_blockNumber", vec![]);
        assert_eq!(request.jsonrpc, "2.0");
        assert_eq!(request.method, "eth_blockNumber");
        assert_eq!(request.id, 1);
    }

    #[tokio::test]
    async fn test_pool_creation() {
        let config = EndpointPoolConfig {
            endpoints: vec![
                "http://endpoint1.com".to_string(),
                "http://endpoint2.com".to_string(),
            ],
            ..Default::default()
        };

        let pool = EndpointPool::new("ethereum".to_string(), config).unwrap();

        let health = pool.health_status();
        assert_eq!(health.total_endpoints, 2);
        assert_eq!(health.healthy_endpoints, 2); // All start healthy
    }

    #[tokio::test]
    async fn test_pool_requires_endpoints() {
        let config = EndpointPoolConfig {
            endpoints: vec![],
            ..Default::default()
        };

        let result = EndpointPool::new("ethereum".to_string(), config);
        assert!(result.is_err());
    }

    #[test]
    fn test_health_status_percentage() {
        let status = PoolHealthStatus {
            network: "ethereum".to_string(),
            total_endpoints: 4,
            healthy_endpoints: 3,
            unhealthy_endpoints: 1,
            half_open_endpoints: 0,
        };

        assert_eq!(status.health_percentage(), 75.0);
        assert!(status.is_healthy());
    }

    #[test]
    fn test_health_status_all_unhealthy() {
        let status = PoolHealthStatus {
            network: "ethereum".to_string(),
            total_endpoints: 2,
            healthy_endpoints: 0,
            unhealthy_endpoints: 2,
            half_open_endpoints: 0,
        };

        assert_eq!(status.health_percentage(), 0.0);
        assert!(!status.is_healthy());
    }
}
