//! # Transaction Processor Actor
//!
//! WasmCloud actor that processes raw blockchain transactions from various networks.
//! This actor receives raw transaction data via NATS messaging, enriches and filters them,
//! and publishes processed transactions to downstream consumers.

use serde::{Deserialize, Serialize};
use std::str::from_utf8;

// Generate WIT bindings for the transaction-processor world
wit_bindgen::generate!({ generate_all });

use exports::ekko::messaging::consumer::Guest as MessageConsumer;

/// Simplified Ethereum transaction structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EthTransaction {
    /// Transaction hash
    pub hash: String,
    /// Block number
    pub block_number: Option<u64>,
    /// Transaction index in block
    pub transaction_index: Option<u64>,
    /// From address
    pub from: String,
    /// To address (if any)
    pub to: Option<String>,
    /// Value transferred
    pub value: String,
    /// Gas limit
    pub gas: String,
    /// Gas price
    pub gas_price: String,
    /// Input data
    pub input: String,
    /// Subscribed UIDs (for filtering)
    pub subscribed_uids: Option<Vec<String>>,
}

/// Raw transaction message wrapper
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTransactionMessage {
    /// Source network (ethereum, bitcoin, solana, etc.)
    pub network: String,
    /// Subnet identifier (mainnet, sepolia, testnet, etc.)
    pub subnet: String,
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

/// Processed transaction output
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessedTransactionOutput {
    /// Network identifier (ethereum, bitcoin, solana, etc.)
    pub network: String,
    /// Subnet identifier (mainnet, sepolia, testnet, etc.)
    pub subnet: String,
    /// Processing status
    pub status: String,
    /// Number of transactions processed
    pub transaction_count: usize,
    /// Number of filtered/subscribed transactions
    pub filtered_count: usize,
    /// Processed transactions as JSON
    pub transactions: String,
    /// Processing timestamp
    pub processed_at: String,
}

impl RawTransactionMessage {
    /// Parse raw transaction message from JSON
    pub fn from_json(data: &[u8]) -> Result<Self, String> {
        serde_json::from_slice(data)
            .map_err(|e| format!("Failed to parse raw transaction message: {}", e))
    }
}

impl ProcessedTransactionOutput {
    /// Convert to JSON bytes
    pub fn to_json(&self) -> Result<Vec<u8>, String> {
        serde_json::to_vec(self)
            .map_err(|e| format!("Failed to serialize processed transaction output: {}", e))
    }
}

/// Main Transaction Processor Actor Component
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl Component {
    /// Filter transactions to only include those with subscriptions
    fn filter_subscribed_transactions(transactions: &mut Vec<EthTransaction>) {
        transactions.retain(|transaction| transaction.subscribed_uids.is_some());
    }

    /// Process Ethereum transactions
    fn process_eth_transactions(
        network: &str,
        subnet: &str,
        transactions_json: &str,
    ) -> Result<ProcessedTransactionOutput, String> {
        // Deserialize the transactions
        let mut transactions: Vec<EthTransaction> = serde_json::from_str(transactions_json)
            .map_err(|e| format!("Failed to parse eth transactions: {}", e))?;

        let original_count = transactions.len();
        eprintln!(
            "Processing {} ETH transactions for {}.{}",
            original_count, network, subnet
        );

        // Simple enrichment - add block number if missing
        for transaction in &mut transactions {
            if transaction.block_number.is_none() {
                // For demo purposes, set a default block number
                transaction.block_number = Some(0);
            }
        }
        eprintln!("After enrichment: {} transactions", transactions.len());

        // Filter to only subscribed transactions
        Self::filter_subscribed_transactions(&mut transactions);
        let filtered_count = transactions.len();
        eprintln!(
            "After filtering: {} subscribed transactions",
            filtered_count
        );

        // Convert back to JSON
        let processed_json = serde_json::to_string(&transactions)
            .map_err(|e| format!("Failed to serialize processed transactions: {}", e))?;

        Ok(ProcessedTransactionOutput {
            network: network.to_string(),
            subnet: subnet.to_string(),
            status: "processed".to_string(),
            transaction_count: original_count,
            filtered_count,
            transactions: processed_json,
            processed_at: chrono::Utc::now().to_rfc3339(),
        })
    }

    /// Process transaction message based on network type
    fn process_transaction_message(
        message: RawTransactionMessage,
    ) -> Result<ProcessedTransactionOutput, String> {
        let network = &message.network;
        let subnet = &message.subnet;

        match network.as_str() {
            "ethereum" | "eth" => {
                Self::process_eth_transactions(network, subnet, &message.transactions)
            }
            "bitcoin" | "btc" => {
                // TODO: Implement Bitcoin transaction processing
                Ok(ProcessedTransactionOutput {
                    network: network.to_string(),
                    subnet: subnet.to_string(),
                    status: "not_implemented".to_string(),
                    transaction_count: 0,
                    filtered_count: 0,
                    transactions: "[]".to_string(),
                    processed_at: chrono::Utc::now().to_rfc3339(),
                })
            }
            "solana" | "sol" => {
                // TODO: Implement Solana transaction processing
                Ok(ProcessedTransactionOutput {
                    network: network.to_string(),
                    subnet: subnet.to_string(),
                    status: "not_implemented".to_string(),
                    transaction_count: 0,
                    filtered_count: 0,
                    transactions: "[]".to_string(),
                    processed_at: chrono::Utc::now().to_rfc3339(),
                })
            }
            _ => Err(format!("Unsupported network: {}", network)),
        }
    }

    /// Publish processed transactions to downstream consumers
    fn publish_processed_transactions(output: &ProcessedTransactionOutput) -> Result<(), String> {
        // Only publish if we have filtered transactions to send
        if output.filtered_count == 0 {
            eprintln!(
                "No subscribed transactions to publish for {}.{}",
                output.network, output.subnet
            );
            return Ok(());
        }

        // Convert output to JSON
        let output_json = output.to_json()?;

        // Publish to network/subnet-specific processed transaction subject
        // Subject pattern: blockchain.{network}.{subnet}.transactions.processed
        let processed_subject = format!(
            "blockchain.{}.{}.transactions.processed",
            output.network, output.subnet
        );

        // Use the messaging handler to publish processed transactions
        use ekko::messaging::handler::publish;

        match publish(&processed_subject, &output_json) {
            Ok(_) => {
                eprintln!(
                    "Published {} processed {}.{} transactions to: {}",
                    output.filtered_count, output.network, output.subnet, processed_subject
                );
                Ok(())
            }
            Err(e) => {
                eprintln!("Failed to publish processed transactions: {}", e);
                Err(format!("Failed to publish: {}", e))
            }
        }
    }

    /// Publish notifications for high-priority transactions
    fn publish_notifications(output: &ProcessedTransactionOutput) -> Result<(), String> {
        // Only send notifications if we have transactions to notify about
        if output.filtered_count == 0 {
            return Ok(());
        }

        // Create notification payload
        let notification_payload = serde_json::json!({
            "type": "transaction_batch_processed",
            "network": output.network,
            "subnet": output.subnet,
            "transaction_count": output.transaction_count,
            "filtered_count": output.filtered_count,
            "processed_at": output.processed_at,
            "status": output.status
        });

        let notification_json = serde_json::to_vec(&notification_payload)
            .map_err(|e| format!("Failed to serialize notification: {}", e))?;

        // Publish to notification subject (PRD hierarchy: notifications.send.immediate.{channel})
        let notification_subject = "notifications.send.immediate.system";

        // Use the messaging handler to publish notification
        use ekko::messaging::handler::publish;

        match publish(notification_subject, &notification_json) {
            Ok(_) => {
                eprintln!(
                    "Sent notification for {} processed transactions",
                    output.filtered_count
                );
                Ok(())
            }
            Err(e) => {
                eprintln!("Failed to send notification: {}", e);
                Err(format!("Failed to send notification: {}", e))
            }
        }
    }
}

impl MessageConsumer for Component {
    /// Handle incoming NATS messages containing raw transaction data
    fn handle_message(subject: String, payload: Vec<u8>) -> Result<(), String> {
        // Only process blockchain transaction messages
        // Subject pattern: blockchain.{network}.{subnet}.transactions.*
        if !subject.starts_with("blockchain.") || !subject.contains(".transactions.") {
            return Ok(()); // Ignore non-blockchain-transaction messages
        }

        eprintln!(
            "Transaction processor received message on subject: {}",
            subject
        );

        // Try to parse as structured message first
        let message = match RawTransactionMessage::from_json(&payload) {
            Ok(msg) => msg,
            Err(_) => {
                // Fallback: try to parse as direct JSON transaction array (legacy format)
                let transactions_str = from_utf8(&payload)
                    .map_err(|e| format!("Failed to parse payload as UTF-8: {}", e))?;

                // Parse network and subnet from subject
                // Subject pattern: blockchain.{network}.{subnet}.transactions.*
                let parts: Vec<&str> = subject.split('.').collect();
                let (network, subnet) = if parts.len() >= 4 {
                    // New pattern: blockchain.{network}.{subnet}.transactions.*
                    (parts[1], parts[2])
                } else {
                    // Legacy pattern: blockchain.{network}.transactions.*
                    let network = if subject.contains("eth") {
                        "ethereum"
                    } else if subject.contains("btc") {
                        "bitcoin"
                    } else if subject.contains("sol") {
                        "solana"
                    } else {
                        "unknown"
                    };
                    (network, "mainnet") // Default to mainnet for legacy subjects
                };

                RawTransactionMessage {
                    network: network.to_string(),
                    subnet: subnet.to_string(),
                    transactions: transactions_str.to_string(),
                    metadata: None,
                }
            }
        };

        // Process the transaction message
        let processed_output = match Component::process_transaction_message(message) {
            Ok(output) => output,
            Err(e) => {
                eprintln!("Failed to process transaction message: {}", e);
                return Err(e);
            }
        };

        // Publish processed transactions to downstream consumers
        if let Err(e) = Component::publish_processed_transactions(&processed_output) {
            eprintln!("Failed to publish processed transactions: {}", e);
            return Err(e);
        }

        // Send notifications for processed transactions
        if let Err(e) = Component::publish_notifications(&processed_output) {
            eprintln!("Failed to send notifications: {}", e);
            return Err(e);
        }

        eprintln!(
            "Successfully processed {} transactions ({} filtered) for {}.{}",
            processed_output.transaction_count,
            processed_output.filtered_count,
            processed_output.network,
            processed_output.subnet
        );

        Ok(())
    }
}

// Include tests module
#[cfg(test)]
mod tests;

#[cfg(not(target_arch = "wasm32"))]
fn main() {
    // This function is never called in the WASM build
    println!("Transaction processor actor - use as WASM component");
}
