//! # Ethereum Client Implementation
//!
//! Implements the BlockchainClient trait for Ethereum and EVM-compatible chains.

use anyhow::{anyhow, Result};
use futures_util::{SinkExt, StreamExt};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock};
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{debug, error, info, warn};

use crate::traits::{
    current_timestamp, parse_hex_u64, BlockHeader, BlockchainClient, ChainConfig, ConnectionStats,
};

/// Ethereum-specific block header from JSON-RPC
#[derive(Debug, Deserialize)]
struct EthBlockHeader {
    number: String,
    hash: String,
    #[serde(rename = "parentHash")]
    parent_hash: String,
    timestamp: String,
    difficulty: Option<String>,
    #[serde(rename = "gasLimit")]
    gas_limit: Option<String>,
    #[serde(rename = "gasUsed")]
    gas_used: Option<String>,
    miner: Option<String>,
    #[serde(rename = "extraData")]
    extra_data: Option<String>,
}

/// Ethereum JSON-RPC response structure
#[derive(Debug, Deserialize)]
struct JsonRpcResponse<T> {
    id: u64,
    jsonrpc: String,
    result: Option<T>,
    error: Option<JsonRpcError>,
}

#[derive(Debug, Deserialize)]
struct JsonRpcError {
    code: i32,
    message: String,
}

/// Ethereum newheads subscription response
#[derive(Debug, Deserialize)]
struct NewheadsNotification {
    jsonrpc: String,
    method: String,
    params: NewheadsParams,
}

#[derive(Debug, Deserialize)]
struct NewheadsParams {
    subscription: String,
    result: EthBlockHeader,
}

/// Ethereum client for connecting to Ethereum and EVM-compatible chains
pub struct EthereumClient {
    config: ChainConfig,
    stats: Arc<RwLock<ConnectionStats>>,
    http_client: reqwest::Client,
    nats_client: Option<async_nats::Client>,
}

impl std::fmt::Debug for EthereumClient {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("EthereumClient")
            .field("config", &self.config)
            .field("stats", &"<ConnectionStats>")
            .field("http_client", &"<reqwest::Client>")
            .field("nats_client", &self.nats_client.is_some())
            .finish()
    }
}

impl EthereumClient {
    /// Create a new Ethereum client
    pub async fn new(config: ChainConfig) -> Result<Self> {
        let http_client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()?;

        let client = Self {
            config,
            stats: Arc::new(RwLock::new(ConnectionStats::default())),
            http_client,
            nats_client: None, // Will be set by the provider
        };

        // Test the connection
        client.test_connection().await?;

        Ok(client)
    }

    /// Create a new Ethereum client with NATS integration
    pub async fn new_with_nats(
        config: ChainConfig,
        nats_client: async_nats::Client,
    ) -> Result<Self> {
        let http_client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()?;

        let client = Self {
            config,
            stats: Arc::new(RwLock::new(ConnectionStats::default())),
            http_client,
            nats_client: Some(nats_client),
        };

        // Test the connection
        client.test_connection().await?;

        Ok(client)
    }

    /// Convert Ethereum block header to common format with network context
    fn convert_block_header(&self, eth_header: EthBlockHeader) -> Result<BlockHeader> {
        let block_number = parse_hex_u64(&eth_header.number)?;
        let timestamp = parse_hex_u64(&eth_header.timestamp)?;

        let gas_limit = eth_header
            .gas_limit
            .as_ref()
            .and_then(|s| parse_hex_u64(s).ok());

        let gas_used = eth_header
            .gas_used
            .as_ref()
            .and_then(|s| parse_hex_u64(s).ok());

        // Create network-specific data
        let mut network_specific = serde_json::Map::new();
        if let Some(ref difficulty) = eth_header.difficulty {
            network_specific.insert(
                "difficulty".to_string(),
                serde_json::Value::String(difficulty.clone()),
            );
        }
        if let Some(ref extra_data) = eth_header.extra_data {
            network_specific.insert(
                "extraData".to_string(),
                serde_json::Value::String(extra_data.clone()),
            );
        }

        Ok(BlockHeader {
            network: self.config.network.clone(),
            subnet: self.config.subnet.clone(),
            vm_type: self.config.vm_type.clone(),
            chain_id: self.config.chain_id.clone(),
            chain_name: self.config.chain_name.clone(),
            block_number,
            block_hash: eth_header.hash,
            parent_hash: eth_header.parent_hash,
            timestamp,
            difficulty: eth_header.difficulty,
            gas_limit,
            gas_used,
            miner: eth_header.miner,
            extra_data: eth_header.extra_data,
            network_specific: serde_json::Value::Object(network_specific),
            received_at: chrono::Utc::now(),
            provider_id: format!("ethereum-client-{}", self.config.chain_id),
            raw_data: None, // Could store the original JSON here if needed
            rpc_url: Some(self.config.rpc_url.clone()),
            ws_url: Some(self.config.ws_url.clone()),
        })
    }

