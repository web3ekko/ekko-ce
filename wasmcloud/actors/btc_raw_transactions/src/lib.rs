//! # BTC Raw Transactions Actor
//!
//! WasmCloud actor that processes Bitcoin and UTXO blockchain newheads and fetches raw transactions.
//! This actor receives blockchain newheads via NATS messaging, fetches transaction details via HTTP RPC,
//! and publishes processed transactions back to NATS for downstream processing.

use serde::{Deserialize, Serialize};

// Generate WIT bindings for the btc-raw-transactions world
wit_bindgen::generate!({ generate_all });

use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use wasmcloud::messaging::{consumer, types};

/// Block header from newheads provider
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockHeader {
    pub network: String,    // e.g., "bitcoin", "litecoin", "dogecoin"
    pub subnet: String,     // e.g., "mainnet", "testnet"
    pub vm_type: String,    // "utxo"
    pub chain_id: String,   // e.g., "bitcoin-mainnet"
    pub chain_name: String, // e.g., "Bitcoin Mainnet"
    pub block_number: u64,
    pub block_hash: String,
    pub parent_hash: String,
    pub timestamp: u64,
    pub transaction_count: Option<u32>,
    pub received_at: String, // ISO timestamp
    pub provider_id: String,
}

/// Network configuration from Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    pub rpc_urls: Vec<String>,
    pub ws_urls: Vec<String>,
    pub chain_id: Option<u64>,
    pub enabled: bool,
}

/// Raw UTXO transaction payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransaction {
    // Network context (inherited from block header)
    pub network: String,
    pub subnet: String,
    pub vm_type: String,

    // Transaction data
    pub transaction_hash: String,
    pub block_number: u64,
    pub transaction_index: u32,
    pub version: u32,
    pub lock_time: u32,
    pub size: u32,
    pub weight: Option<u32>, // For SegWit transactions

    // UTXO-specific data
    pub inputs: Vec<TransactionInput>,
    pub outputs: Vec<TransactionOutput>,
    pub fee: Option<u64>, // Calculated fee in satoshis

    // Processing metadata
    pub processed_at: String, // ISO timestamp
    pub processor_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionInput {
    pub previous_output_hash: String,
    pub previous_output_index: u32,
    pub script_sig: String,
    pub sequence: u32,
    pub witness: Option<Vec<String>>, // For SegWit
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionOutput {
    pub value: u64, // Value in satoshis
    pub script_pubkey: String,
    pub address: Option<String>, // Decoded address if possible
}

/// Raw transaction message wrapper
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransactionMessage {
    /// Source network (bitcoin, litecoin, dogecoin, etc.)
    pub network: String,
    /// Raw transaction data as JSON string
    pub transactions: String,
    /// Processing metadata
    pub metadata: Option<ProcessingMetadata>,
}

/// Processing metadata for transaction batches
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingMetadata {
    /// Batch ID for tracking
    pub batch_id: String,
    /// Block number/height
    pub block_number: u64,
    /// Timestamp of processing
    pub timestamp: u64,
    /// Source identifier
    pub source: String,
}

/// Main BTC Raw Transactions Actor Component
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    /// Handle incoming NATS messages containing blockchain newheads
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        // Only process newheads messages for UTXO chains
        if !msg.subject.starts_with("newheads.") || !msg.subject.ends_with(".utxo") {
            return Ok(());
        }

        eprintln!(
            "BTC Raw Transactions received message on subject: {}",
            msg.subject
        );

        // Parse the block header from the message
        let block_header: BlockHeader = serde_json::from_slice(&msg.body)
            .map_err(|e| format!("Failed to parse block header: {}", e))?;

        // Process the block header and fetch transactions
        Self::process_block_header(block_header)?;

        Ok(())
    }
}

impl Component {
    /// Process a block header by fetching its transactions and publishing them
    fn process_block_header(block_header: BlockHeader) -> Result<(), String> {
        eprintln!(
            "Processing UTXO block #{} from {}.{}",
            block_header.block_number, block_header.network, block_header.subnet
        );

        // Get network configuration from Redis
        let config = Self::get_network_config(&block_header)?;

        if !config.enabled {
            return Err(format!(
                "Network {}:{}:{} is disabled",
                block_header.network, block_header.subnet, block_header.vm_type
            ));
        }

        // Get the first available RPC URL
        let rpc_url = config
            .rpc_urls
            .first()
            .ok_or_else(|| "No RPC URLs configured for network".to_string())?;

        // Fetch block with transactions from Bitcoin RPC
        let transactions = Self::fetch_block_transactions(rpc_url, &block_header)?;

        eprintln!(
            "Fetched {} UTXO transactions for block #{}",
            transactions.len(),
            block_header.block_number
        );

        // Create transaction message wrapper
        let tx_message = RawTransactionMessage {
            network: format!(
                "{}.{}.{}",
                block_header.network, block_header.subnet, block_header.vm_type
            ),
            transactions: serde_json::to_string(&transactions)
                .map_err(|e| format!("Failed to serialize transactions: {}", e))?,
            metadata: Some(ProcessingMetadata {
                batch_id: format!("{}_{}", block_header.block_hash, block_header.block_number),
                block_number: block_header.block_number,
                timestamp: block_header.timestamp,
                source: "btc-raw-transactions-actor".to_string(),
            }),
        };

        // Publish the batch to NATS
        Self::publish_transaction_batch(tx_message)?;

        Ok(())
    }

