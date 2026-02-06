//! # EVM Logs Ingestion Actor
//!
//! WasmCloud actor that ingests EVM event logs for each new block, persists them to DuckLake,
//! and publishes event-driven schedule requests for alert evaluation.
//!
//! ## Subscription Pattern
//! - Subscribes to: `newheads.{network}.{subnet}.evm`
//! - Publishes to:
//!   - `ducklake.logs.{network}.{subnet}.write`
//!   - `alerts.schedule.event_driven`

use serde::{Deserialize, Serialize};

// Generate WIT bindings for the processor world
wit_bindgen::generate!({ generate_all });

use alert_runtime_common::{
    alert_schedule_event_driven_schema_version_v1, AlertScheduleEventDrivenV1, EvmLogV1,
    PartitionV1, ScheduleEventV1, TxKindV1, VmKindV1,
};
use chrono::{TimeZone, Utc};
use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use wasmcloud::messaging::{consumer, types};

const MAX_LOGS_PER_BLOCK: usize = 50_000;
const RPC_RETRY_ATTEMPTS: usize = 3;

/// Block header from newheads provider
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockHeader {
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub chain_id: String,
    pub chain_name: String,
    pub block_number: u64,
    pub block_hash: String,
    pub parent_hash: String,
    pub timestamp: u64,
    pub transaction_count: Option<u32>,
    pub received_at: String,
    pub provider_id: String,
}

/// Network configuration from Redis (matches Django's blockchain node format)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    pub chain_id: String,
    pub chain_name: String,
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub rpc_url: String,
    #[serde(default)]
    pub ws_url: Option<String>,
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub is_primary: bool,
    #[serde(default)]
    pub priority: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RpcLog {
    pub address: String,
    pub topics: Vec<String>,
    pub data: String,
    #[serde(rename = "logIndex")]
    pub log_index: String,
    #[serde(rename = "transactionHash")]
    pub transaction_hash: String,
    #[serde(rename = "blockNumber")]
    pub block_number: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct DuckLakeLogRecord {
    pub chain_id: String,
    pub block_date: String,
    pub block_number: i64,
    pub block_timestamp: i64,
    pub transaction_hash: String,
    pub log_index: i32,
    pub address: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub topic0: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub topic1: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub topic2: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub topic3: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_signature: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_transfer: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_approval: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_swap: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_mint: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_burn: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_event_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_event_signature: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_event_parameters: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_decoding_status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_anonymous_event: Option<bool>,
    pub ingested_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_at: Option<String>,
}

/// Main EVM Logs Ingestion Actor
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        eprintln!("[EVM-LOGS] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        eprintln!("[EVM-LOGS] 📨 Received message on subject: {}", msg.subject);

        if !msg.subject.starts_with("newheads.") || !msg.subject.ends_with(".evm") {
            eprintln!("[EVM-LOGS] ⏭️  Skipping - not an EVM newheads message");
            return Ok(());
        }

        let block_header: BlockHeader = serde_json::from_slice(&msg.body)
            .map_err(|e| format!("Failed to parse block header: {}", e))?;

        eprintln!(
            "[EVM-LOGS] 🔗 Processing block #{} on {}",
            block_header.block_number, block_header.chain_name
        );

        Self::process_block_header(block_header)
    }
}

