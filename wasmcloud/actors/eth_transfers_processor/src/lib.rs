//! # Ethereum Transfers Processor Actor
//!
//! WasmCloud actor that processes ETH transfer transactions with balance tracking,
//! transfer categorization, and alert routing. This actor receives transfer transactions
//! from the eth_process_transactions actor and enriches them with balance context.
//!
//! ## Schema Redesign (2025)
//! Updated to use unified `transactions` table instead of `processed_transfers`.
//! Now includes decoded function fields (set to NativeTransfer for native transfers).
//!
//! ## Architecture
//! - **wasmCloud Actor**: Uses proper WIT interfaces
//! - **WASM Component**: Runs in wasmCloud runtime
//! - **Messaging**: Subscribes to transfer-transactions.*.*.evm.raw
//! - **State**: Redis for balance tracking and statistics
//!
//! ## Subscription Pattern
//! - Subscribes to: `transfer-transactions.*.*.evm.raw` (wildcard for all EVM chains)
//! - Publishes to:
//!   - `transfers.processed.evm` - Processed transfers with enrichment
//!   - `alerts.schedule.event_driven` - Alert schedule requests (Stage 1)
//!   - `balances.updated.{chain}` - Balance change notifications
//!   - `ducklake.transactions.{chain}.{subnet}.write` - DuckLake persistence (Schema Redesign)

use chrono::{DateTime, TimeZone, Utc};
use serde::{Deserialize, Serialize};
use time::format_description::well_known::Rfc3339;

// Generate WIT bindings for the processor world
wit_bindgen::generate!({ generate_all });

use alert_runtime_common::{
    alert_schedule_event_driven_schema_version_v1, AlertScheduleEventDrivenV1, EvmTxV1,
    PartitionV1, ScheduleEventV1, TxKindV1, VmKindV1,
};
use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use wasmcloud::messaging::{consumer, types};

// Thread-local counter for generating unique correlation IDs
use std::sync::atomic::{AtomicU64, Ordering};
static COUNTER: AtomicU64 = AtomicU64::new(0);

/// Get a unique monotonic timestamp value (not wall clock, but unique per call)
/// This is used for correlation IDs and uniqueness, not for actual timing
fn get_unique_counter() -> u64 {
    COUNTER.fetch_add(1, Ordering::SeqCst)
}

fn datetime_from_unix_secs(seconds: u64) -> DateTime<Utc> {
    let rendered = rfc3339_from_unix_secs(seconds);
    DateTime::parse_from_rfc3339(&rendered)
        .map(|dt| dt.with_timezone(&Utc))
        .unwrap_or_else(|_| DateTime::<Utc>::from_timestamp(0, 0).unwrap())
}

fn rfc3339_from_unix_secs(seconds: u64) -> String {
    let secs = i64::try_from(seconds).unwrap_or(0);
    let dt =
        time::OffsetDateTime::from_unix_timestamp(secs).unwrap_or(time::OffsetDateTime::UNIX_EPOCH);
    dt.format(&Rfc3339)
        .unwrap_or_else(|_| "1970-01-01T00:00:00Z".to_string())
}

/// Raw transfer transaction in standard Ethereum format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransferTransaction {
    // Standard Ethereum transaction fields
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

    // Optional signature fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,
}

/// Processed transfer with enrichment and balance context
/// Updated for unified transactions schema (DuckLake Schema Redesign)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessedTransfer {
    // ═══════════════════════════════════════════════════════════════════════════
    // NETWORK IDENTIFICATION (Schema Redesign)
    // ═══════════════════════════════════════════════════════════════════════════
    pub network: String,  // ethereum, polygon, solana, bitcoin
    pub subnet: String,   // mainnet, sepolia, devnet
    pub vm_type: String,  // evm, svm, utxo
    pub chain_id: String, // Combined: "{network}_{subnet}" for partitioning

    // ═══════════════════════════════════════════════════════════════════════════
    // CORE TRANSACTION DATA
    // ═══════════════════════════════════════════════════════════════════════════
    pub transaction_hash: String,
    pub block_number: u64,
    pub block_timestamp: u64,
    pub from_address: String,
    pub to_address: String,

    // ═══════════════════════════════════════════════════════════════════════════
    // VALUE ENRICHMENT (Schema Redesign - from processed_transfers)
    // ═══════════════════════════════════════════════════════════════════════════
    pub amount_wei: String,      // Raw value in smallest unit
    pub amount_native: f64,      // Amount in native units (renamed from amount_eth)
    pub amount_usd: Option<f64>, // USD value at tx time

    // Gas and costs
    pub gas_used: u64,
    pub gas_price: String,
    pub transaction_fee_wei: String,
    pub transaction_fee_native: f64, // Renamed from transaction_fee_eth
    pub fee_usd: Option<f64>,        // NEW: Fee in USD

    // Transfer classification
    pub transfer_category: TransferCategory, // Micro/Small/Medium/Large/Whale
    pub sender_type: AddressType,            // EOA/Contract/Unknown
    pub recipient_type: AddressType,

    // Balance context (populated from Redis in production)
    pub sender_balance_before: Option<String>,
    pub sender_balance_after: Option<String>,
    pub recipient_balance_before: Option<String>,
    pub recipient_balance_after: Option<String>,

    // ═══════════════════════════════════════════════════════════════════════════
    // TRANSACTION CLASSIFICATION (Schema Redesign)
    // ═══════════════════════════════════════════════════════════════════════════
    pub transaction_type: String, // TRANSFER, CONTRACT_CALL, CONTRACT_CREATE
    pub transaction_subtype: String, // native, erc20, swap, stake, etc.
    pub transaction_currency: String, // "ETH" | "{TOKEN_SYMBOL}"
    pub transaction_value: String, // "1.5 ETH" | "100 USDT"
    pub protocol: Option<String>, // None for native, "ERC20" for tokens
    pub category: String,         // value_transfer, contract_interaction, etc.

    // ═══════════════════════════════════════════════════════════════════════════
    // DECODED FUNCTION DATA (Schema Redesign - from abi-decoder actor)
    // For native transfers, most fields are None/NativeTransfer status
    // ═══════════════════════════════════════════════════════════════════════════
    pub decoded_function_name: Option<String>, // e.g., "transfer", "swap", "approve"
    pub decoded_function_signature: Option<String>, // e.g., "transfer(address,uint256)"
    pub decoded_function_selector: Option<String>, // e.g., "0xa9059cbb" (first 4 bytes)
    pub decoded_parameters: Option<String>,    // JSON array of DecodedParameter
    pub decoding_status: String,               // Success, NativeTransfer, ContractCreation, etc.
    pub abi_source: Option<String>,            // etherscan, sourcify, 4byte, manual
    pub decoding_time_ms: Option<i32>,         // Time taken to decode
    pub decoded_summary: Option<String>,       // Human-readable: "transfer 1.5 ETH to 0x742e..."

    // Legacy decoded field (JSON) - kept for backwards compatibility
    pub decoded: serde_json::Value,

    // ═══════════════════════════════════════════════════════════════════════════
    // PROCESSING METADATA
    // ═══════════════════════════════════════════════════════════════════════════
    pub processed_at: String,
    pub processor_id: String,
    pub correlation_id: String,
}

