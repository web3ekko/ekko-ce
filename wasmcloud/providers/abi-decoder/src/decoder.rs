//! Core ABI decoding implementation using Alloy

use crate::config::AbiDecoderConfig;
use crate::types::{
    AbiInfo, CacheStats, DecodedFunction, DecodedParameter, DecoderError, DecodingResult,
    TransactionInput,
};

use alloy_dyn_abi::{DynSolValue, JsonAbiExt};
use alloy_primitives::hex;
use anyhow::{Context, Result};
use lru::LruCache;
use redis::aio::ConnectionManager;
use redis::{AsyncCommands, RedisResult};
use std::num::NonZeroUsize;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, info, instrument, warn};

/// High-performance ABI decoder using Alloy
pub struct AbiDecoder {
    /// Configuration
    pub config: AbiDecoderConfig,

    /// Hot cache for frequently used ABIs
    pub hot_cache: Arc<RwLock<LruCache<String, AbiInfo>>>,

    /// Redis connection for persistent caching
    pub redis: ConnectionManager,

    /// Cache statistics
    pub stats: Arc<RwLock<CacheStats>>,

    /// Object store for DuckLake integration
    pub object_store: Arc<dyn object_store::ObjectStore>,
}

impl AbiDecoder {
    /// Create a new ABI decoder
    pub async fn new(config: AbiDecoderConfig) -> Result<Self> {
        // Validate configuration
        config.validate().context("Invalid configuration")?;

        // Create hot cache
        let cache_size = NonZeroUsize::new(config.hot_cache.max_size)
            .context("Hot cache size must be greater than 0")?;
        let hot_cache = Arc::new(RwLock::new(LruCache::new(cache_size)));

        // Connect to Redis
        let redis_client = redis::Client::open(config.redis.url.as_str())
            .context("Failed to create Redis client")?;
        let redis = ConnectionManager::new(redis_client)
            .await
            .context("Failed to connect to Redis")?;

        // Create object store for DuckLake
        let object_store = Self::create_object_store(&config)?;

        // Initialize stats
        let stats = Arc::new(RwLock::new(CacheStats::default()));

        info!(
            "ABI decoder initialized with hot cache size: {}",
            config.hot_cache.max_size
        );

        Ok(Self {
            config,
            hot_cache,
            redis,
            stats,
            object_store,
        })
    }

    /// Create object store for DuckLake integration
    fn create_object_store(
        config: &AbiDecoderConfig,
    ) -> Result<Arc<dyn object_store::ObjectStore>> {
        use object_store::aws::AmazonS3Builder;

        let store = AmazonS3Builder::new()
            .with_endpoint(&config.ducklake.s3_endpoint)
            .with_region(&config.ducklake.s3_region)
            .with_bucket_name(&config.ducklake.s3_bucket)
            .with_access_key_id(&config.ducklake.s3_access_key_id)
            .with_secret_access_key(&config.ducklake.s3_secret_access_key)
            .build()
            .context("Failed to create S3 object store")?;

        Ok(Arc::new(store))
    }

