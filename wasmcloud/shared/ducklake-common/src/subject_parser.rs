//! NATS subject parser for DuckLake providers
//!
//! Parses NATS subjects in the format:
//! `ducklake.{table}.{chain}.{subnet}.{action}`
//!
//! Examples:
//! - `ducklake.transactions.ethereum.mainnet.write`
//! - `ducklake.blocks.polygon.mainnet.write`
//! - `ducklake.logs.arbitrum.one.write`

use serde::{Deserialize, Serialize};
use std::fmt;

use crate::error::DuckLakeError;
#[allow(deprecated)]
use crate::schemas::{
    // NEW: Unified Schema Tables (Schema Redesign)
    ADDRESS_TRANSACTIONS_TABLE,
    // Core tables
    BLOCKS_TABLE,
    CONTRACT_CALLS_TABLE,
    // DEPRECATED: Decoded transaction tables
    DECODED_TRANSACTIONS_EVM_TABLE,
    LOGS_TABLE,
    NOTIFICATION_CONTENT_TABLE,
    NOTIFICATION_DELIVERIES_TABLE,
    // DEPRECATED: Processed/enriched transaction tables
    PROCESSED_TRANSFERS_TABLE,
    PROTOCOL_EVENTS_TABLE,
    TOKEN_PRICES_TABLE,
    TOKEN_TRANSFERS_TABLE,
    // DEPRECATED: VM-specific transaction tables (kept for backward compatibility)
    TRANSACTIONS_BTC_TABLE,
    TRANSACTIONS_EVM_TABLE,
    TRANSACTIONS_SVM_TABLE,
    TRANSACTIONS_TABLE,
};

/// Parsed information from a NATS subject
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SubjectInfo {
    /// Target DuckLake table name
    pub table: String,
    /// Blockchain network (e.g., "ethereum", "polygon", "bitcoin")
    pub chain: String,
    /// Network subnet (e.g., "mainnet", "sepolia", "mumbai")
    pub subnet: String,
    /// Action to perform (e.g., "write", "query")
    pub action: String,
    /// Combined chain_id for partitioning (e.g., "ethereum_mainnet")
    pub chain_id: String,
}

impl SubjectInfo {
    /// Parse a NATS subject into SubjectInfo
    ///
    /// Expected format: `ducklake.{table}.{chain}.{subnet}.{action}`
    ///
    /// # Examples
    /// ```
    /// use ducklake_common::SubjectInfo;
    ///
    /// let info = SubjectInfo::parse("ducklake.transactions.ethereum.mainnet.write").unwrap();
    /// assert_eq!(info.table, "transactions");
    /// assert_eq!(info.chain, "ethereum");
    /// assert_eq!(info.subnet, "mainnet");
    /// assert_eq!(info.action, "write");
    /// assert_eq!(info.chain_id, "ethereum_mainnet");
    /// ```
    pub fn parse(subject: &str) -> Result<Self, SubjectParseError> {
        let parts: Vec<&str> = subject.split('.').collect();

        if parts.len() != 5 {
            return Err(SubjectParseError::InvalidFormat(format!(
                "Expected format 'ducklake.{{table}}.{{chain}}.{{subnet}}.{{action}}', got: {}",
                subject
            )));
        }

        if parts[0] != "ducklake" {
            return Err(SubjectParseError::InvalidPrefix(format!(
                "Subject must start with 'ducklake', got: {}",
                parts[0]
            )));
        }

        let table = parts[1].to_string();
        let chain = parts[2].to_string();
        let subnet = parts[3].to_string();
        let action = parts[4].to_string();

        // Validate action
        if !Self::is_valid_action(&action) {
            return Err(SubjectParseError::InvalidAction(format!(
                "Unknown action: {}. Valid actions: write, query, compact",
                action
            )));
        }

        // Validate table name.
        //
        // Important: query subjects may reference *virtual* datasource routing names
        // (e.g. "wallet_balance_latest") which are not physical DuckLake tables.
        // We keep write/compact validation strict to prevent accidental writes to unknown tables.
        if action != "query" && !Self::is_valid_table(&table) {
            return Err(SubjectParseError::InvalidTable(format!(
                "Unknown table: {}. Valid tables: blocks, transactions, transactions_evm, transactions_svm, transactions_btc, decoded_transactions_evm, logs, token_prices, protocol_events, contract_calls, notification_deliveries, notification_content, processed_transfers, token_transfers, address_transactions",
                table
            )));
        }

        // Construct chain_id for partitioning
        let chain_id = format!("{}_{}", chain, subnet);

        Ok(Self {
            table,
            chain,
            subnet,
            action,
            chain_id,
        })
    }

