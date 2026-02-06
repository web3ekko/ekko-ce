//! Configuration for ABI decoder provider

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;

/// ABI decoder provider configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AbiDecoderConfig {
    /// Redis configuration for caching
    pub redis: RedisConfig,

    /// Hot cache configuration
    pub hot_cache: HotCacheConfig,

    /// External API sources for ABI downloads
    pub api_sources: HashMap<String, Vec<ApiSourceConfig>>,

    /// Rate limiting configuration
    pub rate_limiting: RateLimitingConfig,

    /// DuckLake configuration for ABI storage
    pub ducklake: DuckLakeConfig,

    /// Provider instance configuration
    pub instance_id: String,

    /// Enable metrics collection
    pub enable_metrics: bool,
}

/// Redis configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RedisConfig {
    /// Redis URL
    pub url: String,
    /// Connection timeout in seconds
    pub connection_timeout_secs: u64,
    /// Command timeout in seconds
    pub command_timeout_secs: u64,
    /// Maximum number of connections
    pub max_connections: u32,
    /// ABI cache TTL in seconds
    pub abi_cache_ttl_secs: u64,
    /// Key prefix for ABI cache
    pub abi_key_prefix: String,
}

/// Hot cache configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HotCacheConfig {
    /// Maximum number of ABIs to keep in memory
    pub max_size: usize,
    /// TTL for hot cache entries in seconds
    pub ttl_secs: u64,
}

/// External API source configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiSourceConfig {
    /// Source name (e.g., "etherscan", "sourcify")
    pub name: String,
    /// Base URL for the API
    pub base_url: String,
    /// API key (optional)
    pub api_key: Option<String>,
    /// Rate limit (requests per second)
    pub rate_limit_rps: f64,
    /// Request timeout in seconds
    pub timeout_secs: u64,
    /// Whether this source is enabled
    pub enabled: bool,
    /// Priority (lower number = higher priority)
    pub priority: u32,
}

/// Rate limiting configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitingConfig {
    /// Global rate limit for all API calls (requests per second)
    pub global_rps: f64,
    /// Per-source rate limits
    pub per_source_rps: HashMap<String, f64>,
}

/// DuckLake configuration for ABI storage
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuckLakeConfig {
    /// S3 endpoint
    pub s3_endpoint: String,
    /// S3 region
    pub s3_region: String,
    /// S3 bucket
    pub s3_bucket: String,
    /// S3 access key ID
    pub s3_access_key_id: String,
    /// S3 secret access key
    pub s3_secret_access_key: String,
    /// Base path for ABI storage
    pub base_path: String,
}

impl AbiDecoderConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Result<Self> {
        let redis_url = env::var("ABI_DECODER_REDIS_URL")
            .unwrap_or_else(|_| "redis://localhost:6379".to_string());

        let redis = RedisConfig {
            url: redis_url,
            connection_timeout_secs: env::var("ABI_DECODER_REDIS_CONNECTION_TIMEOUT")
                .unwrap_or_else(|_| "5".to_string())
                .parse()
                .unwrap_or(5),
            command_timeout_secs: env::var("ABI_DECODER_REDIS_COMMAND_TIMEOUT")
                .unwrap_or_else(|_| "30".to_string())
                .parse()
                .unwrap_or(30),
            max_connections: env::var("ABI_DECODER_REDIS_MAX_CONNECTIONS")
                .unwrap_or_else(|_| "10".to_string())
                .parse()
                .unwrap_or(10),
            abi_cache_ttl_secs: env::var("ABI_DECODER_CACHE_TTL_HOURS")
                .unwrap_or_else(|_| "24".to_string())
                .parse::<u64>()
                .unwrap_or(24)
                * 3600,
            abi_key_prefix: env::var("ABI_DECODER_REDIS_KEY_PREFIX")
                .unwrap_or_else(|_| "abi:".to_string()),
        };

        let hot_cache = HotCacheConfig {
            max_size: env::var("ABI_DECODER_HOT_CACHE_SIZE")
                .unwrap_or_else(|_| "1000".to_string())
                .parse()
                .unwrap_or(1000),
            ttl_secs: env::var("ABI_DECODER_HOT_CACHE_TTL_HOURS")
                .unwrap_or_else(|_| "1".to_string())
                .parse::<u64>()
                .unwrap_or(1)
                * 3600,
        };

        // Default API sources
        let mut api_sources = HashMap::new();

        // Ethereum mainnet sources
        let mut ethereum_mainnet = Vec::new();
        if let Ok(etherscan_key) = env::var("ETHERSCAN_API_KEY") {
            ethereum_mainnet.push(ApiSourceConfig {
                name: "etherscan".to_string(),
                base_url: "https://api.etherscan.io/api".to_string(),
                api_key: Some(etherscan_key),
                rate_limit_rps: 5.0,
                timeout_secs: 30,
                enabled: true,
                priority: 1,
            });
        }

        ethereum_mainnet.push(ApiSourceConfig {
            name: "sourcify".to_string(),
            base_url: "https://sourcify.dev/server".to_string(),
            api_key: None,
            rate_limit_rps: 10.0,
            timeout_secs: 30,
            enabled: true,
            priority: 2,
        });

        api_sources.insert("ethereum.mainnet".to_string(), ethereum_mainnet);

