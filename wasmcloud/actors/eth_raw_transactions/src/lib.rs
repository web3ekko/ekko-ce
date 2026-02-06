//! # ETH Raw Transactions Actor
//!
//! WasmCloud actor that processes Ethereum newheads and fetches raw transactions from RPC nodes.
//! This actor receives blockchain newheads via NATS, fetches transaction details via HTTP RPC,
//! and publishes processed transactions back to NATS for downstream processing.

use serde::{Deserialize, Serialize};

// Generate WIT bindings for the processor world
wit_bindgen::generate!({ generate_all });

use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use wasmcloud::messaging::{consumer, types};

mod simplified_lib;

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

/// Raw transaction data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransaction {
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
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
    pub max_fee_per_gas: Option<String>,
    pub max_priority_fee_per_gas: Option<String>,
    pub transaction_type: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,
    pub processed_at: String,
    pub processor_id: String,
}

/// Main ETH Raw Transactions Actor
pub struct Component;

// Export Component for WasmCloud
export!(Component);

/// Get current UTC timestamp as ISO 8601 string using WASI clock interface
fn get_current_timestamp() -> String {
    let now = wasi::clocks::wall_clock::now();
    // Convert WASI datetime (seconds + nanoseconds) to ISO 8601 format
    let total_seconds = now.seconds;

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

/// Convert days since Unix epoch to year-month-day
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

    let month_days: [i64; 12] = if is_leap_year(year) {
        [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    } else {
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    };

    let mut month = 1u32;
    for days_in_month in month_days.iter() {
        if remaining_days < *days_in_month {
            break;
        }
        remaining_days -= *days_in_month;
        month += 1;
    }

    let day = remaining_days as u32 + 1;

    (year, month, day)
}

/// Check if a year is a leap year
fn is_leap_year(year: i32) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

impl MessageHandler for Component {
    /// Handle incoming NATS messages containing blockchain newheads
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        eprintln!("[ETH-RAW] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        eprintln!("[ETH-RAW] 📨 Received message on subject: {}", msg.subject);

        // Only process newheads messages for EVM chains
        if !msg.subject.starts_with("newheads.") || !msg.subject.ends_with(".evm") {
            eprintln!("[ETH-RAW] ⏭️  Skipping - not an EVM newheads message");
            return Ok(());
        }

        // Parse the block header from the message
        let block_header: BlockHeader = serde_json::from_slice(&msg.body).map_err(|e| {
            eprintln!("[ETH-RAW] ❌ Failed to parse block header: {}", e);
            format!("Failed to parse block header: {}", e)
        })?;

        eprintln!(
            "[ETH-RAW] 🔗 Processing newheads for block #{} on {}",
            block_header.block_number, block_header.chain_name
        );
        eprintln!(
            "[ETH-RAW]    Chain: {}/{}/{}",
            block_header.network, block_header.subnet, block_header.vm_type
        );
        eprintln!("[ETH-RAW]    Block hash: {}", block_header.block_hash);

        // Process the block header and fetch transactions
        Self::process_block_header(block_header)?;

        Ok(())
    }
}

impl Component {
    /// Process a block header by fetching its transactions and publishing them
    fn process_block_header(block_header: BlockHeader) -> Result<(), String> {
        // Get network configuration from Redis
        eprintln!("[ETH-RAW] 📋 Fetching network config from Redis...");
        let config = Self::get_network_config(&block_header)?;

        // Check if network is enabled
        if !config.enabled {
            eprintln!(
                "[ETH-RAW] ⚠️  Network {} is not enabled",
                block_header.network
            );
            return Err(format!("Network {} is not enabled", block_header.network));
        }

        // Check if RPC URL is configured
        if config.rpc_url.is_empty() {
            eprintln!(
                "[ETH-RAW] ❌ No RPC URL configured for {}",
                block_header.network
            );
            return Err(format!(
                "No RPC URL configured for {}",
                block_header.network
            ));
        }

        let rpc_url = &config.rpc_url;
        eprintln!("[ETH-RAW] 🌐 Fetching block from RPC: {}...", rpc_url);

        // Fetch block with transactions from RPC node
        let block_data = Self::fetch_block_with_transactions(rpc_url, &block_header.block_hash)?;

        // Extract transactions array from block data
        let transactions = block_data
            .get("transactions")
            .and_then(|v| v.as_array())
            .ok_or("No transactions array in block data")?;

        let tx_count = transactions.len();
        eprintln!(
            "[ETH-RAW] 📊 Fetched {} transactions from block #{}",
            tx_count, block_header.block_number
        );

        // Process and publish each transaction
        let mut published_count = 0;
        for (index, tx_data) in transactions.iter().enumerate() {
            let transaction = Self::parse_transaction(tx_data, &block_header, index as u32)?;
            Self::publish_transaction(transaction)?;
            published_count += 1;
        }

        eprintln!(
            "[ETH-RAW] ✅ Published {} raw transactions to transactions.raw.evm",
            published_count
        );
        eprintln!("[ETH-RAW] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        Ok(())
    }

    /// Get network configuration from Redis key-value store
    /// Uses Django's key format: blockchain:nodes:{network}-{subnet}
    fn get_network_config(block_header: &BlockHeader) -> Result<NetworkConfig, String> {
        let redis_key = format!(
            "blockchain:nodes:{}-{}",
            block_header.network, block_header.subnet
        );
        eprintln!("[ETH-RAW] Looking up Redis key: {}", redis_key);

        // Open default key-value store bucket
        let bucket = wasi::keyvalue::store::open("default")
            .map_err(|e| format!("Failed to open keyvalue bucket: {:?}", e))?;

        // Get configuration from store
        let config_bytes = bucket
            .get(&redis_key)
            .map_err(|e| format!("Failed to get key from store: {:?}", e))?
            .ok_or_else(|| format!("No configuration found for key: {}", redis_key))?;

        let config: NetworkConfig = serde_json::from_slice(&config_bytes)
            .map_err(|e| format!("Failed to parse network config: {}", e))?;

        Ok(config)
    }

    /// Parse URL into components for WASI HTTP request
    fn parse_url(url: &str) -> Result<(wasi::http::types::Scheme, String, String), String> {
        // Parse scheme
        let (scheme_str, rest) = url
            .split_once("://")
            .ok_or_else(|| format!("Invalid URL format: {}", url))?;

        let scheme = match scheme_str {
            "http" => wasi::http::types::Scheme::Http,
            "https" => wasi::http::types::Scheme::Https,
            _ => return Err(format!("Unsupported scheme: {}", scheme_str)),
        };

        // Parse authority (host[:port]) and path
        let (authority, path) = if let Some((auth, p)) = rest.split_once('/') {
            (auth.to_string(), format!("/{}", p))
        } else {
            (rest.to_string(), "/".to_string())
        };

        Ok((scheme, authority, path))
    }

    /// Fetch block with transactions using HTTP RPC call to Ethereum node
    fn fetch_block_with_transactions(
        rpc_url: &str,
        block_hash: &str,
    ) -> Result<serde_json::Value, String> {
        eprintln!("[ETH-RAW] fetch_block_with_transactions called");
        eprintln!("[ETH-RAW]   rpc_url: {}", rpc_url);
        eprintln!("[ETH-RAW]   block_hash: {}", block_hash);

        // Parse the RPC URL
        eprintln!("[ETH-RAW] Parsing URL...");
        let (scheme, authority, path) = match Self::parse_url(rpc_url) {
            Ok((s, a, p)) => {
                eprintln!(
                    "[ETH-RAW] URL parsed - scheme: {:?}, authority: {}, path: {}",
                    s, a, p
                );
                (s, a, p)
            }
            Err(e) => {
                eprintln!("[ETH-RAW] ERROR parsing URL: {}", e);
                return Err(e);
            }
        };

        // Construct JSON-RPC request
        let rpc_request = serde_json::json!({
            "jsonrpc": "2.0",
            "method": "eth_getBlockByHash",
            "params": [block_hash, true],  // true = include full transaction objects
            "id": 1
        });
        eprintln!("[ETH-RAW] JSON-RPC request: {}", rpc_request);

        let request_body = serde_json::to_vec(&rpc_request).map_err(|e| {
            let err = format!("Failed to serialize RPC request: {}", e);
            eprintln!("[ETH-RAW] ERROR: {}", err);
            err
        })?;
        eprintln!("[ETH-RAW] Request body size: {} bytes", request_body.len());

        // Create HTTP headers
        eprintln!("[ETH-RAW] Creating HTTP headers...");
        let headers = wasi::http::types::Fields::new();

        headers
            .set(
                &"content-type".to_string(),
                &vec!["application/json".as_bytes().to_vec()],
            )
            .map_err(|e| {
                let err = format!("Failed to set content-type header: {:?}", e);
                eprintln!("[ETH-RAW] ERROR: {}", err);
                err
            })?;
        headers
            .set(
                &"content-length".to_string(),
                &vec![request_body.len().to_string().as_bytes().to_vec()],
            )
            .map_err(|e| {
                let err = format!("Failed to set content-length header: {:?}", e);
                eprintln!("[ETH-RAW] ERROR: {}", err);
                err
            })?;
        eprintln!("[ETH-RAW] Headers set successfully");

        // Create outgoing HTTP request
        eprintln!("[ETH-RAW] Creating OutgoingRequest...");
        let request = wasi::http::types::OutgoingRequest::new(headers);

        // Set request properties
        eprintln!("[ETH-RAW] Setting request properties...");
        request
            .set_method(&wasi::http::types::Method::Post)
            .map_err(|_| {
                eprintln!("[ETH-RAW] ERROR: Failed to set request method");
                "Failed to set request method".to_string()
            })?;
        request.set_scheme(Some(&scheme)).map_err(|_| {
            eprintln!("[ETH-RAW] ERROR: Failed to set request scheme");
            "Failed to set request scheme".to_string()
        })?;
        request.set_authority(Some(&authority)).map_err(|_| {
            eprintln!("[ETH-RAW] ERROR: Failed to set request authority");
            "Failed to set request authority".to_string()
        })?;
        request.set_path_with_query(Some(&path)).map_err(|_| {
            eprintln!("[ETH-RAW] ERROR: Failed to set request path");
            "Failed to set request path".to_string()
        })?;
        eprintln!("[ETH-RAW] Request properties set successfully");

        // Get the request body and write to it
        eprintln!("[ETH-RAW] Getting request body...");
        let body = request.body().map_err(|_| {
            eprintln!("[ETH-RAW] ERROR: Failed to get request body");
            "Failed to get request body".to_string()
        })?;

        {
            eprintln!("[ETH-RAW] Writing to body output stream...");
            let output_stream = body.write().map_err(|_| {
                eprintln!("[ETH-RAW] ERROR: Failed to get body output stream");
                "Failed to get body output stream".to_string()
            })?;

            output_stream
                .blocking_write_and_flush(&request_body)
                .map_err(|e| {
                    let err = format!("Failed to write request body: {:?}", e);
                    eprintln!("[ETH-RAW] ERROR: {}", err);
                    err
                })?;
            eprintln!("[ETH-RAW] Body written successfully");
        }

        eprintln!("[ETH-RAW] Finishing request body...");
        wasi::http::types::OutgoingBody::finish(body, None).map_err(|_| {
            eprintln!("[ETH-RAW] ERROR: Failed to finish request body");
            "Failed to finish request body".to_string()
        })?;

        // Send the HTTP request
        eprintln!("[ETH-RAW] Sending HTTP request via wasi::http::outgoing_handler::handle...");
        let future_response = wasi::http::outgoing_handler::handle(request, None).map_err(|e| {
            let err = format!("Failed to send HTTP request: {:?}", e);
            eprintln!("[ETH-RAW] ERROR: {}", err);
            err
        })?;
        eprintln!("[ETH-RAW] HTTP request sent, waiting for response...");

        // Wait for the response to be ready by polling
        eprintln!("[ETH-RAW] Subscribing to response future...");
        let pollable = future_response.subscribe();
        eprintln!("[ETH-RAW] Polling for response...");
        wasi::io::poll::poll(&[&pollable]);
        eprintln!("[ETH-RAW] Poll complete, response should be ready");

        // Now get the response - it should be ready after polling
        // .get() returns option<result<result<incoming-response, error-code>>>
        let outer_result = future_response.get().ok_or_else(|| {
            eprintln!("[ETH-RAW] ERROR: Failed to get response from future after polling");
            "Failed to get response from future".to_string()
        })?;
        eprintln!("[ETH-RAW] Got outer result from future");

        // Unwrap outer result
        let inner_result = outer_result.map_err(|e| {
            let err = format!("HTTP request failed (outer): {:?}", e);
            eprintln!("[ETH-RAW] ERROR: {}", err);
            err
        })?;
        eprintln!("[ETH-RAW] Unwrapped outer result");

        // Unwrap inner result
        let incoming_response = inner_result.map_err(|e| {
            let err = format!("HTTP request failed (inner): {:?}", e);
            eprintln!("[ETH-RAW] ERROR: {}", err);
            err
        })?;
        eprintln!("[ETH-RAW] Got IncomingResponse");

        // Check response status
        let status = incoming_response.status();
        eprintln!("[ETH-RAW] Response status: {}", status);
        if status < 200 || status >= 300 {
            let err = format!("HTTP error: status {}", status);
            eprintln!("[ETH-RAW] ERROR: {}", err);
            return Err(err);
        }

        // Read response body
        eprintln!("[ETH-RAW] Consuming response body...");
        let response_body = incoming_response.consume().map_err(|_| {
            eprintln!("[ETH-RAW] ERROR: Failed to consume response body");
            "Failed to consume response body".to_string()
        })?;

        eprintln!("[ETH-RAW] Getting response stream...");
        let input_stream = response_body.stream().map_err(|_| {
            eprintln!("[ETH-RAW] ERROR: Failed to get response stream");
            "Failed to get response stream".to_string()
        })?;

        eprintln!("[ETH-RAW] Reading response chunks...");
        let mut response_bytes = Vec::new();
        loop {
            match input_stream.blocking_read(8192) {
                Ok(chunk) => {
                    if chunk.is_empty() {
                        eprintln!("[ETH-RAW] End of response stream");
                        break;
                    }
                    eprintln!("[ETH-RAW] Read {} bytes", chunk.len());
                    response_bytes.extend_from_slice(&chunk);
                }
                Err(e) => {
                    eprintln!("[ETH-RAW] Read error (stopping): {:?}", e);
                    break;
                }
            }
        }
        eprintln!(
            "[ETH-RAW] Total response size: {} bytes",
            response_bytes.len()
        );

        // Parse JSON-RPC response
        eprintln!("[ETH-RAW] Parsing JSON response...");
        let rpc_response: serde_json::Value =
            serde_json::from_slice(&response_bytes).map_err(|e| {
                let err = format!("Failed to parse JSON response: {}", e);
                eprintln!("[ETH-RAW] ERROR: {}", err);
                err
            })?;
        eprintln!("[ETH-RAW] JSON parsed successfully");

        // Check for JSON-RPC error
        if let Some(error) = rpc_response.get("error") {
            let err = format!("RPC error: {}", error);
            eprintln!("[ETH-RAW] ERROR: {}", err);
            return Err(err);
        }

        // Extract result
        let result = rpc_response
            .get("result")
            .ok_or_else(|| {
                eprintln!("[ETH-RAW] ERROR: No result in RPC response");
                "No result in RPC response".to_string()
            })?
            .clone();
        eprintln!("[ETH-RAW] Successfully extracted result from RPC response");

        Ok(result)
    }

    /// Parse a raw transaction from Ethereum RPC response into our format
    fn parse_transaction(
        tx_data: &serde_json::Value,
        block_header: &BlockHeader,
        index: u32,
    ) -> Result<RawTransaction, String> {
        Ok(RawTransaction {
            network: block_header.network.clone(),
            subnet: block_header.subnet.clone(),
            vm_type: block_header.vm_type.clone(),
            transaction_hash: tx_data
                .get("hash")
                .and_then(|v| v.as_str())
                .ok_or("Missing transaction hash")?
                .to_string(),
            block_number: block_header.block_number,
            block_hash: tx_data
                .get("blockHash")
                .and_then(|v| v.as_str())
                .unwrap_or(&block_header.block_hash)
                .to_string(),
            block_timestamp: block_header.timestamp,
            transaction_index: index,
            from_address: tx_data
                .get("from")
                .and_then(|v| v.as_str())
                .ok_or("Missing from address")?
                .to_string(),
            to_address: tx_data
                .get("to")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            value: tx_data
                .get("value")
                .and_then(|v| v.as_str())
                .unwrap_or("0x0")
                .to_string(),
            gas_limit: Self::parse_hex_u64(
                tx_data
                    .get("gas")
                    .and_then(|v| v.as_str())
                    .unwrap_or("0x5208"),
            ),
            gas_price: tx_data
                .get("gasPrice")
                .and_then(|v| v.as_str())
                .unwrap_or("0x0")
                .to_string(),
            input_data: tx_data
                .get("input")
                .and_then(|v| v.as_str())
                .unwrap_or("0x")
                .to_string(),
            nonce: Self::parse_hex_u64(
                tx_data
                    .get("nonce")
                    .and_then(|v| v.as_str())
                    .unwrap_or("0x0"),
            ),
            chain_id: tx_data
                .get("chainId")
                .and_then(|v| v.as_str())
                .unwrap_or("0x0")
                .to_string(),
            max_fee_per_gas: tx_data
                .get("maxFeePerGas")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            max_priority_fee_per_gas: tx_data
                .get("maxPriorityFeePerGas")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            transaction_type: tx_data
                .get("type")
                .and_then(|v| v.as_str())
                .and_then(|s| Self::parse_hex_u8(s)),
            v: tx_data
                .get("v")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            r: tx_data
                .get("r")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            s: tx_data
                .get("s")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            processed_at: get_current_timestamp(),
            processor_id: "eth-raw-transactions-actor".to_string(),
        })
    }

    /// Publish processed transaction to NATS
    fn publish_transaction(transaction: RawTransaction) -> Result<(), String> {
        let tx_payload = serde_json::to_vec(&transaction)
            .map_err(|e| format!("Failed to serialize transaction: {}", e))?;

        // Publish to transactions.raw.evm topic
        let msg = types::BrokerMessage {
            subject: "transactions.raw.evm".to_string(),
            body: tx_payload,
            reply_to: None,
        };

        consumer::publish(&msg).map_err(|e| format!("Failed to publish message: {:?}", e))?;

        Ok(())
    }

    /// Parse hexadecimal string to u64
    fn parse_hex_u64(hex_str: &str) -> u64 {
        let cleaned = hex_str.trim_start_matches("0x");
        u64::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Parse hexadecimal string to u8
    fn parse_hex_u8(hex_str: &str) -> Option<u8> {
        let cleaned = hex_str.trim_start_matches("0x");
        u8::from_str_radix(cleaned, 16).ok()
    }
}

#[cfg(test)]
mod tests;