    /// Check if a table name is valid
    ///
    /// Accepts both current and deprecated table names for backward compatibility.
    #[allow(deprecated)]
    pub fn is_valid_table(table: &str) -> bool {
        matches!(
            table,
            // Core tables
            BLOCKS_TABLE
                | TRANSACTIONS_TABLE
                | LOGS_TABLE
                | TOKEN_PRICES_TABLE
                | PROTOCOL_EVENTS_TABLE
                | CONTRACT_CALLS_TABLE
                | NOTIFICATION_DELIVERIES_TABLE
                | NOTIFICATION_CONTENT_TABLE
                // DEPRECATED: VM-specific transaction tables (kept for backward compatibility)
                | TRANSACTIONS_EVM_TABLE
                | TRANSACTIONS_SVM_TABLE
                | TRANSACTIONS_BTC_TABLE
                // DEPRECATED: Decoded transaction tables
                | DECODED_TRANSACTIONS_EVM_TABLE
                // DEPRECATED: Processed/enriched transaction tables
                | PROCESSED_TRANSFERS_TABLE
                // NEW: Unified Schema Tables (Schema Redesign)
                | TOKEN_TRANSFERS_TABLE
                | ADDRESS_TRANSACTIONS_TABLE
        )
    }

    /// Check if an action is valid
    pub fn is_valid_action(action: &str) -> bool {
        matches!(action, "write" | "query" | "compact")
    }

    /// Get the full NATS subject for this info
    pub fn to_subject(&self) -> String {
        format!(
            "ducklake.{}.{}.{}.{}",
            self.table, self.chain, self.subnet, self.action
        )
    }

    /// Create a subscription pattern for all tables on a chain
    ///
    /// Returns: `ducklake.*.{chain}.{subnet}.{action}`
    pub fn subscription_pattern_for_chain(chain: &str, subnet: &str, action: &str) -> String {
        format!("ducklake.*.{}.{}.{}", chain, subnet, action)
    }

    /// Create a subscription pattern for a specific table on all chains
    ///
    /// Returns: `ducklake.{table}.*.*.{action}`
    pub fn subscription_pattern_for_table(table: &str, action: &str) -> String {
        format!("ducklake.{}.*.*.{}", table, action)
    }

    /// Create a subscription pattern for all write operations
    ///
    /// Returns: `ducklake.*.*.*.write`
    pub fn subscription_pattern_all_writes() -> String {
        "ducklake.*.*.*.write".to_string()
    }

    /// Create a subscription pattern for all query operations
    ///
    /// Returns: `ducklake.*.*.*.query`
    pub fn subscription_pattern_all_queries() -> String {
        "ducklake.*.*.*.query".to_string()
    }

    // =========================================================================
    // NEW: Subscription patterns for unified schema tables (Schema Redesign)
    // =========================================================================

    /// Create a subscription pattern for all token transfer writes
    ///
    /// Returns: `ducklake.token_transfers.*.*.write`
    pub fn subscription_pattern_token_transfers_writes() -> String {
        format!("ducklake.{}.*.*.write", TOKEN_TRANSFERS_TABLE)
    }

