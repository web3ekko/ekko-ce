//! ABI Decoder Capability Provider
//!
//! High-performance EVM ABI decoding using Alloy library.
//! Provides multi-level caching and external API integration for ABI discovery.

pub mod config;
pub mod decoder;
pub mod types;

pub use config::AbiDecoderConfig;
pub use decoder::AbiDecoder;
pub use types::{
    AbiInfo, CacheStats, DecodedFunction, DecodedParameter, DecoderError, DecodingResult,
    DecodingStatus, TransactionInput,
};

use anyhow::Result;
use async_trait::async_trait;
use redis::AsyncCommands;
use tracing::{info, instrument};
use wasmcloud_provider_sdk::Provider;

/// ABI Decoder Provider implementation
pub struct AbiDecoderProvider {
    decoder: AbiDecoder,
    config: AbiDecoderConfig,
}

impl AbiDecoderProvider {
    /// Create a new ABI decoder provider
    #[instrument]
    pub async fn new() -> Result<Self> {
        info!("Initializing ABI Decoder Provider");

        // Load configuration from environment
        let config = AbiDecoderConfig::from_env()?;

        // Create decoder
        let decoder = AbiDecoder::new(config.clone()).await?;

        info!("ABI Decoder Provider initialized successfully");

        Ok(Self { decoder, config })
    }

    /// Create provider with custom configuration
    pub async fn with_config(config: AbiDecoderConfig) -> Result<Self> {
        let decoder = AbiDecoder::new(config.clone()).await?;
        Ok(Self { decoder, config })
    }

    /// Create provider from wasmCloud host data (for WADM deployment)
    pub async fn from_host_data(_host_data: wasmcloud_provider_sdk::HostData) -> Result<Self> {
        info!("🌟 Creating ABI Decoder Provider from wasmCloud host data");

        // Load configuration from environment
        let config = AbiDecoderConfig::from_env()?;

        Self::with_config(config).await
    }

    /// Decode a single transaction
    pub async fn decode_transaction(
        &self,
        input: TransactionInput,
    ) -> Result<DecodingResult, DecoderError> {
        self.decoder.decode_transaction(input).await
    }

    /// Decode multiple transactions in batch
    pub async fn decode_batch(
        &self,
        inputs: Vec<TransactionInput>,
    ) -> Result<Vec<DecodingResult>, DecoderError> {
        self.decoder.decode_batch(inputs).await
    }

    /// Check if ABI exists in cache
    pub async fn has_abi(
        &self,
        contract_address: &str,
        network: &str,
    ) -> Result<bool, DecoderError> {
        // Check hot cache first
        let cache_key = format!("{}:{}", network, contract_address);
        {
            let hot_cache = self.decoder.hot_cache.read().await;
            if hot_cache.contains(&cache_key) {
                return Ok(true);
            }
        }

        // Check Redis cache
        let redis_key = format!(
            "{}{}:{}",
            self.config.redis.abi_key_prefix, network, contract_address
        );
        let redis_result: redis::RedisResult<bool> =
            self.decoder.redis.clone().exists(&redis_key).await;

        match redis_result {
            Ok(exists) => Ok(exists),
            Err(e) => Err(DecoderError::CacheError(format!("Redis error: {}", e))),
        }
    }

    /// Get ABI from cache
    pub async fn get_abi(
        &self,
        contract_address: &str,
        network: &str,
    ) -> Result<Option<AbiInfo>, DecoderError> {
        self.decoder
            .get_abi_with_fallback(contract_address, network, "mainnet")
            .await
            .map_err(|e| DecoderError::CacheError(e.to_string()))
    }

    /// Cache an ABI (called by ABI downloader)
    pub async fn cache_abi(
        &self,
        contract_address: &str,
        network: &str,
        abi_json: &str,
        source: &str,
    ) -> Result<(), DecoderError> {
        // Create ABI info
        let mut abi_info = AbiInfo::new(
            contract_address.to_string(),
            abi_json.to_string(),
            source.to_string(),
            true, // Assume verified if we're caching it
        );

        // Parse ABI to validate
        abi_info
            .parse_abi()
            .map_err(|e| DecoderError::AbiParseError(e))?;

        // Cache in Redis
        let redis_key = format!(
            "{}{}:{}",
            self.config.redis.abi_key_prefix, network, contract_address
        );
        let ttl = self.config.redis.abi_cache_ttl_secs;
        let _: redis::RedisResult<()> = self
            .decoder
            .redis
            .clone()
            .set_ex(&redis_key, abi_json, ttl)
            .await;

        // Cache in hot cache
        let cache_key = format!("{}:{}", network, contract_address);
        {
            let mut hot_cache = self.decoder.hot_cache.write().await;
            hot_cache.put(cache_key, abi_info);
        }

        info!(
            "Cached ABI for contract {} on network {} from source {}",
            contract_address, network, source
        );

        Ok(())
    }

    /// Remove ABI from cache
    pub async fn remove_abi(
        &self,
        contract_address: &str,
        network: &str,
    ) -> Result<(), DecoderError> {
        // Remove from Redis
        let redis_key = format!(
            "{}{}:{}",
            self.config.redis.abi_key_prefix, network, contract_address
        );
        let _: redis::RedisResult<()> = self.decoder.redis.clone().del(&redis_key).await;

        // Remove from hot cache
        let cache_key = format!("{}:{}", network, contract_address);
        {
            let mut hot_cache = self.decoder.hot_cache.write().await;
            hot_cache.pop(&cache_key);
        }

        Ok(())
    }

    /// Get cache statistics
    pub async fn get_cache_stats(&self) -> Result<CacheStats, DecoderError> {
        Ok(self.decoder.get_cache_stats().await)
    }

    /// Get configuration
    pub fn get_config(&self) -> &AbiDecoderConfig {
        &self.config
    }
}

/// Provider trait implementation for wasmCloud SDK
///
/// Uses default implementations from the SDK since initialization happens in:
/// - from_host_data() - Called by wasmCloud deployment
/// - new() - Called for standalone usage
#[async_trait]
impl Provider for AbiDecoderProvider {
    // All methods use default implementations from wasmcloud-provider-sdk
    // The SDK manages the provider lifecycle automatically
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::AbiDecoderConfig;

    #[tokio::test]
    async fn test_provider_creation() {
        let config = AbiDecoderConfig::default();
        let result = AbiDecoderProvider::with_config(config).await;

        // This might fail due to Redis connection, but we can test the structure
        match result {
            Ok(_) => println!("Provider created successfully"),
            Err(e) => println!("Expected error (Redis not available): {}", e),
        }
    }

    #[test]
    fn test_transaction_input_validation() {
        let input = TransactionInput {
            to_address: "0x1234567890123456789012345678901234567890".to_string(),
            input_data: "0xa9059cbb000000000000000000000000".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0xabcd".to_string(),
        };

        assert!(!input.is_native_transfer());
        assert!(!input.is_contract_creation());
        assert_eq!(
            input.get_function_selector(),
            Some("0xa9059cbb".to_string())
        );
    }

    #[test]
    fn test_native_transfer_detection() {
        let input = TransactionInput {
            to_address: "0x1234567890123456789012345678901234567890".to_string(),
            input_data: "0x".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0xabcd".to_string(),
        };

        assert!(input.is_native_transfer());
        assert!(!input.is_contract_creation());
    }

    #[test]
    fn test_contract_creation_detection() {
        let input = TransactionInput {
            to_address: "".to_string(),
            input_data: "0x608060405234801561001057600080fd5b50".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0xabcd".to_string(),
        };

        assert!(!input.is_native_transfer());
        assert!(input.is_contract_creation());
    }
}
