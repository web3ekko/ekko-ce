//! # Ethereum Process Transactions Actor
//!
//! WasmCloud actor that processes raw Ethereum transactions and applies business logic,
//! validation, and enrichment. This actor receives individual transactions from the
//! eth_raw_transactions actor and categorizes them by type for downstream processing.
//!
//! ## Architecture
//! - **wasmCloud Actor**: Uses proper WIT interfaces
//! - **WASM Component**: Runs in wasmCloud runtime
//! - **Messaging**: Subscribes to transactions.raw.evm and publishes categorized transactions
//! - **Processing**: Pure Rust logic for transaction analysis and categorization
//!
//! ## Subscription Pattern
//! - Subscribes to: `transactions.raw.evm` (individual raw transactions)
//! - Publishes to: Type-specific subjects:
//!   - `transfer-transactions.{network}.{subnet}.{vm_type}.raw` for transfers
//!   - `contract-creations.{network}.{subnet}.{vm_type}.raw` for contract creation
//!   - `contract-transactions.{network}.{subnet}.{vm_type}.raw` for function calls

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// Generate WIT bindings for the processor world
wit_bindgen::generate!({ generate_all });

use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use wasmcloud::messaging::{consumer, types};

/// Raw transaction from eth_raw_transactions actor
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransaction {
    // Network context
    pub network: String,
    pub subnet: String,
    pub vm_type: String,

    // Transaction data
    pub transaction_hash: String,
    pub block_number: u64,
    pub block_hash: String,
    pub block_timestamp: u64,
    pub transaction_index: u32,
    pub from_address: String,
    pub to_address: Option<String>,
    pub value: String,
    pub gas_limit: u64,
    pub gas_price: String,
    pub input_data: String,
    pub nonce: u64,
    pub chain_id: String,

    // EVM-specific data
    pub max_fee_per_gas: Option<String>,
    pub max_priority_fee_per_gas: Option<String>,
    pub transaction_type: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,

    // Processing metadata
    pub processed_at: String,
    pub processor_id: String,
}

/// Raw transfer transaction in standard Ethereum format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransferTransaction {
    pub hash: String,
    pub from: String,
    pub to: String,
    pub value: String,
    pub gas: String,
    pub gas_price: String,
    pub input: String,
    pub nonce: String,
    pub block_number: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub block_timestamp: Option<String>,
    pub block_hash: String,
    pub transaction_index: String,
    pub chain_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,
}

/// Raw contract creation transaction in standard Ethereum format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawContractCreation {
    pub hash: String,
    pub from: String,
    #[serde(default)]
    pub to: Option<String>,
    pub value: String,
    pub gas: String,
    pub gas_price: String,
    pub input: String,
    pub nonce: String,
    pub block_number: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub block_timestamp: Option<String>,
    pub block_hash: String,
    pub transaction_index: String,
    pub chain_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub contract_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,
}

/// Raw contract transaction in standard Ethereum format with receipt data
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
    pub block_hash: String,
    pub transaction_index: String,
    pub chain_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub revert_reason: Option<String>,
    pub gas_used: String,
    pub logs: Vec<RawEventLog>,
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