    /// Create a subscription pattern for all address transaction index writes
    ///
    /// Returns: `ducklake.address_transactions.*.*.write`
    pub fn subscription_pattern_address_transactions_writes() -> String {
        format!("ducklake.{}.*.*.write", ADDRESS_TRANSACTIONS_TABLE)
    }

    /// Create a subscription pattern for all unified transaction writes
    /// This is the new canonical way to subscribe to all transaction data
    ///
    /// Returns: `ducklake.transactions.*.*.write`
    pub fn subscription_pattern_unified_transactions_writes() -> String {
        format!("ducklake.{}.*.*.write", TRANSACTIONS_TABLE)
    }
}

impl fmt::Display for SubjectInfo {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.to_subject())
    }
}

/// Errors that can occur when parsing NATS subjects
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SubjectParseError {
    /// Subject format is invalid
    InvalidFormat(String),
    /// Subject doesn't start with 'ducklake'
    InvalidPrefix(String),
    /// Table name is not recognized
    InvalidTable(String),
    /// Action is not recognized
    InvalidAction(String),
}

impl fmt::Display for SubjectParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SubjectParseError::InvalidFormat(msg) => write!(f, "Invalid subject format: {}", msg),
            SubjectParseError::InvalidPrefix(msg) => write!(f, "Invalid subject prefix: {}", msg),
            SubjectParseError::InvalidTable(msg) => write!(f, "Invalid table: {}", msg),
            SubjectParseError::InvalidAction(msg) => write!(f, "Invalid action: {}", msg),
        }
    }
}

impl std::error::Error for SubjectParseError {}

impl From<SubjectParseError> for DuckLakeError {
    fn from(err: SubjectParseError) -> Self {
        DuckLakeError::SubjectParseError(err.to_string())
    }
}

