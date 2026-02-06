//! # ABI Decoder Actor
//!
//! WasmCloud actor that decodes EVM transaction ABIs using the Alloy library.
//! This actor receives transactions via NATS and responds with decoded function information.
//!
//! ## Message Subjects
//! - `contract-transactions.{network}.{subnet}.*.raw` - Contract transactions from pipeline
//! - `abi.decode.request` - Direct ABI decode requests
//! - `abi.decode.batch` - Batch decode requests
//!
//! ## Output Subjects
//! - `blockchain.{network}.{subnet}.contracts.decoded` - Successfully decoded contract transactions
//! - `abi.decode.result` - Single decode results
//! - `abi.decode.batch.result` - Batch decode results
//!
//! NOTE: HTTP capability temporarily disabled due to WASI 0.2.3 incompatibility.
//! ABIs must be pre-populated in Redis cache using key format: abi:{network}:{contract_address}

// mod abi_fetcher; // Disabled - HTTP capability causes WASI 0.2.3 dependency

use serde::{Deserialize, Serialize};

// Generate WIT bindings for the abi-decoder world
wit_bindgen::generate!({ generate_all });

/// ABI entry (function, event, constructor, etc.) for parsing JSON ABI
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AbiEntry {
    /// Entry type: "function", "event", "constructor", etc.
    #[serde(rename = "type", default)]
    pub entry_type: String,
    /// Function/event name
    #[serde(default)]
    pub name: String,
    /// Input parameters
    #[serde(default)]
    pub inputs: Vec<AbiParam>,
    /// Output parameters
    #[serde(default)]
    pub outputs: Vec<AbiParam>,
    /// State mutability
    #[serde(rename = "stateMutability", default)]
    pub state_mutability: Option<String>,
}

/// ABI parameter for parsing JSON ABI
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AbiParam {
    /// Parameter name
    #[serde(default)]
    pub name: String,
    /// Parameter type (e.g., "address", "uint256", "bytes")
    #[serde(rename = "type")]
    pub param_type: String,
    /// Whether the parameter is indexed (for events)
    #[serde(default)]
    pub indexed: bool,
    /// Components for tuple types
    #[serde(default)]
    pub components: Option<Vec<AbiParam>>,
}

/// Decoded ABI value
#[derive(Debug, Clone)]
pub enum AbiValue {
    Address([u8; 20]),
    Uint256([u8; 32]),
    Int256([u8; 32]),
    Bool(bool),
    Bytes(Vec<u8>),
    FixedBytes(Vec<u8>),
    String(String),
    Array(Vec<AbiValue>),
    Tuple(Vec<AbiValue>),
}

use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use subject_registry::blockchain;
use wasmcloud::messaging::{consumer, types};

/// Contract transaction from the pipeline (from eth_process_transactions or eth_raw_transactions)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContractTransaction {
    /// Network (e.g., "ethereum", "polygon")
    pub network: String,
    /// Subnet (e.g., "mainnet", "sepolia")
    pub subnet: String,
    /// VM type (e.g., "evm")
    pub vm_type: String,
    /// Transaction hash
    pub transaction_hash: String,
    /// Block number
    pub block_number: u64,
    /// Transaction index in block
    pub transaction_index: u32,
    /// Sender address
    pub from_address: String,
    /// Contract address (recipient)
    pub to_address: String,
    /// Value transferred (wei as hex string)
    pub value: String,
    /// Gas limit
    pub gas_limit: u64,
    /// Gas price (wei as hex string)
    pub gas_price: String,
    /// Input data (function call data)
    pub input_data: String,
    /// Nonce
    pub nonce: u64,
    /// Max fee per gas (EIP-1559)
    pub max_fee_per_gas: Option<String>,
    /// Max priority fee per gas (EIP-1559)
    pub max_priority_fee_per_gas: Option<String>,
    /// Transaction type
    pub transaction_type: Option<u8>,
    /// Processing timestamp
    pub processed_at: String,
    /// Processor ID
    pub processor_id: String,
}

/// Raw contract transaction payload from eth_process_transactions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawContractTransaction {
    pub hash: String,
    pub from: String,
    pub to: String,
    pub value: String,
    pub gas: String,
    pub gas_price: String,
    pub input: String,
    pub nonce: String,
    pub block_number: String,
    pub transaction_index: String,
    pub chain_id: String,
}

/// ABI decode request (for direct requests)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodeRequest {
    /// Contract address
    pub to_address: String,
    /// Transaction input data (hex)
    pub input_data: String,
    /// Network (e.g., "ethereum", "polygon")
    pub network: String,
    /// Subnet (e.g., "mainnet", "goerli")
    pub subnet: String,
    /// Transaction hash for context
    pub transaction_hash: String,
    /// Request ID for tracking
    pub request_id: String,
}

