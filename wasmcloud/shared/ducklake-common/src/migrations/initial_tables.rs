//! V001: Initial table creation migration
//!
//! Creates all 7 DuckLake tables with proper partitioning.

use super::ddl::{generate_create_table_ddl, schemas_to_json};
use super::definitions::{Migration, MigrationVersion};
use crate::schemas::{
    blocks_schema, contract_calls_schema, get_partition_columns_for_table, logs_schema,
    notification_deliveries_schema, protocol_events_schema, token_prices_schema,
    transactions_schema, BLOCKS_TABLE, CONTRACT_CALLS_TABLE, LOGS_TABLE,
    NOTIFICATION_DELIVERIES_TABLE, PROTOCOL_EVENTS_TABLE, TOKEN_PRICES_TABLE, TRANSACTIONS_TABLE,
};

/// V001: Create initial DuckLake tables
pub struct V001InitialTables;

impl Migration for V001InitialTables {
    fn version(&self) -> MigrationVersion {
        1
    }

    fn name(&self) -> &'static str {
        "create_initial_tables"
    }

    fn up(&self) -> &'static str {
        V001_UP_SQL
    }

    fn down(&self) -> &'static str {
        V001_DOWN_SQL
    }

    fn schema_json(&self) -> Option<String> {
        // Generate schema JSON from Arrow schemas
        let blocks = blocks_schema();
        let transactions = transactions_schema();
        let logs = logs_schema();
        let token_prices = token_prices_schema();
        let protocol_events = protocol_events_schema();
        let contract_calls = contract_calls_schema();
        let notification_deliveries = notification_deliveries_schema();

        Some(schemas_to_json(&[
            (BLOCKS_TABLE, blocks.as_ref()),
            (TRANSACTIONS_TABLE, transactions.as_ref()),
            (LOGS_TABLE, logs.as_ref()),
            (TOKEN_PRICES_TABLE, token_prices.as_ref()),
            (PROTOCOL_EVENTS_TABLE, protocol_events.as_ref()),
            (CONTRACT_CALLS_TABLE, contract_calls.as_ref()),
            (
                NOTIFICATION_DELIVERIES_TABLE,
                notification_deliveries.as_ref(),
            ),
        ]))
    }
}

/// Generate the up SQL dynamically from Arrow schemas
pub fn generate_v001_up_sql() -> String {
    let mut sql_parts = Vec::new();

    // Generate DDL for each table
    let tables = [
        (BLOCKS_TABLE, blocks_schema()),
        (TRANSACTIONS_TABLE, transactions_schema()),
        (LOGS_TABLE, logs_schema()),
        (TOKEN_PRICES_TABLE, token_prices_schema()),
        (PROTOCOL_EVENTS_TABLE, protocol_events_schema()),
        (CONTRACT_CALLS_TABLE, contract_calls_schema()),
        (
            NOTIFICATION_DELIVERIES_TABLE,
            notification_deliveries_schema(),
        ),
    ];

    for (table_name, schema) in tables {
        let partition_cols = get_partition_columns_for_table(table_name);
        let ddl = generate_create_table_ddl(table_name, &schema, &partition_cols);
        sql_parts.push(ddl);
    }

    sql_parts.join("\n\n")
}

/// Static SQL for up migration (generated from Arrow schemas)
const V001_UP_SQL: &str = r#"
-- V001: Create initial DuckLake tables
-- Generated from Arrow schema definitions

