//! V003: Add wallet_balances table for lazy field resolution
//!
//! Creates the wallet_balances table for storing token balances with timestamps.
//! This table is used by the alert system for lazy field resolution - balances
//! are fetched only when an alert's expression requires balance data.
//!
//! Key features:
//! - Snapshot-based storage with timestamps for historical balance queries
//! - Partitioned by chain_id and snapshot_date for efficient queries
//! - Z-ordered by wallet_address, token_address, snapshot_timestamp

use super::ddl::schemas_to_json;
use super::definitions::{Migration, MigrationVersion};
use crate::schemas::{wallet_balances_schema, WALLET_BALANCES_TABLE};

/// V003: Add wallet_balances table
pub struct V003AddWalletBalances;

impl Migration for V003AddWalletBalances {
    fn version(&self) -> MigrationVersion {
        3
    }

    fn name(&self) -> &'static str {
        "add_wallet_balances_table"
    }

    fn up(&self) -> &'static str {
        V003_UP_SQL
    }

    fn down(&self) -> &'static str {
        V003_DOWN_SQL
    }

    fn schema_json(&self) -> Option<String> {
        let wallet_balances = wallet_balances_schema();

        Some(schemas_to_json(&[(
            WALLET_BALANCES_TABLE,
            wallet_balances.as_ref(),
        )]))
    }
}

/// Static SQL for up migration
///
/// Creates the wallet_balances table with snapshot-based partitioning:
/// - Partition by: chain_id, snapshot_date
/// - Z-order: wallet_address, token_address, snapshot_timestamp
///
/// Used by the alert system for lazy field resolution when evaluating
/// alert expressions that reference balance fields.
const V003_UP_SQL: &str = r#"
-- V003: Add wallet_balances table for alert system lazy field resolution
-- Stores wallet token balances with timestamps for alert evaluation

-- ============================================================================
-- wallet_balances: Token balance snapshots for alert evaluation
-- ============================================================================
-- Partitioned by chain_id and snapshot_date for efficient time-based queries.
-- Supports lazy field resolution in the alert processor - balances are only
-- fetched when an alert's expression requires balance data.
CREATE TABLE IF NOT EXISTS "wallet_balances" (
    "chain_id" INTEGER NOT NULL,
    "snapshot_date" DATE NOT NULL,
    "wallet_address" VARCHAR NOT NULL,
    "token_address" VARCHAR NOT NULL,
    "token_symbol" VARCHAR,
    "token_decimals" INTEGER,
    "balance" HUGEINT NOT NULL,
    "balance_formatted" DOUBLE,
    "balance_usd" DOUBLE,
    "snapshot_timestamp" TIMESTAMP NOT NULL,
    "block_number" BIGINT,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "wallet_balances" SET PARTITIONED BY (chain_id, snapshot_date);

-- Create index for efficient wallet + token lookups
-- Note: DuckLake uses z-ordering, but we document the intended query patterns
-- Queries typically filter by: wallet_address AND token_address AND time range
"#;

/// Static SQL for down migration (rollback)
const V003_DOWN_SQL: &str = r#"
-- V003: Drop wallet_balances table
DROP TABLE IF EXISTS "wallet_balances";
"#;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_v003_migration_properties() {
        let migration = V003AddWalletBalances;

        assert_eq!(migration.version(), 3);
        assert_eq!(migration.name(), "add_wallet_balances_table");
        assert!(!migration.up().is_empty());
        assert!(!migration.down().is_empty());
    }

    #[test]
    fn test_v003_up_contains_table() {
        let sql = V003_UP_SQL;

        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"wallet_balances\""));
    }

    #[test]
    fn test_v003_down_drops_table() {
        let sql = V003_DOWN_SQL;

        assert!(sql.contains("DROP TABLE IF EXISTS \"wallet_balances\""));
    }

    #[test]
    fn test_v003_partitioning() {
        let sql = V003_UP_SQL;

        // wallet_balances should use snapshot_date partitioning
        assert!(sql.contains(
            "ALTER TABLE \"wallet_balances\" SET PARTITIONED BY (chain_id, snapshot_date)"
        ));
    }

    #[test]
    fn test_v003_required_columns() {
        let sql = V003_UP_SQL;

        // Required columns for alert system
        assert!(sql.contains("\"wallet_address\" VARCHAR NOT NULL"));
        assert!(sql.contains("\"token_address\" VARCHAR NOT NULL"));
        assert!(sql.contains("\"chain_id\" INTEGER NOT NULL"));
        assert!(sql.contains("\"balance\" HUGEINT NOT NULL"));
        assert!(sql.contains("\"snapshot_timestamp\" TIMESTAMP NOT NULL"));
    }

    #[test]
    fn test_v003_optional_columns() {
        let sql = V003_UP_SQL;

        // Optional columns for enrichment
        assert!(sql.contains("\"balance_formatted\" DOUBLE"));
        assert!(sql.contains("\"balance_usd\" DOUBLE"));
        assert!(sql.contains("\"token_symbol\" VARCHAR"));
        assert!(sql.contains("\"token_decimals\" INTEGER"));
        assert!(sql.contains("\"block_number\" BIGINT"));
    }

    #[test]
    fn test_v003_schema_json() {
        let migration = V003AddWalletBalances;
        let schema_json = migration.schema_json();

        assert!(schema_json.is_some());
        let json = schema_json.unwrap();

        // Should contain wallet_balances table
        assert!(json.contains("wallet_balances"));
    }
}