impl DecodeRequest {
    /// Check if this is a native transfer
    pub fn is_native_transfer(&self) -> bool {
        self.input_data.is_empty() || self.input_data == "0x"
    }

    /// Check if this is a contract creation
    pub fn is_contract_creation(&self) -> bool {
        self.to_address.is_empty() || self.to_address == "0x"
    }

    /// Get function selector from input data
    pub fn get_function_selector(&self) -> Option<String> {
        if self.input_data.len() >= 10 && self.input_data.starts_with("0x") {
            Some(self.input_data[0..10].to_string())
        } else {
            None
        }
    }
}

/// Decoded transaction output (for pipeline)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedTransaction {
    /// Original transaction data
    pub transaction_hash: String,
    pub block_number: u64,
    pub from_address: String,
    pub to_address: String,
    pub network: String,
    pub subnet: String,
    pub value: String,
    /// Decode status
    pub decoding_status: String,
    /// Decoded function (if successful)
    pub decoded_function: Option<DecodedFunction>,
    /// Raw input data (always included for reference)
    pub input_data: String,
    /// ABI source
    pub abi_source: Option<String>,
    /// Processing timestamp
    pub processed_at: String,
    /// Processor ID
    pub processor_id: String,
}

/// ABI decode result (for direct requests)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodeResult {
    /// Original request
    pub request: DecodeRequest,
    /// Decode status
    pub status: DecodeStatus,
    /// Decoded function (if successful)
    pub decoded_function: Option<DecodedFunction>,
    /// Processing time in milliseconds
    pub processing_time_ms: u64,
    /// Processed timestamp
    pub processed_at: String,
    /// Processor ID
    pub processor_id: String,
}

/// Decode status
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "details")]
pub enum DecodeStatus {
    Success,
    NativeTransfer,
    ContractCreation,
    AbiNotFound { message: String },
    AbiAutoFetched { source: String },
    DecodingFailed { error: String },
    InvalidInput { error: String },
    RateLimited { message: String },
}

/// Decoded function information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedFunction {
    /// Function name
    pub name: String,
    /// Function selector
    pub selector: String,
    /// Function signature
    pub signature: String,
    /// Decoded parameters
    pub parameters: Vec<DecodedParameter>,
    /// ABI source
    pub abi_source: String,
}

/// Decoded parameter
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedParameter {
    /// Parameter name
    pub name: String,
    /// Parameter type
    pub param_type: String,
    /// Parameter value (as string)
    pub value: String,
    /// Whether parameter is indexed (for events)
    pub indexed: bool,
}

/// Batch decode request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchDecodeRequest {
    /// Multiple decode requests
    pub requests: Vec<DecodeRequest>,
    /// Batch ID for tracking
    pub batch_id: String,
    /// Priority level
    pub priority: String,
    /// Submitted timestamp
    pub submitted_at: String,
}

/// Batch decode result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchDecodeResult {
    /// Batch ID
    pub batch_id: String,
    /// Individual results
    pub results: Vec<DecodeResult>,
    /// Processing summary
    pub summary: BatchSummary,
    /// Processed timestamp
    pub processed_at: String,
}

/// Batch processing summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchSummary {
    /// Total requests
    pub total_requests: u32,
    /// Successful decodes
    pub successful_decodes: u32,
    /// Failed decodes
    pub failed_decodes: u32,
    /// Native transfers
    pub native_transfers: u32,
    /// Total processing time in milliseconds
    pub total_processing_time_ms: u64,
}

/// ABI information stored in cache
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AbiInfo {
    /// Contract address
    pub address: String,
    /// Network identifier
    pub network: String,
    /// ABI JSON string
    pub abi_json: String,
    /// Source of ABI (e.g., "etherscan", "sourcify")
    pub source: String,
    /// Verified status
    pub verified: bool,
    /// Cached timestamp
    pub cached_at: String,
}

/// Main ABI Decoder Actor Component
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    /// Handle incoming NATS messages
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        let subject = &msg.subject;
        eprintln!("[ABI-DECODER] Received message on subject: {}", subject);

        // Handle pipeline contract transactions
        if subject.starts_with("contract-transactions.") {
            return Self::handle_contract_transaction(&msg);
        }

        // Handle direct decode requests
        match subject.as_str() {
            "abi.decode.request" => {
                let request: DecodeRequest = serde_json::from_slice(&msg.body)
                    .map_err(|e| format!("Failed to parse decode request: {}", e))?;

                let result = Self::decode_transaction(request)?;
                Self::publish_result(result)?;
            }
            "abi.decode.batch" => {
                let batch_request: BatchDecodeRequest = serde_json::from_slice(&msg.body)
                    .map_err(|e| format!("Failed to parse batch request: {}", e))?;

                let result = Self::decode_batch(batch_request)?;
                Self::publish_batch_result(result)?;
            }
            _ => {
                // Unknown subject, ignore
                eprintln!("[ABI-DECODER] Ignoring unknown subject: {}", subject);
            }
        }

        Ok(())
    }
}