-- Blocks table
CREATE TABLE IF NOT EXISTS "blocks" (
    "chain_id" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "block_number" BIGINT NOT NULL,
    "block_hash" VARCHAR NOT NULL,
    "parent_hash" VARCHAR,
    "block_timestamp" TIMESTAMP NOT NULL,
    "gas_limit" BIGINT,
    "gas_used" BIGINT,
    "difficulty" BIGINT,
    "total_difficulty" BIGINT,
    "size_bytes" BIGINT,
    "transaction_count" INTEGER,
    "miner" VARCHAR,
    "nonce" VARCHAR,
    "extra_data" VARCHAR,
    "base_fee_per_gas" BIGINT,
    "withdrawal_root" VARCHAR,
    "slot_number" BIGINT,
    "validator_index" INTEGER,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "blocks" SET PARTITIONED BY (chain_id, block_date, shard);

-- Transactions table
CREATE TABLE IF NOT EXISTS "transactions" (
    "chain_id" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "block_number" BIGINT NOT NULL,
    "transaction_hash" VARCHAR NOT NULL,
    "transaction_index" INTEGER NOT NULL,
    "from_address" VARCHAR,
    "to_address" VARCHAR,
    "value" DECIMAL(38, 18),
    "gas_limit" BIGINT,
    "gas_used" BIGINT,
    "gas_price" DECIMAL(38, 18),
    "max_fee_per_gas" DECIMAL(38, 18),
    "max_priority_fee_per_gas" DECIMAL(38, 18),
    "status" VARCHAR NOT NULL,
    "transaction_fee" DECIMAL(38, 18),
    "effective_gas_price" DECIMAL(38, 18),
    "input_data" VARCHAR,
    "transaction_type" VARCHAR,
    "method_signature" VARCHAR,
    "nonce" BIGINT,
    "v" BIGINT,
    "r" VARCHAR,
    "s" VARCHAR,
    "recent_blockhash" VARCHAR,
    "compute_units_consumed" BIGINT,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "transactions" SET PARTITIONED BY (chain_id, block_date, shard);

-- Logs table (smart contract events)
CREATE TABLE IF NOT EXISTS "logs" (
    "chain_id" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "block_number" BIGINT NOT NULL,
    "transaction_hash" VARCHAR NOT NULL,
    "log_index" INTEGER NOT NULL,
    "address" VARCHAR NOT NULL,
    "topic0" VARCHAR,
    "topic1" VARCHAR,
    "topic2" VARCHAR,
    "topic3" VARCHAR,
    "data" VARCHAR,
    "event_name" VARCHAR,
    "event_signature" VARCHAR,
    "is_transfer" BOOLEAN,
    "is_approval" BOOLEAN,
    "is_swap" BOOLEAN,
    "is_mint" BOOLEAN,
    "is_burn" BOOLEAN,
    "ingested_at" TIMESTAMP NOT NULL,
    "decoded_at" TIMESTAMP
);
ALTER TABLE "logs" SET PARTITIONED BY (chain_id, block_date, shard);

-- Token prices table
CREATE TABLE IF NOT EXISTS "token_prices" (
    "chain_id" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "block_number" BIGINT NOT NULL,
    "price_timestamp" TIMESTAMP NOT NULL,
    "token_address" VARCHAR NOT NULL,
    "token_symbol" VARCHAR,
    "token_name" VARCHAR,
    "token_decimals" INTEGER,
    "price_usd" DECIMAL(18, 8),
    "price_eth" DECIMAL(18, 8),
    "price_btc" DECIMAL(18, 8),
    "source_type" VARCHAR NOT NULL,
    "source_name" VARCHAR NOT NULL,
    "source_address" VARCHAR,
    "dex_pool_address" VARCHAR,
    "liquidity_usd" DECIMAL(18, 8),
    "volume_24h_usd" DECIMAL(18, 8),
    "round_id" BIGINT,
    "confidence_interval" DECIMAL(8, 4),
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "token_prices" SET PARTITIONED BY (chain_id, block_date, shard);

-- Protocol events table
CREATE TABLE IF NOT EXISTS "protocol_events" (
    "chain_id" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "block_number" BIGINT NOT NULL,
    "transaction_hash" VARCHAR NOT NULL,
    "log_index" INTEGER,
    "protocol_name" VARCHAR NOT NULL,
    "protocol_version" VARCHAR,
    "contract_address" VARCHAR NOT NULL,
    "event_category" VARCHAR NOT NULL,
    "event_name" VARCHAR NOT NULL,
    "user_address" VARCHAR,
    "token_in_address" VARCHAR,
    "token_in_symbol" VARCHAR,
    "amount_in" DECIMAL(38, 18),
    "token_out_address" VARCHAR,
    "token_out_symbol" VARCHAR,
    "amount_out" DECIMAL(38, 18),
    "pool_address" VARCHAR,
    "position_id" BIGINT,
    "fee_tier" INTEGER,
    "tick_lower" INTEGER,
    "tick_upper" INTEGER,
    "value_usd" DECIMAL(18, 8),
    "fees_usd" DECIMAL(18, 8),
    "gas_cost_usd" DECIMAL(18, 8),
    "ingested_at" TIMESTAMP NOT NULL,
    "decoded_at" TIMESTAMP
);
ALTER TABLE "protocol_events" SET PARTITIONED BY (chain_id, block_date, shard);

-- Contract calls table
CREATE TABLE IF NOT EXISTS "contract_calls" (
    "chain_id" VARCHAR NOT NULL,
    "block_date" DATE NOT NULL,
    "shard" INTEGER NOT NULL,
    "block_number" BIGINT NOT NULL,
    "block_timestamp" TIMESTAMP NOT NULL,
    "transaction_hash" VARCHAR NOT NULL,
    "call_index" INTEGER NOT NULL,
    "from_address" VARCHAR NOT NULL,
    "to_address" VARCHAR NOT NULL,
    "call_type" VARCHAR NOT NULL,
    "method_signature" VARCHAR,
    "method_name" VARCHAR,
    "function_signature" VARCHAR,
    "input_data" VARCHAR,
    "output_data" VARCHAR,
    "decoded_input" VARCHAR,
    "decoded_output" VARCHAR,
    "gas_limit" BIGINT,
    "gas_used" BIGINT,
    "value" DECIMAL(38, 18),
    "call_depth" INTEGER,
    "success" BOOLEAN NOT NULL,
    "revert_reason" VARCHAR,
    "ingested_at" TIMESTAMP NOT NULL,
    "decoded_at" TIMESTAMP
);
ALTER TABLE "contract_calls" SET PARTITIONED BY (chain_id, year(block_timestamp), month(block_timestamp), day(block_timestamp));

-- Notification deliveries table
CREATE TABLE IF NOT EXISTS "notification_deliveries" (
    "delivery_date" DATE NOT NULL,
    "channel_type" VARCHAR NOT NULL,
    "shard" INTEGER NOT NULL,
    "notification_id" VARCHAR NOT NULL,
    "channel_id" VARCHAR NOT NULL,
    "endpoint_url" VARCHAR,
    "attempt_number" INTEGER NOT NULL,
    "max_attempts" INTEGER NOT NULL,
    "delivery_status" VARCHAR NOT NULL,
    "started_at" TIMESTAMP NOT NULL,
    "completed_at" TIMESTAMP,
    "response_time_ms" BIGINT,
    "http_status_code" INTEGER,
    "response_body" VARCHAR,
    "error_message" VARCHAR,
    "error_type" VARCHAR,
    "alert_id" VARCHAR,
    "transaction_hash" VARCHAR,
    "severity" VARCHAR,
    "message_size_bytes" INTEGER,
    "used_fallback" BOOLEAN NOT NULL,
    "fallback_url" VARCHAR,
    "retry_delay_ms" BIGINT,
    "provider_id" VARCHAR,
    "provider_version" VARCHAR,
    "ingested_at" TIMESTAMP NOT NULL
);
ALTER TABLE "notification_deliveries" SET PARTITIONED BY (delivery_date, channel_type, shard);
"#;

/// Static SQL for down migration (rollback)
const V001_DOWN_SQL: &str = r#"
-- V001: Drop all initial DuckLake tables
-- Order reversed to handle potential dependencies

DROP TABLE IF EXISTS "notification_deliveries";
DROP TABLE IF EXISTS "contract_calls";
DROP TABLE IF EXISTS "protocol_events";
DROP TABLE IF EXISTS "token_prices";
DROP TABLE IF EXISTS "logs";
DROP TABLE IF EXISTS "transactions";
DROP TABLE IF EXISTS "blocks";
"#;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_v001_migration_properties() {
        let migration = V001InitialTables;

        assert_eq!(migration.version(), 1);
        assert_eq!(migration.name(), "create_initial_tables");
        assert!(!migration.up().is_empty());
        assert!(!migration.down().is_empty());
    }

    #[test]
    fn test_v001_up_contains_all_tables() {
        let sql = V001_UP_SQL;

        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"blocks\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"transactions\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"logs\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"token_prices\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"protocol_events\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"contract_calls\""));
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS \"notification_deliveries\""));
    }

    #[test]
    fn test_v001_down_drops_all_tables() {
        let sql = V001_DOWN_SQL;

        assert!(sql.contains("DROP TABLE IF EXISTS \"blocks\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"transactions\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"logs\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"token_prices\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"protocol_events\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"contract_calls\""));
        assert!(sql.contains("DROP TABLE IF EXISTS \"notification_deliveries\""));
    }

    #[test]
    fn test_v001_partitioning() {
        let sql = V001_UP_SQL;

        // Blockchain tables should have chain_id, block_date, shard
        assert!(
            sql.contains("ALTER TABLE \"blocks\" SET PARTITIONED BY (chain_id, block_date, shard)")
        );
        assert!(sql.contains(
            "ALTER TABLE \"transactions\" SET PARTITIONED BY (chain_id, block_date, shard)"
        ));
        assert!(sql.contains("ALTER TABLE \"contract_calls\" SET PARTITIONED BY (chain_id, year(block_timestamp), month(block_timestamp), day(block_timestamp))"));

        // Notification deliveries should have different partitioning
        assert!(sql.contains("ALTER TABLE \"notification_deliveries\" SET PARTITIONED BY (delivery_date, channel_type, shard)"));
    }

    #[test]
    fn test_v001_schema_json() {
        let migration = V001InitialTables;
        let schema_json = migration.schema_json();

        assert!(schema_json.is_some());
        let json = schema_json.unwrap();

        // Should contain all tables
        assert!(json.contains("blocks"));
        assert!(json.contains("transactions"));
        assert!(json.contains("logs"));
        assert!(json.contains("notification_deliveries"));
    }

    #[test]
    fn test_generate_v001_up_sql() {
        let generated = generate_v001_up_sql();

        // Should generate DDL for all tables
        assert!(generated.contains("CREATE TABLE IF NOT EXISTS \"blocks\""));
        assert!(generated.contains("CREATE TABLE IF NOT EXISTS \"transactions\""));
        assert!(generated.contains("CREATE TABLE IF NOT EXISTS \"notification_deliveries\""));
    }
}
