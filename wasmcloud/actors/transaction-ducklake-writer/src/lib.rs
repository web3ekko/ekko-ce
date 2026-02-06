//! # Transaction DuckLake Writer Actor
//!
//! WasmCloud actor that processes and persists blockchain transactions to DuckLake.
//! This actor receives processed transactions via NATS messaging and publishes them
//! to DuckLake NATS subjects in the format: `ducklake.{table}.{chain}.{subnet}.write`
//!
//! The ducklake-write provider subscribes to these subjects and handles batch ingestion.
//!
//! ## Supported Input Subjects
//! - `blockchain.{network}.{subnet}.transactions.processed` - From transaction processing actors
//! - `blockchain.{network}.{subnet}.contracts.decoded` - From abi-decoder actor
//!
//! ## WASM Compatibility
//! This actor avoids using chrono::Utc::now() which doesn't work in WASM.
//! Instead, timestamps are derived from incoming transaction data.

use serde::{Deserialize, Serialize};
use serde_json::json;

/// Parse an ISO 8601 timestamp string to extract date parts for partitioning.
/// Returns (year, month, day, hour) or defaults if parsing fails.
fn parse_timestamp_parts(
    timestamp_str: &str,
    fallback_unix: Option<u64>,
) -> (String, String, String, String) {
    // Try to parse ISO 8601 format: "2025-12-26T14:30:00Z" or similar
    if timestamp_str.len() >= 13 {
        if let (Some(year), Some(month), Some(day), Some(hour)) = (
            timestamp_str.get(0..4),
            timestamp_str.get(5..7),
            timestamp_str.get(8..10),
            timestamp_str.get(11..13),
        ) {
            return (
                year.to_string(),
                month.to_string(),
                day.to_string(),
                hour.to_string(),
            );
        }
    }

    let fallback = fallback_unix.unwrap_or_else(current_unix_timestamp);
    unix_timestamp_to_parts(fallback)
}

fn current_unix_timestamp() -> u64 {
    #[cfg(target_arch = "wasm32")]
    {
        wasi::clocks::wall_clock::now().seconds
    }

    #[cfg(not(target_arch = "wasm32"))]
    {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }
}

/// Convert Unix timestamp to date parts for partitioning.
/// Returns (year, month, day, hour).
fn unix_timestamp_to_parts(timestamp: u64) -> (String, String, String, String) {
    // Simple conversion without chrono
    // Seconds per unit
    const SECS_PER_HOUR: u64 = 3600;
    const SECS_PER_DAY: u64 = 86400;

    // Days per month (non-leap year approximation)
    const DAYS_PER_MONTH: [u64; 12] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

    // Calculate year (starting from 1970)
    let mut remaining = timestamp;
    let mut year = 1970u64;

    loop {
        let days_in_year = if is_leap_year(year) { 366 } else { 365 };
        let secs_in_year = days_in_year * SECS_PER_DAY;
        if remaining < secs_in_year {
            break;
        }
        remaining -= secs_in_year;
        year += 1;
    }

    // Calculate month and day
    let mut month = 1u64;
    for (i, &days) in DAYS_PER_MONTH.iter().enumerate() {
        let days_in_month = if i == 1 && is_leap_year(year) {
            29
        } else {
            days
        };
        let secs_in_month = days_in_month * SECS_PER_DAY;
        if remaining < secs_in_month {
            break;
        }
        remaining -= secs_in_month;
        month += 1;
    }

    let day = (remaining / SECS_PER_DAY) + 1;
    remaining %= SECS_PER_DAY;
    let hour = remaining / SECS_PER_HOUR;

    (
        format!("{:04}", year),
        format!("{:02}", month),
        format!("{:02}", day),
        format!("{:02}", hour),
    )
}

fn is_leap_year(year: u64) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

// Generate WIT bindings for the transaction-ducklake-writer world
wit_bindgen::generate!({ generate_all });

use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use subject_registry::blockchain;
use wasmcloud::messaging::{consumer, types};