impl Component {
    fn process_block_header(block_header: BlockHeader) -> Result<(), String> {
        let config = Self::get_network_config(&block_header)?;
        if !config.enabled {
            eprintln!(
                "[EVM-LOGS] ⚠️  Network {}-{} is disabled",
                block_header.network, block_header.subnet
            );
            return Err(format!(
                "Network {}-{} is disabled",
                block_header.network, block_header.subnet
            ));
        }
        if config.rpc_url.is_empty() {
            return Err(format!(
                "No RPC URL configured for {}",
                block_header.network
            ));
        }

        let logs = Self::fetch_block_logs_with_retry(&config.rpc_url, block_header.block_number)?;
        if logs.is_empty() {
            eprintln!("[EVM-LOGS] ℹ️  No logs found for block");
            return Ok(());
        }

        let capped_logs = if logs.len() > MAX_LOGS_PER_BLOCK {
            eprintln!(
                "[EVM-LOGS] ⚠️  Capping logs from {} to {}",
                logs.len(),
                MAX_LOGS_PER_BLOCK
            );
            logs.into_iter()
                .take(MAX_LOGS_PER_BLOCK)
                .collect::<Vec<_>>()
        } else {
            logs
        };

        let chain_prefix = Self::network_prefix(&block_header.network);
        let chain_id_numeric = Self::chain_id_numeric(&block_header, chain_prefix);
        if chain_id_numeric == 0 {
            eprintln!(
                "[EVM-LOGS] ⚠️  Unable to resolve numeric chain_id for {}-{} (chain_id={})",
                block_header.network, block_header.subnet, block_header.chain_id
            );
        }
        let block_dt = Utc
            .timestamp_opt(block_header.timestamp as i64, 0)
            .single()
            .unwrap_or_else(|| Utc.timestamp_opt(0, 0).unwrap());
        let block_date = block_dt.format("%Y-%m-%d").to_string();

        let mut schedule_count = 0u64;
        let mut persisted_count = 0u64;
        let mut ducklake_failures = 0u64;
        let mut schedule_failures = 0u64;

        for log in capped_logs.iter() {
            let normalized_address = Self::normalize_hex(&log.address);
            let normalized_tx_hash = Self::normalize_hex(&log.transaction_hash);
            let normalized_data = Self::normalize_hex(&log.data);

            let topics = log
                .topics
                .iter()
                .map(|topic| Self::normalize_hex(topic))
                .collect::<Vec<_>>();
            let topic0 = topics.get(0).cloned();
            let topic1 = topics.get(1).cloned();
            let topic2 = topics.get(2).cloned();
            let topic3 = topics.get(3).cloned();

            let log_index = Self::parse_hex_i64(&log.log_index) as i32;
            let block_number = block_header.block_number as i64;

            let record = DuckLakeLogRecord {
                chain_id: Self::normalize_chain_id(&block_header),
                block_date: block_date.clone(),
                block_number,
                block_timestamp: block_header.timestamp as i64,
                transaction_hash: normalized_tx_hash.clone(),
                log_index,
                address: normalized_address.clone(),
                topic0: topic0.clone(),
                topic1: topic1.clone(),
                topic2: topic2.clone(),
                topic3: topic3.clone(),
                data: Some(normalized_data.clone()),
                event_name: None,
                event_signature: None,
                is_transfer: None,
                is_approval: None,
                is_swap: None,
                is_mint: None,
                is_burn: None,
                decoded_event_name: None,
                decoded_event_signature: None,
                decoded_event_parameters: None,
                event_decoding_status: None,
                is_anonymous_event: Some(topic0.is_none()),
                ingested_at: block_dt.to_rfc3339(),
                decoded_at: None,
            };

            if let Err(err) =
                Self::publish_ducklake_log(&record, &block_header.network, &block_header.subnet)
            {
                ducklake_failures += 1;
                eprintln!("[EVM-LOGS] ❌ Failed to persist log: {}", err);
            } else {
                persisted_count += 1;
            }

            let candidate_target_keys = Self::build_candidate_target_keys(
                chain_prefix,
                &block_header.subnet,
                &normalized_address,
                &topic1,
                &topic2,
                &topic3,
            );

            if candidate_target_keys.is_empty() {
                continue;
            }

            let evm_log = EvmLogV1 {
                transaction_hash: normalized_tx_hash.clone(),
                log_index: log_index as i64,
                address: normalized_address.clone(),
                topic0: topic0.unwrap_or_default(),
                topic1,
                topic2,
                topic3,
                data: normalized_data,
                block_number,
                block_timestamp: block_dt,
            };

            let schedule_event = AlertScheduleEventDrivenV1 {
                schema_version: alert_schedule_event_driven_schema_version_v1(),
                vm: VmKindV1::Evm,
                partition: PartitionV1 {
                    network: chain_prefix.to_string(),
                    subnet: block_header.subnet.clone(),
                    chain_id: chain_id_numeric,
                },
                candidate_target_keys,
                event: ScheduleEventV1 {
                    kind: TxKindV1::Log,
                    evm_tx: None,
                    evm_log: Some(evm_log),
                },
                requested_at: block_dt,
                source: "evm_logs_ingestion".to_string(),
            };

            let payload = serde_json::to_vec(&schedule_event)
                .map_err(|e| format!("Failed to serialize schedule event: {}", e))?;
            if let Err(err) = Self::publish_message("alerts.schedule.event_driven", &payload) {
                schedule_failures += 1;
                eprintln!("[EVM-LOGS] ❌ Failed to publish schedule event: {}", err);
            } else {
                schedule_count += 1;
            }
        }

        eprintln!(
            "[EVM-LOGS] ✅ Published {} schedule events, persisted {} logs",
            schedule_count, persisted_count
        );
        if ducklake_failures > 0 || schedule_failures > 0 {
            eprintln!(
                "[EVM-LOGS] ⚠️  DuckLake failures: {}, schedule failures: {}",
                ducklake_failures, schedule_failures
            );
        }
        eprintln!("[EVM-LOGS] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        Ok(())
    }

    fn publish_ducklake_log(
        record: &DuckLakeLogRecord,
        network: &str,
        subnet: &str,
    ) -> Result<(), String> {
        let payload = serde_json::to_vec(record)
            .map_err(|e| format!("Failed to serialize ducklake log: {}", e))?;
        let subject = format!("ducklake.logs.{}.{}.write", network, subnet);
        Self::publish_message(&subject, &payload)
    }

    fn publish_message(subject: &str, payload: &[u8]) -> Result<(), String> {
        let msg = types::BrokerMessage {
            subject: subject.to_string(),
            body: payload.to_vec(),
            reply_to: None,
        };
        consumer::publish(&msg)
            .map_err(|e| format!("Failed to publish to {}: {:?}", subject, e))?;
        Ok(())
    }

    fn build_candidate_target_keys(
        chain_prefix: &str,
        subnet: &str,
        log_address: &str,
        topic1: &Option<String>,
        topic2: &Option<String>,
        topic3: &Option<String>,
    ) -> Vec<String> {
        let mut keys = Vec::new();
        let to_key = |addr: &str| format!("{}:{}:{}", chain_prefix, subnet, addr.to_lowercase());

        if !log_address.is_empty() {
            keys.push(to_key(log_address));
        }

        if let Some(addr) = topic1
            .as_ref()
            .and_then(|t| Self::extract_address_from_topic(t))
        {
            keys.push(to_key(&addr));
        }
        if let Some(addr) = topic2
            .as_ref()
            .and_then(|t| Self::extract_address_from_topic(t))
        {
            keys.push(to_key(&addr));
        }
        if let Some(addr) = topic3
            .as_ref()
            .and_then(|t| Self::extract_address_from_topic(t))
        {
            keys.push(to_key(&addr));
        }

        keys.sort();
        keys.dedup();
        keys
    }

    fn extract_address_from_topic(topic: &str) -> Option<String> {
        let topic = topic.trim().to_lowercase();
        if !topic.starts_with("0x") || topic.len() != 66 {
            return None;
        }

        let addr = &topic[topic.len() - 40..];
        if addr.chars().all(|c| c == '0') {
            return None;
        }

        Some(format!("0x{}", addr).to_lowercase())
    }

    fn normalize_chain_id(block_header: &BlockHeader) -> String {
        if block_header.chain_id.contains('_') {
            return block_header.chain_id.clone();
        }

        if block_header.chain_id.contains('-') {
            return block_header.chain_id.replace('-', "_");
        }

        format!("{}_{}", block_header.network, block_header.subnet)
    }

    fn parse_chain_id_numeric(chain_id: &str) -> Option<i64> {
        if let Some(stripped) = chain_id.strip_prefix("0x") {
            return i64::from_str_radix(stripped, 16).ok();
        }
        chain_id.parse::<i64>().ok()
    }

    fn network_prefix(network: &str) -> &str {
        match network.to_lowercase().as_str() {
            "ethereum" => "ETH",
            "polygon" => "MATIC",
            "binance" => "BNB",
            "avalanche" => "AVAX",
            _ => "ETH",
        }
    }

    fn normalize_hex(value: &str) -> String {
        value.trim().to_lowercase()
    }

    fn chain_id_numeric(block_header: &BlockHeader, chain_prefix: &str) -> i64 {
        if let Some(parsed) = Self::parse_chain_id_numeric(&block_header.chain_id) {
            return parsed;
        }

        Self::chain_id_from_partition(chain_prefix, &block_header.subnet).unwrap_or(0)
    }

    fn chain_id_from_partition(network: &str, subnet: &str) -> Option<i64> {
        match (network, subnet) {
            ("ETH", "mainnet") => Some(1),
            ("ETH", "sepolia") => Some(11155111),
            ("AVAX", "mainnet") => Some(43114),
            ("AVAX", "fuji") => Some(43113),
            ("MATIC", "mainnet") => Some(137),
            ("MATIC", "mumbai") => Some(80001),
            ("BNB", "mainnet") => Some(56),
            ("BNB", "testnet") => Some(97),
            _ => None,
        }
    }

    fn get_network_config(block_header: &BlockHeader) -> Result<NetworkConfig, String> {
        let redis_key = format!(
            "blockchain:nodes:{}-{}",
            block_header.network, block_header.subnet
        );
        let bucket = wasi::keyvalue::store::open("default")
            .map_err(|e| format!("Failed to open keyvalue bucket: {:?}", e))?;

        let config_bytes = bucket
            .get(&redis_key)
            .map_err(|e| format!("Failed to get key from store: {:?}", e))?
            .ok_or_else(|| format!("No configuration found for key: {}", redis_key))?;

        let config: NetworkConfig = serde_json::from_slice(&config_bytes)
            .map_err(|e| format!("Failed to parse network config: {}", e))?;

        Ok(config)
    }

    fn parse_url(url: &str) -> Result<(wasi::http::types::Scheme, String, String), String> {
        let (scheme_str, rest) = url
            .split_once("://")
            .ok_or_else(|| format!("Invalid URL format: {}", url))?;

        let scheme = match scheme_str {
            "http" => wasi::http::types::Scheme::Http,
            "https" => wasi::http::types::Scheme::Https,
            _ => return Err(format!("Unsupported scheme: {}", scheme_str)),
        };

        let (authority, path) = if let Some((auth, p)) = rest.split_once('/') {
            (auth.to_string(), format!("/{}", p))
        } else {
            (rest.to_string(), "/".to_string())
        };

        Ok((scheme, authority, path))
    }

    fn fetch_block_logs_with_retry(
        rpc_url: &str,
        block_number: u64,
    ) -> Result<Vec<RpcLog>, String> {
        let mut last_err: Option<String> = None;
        for attempt in 1..=RPC_RETRY_ATTEMPTS {
            match Self::fetch_block_logs(rpc_url, block_number) {
                Ok(logs) => return Ok(logs),
                Err(err) => {
                    eprintln!(
                        "[EVM-LOGS] ⚠️  RPC attempt {}/{} failed: {}",
                        attempt, RPC_RETRY_ATTEMPTS, err
                    );
                    last_err = Some(err);
                }
            }
        }

        Err(last_err.unwrap_or_else(|| "RPC request failed".to_string()))
    }

    fn fetch_block_logs(rpc_url: &str, block_number: u64) -> Result<Vec<RpcLog>, String> {
        let (scheme, authority, path) = Self::parse_url(rpc_url)?;
        let block_hex = format!("0x{:x}", block_number);

        let rpc_request = serde_json::json!({
            "jsonrpc": "2.0",
            "method": "eth_getLogs",
            "params": [{
                "fromBlock": block_hex,
                "toBlock": block_hex
            }],
            "id": 1
        });

        let request_body = serde_json::to_vec(&rpc_request)
            .map_err(|e| format!("Failed to serialize RPC request: {}", e))?;

        let headers = wasi::http::types::Fields::new();
        headers
            .set(
                &"content-type".to_string(),
                &vec!["application/json".as_bytes().to_vec()],
            )
            .map_err(|e| format!("Failed to set content-type header: {:?}", e))?;
        headers
            .set(
                &"content-length".to_string(),
                &vec![request_body.len().to_string().as_bytes().to_vec()],
            )
            .map_err(|e| format!("Failed to set content-length header: {:?}", e))?;
        let request = wasi::http::types::OutgoingRequest::new(headers);

        request
            .set_method(&wasi::http::types::Method::Post)
            .map_err(|e| format!("Failed to set method: {:?}", e))?;
        request
            .set_scheme(Some(&scheme))
            .map_err(|e| format!("Failed to set scheme: {:?}", e))?;
        request
            .set_authority(Some(&authority))
            .map_err(|e| format!("Failed to set authority: {:?}", e))?;
        request
            .set_path_with_query(Some(&path))
            .map_err(|e| format!("Failed to set path: {:?}", e))?;

        let body = request
            .body()
            .map_err(|_| "Failed to get request body".to_string())?;
        {
            let output_stream = body
                .write()
                .map_err(|_| "Failed to get body output stream".to_string())?;
            output_stream
                .blocking_write_and_flush(&request_body)
                .map_err(|e| format!("Failed to write request body: {:?}", e))?;
        }
        wasi::http::types::OutgoingBody::finish(body, None)
            .map_err(|_| "Failed to finish request body".to_string())?;

        let future_response = wasi::http::outgoing_handler::handle(request, None)
            .map_err(|e| format!("HTTP request failed: {:?}", e))?;
        let pollable = future_response.subscribe();
        wasi::io::poll::poll(&[&pollable]);

        let outer_result = future_response
            .get()
            .ok_or_else(|| "Failed to get response from future".to_string())?;
        let inner_result =
            outer_result.map_err(|e| format!("HTTP request failed (outer): {:?}", e))?;
        let response = inner_result.map_err(|e| format!("HTTP request failed (inner): {:?}", e))?;

        let status = response.status();
        if status < 200 || status >= 300 {
            return Err(format!("HTTP error: status {}", status));
        }

        let response_body = response
            .consume()
            .map_err(|_| "Failed to consume response".to_string())?;
        let mut response_bytes = Vec::new();
        let input_stream = response_body
            .stream()
            .map_err(|_| "Failed to get response stream".to_string())?;

        loop {
            match input_stream.blocking_read(8192) {
                Ok(chunk) => {
                    if chunk.is_empty() {
                        break;
                    }
                    response_bytes.extend_from_slice(&chunk);
                }
                Err(_) => break,
            }
        }

        let rpc_response: serde_json::Value = serde_json::from_slice(&response_bytes)
            .map_err(|e| format!("Failed to parse RPC response: {}", e))?;

        if let Some(error) = rpc_response.get("error") {
            return Err(format!("RPC error: {}", error));
        }

        let result = rpc_response
            .get("result")
            .and_then(|v| v.as_array())
            .ok_or("No result logs array in response")?;

        let mut logs = Vec::with_capacity(result.len());
        for log_value in result {
            let log: RpcLog = serde_json::from_value(log_value.clone())
                .map_err(|e| format!("Failed to parse log entry: {}", e))?;
            logs.push(log);
        }

        Ok(logs)
    }

    fn parse_hex_i64(hex_str: &str) -> i64 {
        let cleaned = hex_str.trim_start_matches("0x");
        i64::from_str_radix(cleaned, 16).unwrap_or(0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_address_from_topic() {
        let topic = "0x0000000000000000000000005aeda56215b167893e80b4fe645ba6d5bab767de";
        let addr = Component::extract_address_from_topic(topic).expect("address extracted");
        assert_eq!(addr, "0x5aeda56215b167893e80b4fe645ba6d5bab767de");

        let zero_topic = "0x0000000000000000000000000000000000000000000000000000000000000000";
        assert!(Component::extract_address_from_topic(zero_topic).is_none());
    }

    #[test]
    fn test_build_candidate_target_keys() {
        let keys = Component::build_candidate_target_keys(
            "ETH",
            "mainnet",
            "0xABCDEF",
            &Some("0x0000000000000000000000005aeda56215b167893e80b4fe645ba6d5bab767de".to_string()),
            &None,
            &None,
        );

        assert_eq!(keys.len(), 2);
        assert!(keys.contains(&"ETH:mainnet:0xabcdef".to_string()));
        assert!(
            keys.contains(&"ETH:mainnet:0x5aeda56215b167893e80b4fe645ba6d5bab767de".to_string())
        );
    }

    #[test]
    fn test_normalize_chain_id() {
        let header = BlockHeader {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            block_number: 1,
            block_hash: "0x1".to_string(),
            parent_hash: "0x0".to_string(),
            timestamp: 0,
            transaction_count: None,
            received_at: "2025-01-01T00:00:00Z".to_string(),
            provider_id: "provider".to_string(),
        };

        assert_eq!(Component::normalize_chain_id(&header), "ethereum_mainnet");
    }

    #[test]
    fn test_chain_id_numeric_fallback() {
        let header = BlockHeader {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            block_number: 1,
            block_hash: "0x1".to_string(),
            parent_hash: "0x0".to_string(),
            timestamp: 0,
            transaction_count: None,
            received_at: "2025-01-01T00:00:00Z".to_string(),
            provider_id: "provider".to_string(),
        };

        let chain_id =
            Component::chain_id_numeric(&header, Component::network_prefix(&header.network));
        assert_eq!(chain_id, 1);
    }

    #[test]
    fn test_normalize_hex_lowercases() {
        let value = "0xABCDEF";
        assert_eq!(Component::normalize_hex(value), "0xabcdef");
    }
}
