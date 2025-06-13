use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use std::collections::HashMap;

/// Event types supported by the system
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    WalletTx,
    TokenTransfer,
    ContractCall,
    NftTransfer,
    Staking,
    Swap,
    Defi,
}

/// Entity types in the blockchain ecosystem
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum EntityType {
    Wallet,
    Contract,
    Token,
    Nft,
    Pool,
}

/// Entity information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    pub r#type: EntityType,
    pub chain: String,
    pub address: String,
    pub name: Option<String>,
    pub symbol: Option<String>,
}

/// Event metadata for indexing and partitioning
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventMetadata {
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub block_number: u64,
    pub block_hash: String,
    pub tx_index: u32,
    
    // Time partitioning fields
    pub year: i32,
    pub month: i32,
    pub day: i32,
    pub hour: i32,
}

/// Main blockchain event structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockchainEvent {
    pub event_type: EventType,
    pub entity: Entity,
    pub timestamp: DateTime<Utc>,
    pub tx_hash: String,
    pub details: serde_json::Value, // Flexible JSON details
    pub metadata: EventMetadata,
}

/// Wallet transaction details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletTxDetails {
    pub from: String,
    pub to: Option<String>,
    pub value: String,
    pub token: String,
    pub token_address: Option<String>,
    
    // Gas information
    pub gas: String,
    pub gas_price: String,
    pub gas_used: Option<String>,
    
    // Transaction metadata
    pub nonce: String,
    pub input: String,
    pub status: String, // "confirmed", "failed", "pending"
    
    // Derived information
    pub tx_type: String,    // "send", "receive", "contract_call"
    pub direction: String,  // "in", "out", "self"
    pub value_usd: Option<String>,
}

/// Token transfer details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenTransferDetails {
    pub from: String,
    pub to: String,
    pub amount: String,
    pub token_address: String,
    pub token_symbol: String,
    pub token_name: String,
    pub decimals: u8,
    
    // Context
    pub tx_hash: String,
    pub log_index: u32,
    pub value_usd: Option<String>,
}

/// Contract call details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContractCallDetails {
    pub contract: String,
    pub function: String,
    pub parameters: HashMap<String, serde_json::Value>,
    pub return_values: Option<HashMap<String, serde_json::Value>>,
    
    // Gas and execution info
    pub gas: String,
    pub gas_used: String,
    pub status: String,
}

impl BlockchainEvent {
    /// Create a new wallet transaction event
    pub fn new_wallet_tx(
        entity: Entity,
        tx_hash: String,
        timestamp: DateTime<Utc>,
        details: WalletTxDetails,
        metadata: EventMetadata,
    ) -> Self {
        Self {
            event_type: EventType::WalletTx,
            entity,
            timestamp,
            tx_hash,
            details: serde_json::to_value(details).unwrap(),
            metadata,
        }
    }

    /// Create a new token transfer event
    pub fn new_token_transfer(
        entity: Entity,
        tx_hash: String,
        timestamp: DateTime<Utc>,
        details: TokenTransferDetails,
        metadata: EventMetadata,
    ) -> Self {
        Self {
            event_type: EventType::TokenTransfer,
            entity,
            timestamp,
            tx_hash,
            details: serde_json::to_value(details).unwrap(),
            metadata,
        }
    }

    /// Create a new contract call event
    pub fn new_contract_call(
        entity: Entity,
        tx_hash: String,
        timestamp: DateTime<Utc>,
        details: ContractCallDetails,
        metadata: EventMetadata,
    ) -> Self {
        Self {
            event_type: EventType::ContractCall,
            entity,
            timestamp,
            tx_hash,
            details: serde_json::to_value(details).unwrap(),
            metadata,
        }
    }

    /// Get the partition path for this event
    pub fn partition_path(&self) -> String {
        format!(
            "chain={}/event_type={}/year={}/month={:02}/day={:02}",
            self.entity.chain,
            serde_json::to_string(&self.event_type).unwrap().trim_matches('"'),
            self.metadata.year,
            self.metadata.month,
            self.metadata.day
        )
    }

    /// Get details as a specific type
    pub fn get_details_as<T>(&self) -> Result<T, serde_json::Error>
    where
        T: for<'de> Deserialize<'de>,
    {
        serde_json::from_value(self.details.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wallet_tx_event_creation() {
        let entity = Entity {
            r#type: EntityType::Wallet,
            chain: "avax".to_string(),
            address: "0x123...".to_string(),
            name: None,
            symbol: None,
        };

        let details = WalletTxDetails {
            from: "0x123...".to_string(),
            to: Some("0x456...".to_string()),
            value: "1000000000000000000".to_string(),
            token: "AVAX".to_string(),
            token_address: None,
            gas: "21000".to_string(),
            gas_price: "25000000000".to_string(),
            gas_used: Some("21000".to_string()),
            nonce: "1".to_string(),
            input: "0x".to_string(),
            status: "confirmed".to_string(),
            tx_type: "send".to_string(),
            direction: "out".to_string(),
            value_usd: Some("25.50".to_string()),
        };

        let metadata = EventMetadata {
            network: "Avalanche".to_string(),
            subnet: "Mainnet".to_string(),
            vm_type: "EVM".to_string(),
            block_number: 12345,
            block_hash: "0xblock123...".to_string(),
            tx_index: 0,
            year: 2024,
            month: 12,
            day: 19,
            hour: 10,
        };

        let event = BlockchainEvent::new_wallet_tx(
            entity,
            "0xtx123...".to_string(),
            Utc::now(),
            details,
            metadata,
        );

        assert_eq!(event.event_type, EventType::WalletTx);
        assert_eq!(event.entity.chain, "avax");
        assert_eq!(event.partition_path(), "chain=avax/event_type=wallet_tx/year=2024/month=12/day=19");
    }
}