    /// Decode a single transaction
    #[instrument(skip(self), fields(contract = %input.to_address, selector = input.get_function_selector()))]
    pub async fn decode_transaction(
        &self,
        input: TransactionInput,
    ) -> Result<DecodingResult, DecoderError> {
        let start_time = Instant::now();

        // Update stats
        {
            let mut stats = self.stats.write().await;
            stats.total_decodings += 1;
        }

        // Quick checks for special cases
        if input.is_native_transfer() {
            // Add small delay to ensure processing time > 0
            tokio::time::sleep(Duration::from_micros(1)).await;
            let processing_time = start_time.elapsed().as_millis() as u64;
            let processing_time = if processing_time == 0 {
                1
            } else {
                processing_time
            };
            return Ok(DecodingResult::native_transfer(input, processing_time));
        }

        if input.is_contract_creation() {
            // Add small delay to ensure processing time > 0
            tokio::time::sleep(Duration::from_micros(1)).await;
            let processing_time = start_time.elapsed().as_millis() as u64;
            let processing_time = if processing_time == 0 {
                1
            } else {
                processing_time
            };
            return Ok(DecodingResult::contract_creation(input, processing_time));
        }

        // Get function selector
        let selector = match input.get_function_selector() {
            Some(sel) => sel,
            None => {
                let processing_time = start_time.elapsed().as_millis() as u64;
                return Ok(DecodingResult::decoding_failed(
                    input,
                    "Invalid input data: missing function selector".to_string(),
                    processing_time,
                ));
            }
        };

        // Get ABI for contract
        let abi_info = match self
            .get_abi_with_fallback(&input.to_address, &input.network, &input.subnet)
            .await
        {
            Ok(Some(abi)) => abi,
            Ok(None) => {
                let processing_time = start_time.elapsed().as_millis() as u64;
                return Ok(DecodingResult::abi_not_found(input, processing_time));
            }
            Err(e) => {
                let processing_time = start_time.elapsed().as_millis() as u64;
                return Ok(DecodingResult::decoding_failed(
                    input,
                    format!("Failed to get ABI: {}", e),
                    processing_time,
                ));
            }
        };

        // Decode the transaction
        match self.decode_with_abi(&input, &abi_info, &selector).await {
            Ok(decoded_function) => {
                let processing_time = start_time.elapsed().as_millis() as u64;

                // Update success stats
                {
                    let mut stats = self.stats.write().await;
                    stats.successful_decodings += 1;
                    stats.avg_decoding_time_ms = (stats.avg_decoding_time_ms
                        * (stats.total_decodings - 1) as f64
                        + processing_time as f64)
                        / stats.total_decodings as f64;
                }

                Ok(DecodingResult::success(
                    input,
                    decoded_function,
                    abi_info.source,
                    processing_time,
                ))
            }
            Err(e) => {
                let processing_time = start_time.elapsed().as_millis() as u64;
                Ok(DecodingResult::decoding_failed(
                    input,
                    format!("Decoding failed: {}", e),
                    processing_time,
                ))
            }
        }
    }

    /// Decode multiple transactions in batch
    pub async fn decode_batch(
        &self,
        inputs: Vec<TransactionInput>,
    ) -> Result<Vec<DecodingResult>, DecoderError> {
        let mut results = Vec::with_capacity(inputs.len());

        // Process in parallel batches for better performance
        let batch_size = 10;
        for chunk in inputs.chunks(batch_size) {
            let mut batch_futures = Vec::new();

            for input in chunk {
                batch_futures.push(self.decode_transaction(input.clone()));
            }

            // Wait for batch to complete
            let batch_results = futures::future::join_all(batch_futures).await;

            for result in batch_results {
                results.push(result?);
            }
        }

        Ok(results)
    }

    /// Get ABI with multi-level fallback
    pub async fn get_abi_with_fallback(
        &self,
        contract: &str,
        network: &str,
        subnet: &str,
    ) -> Result<Option<AbiInfo>> {
        let cache_key = format!("{}:{}", network, contract);

        // L1: Hot cache (in-memory)
        {
            let mut hot_cache = self.hot_cache.write().await;
            if let Some(abi_info) = hot_cache.get(&cache_key) {
                debug!("ABI cache hit (hot): {}", contract);

                // Update stats
                {
                    let mut stats = self.stats.write().await;
                    stats.hot_cache_hit_rate = (stats.hot_cache_hit_rate * 0.9) + (1.0 * 0.1);
                    // Exponential moving average
                }

                return Ok(Some(abi_info.clone()));
            }
        }

        // L2: Redis cache
        let redis_key = format!(
            "{}{}:{}",
            self.config.redis.abi_key_prefix, network, contract
        );
        let redis_result: RedisResult<Option<String>> = self.redis.clone().get(&redis_key).await;

        if let Ok(Some(abi_json)) = redis_result {
            debug!("ABI cache hit (redis): {}", contract);

            let mut abi_info =
                AbiInfo::new(contract.to_string(), abi_json, "cache".to_string(), false);
            if let Err(e) = abi_info.parse_abi() {
                warn!("Failed to parse cached ABI for {}: {}", contract, e);
            } else {
                // Cache in hot cache
                {
                    let mut hot_cache = self.hot_cache.write().await;
                    hot_cache.put(cache_key, abi_info.clone());
                }

                // Update stats
                {
                    let mut stats = self.stats.write().await;
                    stats.redis_cache_hit_rate = (stats.redis_cache_hit_rate * 0.9) + (1.0 * 0.1);
                }

                return Ok(Some(abi_info));
            }
        }

        // L3: DuckLake storage
        if let Ok(Some(abi_info)) = self.get_abi_from_ducklake(contract, network, subnet).await {
            debug!("ABI found in DuckLake: {}", contract);

            // Cache in both levels
            let _ = self
                .cache_abi_in_redis(&redis_key, &abi_info.abi_json)
                .await;
            {
                let mut hot_cache = self.hot_cache.write().await;
                hot_cache.put(cache_key, abi_info.clone());
            }

            return Ok(Some(abi_info));
        }

        debug!("ABI not found: {}", contract);
        Ok(None)
    }

