//! Partitioning logic for DuckLake tables
//!
//! Implements multiple partitioning strategies:
//! - Standard 3-level: (chain_id, block_date, shard)
//! - Address-prefix 4-level: (chain_id, address_prefix, block_date, shard)
//! - Snapshot: (chain_id, snapshot_date, shard)
//! - Interval: (chain_id, interval, block_date, shard)
//!
//! Uses consistent hash-based sharding for even data distribution.

use chrono::DateTime;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use tracing::{debug, instrument, warn};

use crate::error::DuckLakeError;
use crate::schemas::{
    ADDRESS_INDEX_TABLE, BLOCKS_TABLE, CONTRACT_CALLS_TABLE, LOGS_TABLE, LP_POSITIONS_TABLE,
    NOTIFICATION_CONTENT_TABLE, NOTIFICATION_DELIVERIES_TABLE, PROTOCOL_EVENTS_TABLE,
    TOKEN_HOLDINGS_TABLE, TOKEN_OHLCV_TABLE, TOKEN_PRICES_TABLE, TRANSACTIONS_TABLE,
    WALLET_ACTIVITY_TABLE, YIELD_EVENTS_TABLE,
};

/// Default shard counts per table type for optimal query performance
pub const DEFAULT_SHARD_COUNT: u16 = 16;
pub const HIGH_CARDINALITY_SHARD_COUNT: u16 = 64;
pub const ADDRESS_BASED_SHARD_COUNT: u16 = 256;
pub const MEDIUM_SHARD_COUNT: u16 = 32;
pub const SNAPSHOT_SHARD_COUNT: u16 = 128;

/// Partition specification for a record
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct PartitionSpec {
    pub chain_id: String,
    pub block_date: String, // YYYY-MM-DD format
    pub shard: u16,
}

impl PartitionSpec {
    /// Create new partition spec
    pub fn new(chain_id: String, block_date: String, shard: u16) -> Self {
        Self {
            chain_id,
            block_date,
            shard,
        }
    }

    /// Get partition path for S3/MinIO storage
    pub fn to_path(&self, table_name: &str) -> String {
        format!(
            "{}/chain_id={}/block_date={}/shard={}",
            table_name, self.chain_id, self.block_date, self.shard
        )
    }

    /// Get partition values as key-value pairs
    pub fn to_partition_values(&self) -> HashMap<String, String> {
        let mut values = HashMap::new();
        values.insert("chain_id".to_string(), self.chain_id.clone());
        values.insert("block_date".to_string(), self.block_date.clone());
        values.insert("shard".to_string(), self.shard.to_string());
        values
    }

    /// Parse partition spec from path
    pub fn from_path(path: &str) -> Result<Self, DuckLakeError> {
        let parts: Vec<&str> = path.split('/').collect();
        if parts.len() < 3 {
            return Err(DuckLakeError::SerializationError(format!(
                "Invalid partition path format: {}",
                path
            )));
        }

        let mut chain_id = None;
        let mut block_date = None;
        let mut shard = None;

        // Look through all parts for partition key-value pairs
        for part in parts.iter() {
            if let Some(stripped) = part.strip_prefix("chain_id=") {
                chain_id = Some(stripped.to_string());
            } else if let Some(stripped) = part.strip_prefix("block_date=") {
                block_date = Some(stripped.to_string());
            } else if let Some(stripped) = part.strip_prefix("shard=") {
                shard = Some(stripped.parse::<u16>().map_err(|e| {
                    DuckLakeError::SerializationError(format!("Invalid shard number: {}", e))
                })?);
            }
        }

        Ok(Self {
            chain_id: chain_id
                .ok_or_else(|| DuckLakeError::SerializationError("Missing chain_id".to_string()))?,
            block_date: block_date.ok_or_else(|| {
                DuckLakeError::SerializationError("Missing block_date".to_string())
            })?,
            shard: shard
                .ok_or_else(|| DuckLakeError::SerializationError("Missing shard".to_string()))?,
        })
    }
}

/// Address-prefix partition specification for wallet/address-centric tables
///
/// Uses 4-level partitioning: (chain_id, address_prefix, block_date, shard)
/// where address_prefix is the first 4 hex characters after "0x".
/// This enables partition pruning for wallet tracking queries.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct AddressPrefixPartitionSpec {
    pub chain_id: String,
    pub address_prefix: String, // First 4 hex chars (e.g., "a1b2")
    pub block_date: String,     // YYYY-MM-DD format
    pub shard: u16,
}

impl AddressPrefixPartitionSpec {
    /// Create new address-prefix partition spec
    pub fn new(chain_id: String, address_prefix: String, block_date: String, shard: u16) -> Self {
        Self {
            chain_id,
            address_prefix,
            block_date,
            shard,
        }
    }

    /// Get partition path for S3/MinIO storage
    pub fn to_path(&self, table_name: &str) -> String {
        format!(
            "{}/chain_id={}/address_prefix={}/block_date={}/shard={}",
            table_name, self.chain_id, self.address_prefix, self.block_date, self.shard
        )
    }