#[cfg(test)]
#[allow(deprecated)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_valid_subject() {
        let info = SubjectInfo::parse("ducklake.transactions.ethereum.mainnet.write").unwrap();
        assert_eq!(info.table, "transactions");
        assert_eq!(info.chain, "ethereum");
        assert_eq!(info.subnet, "mainnet");
        assert_eq!(info.action, "write");
        assert_eq!(info.chain_id, "ethereum_mainnet");
    }

    #[test]
    fn test_parse_all_tables() {
        let tables = vec![
            // Core tables
            "blocks",
            "transactions",
            "logs",
            "token_prices",
            "protocol_events",
            "contract_calls",
            "notification_deliveries",
            "notification_content",
            // VM-specific transaction tables
            "transactions_evm",
            "transactions_svm",
            "transactions_btc",
            // Decoded transaction tables
            "decoded_transactions_evm",
            // Processed/enriched transaction tables
            "processed_transfers",
            // NEW: Unified Schema Tables (Schema Redesign)
            "token_transfers",
            "address_transactions",
        ];

        for table in tables {
            let subject = format!("ducklake.{}.polygon.mainnet.write", table);
            let info = SubjectInfo::parse(&subject).unwrap();
            assert_eq!(info.table, table);
        }
    }

    #[test]
    fn test_parse_all_actions() {
        let actions = vec!["write", "query", "compact"];

        for action in actions {
            let subject = format!("ducklake.blocks.bitcoin.mainnet.{}", action);
            let info = SubjectInfo::parse(&subject).unwrap();
            assert_eq!(info.action, action);
        }
    }

    #[test]
    fn test_parse_invalid_format() {
        let result = SubjectInfo::parse("ducklake.transactions.ethereum.mainnet");
        assert!(matches!(result, Err(SubjectParseError::InvalidFormat(_))));
    }

    #[test]
    fn test_parse_invalid_prefix() {
        let result = SubjectInfo::parse("delta.transactions.ethereum.mainnet.write");
        assert!(matches!(result, Err(SubjectParseError::InvalidPrefix(_))));
    }

    #[test]
    fn test_parse_invalid_table() {
        let result = SubjectInfo::parse("ducklake.invalid_table.ethereum.mainnet.write");
        assert!(matches!(result, Err(SubjectParseError::InvalidTable(_))));
    }

    #[test]
    fn test_parse_virtual_table_for_query() {
        let info =
            SubjectInfo::parse("ducklake.wallet_balance_latest.ethereum.mainnet.query").unwrap();
        assert_eq!(info.table, "wallet_balance_latest");
        assert_eq!(info.chain, "ethereum");
        assert_eq!(info.subnet, "mainnet");
        assert_eq!(info.action, "query");
    }

    #[test]
    fn test_parse_invalid_action() {
        let result = SubjectInfo::parse("ducklake.transactions.ethereum.mainnet.invalid");
        assert!(matches!(result, Err(SubjectParseError::InvalidAction(_))));
    }

    #[test]
    fn test_to_subject() {
        let info = SubjectInfo {
            table: "logs".to_string(),
            chain: "arbitrum".to_string(),
            subnet: "one".to_string(),
            action: "write".to_string(),
            chain_id: "arbitrum_one".to_string(),
        };

        assert_eq!(info.to_subject(), "ducklake.logs.arbitrum.one.write");
    }

    #[test]
    fn test_subscription_patterns() {
        assert_eq!(
            SubjectInfo::subscription_pattern_for_chain("ethereum", "mainnet", "write"),
            "ducklake.*.ethereum.mainnet.write"
        );

        assert_eq!(
            SubjectInfo::subscription_pattern_for_table("transactions", "write"),
            "ducklake.transactions.*.*.write"
        );

        assert_eq!(
            SubjectInfo::subscription_pattern_all_writes(),
            "ducklake.*.*.*.write"
        );

        assert_eq!(
            SubjectInfo::subscription_pattern_all_queries(),
            "ducklake.*.*.*.query"
        );
    }

    #[test]
    fn test_chain_id_construction() {
        let test_cases = vec![
            ("ethereum", "mainnet", "ethereum_mainnet"),
            ("polygon", "mumbai", "polygon_mumbai"),
            ("bitcoin", "mainnet", "bitcoin_mainnet"),
            ("solana", "devnet", "solana_devnet"),
        ];

        for (chain, subnet, expected_chain_id) in test_cases {
            let subject = format!("ducklake.blocks.{}.{}.write", chain, subnet);
            let info = SubjectInfo::parse(&subject).unwrap();
            assert_eq!(info.chain_id, expected_chain_id);
        }
    }

    #[test]
    fn test_display() {
        let info = SubjectInfo::parse("ducklake.blocks.ethereum.mainnet.write").unwrap();
        assert_eq!(
            format!("{}", info),
            "ducklake.blocks.ethereum.mainnet.write"
        );
    }

    #[test]
    fn test_new_unified_schema_subscription_patterns() {
        assert_eq!(
            SubjectInfo::subscription_pattern_token_transfers_writes(),
            "ducklake.token_transfers.*.*.write"
        );

        assert_eq!(
            SubjectInfo::subscription_pattern_address_transactions_writes(),
            "ducklake.address_transactions.*.*.write"
        );

        assert_eq!(
            SubjectInfo::subscription_pattern_unified_transactions_writes(),
            "ducklake.transactions.*.*.write"
        );
    }

    #[test]
    fn test_new_tables_parse_correctly() {
        // Test token_transfers table
        let tt_info =
            SubjectInfo::parse("ducklake.token_transfers.ethereum.mainnet.write").unwrap();
        assert_eq!(tt_info.table, "token_transfers");
        assert_eq!(tt_info.chain, "ethereum");
        assert_eq!(tt_info.chain_id, "ethereum_mainnet");

        // Test address_transactions table
        let at_info =
            SubjectInfo::parse("ducklake.address_transactions.polygon.mainnet.write").unwrap();
        assert_eq!(at_info.table, "address_transactions");
        assert_eq!(at_info.chain, "polygon");
        assert_eq!(at_info.chain_id, "polygon_mainnet");
    }
}