impl Component {
    /// Handle a contract transaction from the pipeline
    fn handle_contract_transaction(msg: &types::BrokerMessage) -> Result<(), String> {
        eprintln!("[ABI-DECODER] Processing contract transaction");

        let tx = match serde_json::from_slice::<ContractTransaction>(&msg.body) {
            Ok(tx) => tx,
            Err(_) => {
                let raw_tx: RawContractTransaction = serde_json::from_slice(&msg.body)
                    .map_err(|e| format!("Failed to parse raw contract transaction: {}", e))?;
                let (network, subnet, vm_type) = Self::parse_contract_subject(&msg.subject)?;
                Self::contract_tx_from_raw(raw_tx, network, subnet, vm_type)
            }
        };

        let processed_at = Self::resolve_processed_at(&tx);

        eprintln!(
            "[ABI-DECODER] Transaction {} to contract {}",
            tx.transaction_hash, tx.to_address
        );

        // Create decode request from transaction
        let request = DecodeRequest {
            to_address: tx.to_address.clone(),
            input_data: tx.input_data.clone(),
            network: tx.network.clone(),
            subnet: tx.subnet.clone(),
            transaction_hash: tx.transaction_hash.clone(),
            request_id: format!("pipeline-{}", tx.transaction_hash),
        };

        // Get function selector
        let selector = match request.get_function_selector() {
            Some(sel) => sel,
            None => {
                // No valid input data, publish as-is
                let decoded_tx = DecodedTransaction {
                    transaction_hash: tx.transaction_hash,
                    block_number: tx.block_number,
                    from_address: tx.from_address,
                    to_address: tx.to_address,
                    network: tx.network.clone(),
                    subnet: tx.subnet.clone(),
                    value: tx.value,
                    decoding_status: "InvalidInput".to_string(),
                    decoded_function: None,
                    input_data: tx.input_data,
                    abi_source: None,
                    processed_at: processed_at.clone(),
                    processor_id: "abi-decoder-actor".to_string(),
                };
                Self::publish_decoded_transaction(&decoded_tx)?;
                return Ok(());
            }
        };

        // Try to get ABI from cache
        let abi_info = match Self::get_abi_from_cache(&tx.to_address, &tx.network) {
            Some(abi) => {
                eprintln!("[ABI-DECODER] Found ABI in cache from {}", abi.source);
                abi
            }
            None => {
                // Try to auto-fetch ABI
                eprintln!("[ABI-DECODER] ABI not in cache, attempting to fetch...");
                match Self::fetch_and_cache_abi(&tx.to_address, &tx.network, &tx.subnet) {
                    Ok(abi) => {
                        eprintln!(
                            "[ABI-DECODER] Successfully fetched and cached ABI from {}",
                            abi.source
                        );
                        abi
                    }
                    Err(e) => {
                        eprintln!("[ABI-DECODER] Failed to fetch ABI: {}", e);
                        // Publish transaction without decoding
                        let decoded_tx = DecodedTransaction {
                            transaction_hash: tx.transaction_hash,
                            block_number: tx.block_number,
                            from_address: tx.from_address,
                            to_address: tx.to_address,
                            network: tx.network.clone(),
                            subnet: tx.subnet.clone(),
                            value: tx.value,
                            decoding_status: "AbiNotFound".to_string(),
                            decoded_function: None,
                            input_data: tx.input_data,
                            abi_source: None,
                            processed_at: processed_at.clone(),
                            processor_id: "abi-decoder-actor".to_string(),
                        };
                        Self::publish_decoded_transaction(&decoded_tx)?;
                        return Ok(());
                    }
                }
            }
        };

        // Decode the transaction
        let decoded_tx = match Self::decode_with_alloy(&abi_info, &selector, &tx.input_data) {
            Ok(decoded_function) => {
                eprintln!(
                    "[ABI-DECODER] Successfully decoded function: {}",
                    decoded_function.name
                );
                DecodedTransaction {
                    transaction_hash: tx.transaction_hash,
                    block_number: tx.block_number,
                    from_address: tx.from_address,
                    to_address: tx.to_address,
                    network: tx.network.clone(),
                    subnet: tx.subnet.clone(),
                    value: tx.value,
                    decoding_status: "Success".to_string(),
                    decoded_function: Some(decoded_function),
                    input_data: tx.input_data,
                    abi_source: Some(abi_info.source),
                    processed_at: processed_at.clone(),
                    processor_id: "abi-decoder-actor".to_string(),
                }
            }
            Err(e) => {
                eprintln!("[ABI-DECODER] Decoding failed: {}", e);
                DecodedTransaction {
                    transaction_hash: tx.transaction_hash,
                    block_number: tx.block_number,
                    from_address: tx.from_address,
                    to_address: tx.to_address,
                    network: tx.network.clone(),
                    subnet: tx.subnet.clone(),
                    value: tx.value,
                    decoding_status: format!("DecodingFailed: {}", e),
                    decoded_function: None,
                    input_data: tx.input_data,
                    abi_source: Some(abi_info.source),
                    processed_at: processed_at.clone(),
                    processor_id: "abi-decoder-actor".to_string(),
                }
            }
        };

        // Publish to blockchain.{network}.{subnet}.contracts.decoded subject
        Self::publish_decoded_transaction(&decoded_tx)?;

        Ok(())
    }