    /// Make an HTTP JSON-RPC call
    async fn rpc_call<T>(&self, method: &str, params: Value) -> Result<T>
    where
        T: for<'de> Deserialize<'de>,
    {
        let request_body = json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        });

        let response = self
            .http_client
            .post(&self.config.rpc_url)
            .json(&request_body)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow!("HTTP error: {}", response.status()));
        }

        let rpc_response: JsonRpcResponse<T> = response.json().await?;

        if let Some(error) = rpc_response.error {
            return Err(anyhow!("RPC error {}: {}", error.code, error.message));
        }

        rpc_response
            .result
            .ok_or_else(|| anyhow!("No result in RPC response"))
    }
}

#[async_trait::async_trait]
impl BlockchainClient for EthereumClient {
    async fn subscribe_newheads(&self) -> Result<mpsc::UnboundedReceiver<BlockHeader>> {
        let (sender, receiver) = mpsc::unbounded_channel();

        // Connect to WebSocket
        let (ws_stream, _) = connect_async(&self.config.ws_url)
            .await
            .map_err(|e| anyhow!("Failed to connect to WebSocket: {}", e))?;

        let (mut ws_sender, mut ws_receiver) = ws_stream.split();

        // Subscribe to newHeads
        let subscribe_msg = json!({
            "jsonrpc": "2.0",
            "method": "eth_subscribe",
            "params": ["newHeads"],
            "id": 1
        });

        ws_sender
            .send(Message::Text(subscribe_msg.to_string()))
            .await
            .map_err(|e| anyhow!("Failed to send subscription message: {}", e))?;

        info!(
            "Subscribed to newHeads for chain '{}'",
            self.config.chain_id
        );

        // Update connection stats
        {
            let mut stats = self.stats.write().await;
            stats.connected = true;
            stats.connected_at = Some(current_timestamp());
        }

        // Spawn task to handle incoming messages
        let chain_id = self.config.chain_id.clone();
        let chain_name = self.config.chain_name.clone();
        let network = self.config.network.clone();
        let subnet = self.config.subnet.clone();
        let vm_type = self.config.vm_type.clone();
        let rpc_url = self.config.rpc_url.clone();
        let ws_url = self.config.ws_url.clone();
        let stats = self.stats.clone();
        let nats_client = self.nats_client.clone();

        tokio::spawn(async move {
            while let Some(msg) = ws_receiver.next().await {
                match msg {
                    Ok(Message::Text(text)) => {
                        debug!("Received WebSocket message: {}", text);

                        // Try to parse as newheads notification
                        if let Ok(notification) =
                            serde_json::from_str::<NewheadsNotification>(&text)
                        {
                            if notification.method == "eth_subscription" {
                                // Convert to common block header format
                                let eth_header = notification.params.result;

                                if let Ok(block_number) = parse_hex_u64(&eth_header.number) {
                                    if let Ok(timestamp) = parse_hex_u64(&eth_header.timestamp) {
                                        // Create network-specific data
                                        let mut network_specific = serde_json::Map::new();
                                        if let Some(ref difficulty) = eth_header.difficulty {
                                            network_specific.insert(
                                                "difficulty".to_string(),
                                                serde_json::Value::String(difficulty.clone()),
                                            );
                                        }
                                        if let Some(ref extra_data) = eth_header.extra_data {
                                            network_specific.insert(
                                                "extraData".to_string(),
                                                serde_json::Value::String(extra_data.clone()),
                                            );
                                        }

                                        let block_header = BlockHeader {
                                            network: network.clone(),
                                            subnet: subnet.clone(),
                                            vm_type: vm_type.clone(),
                                            chain_id: chain_id.clone(),
                                            chain_name: chain_name.clone(),
                                            block_number,
                                            block_hash: eth_header.hash,
                                            parent_hash: eth_header.parent_hash,
                                            timestamp,
                                            difficulty: eth_header.difficulty,
                                            gas_limit: eth_header
                                                .gas_limit
                                                .and_then(|s| parse_hex_u64(&s).ok()),
                                            gas_used: eth_header
                                                .gas_used
                                                .and_then(|s| parse_hex_u64(&s).ok()),
                                            miner: eth_header.miner,
                                            extra_data: eth_header.extra_data,
                                            network_specific: serde_json::Value::Object(
                                                network_specific,
                                            ),
                                            received_at: chrono::Utc::now(),
                                            provider_id: format!("ethereum-client-{}", chain_id),
                                            raw_data: Some(text),
                                            rpc_url: Some(rpc_url.clone()),
                                            ws_url: Some(ws_url.clone()),
                                        };

                                        // Get NATS subject for logging
                                        let nats_subject = block_header.nats_subject();

                                        // Publish to NATS if client is available
                                        if let Some(ref nats) = nats_client {
                                            let payload = match serde_json::to_vec(&block_header) {
                                                Ok(data) => data,
                                                Err(e) => {
                                                    error!(
                                                        "Failed to serialize block header: {}",
                                                        e
                                                    );
                                                    continue;
                                                }
                                            };

                                            if let Err(e) = nats
                                                .publish(nats_subject.clone(), payload.into())
                                                .await
                                            {
                                                error!(
                                                    "Failed to publish to NATS subject '{}': {}",
                                                    nats_subject, e
                                                );
                                            } else {
                                                debug!(
                                                    "Published block #{} to NATS subject '{}'",
                                                    block_number, nats_subject
                                                );
                                            }
                                        }

                                        // Update stats
                                        {
                                            let mut stats = stats.write().await;
                                            stats.last_block_received = Some(block_number);
                                            stats.total_blocks_received += 1;
                                        }

                                        // Send to channel (for backward compatibility)
                                        if let Err(e) = sender.send(block_header) {
                                            error!("Failed to send block header: {}", e);
                                            break;
                                        }

                                        info!(
                                            "Received new block #{} for chain '{}' ({})",
                                            block_number, chain_id, nats_subject
                                        );
                                    }
                                }
                            }
                        }
                    }
                    Ok(Message::Binary(_)) => {
                        // Ignore binary messages
                        debug!("Received binary WebSocket message (ignored)");
                    }
                    Ok(Message::Ping(_)) => {
                        // Ping messages are handled automatically by tungstenite
                        debug!("Received WebSocket ping");
                    }
                    Ok(Message::Pong(_)) => {
                        // Pong messages are handled automatically by tungstenite
                        debug!("Received WebSocket pong");
                    }
                    Ok(Message::Close(_)) => {
                        warn!("WebSocket connection closed for chain '{}'", chain_id);
                        break;
                    }
                    Ok(Message::Frame(_)) => {
                        // Raw frames are not typically handled at this level
                        debug!("Received raw WebSocket frame (ignored)");
                    }
                    Err(e) => {
                        error!("WebSocket error for chain '{}': {}", chain_id, e);

                        // Update error stats
                        {
                            let mut stats = stats.write().await;
                            stats.connection_errors += 1;
                            stats.last_error = Some(e.to_string());
                            stats.last_error_at = Some(current_timestamp());
                            stats.connected = false;
                        }
                        break;
                    }
                }
            }

            // Connection ended
            {
                let mut stats = stats.write().await;
                stats.connected = false;
            }

            warn!("WebSocket subscription ended for chain '{}'", chain_id);
        });

        Ok(receiver)
    }

    async fn get_latest_header(&self) -> Result<BlockHeader> {
        let eth_header: EthBlockHeader = self
            .rpc_call("eth_getBlockByNumber", json!(["latest", false]))
            .await?;
        self.convert_block_header(eth_header)
    }

    async fn test_connection(&self) -> Result<()> {
        // Test HTTP RPC connection
        let _chain_id: String = self.rpc_call("eth_chainId", json!([])).await?;

        info!("Successfully connected to chain '{}'", self.config.chain_id);
        Ok(())
    }

    fn get_config(&self) -> &ChainConfig {
        &self.config
    }

    fn is_connected(&self) -> bool {
        // Use try_read for non-blocking access to connection stats
        match self.stats.try_read() {
            Ok(stats) => stats.connected,
            Err(_) => false, // If lock is held, assume not connected for safety
        }
    }

    fn get_stats(&self) -> ConnectionStats {
        // Use try_read for non-blocking access to connection stats
        match self.stats.try_read() {
            Ok(stats) => stats.clone(),
            Err(_) => ConnectionStats::default(), // Return default if lock is held
        }
    }
}