    /// Get network configuration from Redis key-value store
    fn get_network_config(block_header: &BlockHeader) -> Result<NetworkConfig, String> {
        let redis_key = format!(
            "nodes:{}:{}:{}",
            block_header.network, block_header.subnet, block_header.vm_type
        );

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

    /// Get fallback RPC URL for development
    fn get_fallback_rpc_url(network: &str, subnet: &str) -> String {
        match (network, subnet) {
            ("bitcoin", "mainnet") => "https://bitcoin-mainnet.example.com".to_string(),
            ("bitcoin", "testnet") => "https://bitcoin-testnet.example.com".to_string(),
            ("litecoin", "mainnet") => "https://litecoin-mainnet.example.com".to_string(),
            ("dogecoin", "mainnet") => "https://dogecoin-mainnet.example.com".to_string(),
            _ => format!("https://{}-{}.example.com", network, subnet),
        }
    }

    /// Parse URL into components for WASI HTTP request
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

    /// Send a JSON POST request using WASI HTTP and return raw response bytes
    fn post_json(url: &str, body: &str) -> Result<Vec<u8>, String> {
        let (scheme, authority, path) = Self::parse_url(url)?;

        let headers = wasi::http::types::Fields::new();
        headers
            .set(
                &"content-type".to_string(),
                &vec![b"application/json".to_vec()],
            )
            .map_err(|e| format!("Failed to set content-type header: {:?}", e))?;
        headers
            .set(
                &"content-length".to_string(),
                &vec![body.len().to_string().into_bytes()],
            )
            .map_err(|e| format!("Failed to set content-length header: {:?}", e))?;

        let request = wasi::http::types::OutgoingRequest::new(headers);
        request
            .set_method(&wasi::http::types::Method::Post)
            .map_err(|_| "Failed to set request method".to_string())?;
        request
            .set_scheme(Some(&scheme))
            .map_err(|_| "Failed to set request scheme".to_string())?;
        request
            .set_authority(Some(&authority))
            .map_err(|_| "Failed to set request authority".to_string())?;
        request
            .set_path_with_query(Some(&path))
            .map_err(|_| "Failed to set request path".to_string())?;

        let request_body = request
            .body()
            .map_err(|_| "Failed to get request body".to_string())?;
        {
            let output_stream = request_body
                .write()
                .map_err(|_| "Failed to get body output stream".to_string())?;
            output_stream
                .blocking_write_and_flush(body.as_bytes())
                .map_err(|e| format!("Failed to write request body: {:?}", e))?;
        }
        wasi::http::types::OutgoingBody::finish(request_body, None)
            .map_err(|_| "Failed to finish request body".to_string())?;

        let future_response = wasi::http::outgoing_handler::handle(request, None)
            .map_err(|e| format!("Failed to send HTTP request: {:?}", e))?;
        let pollable = future_response.subscribe();
        wasi::io::poll::poll(&[&pollable]);

        let outer_result = future_response
            .get()
            .ok_or_else(|| "Failed to get response from future".to_string())?;
        let inner_result =
            outer_result.map_err(|e| format!("HTTP request failed (outer): {:?}", e))?;
        let incoming_response =
            inner_result.map_err(|e| format!("HTTP request failed (inner): {:?}", e))?;

        let status = incoming_response.status();
        if status < 200 || status >= 300 {
            return Err(format!("HTTP error: status {}", status));
        }

        let response_body = incoming_response
            .consume()
            .map_err(|_| "Failed to consume response body".to_string())?;
        let input_stream = response_body
            .stream()
            .map_err(|_| "Failed to get response stream".to_string())?;

        let mut response_bytes = Vec::new();
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

        Ok(response_bytes)
    }

    /// Fetch block with transactions using HTTP RPC call to Bitcoin node
    fn fetch_block_transactions(
        rpc_url: &str,
        block_header: &BlockHeader,
    ) -> Result<Vec<RawTransaction>, String> {
        // Prepare JSON-RPC request for getblock with transaction details
        let rpc_request = serde_json::json!({
            "jsonrpc": "1.0",
            "method": "getblock",
            "params": [block_header.block_hash, 2], // 2 = include full transaction objects
            "id": 1
        });

        let request_body = serde_json::to_string(&rpc_request)
            .map_err(|e| format!("Failed to serialize RPC request: {}", e))?;

        // Parse JSON-RPC response
        let response_bytes = Self::post_json(rpc_url, &request_body)?;
        let rpc_response: serde_json::Value = serde_json::from_slice(&response_bytes)
            .map_err(|e| format!("Failed to parse JSON-RPC response: {}", e))?;

        if let Some(error) = rpc_response.get("error") {
            return Err(format!("RPC error: {}", error));
        }

        let block_data = rpc_response
            .get("result")
            .ok_or_else(|| "No result in RPC response".to_string())?;

        // Extract and process each transaction in the block
        let mut transactions = Vec::new();
        if let Some(tx_array) = block_data.get("tx").and_then(|v| v.as_array()) {
            for (index, tx_data) in tx_array.iter().enumerate() {
                let raw_tx = Self::parse_transaction(tx_data, block_header, index as u32)?;
                transactions.push(raw_tx);
            }
        }

        Ok(transactions)
    }

    /// Parse a raw transaction from Bitcoin RPC response into our format
    fn parse_transaction(
        tx_data: &serde_json::Value,
        block_header: &BlockHeader,
        index: u32,
    ) -> Result<RawTransaction, String> {
        // Parse inputs
        let mut inputs = Vec::new();
        if let Some(vin_array) = tx_data.get("vin").and_then(|v| v.as_array()) {
            for vin in vin_array {
                let input = TransactionInput {
                    previous_output_hash: vin
                        .get("txid")
                        .and_then(|v| v.as_str())
                        .unwrap_or(
                            "0000000000000000000000000000000000000000000000000000000000000000",
                        )
                        .to_string(),
                    previous_output_index: vin.get("vout").and_then(|v| v.as_u64()).unwrap_or(0)
                        as u32,
                    script_sig: vin
                        .get("scriptSig")
                        .and_then(|v| v.get("hex"))
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string(),
                    sequence: vin.get("sequence").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
                    witness: vin
                        .get("txinwitness")
                        .and_then(|v| v.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|v| v.as_str())
                                .map(|s| s.to_string())
                                .collect()
                        }),
                };
                inputs.push(input);
            }
        }