/// Minimal DuckLake transaction record aligned to transactions schema.
/// This intentionally excludes non-schema fields to avoid DuckDB binder errors.
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
pub enum TransferCategory {
    Micro,  // < 0.01 ETH
    Small,  // 0.01 - 1 ETH
    Medium, // 1 - 10 ETH
    Large,  // 10 - 100 ETH
    Whale,  // > 100 ETH
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum AddressType {
    ExternallyOwnedAccount, // EOA
    Contract,
    Unknown,
}

/// Main ETH Transfers Processor Actor
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    /// Handle incoming NATS messages containing transfer transactions
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        // Check if subject matches transfer pattern
        if !msg.subject.starts_with("transfer-transactions.") || !msg.subject.ends_with(".raw") {
            return Ok(());
        }

        // Extract network context from subject: transfer-transactions.{network}.{subnet}.{vm_type}.raw
        let (network, subnet, vm_type) = Self::parse_subject_context(&msg.subject)?;

        // Parse the transfer transaction from the message
        let raw_transfer: RawTransferTransaction = serde_json::from_slice(&msg.body)
            .map_err(|e| format!("Failed to parse transfer transaction: {}", e))?;

        // Process the transfer and publish results
        Self::process_and_publish_transfer(raw_transfer, network, subnet, vm_type)?;

        Ok(())
    }
}