    /// Get partition values as key-value pairs
    pub fn to_partition_values(&self) -> HashMap<String, String> {
        let mut values = HashMap::new();
        values.insert("chain_id".to_string(), self.chain_id.clone());
        values.insert("address_prefix".to_string(), self.address_prefix.clone());
        values.insert("block_date".to_string(), self.block_date.clone());
        values.insert("shard".to_string(), self.shard.to_string());
        values
    }

    /// Parse address-prefix partition spec from path
    pub fn from_path(path: &str) -> Result<Self, DuckLakeError> {
        let parts: Vec<&str> = path.split('/').collect();
        if parts.len() < 4 {
            return Err(DuckLakeError::SerializationError(format!(
                "Invalid address-prefix partition path format: {}",
                path
            )));
        }

        let mut chain_id = None;
        let mut address_prefix = None;
        let mut block_date = None;
        let mut shard = None;

        for part in parts.iter() {
            if let Some(stripped) = part.strip_prefix("chain_id=") {
                chain_id = Some(stripped.to_string());
            } else if let Some(stripped) = part.strip_prefix("address_prefix=") {
                address_prefix = Some(stripped.to_string());
            } else if let Some(stripped) = part.strip_prefix("block_date=") {
                block_date = Some(stripped.to_string());
            } else if let Some(stripped) = part.strip_prefix("shard=") {
                shard = Some(stripped.parse::<u16>().map_err(|e| {
                    DuckLakeError::SerializationError(format!("Invalid shard number: {}", e))
                })?);
            }
        }

        Ok(Self {
            chain_id: chain_id
                .ok_or_else(|| DuckLakeError::SerializationError("Missing chain_id".to_string()))?,
            address_prefix: address_prefix.ok_or_else(|| {
                DuckLakeError::SerializationError("Missing address_prefix".to_string())
            })?,
            block_date: block_date.ok_or_else(|| {
                DuckLakeError::SerializationError("Missing block_date".to_string())
            })?,
            shard: shard
                .ok_or_else(|| DuckLakeError::SerializationError("Missing shard".to_string()))?,
        })
    }
}

/// Snapshot partition specification for point-in-time tables (token_holdings)
///
/// Uses 3-level partitioning: (chain_id, snapshot_date, shard)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct SnapshotPartitionSpec {
    pub chain_id: String,
    pub snapshot_date: String, // YYYY-MM-DD format
    pub shard: u16,
}

impl SnapshotPartitionSpec {
    /// Create new snapshot partition spec
    pub fn new(chain_id: String, snapshot_date: String, shard: u16) -> Self {
        Self {
            chain_id,
            snapshot_date,
            shard,
        }
    }

    /// Get partition path for S3/MinIO storage
    pub fn to_path(&self, table_name: &str) -> String {
        format!(
            "{}/chain_id={}/snapshot_date={}/shard={}",
            table_name, self.chain_id, self.snapshot_date, self.shard
        )
    }

    /// Get partition values as key-value pairs
    pub fn to_partition_values(&self) -> HashMap<String, String> {
        let mut values = HashMap::new();
        values.insert("chain_id".to_string(), self.chain_id.clone());
        values.insert("snapshot_date".to_string(), self.snapshot_date.clone());
        values.insert("shard".to_string(), self.shard.to_string());
        values
    }
}

/// Interval partition specification for OHLCV tables
///
/// Uses 4-level partitioning: (chain_id, interval, block_date, shard)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct IntervalPartitionSpec {
    pub chain_id: String,
    pub interval: String,   // "1m", "5m", "15m", "1h", "4h", "1d"
    pub block_date: String, // YYYY-MM-DD format
    pub shard: u16,
}

impl IntervalPartitionSpec {
    /// Create new interval partition spec
    pub fn new(chain_id: String, interval: String, block_date: String, shard: u16) -> Self {
        Self {
            chain_id,
            interval,
            block_date,
            shard,
        }
    }

    /// Get partition path for S3/MinIO storage
    pub fn to_path(&self, table_name: &str) -> String {
        format!(
            "{}/chain_id={}/interval={}/block_date={}/shard={}",
            table_name, self.chain_id, self.interval, self.block_date, self.shard
        )
    }

    /// Get partition values as key-value pairs
    pub fn to_partition_values(&self) -> HashMap<String, String> {
        let mut values = HashMap::new();
        values.insert("chain_id".to_string(), self.chain_id.clone());
        values.insert("interval".to_string(), self.interval.clone());
        values.insert("block_date".to_string(), self.block_date.clone());
        values.insert("shard".to_string(), self.shard.to_string());
        values
    }
}

/// Table-specific shard configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableShardConfig {
    /// Shard count per table name
    pub shard_counts: HashMap<String, u16>,
}