/// Processed transaction with Ethereum-specific enrichment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessedTransaction {
    // Inherited from raw transaction
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub transaction_hash: String,
    pub block_number: u64,
    pub transaction_index: u32,
    pub from_address: String,
    pub to_address: Option<String>,
    pub value: String,
    pub gas_limit: u64,
    pub gas_price: String,
    pub input_data: String,
    pub nonce: u64,

    // EIP-1559 fields
    pub max_fee_per_gas: Option<String>,
    pub max_priority_fee_per_gas: Option<String>,
    pub transaction_type: Option<u8>,

    // Processing results
    pub transaction_category: TransactionType,
    pub method_signature: Option<String>,
    pub gas_analysis: GasAnalysis,

    // Flexible details map for scenario-specific data
    pub details: HashMap<String, serde_json::Value>,

    // Processing metadata
    pub processed_at: String,
    pub processor_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransactionType {
    Transfer,         // Simple ETH transfer (Scenario 1)
    ContractCreation, // Contract deployment (Scenario 2)
    FunctionCall,     // Smart contract interaction (Scenario 3)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GasAnalysis {
    pub price_gwei: f64,
    pub category: GasPriceCategory,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum GasPriceCategory {
    Low,
    Standard,
    High,
    Extreme,
}

/// Main ETH Process Transactions Actor
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    /// Handle incoming NATS messages containing raw transactions
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        eprintln!("[ETH-PROCESS] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        eprintln!(
            "[ETH-PROCESS] 📨 Received message on subject: {}",
            msg.subject
        );

        // Only process transactions.raw.evm messages
        if msg.subject != "transactions.raw.evm" {
            eprintln!("[ETH-PROCESS] ⏭️  Skipping - not a raw EVM transaction message");
            return Ok(());
        }

        // Parse the raw transaction from the message
        let raw_tx: RawTransaction = serde_json::from_slice(&msg.body).map_err(|e| {
            eprintln!("[ETH-PROCESS] ❌ Failed to parse raw transaction: {}", e);
            format!("Failed to parse raw transaction: {}", e)
        })?;

        eprintln!(
            "[ETH-PROCESS] 🔍 Processing transaction {}",
            &raw_tx.transaction_hash[..std::cmp::min(18, raw_tx.transaction_hash.len())]
        );
        eprintln!(
            "[ETH-PROCESS]    Block: #{}, Index: {}",
            raw_tx.block_number, raw_tx.transaction_index
        );
        eprintln!("[ETH-PROCESS]    From: {}", raw_tx.from_address);
        eprintln!(
            "[ETH-PROCESS]    To: {}",
            raw_tx
                .to_address
                .as_deref()
                .unwrap_or("(contract creation)")
        );

        // Process the transaction and publish results
        Self::process_and_publish_transaction(raw_tx)?;

        Ok(())
    }
}

impl Component {
    /// Process a raw transaction and publish it to appropriate subjects
    fn process_and_publish_transaction(raw_tx: RawTransaction) -> Result<(), String> {
        // Determine transaction type
        let transaction_category = Self::detect_transaction_type(&raw_tx);

        // Analyze gas price
        let gas_analysis = Self::analyze_gas_price(&raw_tx.gas_price);

        // Extract method signature for function calls
        let method_signature = if matches!(transaction_category, TransactionType::FunctionCall) {
            Self::extract_method_signature(&raw_tx.input_data)
        } else {
            None
        };

        // Create details based on transaction type
        let details = match transaction_category {
            TransactionType::Transfer => Self::create_transfer_details(&raw_tx),
            TransactionType::ContractCreation => Self::create_contract_creation_details(&raw_tx),
            TransactionType::FunctionCall => Self::create_function_call_details(&raw_tx),
        };

        // Create processed transaction
        let processed_tx = ProcessedTransaction {
            network: raw_tx.network.clone(),
            subnet: raw_tx.subnet.clone(),
            vm_type: raw_tx.vm_type.clone(),
            transaction_hash: raw_tx.transaction_hash.clone(),
            block_number: raw_tx.block_number,
            transaction_index: raw_tx.transaction_index,
            from_address: raw_tx.from_address.clone(),
            to_address: raw_tx.to_address.clone(),
            value: raw_tx.value.clone(),
            gas_limit: raw_tx.gas_limit,
            gas_price: raw_tx.gas_price.clone(),
            input_data: raw_tx.input_data.clone(),
            nonce: raw_tx.nonce,
            max_fee_per_gas: raw_tx.max_fee_per_gas.clone(),
            max_priority_fee_per_gas: raw_tx.max_priority_fee_per_gas.clone(),
            transaction_type: raw_tx.transaction_type,
            transaction_category,
            method_signature,
            gas_analysis,
            details,
            processed_at: chrono::Utc::now().to_rfc3339(),
            processor_id: "eth-process-transactions-actor".to_string(),
        };

        // Publish to appropriate subject based on transaction type
        Self::publish_processed_transaction(&processed_tx, &raw_tx)?;

        Ok(())
    }

    /// Detect transaction type based on raw transaction data
    fn detect_transaction_type(raw_tx: &RawTransaction) -> TransactionType {
        match (&raw_tx.to_address, &raw_tx.input_data) {
            // Contract Creation: no to_address, has bytecode
            (None, input) if !input.is_empty() && input != "0x" => {
                TransactionType::ContractCreation
            }

            // Transfer: has to_address, no input data or empty input
            (Some(_), input) if input.is_empty() || input == "0x" => TransactionType::Transfer,

            // Function Call: has to_address and input data
            (Some(_), input) if !input.is_empty() && input != "0x" => TransactionType::FunctionCall,

            // Fallback to Transfer for edge cases
            _ => TransactionType::Transfer,
        }
    }

