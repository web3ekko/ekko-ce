//! V002: Add DeFi analytics tables
//!
//! Creates 6 new tables optimized for DeFi analytics and wallet tracking:
//! - wallet_activity: Address-centric view with address-prefix partitioning
//! - lp_positions: LP position tracking for DeFi protocols
//! - yield_events: Yield farming, staking, and reward tracking
//! - token_holdings: Point-in-time balance snapshots
//! - token_ohlcv: Pre-aggregated OHLCV price candles
//! - address_index: Fast address lookup table

use super::ddl::schemas_to_json;
use super::definitions::{Migration, MigrationVersion};
use crate::schemas::{
    address_index_schema, lp_positions_schema, token_holdings_schema, token_ohlcv_schema,
    wallet_activity_schema, yield_events_schema, ADDRESS_INDEX_TABLE, LP_POSITIONS_TABLE,
    TOKEN_HOLDINGS_TABLE, TOKEN_OHLCV_TABLE, WALLET_ACTIVITY_TABLE, YIELD_EVENTS_TABLE,
};

/// V002: Add DeFi analytics tables
pub struct V002AddDefiTables;

impl Migration for V002AddDefiTables {
    fn version(&self) -> MigrationVersion {
        2
    }

    fn name(&self) -> &'static str {
        "add_defi_analytics_tables"
    }

    fn up(&self) -> &'static str {
        V002_UP_SQL
    }

    fn down(&self) -> &'static str {
        V002_DOWN_SQL
    }

    fn schema_json(&self) -> Option<String> {
        let wallet_activity = wallet_activity_schema();
        let lp_positions = lp_positions_schema();
        let yield_events = yield_events_schema();
        let token_holdings = token_holdings_schema();
        let token_ohlcv = token_ohlcv_schema();
        let address_index = address_index_schema();

        Some(schemas_to_json(&[
            (WALLET_ACTIVITY_TABLE, wallet_activity.as_ref()),
            (LP_POSITIONS_TABLE, lp_positions.as_ref()),
            (YIELD_EVENTS_TABLE, yield_events.as_ref()),
            (TOKEN_HOLDINGS_TABLE, token_holdings.as_ref()),
            (TOKEN_OHLCV_TABLE, token_ohlcv.as_ref()),
            (ADDRESS_INDEX_TABLE, address_index.as_ref()),
        ]))
    }
}

/// Static SQL for up migration
///
/// Creates 6 DeFi analytics tables with optimized partitioning:
/// - wallet_activity: 4-level partitioning (chain_id, address_prefix, block_date, shard)
/// - token_holdings: snapshot_date based partitioning
/// - token_ohlcv: interval-based partitioning for time-series queries
/// - address_index: 4-level partitioning with address_prefix
const V002_UP_SQL: &str = r#"
-- V002: Add DeFi analytics tables
-- Optimized for wallet tracking, LP positions, yields, and price analytics