impl Default for TableShardConfig {
    fn default() -> Self {
        let mut shard_counts = HashMap::new();

        // Core tables
        shard_counts.insert(BLOCKS_TABLE.to_string(), DEFAULT_SHARD_COUNT);
        shard_counts.insert(TRANSACTIONS_TABLE.to_string(), HIGH_CARDINALITY_SHARD_COUNT);
        shard_counts.insert(LOGS_TABLE.to_string(), HIGH_CARDINALITY_SHARD_COUNT);
        shard_counts.insert(TOKEN_PRICES_TABLE.to_string(), MEDIUM_SHARD_COUNT);
        shard_counts.insert(PROTOCOL_EVENTS_TABLE.to_string(), MEDIUM_SHARD_COUNT);
        shard_counts.insert(CONTRACT_CALLS_TABLE.to_string(), MEDIUM_SHARD_COUNT);
        shard_counts.insert(
            NOTIFICATION_DELIVERIES_TABLE.to_string(),
            DEFAULT_SHARD_COUNT,
        );
        shard_counts.insert(NOTIFICATION_CONTENT_TABLE.to_string(), DEFAULT_SHARD_COUNT);

        // DeFi analytics tables
        shard_counts.insert(WALLET_ACTIVITY_TABLE.to_string(), ADDRESS_BASED_SHARD_COUNT);
        shard_counts.insert(LP_POSITIONS_TABLE.to_string(), MEDIUM_SHARD_COUNT);
        shard_counts.insert(YIELD_EVENTS_TABLE.to_string(), MEDIUM_SHARD_COUNT);
        shard_counts.insert(TOKEN_HOLDINGS_TABLE.to_string(), SNAPSHOT_SHARD_COUNT);
        shard_counts.insert(TOKEN_OHLCV_TABLE.to_string(), MEDIUM_SHARD_COUNT);
        shard_counts.insert(ADDRESS_INDEX_TABLE.to_string(), ADDRESS_BASED_SHARD_COUNT);

        Self { shard_counts }
    }
}

impl TableShardConfig {
    /// Get shard count for a specific table
    pub fn get_shard_count(&self, table_name: &str) -> u16 {
        *self
            .shard_counts
            .get(table_name)
            .unwrap_or(&DEFAULT_SHARD_COUNT)
    }

    /// Set custom shard count for a table
    pub fn set_shard_count(&mut self, table_name: &str, count: u16) {
        self.shard_counts.insert(table_name.to_string(), count);
    }
}

/// Extract address prefix (first 4 hex characters after 0x)
///
/// # Arguments
/// * `address` - Blockchain address (e.g., "0xa1b2c3d4e5...")
///
/// # Returns
/// First 4 hex characters in lowercase (e.g., "a1b2")
///
/// # Examples
/// ```
/// use ducklake_common::partitioner::extract_address_prefix;
///
/// assert_eq!(extract_address_prefix("0xa1b2c3d4e5f6"), "a1b2");
/// assert_eq!(extract_address_prefix("A1B2C3D4E5F6"), "a1b2");
/// assert_eq!(extract_address_prefix("0xABCD"), "abcd");
/// ```
pub fn extract_address_prefix(address: &str) -> String {
    let normalized = address.to_lowercase();
    let without_prefix = normalized.strip_prefix("0x").unwrap_or(&normalized);

    // Take first 4 characters, padding with zeros if needed
    let prefix: String = without_prefix.chars().take(4).collect();
    if prefix.len() < 4 {
        format!("{:0<4}", prefix)
    } else {
        prefix
    }
}

/// Partitioner for handling blockchain data distribution
pub struct Partitioner {
    /// Default number of shards per partition
    shard_count: u16,
    /// Per-table shard configuration
    table_config: TableShardConfig,
}

impl Partitioner {
    /// Create new partitioner with default shard count
    pub fn new() -> Self {
        Self {
            shard_count: DEFAULT_SHARD_COUNT,
            table_config: TableShardConfig::default(),
        }
    }

    /// Create new partitioner with custom shard count
    pub fn with_shard_count(shard_count: u16) -> Self {
        Self {
            shard_count,
            table_config: TableShardConfig::default(),
        }
    }

    /// Create new partitioner with custom table configuration
    pub fn with_table_config(table_config: TableShardConfig) -> Self {
        Self {
            shard_count: DEFAULT_SHARD_COUNT,
            table_config,
        }
    }

    /// Get shard count for a specific table
    pub fn get_table_shard_count(&self, table_name: &str) -> u16 {
        self.table_config.get_shard_count(table_name)
    }

    /// Calculate shard for a given hash using table-specific shard count
    #[instrument(skip(self))]
    pub fn calculate_shard_for_table(
        &self,
        hash: &str,
        table_name: &str,
    ) -> Result<u16, DuckLakeError> {
        let shard_count = self.get_table_shard_count(table_name);
        self.calculate_shard_with_count(hash, shard_count)
    }