        // Parse outputs
        let mut outputs = Vec::new();
        if let Some(vout_array) = tx_data.get("vout").and_then(|v| v.as_array()) {
            for vout in vout_array {
                let output = TransactionOutput {
                    value: (vout.get("value").and_then(|v| v.as_f64()).unwrap_or(0.0)
                        * 100_000_000.0) as u64, // Convert BTC to satoshis
                    script_pubkey: vout
                        .get("scriptPubKey")
                        .and_then(|v| v.get("hex"))
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string(),
                    address: vout
                        .get("scriptPubKey")
                        .and_then(|v| v.get("address"))
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string()),
                };
                outputs.push(output);
            }
        }

        Ok(RawTransaction {
            network: block_header.network.clone(),
            subnet: block_header.subnet.clone(),
            vm_type: block_header.vm_type.clone(),
            transaction_hash: tx_data
                .get("txid")
                .and_then(|v| v.as_str())
                .ok_or("Missing transaction hash")?
                .to_string(),
            block_number: block_header.block_number,
            transaction_index: index,
            version: tx_data.get("version").and_then(|v| v.as_u64()).unwrap_or(1) as u32,
            lock_time: tx_data
                .get("locktime")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as u32,
            size: tx_data.get("size").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
            weight: tx_data
                .get("weight")
                .and_then(|v| v.as_u64())
                .map(|w| w as u32),
            inputs,
            outputs,
            fee: None, // Will be calculated if needed
            processed_at: chrono::Utc::now().to_rfc3339(),
            processor_id: "btc-raw-transactions-actor".to_string(),
        })
    }

    /// Publish processed transaction batch to NATS
    fn publish_transaction_batch(message: RawTransactionMessage) -> Result<(), String> {
        let tx_payload = serde_json::to_vec(&message)
            .map_err(|e| format!("Failed to serialize transaction message: {}", e))?;

        let msg = types::BrokerMessage {
            subject: "transactions.raw.utxo".to_string(),
            body: tx_payload,
            reply_to: None,
        };

        consumer::publish(&msg)
            .map_err(|e| format!("Failed to publish transaction batch: {:?}", e))?;

        eprintln!(
            "Published UTXO transaction batch for network: {}",
            message.network
        );
        Ok(())
    }
}

#[cfg(not(target_arch = "wasm32"))]
fn main() {
    // This function is never called in the WASM build
    println!("BTC raw transactions actor - use as WASM component");
}
