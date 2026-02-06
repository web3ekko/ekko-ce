//! Type definitions for ABI decoder provider

use alloy_json_abi::{Function, JsonAbi};
use alloy_primitives::{hex, Address, Bytes, FixedBytes};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Transaction input for decoding
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionInput {
    /// Contract address being called
    pub to_address: String,
    /// Transaction input data (hex)
    pub input_data: String,
    /// Network (e.g., "ethereum", "polygon")
    pub network: String,
    /// Subnet (e.g., "mainnet", "goerli")
    pub subnet: String,
    /// Transaction hash for context
    pub transaction_hash: String,
}

impl TransactionInput {
    /// Check if this is a native ETH transfer
    pub fn is_native_transfer(&self) -> bool {
        self.input_data.is_empty() || self.input_data == "0x"
    }

    /// Check if this is a contract creation
    pub fn is_contract_creation(&self) -> bool {
        self.to_address.is_empty() || self.to_address == "0x"
    }

    /// Get function selector from input data
    pub fn get_function_selector(&self) -> Option<String> {
        if self.input_data.len() >= 10 {
            Some(self.input_data[0..10].to_string())
        } else {
            None
        }
    }

    /// Parse contract address as Alloy Address
    pub fn parse_address(&self) -> Result<Address, String> {
        self.to_address
            .parse()
            .map_err(|e| format!("Invalid contract address: {}", e))
    }

    /// Parse input data as Alloy Bytes
    pub fn parse_input_data(&self) -> Result<Bytes, String> {
        self.input_data
            .parse()
            .map_err(|e| format!("Invalid input data: {}", e))
    }
}

/// Decoded function parameter
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedParameter {
    /// Parameter name from ABI
    pub name: String,
    /// Parameter type (e.g., "uint256", "address")
    pub param_type: String,
    /// Decoded value as string
    pub value: String,
    /// Raw hex value
    pub raw_value: String,
}

/// Decoded function call
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedFunction {
    /// Function name
    pub name: String,
    /// Function signature (e.g., "transfer(address,uint256)")
    pub signature: String,
    /// Function selector (4 bytes hex)
    pub selector: String,
    /// Decoded parameters
    pub parameters: Vec<DecodedParameter>,
}

/// Decoding status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum DecodingStatus {
    /// Successfully decoded
    Success,
    /// Native ETH transfer (no decoding needed)
    NativeTransfer,
    /// Contract creation transaction
    ContractCreation,
    /// ABI not found for contract
    AbiNotFound,
    /// ABI found but decoding failed
    DecodingFailed,
    /// Invalid input data format
    InvalidInput,
}

/// Decoding result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodingResult {
    /// Original transaction input
    pub input: TransactionInput,
    /// Decoding status
    pub status: DecodingStatus,
    /// Decoded function (if successful)
    pub decoded_function: Option<DecodedFunction>,
    /// ABI source used
    pub abi_source: Option<String>,
    /// Error message (if failed)
    pub error_message: Option<String>,
    /// Processing time in milliseconds
    pub processing_time_ms: u64,
}

impl DecodingResult {
    /// Create a successful decoding result
    pub fn success(
        input: TransactionInput,
        decoded_function: DecodedFunction,
        abi_source: String,
        processing_time_ms: u64,
    ) -> Self {
        Self {
            input,
            status: DecodingStatus::Success,
            decoded_function: Some(decoded_function),
            abi_source: Some(abi_source),
            error_message: None,
            processing_time_ms,
        }
    }

    /// Create a native transfer result
    pub fn native_transfer(input: TransactionInput, processing_time_ms: u64) -> Self {
        Self {
            input,
            status: DecodingStatus::NativeTransfer,
            decoded_function: None,
            abi_source: None,
            error_message: None,
            processing_time_ms,
        }
    }