    /// Calculate shard for a given hash with specific shard count
    fn calculate_shard_with_count(
        &self,
        hash: &str,
        shard_count: u16,
    ) -> Result<u16, DuckLakeError> {
        if hash.is_empty() {
            return Err(DuckLakeError::SerializationError(
                "Hash cannot be empty".to_string(),
            ));
        }

        let mut hasher = Sha256::new();
        hasher.update(hash.as_bytes());
        let hash_bytes = hasher.finalize();

        let hash_u32 =
            u32::from_be_bytes([hash_bytes[0], hash_bytes[1], hash_bytes[2], hash_bytes[3]]);

        let shard = (hash_u32 % shard_count as u32) as u16;

        debug!(
            "Calculated shard {} for hash {} (mod {})",
            shard, hash, shard_count
        );
        Ok(shard)
    }

    /// Calculate shard for a given hash using consistent hashing
    #[instrument(skip(self))]
    pub fn calculate_shard(&self, hash: &str) -> Result<u16, DuckLakeError> {
        if hash.is_empty() {
            return Err(DuckLakeError::SerializationError(
                "Hash cannot be empty".to_string(),
            ));
        }

        // Use SHA-256 for consistent hashing
        let mut hasher = Sha256::new();
        hasher.update(hash.as_bytes());
        let hash_bytes = hasher.finalize();

        // Use first 4 bytes as u32 for shard calculation
        let hash_u32 =
            u32::from_be_bytes([hash_bytes[0], hash_bytes[1], hash_bytes[2], hash_bytes[3]]);

        let shard = (hash_u32 % self.shard_count as u32) as u16;

        debug!(
            "Calculated shard {} for hash {} (mod {})",
            shard, hash, self.shard_count
        );
        Ok(shard)
    }

    /// Get partition spec for a block record
    pub fn partition_for_block(
        &self,
        chain_id: &str,
        block_hash: &str,
        block_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        let shard = self.calculate_shard(block_hash)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        Ok(PartitionSpec::new(chain_id.to_string(), block_date, shard))
    }

    /// Get partition spec for a transaction record
    pub fn partition_for_transaction(
        &self,
        chain_id: &str,
        transaction_hash: &str,
        block_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        let shard = self.calculate_shard(transaction_hash)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        Ok(PartitionSpec::new(chain_id.to_string(), block_date, shard))
    }

    /// Get partition spec for a log record (uses transaction hash for consistency)
    pub fn partition_for_log(
        &self,
        chain_id: &str,
        transaction_hash: &str,
        block_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        // Use transaction hash to keep logs with their transactions
        let shard = self.calculate_shard(transaction_hash)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        Ok(PartitionSpec::new(chain_id.to_string(), block_date, shard))
    }

    /// Get partition spec for a token price record
    pub fn partition_for_token_price(
        &self,
        chain_id: &str,
        token_address: &str,
        block_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        // Use token address for even distribution of token prices
        let shard = self.calculate_shard(token_address)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        Ok(PartitionSpec::new(chain_id.to_string(), block_date, shard))
    }

    /// Get partition spec for a protocol event record
    pub fn partition_for_protocol_event(
        &self,
        chain_id: &str,
        transaction_hash: &str,
        protocol_name: &str,
        block_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        // Combine transaction hash and protocol for distribution
        let combined_key = format!("{}:{}", transaction_hash, protocol_name);
        let shard = self.calculate_shard(&combined_key)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        Ok(PartitionSpec::new(chain_id.to_string(), block_date, shard))
    }

    /// Get partition spec for a contract call record
    pub fn partition_for_contract_call(
        &self,
        chain_id: &str,
        transaction_hash: &str,
        call_index: i32,
        block_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        // Combine transaction hash and call index for unique distribution
        let combined_key = format!("{}:{}", transaction_hash, call_index);
        let shard = self.calculate_shard(&combined_key)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        Ok(PartitionSpec::new(chain_id.to_string(), block_date, shard))
    }

    /// Get partition spec for a notification delivery record
    pub fn partition_for_notification_delivery(
        &self,
        channel_type: &str,
        notification_id: &str,
        delivery_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        let shard = self.calculate_shard(notification_id)?;
        let delivery_date = self.timestamp_to_date(delivery_timestamp)?;

        // For notifications, we use channel_type as the first partition key
        Ok(PartitionSpec::new(
            channel_type.to_string(),
            delivery_date,
            shard,
        ))
    }

    // =========================================================================
    // DeFi Analytics Table Partitioning Methods
    // =========================================================================

    /// Get partition spec for a wallet activity record
    ///
    /// Uses address-prefix partitioning for efficient wallet tracking queries.
    /// The address prefix enables partition pruning when querying by wallet address.
    pub fn partition_for_wallet_activity(
        &self,
        chain_id: &str,
        wallet_address: &str,
        block_timestamp: i64,
    ) -> Result<AddressPrefixPartitionSpec, DuckLakeError> {
        let address_prefix = extract_address_prefix(wallet_address);
        let shard_count = self.get_table_shard_count(WALLET_ACTIVITY_TABLE);
        let shard = self.calculate_shard_with_count(wallet_address, shard_count)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        debug!(
            "Wallet activity partition: chain={}, prefix={}, date={}, shard={}",
            chain_id, address_prefix, block_date, shard
        );

        Ok(AddressPrefixPartitionSpec::new(
            chain_id.to_string(),
            address_prefix,
            block_date,
            shard,
        ))
    }