    fn parse_contract_subject(subject: &str) -> Result<(String, String, String), String> {
        let parts: Vec<&str> = subject.split('.').collect();
        if parts.len() >= 5 && parts[0] == "contract-transactions" {
            return Ok((
                parts[1].to_string(),
                parts[2].to_string(),
                parts[3].to_string(),
            ));
        }
        Err(format!(
            "Invalid contract-transactions subject: {}",
            subject
        ))
    }

    fn contract_tx_from_raw(
        raw_tx: RawContractTransaction,
        network: String,
        subnet: String,
        vm_type: String,
    ) -> ContractTransaction {
        ContractTransaction {
            network,
            subnet,
            vm_type,
            transaction_hash: raw_tx.hash,
            block_number: Self::parse_hex_u64(&raw_tx.block_number),
            transaction_index: Self::parse_hex_u64(&raw_tx.transaction_index) as u32,
            from_address: raw_tx.from,
            to_address: raw_tx.to,
            value: raw_tx.value,
            gas_limit: Self::parse_hex_u64(&raw_tx.gas),
            gas_price: raw_tx.gas_price,
            input_data: raw_tx.input,
            nonce: Self::parse_hex_u64(&raw_tx.nonce),
            max_fee_per_gas: None,
            max_priority_fee_per_gas: None,
            transaction_type: None,
            processed_at: Self::get_timestamp(),
            processor_id: "abi-decoder-actor".to_string(),
        }
    }