    /// Analyze gas price and categorize it
    fn analyze_gas_price(gas_price_hex: &str) -> GasAnalysis {
        let gas_price_wei = Self::parse_hex_u64(gas_price_hex);
        let price_gwei = gas_price_wei as f64 / 1_000_000_000.0;

        let category = if price_gwei < 10.0 {
            GasPriceCategory::Low
        } else if price_gwei < 50.0 {
            GasPriceCategory::Standard
        } else if price_gwei < 100.0 {
            GasPriceCategory::High
        } else {
            GasPriceCategory::Extreme
        };

        GasAnalysis {
            price_gwei,
            category,
        }
    }

    /// Extract method signature from input data
    fn extract_method_signature(input_data: &str) -> Option<String> {
        if input_data.len() >= 10 && input_data.starts_with("0x") {
            Some(input_data[0..10].to_string())
        } else {
            None
        }
    }

    /// Parse hexadecimal string to u64
    fn parse_hex_u64(hex_str: &str) -> u64 {
        let cleaned = hex_str.trim_start_matches("0x");
        u64::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Parse hexadecimal string to u128
    fn parse_hex_u128(hex_str: &str) -> u128 {
        let cleaned = hex_str.trim_start_matches("0x");
        u128::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Create details map for transfer transaction (Scenario 1)
    fn create_transfer_details(raw_tx: &RawTransaction) -> HashMap<String, serde_json::Value> {
        let mut details = HashMap::new();

        details.insert(
            "type".to_string(),
            serde_json::Value::String("transfer".to_string()),
        );
        details.insert(
            "amount_wei".to_string(),
            serde_json::Value::String(raw_tx.value.clone()),
        );

        // Convert Wei to ETH
        let wei_value = if raw_tx.value.trim_start_matches("0x").is_empty() {
            0
        } else if raw_tx.value.starts_with("0x") {
            Self::parse_hex_u128(&raw_tx.value)
        } else {
            raw_tx.value.parse::<u128>().unwrap_or(0)
        };
        let eth_value = wei_value as f64 / 1_000_000_000_000_000_000.0;
        details.insert(
            "amount_eth".to_string(),
            serde_json::Value::String(format!("{:.18}", eth_value)),
        );

        if let Some(ref to_addr) = raw_tx.to_address {
            details.insert(
                "recipient".to_string(),
                serde_json::Value::String(to_addr.clone()),
            );
        }

        details
    }

    /// Create details map for contract creation transaction (Scenario 2)
    fn create_contract_creation_details(
        raw_tx: &RawTransaction,
    ) -> HashMap<String, serde_json::Value> {
        let mut details = HashMap::new();

        details.insert(
            "type".to_string(),
            serde_json::Value::String("contract_creation".to_string()),
        );
        details.insert(
            "bytecode_size".to_string(),
            serde_json::Value::Number(serde_json::Number::from(raw_tx.input_data.len())),
        );

        // Extract constructor args if present (after bytecode)
        if raw_tx.input_data.len() > 10 {
            details.insert(
                "constructor_args".to_string(),
                serde_json::Value::String(raw_tx.input_data.clone()),
            );
        }

        // Estimate gas used based on bytecode size (hex string length / 2 for actual bytes)
        let bytecode_bytes = if raw_tx.input_data.starts_with("0x") {
            (raw_tx.input_data.len() - 2) / 2
        } else {
            raw_tx.input_data.len() / 2
        };
        let estimated_gas = std::cmp::max(21000, bytecode_bytes as u64 * 200);
        details.insert(
            "estimated_gas_used".to_string(),
            serde_json::Value::Number(serde_json::Number::from(estimated_gas)),
        );

        details
    }

    /// Create details map for function call transaction (Scenario 3)
    fn create_function_call_details(raw_tx: &RawTransaction) -> HashMap<String, serde_json::Value> {
        let mut details = HashMap::new();

        details.insert(
            "type".to_string(),
            serde_json::Value::String("function_call".to_string()),
        );

        if let Some(ref to_addr) = raw_tx.to_address {
            details.insert(
                "contract_address".to_string(),
                serde_json::Value::String(to_addr.clone()),
            );
        }

        // Extract function signature (first 4 bytes)
        if raw_tx.input_data.len() >= 10 {
            let function_sig = &raw_tx.input_data[0..10];
            details.insert(
                "function_signature".to_string(),
                serde_json::Value::String(function_sig.to_string()),
            );
        }

        details.insert(
            "input_data".to_string(),
            serde_json::Value::String(raw_tx.input_data.clone()),
        );

        details
    }

    /// Publish processed transaction to appropriate subject based on type
    fn publish_processed_transaction(
        processed_tx: &ProcessedTransaction,
        raw_tx: &RawTransaction,
    ) -> Result<(), String> {
        let (subject, type_emoji) = match processed_tx.transaction_category {
            TransactionType::Transfer => (
                format!(
                    "transfer-transactions.{}.{}.{}.raw",
                    raw_tx.network, raw_tx.subnet, raw_tx.vm_type
                ),
                "💸",
            ),
            TransactionType::ContractCreation => (
                format!(
                    "contract-creations.{}.{}.{}.raw",
                    raw_tx.network, raw_tx.subnet, raw_tx.vm_type
                ),
                "📝",
            ),
            TransactionType::FunctionCall => (
                format!(
                    "contract-transactions.{}.{}.{}.raw",
                    raw_tx.network, raw_tx.subnet, raw_tx.vm_type
                ),
                "⚙️",
            ),
        };

        eprintln!(
            "[ETH-PROCESS] {} Categorized as: {:?}",
            type_emoji, processed_tx.transaction_category
        );

        let payload = match processed_tx.transaction_category {
            TransactionType::Transfer => {
                let transfer = Self::build_raw_transfer(raw_tx)?;
                serde_json::to_vec(&transfer).map_err(|e| {
                    eprintln!("[ETH-PROCESS] ❌ Failed to serialize transfer: {}", e);
                    format!("Failed to serialize transfer transaction: {}", e)
                })?
            }
            TransactionType::ContractCreation => {
                let creation = Self::build_raw_contract_creation(raw_tx)?;
                serde_json::to_vec(&creation).map_err(|e| {
                    eprintln!("[ETH-PROCESS] ❌ Failed to serialize creation: {}", e);
                    format!("Failed to serialize contract creation: {}", e)
                })?
            }
            TransactionType::FunctionCall => {
                let contract_call = Self::build_raw_contract_transaction(raw_tx)?;
                serde_json::to_vec(&contract_call).map_err(|e| {
                    eprintln!("[ETH-PROCESS] ❌ Failed to serialize contract call: {}", e);
                    format!("Failed to serialize contract transaction: {}", e)
                })?
            }
        };

        let subjects: Vec<String> = if matches!(
            processed_tx.transaction_category,
            TransactionType::ContractCreation
        ) {
            vec![
                subject.clone(),
                format!(
                    "blockchain.{}.{}.contracts.creation",
                    raw_tx.network, raw_tx.subnet
                ),
            ]
        } else {
            vec![subject.clone()]
        };

        for target in subjects {
            let msg = types::BrokerMessage {
                subject: target.clone(),
                body: payload.clone(),
                reply_to: None,
            };

            let result = consumer::publish(&msg);

            match &result {
                Ok(_) => {
                    eprintln!("[ETH-PROCESS] ✅ Published to: {}", target);
                    eprintln!("[ETH-PROCESS] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                }
                Err(e) => eprintln!("[ETH-PROCESS] ❌ Failed to publish: {:?}", e),
            }

            result.map_err(|e| format!("Failed to publish message: {:?}", e))?;
        }

        Ok(())
    }

    fn build_raw_transfer(raw_tx: &RawTransaction) -> Result<RawTransferTransaction, String> {
        let to_address = raw_tx
            .to_address
            .clone()
            .ok_or_else(|| "Transfer transaction missing to_address".to_string())?;

        Ok(RawTransferTransaction {
            hash: raw_tx.transaction_hash.clone(),
            from: raw_tx.from_address.clone(),
            to: to_address,
            value: Self::normalize_hex_quantity(&raw_tx.value),
            gas: Self::to_hex_u64(raw_tx.gas_limit),
            gas_price: Self::normalize_hex_quantity(&raw_tx.gas_price),
            input: raw_tx.input_data.clone(),
            nonce: Self::to_hex_u64(raw_tx.nonce),
            block_number: Self::to_hex_u64(raw_tx.block_number),
            block_timestamp: Some(Self::to_hex_u64(raw_tx.block_timestamp)),
            block_hash: raw_tx.block_hash.clone(),
            transaction_index: Self::to_hex_u32(raw_tx.transaction_index),
            chain_id: Self::resolve_chain_id_hex(raw_tx),
            v: raw_tx.v.clone(),
            r: raw_tx.r.clone(),
            s: raw_tx.s.clone(),
        })
    }

    fn build_raw_contract_creation(raw_tx: &RawTransaction) -> Result<RawContractCreation, String> {
        Ok(RawContractCreation {
            hash: raw_tx.transaction_hash.clone(),
            from: raw_tx.from_address.clone(),
            to: None,
            value: Self::normalize_hex_quantity(&raw_tx.value),
            gas: Self::to_hex_u64(raw_tx.gas_limit),
            gas_price: Self::normalize_hex_quantity(&raw_tx.gas_price),
            input: raw_tx.input_data.clone(),
            nonce: Self::to_hex_u64(raw_tx.nonce),
            block_number: Self::to_hex_u64(raw_tx.block_number),
            block_timestamp: Some(Self::to_hex_u64(raw_tx.block_timestamp)),
            block_hash: raw_tx.block_hash.clone(),
            transaction_index: Self::to_hex_u32(raw_tx.transaction_index),
            chain_id: Self::resolve_chain_id_hex(raw_tx),
            contract_address: None,
            v: raw_tx.v.clone(),
            r: raw_tx.r.clone(),
            s: raw_tx.s.clone(),
        })
    }

    fn build_raw_contract_transaction(
        raw_tx: &RawTransaction,
    ) -> Result<RawContractTransaction, String> {
        let to_address = raw_tx
            .to_address
            .clone()
            .ok_or_else(|| "Contract transaction missing to_address".to_string())?;

        Ok(RawContractTransaction {
            hash: raw_tx.transaction_hash.clone(),
            from: raw_tx.from_address.clone(),
            to: to_address,
            value: Self::normalize_hex_quantity(&raw_tx.value),
            gas: Self::to_hex_u64(raw_tx.gas_limit),
            gas_price: Self::normalize_hex_quantity(&raw_tx.gas_price),
            input: raw_tx.input_data.clone(),
            nonce: Self::to_hex_u64(raw_tx.nonce),
            block_number: Self::to_hex_u64(raw_tx.block_number),
            block_hash: raw_tx.block_hash.clone(),
            transaction_index: Self::to_hex_u32(raw_tx.transaction_index),
            chain_id: Self::resolve_chain_id_hex(raw_tx),
            v: raw_tx.v.clone(),
            r: raw_tx.r.clone(),
            s: raw_tx.s.clone(),
            status: "0x1".to_string(),
            revert_reason: None,
            gas_used: "0x0".to_string(),
            logs: Vec::new(),
            block_timestamp: Some(Self::to_hex_u64(raw_tx.block_timestamp)),
        })
    }

    fn to_hex_u64(value: u64) -> String {
        format!("0x{:x}", value)
    }

    fn to_hex_u32(value: u32) -> String {
        format!("0x{:x}", value)
    }

    fn normalize_hex_quantity(value: &str) -> String {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            return "0x0".to_string();
        }
        if trimmed.starts_with("0x") || trimmed.starts_with("0X") {
            return format!(
                "0x{}",
                trimmed
                    .trim_start_matches("0x")
                    .trim_start_matches("0X")
                    .to_lowercase()
            );
        }
        match trimmed.parse::<u128>() {
            Ok(parsed) => format!("0x{:x}", parsed),
            Err(_) => "0x0".to_string(),
        }
    }

    fn resolve_chain_id_hex(raw_tx: &RawTransaction) -> String {
        let normalized = Self::normalize_hex_quantity(&raw_tx.chain_id);
        if normalized != "0x0" {
            return normalized;
        }

        match (raw_tx.network.as_str(), raw_tx.subnet.as_str()) {
            ("ethereum", "mainnet") => "0x1",
            ("ethereum", "sepolia") => "0xaa36a7",
            ("ethereum", "goerli") => "0x5",
            ("polygon", "mainnet") => "0x89",
            ("polygon", "mumbai") => "0x13881",
            ("avalanche", "mainnet") => "0xa86a",
            ("avalanche", "fuji") => "0xa869",
            ("binance", "mainnet") => "0x38",
            ("binance", "testnet") => "0x61",
            ("arbitrum", "mainnet") => "0xa4b1",
            ("optimism", "mainnet") => "0xa",
            _ => "0x0",
        }
        .to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_raw_transaction(tx_type: &str) -> RawTransaction {
        match tx_type {
            "transfer" => RawTransaction {
                network: "ethereum".to_string(),
                subnet: "mainnet".to_string(),
                vm_type: "evm".to_string(),
                transaction_hash: "0x1234567890abcdef".to_string(),
                block_number: 18500000,
                block_hash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890".to_string(),
                block_timestamp: 1699000000,
                transaction_index: 42,
                from_address: "0xfrom123".to_string(),
                to_address: Some("0xto456".to_string()),
                value: "0xde0b6b3a7640000".to_string(), // 1 ETH
                gas_limit: 21000,
                gas_price: "0x4a817c800".to_string(), // 20 Gwei
                input_data: "0x".to_string(),
                nonce: 1,
                chain_id: "0x1".to_string(),
                max_fee_per_gas: None,
                max_priority_fee_per_gas: None,
                transaction_type: None,
                v: Some("0x1b".to_string()),
                r: Some("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string()),
                s: Some("0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321".to_string()),
                processed_at: "2024-01-15T10:30:00Z".to_string(),
                processor_id: "test".to_string(),
            },
            "contract_creation" => RawTransaction {
                network: "ethereum".to_string(),
                subnet: "mainnet".to_string(),
                vm_type: "evm".to_string(),
                transaction_hash: "0xabcdef1234567890".to_string(),
                block_number: 18500001,
                block_hash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890".to_string(),
                block_timestamp: 1699000001,
                transaction_index: 43,
                from_address: "0xfrom789".to_string(),
                to_address: None,
                value: "0x0".to_string(),
                gas_limit: 2100000,
                gas_price: "0x5d21dba00".to_string(), // 25 Gwei
                input_data: "0x608060405234801561001057600080fd5b50608060405234801561001057600080fd5b50608060405234801561001057600080fd5b50608060405234801561001057600080fd5b50608060405234801561001057600080fd5b50608060405234801561001057600080fd5b50".to_string(),
                nonce: 2,
                chain_id: "0x1".to_string(),
                max_fee_per_gas: None,
                max_priority_fee_per_gas: None,
                transaction_type: None,
                v: Some("0x1b".to_string()),
                r: Some("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string()),
                s: Some("0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321".to_string()),
                processed_at: "2024-01-15T10:30:01Z".to_string(),
                processor_id: "test".to_string(),
            },
            "function_call" => RawTransaction {
                network: "ethereum".to_string(),
                subnet: "mainnet".to_string(),
                vm_type: "evm".to_string(),
                transaction_hash: "0xfedcba0987654321".to_string(),
                block_number: 18500002,
                block_hash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890".to_string(),
                block_timestamp: 1699000002,
                transaction_index: 44,
                from_address: "0xfrom999".to_string(),
                to_address: Some("0xcontract123".to_string()),
                value: "0x0".to_string(),
                gas_limit: 100000,
                gas_price: "0x6fc23ac00".to_string(), // 30 Gwei
                input_data: "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b6000000000000000000000000000000000000000000000000de0b6b3a7640000".to_string(),
                nonce: 3,
                chain_id: "0x1".to_string(),
                max_fee_per_gas: None,
                max_priority_fee_per_gas: None,
                transaction_type: None,
                v: Some("0x1b".to_string()),
                r: Some("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string()),
                s: Some("0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321".to_string()),
                processed_at: "2024-01-15T10:30:02Z".to_string(),
                processor_id: "test".to_string(),
            },
            _ => panic!("Unknown transaction type"),
        }
    }

    #[test]
    fn test_detect_transaction_type() {
        let transfer_tx = create_test_raw_transaction("transfer");
        assert!(matches!(
            Component::detect_transaction_type(&transfer_tx),
            TransactionType::Transfer
        ));

        let creation_tx = create_test_raw_transaction("contract_creation");
        assert!(matches!(
            Component::detect_transaction_type(&creation_tx),
            TransactionType::ContractCreation
        ));

        let function_tx = create_test_raw_transaction("function_call");
        assert!(matches!(
            Component::detect_transaction_type(&function_tx),
            TransactionType::FunctionCall
        ));
    }

    #[test]
    fn test_create_transfer_details() {
        let raw_tx = create_test_raw_transaction("transfer");
        let details = Component::create_transfer_details(&raw_tx);

        assert_eq!(
            details.get("type").unwrap(),
            &serde_json::Value::String("transfer".to_string())
        );
        assert_eq!(
            details.get("amount_wei").unwrap(),
            &serde_json::Value::String("0xde0b6b3a7640000".to_string())
        );
        assert_eq!(
            details.get("recipient").unwrap(),
            &serde_json::Value::String("0xto456".to_string())
        );

        // Check ETH conversion
        let amount_eth = details.get("amount_eth").unwrap().as_str().unwrap();
        assert!(amount_eth.starts_with("1."));
    }

    #[test]
    fn test_create_contract_creation_details() {
        let raw_tx = create_test_raw_transaction("contract_creation");
        let details = Component::create_contract_creation_details(&raw_tx);

        assert_eq!(
            details.get("type").unwrap(),
            &serde_json::Value::String("contract_creation".to_string())
        );
        assert!(details.get("bytecode_size").unwrap().as_u64().unwrap() > 0);
        assert!(details.get("estimated_gas_used").unwrap().as_u64().unwrap() > 21000);
    }

    #[test]
    fn test_create_function_call_details() {
        let raw_tx = create_test_raw_transaction("function_call");
        let details = Component::create_function_call_details(&raw_tx);

        assert_eq!(
            details.get("type").unwrap(),
            &serde_json::Value::String("function_call".to_string())
        );
        assert_eq!(
            details.get("contract_address").unwrap(),
            &serde_json::Value::String("0xcontract123".to_string())
        );
        assert_eq!(
            details.get("function_signature").unwrap(),
            &serde_json::Value::String("0xa9059cbb".to_string())
        );
    }

    #[test]
    fn test_analyze_gas_price() {
        let test_cases = vec![
            ("0x12a05f200", GasPriceCategory::Low),      // 5 Gwei in hex
            ("0x4a817c800", GasPriceCategory::Standard), // 20 Gwei in hex
            ("0x1176592e00", GasPriceCategory::High),    // 75 Gwei in hex
            ("0x22ecb25c00", GasPriceCategory::Extreme), // 150 Gwei in hex
        ];

        for (gas_price, expected_category) in test_cases {
            let analysis = Component::analyze_gas_price(gas_price);
            match expected_category {
                GasPriceCategory::Low => {
                    assert!(matches!(analysis.category, GasPriceCategory::Low))
                }
                GasPriceCategory::Standard => {
                    assert!(matches!(analysis.category, GasPriceCategory::Standard))
                }
                GasPriceCategory::High => {
                    assert!(matches!(analysis.category, GasPriceCategory::High))
                }
                GasPriceCategory::Extreme => {
                    assert!(matches!(analysis.category, GasPriceCategory::Extreme))
                }
            }
        }
    }

    #[test]
    fn test_extract_method_signature() {
        let input_data =
            "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b6";
        let signature = Component::extract_method_signature(input_data);
        assert_eq!(signature, Some("0xa9059cbb".to_string()));

        // Test with empty input
        let empty_signature = Component::extract_method_signature("0x");
        assert_eq!(empty_signature, None);

        // Test with short input
        let short_signature = Component::extract_method_signature("0x1234");
        assert_eq!(short_signature, None);
    }

    #[test]
    fn test_parse_hex_u64() {
        assert_eq!(Component::parse_hex_u64("0x1234"), 0x1234);
        assert_eq!(Component::parse_hex_u64("1234"), 0x1234);
        assert_eq!(Component::parse_hex_u64("0x0"), 0);
        assert_eq!(Component::parse_hex_u64("invalid"), 0); // Should handle invalid gracefully
    }

    #[test]
    fn test_build_raw_transfer_payload() {
        let raw_tx = create_test_raw_transaction("transfer");
        let payload = Component::build_raw_transfer(&raw_tx).expect("build transfer");

        assert_eq!(payload.chain_id, "0x1");
        assert_eq!(payload.block_number, "0x11a49a0");
        assert_eq!(payload.block_timestamp.as_deref(), Some("0x6544aec0"));
        assert_eq!(payload.transaction_index, "0x2a");
        assert_eq!(payload.value, "0xde0b6b3a7640000");
    }

    #[test]
    fn test_resolve_chain_id_hex_fallback() {
        let mut raw_tx = create_test_raw_transaction("transfer");
        raw_tx.chain_id = "0x0".to_string();
        raw_tx.network = "polygon".to_string();
        raw_tx.subnet = "mainnet".to_string();

        assert_eq!(Component::resolve_chain_id_hex(&raw_tx), "0x89");
    }
}