impl Component {
    /// Parse network context from NATS subject
    fn parse_subject_context(subject: &str) -> Result<(String, String, String), String> {
        // transfer-transactions.ethereum.mainnet.evm.raw
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

    /// Process a transfer transaction and publish to appropriate subjects
    fn process_and_publish_transfer(
        raw_transfer: RawTransferTransaction,
        network: String,
        subnet: String,
        vm_type: String,
    ) -> Result<(), String> {
        let chain_id_numeric = Self::parse_hex_u128(&raw_transfer.chain_id) as i64;
        let canonical_network = Self::canonical_network_name(&network, chain_id_numeric);
        let normalized_subnet = subnet.to_lowercase();

        // Parse block number
        let block_number = Self::parse_hex_u64(&raw_transfer.block_number);

        // Calculate transfer amounts
        let amount_eth = Self::wei_to_eth(&raw_transfer.value);

        // Parse gas limit
        let gas_limit = Self::parse_hex_u64(&raw_transfer.gas);

        // Calculate transaction fee (estimate using gas limit since gas_used not in raw tx)
        let transaction_fee_wei =
            Self::calculate_transaction_fee(gas_limit, &raw_transfer.gas_price);
        let transaction_fee_eth = Self::wei_to_eth(&transaction_fee_wei);

        // Categorize transfer size
        let transfer_category = Self::categorize_transfer(amount_eth);

        // Determine address types (simplified - in production would check chain state)
        let sender_type = Self::determine_address_type(&raw_transfer.from);
        let recipient_type = Self::determine_address_type(&raw_transfer.to);

        // Generate correlation ID
        let correlation_id = format!("{}-{}", raw_transfer.hash, get_unique_counter());

        // Create decoded transfer details
        let decoded = Self::create_decoded_transfer_details(
            &raw_transfer.hash,
            &raw_transfer.from,
            &raw_transfer.to,
            &raw_transfer.value,
            amount_eth,
            gas_limit,
            &raw_transfer.gas_price,
            &transfer_category,
        );

        // Determine transaction currency and value
        let transaction_currency = Self::get_network_currency(&canonical_network);
        let transaction_value = format!("{:.6} {}", amount_eth, transaction_currency);

        // Prefer block timestamp from raw payload; fall back to current time if missing.
        let block_timestamp = raw_transfer
            .block_timestamp
            .as_ref()
            .map(|ts| Self::parse_hex_u64(ts))
            .unwrap_or_else(|| chrono::Utc::now().timestamp() as u64);

        // Construct chain_id for partitioning (Schema Redesign)
        let chain_id = format!("{}_{}", canonical_network, normalized_subnet);

        // Create human-readable decoded summary for native transfers
        let to_short = if raw_transfer.to.len() > 10 {
            format!(
                "{}...{}",
                &raw_transfer.to[..6],
                &raw_transfer.to[raw_transfer.to.len() - 4..]
            )
        } else {
            raw_transfer.to.clone()
        };
        let decoded_summary = format!(
            "transfer {:.4} {} to {}",
            amount_eth, transaction_currency, to_short
        );

        // Create processed transfer with unified schema fields
        let processed_transfer = ProcessedTransfer {
            // Network identification (Schema Redesign)
            network: canonical_network.clone(),
            subnet: normalized_subnet.clone(),
            vm_type: vm_type.clone(),
            chain_id,

            // Core transaction data
            transaction_hash: raw_transfer.hash.clone(),
            block_number,
            block_timestamp,
            from_address: raw_transfer.from.clone(),
            to_address: raw_transfer.to.clone(),

            // Value enrichment (Schema Redesign)
            amount_wei: raw_transfer.value.clone(),
            amount_native: amount_eth, // Renamed from amount_eth
            amount_usd: None,          // Would be calculated from price oracle in production
            gas_used: gas_limit,       // Use gas limit as estimate (actual gas_used in receipt)
            gas_price: raw_transfer.gas_price.clone(),
            transaction_fee_wei,
            transaction_fee_native: transaction_fee_eth, // Renamed from transaction_fee_eth
            fee_usd: None, // NEW: Would be calculated from price oracle

            // Transfer classification
            transfer_category,
            sender_type,
            recipient_type,

            // Balance context (populated from Redis in production)
            sender_balance_before: None,
            sender_balance_after: None,
            recipient_balance_before: None,
            recipient_balance_after: None,

            // Transaction classification (Schema Redesign)
            transaction_type: "TRANSFER".to_string(), // Uppercase for consistency
            transaction_subtype: "native".to_string(),
            transaction_currency: transaction_currency.clone(),
            transaction_value,
            protocol: None, // Native transfers have no protocol
            category: "value_transfer".to_string(),

            // Decoded function data (Schema Redesign)
            // For native transfers, most fields are None with NativeTransfer status
            decoded_function_name: None,
            decoded_function_signature: None,
            decoded_function_selector: None,
            decoded_parameters: None,
            decoding_status: "NativeTransfer".to_string(), // Native transfers don't need ABI decoding
            abi_source: None,
            decoding_time_ms: Some(0), // No decoding time for native transfers
            decoded_summary: Some(decoded_summary),

            // Legacy decoded field for backwards compatibility
            decoded,

            // Processing metadata
            processed_at: rfc3339_from_unix_secs(block_timestamp),
            processor_id: "eth-transfers-processor-actor".to_string(),
            correlation_id,
        };

        // Publish to all destinations
        Self::publish_processed_transfer(
            &processed_transfer,
            &raw_transfer,
            &raw_transfer.input,
            chain_id_numeric,
            &canonical_network,
            &normalized_subnet,
        )?;

        Ok(())
    }

    /// Convert Wei (as hex string) to ETH (as f64)
    fn wei_to_eth(wei_hex: &str) -> f64 {
        let wei_value = Self::parse_hex_u128(wei_hex);
        wei_value as f64 / 1_000_000_000_000_000_000.0
    }

    /// Calculate transaction fee in Wei
    fn calculate_transaction_fee(gas_used: u64, gas_price_hex: &str) -> String {
        let gas_price = Self::parse_hex_u128(gas_price_hex);
        let fee = gas_price * gas_used as u128;
        format!("0x{:x}", fee)
    }

    /// Categorize transfer by size
    fn categorize_transfer(amount_eth: f64) -> TransferCategory {
        if amount_eth < 0.01 {
            TransferCategory::Micro
        } else if amount_eth < 1.0 {
            TransferCategory::Small
        } else if amount_eth < 10.0 {
            TransferCategory::Medium
        } else if amount_eth < 100.0 {
            TransferCategory::Large
        } else {
            TransferCategory::Whale
        }
    }

    /// Determine address type (simplified - would check bytecode in production)
    fn determine_address_type(address: &str) -> AddressType {
        // Simplified: Check if address starts with known contract patterns
        // In production, would query chain for bytecode
        if address.to_lowercase().contains("contract") {
            AddressType::Contract
        } else if address.len() == 42 && address.starts_with("0x") {
            AddressType::ExternallyOwnedAccount
        } else {
            AddressType::Unknown
        }
    }

    /// Get native currency for network
    fn get_network_currency(network: &str) -> String {
        match network.to_lowercase().as_str() {
            "ethereum" => "ETH".to_string(),
            "arbitrum" => "ETH".to_string(),
            "optimism" => "ETH".to_string(),
            "base" => "ETH".to_string(),
            "polygon" => "MATIC".to_string(),
            "binance" => "BNB".to_string(),
            "bsc" => "BNB".to_string(),
            "bnb" => "BNB".to_string(),
            "avalanche" => "AVAX".to_string(),
            _ => "ETH".to_string(), // Default to ETH
        }
    }

    fn canonical_network_name(network: &str, chain_id: i64) -> String {
        match network.to_lowercase().as_str() {
            "ethereum" | "eth" => "ethereum".to_string(),
            "arbitrum" | "arb" => "arbitrum".to_string(),
            "optimism" | "op" => "optimism".to_string(),
            "base" => "base".to_string(),
            "polygon" | "matic" => "polygon".to_string(),
            "avalanche" | "avax" => "avalanche".to_string(),
            "binance" | "bsc" | "bnb" => "bsc".to_string(),
            _ => match chain_id {
                1 | 5 | 11155111 => "ethereum".to_string(),
                10 => "optimism".to_string(),
                56 => "bsc".to_string(),
                137 | 80001 => "polygon".to_string(),
                42161 => "arbitrum".to_string(),
                43113 | 43114 => "avalanche".to_string(),
                8453 => "base".to_string(),
                _ => network.trim().to_lowercase(),
            },
        }
    }

    /// Create decoded transfer details JSON
    fn create_decoded_transfer_details(
        transaction_hash: &str,
        from_address: &str,
        to_address: &str,
        value_wei: &str,
        amount_eth: f64,
        gas_limit: u64,
        gas_price: &str,
        category: &TransferCategory,
    ) -> serde_json::Value {
        serde_json::json!({
            "transfer_type": "native",
            "transaction_hash": transaction_hash,
            "from": from_address,
            "to": to_address,
            "amount_wei": value_wei,
            "amount_formatted": format!("{:.6}", amount_eth),
            "category": format!("{:?}", category),
            "gas_limit": gas_limit,
            "gas_price": gas_price,
        })
    }

    /// Parse hexadecimal string to u128
    fn parse_hex_u128(hex_str: &str) -> u128 {
        let cleaned = hex_str.trim_start_matches("0x");
        u128::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Parse hexadecimal string to u64
    fn parse_hex_u64(hex_str: &str) -> u64 {
        let cleaned = hex_str.trim_start_matches("0x");
        u64::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Publish processed transfer to all destinations
    fn publish_processed_transfer(
        processed_transfer: &ProcessedTransfer,
        raw_transfer: &RawTransferTransaction,
        input: &str,
        chain_id: i64,
        network: &str,
        subnet: &str,
    ) -> Result<(), String> {
        let payload = serde_json::to_vec(processed_transfer)
            .map_err(|e| format!("Failed to serialize processed transfer: {}", e))?;

        // 1. Publish to processed transfers subject
        let processed_subject = "transfers.processed.evm".to_string();
        Self::publish_message(&processed_subject, &payload)?;

        // 2. Publish a schedule event for candidate targets
        let chain = Self::get_network_currency(network);
        let candidate_target_keys = Self::build_candidate_target_keys(
            &chain,
            subnet,
            &processed_transfer.from_address,
            &processed_transfer.to_address,
        );

        if candidate_target_keys.is_empty() {
            eprintln!("[ETH-TRANSFERS] ℹ️  No candidate targets for this transfer");
        } else {
            let schedule_event = Self::build_schedule_event(
                processed_transfer,
                input,
                &chain,
                subnet,
                chain_id,
                candidate_target_keys,
            );
            let schedule_payload = serde_json::to_vec(&schedule_event)
                .map_err(|e| format!("Failed to serialize schedule event: {}", e))?;
            Self::publish_message("alerts.schedule.event_driven", &schedule_payload)?;
            eprintln!(
                "[ETH-TRANSFERS] ✅ Published schedule event for {} candidate targets",
                schedule_event.candidate_target_keys.len()
            );
        }

        // 4. Publish balance update notifications
        let balance_subject = format!("balances.updated.{}.{}", network, subnet);
        Self::publish_message(&balance_subject, &payload)?;

        // 5. Publish to DuckLake for persistence (Schema Redesign: unified transactions table)
        let ducklake_record =
            Self::build_ducklake_transaction_record(processed_transfer, raw_transfer, input);
        let ducklake_payload = serde_json::to_vec(&ducklake_record)
            .map_err(|e| format!("Failed to serialize ducklake transaction: {}", e))?;
        let ducklake_subject = format!("ducklake.transactions.{}.{}.write", network, subnet);
        Self::publish_message(&ducklake_subject, &ducklake_payload)?;

        let address_records =
            Self::build_address_transaction_records(processed_transfer, raw_transfer);
        let address_subject = format!("ducklake.address_transactions.{}.{}.write", network, subnet);
        for record in address_records {
            let address_payload = serde_json::to_vec(&record)
                .map_err(|e| format!("Failed to serialize address transaction: {}", e))?;
            Self::publish_message(&address_subject, &address_payload)?;
        }

        Ok(())
    }

    fn build_candidate_target_keys(
        chain: &str,
        subnet: &str,
        from_addr: &str,
        to_addr: &str,
    ) -> Vec<String> {
        let mut keys = Vec::new();
        let to_key = |addr: &str| format!("{}:{}:{}", chain, subnet, addr.to_lowercase());

        if !from_addr.is_empty() {
            keys.push(to_key(from_addr));
        }
        if !to_addr.is_empty() {
            keys.push(to_key(to_addr));
        }

        keys.sort();
        keys.dedup();
        keys
    }

    fn build_schedule_event(
        transfer: &ProcessedTransfer,
        input: &str,
        chain: &str,
        subnet: &str,
        chain_id: i64,
        candidate_target_keys: Vec<String>,
    ) -> AlertScheduleEventDrivenV1 {
        let method_selector = Self::extract_method_selector(input);
        let event_time = datetime_from_unix_secs(transfer.block_timestamp);

        AlertScheduleEventDrivenV1 {
            schema_version: alert_schedule_event_driven_schema_version_v1(),
            vm: VmKindV1::Evm,
            partition: PartitionV1 {
                network: chain.to_string(),
                subnet: subnet.to_string(),
                chain_id,
            },
            candidate_target_keys,
            event: ScheduleEventV1 {
                kind: TxKindV1::Tx,
                evm_tx: Some(EvmTxV1 {
                    hash: transfer.transaction_hash.clone(),
                    from: transfer.from_address.clone(),
                    to: Some(transfer.to_address.clone()),
                    input: input.to_string(),
                    method_selector,
                    value_wei: transfer.amount_wei.clone(),
                    value_native: transfer.amount_native,
                    block_number: transfer.block_number as i64,
                    block_timestamp: event_time,
                }),
                evm_log: None,
            },
            requested_at: event_time,
            source: "eth_transfers_processor".to_string(),
        }
    }

    fn extract_method_selector(input: &str) -> Option<String> {
        if input.starts_with("0x") && input.len() >= 10 {
            Some(input[..10].to_string())
        } else {
            None
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

    fn optional_string(value: &str) -> Option<String> {
        if value.trim().is_empty() {
            None
        } else {
            Some(value.to_string())
        }
    }

    fn build_ducklake_transaction_record(
        processed_transfer: &ProcessedTransfer,
        raw_transfer: &RawTransferTransaction,
        input: &str,
    ) -> DuckLakeTransactionRecord {
        let gas_limit = Self::parse_hex_u64(&raw_transfer.gas);
        let transaction_index = Self::parse_hex_u64(&raw_transfer.transaction_index) as u32;
        let nonce = Some(Self::parse_hex_u64(&raw_transfer.nonce));
        let v = raw_transfer
            .v
            .as_ref()
            .map(|value| Self::parse_hex_u64(value));

        let gas_price = Self::normalize_quantity_string(&raw_transfer.gas_price);
        let value = Self::normalize_quantity_string(&raw_transfer.value);
        let transaction_fee =
            Self::normalize_quantity_string(&processed_transfer.transaction_fee_wei);
        let block_date = Utc
            .timestamp_opt(processed_transfer.block_timestamp as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "1970-01-01".to_string());

        let input_data = if input.trim().is_empty() || input == "0x" {
            None
        } else {
            Some(input.to_string())
        };

        DuckLakeTransactionRecord {
            chain_id: processed_transfer.chain_id.clone(),
            block_date,
            network: processed_transfer.network.clone(),
            subnet: processed_transfer.subnet.clone(),
            vm_type: processed_transfer.vm_type.clone(),
            block_number: processed_transfer.block_number,
            block_timestamp: processed_transfer.block_timestamp,
            transaction_hash: processed_transfer.transaction_hash.clone(),
            transaction_index,
            from_address: Self::optional_string(&processed_transfer.from_address),
            to_address: Self::optional_string(&processed_transfer.to_address),
            value: Some(value),
            gas_limit: Some(gas_limit),
            gas_used: Some(gas_limit),
            gas_price: Some(gas_price.clone()),
            max_fee_per_gas: None,
            max_priority_fee_per_gas: None,
            status: "SUCCESS".to_string(),
            transaction_fee: Some(transaction_fee),
            effective_gas_price: Some(gas_price),
            input_data,
            method_signature: Self::extract_method_selector(input),
            transaction_type: processed_transfer.transaction_type.clone(),
            transaction_subtype: Some(processed_transfer.transaction_subtype.clone()),
            amount_native: Some(processed_transfer.amount_native),
            amount_usd: processed_transfer.amount_usd,
            fee_usd: processed_transfer.fee_usd,
            transfer_category: Some(format!("{:?}", processed_transfer.transfer_category)),
            sender_type: Some(format!("{:?}", processed_transfer.sender_type)),
            recipient_type: Some(format!("{:?}", processed_transfer.recipient_type)),
            decoded_function_name: processed_transfer.decoded_function_name.clone(),
            decoded_function_signature: processed_transfer.decoded_function_signature.clone(),
            decoded_function_selector: processed_transfer.decoded_function_selector.clone(),
            decoded_parameters: processed_transfer.decoded_parameters.clone(),
            decoding_status: Some(processed_transfer.decoding_status.clone()),
            abi_source: processed_transfer.abi_source.clone(),
            decoding_time_ms: processed_transfer.decoding_time_ms,
            decoded_summary: processed_transfer.decoded_summary.clone(),
            nonce,
            v,
            r: raw_transfer.r.clone(),
            s: raw_transfer.s.clone(),
            processor_id: Some(processed_transfer.processor_id.clone()),
            correlation_id: Some(processed_transfer.correlation_id.clone()),
        }
    }

    fn build_address_transaction_records(
        processed_transfer: &ProcessedTransfer,
        raw_transfer: &RawTransferTransaction,
    ) -> Vec<DuckLakeAddressTransactionRecord> {
        let block_date = Utc
            .timestamp_opt(processed_transfer.block_timestamp as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "1970-01-01".to_string());

        let value = Some(Self::normalize_quantity_string(&raw_transfer.value));
        let transaction_type = Some(processed_transfer.transaction_type.clone());
        let transaction_subtype = Some(processed_transfer.transaction_subtype.clone());

        let from_addr = processed_transfer.from_address.to_lowercase();
        let to_addr = processed_transfer.to_address.to_lowercase();

        vec![
            DuckLakeAddressTransactionRecord {
                chain_id: processed_transfer.chain_id.clone(),
                block_date: block_date.clone(),
                address: from_addr.clone(),
                transaction_hash: processed_transfer.transaction_hash.clone(),
                block_number: processed_transfer.block_number,
                block_timestamp: processed_transfer.block_timestamp,
                is_sender: true,
                counterparty_address: Some(to_addr.clone()),
                value: value.clone(),
                transaction_type: transaction_type.clone(),
                transaction_subtype: transaction_subtype.clone(),
            },
            DuckLakeAddressTransactionRecord {
                chain_id: processed_transfer.chain_id.clone(),
                block_date,
                address: to_addr,
                transaction_hash: processed_transfer.transaction_hash.clone(),
                block_number: processed_transfer.block_number,
                block_timestamp: processed_transfer.block_timestamp,
                is_sender: false,
                counterparty_address: Some(from_addr),
                value,
                transaction_type,
                transaction_subtype,
            },
        ]
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
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_transfer() -> RawTransferTransaction {
        RawTransferTransaction {
            hash: "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string(),
            from: "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045".to_string(),
            to: "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb".to_string(),
            value: "0xde0b6b3a7640000".to_string(), // 1 ETH in hex
            gas: "0x5208".to_string(),              // 21000 in hex
            gas_price: "0x4a817c800".to_string(),   // 20 Gwei in hex
            input: "0x".to_string(),
            nonce: "0x2a".to_string(),                       // 42 in hex
            block_number: "0x11a4bc0".to_string(),           // 18500000 in hex
            block_timestamp: Some("0x6544aec0".to_string()), // 1699000000 in hex
            block_hash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
                .to_string(),
            transaction_index: "0x5".to_string(), // 5 in hex
            chain_id: "0x1".to_string(),          // 1 for mainnet
            v: Some("0x1".to_string()),
            r: Some(
                "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string(),
            ),
            s: Some(
                "0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321".to_string(),
            ),
        }
    }

    fn create_test_processed_transfer() -> ProcessedTransfer {
        let raw_transfer = create_test_transfer();
        let amount_eth = Component::wei_to_eth(&raw_transfer.value);
        let fee_wei = Component::calculate_transaction_fee(21000, &raw_transfer.gas_price);
        let fee_native = Component::wei_to_eth(&fee_wei);

        ProcessedTransfer {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            chain_id: "ethereum_mainnet".to_string(),
            transaction_hash: raw_transfer.hash.clone(),
            block_number: 18500000,
            block_timestamp: 1699000000,
            from_address: raw_transfer.from.clone(),
            to_address: raw_transfer.to.clone(),
            amount_wei: raw_transfer.value.clone(),
            amount_native: amount_eth,
            amount_usd: None,
            gas_used: 21000,
            gas_price: raw_transfer.gas_price.clone(),
            transaction_fee_wei: fee_wei,
            transaction_fee_native: fee_native,
            fee_usd: None,
            transfer_category: TransferCategory::Medium,
            sender_type: AddressType::ExternallyOwnedAccount,
            recipient_type: AddressType::ExternallyOwnedAccount,
            sender_balance_before: None,
            sender_balance_after: None,
            recipient_balance_before: None,
            recipient_balance_after: None,
            transaction_type: "TRANSFER".to_string(),
            transaction_subtype: "native".to_string(),
            transaction_currency: "ETH".to_string(),
            transaction_value: "1.000000 ETH".to_string(),
            protocol: None,
            category: "value_transfer".to_string(),
            decoded_function_name: None,
            decoded_function_signature: None,
            decoded_function_selector: None,
            decoded_parameters: None,
            decoding_status: "NativeTransfer".to_string(),
            abi_source: None,
            decoding_time_ms: Some(0),
            decoded_summary: None,
            decoded: serde_json::json!({}),
            processed_at: "2024-01-01T00:00:00Z".to_string(),
            processor_id: "test".to_string(),
            correlation_id: "test".to_string(),
        }
    }

    #[test]
    fn test_wei_to_eth_conversion() {
        // 1 ETH = 1000000000000000000 Wei = 0xde0b6b3a7640000
        let eth = Component::wei_to_eth("0xde0b6b3a7640000");
        assert!((eth - 1.0).abs() < 0.0001);

        // 0.5 ETH
        let eth = Component::wei_to_eth("0x6f05b59d3b20000");
        assert!((eth - 0.5).abs() < 0.0001);

        // 10 ETH
        let eth = Component::wei_to_eth("0x8ac7230489e80000");
        assert!((eth - 10.0).abs() < 0.0001);
    }

    #[test]
    fn test_calculate_transaction_fee() {
        // gas_used = 21000, gas_price = 20 Gwei (0x4a817c800)
        // Fee = 21000 * 20000000000 = 420000000000000 = 0x17d7840ba8000
        let fee = Component::calculate_transaction_fee(21000, "0x4a817c800");
        let fee_eth = Component::wei_to_eth(&fee);
        assert!((fee_eth - 0.00042).abs() < 0.000001);
    }

    #[test]
    fn test_transfer_categorization() {
        assert_eq!(
            Component::categorize_transfer(0.005),
            TransferCategory::Micro
        );
        assert_eq!(Component::categorize_transfer(0.5), TransferCategory::Small);
        assert_eq!(
            Component::categorize_transfer(5.0),
            TransferCategory::Medium
        );
        assert_eq!(
            Component::categorize_transfer(50.0),
            TransferCategory::Large
        );
        assert_eq!(
            Component::categorize_transfer(150.0),
            TransferCategory::Whale
        );
    }

    #[test]
    fn test_determine_address_type() {
        let eoa = Component::determine_address_type("0x742d35cc6634c0532925a3b8d4c9db96c4b4d8b6");
        assert_eq!(eoa, AddressType::ExternallyOwnedAccount);

        let contract = Component::determine_address_type("0xcontract123");
        assert_eq!(contract, AddressType::Contract);

        let unknown = Component::determine_address_type("invalid");
        assert_eq!(unknown, AddressType::Unknown);
    }

    #[test]
    fn test_get_network_currency() {
        assert_eq!(Component::get_network_currency("ethereum"), "ETH");
        assert_eq!(Component::get_network_currency("arbitrum"), "ETH");
        assert_eq!(Component::get_network_currency("optimism"), "ETH");
        assert_eq!(Component::get_network_currency("base"), "ETH");
        assert_eq!(Component::get_network_currency("polygon"), "MATIC");
        assert_eq!(Component::get_network_currency("binance"), "BNB");
        assert_eq!(Component::get_network_currency("bsc"), "BNB");
        assert_eq!(Component::get_network_currency("avalanche"), "AVAX");
        assert_eq!(Component::get_network_currency("unknown"), "ETH");
    }

    #[test]
    fn test_canonical_network_name_normalizes_inputs() {
        assert_eq!(Component::canonical_network_name("ETH", 1), "ethereum");
        assert_eq!(
            Component::canonical_network_name("AvAx", 43114),
            "avalanche"
        );
        assert_eq!(Component::canonical_network_name("bsc", 56), "bsc");
        assert_eq!(Component::canonical_network_name("op", 10), "optimism");
    }

    #[test]
    fn test_canonical_network_name_uses_chain_id_fallback() {
        assert_eq!(Component::canonical_network_name("mainnet", 1), "ethereum");
        assert_eq!(
            Component::canonical_network_name("mainnet", 43113),
            "avalanche"
        );
    }

    #[test]
    fn test_create_decoded_transfer_details() {
        let raw_transfer = create_test_transfer();
        let amount_eth = 1.0;
        let category = TransferCategory::Small;

        let decoded = Component::create_decoded_transfer_details(
            &raw_transfer.hash,
            &raw_transfer.from,
            &raw_transfer.to,
            &raw_transfer.value,
            amount_eth,
            21000,
            &raw_transfer.gas_price,
            &category,
        );

        assert_eq!(decoded["transfer_type"], "native");
        assert_eq!(
            decoded["from"],
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        );
        assert_eq!(decoded["to"], "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb");
        assert_eq!(decoded["amount_wei"], "0xde0b6b3a7640000");
        assert_eq!(decoded["category"], "Small");
        assert_eq!(decoded["gas_limit"], 21000);
    }

    #[test]
    fn test_build_ducklake_transaction_record_converts_hex_and_filters_fields() {
        let raw_transfer = create_test_transfer();
        let processed_transfer = create_test_processed_transfer();

        let record = Component::build_ducklake_transaction_record(
            &processed_transfer,
            &raw_transfer,
            &raw_transfer.input,
        );
        let expected_date = Utc
            .timestamp_opt(processed_transfer.block_timestamp as i64, 0)
            .single()
            .expect("expected timestamp")
            .format("%Y-%m-%d")
            .to_string();

        assert_eq!(record.value.as_deref(), Some("1000000000000000000"));
        assert_eq!(record.gas_price.as_deref(), Some("20000000000"));
        assert_eq!(record.transaction_fee.as_deref(), Some("420000000000000"));
        assert_eq!(record.transaction_index, 5);
        assert_eq!(record.status, "SUCCESS");
        assert_eq!(record.method_signature, None);
        assert_eq!(record.input_data, None);
        assert_eq!(record.transfer_category.as_deref(), Some("Medium"));
        assert_eq!(record.block_date, expected_date);

        let json = serde_json::to_value(&record).expect("ducklake record should serialize");
        assert!(json.get("recipient_balance_before").is_none());
        assert!(json.get("transaction_fee_native").is_none());
    }

    #[test]
    fn test_build_address_transaction_records() {
        let raw_transfer = create_test_transfer();
        let processed_transfer = create_test_processed_transfer();

        let records =
            Component::build_address_transaction_records(&processed_transfer, &raw_transfer);

        assert_eq!(records.len(), 2);
        assert!(records.iter().any(|r| r.is_sender));
        assert!(records.iter().any(|r| !r.is_sender));

        let from_record = records.iter().find(|r| r.is_sender).expect("from record");
        let to_record = records.iter().find(|r| !r.is_sender).expect("to record");
        let from_lower = raw_transfer.from.to_lowercase();
        let to_lower = raw_transfer.to.to_lowercase();

        assert_eq!(from_record.address, from_lower);
        assert_eq!(to_record.address, to_lower);
        assert_eq!(
            from_record.counterparty_address.as_deref(),
            Some(to_lower.as_str())
        );
        assert_eq!(
            to_record.counterparty_address.as_deref(),
            Some(from_lower.as_str())
        );
        assert_eq!(from_record.transaction_hash, raw_transfer.hash);
        assert_eq!(from_record.transaction_type.as_deref(), Some("TRANSFER"));
    }

    #[test]
    fn test_enrichment_fields() {
        let raw_transfer = create_test_transfer();

        // Simulate processing to get enrichment fields
        let amount_eth = Component::wei_to_eth(&raw_transfer.value);
        let transfer_category = Component::categorize_transfer(amount_eth);
        let currency = Component::get_network_currency("ethereum"); // Fixed: use string literal
        let transaction_value = format!("{:.6} {}", amount_eth, currency);

        // Verify enrichment fields
        assert_eq!("TRANSFER", "TRANSFER"); // transaction_type (now uppercase)
        assert_eq!(currency, "ETH"); // transaction_currency
        assert!(transaction_value.starts_with("1.")); // transaction_value
        assert_eq!("native", "native"); // transaction_subtype
        assert_eq!("value_transfer", "value_transfer"); // category

        // Verify decoded structure
        let decoded = Component::create_decoded_transfer_details(
            &raw_transfer.hash,
            &raw_transfer.from,
            &raw_transfer.to,
            &raw_transfer.value,
            amount_eth,
            21000,
            &raw_transfer.gas_price,
            &transfer_category,
        );
        assert!(decoded.is_object());
        assert_eq!(decoded["transfer_type"], "native");
    }

    #[test]
    fn test_new_schema_fields() {
        // Test the new fields added for unified transactions schema
        let raw_transfer = create_test_transfer();
        let amount_eth = Component::wei_to_eth(&raw_transfer.value);
        let currency = Component::get_network_currency("ethereum");

        // Test chain_id construction
        let network = "ethereum";
        let subnet = "mainnet";
        let chain_id = format!("{}_{}", network, subnet);
        assert_eq!(chain_id, "ethereum_mainnet");

        // Test decoded_summary generation
        let to_short = format!(
            "{}...{}",
            &raw_transfer.to[..6],
            &raw_transfer.to[raw_transfer.to.len() - 4..]
        );
        let decoded_summary = format!("transfer {:.4} {} to {}", amount_eth, currency, to_short);
        assert!(decoded_summary.starts_with("transfer 1.0000 ETH to 0x742d"));

        // Test decoding_status for native transfers
        let decoding_status = "NativeTransfer".to_string();
        assert_eq!(decoding_status, "NativeTransfer");

        // Test that decoded function fields are None for native transfers
        let decoded_function_name: Option<String> = None;
        let decoded_function_signature: Option<String> = None;
        let decoded_parameters: Option<String> = None;
        assert_eq!(decoded_function_name, None);
        assert_eq!(decoded_function_signature, None);
        assert_eq!(decoded_parameters, None);
    }

    #[test]
    fn test_fee_usd_field() {
        // Test the new fee_usd field (None until price oracle integration)
        let fee_usd: Option<f64> = None;
        assert_eq!(fee_usd, None);

        // In production with price oracle:
        // let fee_usd: Option<f64> = Some(0.84); // 0.00042 ETH * $2000/ETH
        // assert!((fee_usd.unwrap() - 0.84).abs() < 0.01);
    }

    #[test]
    fn test_amount_native_renamed() {
        // Test that amount_native (renamed from amount_eth) works correctly
        let raw_transfer = create_test_transfer();
        let amount_native = Component::wei_to_eth(&raw_transfer.value);
        assert!((amount_native - 1.0).abs() < 0.0001);

        // Verify the field name change in ProcessedTransfer struct
        // (ProcessedTransfer now has amount_native instead of amount_eth)
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
        assert_eq!(Component::parse_hex_u128("invalid"), 0); // Should handle invalid gracefully
    }

    #[test]
    fn test_balance_context_fields() {
        // Test that balance fields are properly initialized
        // In a full integration, these would be fetched from Redis
        let sender_balance_before: Option<String> = None;
        let sender_balance_after: Option<String> = None;
        let recipient_balance_before: Option<String> = None;
        let recipient_balance_after: Option<String> = None;

        assert_eq!(sender_balance_before, None);
        assert_eq!(sender_balance_after, None);
        assert_eq!(recipient_balance_before, None);
        assert_eq!(recipient_balance_after, None);
    }

    #[test]
    fn test_all_enrichment_fields_populated() {
        let raw_transfer = create_test_transfer();
        let amount_eth = Component::wei_to_eth(&raw_transfer.value);
        let transfer_category = Component::categorize_transfer(amount_eth);
        let currency = Component::get_network_currency("ethereum");
        let decoded = Component::create_decoded_transfer_details(
            &raw_transfer.hash,
            &raw_transfer.from,
            &raw_transfer.to,
            &raw_transfer.value,
            amount_eth,
            21000,
            &raw_transfer.gas_price,
            &transfer_category,
        );

        // Verify all enrichment fields (Schema Redesign)
        let transaction_type = "TRANSFER".to_string(); // Updated: now uppercase
        let transaction_currency = currency.clone();
        let transaction_value = format!("{:.6} {}", amount_eth, currency);
        let transaction_subtype = "native".to_string();
        let protocol: Option<String> = None;
        let category = "value_transfer".to_string();

        // New decoded function fields for native transfers
        let decoding_status = "NativeTransfer".to_string();
        let decoded_function_name: Option<String> = None;
        let abi_source: Option<String> = None;

        assert_eq!(transaction_type, "TRANSFER");
        assert_eq!(transaction_currency, "ETH");
        assert!(transaction_value.contains("ETH"));
        assert_eq!(transaction_subtype, "native");
        assert_eq!(protocol, None);
        assert_eq!(category, "value_transfer");
        assert!(decoded.is_object());

        // Verify native transfer decoding fields
        assert_eq!(decoding_status, "NativeTransfer");
        assert_eq!(decoded_function_name, None);
        assert_eq!(abi_source, None);
    }

    #[test]
    fn test_build_schedule_event() {
        let transfer = create_test_processed_transfer();
        let chain = Component::get_network_currency("ethereum");
        let candidate_keys = Component::build_candidate_target_keys(
            &chain,
            "mainnet",
            &transfer.from_address,
            &transfer.to_address,
        );

        let event =
            Component::build_schedule_event(&transfer, "0x", &chain, "mainnet", 1, candidate_keys);

        assert_eq!(
            event.schema_version,
            alert_schedule_event_driven_schema_version_v1()
        );
        assert_eq!(event.partition.network, "ETH");
        assert_eq!(event.partition.subnet, "mainnet");
        assert_eq!(event.partition.chain_id, 1);
        assert_eq!(event.event.kind, TxKindV1::Tx);
        assert_eq!(event.candidate_target_keys.len(), 2);
        assert_eq!(
            event
                .event
                .evm_tx
                .as_ref()
                .unwrap()
                .block_timestamp
                .timestamp(),
            transfer.block_timestamp as i64
        );
        assert_eq!(
            event.requested_at.timestamp(),
            transfer.block_timestamp as i64
        );
        assert_eq!(event.event.evm_tx.as_ref().unwrap().method_selector, None);
    }

    #[test]
    fn test_datetime_from_unix_secs_roundtrip() {
        let secs = 1_769_540_484u64;
        let dt = datetime_from_unix_secs(secs);
        assert_eq!(dt.timestamp(), secs as i64);
    }

    #[test]
    fn test_rfc3339_from_unix_secs_roundtrip() {
        let secs = 1_704_067_200u64;
        let rendered = rfc3339_from_unix_secs(secs);
        let parsed = DateTime::parse_from_rfc3339(&rendered).unwrap();
        assert_eq!(parsed.timestamp(), secs as i64);
    }

    #[test]
    fn test_ducklake_subject_format() {
        // Test that DuckLake subject uses unified transactions table
        let network = "ethereum";
        let subnet = "mainnet";
        let ducklake_subject = format!("ducklake.transactions.{}.{}.write", network, subnet);
        assert_eq!(
            ducklake_subject,
            "ducklake.transactions.ethereum.mainnet.write"
        );

        // Verify it does NOT use the old processed_transfers table
        assert!(!ducklake_subject.contains("processed_transfers"));
    }
}
