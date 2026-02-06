//! DuckLake Common Library
//!
//! Shared types, schemas, configuration, and utilities for the DuckLake
//! read and write providers. Both providers connect to the same DuckLake
//! instance (PostgreSQL metadata catalog + S3/MinIO parquet storage).

pub mod error;
pub mod schemas;
pub mod subject_parser;
pub mod types;

// Native-only modules (DuckDB / Postgres / filesystem access). Actors compile to WASM and must
// only depend on the pure contract/types layer.
#[cfg(not(target_family = "wasm"))]
pub mod config;
#[cfg(not(target_family = "wasm"))]
pub mod connection;
#[cfg(not(target_family = "wasm"))]
pub mod maintenance;
#[cfg(not(target_family = "wasm"))]
pub mod migrations;
#[cfg(not(target_family = "wasm"))]
pub mod partitioner;

// Re-export commonly used types
pub use error::DuckLakeError;
pub use schemas::{
    address_index_schema,
    address_transactions_schema,
    // Core table schemas
    blocks_schema,
    contract_calls_schema,
    get_all_table_names,
    get_partition_columns,
    get_partition_columns_for_table,
    get_schema_for_table,
    get_z_order_columns,
    logs_schema,
    lp_positions_schema,
    notification_deliveries_schema,
    processed_transfers_schema,
    protocol_events_schema,
    token_holdings_schema,
    token_ohlcv_schema,
    token_prices_schema,
    // NEW: Unified schema tables (Schema Redesign)
    token_transfers_schema,
    transactions_schema,
    // DeFi analytics table schemas
    wallet_activity_schema,
    yield_events_schema,
    ADDRESS_INDEX_TABLE,
    ADDRESS_TRANSACTIONS_TABLE,
    // Core table names
    BLOCKS_TABLE,
    CONTRACT_CALLS_TABLE,
    LOGS_TABLE,
    LP_POSITIONS_TABLE,
    NOTIFICATION_DELIVERIES_TABLE,
    PROTOCOL_EVENTS_TABLE,
    TOKEN_HOLDINGS_TABLE,
    TOKEN_OHLCV_TABLE,
    TOKEN_PRICES_TABLE,
    // NEW: Unified schema table names (Schema Redesign)
    TOKEN_TRANSFERS_TABLE,
    TRANSACTIONS_TABLE,
    // DeFi analytics table names
    WALLET_ACTIVITY_TABLE,
    YIELD_EVENTS_TABLE,
};

// Re-export deprecated tables for backward compatibility
// These will emit deprecation warnings when used
#[allow(deprecated)]
pub use schemas::{
    DECODED_TRANSACTIONS_EVM_TABLE, PROCESSED_TRANSFERS_TABLE, TRANSACTIONS_BTC_TABLE,
    TRANSACTIONS_EVM_TABLE, TRANSACTIONS_SVM_TABLE,
};
pub use subject_parser::{SubjectInfo, SubjectParseError};
pub use types::*;

#[cfg(not(target_family = "wasm"))]
pub use config::{
    CompressionStrategy, DuckLakeConfig, HotDataConfig, TableCompactionConfig, TableConfigMap,
};
#[cfg(not(target_family = "wasm"))]
pub use connection::create_ducklake_connection;
#[cfg(not(target_family = "wasm"))]
pub use maintenance::{
    apply_z_ordering,
    compact_table,
    compact_table_with_config,
    delete_orphaned_files,
    expire_snapshots,
    flush_inlined_data,
    hot_compact_partition,
    promote_hot_to_warm,
    rewrite_data_files,
    run_full_maintenance,
    run_tiered_maintenance,
    // Tiered compaction system
    DataTier,
    EffectiveCompactionConfig,
    MaintenanceReport,
    MaintenanceSchedule,
    TieredCompactionConfig,
    TieredMaintenanceReport,
};
#[cfg(not(target_family = "wasm"))]
pub use migrations::{
    get_migration_status, run_all_migrations, verify_migration_checksums, MigrationResult,
    MigrationRunner, MigrationStatus,
};
#[cfg(not(target_family = "wasm"))]
pub use partitioner::{
    extract_address_prefix, AddressPrefixPartitionSpec, IntervalPartitionSpec, PartitionSpec,
    PartitionStats, Partitioner, SnapshotPartitionSpec, TableShardConfig,
    ADDRESS_BASED_SHARD_COUNT, DEFAULT_SHARD_COUNT, HIGH_CARDINALITY_SHARD_COUNT,
    MEDIUM_SHARD_COUNT, SNAPSHOT_SHARD_COUNT,
};

/// Result type alias for DuckLake operations
pub type Result<T> = std::result::Result<T, DuckLakeError>;