/// Processed transaction from processing actors
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessedTransaction {
    // Network context
    pub network: String,
    pub subnet: String,
    pub vm_type: String,

    // Common transaction fields
    pub transaction_hash: String,
    pub block_number: u64,
    #[serde(default)]
    pub transaction_index: u32,
    pub from_address: String,
    pub to_address: Option<String>,
    #[serde(default)]
    pub value: String,
    #[serde(default)]
    pub timestamp: u64,

    // Processing metadata
    pub processed_at: String,
    pub processor_id: String,
    #[serde(default)]
    pub processing_duration_ms: u64,

    // VM-specific data (JSON)
    #[serde(default)]
    pub vm_specific_data: serde_json::Value,
}

/// Decoded transaction from abi-decoder actor
/// These come from `blockchain.{network}.{subnet}.contracts.decoded` subjects
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedTransaction {
    pub network: String,
    pub subnet: String,
    pub transaction_hash: String,
    pub block_number: u64,
    pub from_address: String,
    pub to_address: String,
    #[serde(default)]
    pub value: String,
    pub decoding_status: String,
    pub decoded_function: Option<DecodedFunction>,
    #[serde(default)]
    pub input_data: String,
    pub abi_source: Option<String>,
    pub processed_at: String,
    pub processor_id: String,
}

/// Decoded function information from ABI decoding
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedFunction {
    pub name: String,
    pub selector: String,
    pub signature: String,
    #[serde(default)]
    pub parameters: Vec<DecodedParameter>,
    #[serde(default)]
    pub abi_source: Option<String>,
}

/// Decoded parameter from ABI decoding
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecodedParameter {
    pub name: String,
    #[serde(alias = "type", alias = "param_type")]
    pub param_type: String,
    pub value: String,
    #[serde(default)]
    pub indexed: bool,
}

impl DecodedTransaction {
    /// Parse decoded transaction from JSON
    pub fn from_json(data: &[u8]) -> Result<Self, String> {
        serde_json::from_slice(data)
            .map_err(|e| format!("Failed to parse decoded transaction: {}", e))
    }

    /// Generate DuckLake partition values from decoded transaction
    /// Uses processed_at timestamp instead of current time (WASM compatible)
    pub fn generate_partitions(&self) -> Vec<(String, String)> {
        let (year, month, day, hour) = parse_timestamp_parts(&self.processed_at, None);

        vec![
            ("network".to_string(), self.network.clone()),
            ("subnet".to_string(), self.subnet.clone()),
            ("vm_type".to_string(), "evm".to_string()), // Decoded transactions are always EVM
            ("year".to_string(), year),
            ("month".to_string(), month),
            ("day".to_string(), day),
            ("hour".to_string(), hour),
        ]
    }

    /// Convert decoded transaction to DuckLake record
    /// Note: ingested_at uses processed_at timestamp (WASM compatible - no system time access)
    pub fn to_delta_record(&self) -> serde_json::Value {
        let mut record = json!({
            // Transaction core data
            "transaction_hash": self.transaction_hash,
            "block_number": self.block_number,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "value": self.value,

            // Decoding information
            "decoding_status": self.decoding_status,
            "input_data": self.input_data,
            "abi_source": self.abi_source,

            // Processing metadata
            "processed_at": self.processed_at,
            "processor_id": self.processor_id,
            "ingested_at": self.processed_at, // Use processed_at as ingested_at (WASM compatible)
            "data_version": "1.0",

            // Network context
            "network": self.network,
            "subnet": self.subnet,
            "vm_type": "evm",
        });

        // Add decoded function data if present
        if let Some(ref func) = self.decoded_function {
            if let serde_json::Value::Object(ref mut record_obj) = record {
                record_obj.insert("function_name".to_string(), json!(func.name));
                record_obj.insert("function_selector".to_string(), json!(func.selector));
                record_obj.insert("function_signature".to_string(), json!(func.signature));
                record_obj.insert("decoded_parameters".to_string(), json!(func.parameters));
            }
        }

        record
    }
}

/// DuckLake write request structure
/// Sent to ducklake-write provider via NATS subject: ducklake.{table}.{chain}.{subnet}.write
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuckLakeWriteRequest {
    pub table_name: String,
    pub chain: String,
    pub subnet: String,
    pub partition_values: Vec<(String, String)>,
    pub record: serde_json::Value,
    pub write_mode: String, // "append", "overwrite", "merge"
}