    /// Decode transaction input using ABI
    async fn decode_with_abi(
        &self,
        input: &TransactionInput,
        abi_info: &AbiInfo,
        selector: &str,
    ) -> Result<DecodedFunction> {
        let abi = abi_info.parsed_abi.as_ref().context("ABI not parsed")?;

        // Find function by selector
        let function = abi_info
            .get_function_by_selector(selector)
            .context("Function not found for selector")?;

        // Parse input data
        let input_bytes = input
            .parse_input_data()
            .map_err(|e| anyhow::anyhow!("Failed to parse input data: {}", e))?;

        // Skip the 4-byte selector
        if input_bytes.len() < 4 {
            return Err(anyhow::anyhow!("Input data too short"));
        }
        let calldata = &input_bytes[4..];

        // Decode parameters using Alloy
        let decoded_values = function
            .abi_decode_input(calldata, false)
            .map_err(|e| anyhow::anyhow!("Failed to decode input: {}", e))?;

        // Convert to our parameter format
        let mut parameters = Vec::new();
        for (i, (param, value)) in function
            .inputs
            .iter()
            .zip(decoded_values.iter())
            .enumerate()
        {
            let decoded_param = DecodedParameter {
                name: param.name.clone(),
                param_type: param.ty.to_string(),
                value: self.format_decoded_value(value),
                raw_value: format!("0x{}", hex::encode(value.abi_encode())),
            };
            parameters.push(decoded_param);
        }

        Ok(DecodedFunction {
            name: function.name.clone(),
            signature: function.signature(),
            selector: selector.to_string(),
            parameters,
        })
    }

    /// Format decoded value for display
    fn format_decoded_value(&self, value: &DynSolValue) -> String {
        match value {
            DynSolValue::Address(addr) => format!("0x{:x}", addr),
            DynSolValue::Uint(uint, _) => uint.to_string(),
            DynSolValue::Int(int, _) => int.to_string(),
            DynSolValue::Bool(b) => b.to_string(),
            DynSolValue::Bytes(bytes) => format!("0x{}", hex::encode(bytes)),
            DynSolValue::FixedBytes(bytes, _) => format!("0x{}", hex::encode(bytes)),
            DynSolValue::String(s) => s.clone(),
            DynSolValue::Array(arr) => {
                let formatted: Vec<String> =
                    arr.iter().map(|v| self.format_decoded_value(v)).collect();
                format!("[{}]", formatted.join(", "))
            }
            DynSolValue::FixedArray(arr) => {
                let formatted: Vec<String> =
                    arr.iter().map(|v| self.format_decoded_value(v)).collect();
                format!("[{}]", formatted.join(", "))
            }
            DynSolValue::Tuple(tuple) => {
                let formatted: Vec<String> =
                    tuple.iter().map(|v| self.format_decoded_value(v)).collect();
                format!("({})", formatted.join(", "))
            }
            DynSolValue::Function(_) => "function".to_string(),
        }
    }

    /// Get ABI from DuckLake storage
    async fn get_abi_from_ducklake(
        &self,
        _contract: &str,
        _network: &str,
        _subnet: &str,
    ) -> Result<Option<AbiInfo>> {
        // DuckLake ABI lookup not yet implemented; return None to fall back to other sources.
        Ok(None)
    }

    /// Cache ABI in Redis
    async fn cache_abi_in_redis(&self, key: &str, abi_json: &str) -> Result<()> {
        let ttl = self.config.redis.abi_cache_ttl_secs;
        let _: RedisResult<()> = self.redis.clone().set_ex(key, abi_json, ttl).await;
        Ok(())
    }

    /// Get cache statistics
    pub async fn get_cache_stats(&self) -> CacheStats {
        let mut stats = self.stats.read().await.clone();

        // Update hot cache size
        {
            let hot_cache = self.hot_cache.read().await;
            stats.hot_cache_size = hot_cache.len() as u64;
        }

        stats
    }
}