    fn parse_hex_u64(hex_str: &str) -> u64 {
        let cleaned = hex_str.trim_start_matches("0x");
        u64::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Fetch ABI from external sources and cache it
    /// NOTE: HTTP capability disabled - ABIs must be pre-populated in Redis
    fn fetch_and_cache_abi(
        contract_address: &str,
        network: &str,
        _subnet: &str,
    ) -> Result<AbiInfo, String> {
        // HTTP capability is disabled due to WASI 0.2.3 incompatibility
        // ABIs must be pre-populated in Redis using key format: abi:{network}:{contract_address}
        eprintln!(
            "[ABI-DECODER] HTTP fetch disabled. ABI for {} on {} must be pre-populated in Redis",
            contract_address, network
        );
        Err(format!(
            "ABI auto-fetch disabled. Pre-populate ABI in Redis with key: abi:{}:{}",
            network,
            contract_address.to_lowercase()
        ))
    }

    /// Decode a single transaction (for direct requests)
    fn decode_transaction(request: DecodeRequest) -> Result<DecodeResult, String> {
        let start_time = std::time::Instant::now();
        let processed_at = Self::get_timestamp();

        // Quick checks for special cases
        if request.is_native_transfer() {
            let processing_time = start_time.elapsed().as_millis() as u64;
            return Ok(DecodeResult {
                request,
                status: DecodeStatus::NativeTransfer,
                decoded_function: None,
                processing_time_ms: processing_time,
                processed_at: processed_at.clone(),
                processor_id: "abi-decoder-actor".to_string(),
            });
        }

        if request.is_contract_creation() {
            let processing_time = start_time.elapsed().as_millis() as u64;
            return Ok(DecodeResult {
                request,
                status: DecodeStatus::ContractCreation,
                decoded_function: None,
                processing_time_ms: processing_time,
                processed_at: processed_at.clone(),
                processor_id: "abi-decoder-actor".to_string(),
            });
        }

        // Get function selector
        let selector = match request.get_function_selector() {
            Some(sel) => sel,
            None => {
                let processing_time = start_time.elapsed().as_millis() as u64;
                return Ok(DecodeResult {
                    request,
                    status: DecodeStatus::InvalidInput {
                        error: "Invalid input data format".to_string(),
                    },
                    decoded_function: None,
                    processing_time_ms: processing_time,
                    processed_at: processed_at.clone(),
                    processor_id: "abi-decoder-actor".to_string(),
                });
            }
        };

        // Try to get ABI from cache, then fetch if not found
        let (abi_info, auto_fetched) =
            match Self::get_abi_from_cache(&request.to_address, &request.network) {
                Some(abi) => (abi, false),
                None => {
                    // Try to auto-fetch
                    match Self::fetch_and_cache_abi(
                        &request.to_address,
                        &request.network,
                        &request.subnet,
                    ) {
                        Ok(abi) => (abi, true),
                        Err(e) => {
                            let processing_time = start_time.elapsed().as_millis() as u64;
                            return Ok(DecodeResult {
                                request,
                                status: DecodeStatus::AbiNotFound { message: e },
                                decoded_function: None,
                                processing_time_ms: processing_time,
                                processed_at: processed_at.clone(),
                                processor_id: "abi-decoder-actor".to_string(),
                            });
                        }
                    }
                }
            };

        // Decode the transaction using Alloy
        match Self::decode_with_alloy(&abi_info, &selector, &request.input_data) {
            Ok(decoded_function) => {
                let processing_time = start_time.elapsed().as_millis() as u64;
                let status = if auto_fetched {
                    DecodeStatus::AbiAutoFetched {
                        source: abi_info.source.clone(),
                    }
                } else {
                    DecodeStatus::Success
                };
                Ok(DecodeResult {
                    request,
                    status,
                    decoded_function: Some(decoded_function),
                    processing_time_ms: processing_time,
                    processed_at: processed_at.clone(),
                    processor_id: "abi-decoder-actor".to_string(),
                })
            }
            Err(e) => {
                let processing_time = start_time.elapsed().as_millis() as u64;
                Ok(DecodeResult {
                    request,
                    status: DecodeStatus::DecodingFailed {
                        error: e.to_string(),
                    },
                    decoded_function: None,
                    processing_time_ms: processing_time,
                    processed_at: processed_at.clone(),
                    processor_id: "abi-decoder-actor".to_string(),
                })
            }
        }
    }

    /// Decode multiple transactions in batch
    fn decode_batch(batch_request: BatchDecodeRequest) -> Result<BatchDecodeResult, String> {
        let start_time = std::time::Instant::now();
        let mut results = Vec::new();
        let mut successful = 0;
        let mut failed = 0;
        let mut native_transfers = 0;

        for request in batch_request.requests {
            let result = Self::decode_transaction(request)?;

            match &result.status {
                DecodeStatus::Success | DecodeStatus::AbiAutoFetched { .. } => successful += 1,
                DecodeStatus::NativeTransfer => native_transfers += 1,
                DecodeStatus::ContractCreation => native_transfers += 1,
                _ => failed += 1,
            }

            results.push(result);
        }

        let total_processing_time = start_time.elapsed().as_millis() as u64;
        let processed_at = Self::get_timestamp();

        let total_requests = results.len() as u32;
        Ok(BatchDecodeResult {
            batch_id: batch_request.batch_id,
            results,
            summary: BatchSummary {
                total_requests,
                successful_decodes: successful,
                failed_decodes: failed,
                native_transfers,
                total_processing_time_ms: total_processing_time,
            },
            processed_at,
        })
    }

    /// Get ABI from cache (Redis)
    fn get_abi_from_cache(contract_address: &str, network: &str) -> Option<AbiInfo> {
        let cache_key = format!("abi:{}:{}", network, contract_address.to_lowercase());

        match Self::get_from_redis(&cache_key) {
            Some(abi_json) => match serde_json::from_str::<AbiInfo>(&abi_json) {
                Ok(abi_info) => Some(abi_info),
                Err(_) => None,
            },
            None => None,
        }
    }

    /// Get value from Redis
    fn get_from_redis(key: &str) -> Option<String> {
        match wasi::keyvalue::store::open("default") {
            Ok(bucket) => match bucket.get(key) {
                Ok(Some(bytes)) => String::from_utf8(bytes).ok(),
                _ => None,
            },
            Err(_) => None,
        }
    }

    /// Set value in Redis
    fn set_in_redis(key: &str, value: &str) -> Result<(), String> {
        let bucket = wasi::keyvalue::store::open("default")
            .map_err(|e| format!("Failed to open keyvalue bucket: {:?}", e))?;

        bucket
            .set(key, value.as_bytes())
            .map_err(|e| format!("Failed to set key: {:?}", e))?;

        Ok(())
    }

    /// Cache an ABI in Redis
    fn cache_abi(abi_info: &AbiInfo) -> Result<(), String> {
        let cache_key = format!(
            "abi:{}:{}",
            abi_info.network,
            abi_info.address.to_lowercase()
        );

        let abi_json = serde_json::to_string(abi_info)
            .map_err(|e| format!("Failed to serialize ABI info: {}", e))?;

        Self::set_in_redis(&cache_key, &abi_json)
    }

    /// Decode transaction using custom minimal ABI decoder (WASM-compatible)
    fn decode_with_alloy(
        abi_info: &AbiInfo,
        selector: &str,
        input_data: &str,
    ) -> Result<DecodedFunction, Box<dyn std::error::Error>> {
        // Parse the ABI JSON to find the function
        let abi: Vec<AbiEntry> = serde_json::from_str(&abi_info.abi_json)?;

        // Convert selector to bytes
        let selector_bytes = hex::decode(&selector[2..])?;
        let selector_array: [u8; 4] = selector_bytes
            .try_into()
            .map_err(|_| "Invalid selector length")?;

        // Find function by selector
        let function = abi
            .iter()
            .filter(|e| e.entry_type == "function")
            .find(|f| {
                // Calculate selector from function signature
                let sig = Self::build_signature(&f.name, &f.inputs);
                let hash = Self::keccak256(sig.as_bytes());
                hash[..4] == selector_array
            })
            .ok_or("Function not found in ABI")?;

        // Extract and decode parameters (skip the 4-byte selector)
        let input_bytes = hex::decode(&input_data[10..])?;
        let decoded_params = Self::decode_abi_params(&function.inputs, &input_bytes)?;

        // Convert to our parameter format
        let mut parameters = Vec::new();
        for (i, param) in function.inputs.iter().enumerate() {
            if let Some(value) = decoded_params.get(i) {
                parameters.push(DecodedParameter {
                    name: param.name.clone(),
                    param_type: param.param_type.clone(),
                    value: Self::format_abi_value(value),
                    indexed: false,
                });
            }
        }

        let signature = Self::build_signature(&function.name, &function.inputs);

        Ok(DecodedFunction {
            name: function.name.clone(),
            selector: selector.to_string(),
            signature,
            parameters,
            abi_source: abi_info.source.clone(),
        })
    }

    /// Build function signature from name and inputs
    fn build_signature(name: &str, inputs: &[AbiParam]) -> String {
        let params: Vec<String> = inputs.iter().map(|p| p.param_type.clone()).collect();
        format!("{}({})", name, params.join(","))
    }

    /// Simple keccak256 implementation using tiny-keccak
    fn keccak256(data: &[u8]) -> [u8; 32] {
        use tiny_keccak::{Hasher, Keccak};
        let mut hasher = Keccak::v256();
        let mut output = [0u8; 32];
        hasher.update(data);
        hasher.finalize(&mut output);
        output
    }

    /// Decode ABI-encoded parameters
    fn decode_abi_params(params: &[AbiParam], data: &[u8]) -> Result<Vec<AbiValue>, String> {
        let mut results = Vec::new();
        let mut offset = 0;

        for param in params {
            let (value, consumed) = Self::decode_single_param(&param.param_type, data, offset)?;
            results.push(value);
            offset += consumed;
        }

        Ok(results)
    }

    /// Decode a single ABI parameter
    fn decode_single_param(
        type_str: &str,
        data: &[u8],
        offset: usize,
    ) -> Result<(AbiValue, usize), String> {
        // Handle basic types (all are 32 bytes padded)
        match type_str {
            "address" => {
                if offset + 32 > data.len() {
                    return Err("Not enough data for address".to_string());
                }
                let mut addr = [0u8; 20];
                addr.copy_from_slice(&data[offset + 12..offset + 32]);
                Ok((AbiValue::Address(addr), 32))
            }
            "bool" => {
                if offset + 32 > data.len() {
                    return Err("Not enough data for bool".to_string());
                }
                let val = data[offset + 31] != 0;
                Ok((AbiValue::Bool(val), 32))
            }
            "string" => {
                // Dynamic type - first 32 bytes is offset, then length + data
                if offset + 32 > data.len() {
                    return Err("Not enough data for string offset".to_string());
                }
                let data_offset = Self::read_u256_as_usize(&data[offset..offset + 32])?;
                if data_offset + 32 > data.len() {
                    return Err("Invalid string offset".to_string());
                }
                let str_len = Self::read_u256_as_usize(&data[data_offset..data_offset + 32])?;
                if data_offset + 32 + str_len > data.len() {
                    return Err("String data out of bounds".to_string());
                }
                let str_data = &data[data_offset + 32..data_offset + 32 + str_len];
                let s = String::from_utf8(str_data.to_vec()).map_err(|_| "Invalid UTF-8 string")?;
                Ok((AbiValue::String(s), 32))
            }
            "bytes" => {
                // Dynamic type
                if offset + 32 > data.len() {
                    return Err("Not enough data for bytes offset".to_string());
                }
                let data_offset = Self::read_u256_as_usize(&data[offset..offset + 32])?;
                if data_offset + 32 > data.len() {
                    return Err("Invalid bytes offset".to_string());
                }
                let bytes_len = Self::read_u256_as_usize(&data[data_offset..data_offset + 32])?;
                if data_offset + 32 + bytes_len > data.len() {
                    return Err("Bytes data out of bounds".to_string());
                }
                let bytes_data = data[data_offset + 32..data_offset + 32 + bytes_len].to_vec();
                Ok((AbiValue::Bytes(bytes_data), 32))
            }
            t if t.starts_with("uint") => {
                if offset + 32 > data.len() {
                    return Err("Not enough data for uint".to_string());
                }
                let mut val = [0u8; 32];
                val.copy_from_slice(&data[offset..offset + 32]);
                Ok((AbiValue::Uint256(val), 32))
            }
            t if t.starts_with("int") => {
                if offset + 32 > data.len() {
                    return Err("Not enough data for int".to_string());
                }
                let mut val = [0u8; 32];
                val.copy_from_slice(&data[offset..offset + 32]);
                Ok((AbiValue::Int256(val), 32))
            }
            t if t.starts_with("bytes") && t.len() > 5 => {
                // Fixed bytes (bytes1 to bytes32)
                let size: usize = t[5..].parse().map_err(|_| "Invalid bytes size")?;
                if offset + 32 > data.len() {
                    return Err("Not enough data for fixed bytes".to_string());
                }
                let val = data[offset..offset + size].to_vec();
                Ok((AbiValue::FixedBytes(val), 32))
            }
            _ => Err(format!("Unsupported type: {}", type_str)),
        }
    }

    /// Read u256 as usize (for offsets and lengths)
    fn read_u256_as_usize(data: &[u8]) -> Result<usize, String> {
        if data.len() < 32 {
            return Err("Not enough data for u256".to_string());
        }
        // Only read last 8 bytes as usize (enough for any practical offset)
        let mut bytes = [0u8; 8];
        bytes.copy_from_slice(&data[24..32]);
        Ok(u64::from_be_bytes(bytes) as usize)
    }

    /// Format ABI value for display
    fn format_abi_value(value: &AbiValue) -> String {
        match value {
            AbiValue::Address(addr) => format!("0x{}", hex::encode(addr)),
            AbiValue::Uint256(val) => {
                // Convert to decimal string
                Self::u256_to_decimal(val)
            }
            AbiValue::Int256(val) => {
                // Convert to decimal string (handle sign)
                Self::i256_to_decimal(val)
            }
            AbiValue::Bool(val) => val.to_string(),
            AbiValue::Bytes(bytes) => format!("0x{}", hex::encode(bytes)),
            AbiValue::FixedBytes(bytes) => format!("0x{}", hex::encode(bytes)),
            AbiValue::String(s) => s.clone(),
            AbiValue::Array(arr) => {
                let formatted: Vec<String> = arr.iter().map(Self::format_abi_value).collect();
                format!("[{}]", formatted.join(", "))
            }
            AbiValue::Tuple(tuple) => {
                let formatted: Vec<String> = tuple.iter().map(Self::format_abi_value).collect();
                format!("({})", formatted.join(", "))
            }
        }
    }

    /// Convert u256 bytes to decimal string
    fn u256_to_decimal(bytes: &[u8; 32]) -> String {
        // Simple implementation: convert to hex first, then parse
        // For large numbers, we'll just return hex format
        let hex_str = hex::encode(bytes);

        // Check if it's small enough to fit in u128
        let leading_zeros: usize = bytes.iter().take_while(|&&b| b == 0).count();
        if leading_zeros >= 16 {
            // Fits in u128
            let mut val_bytes = [0u8; 16];
            val_bytes.copy_from_slice(&bytes[16..32]);
            let val = u128::from_be_bytes(val_bytes);
            val.to_string()
        } else {
            // Too large, return as hex with 0x prefix
            format!("0x{}", hex_str.trim_start_matches('0'))
        }
    }

    /// Convert i256 bytes to decimal string
    fn i256_to_decimal(bytes: &[u8; 32]) -> String {
        // Check sign bit
        let is_negative = bytes[0] & 0x80 != 0;

        if is_negative {
            // For negative numbers, just show hex
            format!("-0x{}", hex::encode(bytes))
        } else {
            Self::u256_to_decimal(bytes)
        }
    }

    fn resolve_processed_at(tx: &ContractTransaction) -> String {
        if tx.processed_at.is_empty() {
            Self::get_timestamp()
        } else {
            tx.processed_at.clone()
        }
    }

    /// Get current timestamp as ISO 8601 string
    fn get_timestamp() -> String {
        #[cfg(target_arch = "wasm32")]
        {
            let now = wasi::clocks::wall_clock::now();
            rfc3339_from_unix_secs(now.seconds)
        }

        #[cfg(not(target_arch = "wasm32"))]
        {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default();
            rfc3339_from_unix_secs(now.as_secs())
        }
    }

    /// Publish decoded transaction to pipeline
    fn publish_decoded_transaction(decoded_tx: &DecodedTransaction) -> Result<(), String> {
        let subject = blockchain::contracts_decoded(&decoded_tx.network, &decoded_tx.subnet);
        let payload = serde_json::to_vec(decoded_tx)
            .map_err(|e| format!("Failed to serialize decoded transaction: {}", e))?;

        eprintln!("[ABI-DECODER] Publishing to {}", subject);

        consumer::publish(&types::BrokerMessage {
            subject,
            body: payload,
            reply_to: None,
        })?;

        Ok(())
    }

    /// Publish decode result to NATS
    fn publish_result(result: DecodeResult) -> Result<(), String> {
        let payload = serde_json::to_vec(&result)
            .map_err(|e| format!("Failed to serialize result: {}", e))?;

        consumer::publish(&types::BrokerMessage {
            subject: "abi.decode.result".to_string(),
            body: payload,
            reply_to: None,
        })?;

        Ok(())
    }

    /// Publish batch decode result to NATS
    fn publish_batch_result(result: BatchDecodeResult) -> Result<(), String> {
        let payload = serde_json::to_vec(&result)
            .map_err(|e| format!("Failed to serialize batch result: {}", e))?;

        consumer::publish(&types::BrokerMessage {
            subject: "abi.decode.batch.result".to_string(),
            body: payload,
            reply_to: None,
        })?;

        Ok(())
    }
}

fn rfc3339_from_unix_secs(total_seconds: u64) -> String {
    let days_since_epoch = total_seconds / 86400;
    let time_of_day = total_seconds % 86400;

    let hours = time_of_day / 3600;
    let minutes = (time_of_day % 3600) / 60;
    let seconds = time_of_day % 60;

    let (year, month, day) = days_to_ymd(days_since_epoch as i64);

    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        year, month, day, hours, minutes, seconds
    )
}

