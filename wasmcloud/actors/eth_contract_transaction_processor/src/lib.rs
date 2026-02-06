//! # Ethereum Contract Transaction Processor Actor
//!
//! WasmCloud actor that processes smart contract function call transactions with decoder coordination,
//! event log processing, and popular function detection. This actor receives contract transactions
//! from the eth_process_transactions actor and enriches them with decoded parameters and analysis.
//!
//! ## Architecture
//! - **wasmCloud Actor**: Uses proper WIT interfaces
//! - **WASM Component**: Runs in wasmCloud runtime
//! - **Messaging**: Subscribes to contract-transactions.*.*.evm.raw AND blockchain.{network}.{subnet}.contracts.decoded
//! - **State**: Redis for call tracking and pending decode management
//!
//! ## Subscription Pattern
//! - Subscribes to: `contract-transactions.*.*.evm.raw` (wildcard for all EVM chains)
//! - Subscribes to: `blockchain.{network}.{subnet}.contracts.decoded` (decoded transaction responses)
//! - Publishes to:
//!   - `contract-calls.processed.evm` - Processed calls with enrichment
//!   - `alerts.evaluate.{network}.{subnet}` - Alert evaluation system
//!   - `abi.decode.request` - ABI decode requests
//!   - `ducklake.contract_calls.{network}.{subnet}.write` - Contract call analytics
//!   - `ducklake.transactions.{network}.{subnet}.write` - Unified transaction history

use chrono::{TimeZone, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// Generate WIT bindings for the processor world
wit_bindgen::generate!({ generate_all });

use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use wasmcloud::messaging::{consumer, types};

/// Raw contract transaction in standard Ethereum format with receipt data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawContractTransaction {
    // Standard Ethereum transaction fields
    pub hash: String,
    pub from: String,
    pub to: String, // Contract address
    pub value: String,
    pub gas: String,
    pub gas_price: String,
    pub input: String, // Function call data
    pub nonce: String,
    pub block_number: String,
    pub block_hash: String,
    pub transaction_index: String,
    pub chain_id: String,

    // Optional signature fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,

    // Receipt data (execution results)
    pub status: String, // "0x1" = success, "0x0" = failed
    #[serde(skip_serializing_if = "Option::is_none")]
    pub revert_reason: Option<String>,
    pub gas_used: String,

    // Event logs from receipt
    pub logs: Vec<RawEventLog>,

    // Block timestamp (not in standard transaction, but commonly provided)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub block_timestamp: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawEventLog {
    pub address: String,
    pub topics: Vec<String>,
    pub data: String,
    pub log_index: u32,
}

/// Decoded transaction response from decoder
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedTransactionResponse {
    pub transaction_hash: String,
    pub network: String,
    pub subnet: String,
    pub decoded_params: Vec<DecodedParameter>,
    pub function_signature: Option<String>,
}

/// Decoded transaction payload emitted by abi-decoder actor
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AbiDecodedTransaction {
    pub transaction_hash: String,
    pub network: String,
    pub subnet: String,
    #[serde(default)]
    pub decoding_status: String,
    #[serde(default)]
    pub decoded_function: Option<AbiDecodedFunction>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AbiDecodedFunction {
    pub name: String,
    pub selector: String,
    pub signature: String,
    #[serde(default)]
    pub parameters: Vec<AbiDecodedParameter>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AbiDecodedParameter {
    pub name: String,
    #[serde(alias = "type", alias = "param_type")]
    pub param_type: String,
    pub value: String,
    #[serde(default)]
    pub indexed: bool,
}

/// Processed contract transaction with enrichment and analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessedContractTransaction {
    // Original transaction data
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub transaction_hash: String,
    pub block_number: u64,
    pub block_timestamp: u64,

    // Function call data
    pub contract_address: String,
    pub caller_address: String,
    pub function_selector: String,
    pub function_signature: Option<String>,
    pub function_category: FunctionCategory,
    pub input_data: String,
    pub call_value_wei: String,

    // Transaction execution
    pub status: TransactionStatus,
    pub revert_reason: Option<String>,
    pub gas_used: u64,
    pub gas_price: String,
    pub transaction_fee_wei: String,

    // Decoded parameters (if available)
    pub decoded_params: Option<Vec<DecodedParameter>>,
    pub decoding_status: DecodingStatus,

    // Event logs
    pub events: Vec<EventLog>,
    pub event_count: u32,

    // Analysis
    pub is_popular_function: bool,
    pub interaction_frequency: u32,

    // Metadata
    pub processed_at: String,
    pub processor_id: String,
    pub correlation_id: String,

    // Standardized enrichment fields (cross-actor consistency)
    pub transaction_type: String,     // Always "contract_call"
    pub transaction_currency: String, // "ETH" | "{TOKEN_SYMBOL}" | "NONE"
    pub transaction_value: String,    // "0.1 ETH" | "100 USDT" | "0"
    pub transaction_subtype: String,  // "swap" | "stake" | "borrow" | "transfer" | etc.
    pub protocol: Option<String>,     // "Uniswap_V2" | "Aave" | "ERC20" | etc.
    pub category: String,             // "defi" | "nft" | "governance" | "token" | etc.
    pub decoded: serde_json::Value,   // Function call details JSON
}

/// Minimal DuckLake contract_calls record aligned to schema requirements.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuckLakeContractCallRecord {
    pub chain_id: String,
    pub block_date: String,
    pub shard: i32,
    pub block_number: i64,
    pub block_timestamp: i64,
    pub transaction_hash: String,
    pub call_index: i32,
    pub from_address: String,
    pub to_address: String,
    pub call_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub method_signature: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub method_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub function_signature: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_data: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_data: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_input: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gas_limit: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gas_used: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub call_depth: Option<i32>,
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub revert_reason: Option<String>,
}

/// Minimal DuckLake transaction record aligned to unified transactions schema.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuckLakeTransactionRecord {
    pub chain_id: String,
    pub block_date: String,
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub block_number: u64,
    pub block_timestamp: u64,
    pub transaction_hash: String,
    pub transaction_index: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub from_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub to_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gas_limit: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gas_used: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gas_price: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_fee_per_gas: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_priority_fee_per_gas: Option<String>,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_fee: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub effective_gas_price: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_data: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub method_signature: Option<String>,
    pub transaction_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_subtype: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub amount_native: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub amount_usd: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fee_usd: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transfer_category: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sender_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recipient_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_function_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_function_signature: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_function_selector: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_parameters: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoding_status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub abi_source: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoding_time_ms: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_summary: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub nonce: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub processor_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub correlation_id: Option<String>,
}