    /// Get partition spec for an LP position record
    ///
    /// Uses user_address for sharding to keep user's positions together.
    pub fn partition_for_lp_position(
        &self,
        chain_id: &str,
        user_address: &str,
        block_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        let shard_count = self.get_table_shard_count(LP_POSITIONS_TABLE);
        let shard = self.calculate_shard_with_count(user_address, shard_count)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        Ok(PartitionSpec::new(chain_id.to_string(), block_date, shard))
    }

    /// Get partition spec for a yield event record
    ///
    /// Uses user_address for sharding to keep user's yield events together.
    pub fn partition_for_yield_event(
        &self,
        chain_id: &str,
        user_address: &str,
        block_timestamp: i64,
    ) -> Result<PartitionSpec, DuckLakeError> {
        let shard_count = self.get_table_shard_count(YIELD_EVENTS_TABLE);
        let shard = self.calculate_shard_with_count(user_address, shard_count)?;
        let block_date = self.timestamp_to_date(block_timestamp)?;

        Ok(PartitionSpec::new(chain_id.to_string(), block_date, shard))
    }

    /// Get partition spec for a token holdings snapshot record
    ///
    /// Uses snapshot_date as the primary temporal partition key.
    /// Shards by wallet_address for even distribution.
    pub fn partition_for_token_holding(
        &self,
        chain_id: &str,
        wallet_address: &str,
        snapshot_timestamp: i64,
    ) -> Result<SnapshotPartitionSpec, DuckLakeError> {
        let shard_count = self.get_table_shard_count(TOKEN_HOLDINGS_TABLE);
        let shard = self.calculate_shard_with_count(wallet_address, shard_count)?;
        let snapshot_date = self.timestamp_to_date(snapshot_timestamp)?;

        Ok(SnapshotPartitionSpec::new(
            chain_id.to_string(),
            snapshot_date,
            shard,
        ))
    }

    /// Get partition spec for a token OHLCV record
    ///
    /// Uses interval as a partition key for efficient time-series queries.
    pub fn partition_for_token_ohlcv(
        &self,
        chain_id: &str,
        token_address: &str,
        interval: &str,
        interval_timestamp: i64,
    ) -> Result<IntervalPartitionSpec, DuckLakeError> {
        let shard_count = self.get_table_shard_count(TOKEN_OHLCV_TABLE);
        let shard = self.calculate_shard_with_count(token_address, shard_count)?;
        let block_date = self.timestamp_to_date(interval_timestamp)?;

        // Validate interval
        let valid_intervals = ["1m", "5m", "15m", "1h", "4h", "1d"];
        if !valid_intervals.contains(&interval) {
            warn!(
                "Invalid OHLCV interval '{}', expected one of: {:?}",
                interval, valid_intervals
            );
        }

        Ok(IntervalPartitionSpec::new(
            chain_id.to_string(),
            interval.to_string(),
            block_date,
            shard,
        ))
    }

    /// Get partition spec for an address index record
    ///
    /// Uses address-prefix partitioning for fast address lookups.
    pub fn partition_for_address_index(
        &self,
        chain_id: &str,
        address: &str,
        first_seen_timestamp: i64,
    ) -> Result<AddressPrefixPartitionSpec, DuckLakeError> {
        let address_prefix = extract_address_prefix(address);
        let shard_count = self.get_table_shard_count(ADDRESS_INDEX_TABLE);
        let shard = self.calculate_shard_with_count(address, shard_count)?;
        let block_date = self.timestamp_to_date(first_seen_timestamp)?;

        Ok(AddressPrefixPartitionSpec::new(
            chain_id.to_string(),
            address_prefix,
            block_date,
            shard,
        ))
    }

    /// Convert Unix timestamp to date string (YYYY-MM-DD)
    fn timestamp_to_date(&self, timestamp: i64) -> Result<String, DuckLakeError> {
        let datetime = DateTime::from_timestamp(timestamp, 0).ok_or_else(|| {
            DuckLakeError::SerializationError(format!("Invalid timestamp: {}", timestamp))
        })?;

        Ok(datetime.format("%Y-%m-%d").to_string())
    }