    /// Create a contract creation result
    pub fn contract_creation(input: TransactionInput, processing_time_ms: u64) -> Self {
        Self {
            input,
            status: DecodingStatus::ContractCreation,
            decoded_function: None,
            abi_source: None,
            error_message: None,
            processing_time_ms,
        }
    }

    /// Create an ABI not found result
    pub fn abi_not_found(input: TransactionInput, processing_time_ms: u64) -> Self {
        Self {
            input,
            status: DecodingStatus::AbiNotFound,
            decoded_function: None,
            abi_source: None,
            error_message: Some("ABI not found for contract".to_string()),
            processing_time_ms,
        }
    }

    /// Create a decoding failed result
    pub fn decoding_failed(
        input: TransactionInput,
        error: String,
        processing_time_ms: u64,
    ) -> Self {
        Self {
            input,
            status: DecodingStatus::DecodingFailed,
            decoded_function: None,
            abi_source: None,
            error_message: Some(error),
            processing_time_ms,
        }
    }
}

/// ABI information with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AbiInfo {
    /// Contract address
    pub contract_address: String,
    /// ABI JSON string
    pub abi_json: String,
    /// Source of ABI (e.g., "etherscan", "sourcify")
    pub source: String,
    /// When ABI was cached
    pub cached_at: DateTime<Utc>,
    /// Whether ABI is verified
    pub verified: bool,
    /// Parsed ABI (not serialized)
    #[serde(skip)]
    pub parsed_abi: Option<JsonAbi>,
}

impl AbiInfo {
    /// Create new ABI info
    pub fn new(contract_address: String, abi_json: String, source: String, verified: bool) -> Self {
        Self {
            contract_address,
            abi_json,
            source,
            cached_at: Utc::now(),
            verified,
            parsed_abi: None,
        }
    }

    /// Parse the ABI JSON
    pub fn parse_abi(&mut self) -> Result<(), String> {
        let abi: JsonAbi = serde_json::from_str(&self.abi_json)
            .map_err(|e| format!("Failed to parse ABI JSON: {}", e))?;
        self.parsed_abi = Some(abi);
        Ok(())
    }

    /// Get function by selector
    pub fn get_function_by_selector(&self, selector: &str) -> Option<&Function> {
        let abi = self.parsed_abi.as_ref()?;
        let selector_bytes = hex::decode(&selector[2..]).ok()?;
        if selector_bytes.len() != 4 {
            return None;
        }
        let selector_array: [u8; 4] = selector_bytes.try_into().ok()?;
        abi.functions()
            .find(|f| f.selector() == FixedBytes::from(selector_array))
    }
}

/// Cache statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheStats {
    /// Total ABIs in hot cache
    pub hot_cache_size: u64,
    /// Hot cache hit rate (0.0 to 1.0)
    pub hot_cache_hit_rate: f64,
    /// Redis cache hit rate (0.0 to 1.0)
    pub redis_cache_hit_rate: f64,
    /// Total decoding operations
    pub total_decodings: u64,
    /// Successful decodings
    pub successful_decodings: u64,
    /// Average decoding time (ms)
    pub avg_decoding_time_ms: f64,
}

impl Default for CacheStats {
    fn default() -> Self {
        Self {
            hot_cache_size: 0,
            hot_cache_hit_rate: 0.0,
            redis_cache_hit_rate: 0.0,
            total_decodings: 0,
            successful_decodings: 0,
            avg_decoding_time_ms: 0.0,
        }
    }
}

/// ABI decoder error types
#[derive(Debug, thiserror::Error)]
pub enum DecoderError {
    #[error("Contract not found: {0}")]
    ContractNotFound(String),

    #[error("ABI parse error: {0}")]
    AbiParseError(String),

    #[error("Input decode error: {0}")]
    InputDecodeError(String),

    #[error("Cache error: {0}")]
    CacheError(String),

    #[error("External API error: {0}")]
    ApiError(String),

    #[error("Configuration error: {0}")]
    ConfigError(String),
}