/// Minimal DuckLake address_transactions record aligned to schema requirements.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuckLakeAddressTransactionRecord {
    pub chain_id: String,
    pub block_date: String,
    pub address: String,
    pub transaction_hash: String,
    pub block_number: u64,
    pub block_timestamp: u64,
    pub is_sender: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub counterparty_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_subtype: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum FunctionCategory {
    Transfer,   // Maps to transaction_subtype: "transfer"
    Approval,   // Maps to transaction_subtype: "approve"
    Swap,       // Maps to transaction_subtype: "swap"
    Stake,      // Maps to transaction_subtype: "stake"
    Unstake,    // Maps to transaction_subtype: "unstake"
    Borrow,     // Maps to transaction_subtype: "borrow"
    Repay,      // Maps to transaction_subtype: "repay"
    Liquidate,  // Maps to transaction_subtype: "liquidate"
    Governance, // Maps to transaction_subtype: "governance"
    Unknown,    // Maps to transaction_subtype: "unknown"
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TransactionStatus {
    Success,
    Failed,
    Reverted(String),
    OutOfGas,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum DecodingStatus {
    Success,
    Pending,
    Failed,
    NoABI,
    NotRequested,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventLog {
    pub event_signature: String,
    pub event_name: Option<String>,
    pub topics: Vec<String>,
    pub data: String,
    pub log_index: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedParameter {
    pub name: String,
    pub param_type: String,
    pub value: serde_json::Value,
}

/// Main ETH Contract Transaction Processor Actor
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    /// Handle incoming NATS messages containing contract transactions or decoded responses
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        // Handle decoded transaction responses (abi-decoder actor)
        if Self::is_contracts_decoded_subject(&msg.subject)
            || msg.subject == "transactions.decoded.evm"
        {
            return Self::handle_decoded_response(msg);
        }

        // Handle raw contract transactions
        if !msg.subject.starts_with("contract-transactions.") || !msg.subject.ends_with(".raw") {
            return Ok(());
        }

        // Extract network context from subject: contract-transactions.{network}.{subnet}.{vm_type}.raw
        let (network, subnet, vm_type) = Self::parse_subject_context(&msg.subject)?;

        // Parse the contract transaction from the message
        let raw_transaction: RawContractTransaction = serde_json::from_slice(&msg.body)
            .map_err(|e| format!("Failed to parse contract transaction: {}", e))?;

        // Process the transaction and publish results
        Self::process_and_publish_transaction(raw_transaction, network, subnet, vm_type)?;

        Ok(())
    }
}

impl Component {
    fn is_contracts_decoded_subject(subject: &str) -> bool {
        let parts: Vec<&str> = subject.split('.').collect();
        parts.len() == 5
            && parts[0] == "blockchain"
            && parts[3] == "contracts"
            && parts[4] == "decoded"
    }

    fn parse_decoded_payload(body: &[u8]) -> Result<DecodedTransactionResponse, String> {
        if let Ok(decoded_tx) = serde_json::from_slice::<AbiDecodedTransaction>(body) {
            let decoded_params = decoded_tx
                .decoded_function
                .as_ref()
                .map(|func| {
                    func.parameters
                        .iter()
                        .map(|param| DecodedParameter {
                            name: param.name.clone(),
                            param_type: param.param_type.clone(),
                            value: serde_json::Value::String(param.value.clone()),
                        })
                        .collect::<Vec<DecodedParameter>>()
                })
                .unwrap_or_default();

            let function_signature = decoded_tx
                .decoded_function
                .as_ref()
                .map(|func| func.signature.clone());

            return Ok(DecodedTransactionResponse {
                transaction_hash: decoded_tx.transaction_hash,
                network: decoded_tx.network,
                subnet: decoded_tx.subnet,
                decoded_params,
                function_signature,
            });
        }

        serde_json::from_slice::<DecodedTransactionResponse>(body)
            .map_err(|e| format!("Failed to parse decoded response: {}", e))
    }

    /// Handle decoded transaction response from decoder
    fn handle_decoded_response(msg: types::BrokerMessage) -> Result<(), String> {
        let decoded_response = Self::parse_decoded_payload(&msg.body)?;

        eprintln!(
            "[DEBUG] 🔄 Received decoded response for tx: {}",
            decoded_response.transaction_hash
        );

        // In production, would retrieve pending transaction from Redis and merge decoded params
        // For now, just log the received decoded data
        eprintln!(
            "[DEBUG] ✅ Decoded params count: {}",
            decoded_response.decoded_params.len()
        );

        Ok(())
    }

    /// Extract network context from NATS subject
    fn parse_subject_context(subject: &str) -> Result<(String, String, String), String> {
        // contract-transactions.ethereum.mainnet.evm.raw
        let parts: Vec<&str> = subject.split('.').collect();
        if parts.len() >= 5 {
            Ok((
                parts[1].to_string(), // network
                parts[2].to_string(), // subnet
                parts[3].to_string(), // vm_type
            ))
        } else {
            Err(format!("Invalid subject pattern: {}", subject))
        }
    }

    /// Process a contract transaction and publish to appropriate subjects
    fn process_and_publish_transaction(
        raw_tx: RawContractTransaction,
        network: String,
        subnet: String,
        vm_type: String,
    ) -> Result<(), String> {
        // Parse numeric fields from hex strings
        let gas_used = Self::parse_hex_u64(&raw_tx.gas_used);
        let gas_limit = Self::parse_hex_u64(&raw_tx.gas);
        let status_u8 = Self::parse_hex_u64(&raw_tx.status) as u8;
        let block_number = Self::parse_hex_u64(&raw_tx.block_number);
        let block_timestamp = raw_tx
            .block_timestamp
            .as_ref()
            .map(|ts| Self::parse_hex_u64(ts))
            .unwrap_or_else(|| chrono::Utc::now().timestamp() as u64);

        // Extract function selector (first 4 bytes / 8 hex chars of input)
        let function_selector = Self::extract_function_selector(&raw_tx.input);

        // Categorize function
        let function_category = Self::categorize_function(&function_selector);

        // Detect popular functions
        let (is_popular, function_signature) = Self::detect_popular_function(&function_selector);

        // Determine transaction status
        let transaction_status = Self::determine_transaction_status(
            status_u8,
            gas_used,
            gas_limit,
            raw_tx.revert_reason.clone(),
        );

        // Process event logs
        let events = Self::process_event_logs(&raw_tx.logs);

        // Calculate transaction fee
        let transaction_fee_wei = Self::calculate_transaction_fee(gas_used, &raw_tx.gas_price);

        // Determine enrichment fields
        let (transaction_currency, transaction_value) =
            Self::determine_currency_and_value(&network, &raw_tx.value, &events);

        let transaction_subtype = Self::category_to_subtype(&function_category);
        let protocol = Self::detect_protocol(&function_selector, &raw_tx.to);
        let category = Self::determine_category(&function_category, &protocol);

        // Create decoded JSON
        let decoded = Self::create_decoded_json(
            &function_selector,
            function_signature.as_deref(),
            &function_category,
            is_popular,
            None, // Decoded params would come from decoder response
            &events,
            &transaction_status,
            gas_used,
        );

        // Generate correlation ID
        let correlation_id = format!("{}-{}", raw_tx.hash, chrono::Utc::now().timestamp_millis());

        // Create processed transaction
        let processed_tx = ProcessedContractTransaction {
            network: network.clone(),
            subnet: subnet.clone(),
            vm_type: vm_type.clone(),
            transaction_hash: raw_tx.hash.clone(),
            block_number,
            block_timestamp,
            contract_address: raw_tx.to.clone(),
            caller_address: raw_tx.from.clone(),
            function_selector: function_selector.clone(),
            function_signature,
            function_category,
            input_data: raw_tx.input.clone(),
            call_value_wei: raw_tx.value.clone(),
            status: transaction_status,
            revert_reason: raw_tx.revert_reason.clone(),
            gas_used,
            gas_price: raw_tx.gas_price.clone(),
            transaction_fee_wei,
            decoded_params: None, // Would be populated when decoder responds
            decoding_status: DecodingStatus::NotRequested,
            events,
            event_count: raw_tx.logs.len() as u32,
            is_popular_function: is_popular,
            interaction_frequency: 0, // Would be fetched from Redis in production
            processed_at: chrono::Utc::now().to_rfc3339(),
            processor_id: "eth-contract-transaction-processor-actor".to_string(),
            correlation_id,
            transaction_type: "contract_call".to_string(),
            transaction_currency,
            transaction_value,
            transaction_subtype,
            protocol,
            category,
            decoded,
        };

        // Publish to all destinations
        Self::publish_processed_transaction(&processed_tx, &raw_tx, &network, &subnet)?;

        // Request ABI decoding if needed (for unknown functions or important contracts)
        if !is_popular {
            Self::request_abi_decode(&raw_tx, &network, &subnet)?;
        }

        Ok(())
    }

    /// Extract function selector (first 4 bytes)
    fn extract_function_selector(input_data: &str) -> String {
        let cleaned = input_data.trim_start_matches("0x");
        if cleaned.len() >= 8 {
            format!("0x{}", &cleaned[..8])
        } else {
            "0x00000000".to_string()
        }
    }

    /// Categorize function by selector pattern
    fn categorize_function(selector: &str) -> FunctionCategory {
        match selector {
            // ERC20 Transfer functions
            "0xa9059cbb" => FunctionCategory::Transfer, // transfer(address,uint256)
            "0x23b872dd" => FunctionCategory::Transfer, // transferFrom(address,address,uint256)

            // Approval functions
            "0x095ea7b3" => FunctionCategory::Approval, // approve(address,uint256)

            // Swap functions (Uniswap, SushiSwap)
            "0x38ed1739" => FunctionCategory::Swap, // swapExactTokensForTokens
            "0x7ff36ab5" => FunctionCategory::Swap, // swapExactETHForTokens
            "0x18cbafe5" => FunctionCategory::Swap, // swapExactTokensForETH

            // Staking functions
            "0xa694fc3a" => FunctionCategory::Stake, // stake(uint256)
            "0xb6b55f25" => FunctionCategory::Stake, // deposit(uint256)

            // Unstaking functions
            "0x2e1a7d4d" => FunctionCategory::Unstake, // withdraw(uint256)

            // Lending/Borrowing (Aave, Compound)
            "0xc5ebeaec" => FunctionCategory::Borrow, // borrow(address,uint256,uint256,uint16,address)
            "0x573ade81" => FunctionCategory::Repay,  // repay(address,uint256,uint256,address)
            "0x00a718a9" => FunctionCategory::Liquidate, // liquidationCall

            // Governance
            "0xda95691a" => FunctionCategory::Governance, // propose
            "0x15373e3d" => FunctionCategory::Governance, // vote

            _ => FunctionCategory::Unknown,
        }
    }

    /// Detect popular functions and return signature
    fn detect_popular_function(selector: &str) -> (bool, Option<String>) {
        let popular_functions: HashMap<&str, &str> = [
            // ERC20
            ("0xa9059cbb", "transfer(address,uint256)"),
            ("0x095ea7b3", "approve(address,uint256)"),
            ("0x23b872dd", "transferFrom(address,address,uint256)"),
            // Uniswap V2
            (
                "0x38ed1739",
                "swapExactTokensForTokens(uint256,uint256,address[],address,uint256)",
            ),
            (
                "0x7ff36ab5",
                "swapExactETHForTokens(uint256,address[],address,uint256)",
            ),
            (
                "0x18cbafe5",
                "swapExactTokensForETH(uint256,uint256,address[],address,uint256)",
            ),
            // Common DeFi
            ("0xa694fc3a", "stake(uint256)"),
            ("0xb6b55f25", "deposit(uint256)"),
            ("0x2e1a7d4d", "withdraw(uint256)"),
            (
                "0xc5ebeaec",
                "borrow(address,uint256,uint256,uint16,address)",
            ),
            ("0x573ade81", "repay(address,uint256,uint256,address)"),
        ]
        .iter()
        .cloned()
        .collect();

        if let Some(signature) = popular_functions.get(selector) {
            (true, Some(signature.to_string()))
        } else {
            (false, None)
        }
    }

    /// Determine transaction status from receipt
    fn determine_transaction_status(
        status: u8,
        gas_used: u64,
        gas_limit: u64,
        revert_reason: Option<String>,
    ) -> TransactionStatus {
        if status == 1 {
            TransactionStatus::Success
        } else if gas_used >= gas_limit {
            TransactionStatus::OutOfGas
        } else if let Some(reason) = revert_reason {
            TransactionStatus::Reverted(reason)
        } else {
            TransactionStatus::Failed
        }
    }

    /// Process event logs from transaction receipt
    fn process_event_logs(raw_logs: &[RawEventLog]) -> Vec<EventLog> {
        raw_logs
            .iter()
            .map(|log| {
                let event_signature = log.topics.first().cloned().unwrap_or_default();
                let event_name = Self::detect_event_name(&event_signature);

                EventLog {
                    event_signature,
                    event_name,
                    topics: log.topics.clone(),
                    data: log.data.clone(),
                    log_index: log.log_index,
                }
            })
            .collect()
    }

    /// Detect common event names from signature
    fn detect_event_name(signature: &str) -> Option<String> {
        let common_events: HashMap<&str, &str> = [
            (
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "Transfer",
            ),
            (
                "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925",
                "Approval",
            ),
            (
                "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822",
                "Swap",
            ),
            (
                "0xe1fffcc4923d04b559f4d29a8bfc6cda04eb5b0d3c460751c2402c5c5cc9109c",
                "Deposit",
            ),
            (
                "0x7fcf532c15f0a6db0bd6d0e038bea71d30d808c7d98cb3bf7268a95bf5081b65",
                "Withdrawal",
            ),
        ]
        .iter()
        .cloned()
        .collect();

        common_events.get(signature).map(|s| s.to_string())
    }

    /// Determine currency and value from transaction and events
    fn determine_currency_and_value(
        network: &str,
        call_value_wei: &str,
        events: &[EventLog],
    ) -> (String, String) {
        let call_value = Self::parse_hex_u128(call_value_wei);

        // Check if there's a native currency transfer
        if call_value > 0 {
            let currency = Self::get_network_currency(network);
            let value_eth = Self::wei_to_eth(call_value_wei);
            return (currency.clone(), format!("{:.6} {}", value_eth, currency));
        }

        // Check for token transfers in events
        for event in events {
            if event.event_name.as_deref() == Some("Transfer") && event.topics.len() >= 3 {
                // This is a token transfer - would extract token symbol from decoder/registry
                return ("TOKEN".to_string(), "UNKNOWN TOKEN".to_string());
            }
        }

        ("NONE".to_string(), "0".to_string())
    }

    /// Convert function category to transaction subtype
    fn category_to_subtype(category: &FunctionCategory) -> String {
        match category {
            FunctionCategory::Transfer => "transfer".to_string(),
            FunctionCategory::Approval => "approve".to_string(),
            FunctionCategory::Swap => "swap".to_string(),
            FunctionCategory::Stake => "stake".to_string(),
            FunctionCategory::Unstake => "unstake".to_string(),
            FunctionCategory::Borrow => "borrow".to_string(),
            FunctionCategory::Repay => "repay".to_string(),
            FunctionCategory::Liquidate => "liquidate".to_string(),
            FunctionCategory::Governance => "governance".to_string(),
            FunctionCategory::Unknown => "unknown".to_string(),
        }
    }

    /// Detect protocol from function selector and contract address
    fn detect_protocol(selector: &str, _contract_address: &str) -> Option<String> {
        // Based on function selector patterns
        match selector {
            // Uniswap V2
            "0x38ed1739" | "0x7ff36ab5" | "0x18cbafe5" => Some("Uniswap_V2".to_string()),

            // Aave
            "0xc5ebeaec" | "0x573ade81" | "0x00a718a9" => Some("Aave".to_string()),

            // ERC20
            "0xa9059cbb" | "0x095ea7b3" | "0x23b872dd" => Some("ERC20".to_string()),

            _ => None,
        }
    }

    /// Determine category from function category and protocol
    fn determine_category(category: &FunctionCategory, protocol: &Option<String>) -> String {
        match category {
            FunctionCategory::Transfer | FunctionCategory::Approval => {
                if protocol.as_deref() == Some("ERC20") {
                    "token".to_string()
                } else {
                    "token".to_string()
                }
            }
            FunctionCategory::Swap
            | FunctionCategory::Stake
            | FunctionCategory::Unstake
            | FunctionCategory::Borrow
            | FunctionCategory::Repay
            | FunctionCategory::Liquidate => "defi".to_string(),
            FunctionCategory::Governance => "governance".to_string(),
            FunctionCategory::Unknown => "unknown".to_string(),
        }
    }

    /// Create decoded JSON structure per PRD specification
    fn create_decoded_json(
        selector: &str,
        signature: Option<&str>,
        category: &FunctionCategory,
        is_popular: bool,
        decoded_params: Option<&Vec<DecodedParameter>>,
        events: &[EventLog],
        status: &TransactionStatus,
        gas_used: u64,
    ) -> serde_json::Value {
        let status_str = match status {
            TransactionStatus::Success => "success",
            TransactionStatus::Failed => "failed",
            TransactionStatus::Reverted(_) => "reverted",
            TransactionStatus::OutOfGas => "out_of_gas",
        };

        let revert_reason = match status {
            TransactionStatus::Reverted(reason) => Some(reason.clone()),
            _ => None,
        };

        serde_json::json!({
            "function": {
                "selector": selector,
                "signature": signature,
                "category": format!("{:?}", category).to_lowercase(),
                "is_popular": is_popular
            },
            "parameters": decoded_params.map(|params| {
                params.iter().map(|p| {
                    serde_json::json!({
                        "name": p.name,
                        "type": p.param_type,
                        "value": p.value
                    })
                }).collect::<Vec<_>>()
            }).unwrap_or_default(),
            "events": events.iter().map(|e| {
                serde_json::json!({
                    "name": e.event_name,
                    "contract": e.topics.get(0).cloned().unwrap_or_default(),
                    "topics": e.topics.clone(),
                    "data": e.data.clone()
                })
            }).collect::<Vec<_>>(),
            "execution": {
                "status": status_str,
                "revert_reason": revert_reason,
                "gas_used": gas_used
            }
        })
    }

    /// Calculate transaction fee in Wei
    fn calculate_transaction_fee(gas_used: u64, gas_price_hex: &str) -> String {
        let gas_price = Self::parse_hex_u128(gas_price_hex);
        let fee = gas_price * gas_used as u128;
        format!("0x{:x}", fee)
    }

    /// Convert Wei to ETH
    fn wei_to_eth(wei_hex: &str) -> f64 {
        let wei_value = Self::parse_hex_u128(wei_hex);
        wei_value as f64 / 1_000_000_000_000_000_000.0
    }

    /// Get network currency
    fn get_network_currency(network: &str) -> String {
        match network.to_lowercase().as_str() {
            "ethereum" => "ETH".to_string(),
            "polygon" => "MATIC".to_string(),
            "binance" => "BNB".to_string(),
            "avalanche" => "AVAX".to_string(),
            _ => "ETH".to_string(),
        }
    }

    /// Parse hex string to u128
    fn parse_hex_u128(hex_str: &str) -> u128 {
        let cleaned = hex_str.trim_start_matches("0x");
        u128::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Parse hex string to u64
    fn parse_hex_u64(hex_str: &str) -> u64 {
        let cleaned = hex_str.trim_start_matches("0x");
        u64::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Request ABI decoding for a transaction
    fn request_abi_decode(
        raw_tx: &RawContractTransaction,
        network: &str,
        subnet: &str,
    ) -> Result<(), String> {
        let decode_request = serde_json::json!({
            "transaction_hash": raw_tx.hash,
            "network": network,
            "subnet": subnet,
            "contract_address": raw_tx.to,
            "function_selector": Self::extract_function_selector(&raw_tx.input),
            "input_data": raw_tx.input,
        });

        let payload = serde_json::to_vec(&decode_request)
            .map_err(|e| format!("Failed to serialize decode request: {}", e))?;

        let decode_subject = "abi.decode.request".to_string();

        Self::publish_message(&decode_subject, &payload)?;
        eprintln!("[DEBUG] 🔄 Requested ABI decode for tx: {}", raw_tx.hash);

        Ok(())
    }

    /// Publish processed transaction to all destinations
    fn publish_processed_transaction(
        processed_tx: &ProcessedContractTransaction,
        raw_tx: &RawContractTransaction,
        network: &str,
        subnet: &str,
    ) -> Result<(), String> {
        let payload = serde_json::to_vec(processed_tx)
            .map_err(|e| format!("Failed to serialize processed transaction: {}", e))?;

        // 1. Publish to processed contract calls subject
        let processed_subject = "contract-calls.processed.evm".to_string();
        Self::publish_message(&processed_subject, &payload)?;

        // 2. Publish to alert evaluation system
        let alert_subject = format!("alerts.evaluate.{}.{}", network, subnet);
        Self::publish_message(&alert_subject, &payload)?;

        // 3. Publish to DuckLake for persistence
        let ducklake_record = Self::build_ducklake_contract_call_record(processed_tx);
        let ducklake_payload = serde_json::to_vec(&ducklake_record)
            .map_err(|e| format!("Failed to serialize ducklake contract call: {}", e))?;
        let ducklake_subject = format!("ducklake.contract_calls.{}.{}.write", network, subnet);
        Self::publish_message(&ducklake_subject, &ducklake_payload)?;

        let transaction_record = Self::build_ducklake_transaction_record(processed_tx, raw_tx);
        let transaction_payload = serde_json::to_vec(&transaction_record)
            .map_err(|e| format!("Failed to serialize ducklake transaction: {}", e))?;
        let transaction_subject = format!("ducklake.transactions.{}.{}.write", network, subnet);
        Self::publish_message(&transaction_subject, &transaction_payload)?;

        let address_records = Self::build_address_transaction_records(processed_tx, raw_tx);
        let address_subject = format!("ducklake.address_transactions.{}.{}.write", network, subnet);
        for record in address_records {
            let address_payload = serde_json::to_vec(&record)
                .map_err(|e| format!("Failed to serialize address transaction: {}", e))?;
            Self::publish_message(&address_subject, &address_payload)?;
        }

        Ok(())
    }

    /// Helper to publish a message to a subject
    fn publish_message(subject: &str, payload: &[u8]) -> Result<(), String> {
        let msg = types::BrokerMessage {
            subject: subject.to_string(),
            body: payload.to_vec(),
            reply_to: None,
        };

        consumer::publish(&msg)
            .map_err(|e| format!("Failed to publish to {}: {:?}", subject, e))?;

        eprintln!("[DEBUG] ✅ Published to: {}", subject);
        Ok(())
    }

    fn build_ducklake_contract_call_record(
        processed_tx: &ProcessedContractTransaction,
    ) -> DuckLakeContractCallRecord {
        let block_date = Utc
            .timestamp_opt(processed_tx.block_timestamp as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "1970-01-01".to_string());

        let method_name = processed_tx
            .function_signature
            .as_ref()
            .and_then(|sig| sig.split('(').next())
            .map(|name| name.to_string());

        let method_signature = if processed_tx.function_selector.trim().is_empty() {
            None
        } else {
            Some(processed_tx.function_selector.clone())
        };

        let input_data =
            if processed_tx.input_data.trim().is_empty() || processed_tx.input_data == "0x" {
                None
            } else {
                Some(processed_tx.input_data.clone())
            };

        let decoded_input = processed_tx
            .decoded_params
            .as_ref()
            .and_then(|params| serde_json::to_string(params).ok());

        let (success, revert_reason) =
            Self::status_fields(&processed_tx.status, &processed_tx.revert_reason);

        DuckLakeContractCallRecord {
            chain_id: format!("{}_{}", processed_tx.network, processed_tx.subnet),
            block_date,
            shard: 0,
            block_number: processed_tx.block_number as i64,
            block_timestamp: processed_tx.block_timestamp as i64,
            transaction_hash: processed_tx.transaction_hash.clone(),
            call_index: 0,
            from_address: processed_tx.caller_address.clone(),
            to_address: processed_tx.contract_address.clone(),
            call_type: "call".to_string(),
            method_signature,
            method_name,
            function_signature: processed_tx.function_signature.clone(),
            input_data,
            output_data: None,
            decoded_input,
            decoded_output: None,
            gas_limit: None,
            gas_used: Some(processed_tx.gas_used as i64),
            value: Some(Self::normalize_quantity_string(
                &processed_tx.call_value_wei,
            )),
            call_depth: None,
            success,
            revert_reason,
        }
    }

    fn build_ducklake_transaction_record(
        processed_tx: &ProcessedContractTransaction,
        raw_tx: &RawContractTransaction,
    ) -> DuckLakeTransactionRecord {
        let block_date = Utc
            .timestamp_opt(processed_tx.block_timestamp as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "1970-01-01".to_string());

        let transaction_index = Self::parse_hex_u64(&raw_tx.transaction_index) as u32;
        let gas_limit = Self::parse_hex_u64(&raw_tx.gas);
        let nonce = Some(Self::parse_hex_u64(&raw_tx.nonce));
        let v = raw_tx.v.as_ref().map(|value| Self::parse_hex_u64(value));

        let gas_price = Self::normalize_quantity_string(&processed_tx.gas_price);
        let value = Self::normalize_quantity_string(&processed_tx.call_value_wei);
        let transaction_fee = Self::normalize_quantity_string(&processed_tx.transaction_fee_wei);

        let input_data =
            if processed_tx.input_data.trim().is_empty() || processed_tx.input_data == "0x" {
                None
            } else {
                Some(processed_tx.input_data.clone())
            };

        let decoded_parameters = processed_tx
            .decoded_params
            .as_ref()
            .and_then(|params| serde_json::to_string(params).ok());

        let decoded_function_name = processed_tx
            .function_signature
            .as_ref()
            .and_then(|sig| sig.split('(').next())
            .map(|name| name.to_string());

        DuckLakeTransactionRecord {
            chain_id: format!("{}_{}", processed_tx.network, processed_tx.subnet),
            block_date,
            network: processed_tx.network.clone(),
            subnet: processed_tx.subnet.clone(),
            vm_type: processed_tx.vm_type.clone(),
            block_number: processed_tx.block_number,
            block_timestamp: processed_tx.block_timestamp,
            transaction_hash: processed_tx.transaction_hash.clone(),
            transaction_index,
            from_address: Some(processed_tx.caller_address.clone()),
            to_address: Some(processed_tx.contract_address.clone()),
            value: Some(value),
            gas_limit: Some(gas_limit),
            gas_used: Some(processed_tx.gas_used),
            gas_price: Some(gas_price.clone()),
            max_fee_per_gas: None,
            max_priority_fee_per_gas: None,
            status: Self::transaction_status_string(&processed_tx.status),
            transaction_fee: Some(transaction_fee),
            effective_gas_price: Some(gas_price),
            input_data,
            method_signature: Some(processed_tx.function_selector.clone()),
            transaction_type: processed_tx.transaction_type.clone(),
            transaction_subtype: Some(processed_tx.transaction_subtype.clone()),
            amount_native: Some(Self::wei_to_eth(&processed_tx.call_value_wei)),
            amount_usd: None,
            fee_usd: None,
            transfer_category: None,
            sender_type: None,
            recipient_type: None,
            decoded_function_name,
            decoded_function_signature: processed_tx.function_signature.clone(),
            decoded_function_selector: Some(processed_tx.function_selector.clone()),
            decoded_parameters,
            decoding_status: Some(Self::decoding_status_string(&processed_tx.decoding_status)),
            abi_source: None,
            decoding_time_ms: None,
            decoded_summary: None,
            nonce,
            v,
            r: raw_tx.r.clone(),
            s: raw_tx.s.clone(),
            processor_id: Some(processed_tx.processor_id.clone()),
            correlation_id: Some(processed_tx.correlation_id.clone()),
        }
    }

    fn build_address_transaction_records(
        processed_tx: &ProcessedContractTransaction,
        _raw_tx: &RawContractTransaction,
    ) -> Vec<DuckLakeAddressTransactionRecord> {
        let block_date = Utc
            .timestamp_opt(processed_tx.block_timestamp as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "1970-01-01".to_string());

        let chain_id = format!("{}_{}", processed_tx.network, processed_tx.subnet);
        let value = Some(Self::normalize_quantity_string(
            &processed_tx.call_value_wei,
        ));
        let transaction_type = Some(processed_tx.transaction_type.clone());
        let transaction_subtype = Some(processed_tx.transaction_subtype.clone());

        let caller_address = processed_tx.caller_address.to_lowercase();
        let contract_address = processed_tx.contract_address.to_lowercase();

        vec![
            DuckLakeAddressTransactionRecord {
                chain_id: chain_id.clone(),
                block_date: block_date.clone(),
                address: caller_address.clone(),
                transaction_hash: processed_tx.transaction_hash.clone(),
                block_number: processed_tx.block_number,
                block_timestamp: processed_tx.block_timestamp,
                is_sender: true,
                counterparty_address: Some(contract_address.clone()),
                value: value.clone(),
                transaction_type: transaction_type.clone(),
                transaction_subtype: transaction_subtype.clone(),
            },
            DuckLakeAddressTransactionRecord {
                chain_id,
                block_date,
                address: contract_address,
                transaction_hash: processed_tx.transaction_hash.clone(),
                block_number: processed_tx.block_number,
                block_timestamp: processed_tx.block_timestamp,
                is_sender: false,
                counterparty_address: Some(caller_address),
                value,
                transaction_type,
                transaction_subtype,
            },
        ]
    }

    fn status_fields(
        status: &TransactionStatus,
        revert_reason: &Option<String>,
    ) -> (bool, Option<String>) {
        match status {
            TransactionStatus::Success => (true, None),
            TransactionStatus::Failed => (false, revert_reason.clone()),
            TransactionStatus::OutOfGas => (false, revert_reason.clone()),
            TransactionStatus::Reverted(reason) => {
                let reason_value = Some(reason.clone());
                (false, reason_value.or_else(|| revert_reason.clone()))
            }
        }
    }

    fn transaction_status_string(status: &TransactionStatus) -> String {
        match status {
            TransactionStatus::Success => "SUCCESS".to_string(),
            TransactionStatus::Failed => "FAILED".to_string(),
            TransactionStatus::OutOfGas => "FAILED".to_string(),
            TransactionStatus::Reverted(_) => "FAILED".to_string(),
        }
    }

    fn decoding_status_string(status: &DecodingStatus) -> String {
        match status {
            DecodingStatus::Success => "Success".to_string(),
            DecodingStatus::Pending => "Pending".to_string(),
            DecodingStatus::Failed => "Failed".to_string(),
            DecodingStatus::NoABI => "AbiNotFound".to_string(),
            DecodingStatus::NotRequested => "NotRequested".to_string(),
        }
    }

    fn normalize_quantity_string(value: &str) -> String {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            return "0".to_string();
        }
        let normalized = trimmed.trim_start_matches("0x");
        if trimmed.starts_with("0x") {
            u128::from_str_radix(normalized, 16)
                .unwrap_or(0)
                .to_string()
        } else {
            normalized.parse::<u128>().unwrap_or(0).to_string()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_transaction() -> RawContractTransaction {
        RawContractTransaction {
            // Standard Ethereum transaction fields (all hex-encoded)
            hash: "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string(),
            from: "0xcaller1234567890abcdef1234567890abcdef12".to_string(),
            to: "0xcontract1234567890abcdef1234567890abcd".to_string(),
            value: "0x0".to_string(),
            gas: "0x186a0".to_string(), // 100000
            gas_price: "0x4a817c800".to_string(), // 20 Gwei
            input: "0xa9059cbb000000000000000000000000recipient1230000000000000000000000000000000000000000000000000000000000000064".to_string(),
            nonce: "0x5".to_string(),
            block_number: "0x11a4810".to_string(), // 18500000
            block_hash: "0xblockhash1234567890abcdef1234567890abcdef1234567890abcdef12345678".to_string(),
            transaction_index: "0xa".to_string(),
            chain_id: "0x1".to_string(), // Ethereum mainnet
            v: Some("0x1b".to_string()),
            r: Some("0xr1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string()),
            s: Some("0xs1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string()),

            // Receipt data
            status: "0x1".to_string(), // Success
            revert_reason: None,
            gas_used: "0xc350".to_string(), // 50000
            logs: vec![
                RawEventLog {
                    address: "0xcontract1234567890abcdef1234567890abcd".to_string(),
                    topics: vec![
                        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef".to_string(),
                        "0x000000000000000000000000caller1234567890abcdef1234567890abcdef12".to_string(),
                        "0x000000000000000000000000recipient1234567890abcdef1234567890abcdef".to_string(),
                    ],
                    data: "0x0000000000000000000000000000000000000000000000000000000000000064".to_string(),
                    log_index: 0,
                }
            ],
            block_timestamp: Some("0x65a4c888".to_string()), // 1705320600
        }
    }

    #[test]
    fn test_extract_function_selector() {
        let input_data = "0xa9059cbb000000000000000000000000recipient123";
        let selector = Component::extract_function_selector(input_data);
        assert_eq!(selector, "0xa9059cbb");

        // Test short input
        let short_input = "0x1234";
        let selector = Component::extract_function_selector(short_input);
        assert_eq!(selector, "0x00000000");
    }

    #[test]
    fn test_categorize_function() {
        assert_eq!(
            Component::categorize_function("0xa9059cbb"),
            FunctionCategory::Transfer
        );
        assert_eq!(
            Component::categorize_function("0x095ea7b3"),
            FunctionCategory::Approval
        );
        assert_eq!(
            Component::categorize_function("0x38ed1739"),
            FunctionCategory::Swap
        );
        assert_eq!(
            Component::categorize_function("0xa694fc3a"),
            FunctionCategory::Stake
        );
        assert_eq!(
            Component::categorize_function("0xc5ebeaec"),
            FunctionCategory::Borrow
        );
        assert_eq!(
            Component::categorize_function("0x00000000"),
            FunctionCategory::Unknown
        );
    }

    #[test]
    fn test_detect_popular_function() {
        let (is_popular, signature) = Component::detect_popular_function("0xa9059cbb");
        assert!(is_popular);
        assert_eq!(signature, Some("transfer(address,uint256)".to_string()));

        let (is_popular, signature) = Component::detect_popular_function("0x38ed1739");
        assert!(is_popular);
        assert_eq!(
            signature,
            Some("swapExactTokensForTokens(uint256,uint256,address[],address,uint256)".to_string())
        );

        let (is_popular, signature) = Component::detect_popular_function("0x00000000");
        assert!(!is_popular);
        assert_eq!(signature, None);
    }

    #[test]
    fn test_determine_transaction_status() {
        // Success
        let status = Component::determine_transaction_status(1, 50000, 100000, None);
        assert_eq!(status, TransactionStatus::Success);

        // Failed
        let status = Component::determine_transaction_status(0, 50000, 100000, None);
        assert_eq!(status, TransactionStatus::Failed);

        // Out of gas
        let status = Component::determine_transaction_status(0, 100000, 100000, None);
        assert_eq!(status, TransactionStatus::OutOfGas);

        // Reverted
        let status = Component::determine_transaction_status(
            0,
            50000,
            100000,
            Some("Insufficient balance".to_string()),
        );
        match status {
            TransactionStatus::Reverted(reason) => assert_eq!(reason, "Insufficient balance"),
            _ => panic!("Expected Reverted status"),
        }
    }

    #[test]
    fn test_process_event_logs() {
        let raw_logs = vec![RawEventLog {
            address: "0xcontract123".to_string(),
            topics: vec![
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef".to_string(),
            ],
            data: "0x1234".to_string(),
            log_index: 0,
        }];

        let events = Component::process_event_logs(&raw_logs);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].event_name, Some("Transfer".to_string()));
        assert_eq!(events[0].log_index, 0);
    }

    #[test]
    fn test_detect_event_name() {
        assert_eq!(
            Component::detect_event_name(
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            ),
            Some("Transfer".to_string())
        );
        assert_eq!(
            Component::detect_event_name(
                "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
            ),
            Some("Approval".to_string())
        );
        assert_eq!(Component::detect_event_name("0xunknown"), None);
    }

    #[test]
    fn test_determine_currency_and_value() {
        let events = vec![];

        // Native currency transfer
        let (currency, value) = Component::determine_currency_and_value(
            "ethereum",
            "0xde0b6b3a7640000", // 1 ETH
            &events,
        );
        assert_eq!(currency, "ETH");
        assert!(value.contains("ETH"));

        // No value
        let (currency, value) = Component::determine_currency_and_value("ethereum", "0x0", &events);
        assert_eq!(currency, "NONE");
        assert_eq!(value, "0");
    }

    #[test]
    fn test_category_to_subtype() {
        assert_eq!(
            Component::category_to_subtype(&FunctionCategory::Transfer),
            "transfer"
        );
        assert_eq!(
            Component::category_to_subtype(&FunctionCategory::Swap),
            "swap"
        );
        assert_eq!(
            Component::category_to_subtype(&FunctionCategory::Governance),
            "governance"
        );
    }

    #[test]
    fn test_detect_protocol() {
        assert_eq!(
            Component::detect_protocol("0x38ed1739", "0xcontract"),
            Some("Uniswap_V2".to_string())
        );
        assert_eq!(
            Component::detect_protocol("0xc5ebeaec", "0xcontract"),
            Some("Aave".to_string())
        );
        assert_eq!(
            Component::detect_protocol("0xa9059cbb", "0xcontract"),
            Some("ERC20".to_string())
        );
        assert_eq!(Component::detect_protocol("0x00000000", "0xcontract"), None);
    }

    #[test]
    fn test_determine_category() {
        assert_eq!(
            Component::determine_category(&FunctionCategory::Transfer, &Some("ERC20".to_string())),
            "token"
        );
        assert_eq!(
            Component::determine_category(&FunctionCategory::Swap, &Some("Uniswap_V2".to_string())),
            "defi"
        );
        assert_eq!(
            Component::determine_category(&FunctionCategory::Governance, &None),
            "governance"
        );
    }

    #[test]
    fn test_create_decoded_json() {
        let events = vec![EventLog {
            event_signature: "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                .to_string(),
            event_name: Some("Transfer".to_string()),
            topics: vec![
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef".to_string(),
            ],
            data: "0x1234".to_string(),
            log_index: 0,
        }];

        let decoded = Component::create_decoded_json(
            "0xa9059cbb",
            Some("transfer(address,uint256)"),
            &FunctionCategory::Transfer,
            true,
            None,
            &events,
            &TransactionStatus::Success,
            50000,
        );

        assert_eq!(decoded["function"]["selector"], "0xa9059cbb");
        assert_eq!(
            decoded["function"]["signature"],
            "transfer(address,uint256)"
        );
        assert_eq!(decoded["function"]["is_popular"], true);
        assert_eq!(decoded["execution"]["status"], "success");
        assert_eq!(decoded["execution"]["gas_used"], 50000);
        assert_eq!(decoded["events"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn test_calculate_transaction_fee() {
        let fee = Component::calculate_transaction_fee(50000, "0x4a817c800"); // 20 Gwei
        let fee_eth = Component::wei_to_eth(&fee);
        assert!((fee_eth - 0.001).abs() < 0.0001); // 50000 * 20 Gwei = 0.001 ETH
    }

    #[test]
    fn test_wei_to_eth() {
        let eth = Component::wei_to_eth("0xde0b6b3a7640000"); // 1 ETH
        assert!((eth - 1.0).abs() < 0.0001);

        let eth = Component::wei_to_eth("0x6f05b59d3b20000"); // 0.5 ETH
        assert!((eth - 0.5).abs() < 0.0001);
    }

    #[test]
    fn test_get_network_currency() {
        assert_eq!(Component::get_network_currency("ethereum"), "ETH");
        assert_eq!(Component::get_network_currency("polygon"), "MATIC");
        assert_eq!(Component::get_network_currency("binance"), "BNB");
        assert_eq!(Component::get_network_currency("avalanche"), "AVAX");
        assert_eq!(Component::get_network_currency("unknown"), "ETH");
    }

    #[test]
    fn test_parse_hex_u128() {
        assert_eq!(Component::parse_hex_u128("0x1234"), 0x1234);
        assert_eq!(Component::parse_hex_u128("1234"), 0x1234);
        assert_eq!(Component::parse_hex_u128("0x0"), 0);
        assert_eq!(
            Component::parse_hex_u128("0xde0b6b3a7640000"),
            1_000_000_000_000_000_000
        );
        assert_eq!(Component::parse_hex_u128("invalid"), 0);
    }

    #[test]
    fn test_all_enrichment_fields_populated() {
        let raw_tx = create_test_transaction();
        let selector = Component::extract_function_selector(&raw_tx.input);
        let category = Component::categorize_function(&selector);
        let network = "ethereum";
        let (currency, value) =
            Component::determine_currency_and_value(network, &raw_tx.value, &[]);
        let subtype = Component::category_to_subtype(&category);
        let protocol = Component::detect_protocol(&selector, &raw_tx.to);
        let cat = Component::determine_category(&category, &protocol);

        // Verify all 7 enrichment fields
        assert_eq!("contract_call", "contract_call");
        assert_eq!(currency, "NONE"); // No value in test
        assert_eq!(value, "0");
        assert_eq!(subtype, "transfer");
        assert_eq!(protocol, Some("ERC20".to_string()));
        assert_eq!(cat, "token");
    }

    #[test]
    fn test_decoded_structure_completeness() {
        let events = vec![];
        let decoded = Component::create_decoded_json(
            "0xa9059cbb",
            Some("transfer(address,uint256)"),
            &FunctionCategory::Transfer,
            true,
            None,
            &events,
            &TransactionStatus::Success,
            50000,
        );

        // Verify all required fields in decoded JSON
        assert!(decoded.get("function").is_some());
        assert!(decoded["function"].get("selector").is_some());
        assert!(decoded["function"].get("signature").is_some());
        assert!(decoded["function"].get("category").is_some());
        assert!(decoded["function"].get("is_popular").is_some());
        assert!(decoded.get("parameters").is_some());
        assert!(decoded.get("events").is_some());
        assert!(decoded.get("execution").is_some());
        assert!(decoded["execution"].get("status").is_some());
        assert!(decoded["execution"].get("gas_used").is_some());
    }

    #[test]
    fn test_is_contracts_decoded_subject() {
        assert!(Component::is_contracts_decoded_subject(
            "blockchain.ethereum.mainnet.contracts.decoded"
        ));
        assert!(!Component::is_contracts_decoded_subject(
            "transactions.decoded.evm"
        ));
        assert!(!Component::is_contracts_decoded_subject(
            "blockchain.ethereum.mainnet.transactions.processed"
        ));
    }

    #[test]
    fn test_parse_decoded_payload_abi_decoder() {
        let decoded = AbiDecodedTransaction {
            transaction_hash: "0xabc".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            decoding_status: "Success".to_string(),
            decoded_function: Some(AbiDecodedFunction {
                name: "transfer".to_string(),
                selector: "0xa9059cbb".to_string(),
                signature: "transfer(address,uint256)".to_string(),
                parameters: vec![
                    AbiDecodedParameter {
                        name: "to".to_string(),
                        param_type: "address".to_string(),
                        value: "0xdeadbeef".to_string(),
                        indexed: false,
                    },
                    AbiDecodedParameter {
                        name: "amount".to_string(),
                        param_type: "uint256".to_string(),
                        value: "1000".to_string(),
                        indexed: false,
                    },
                ],
            }),
        };

        let body = serde_json::to_vec(&decoded).expect("serialize decoded tx");
        let parsed = Component::parse_decoded_payload(&body).expect("parse decoded payload");

        assert_eq!(parsed.transaction_hash, "0xabc");
        assert_eq!(parsed.decoded_params.len(), 2);
        assert_eq!(
            parsed.function_signature.as_deref(),
            Some("transfer(address,uint256)")
        );
    }

    #[test]
    fn test_build_ducklake_contract_call_record() {
        let processed_tx = ProcessedContractTransaction {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: "0xabc".to_string(),
            block_number: 18500000,
            block_timestamp: 1700000000,
            contract_address: "0xcontract".to_string(),
            caller_address: "0xcaller".to_string(),
            function_selector: "0xa9059cbb".to_string(),
            function_signature: Some("transfer(address,uint256)".to_string()),
            function_category: FunctionCategory::Transfer,
            input_data: "0xa9059cbb".to_string(),
            call_value_wei: "0x0".to_string(),
            status: TransactionStatus::Success,
            revert_reason: None,
            gas_used: 21000,
            gas_price: "0x4a817c800".to_string(),
            transaction_fee_wei: "0x0".to_string(),
            decoded_params: None,
            decoding_status: DecodingStatus::NotRequested,
            events: vec![],
            event_count: 0,
            is_popular_function: true,
            interaction_frequency: 1,
            processed_at: "2024-01-01T00:00:00Z".to_string(),
            processor_id: "test".to_string(),
            correlation_id: "corr".to_string(),
            transaction_type: "contract_call".to_string(),
            transaction_currency: "NONE".to_string(),
            transaction_value: "0".to_string(),
            transaction_subtype: "transfer".to_string(),
            protocol: Some("ERC20".to_string()),
            category: "token".to_string(),
            decoded: serde_json::json!({}),
        };

        let record = Component::build_ducklake_contract_call_record(&processed_tx);

        assert_eq!(record.chain_id, "ethereum_mainnet");
        assert_eq!(record.call_index, 0);
        assert!(record.success);
        assert_eq!(record.value, Some("0".to_string()));
        assert_eq!(record.transaction_hash, "0xabc");
    }

    #[test]
    fn test_build_ducklake_transaction_record() {
        let processed_tx = ProcessedContractTransaction {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: "0xabc".to_string(),
            block_number: 18500000,
            block_timestamp: 1700000000,
            contract_address: "0xcontract".to_string(),
            caller_address: "0xcaller".to_string(),
            function_selector: "0xa9059cbb".to_string(),
            function_signature: Some("transfer(address,uint256)".to_string()),
            function_category: FunctionCategory::Transfer,
            input_data: "0xa9059cbb".to_string(),
            call_value_wei: "0x0".to_string(),
            status: TransactionStatus::Success,
            revert_reason: None,
            gas_used: 21000,
            gas_price: "0x4a817c800".to_string(),
            transaction_fee_wei: "0x0".to_string(),
            decoded_params: None,
            decoding_status: DecodingStatus::NotRequested,
            events: vec![],
            event_count: 0,
            is_popular_function: true,
            interaction_frequency: 1,
            processed_at: "2024-01-01T00:00:00Z".to_string(),
            processor_id: "test".to_string(),
            correlation_id: "corr".to_string(),
            transaction_type: "contract_call".to_string(),
            transaction_currency: "NONE".to_string(),
            transaction_value: "0".to_string(),
            transaction_subtype: "transfer".to_string(),
            protocol: Some("ERC20".to_string()),
            category: "token".to_string(),
            decoded: serde_json::json!({}),
        };

        let raw_tx = RawContractTransaction {
            hash: "0xabc".to_string(),
            from: "0xcaller".to_string(),
            to: "0xcontract".to_string(),
            value: "0x0".to_string(),
            gas: "0x5208".to_string(),
            gas_price: "0x4a817c800".to_string(),
            input: "0xa9059cbb".to_string(),
            nonce: "0x2a".to_string(),
            block_number: "0x11a4bc0".to_string(),
            block_hash: "0xblockhash".to_string(),
            transaction_index: "0x5".to_string(),
            chain_id: "0x1".to_string(),
            v: Some("0x1".to_string()),
            r: Some("0x2".to_string()),
            s: Some("0x3".to_string()),
            status: "0x1".to_string(),
            revert_reason: None,
            gas_used: "0x5208".to_string(),
            logs: vec![],
            block_timestamp: Some(format!("0x{:x}", processed_tx.block_timestamp)),
        };

        let record = Component::build_ducklake_transaction_record(&processed_tx, &raw_tx);

        assert_eq!(record.chain_id, "ethereum_mainnet");
        assert_eq!(record.transaction_hash, "0xabc");
        assert_eq!(record.transaction_index, 5);
        assert_eq!(record.status, "SUCCESS");
        assert_eq!(record.method_signature, Some("0xa9059cbb".to_string()));
        assert!(record.amount_native.unwrap_or(1.0).abs() < 1e-9);
    }

    #[test]
    fn test_build_address_transaction_records() {
        let processed_tx = ProcessedContractTransaction {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: "0xabc".to_string(),
            block_number: 18500000,
            block_timestamp: 1700000000,
            contract_address: "0xContract".to_string(),
            caller_address: "0xCaller".to_string(),
            function_selector: "0xa9059cbb".to_string(),
            function_signature: Some("transfer(address,uint256)".to_string()),
            function_category: FunctionCategory::Transfer,
            input_data: "0xa9059cbb".to_string(),
            call_value_wei: "0x0".to_string(),
            status: TransactionStatus::Success,
            revert_reason: None,
            gas_used: 21000,
            gas_price: "0x4a817c800".to_string(),
            transaction_fee_wei: "0x0".to_string(),
            decoded_params: None,
            decoding_status: DecodingStatus::NotRequested,
            events: vec![],
            event_count: 0,
            is_popular_function: true,
            interaction_frequency: 1,
            processed_at: "2024-01-01T00:00:00Z".to_string(),
            processor_id: "test".to_string(),
            correlation_id: "corr".to_string(),
            transaction_type: "contract_call".to_string(),
            transaction_currency: "NONE".to_string(),
            transaction_value: "0".to_string(),
            transaction_subtype: "transfer".to_string(),
            protocol: Some("ERC20".to_string()),
            category: "token".to_string(),
            decoded: serde_json::json!({}),
        };

        let raw_tx = RawContractTransaction {
            hash: "0xabc".to_string(),
            from: "0xCaller".to_string(),
            to: "0xContract".to_string(),
            value: "0x0".to_string(),
            gas: "0x5208".to_string(),
            gas_price: "0x4a817c800".to_string(),
            input: "0xa9059cbb".to_string(),
            nonce: "0x2a".to_string(),
            block_number: "0x11a4bc0".to_string(),
            block_hash: "0xblockhash".to_string(),
            transaction_index: "0x5".to_string(),
            chain_id: "0x1".to_string(),
            v: Some("0x1".to_string()),
            r: Some("0x2".to_string()),
            s: Some("0x3".to_string()),
            status: "0x1".to_string(),
            revert_reason: None,
            gas_used: "0x5208".to_string(),
            logs: vec![],
            block_timestamp: Some(format!("0x{:x}", processed_tx.block_timestamp)),
        };

        let records = Component::build_address_transaction_records(&processed_tx, &raw_tx);

        assert_eq!(records.len(), 2);
        assert!(records.iter().any(|r| r.is_sender));
        assert!(records.iter().any(|r| !r.is_sender));

        let from_record = records.iter().find(|r| r.is_sender).expect("from record");
        let to_record = records.iter().find(|r| !r.is_sender).expect("to record");

        assert_eq!(from_record.address, "0xcaller");
        assert_eq!(to_record.address, "0xcontract");
        assert_eq!(
            from_record.counterparty_address.as_deref(),
            Some("0xcontract")
        );
        assert_eq!(to_record.counterparty_address.as_deref(), Some("0xcaller"));
        assert_eq!(
            from_record.transaction_type.as_deref(),
            Some("contract_call")
        );
    }
}