    /// Get all partitions for a given date range and chain
    pub fn get_partitions_for_date_range(
        &self,
        chain_id: &str,
        start_date: &str,
        end_date: &str,
    ) -> Result<Vec<PartitionSpec>, DuckLakeError> {
        let mut partitions = Vec::new();

        // Parse dates
        let start = chrono::NaiveDate::parse_from_str(start_date, "%Y-%m-%d")
            .map_err(|e| DuckLakeError::SerializationError(format!("Invalid start date: {}", e)))?;
        let end = chrono::NaiveDate::parse_from_str(end_date, "%Y-%m-%d")
            .map_err(|e| DuckLakeError::SerializationError(format!("Invalid end date: {}", e)))?;

        // Generate all partitions for date range
        let mut current_date = start;
        while current_date <= end {
            let date_str = current_date.format("%Y-%m-%d").to_string();

            // Add all shards for this date
            for shard in 0..self.shard_count {
                partitions.push(PartitionSpec::new(
                    chain_id.to_string(),
                    date_str.clone(),
                    shard,
                ));
            }

            current_date = current_date
                .succ_opt()
                .ok_or_else(|| DuckLakeError::SerializationError("Date overflow".to_string()))?;
        }

        Ok(partitions)
    }

    /// Get partition statistics for monitoring
    pub fn get_partition_stats(&self, partitions: &[PartitionSpec]) -> PartitionStats {
        let mut chain_counts = HashMap::new();
        let mut date_counts = HashMap::new();
        let mut shard_counts = HashMap::new();

        for partition in partitions {
            *chain_counts.entry(partition.chain_id.clone()).or_insert(0) += 1;
            *date_counts.entry(partition.block_date.clone()).or_insert(0) += 1;
            *shard_counts.entry(partition.shard).or_insert(0) += 1;
        }

        PartitionStats {
            total_partitions: partitions.len(),
            unique_chains: chain_counts.len(),
            unique_dates: date_counts.len(),
            unique_shards: shard_counts.len(),
            chain_distribution: chain_counts,
            date_distribution: date_counts,
            shard_distribution: shard_counts,
        }
    }
}

/// Partition statistics for monitoring
#[derive(Debug, Serialize, Deserialize)]
pub struct PartitionStats {
    pub total_partitions: usize,
    pub unique_chains: usize,
    pub unique_dates: usize,
    pub unique_shards: usize,
    pub chain_distribution: HashMap<String, u32>,
    pub date_distribution: HashMap<String, u32>,
    pub shard_distribution: HashMap<u16, u32>,
}

impl Default for Partitioner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_shard_consistency() {
        let partitioner = Partitioner::new();
        let hash = "0x1234567890abcdef1234567890abcdef12345678";

        // Same hash should always produce same shard
        let shard1 = partitioner.calculate_shard(hash).unwrap();
        let shard2 = partitioner.calculate_shard(hash).unwrap();
        assert_eq!(shard1, shard2);