fn days_to_ymd(days: i64) -> (i32, u32, u32) {
    let mut remaining_days = days;
    let mut year = 1970i32;

    loop {
        let days_in_year = if is_leap_year(year) { 366 } else { 365 };
        if remaining_days < days_in_year {
            break;
        }
        remaining_days -= days_in_year;
        year += 1;
    }

    let mut month = 1u32;
    let mut day_of_year = remaining_days as u32;

    for days_in_month in [31u32, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31].iter() {
        let dim = if month == 2 && is_leap_year(year) {
            29
        } else {
            *days_in_month
        };
        if day_of_year < dim {
            break;
        }
        day_of_year -= dim;
        month += 1;
    }

    let day = day_of_year + 1;
    (year, month, day)
}

fn is_leap_year(year: i32) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_contract_subject() {
        let (network, subnet, vm_type) =
            Component::parse_contract_subject("contract-transactions.ethereum.mainnet.evm.raw")
                .expect("valid subject");
        assert_eq!(network, "ethereum");
        assert_eq!(subnet, "mainnet");
        assert_eq!(vm_type, "evm");

        assert!(
            Component::parse_contract_subject("contract-transactions.ethereum.mainnet").is_err()
        );
    }

    #[test]
    fn test_contract_tx_from_raw() {
        let raw = RawContractTransaction {
            hash: "0xabc".to_string(),
            from: "0xfrom".to_string(),
            to: "0xto".to_string(),
            value: "0x0".to_string(),
            gas: "0x5208".to_string(),
            gas_price: "0x4a817c800".to_string(),
            input: "0xa9059cbb".to_string(),
            nonce: "0x1".to_string(),
            block_number: "0x11a4bc0".to_string(),
            transaction_index: "0x2".to_string(),
            chain_id: "0x1".to_string(),
        };

        let tx = Component::contract_tx_from_raw(
            raw,
            "ethereum".to_string(),
            "mainnet".to_string(),
            "evm".to_string(),
        );
        assert_eq!(tx.network, "ethereum");
        assert_eq!(tx.subnet, "mainnet");
        assert_eq!(tx.vm_type, "evm");
        assert_eq!(tx.transaction_hash, "0xabc");
        assert_eq!(tx.block_number, 0x11a4bc0);
        assert_eq!(tx.transaction_index, 2);
        assert_eq!(tx.gas_limit, 0x5208);
    }

    #[test]
    fn test_resolve_processed_at_prefers_input() {
        let tx = ContractTransaction {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: "0xabc".to_string(),
            block_number: 1,
            transaction_index: 0,
            from_address: "0xfrom".to_string(),
            to_address: "0xto".to_string(),
            value: "0x0".to_string(),
            gas_limit: 21_000,
            gas_price: "0x1".to_string(),
            input_data: "0x".to_string(),
            nonce: 0,
            max_fee_per_gas: None,
            max_priority_fee_per_gas: None,
            transaction_type: None,
            processed_at: "2026-01-01T00:00:00Z".to_string(),
            processor_id: "test".to_string(),
        };

        let resolved = Component::resolve_processed_at(&tx);
        assert_eq!(resolved, "2026-01-01T00:00:00Z");
    }

    #[test]
    fn test_rfc3339_from_unix_secs_epoch() {
        let ts = rfc3339_from_unix_secs(0);
        assert_eq!(ts, "1970-01-01T00:00:00Z");
    }
}