        // Polygon mainnet sources
        let mut polygon_mainnet = Vec::new();
        if let Ok(polygonscan_key) = env::var("POLYGONSCAN_API_KEY") {
            polygon_mainnet.push(ApiSourceConfig {
                name: "polygonscan".to_string(),
                base_url: "https://api.polygonscan.com/api".to_string(),
                api_key: Some(polygonscan_key),
                rate_limit_rps: 5.0,
                timeout_secs: 30,
                enabled: true,
                priority: 1,
            });
        }

        api_sources.insert("polygon.mainnet".to_string(), polygon_mainnet);

        let rate_limiting = RateLimitingConfig {
            global_rps: env::var("ABI_DECODER_GLOBAL_RATE_LIMIT")
                .unwrap_or_else(|_| "20.0".to_string())
                .parse()
                .unwrap_or(20.0),
            per_source_rps: HashMap::new(),
        };

        let ducklake = DuckLakeConfig {
            s3_endpoint: env::var("ABI_DECODER_S3_ENDPOINT")
                .unwrap_or_else(|_| "http://localhost:9000".to_string()),
            s3_region: env::var("ABI_DECODER_S3_REGION")
                .unwrap_or_else(|_| "us-east-1".to_string()),
            s3_bucket: env::var("ABI_DECODER_S3_BUCKET")
                .unwrap_or_else(|_| "ekko-ducklake".to_string()),
            s3_access_key_id: env::var("ABI_DECODER_S3_ACCESS_KEY_ID")
                .context("ABI_DECODER_S3_ACCESS_KEY_ID environment variable is required")?,
            s3_secret_access_key: env::var("ABI_DECODER_S3_SECRET_ACCESS_KEY")
                .context("ABI_DECODER_S3_SECRET_ACCESS_KEY environment variable is required")?,
            base_path: env::var("ABI_DECODER_BASE_PATH")
                .unwrap_or_else(|_| "s3://ekko-ducklake/abis".to_string()),
        };

        let instance_id = env::var("ABI_DECODER_INSTANCE_ID")
            .unwrap_or_else(|_| uuid::Uuid::new_v4().to_string());

        let enable_metrics = env::var("ABI_DECODER_ENABLE_METRICS")
            .unwrap_or_else(|_| "false".to_string())
            .parse()
            .unwrap_or(false);

        Ok(Self {
            redis,
            hot_cache,
            api_sources,
            rate_limiting,
            ducklake,
            instance_id,
            enable_metrics,
        })
    }

    /// Validate configuration
    pub fn validate(&self) -> Result<()> {
        // Validate Redis URL
        if self.redis.url.is_empty() {
            return Err(anyhow::anyhow!("Redis URL cannot be empty"));
        }

        // Validate hot cache size
        if self.hot_cache.max_size == 0 {
            return Err(anyhow::anyhow!("Hot cache size must be greater than 0"));
        }

        // Validate API sources (allow empty for testing)
        for (_network, sources) in &self.api_sources {
            for source in sources {
                if source.base_url.is_empty() {
                    return Err(anyhow::anyhow!(
                        "Base URL cannot be empty for source: {}",
                        source.name
                    ));
                }
            }
        }

        // Validate DuckLake configuration
        if self.ducklake.s3_access_key_id.is_empty() {
            return Err(anyhow::anyhow!("S3 access key ID cannot be empty"));
        }

        if self.ducklake.s3_secret_access_key.is_empty() {
            return Err(anyhow::anyhow!("S3 secret access key cannot be empty"));
        }

        Ok(())
    }

    /// Get API sources for a network
    pub fn get_api_sources(&self, network: &str, subnet: &str) -> Vec<&ApiSourceConfig> {
        let network_key = format!("{}.{}", network, subnet);
        self.api_sources
            .get(&network_key)
            .map(|sources| {
                let mut sorted_sources: Vec<&ApiSourceConfig> =
                    sources.iter().filter(|s| s.enabled).collect();
                sorted_sources.sort_by_key(|s| s.priority);
                sorted_sources
            })
            .unwrap_or_default()
    }
}

impl Default for AbiDecoderConfig {
    fn default() -> Self {
        Self {
            redis: RedisConfig {
                url: "redis://localhost:6379".to_string(),
                connection_timeout_secs: 5,
                command_timeout_secs: 30,
                max_connections: 10,
                abi_cache_ttl_secs: 24 * 3600,
                abi_key_prefix: "abi:".to_string(),
            },
            hot_cache: HotCacheConfig {
                max_size: 1000,
                ttl_secs: 3600,
            },
            api_sources: HashMap::new(),
            rate_limiting: RateLimitingConfig {
                global_rps: 20.0,
                per_source_rps: HashMap::new(),
            },
            ducklake: DuckLakeConfig {
                s3_endpoint: "http://localhost:9000".to_string(),
                s3_region: "us-east-1".to_string(),
                s3_bucket: "ekko-ducklake".to_string(),
                s3_access_key_id: "minioadmin".to_string(),
                s3_secret_access_key: "minioadmin".to_string(),
                base_path: "s3://ekko-ducklake/abis".to_string(),
            },
            instance_id: uuid::Uuid::new_v4().to_string(),
            enable_metrics: false,
        }
    }
}