        // Should be within shard range
        assert!(shard1 < DEFAULT_SHARD_COUNT);
    }

    #[test]
    fn test_partition_for_block() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200; // 2022-01-01 00:00:00 UTC

        let partition = partitioner
            .partition_for_block("ethereum_mainnet", "0x1234567890abcdef", timestamp)
            .unwrap();

        assert_eq!(partition.chain_id, "ethereum_mainnet");
        assert_eq!(partition.block_date, "2022-01-01");
        assert!(partition.shard < DEFAULT_SHARD_COUNT);
    }

    #[test]
    fn test_partition_logs_match_transactions() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200;
        let tx_hash = "0x1234567890abcdef";

        let tx_partition = partitioner
            .partition_for_transaction("ethereum_mainnet", tx_hash, timestamp)
            .unwrap();

        let log_partition = partitioner
            .partition_for_log("ethereum_mainnet", tx_hash, timestamp)
            .unwrap();

        // Logs should be in the same partition as their transaction
        assert_eq!(tx_partition, log_partition);
    }

    #[test]
    fn test_partition_spec_to_path() {
        let partition =
            PartitionSpec::new("ethereum_mainnet".to_string(), "2022-01-01".to_string(), 5);

        let path = partition.to_path("transactions");
        assert_eq!(
            path,
            "transactions/chain_id=ethereum_mainnet/block_date=2022-01-01/shard=5"
        );
    }

    #[test]
    fn test_partition_spec_from_path() {
        let path =
            "transactions/chain_id=ethereum_mainnet/block_date=2022-01-01/shard=5/file.parquet";
        let partition = PartitionSpec::from_path(path).unwrap();

        assert_eq!(partition.chain_id, "ethereum_mainnet");
        assert_eq!(partition.block_date, "2022-01-01");
        assert_eq!(partition.shard, 5);
    }

    #[test]
    fn test_get_partitions_for_date_range() {
        let partitioner = Partitioner::new();
        let partitions = partitioner
            .get_partitions_for_date_range("ethereum_mainnet", "2022-01-01", "2022-01-02")
            .unwrap();

        // Should have 2 days * 16 shards = 32 partitions
        assert_eq!(partitions.len(), 2 * DEFAULT_SHARD_COUNT as usize);
    }

    #[test]
    fn test_shard_calculation_edge_cases() {
        let partitioner = Partitioner::new();

        // Test empty string should fail
        assert!(partitioner.calculate_shard("").is_err());

        // Test very short hash
        let short_hash = "0x1";
        let shard = partitioner.calculate_shard(short_hash).unwrap();
        assert!(shard < DEFAULT_SHARD_COUNT);
    }

    // =========================================================================
    // Address Prefix Tests
    // =========================================================================

    #[test]
    fn test_extract_address_prefix() {
        // Standard Ethereum address
        assert_eq!(
            extract_address_prefix("0xa1b2c3d4e5f6789012345678901234567890abcd"),
            "a1b2"
        );

        // Without 0x prefix
        assert_eq!(
            extract_address_prefix("a1b2c3d4e5f6789012345678901234567890abcd"),
            "a1b2"
        );

        // Mixed case
        assert_eq!(
            extract_address_prefix("0xA1B2C3D4E5F6789012345678901234567890ABCD"),
            "a1b2"
        );

        // Short address (pads with zeros)
        assert_eq!(extract_address_prefix("0xab"), "ab00");

        // Very short
        assert_eq!(extract_address_prefix("0xa"), "a000");
    }

    #[test]
    fn test_address_prefix_partition_spec() {
        let spec = AddressPrefixPartitionSpec::new(
            "ethereum_mainnet".to_string(),
            "a1b2".to_string(),
            "2024-01-15".to_string(),
            42,
        );

        let path = spec.to_path("wallet_activity");
        assert_eq!(
            path,
            "wallet_activity/chain_id=ethereum_mainnet/address_prefix=a1b2/block_date=2024-01-15/shard=42"
        );

        let values = spec.to_partition_values();
        assert_eq!(values.get("chain_id").unwrap(), "ethereum_mainnet");
        assert_eq!(values.get("address_prefix").unwrap(), "a1b2");
        assert_eq!(values.get("block_date").unwrap(), "2024-01-15");
        assert_eq!(values.get("shard").unwrap(), "42");
    }

    #[test]
    fn test_address_prefix_partition_spec_from_path() {
        let path = "wallet_activity/chain_id=polygon_mainnet/address_prefix=dead/block_date=2024-06-01/shard=128/file.parquet";
        let spec = AddressPrefixPartitionSpec::from_path(path).unwrap();

        assert_eq!(spec.chain_id, "polygon_mainnet");
        assert_eq!(spec.address_prefix, "dead");
        assert_eq!(spec.block_date, "2024-06-01");
        assert_eq!(spec.shard, 128);
    }

    // =========================================================================
    // DeFi Table Partitioning Tests
    // =========================================================================

    #[test]
    fn test_partition_for_wallet_activity() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200; // 2022-01-01 00:00:00 UTC
        let wallet = "0xa1b2c3d4e5f6789012345678901234567890abcd";

        let partition = partitioner
            .partition_for_wallet_activity("ethereum_mainnet", wallet, timestamp)
            .unwrap();

        assert_eq!(partition.chain_id, "ethereum_mainnet");
        assert_eq!(partition.address_prefix, "a1b2");
        assert_eq!(partition.block_date, "2022-01-01");
        assert!(partition.shard < ADDRESS_BASED_SHARD_COUNT);
    }

    #[test]
    fn test_partition_for_lp_position() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200;
        let user = "0xdeadbeef12345678901234567890123456789012";

        let partition = partitioner
            .partition_for_lp_position("avalanche_mainnet", user, timestamp)
            .unwrap();

        assert_eq!(partition.chain_id, "avalanche_mainnet");
        assert_eq!(partition.block_date, "2022-01-01");
        assert!(partition.shard < MEDIUM_SHARD_COUNT);
    }

    #[test]
    fn test_partition_for_yield_event() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200;
        let user = "0xcafebeef12345678901234567890123456789012";

        let partition = partitioner
            .partition_for_yield_event("arbitrum_one", user, timestamp)
            .unwrap();

        assert_eq!(partition.chain_id, "arbitrum_one");
        assert_eq!(partition.block_date, "2022-01-01");
        assert!(partition.shard < MEDIUM_SHARD_COUNT);
    }

    #[test]
    fn test_partition_for_token_holding() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200;
        let wallet = "0x1234567890123456789012345678901234567890";

        let partition = partitioner
            .partition_for_token_holding("base_mainnet", wallet, timestamp)
            .unwrap();

        assert_eq!(partition.chain_id, "base_mainnet");
        assert_eq!(partition.snapshot_date, "2022-01-01");
        assert!(partition.shard < SNAPSHOT_SHARD_COUNT);
    }

    #[test]
    fn test_partition_for_token_ohlcv() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200;
        let token = "0xdac17f958d2ee523a2206206994597c13d831ec7"; // USDT

        let partition = partitioner
            .partition_for_token_ohlcv("ethereum_mainnet", token, "1h", timestamp)
            .unwrap();

        assert_eq!(partition.chain_id, "ethereum_mainnet");
        assert_eq!(partition.interval, "1h");
        assert_eq!(partition.block_date, "2022-01-01");
        assert!(partition.shard < MEDIUM_SHARD_COUNT);
    }

    #[test]
    fn test_partition_for_address_index() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200;
        let address = "0xdeadbeefcafebabe1234567890123456789012ab";

        let partition = partitioner
            .partition_for_address_index("solana_mainnet", address, timestamp)
            .unwrap();

        assert_eq!(partition.chain_id, "solana_mainnet");
        assert_eq!(partition.address_prefix, "dead");
        assert_eq!(partition.block_date, "2022-01-01");
        assert!(partition.shard < ADDRESS_BASED_SHARD_COUNT);
    }

    // =========================================================================
    // Table Shard Configuration Tests
    // =========================================================================

    #[test]
    fn test_table_shard_config_defaults() {
        let config = TableShardConfig::default();

        // Core tables
        assert_eq!(config.get_shard_count("blocks"), DEFAULT_SHARD_COUNT);
        assert_eq!(
            config.get_shard_count("transactions"),
            HIGH_CARDINALITY_SHARD_COUNT
        );
        assert_eq!(config.get_shard_count("logs"), HIGH_CARDINALITY_SHARD_COUNT);

        // DeFi tables
        assert_eq!(
            config.get_shard_count("wallet_activity"),
            ADDRESS_BASED_SHARD_COUNT
        );
        assert_eq!(config.get_shard_count("lp_positions"), MEDIUM_SHARD_COUNT);
        assert_eq!(
            config.get_shard_count("token_holdings"),
            SNAPSHOT_SHARD_COUNT
        );
        assert_eq!(
            config.get_shard_count("address_index"),
            ADDRESS_BASED_SHARD_COUNT
        );

        // Unknown table should return default
        assert_eq!(config.get_shard_count("unknown_table"), DEFAULT_SHARD_COUNT);
    }

    #[test]
    fn test_table_shard_config_custom() {
        let mut config = TableShardConfig::default();
        config.set_shard_count("custom_table", 512);

        assert_eq!(config.get_shard_count("custom_table"), 512);
    }

    #[test]
    fn test_partitioner_with_table_config() {
        let partitioner = Partitioner::new();

        // Verify table-specific shard counts are used
        assert_eq!(
            partitioner.get_table_shard_count("blocks"),
            DEFAULT_SHARD_COUNT
        );
        assert_eq!(
            partitioner.get_table_shard_count("transactions"),
            HIGH_CARDINALITY_SHARD_COUNT
        );
        assert_eq!(
            partitioner.get_table_shard_count("wallet_activity"),
            ADDRESS_BASED_SHARD_COUNT
        );
    }

    // =========================================================================
    // Snapshot and Interval Partition Spec Tests
    // =========================================================================

    #[test]
    fn test_snapshot_partition_spec() {
        let spec = SnapshotPartitionSpec::new(
            "ethereum_mainnet".to_string(),
            "2024-01-15".to_string(),
            64,
        );

        let path = spec.to_path("token_holdings");
        assert_eq!(
            path,
            "token_holdings/chain_id=ethereum_mainnet/snapshot_date=2024-01-15/shard=64"
        );

        let values = spec.to_partition_values();
        assert_eq!(values.get("chain_id").unwrap(), "ethereum_mainnet");
        assert_eq!(values.get("snapshot_date").unwrap(), "2024-01-15");
        assert_eq!(values.get("shard").unwrap(), "64");
    }

    #[test]
    fn test_interval_partition_spec() {
        let spec = IntervalPartitionSpec::new(
            "polygon_mainnet".to_string(),
            "1h".to_string(),
            "2024-01-15".to_string(),
            16,
        );

        let path = spec.to_path("token_ohlcv");
        assert_eq!(
            path,
            "token_ohlcv/chain_id=polygon_mainnet/interval=1h/block_date=2024-01-15/shard=16"
        );

        let values = spec.to_partition_values();
        assert_eq!(values.get("chain_id").unwrap(), "polygon_mainnet");
        assert_eq!(values.get("interval").unwrap(), "1h");
        assert_eq!(values.get("block_date").unwrap(), "2024-01-15");
        assert_eq!(values.get("shard").unwrap(), "16");
    }

    #[test]
    fn test_wallet_same_prefix_different_addresses() {
        let partitioner = Partitioner::new();
        let timestamp = 1640995200;

        // Two addresses with same prefix but different full addresses
        let wallet1 = "0xa1b2c3d4e5f6789012345678901234567890aaaa";
        let wallet2 = "0xa1b2999912345678901234567890123456789999";

        let partition1 = partitioner
            .partition_for_wallet_activity("ethereum_mainnet", wallet1, timestamp)
            .unwrap();
        let partition2 = partitioner
            .partition_for_wallet_activity("ethereum_mainnet", wallet2, timestamp)
            .unwrap();

        // Same prefix
        assert_eq!(partition1.address_prefix, partition2.address_prefix);
        assert_eq!(partition1.address_prefix, "a1b2");

        // But potentially different shards (depends on hash)
        // Both should be within the address-based shard count
        assert!(partition1.shard < ADDRESS_BASED_SHARD_COUNT);
        assert!(partition2.shard < ADDRESS_BASED_SHARD_COUNT);
    }
}