impl ProcessedTransaction {
    /// Parse processed transaction from JSON
    pub fn from_json(data: &[u8]) -> Result<Self, String> {
        serde_json::from_slice(data)
            .map_err(|e| format!("Failed to parse processed transaction: {}", e))
    }

    /// Generate DuckLake partition values from transaction
    /// Uses transaction's Unix timestamp (WASM compatible)
    pub fn generate_partitions(&self) -> Vec<(String, String)> {
        let (year, month, day, hour) = unix_timestamp_to_parts(self.timestamp);

        vec![
            ("network".to_string(), self.network.clone()),
            ("subnet".to_string(), self.subnet.clone()),
            ("vm_type".to_string(), self.vm_type.clone()),
            ("year".to_string(), year),
            ("month".to_string(), month),
            ("day".to_string(), day),
            ("hour".to_string(), hour),
        ]
    }

    /// Convert to enriched DuckLake record
    /// Note: ingested_at uses processed_at timestamp (WASM compatible - no system time access)
    pub fn to_delta_record(&self) -> serde_json::Value {
        let mut record = json!({
            // Transaction core data
            "transaction_hash": self.transaction_hash,
            "block_number": self.block_number,
            "transaction_index": self.transaction_index,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "value": self.value,
            "block_timestamp": self.timestamp,

            // Processing metadata
            "processed_at": self.processed_at,
            "processor_id": self.processor_id,
            "processing_duration_ms": self.processing_duration_ms,
            "ingested_at": self.processed_at, // Use processed_at as ingested_at (WASM compatible)
            "data_version": "1.0",

            // Network context (also in partitions)
            "network": self.network,
            "subnet": self.subnet,
            "vm_type": self.vm_type,
        });

        // Merge VM-specific data
        if let serde_json::Value::Object(vm_data) = &self.vm_specific_data {
            if let serde_json::Value::Object(ref mut record_obj) = record {
                for (key, value) in vm_data {
                    record_obj.insert(key.clone(), value.clone());
                }
            }
        }

        record
    }
}

impl DuckLakeWriteRequest {
    /// Convert to JSON bytes for transmission
    pub fn to_json(&self) -> Result<Vec<u8>, String> {
        serde_json::to_vec(self)
            .map_err(|e| format!("Failed to serialize DuckLake write request: {}", e))
    }

    /// Build the NATS subject for this write request
    /// Format: ducklake.{table}.{chain}.{subnet}.write
    pub fn to_nats_subject(&self) -> String {
        format!(
            "ducklake.{}.{}.{}.write",
            self.table_name, self.chain, self.subnet
        )
    }
}

/// Main Transaction DuckLake Writer Actor Component
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    /// Handle incoming NATS messages containing processed or decoded transactions
    ///
    /// Input subjects:
    /// - `blockchain.{network}.{subnet}.transactions.processed` - From processing actors
    /// - `blockchain.{network}.{subnet}.contracts.decoded` - From abi-decoder actor
    ///
    /// Output subject: ducklake.{table}.{chain}.{subnet}.write
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        // Log immediately on entry to confirm handler is being invoked
        eprintln!("[DuckLake Writer v1.0.4] === HANDLER INVOKED ===");
        eprintln!("[DuckLake Writer] Subject: {}", msg.subject);
        eprintln!("[DuckLake Writer] Payload size: {} bytes", msg.body.len());

        let subject = &msg.subject;
        let payload = &msg.body;

        eprintln!(
            "[DuckLake Writer] Processing message on subject: {}",
            subject
        );

        // Route to appropriate handler based on subject
        if blockchain::is_contracts_decoded_event(subject) {
            return handle_decoded_transaction(subject, payload);
        } else if blockchain::is_transactions_processed_event(subject) {
            return handle_processed_transaction(subject, payload);
        }

        // Ignore non-transaction messages
        Ok(())
    }
}

