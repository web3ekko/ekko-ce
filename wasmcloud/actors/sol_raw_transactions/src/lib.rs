//! # SVM Raw Transactions Actor
//!
//! WasmCloud actor that processes SVM blockchain newheads and fetches raw transactions from RPC nodes.
//! This actor receives blockchain newheads via NATS, fetches transaction details via HTTP RPC,
//! and publishes processed transactions back to NATS for downstream processing.

use serde::{Deserialize, Serialize};

// Generate WIT bindings for the processor world
wit_bindgen::generate!({ generate_all });

use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use wasmcloud::messaging::{consumer, types};

/// Block header from newheads provider
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockHeader {
    pub network: String,     // e.g., "solana"
    pub subnet: String,      // e.g., "mainnet", "devnet", "testnet"
    pub vm_type: String,     // "svm"
    pub chain_id: String,    // e.g., "solana-mainnet"
    pub chain_name: String,  // e.g., "Solana Mainnet"
    pub block_number: u64,   // Slot number in Solana
    pub block_hash: String,  // Block hash
    pub parent_hash: String, // Parent block hash
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
    pub program_id: Option<String>, // SVM-specific: program addresses
    pub enabled: bool,
}

/// Raw SVM transaction data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransaction {
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub transaction_hash: String, // Transaction signature in Solana
    pub block_number: u64,        // Slot number
    pub transaction_index: u32,

    // SVM-specific transaction data
    pub signatures: Vec<String>,
    pub message: TransactionMessage,
    pub meta: Option<TransactionMeta>,

    // Processing metadata
    pub processed_at: String,
    pub processor_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionMessage {
    pub account_keys: Vec<String>,
    pub header: MessageHeader,
    pub instructions: Vec<CompiledInstruction>,
    pub recent_blockhash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageHeader {
    pub num_required_signatures: u8,
    pub num_readonly_signed_accounts: u8,
    pub num_readonly_unsigned_accounts: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompiledInstruction {
    pub program_id_index: u8,
    pub accounts: Vec<u8>,
    pub data: String, // Base64 encoded instruction data
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionMeta {
    pub err: Option<serde_json::Value>,
    pub fee: u64,
    pub pre_balances: Vec<u64>,
    pub post_balances: Vec<u64>,
    pub inner_instructions: Option<Vec<serde_json::Value>>,
    pub log_messages: Option<Vec<String>>,
    pub pre_token_balances: Option<Vec<serde_json::Value>>,
    pub post_token_balances: Option<Vec<serde_json::Value>>,
    pub rewards: Option<Vec<serde_json::Value>>,
}

/// Main SVM Raw Transactions Actor
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    /// Handle incoming NATS messages containing blockchain newheads
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        // Only process newheads messages for SVM chains
        if !msg.subject.starts_with("newheads.") || !msg.subject.ends_with(".svm") {
            return Ok(());
        }

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

        // Fetch block with transactions from Solana RPC
        let block_data = Self::fetch_block_with_transactions(rpc_url, block_header.block_number)?;

        // Extract and process each transaction in the block
        if let Some(transactions) = block_data.get("transactions").and_then(|v| v.as_array()) {
            for (index, tx_data) in transactions.iter().enumerate() {
                let raw_tx = Self::parse_transaction(tx_data, &block_header, index as u32)?;

                // Publish the processed transaction to NATS
                Self::publish_transaction(raw_tx)?;
            }
        }

        Ok(())
    }

    /// Get network configuration from Redis key-value store
    fn get_network_config(block_header: &BlockHeader) -> Result<NetworkConfig, String> {
        let redis_key = format!(
            "nodes:{}:{}:{}",
            block_header.network, block_header.subnet, block_header.vm_type
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

    /// Fetch block with transactions using HTTP RPC call to Solana node
    fn fetch_block_with_transactions(
        rpc_url: &str,
        slot: u64,
    ) -> Result<serde_json::Value, String> {
        // Prepare JSON-RPC request for getBlock
        let rpc_request = serde_json::json!({
            "jsonrpc": "2.0",
            "method": "getBlock",
            "params": [slot, {"encoding": "json", "transactionDetails": "full"}],
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

        rpc_response
            .get("result")
            .ok_or_else(|| "No result in RPC response".to_string())
            .cloned()
    }

    /// Parse a raw transaction from Solana RPC response into our format
    fn parse_transaction(
        tx_data: &serde_json::Value,
        block_header: &BlockHeader,
        index: u32,
    ) -> Result<RawTransaction, String> {
        // Extract transaction signature (hash)
        let signatures = tx_data
            .get("transaction")
            .and_then(|t| t.get("signatures"))
            .and_then(|s| s.as_array())
            .ok_or("Missing transaction signatures")?;

        let transaction_hash = signatures
            .first()
            .and_then(|s| s.as_str())
            .ok_or("Missing transaction signature")?;

        // Extract message details
        let message = tx_data
            .get("transaction")
            .and_then(|t| t.get("message"))
            .ok_or("Missing transaction message")?;

        Ok(RawTransaction {
            network: block_header.network.clone(),
            subnet: block_header.subnet.clone(),
            vm_type: block_header.vm_type.clone(),
            transaction_hash: transaction_hash.to_string(),
            block_number: block_header.block_number,
            transaction_index: index,
            signatures: signatures
                .iter()
                .filter_map(|s| s.as_str())
                .map(|s| s.to_string())
                .collect(),
            message: Self::parse_message(message)?,
            meta: tx_data
                .get("meta")
                .map(|m| Self::parse_meta(m))
                .transpose()?,
            processed_at: chrono::Utc::now().to_rfc3339(),
            processor_id: "svm-raw-transactions-actor".to_string(),
        })
    }

    /// Parse transaction message
    fn parse_message(message: &serde_json::Value) -> Result<TransactionMessage, String> {
        Ok(TransactionMessage {
            account_keys: message
                .get("accountKeys")
                .and_then(|keys| keys.as_array())
                .unwrap_or(&vec![])
                .iter()
                .filter_map(|k| k.as_str())
                .map(|k| k.to_string())
                .collect(),
            header: MessageHeader {
                num_required_signatures: message
                    .get("header")
                    .and_then(|h| h.get("numRequiredSignatures"))
                    .and_then(|n| n.as_u64())
                    .unwrap_or(0) as u8,
                num_readonly_signed_accounts: message
                    .get("header")
                    .and_then(|h| h.get("numReadonlySignedAccounts"))
                    .and_then(|n| n.as_u64())
                    .unwrap_or(0) as u8,
                num_readonly_unsigned_accounts: message
                    .get("header")
                    .and_then(|h| h.get("numReadonlyUnsignedAccounts"))
                    .and_then(|n| n.as_u64())
                    .unwrap_or(0) as u8,
            },
            instructions: message
                .get("instructions")
                .and_then(|inst| inst.as_array())
                .unwrap_or(&vec![])
                .iter()
                .filter_map(|i| Self::parse_instruction(i).ok())
                .collect(),
            recent_blockhash: message
                .get("recentBlockhash")
                .and_then(|h| h.as_str())
                .unwrap_or("")
                .to_string(),
        })
    }

    /// Parse transaction instruction
    fn parse_instruction(instruction: &serde_json::Value) -> Result<CompiledInstruction, String> {
        Ok(CompiledInstruction {
            program_id_index: instruction
                .get("programIdIndex")
                .and_then(|i| i.as_u64())
                .unwrap_or(0) as u8,
            accounts: instruction
                .get("accounts")
                .and_then(|a| a.as_array())
                .unwrap_or(&vec![])
                .iter()
                .filter_map(|a| a.as_u64())
                .map(|a| a as u8)
                .collect(),
            data: instruction
                .get("data")
                .and_then(|d| d.as_str())
                .unwrap_or("")
                .to_string(),
        })
    }

    /// Parse transaction meta
    fn parse_meta(meta: &serde_json::Value) -> Result<TransactionMeta, String> {
        Ok(TransactionMeta {
            err: meta.get("err").cloned(),
            fee: meta.get("fee").and_then(|f| f.as_u64()).unwrap_or(0),
            pre_balances: meta
                .get("preBalances")
                .and_then(|b| b.as_array())
                .unwrap_or(&vec![])
                .iter()
                .filter_map(|b| b.as_u64())
                .collect(),
            post_balances: meta
                .get("postBalances")
                .and_then(|b| b.as_array())
                .unwrap_or(&vec![])
                .iter()
                .filter_map(|b| b.as_u64())
                .collect(),
            inner_instructions: meta
                .get("innerInstructions")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().cloned().collect()),
            log_messages: meta
                .get("logMessages")
                .and_then(|l| l.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|l| l.as_str())
                        .map(|l| l.to_string())
                        .collect()
                }),
            pre_token_balances: meta
                .get("preTokenBalances")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().cloned().collect()),
            post_token_balances: meta
                .get("postTokenBalances")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().cloned().collect()),
            rewards: meta
                .get("rewards")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().cloned().collect()),
        })
    }

    /// Publish processed transaction to NATS
    fn publish_transaction(transaction: RawTransaction) -> Result<(), String> {
        let tx_payload = serde_json::to_vec(&transaction)
            .map_err(|e| format!("Failed to serialize transaction: {}", e))?;

        // Publish to transactions.raw.svm topic
        let msg = types::BrokerMessage {
            subject: "transactions.raw.svm".to_string(),
            body: tx_payload,
            reply_to: None,
        };

        consumer::publish(&msg).map_err(|e| format!("Failed to publish message: {:?}", e))?;

        Ok(())
    }
}