-- ============================================================================
-- wallet_activity: Address-centric view for fast wallet tracking queries
-- ============================================================================
-- Uses 4-level partitioning: (chain_id, address_prefix, block_date, shard)
-- address_prefix is the first 4 hex characters after 0x for partition pruning
CREATE TABLE IF NOT EXISTS "wallet_activity" (
    "chain_id" VARCHAR NOT NULL,
    "address_prefix" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "wallet_address" VARCHAR NOT NULL,
    "counterparty_address" VARCHAR,
    "direction" VARCHAR NOT NULL,
    "token_address" VARCHAR,
    "token_symbol" VARCHAR,
    "amount" DECIMAL(38, 18) NOT NULL,
    "amount_usd" DECIMAL(18, 8),
    "block_number" BIGINT NOT NULL,
    "transaction_hash" VARCHAR NOT NULL,
    "log_index" INTEGER,
    "activity_type" VARCHAR NOT NULL,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "wallet_activity" SET PARTITIONED BY (chain_id, address_prefix, block_date, shard);

-- ============================================================================
-- lp_positions: Liquidity provider position tracking
-- ============================================================================
-- Tracks LP positions across DEXs (Uniswap V2/V3, Curve, Balancer, etc.)
CREATE TABLE IF NOT EXISTS "lp_positions" (
    "chain_id" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "user_address" VARCHAR NOT NULL,
    "protocol_name" VARCHAR NOT NULL,
    "pool_address" VARCHAR NOT NULL,
    "position_id" VARCHAR,
    "token0_address" VARCHAR NOT NULL,
    "token0_symbol" VARCHAR,
    "token1_address" VARCHAR NOT NULL,
    "token1_symbol" VARCHAR,
    "liquidity" DECIMAL(38, 18) NOT NULL,
    "amount0" DECIMAL(38, 18),
    "amount1" DECIMAL(38, 18),
    "tick_lower" INTEGER,
    "tick_upper" INTEGER,
    "fees_earned_token0" DECIMAL(38, 18),
    "fees_earned_token1" DECIMAL(38, 18),
    "fees_earned_usd" DECIMAL(18, 8),
    "position_value_usd" DECIMAL(18, 8),
    "action" VARCHAR NOT NULL,
    "block_number" BIGINT NOT NULL,
    "transaction_hash" VARCHAR NOT NULL,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "lp_positions" SET PARTITIONED BY (chain_id, block_date, shard);

-- ============================================================================
-- yield_events: Yield farming, staking, and reward tracking
-- ============================================================================
-- Tracks yield farming deposits, withdrawals, harvests, and rewards
CREATE TABLE IF NOT EXISTS "yield_events" (
    "chain_id" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "user_address" VARCHAR NOT NULL,
    "protocol_name" VARCHAR NOT NULL,
    "vault_address" VARCHAR NOT NULL,
    "underlying_token" VARCHAR,
    "action" VARCHAR NOT NULL,
    "amount" DECIMAL(38, 18) NOT NULL,
    "amount_usd" DECIMAL(18, 8),
    "reward_token" VARCHAR,
    "reward_amount" DECIMAL(38, 18),
    "reward_usd" DECIMAL(18, 8),
    "apy_at_time" DECIMAL(8, 4),
    "block_number" BIGINT NOT NULL,
    "transaction_hash" VARCHAR NOT NULL,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "yield_events" SET PARTITIONED BY (chain_id, block_date, shard);

-- ============================================================================
-- token_holdings: Point-in-time balance snapshots
-- ============================================================================
-- Daily snapshots of wallet token balances for portfolio tracking
CREATE TABLE IF NOT EXISTS "token_holdings" (
    "chain_id" VARCHAR NOT NULL,
    "snapshot_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "wallet_address" VARCHAR NOT NULL,
    "token_address" VARCHAR NOT NULL,
    "token_symbol" VARCHAR,
    "balance" DECIMAL(38, 18) NOT NULL,
    "balance_usd" DECIMAL(18, 8),
    "price_at_snapshot" DECIMAL(18, 8),
    "block_number" BIGINT NOT NULL,
    "snapshot_timestamp" TIMESTAMP NOT NULL,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "token_holdings" SET PARTITIONED BY (chain_id, snapshot_date, shard);

-- ============================================================================
-- token_ohlcv: Pre-aggregated OHLCV price candles
-- ============================================================================
-- Pre-computed OHLCV candles at multiple intervals for efficient price queries
CREATE TABLE IF NOT EXISTS "token_ohlcv" (
    "chain_id" VARCHAR NOT NULL,
    "interval" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "token_address" VARCHAR NOT NULL,
    "token_symbol" VARCHAR,
    "interval_start" TIMESTAMP NOT NULL,
    "open" DECIMAL(18, 8) NOT NULL,
    "high" DECIMAL(18, 8) NOT NULL,
    "low" DECIMAL(18, 8) NOT NULL,
    "close" DECIMAL(18, 8) NOT NULL,
    "volume_token" DECIMAL(38, 18) NOT NULL,
    "volume_usd" DECIMAL(18, 8) NOT NULL,
    "vwap" DECIMAL(18, 8),
    "trade_count" BIGINT NOT NULL,
    "source_pool" VARCHAR,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "token_ohlcv" SET PARTITIONED BY (chain_id, interval, block_date, shard);

-- ============================================================================
-- address_index: Fast address lookup table
-- ============================================================================
-- Index table for quick address lookups across all chains
-- Uses address_prefix partitioning for efficient queries
CREATE TABLE IF NOT EXISTS "address_index" (
    "chain_id" VARCHAR NOT NULL,
    "address_prefix" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "address" VARCHAR NOT NULL,
    "address_type" VARCHAR NOT NULL,
    "first_seen_block" BIGINT NOT NULL,
    "first_seen_date" DATE NOT NULL,
    "last_seen_block" BIGINT NOT NULL,
    "last_seen_date" DATE NOT NULL,
    "transaction_count" BIGINT NOT NULL,
    "token_transfer_count" BIGINT NOT NULL,
    "unique_counterparties" INTEGER,
    "is_contract" BOOLEAN NOT NULL,
    "contract_name" VARCHAR,
    "token_symbol" VARCHAR,
    "labels" VARCHAR,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "address_index" SET PARTITIONED BY (chain_id, address_prefix, block_date, shard);
"#;

/// Static SQL for down migration (rollback)
const V002_DOWN_SQL: &str = r#"
-- V002: Drop DeFi analytics tables
-- Order reversed to handle potential dependencies

DROP TABLE IF EXISTS "address_index";
DROP TABLE IF EXISTS "token_ohlcv";
DROP TABLE IF EXISTS "token_holdings";
DROP TABLE IF EXISTS "yield_events";
DROP TABLE IF EXISTS "lp_positions";
DROP TABLE IF EXISTS "wallet_activity";
"#;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_v002_migration_properties() {
        let migration = V002AddDefiTables;

        assert_eq!(migration.version(), 2);
        assert_eq!(migration.name(), "add_defi_analytics_tables");
        assert!(!migration.up().is_empty());
        assert!(!migration.down().is_empty());
    }

    #[test]
    fn test_v002_up_contains_all_tables() {
        let sql = V002_UP_SQL;

        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"wallet_activity\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"lp_positions\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"yield_events\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"token_holdings\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"token_ohlcv\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"address_index\""));
    }

    #[test]
    fn test_v002_down_drops_all_tables() {
        let sql = V002_DOWN_SQL;

        assert!(sql.contains("DROP TABLE IF EXISTS \"wallet_activity\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"lp_positions\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"yield_events\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"token_holdings\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"token_ohlcv\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"address_index\""));
    }

    #[test]
    fn test_v002_address_prefix_partitioning() {
        let sql = V002_UP_SQL;

        // wallet_activity and address_index should use address_prefix partitioning
        assert!(sql.contains(
            "ALTER TABLE \"wallet_activity\" SET PARTITIONED BY (chain_id, address_prefix, block_date, shard)"
        ));
        assert!(sql.contains(
            "ALTER TABLE \"address_index\" SET PARTITIONED BY (chain_id, address_prefix, block_date, shard)"
        ));
    }

    #[test]
    fn test_v002_snapshot_partitioning() {
        let sql = V002_UP_SQL;

        // token_holdings should use snapshot_date partitioning
        assert!(sql.contains(
            "ALTER TABLE \"token_holdings\" SET PARTITIONED BY (chain_id, snapshot_date, shard)"
        ));
    }

    #[test]
    fn test_v002_interval_partitioning() {
        let sql = V002_UP_SQL;

        // token_ohlcv should use interval partitioning
        assert!(sql.contains(
            "ALTER TABLE \"token_ohlcv\" SET PARTITIONED BY (chain_id, interval, block_date, shard)"
        ));
    }

    #[test]
    fn test_v002_standard_partitioning() {
        let sql = V002_UP_SQL;

        // lp_positions and yield_events should use standard partitioning
        assert!(sql.contains(
            "ALTER TABLE \"lp_positions\" SET PARTITIONED BY (chain_id, block_date, shard)"
        ));
        assert!(sql.contains(
            "ALTER TABLE \"yield_events\" SET PARTITIONED BY (chain_id, block_date, shard)"
        ));
    }

    #[test]
    fn test_v002_schema_json() {
        let migration = V002AddDefiTables;
        let schema_json = migration.schema_json();

        assert!(schema_json.is_some());
        let json = schema_json.unwrap();

        // Should contain all 6 new tables
        assert!(json.contains("wallet_activity"));
        assert!(json.contains("lp_positions"));
        assert!(json.contains("yield_events"));
        assert!(json.contains("token_holdings"));
        assert!(json.contains("token_ohlcv"));
        assert!(json.contains("address_index"));
    }

    #[test]
    fn test_v002_decimal_precision() {
        let sql = V002_UP_SQL;

        // Financial amounts should use DECIMAL(38, 18)
        assert!(sql.contains("DECIMAL(38, 18)"));

        // USD amounts should use DECIMAL(18, 8)
        assert!(sql.contains("DECIMAL(18, 8)"));

        // APY should use DECIMAL(8, 4)
        assert!(sql.contains("DECIMAL(8, 4)"));
    }

    #[test]
    fn test_v002_wallet_activity_columns() {
        let sql = V002_UP_SQL;

        // wallet_activity should have address_prefix column
        assert!(sql.contains("\"address_prefix\" VARCHAR NOT NULL"));
        assert!(sql.contains("\"wallet_address\" VARCHAR NOT NULL"));
        assert!(sql.contains("\"direction\" VARCHAR NOT NULL"));
        assert!(sql.contains("\"activity_type\" VARCHAR NOT NULL"));
    }

    #[test]
    fn test_v002_lp_positions_columns() {
        let sql = V002_UP_SQL;

        // lp_positions should have tick columns for concentrated liquidity
        assert!(sql.contains("\"tick_lower\" INTEGER"));
        assert!(sql.contains("\"tick_upper\" INTEGER"));
        assert!(sql.contains("\"position_id\" VARCHAR"));
        assert!(sql.contains("\"liquidity\" DECIMAL(38, 18) NOT NULL"));
    }

    #[test]
    fn test_v002_token_ohlcv_columns() {
        let sql = V002_UP_SQL;

        // token_ohlcv should have OHLCV columns
        assert!(sql.contains("\"open\" DECIMAL(18, 8) NOT NULL"));
        assert!(sql.contains("\"high\" DECIMAL(18, 8) NOT NULL"));
        assert!(sql.contains("\"low\" DECIMAL(18, 8) NOT NULL"));
        assert!(sql.contains("\"close\" DECIMAL(18, 8) NOT NULL"));
        assert!(sql.contains("\"vwap\" DECIMAL(18, 8)"));
        assert!(sql.contains("\"trade_count\" BIGINT NOT NULL"));
    }
}