/// Handle decoded transactions from abi-decoder actor
fn handle_decoded_transaction(_subject: &str, payload: &[u8]) -> Result<(), String> {
    // Parse the decoded transaction
    let transaction = match DecodedTransaction::from_json(payload) {
        Ok(tx) => tx,
        Err(e) => {
            eprintln!(
                "[DuckLake Writer] Failed to parse decoded transaction: {}",
                e
            );
            return Err(e);
        }
    };

    eprintln!(
        "[DuckLake Writer] Processing decoded transaction: {} on {}/{}",
        transaction.transaction_hash, transaction.network, transaction.subnet
    );

    // Table name for decoded transactions (EVM only for now)
    let table_name = "decoded_transactions_evm".to_string();

    // Create DuckLake write request
    let ducklake_request = DuckLakeWriteRequest {
        table_name: table_name.clone(),
        chain: transaction.network.clone(),
        subnet: transaction.subnet.clone(),
        partition_values: transaction.generate_partitions(),
        record: transaction.to_delta_record(),
        write_mode: "append".to_string(),
    };

    publish_to_ducklake(
        &ducklake_request,
        &table_name,
        &transaction.network,
        &transaction.subnet,
    )
}

/// Handle processed transactions from processing actors
fn handle_processed_transaction(_subject: &str, payload: &[u8]) -> Result<(), String> {
    // Parse the processed transaction
    let transaction = match ProcessedTransaction::from_json(payload) {
        Ok(tx) => tx,
        Err(e) => {
            eprintln!(
                "[DuckLake Writer] Failed to parse processed transaction: {}",
                e
            );
            return Err(e);
        }
    };

    eprintln!(
        "[DuckLake Writer] Processing transaction: {} on {}/{}",
        transaction.transaction_hash, transaction.network, transaction.subnet
    );

    // Generate table name based on VM type (e.g., "transactions_evm", "transactions_svm")
    let table_name = format!("transactions_{}", transaction.vm_type);

    // Create DuckLake write request with chain/subnet for NATS subject routing
    let ducklake_request = DuckLakeWriteRequest {
        table_name: table_name.clone(),
        chain: transaction.network.clone(),
        subnet: transaction.subnet.clone(),
        partition_values: transaction.generate_partitions(),
        record: transaction.to_delta_record(),
        write_mode: "append".to_string(),
    };

    publish_to_ducklake(
        &ducklake_request,
        &table_name,
        &transaction.network,
        &transaction.subnet,
    )
}

/// Publish a DuckLake write request to NATS
/// The ducklake-write provider subscribes to ducklake.*.*.*.write subjects
fn publish_to_ducklake(
    ducklake_request: &DuckLakeWriteRequest,
    _table_name: &str,
    _network: &str,
    _subnet: &str,
) -> Result<(), String> {
    // Build the NATS subject
    let subject = ducklake_request.to_nats_subject();

    // Serialize the request to JSON
    let payload = match ducklake_request.to_json() {
        Ok(p) => p,
        Err(e) => {
            eprintln!("[DuckLake Writer] Failed to serialize request: {}", e);
            return Err(e);
        }
    };

    eprintln!(
        "[DuckLake Writer] Publishing to subject: {} ({} bytes)",
        subject,
        payload.len()
    );

    // Use the messaging consumer to publish to NATS
    match consumer::publish(&types::BrokerMessage {
        subject: subject.clone(),
        body: payload,
        reply_to: None,
    }) {
        Ok(()) => {
            eprintln!("[DuckLake Writer] Successfully published to {}", subject);
            Ok(())
        }
        Err(e) => {
            let err_msg = format!("Failed to publish to NATS: {}", e);
            eprintln!("[DuckLake Writer] {}", err_msg);
            Err(err_msg)
        }
    }
}

#[cfg(not(target_arch = "wasm32"))]
fn main() {
    // This function is never called in the WASM build
    println!("Transaction delta writer actor - use as WASM component");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_timestamp_parts_valid() {
        let (year, month, day, hour) = parse_timestamp_parts("2026-01-27T15:45:00Z", Some(0));
        assert_eq!(year, "2026");
        assert_eq!(month, "01");
        assert_eq!(day, "27");
        assert_eq!(hour, "15");
    }

    #[test]
    fn test_parse_timestamp_parts_fallback_unix() {
        let fallback = 1_700_000_000u64;
        let expected = unix_timestamp_to_parts(fallback);
        let actual = parse_timestamp_parts("invalid", Some(fallback));
        assert_eq!(actual, expected);
    }
}
