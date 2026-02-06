//! DuckLake writer for batch writes
//!
//! Consumes ready batches and writes them to DuckLake.
//! Uses spawn_blocking for DuckDB operations since Connection is not Send.
//!
//! ## Batch Insert Optimization (Schema Redesign)
//!
//! Implements efficient batch writes using NDJSON (Newline-delimited JSON):
//! - All records in a batch written to a single NDJSON file
//! - Single INSERT statement reads all records at once
//! - Significantly faster than per-record INSERT (10-100x improvement)
//!
//! ## Partitioning Strategy
//!
//! Supports both function-based and shard-based partitioning depending on table schema.

use anyhow::{bail, Context, Result};
use chrono::{DateTime, Utc};
use duckdb::Connection;
use ducklake_common::{
    config::DuckLakeConfig,
    connection::create_ducklake_connection,
    migrations::ddl::generate_create_table_ddl,
    partitioner::Partitioner,
    schemas::{
        get_partition_columns_for_table, get_schema_for_table, CONTRACT_CALLS_TABLE,
        NOTIFICATION_CONTENT_TABLE, TRANSACTIONS_TABLE,
    },
};
use serde_json::{Map, Number, Value};
use std::collections::HashSet;
use std::fs;
use std::io::{BufWriter, Write};
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::mpsc;
use tracing::{debug, error, info, instrument, warn};

use crate::buffer::ReadyBatch;

fn ensure_contract_calls_block_timestamp(map: &mut Map<String, Value>) -> Result<()> {
    if map.contains_key("block_timestamp") {
        return Ok(());
    }

    let timestamp = map.get("timestamp").and_then(|value| match value {
        Value::Number(num) => num.as_i64(),
        Value::String(text) => text.parse::<i64>().ok(),
        _ => None,
    });

    if let Some(ts) = timestamp {
        map.insert(
            "block_timestamp".to_string(),
            Value::Number(Number::from(ts)),
        );
        return Ok(());
    }

    bail!("contract_calls record missing block_timestamp or timestamp");
}

fn ensure_notification_content_partition_fields(
    map: &mut Map<String, Value>,
    partitioner: &Partitioner,
) -> Result<()> {
    let user_id = map
        .get("user_id")
        .and_then(|value| value.as_str())
        .context("notification_content record missing user_id")?
        .to_string();

    if !map.contains_key("user_id_prefix") {
        let prefix: String = user_id.chars().take(8).collect();
        map.insert("user_id_prefix".to_string(), Value::String(prefix));
    }

    if !map.contains_key("shard") {
        let shard = partitioner
            .calculate_shard_for_table(&user_id, NOTIFICATION_CONTENT_TABLE)
            .context("Failed to calculate shard for notification_content")?;
        map.insert(
            "shard".to_string(),
            Value::Number(Number::from(u64::from(shard))),
        );
    }

    Ok(())
}

fn is_transactions_table(table: &str) -> bool {
    table == TRANSACTIONS_TABLE || table.starts_with("transactions_")
}

fn parse_block_timestamp(value: &Value) -> Option<i64> {
    match value {
        Value::Number(num) => num.as_i64().or_else(|| num.as_u64().map(|val| val as i64)),
        Value::String(text) => {
            if let Ok(parsed) = text.parse::<i64>() {
                return Some(parsed);
            }
            DateTime::parse_from_rfc3339(text)
                .ok()
                .map(|dt| dt.timestamp())
        }
        _ => None,
    }
}

fn ensure_transaction_required_fields(
    map: &mut Map<String, Value>,
    partitioner: &Partitioner,
    allowed_columns: &HashSet<String>,
) -> Result<()> {
    let needs_partition =
        allowed_columns.contains("block_date") || allowed_columns.contains("shard");
    if needs_partition {
        let chain_id = map
            .get("chain_id")
            .and_then(|value| value.as_str())
            .context("transactions record missing chain_id")?;
        let tx_hash = map
            .get("transaction_hash")
            .and_then(|value| value.as_str())
            .context("transactions record missing transaction_hash")?;
        let block_timestamp = map
            .get("block_timestamp")
            .and_then(parse_block_timestamp)
            .or_else(|| map.get("block_number").and_then(parse_block_timestamp))
            .context("transactions record missing block_timestamp")?;

        let partition =
            partitioner.partition_for_transaction(chain_id, tx_hash, block_timestamp)?;

        if allowed_columns.contains("block_date") && !map.contains_key("block_date") {
            map.insert(
                "block_date".to_string(),
                Value::String(partition.block_date),
            );
        }
        if allowed_columns.contains("shard") && !map.contains_key("shard") {
            map.insert(
                "shard".to_string(),
                Value::Number(Number::from(u64::from(partition.shard))),
            );
        }
    }

    if allowed_columns.contains("transaction_index") && !map.contains_key("transaction_index") {
        map.insert(
            "transaction_index".to_string(),
            Value::Number(Number::from(0)),
        );
    }

    if allowed_columns.contains("status") && !map.contains_key("status") {
        map.insert("status".to_string(), Value::String("SUCCESS".to_string()));
    }

    Ok(())
}

fn build_select_exprs(column_names: &[String]) -> String {
    column_names
        .iter()
        .map(|c| select_expr_for_column(c))
        .collect::<Vec<_>>()
        .join(", ")
}

fn select_expr_for_column(column: &str) -> String {
    match column {
        "block_timestamp" | "started_at" | "completed_at" | "first_delivery_at"
        | "all_delivered_at" => format!("make_timestamp(\"{}\"::BIGINT) AS \"{}\"", column, column),
        "created_at" | "ingested_at" => {
            format!("\"{}\"::TIMESTAMP AS \"{}\"", column, column)
        }
        "notification_date" | "delivery_date" => format!("\"{}\"::DATE AS \"{}\"", column, column),
        _ => format!("\"{}\"", column),
    }
}

fn retain_schema_columns(map: &mut Map<String, Value>, allowed: &HashSet<String>) -> usize {
    let mut dropped = 0usize;
    map.retain(|key, _| {
        let keep = allowed.contains(key);
        if !keep {
            dropped += 1;
        }
        keep
    });
    dropped
}

fn fetch_table_columns(conn: &Connection, table: &str) -> Result<HashSet<String>> {
    let escaped = table.replace('\'', "''");
    let mut stmt = conn
        .prepare(&format!("PRAGMA table_info('{}')", escaped))
        .context("Failed to prepare table info query")?;
    let mut rows = stmt.query([]).context("Failed to query table info")?;

    let mut columns = HashSet::new();
    while let Some(row) = rows.next().context("Failed to read table info row")? {
        let name: String = row
            .get(1)
            .context("Failed to read column name from table info")?;
        columns.insert(name);
    }
    Ok(columns)
}

/// DuckLake writer that consumes batches
pub struct DuckLakeWriter {
    config: DuckLakeConfig,
}

impl DuckLakeWriter {
    /// Create a new DuckLake writer
    pub fn new(config: DuckLakeConfig) -> Self {
        Self { config }
    }

    /// Start consuming batches from the channel
    #[instrument(skip(self, batch_receiver))]
    pub async fn start(self: Arc<Self>, mut batch_receiver: mpsc::Receiver<ReadyBatch>) {
        info!("DuckLake writer started, waiting for batches");

        while let Some(batch) = batch_receiver.recv().await {
            let writer = Arc::clone(&self);

            // Spawn blocking task for DuckDB operations since Connection is not Send
            let result = tokio::task::spawn_blocking(move || writer.write_batch_sync(&batch)).await;

            match result {
                Ok(Ok(())) => {
                    debug!("Batch written successfully");
                }
                Ok(Err(e)) => {
                    error!("Failed to write batch: {}", e);
                    // TODO: Add retry logic or dead letter queue
                }
                Err(e) => {
                    error!("Task panicked while writing batch: {}", e);
                }
            }
        }

        warn!("Batch receiver closed, writer shutting down");
    }

    /// Write a batch to DuckLake (synchronous, for use with spawn_blocking)
    ///
    /// ## Batch Insert Optimization
    ///
    /// This implementation uses NDJSON (Newline-delimited JSON) for efficient batch writes:
    /// 1. All records enriched and written to a single NDJSON file
    /// 2. Single INSERT statement reads all records at once via read_json()
    /// 3. 10-100x faster than per-record INSERT statements
    ///
    /// ## Function-Based Partitioning (Schema Redesign)
    ///
    /// Partitioning is handled by DuckDB's partitioned INSERT based on:
    /// - `chain_id` column (from record data)
    /// - `year(block_timestamp)`, `month(block_timestamp)`, `day(block_timestamp)`
    /// - No explicit shard column required
    #[instrument(skip(self, batch), fields(
        batch_id = %batch.batch_id,
        table = %batch.table,
        chain_id = %batch.chain_id,
        record_count = batch.records.len()
    ))]
    fn write_batch_sync(&self, batch: &ReadyBatch) -> Result<()> {
        let start_time = Instant::now();

        info!(
            "Writing batch {} to {} ({} records, {} bytes)",
            batch.batch_id,
            batch.table,
            batch.records.len(),
            batch.total_size_bytes
        );

        if batch.records.is_empty() {
            debug!("Empty batch, skipping write");
            return Ok(());
        }

        // Verify table is valid and get its schema
        let schema = get_schema_for_table(&batch.table)
            .ok_or_else(|| anyhow::anyhow!("Unknown table: {}", batch.table))?;

        // Create connection for this batch write
        let conn = create_ducklake_connection(&self.config)
            .context("Failed to create DuckLake connection")?;

        // Ensure table exists (CREATE TABLE IF NOT EXISTS)
        let partition_cols = get_partition_columns_for_table(&batch.table);
        let create_table_ddl = generate_create_table_ddl(&batch.table, &schema, &partition_cols);
        debug!("Ensuring table exists with DDL: {}", create_table_ddl);
        conn.execute(&create_table_ddl, [])
            .with_context(|| format!("Failed to ensure table {} exists", batch.table))?;

        let schema_columns: HashSet<String> = schema
            .fields()
            .iter()
            .map(|field| field.name().to_string())
            .collect();
        let allowed_columns = match fetch_table_columns(&conn, &batch.table) {
            Ok(columns) if !columns.is_empty() => {
                debug!(
                    "Using DuckLake table columns for {} ({} columns)",
                    batch.table,
                    columns.len()
                );
                columns
            }
            Ok(_) | Err(_) => {
                debug!(
                    "Falling back to schema columns for {} ({} columns)",
                    batch.table,
                    schema_columns.len()
                );
                schema_columns
            }
        };

        // =========================================================================
        // BATCH INSERT OPTIMIZATION: Write all records to single NDJSON file
        // =========================================================================

        let temp_path = format!("/tmp/ducklake_batch_{}.ndjson", batch.batch_id);
        let mut all_columns: HashSet<String> = HashSet::new();
        let ingestion_timestamp = Utc::now().format("%Y-%m-%d %H:%M:%S%.6f").to_string();

        let partitioner = Partitioner::new();

        // Phase 1: Enrich all records and write to NDJSON file
        {
            let file = fs::File::create(&temp_path)
                .with_context(|| format!("Failed to create NDJSON temp file: {}", temp_path))?;
            let mut writer = BufWriter::new(file);

            for record in &batch.records {
                // Parse JSON and enrich with required fields
                let mut json_value: Value = serde_json::from_str(&record.data)
                    .with_context(|| format!("Failed to parse JSON record: {}", &record.data))?;

                if let Value::Object(ref mut map) = json_value {
                    if batch.table == CONTRACT_CALLS_TABLE {
                        ensure_contract_calls_block_timestamp(map).with_context(|| {
                            format!("Failed to ensure block_timestamp for {}", batch.table)
                        })?;
                    }

                    if batch.table == NOTIFICATION_CONTENT_TABLE {
                        ensure_notification_content_partition_fields(map, &partitioner)
                            .with_context(|| {
                                format!("Failed to ensure partition fields for {}", batch.table)
                            })?;
                    }

                    if is_transactions_table(&batch.table) {
                        ensure_transaction_required_fields(map, &partitioner, &allowed_columns)
                            .with_context(|| {
                                format!("Failed to ensure required fields for {}", batch.table)
                            })?;
                    }

                    // Add ingested_at if not present (required NOT NULL field)
                    if !map.contains_key("ingested_at") {
                        map.insert(
                            "ingested_at".to_string(),
                            Value::String(ingestion_timestamp.clone()),
                        );
                    }

                    // Convert block_timestamp from unix seconds to microseconds
                    // DuckDB TIMESTAMP expects epoch_us or ISO string
                    if allowed_columns.contains("block_timestamp") {
                        if let Some(Value::Number(ts)) = map.get("block_timestamp") {
                            if let Some(ts_i64) = ts.as_i64() {
                                let ts_us = ts_i64 * 1_000_000;
                                map.insert(
                                    "block_timestamp".to_string(),
                                    Value::Number(Number::from(ts_us)),
                                );
                            }
                        }
                    }

                    let dropped = retain_schema_columns(map, &allowed_columns);
                    if dropped > 0 {
                        debug!(
                            "Dropped {} unknown columns for table {} (record keys now {})",
                            dropped,
                            batch.table,
                            map.len()
                        );
                    }

                    // Collect all column names across all records (after filtering)
                    for key in map.keys() {
                        all_columns.insert(key.clone());
                    }
                }

                // Write as NDJSON (one JSON object per line)
                let json_line = serde_json::to_string(&json_value)
                    .context("Failed to serialize JSON record")?;
                writeln!(writer, "{}", json_line)
                    .with_context(|| format!("Failed to write to NDJSON file: {}", temp_path))?;
            }

            writer
                .flush()
                .with_context(|| format!("Failed to flush NDJSON file: {}", temp_path))?;
        }

        debug!(
            "Wrote {} records to NDJSON file: {} ({} unique columns)",
            batch.records.len(),
            temp_path,
            all_columns.len()
        );

        // Phase 2: Build and execute single batch INSERT
        let column_names: Vec<String> = all_columns.into_iter().collect();

        // Build column list for INSERT
        let columns_str = column_names
            .iter()
            .map(|c| format!("\"{}\"", c))
            .collect::<Vec<_>>()
            .join(", ");

        // Build SELECT expressions with proper type casting for TIMESTAMP columns
        let select_exprs = build_select_exprs(&column_names);

        // Execute single batch INSERT using read_json for NDJSON format
        let insert_sql = format!(
            "INSERT INTO \"{}\" ({}) SELECT {} FROM read_json('{}', format = 'newline_delimited', auto_detect = true, ignore_errors = true)",
            batch.table, columns_str, select_exprs, temp_path
        );

        debug!(
            "Executing batch INSERT with {} columns for {} records",
            column_names.len(),
            batch.records.len()
        );

        let result = conn.execute(&insert_sql, []);

        // Clean up temp file regardless of success/failure
        let _ = fs::remove_file(&temp_path);

        match &result {
            Ok(rows_affected) => {
                let elapsed = start_time.elapsed();
                info!(
                    "Successfully wrote batch {} to {} ({} records in {:?}, {} rows/sec)",
                    batch.batch_id,
                    batch.table,
                    batch.records.len(),
                    elapsed,
                    if elapsed.as_secs_f64() > 0.0 {
                        (batch.records.len() as f64 / elapsed.as_secs_f64()) as u64
                    } else {
                        batch.records.len() as u64
                    }
                );
                debug!("Rows affected: {:?}", rows_affected);
            }
            Err(e) => {
                error!("Batch INSERT failed with error: {}", e);
                error!(
                    "Failed SQL (truncated): {}...",
                    &insert_sql.chars().take(500).collect::<String>()
                );
                error!(
                    "Record count: {}, Columns: {}",
                    batch.records.len(),
                    column_names.len()
                );
            }
        }

        result.map(|_| ()).with_context(|| {
            format!(
                "Failed to batch insert {} records into {}",
                batch.records.len(),
                batch.table
            )
        })
    }

    /// Check if writer is healthy (creates a test connection)
    pub fn is_healthy(&self) -> bool {
        // Use tracing for all logging (eprintln may not appear in K8s logs)
        info!(">>> WRITER: Checking DuckLake connection health...");
        info!(
            ">>> WRITER:   PostgreSQL: {}:{}/{}",
            self.config.postgres_host, self.config.postgres_port, self.config.postgres_database
        );
        info!(">>> WRITER:   S3 Endpoint: {}", self.config.s3_endpoint);
        info!(">>> WRITER:   S3 Bucket: {}", self.config.s3_bucket);

        match create_ducklake_connection(&self.config) {
            Ok(conn) => {
                info!(">>> WRITER: DuckLake connection created, testing query...");
                match conn.execute("SELECT 1", []) {
                    Ok(_) => {
                        info!(">>> WRITER: DuckLake health check PASSED");
                        true
                    }
                    Err(e) => {
                        error!(
                            ">>> WRITER: DuckLake health check FAILED - query error: {}",
                            e
                        );
                        false
                    }
                }
            }
            Err(e) => {
                error!(
                    ">>> WRITER: DuckLake health check FAILED - connection error: {}",
                    e
                );
                false
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_writer_creation() {
        let config = DuckLakeConfig::default();
        let _writer = DuckLakeWriter::new(config);
    }

    #[test]
    fn test_notification_content_enrichment() {
        let mut map = Map::new();
        map.insert(
            "user_id".to_string(),
            Value::String("user123456789".to_string()),
        );

        let partitioner = Partitioner::new();
        ensure_notification_content_partition_fields(&mut map, &partitioner).unwrap();

        assert_eq!(
            map.get("user_id_prefix")
                .and_then(|value| value.as_str())
                .unwrap(),
            "user1234"
        );

        let expected_shard = partitioner
            .calculate_shard_for_table("user123456789", NOTIFICATION_CONTENT_TABLE)
            .unwrap();
        assert_eq!(
            map.get("shard").and_then(|value| value.as_i64()).unwrap(),
            expected_shard as i64
        );
    }

    #[test]
    fn test_retain_schema_columns_drops_unknown_fields() {
        let allowed: HashSet<String> = ["keep", "also_keep"]
            .into_iter()
            .map(|name| name.to_string())
            .collect();
        let mut map = Map::new();
        map.insert("keep".to_string(), Value::String("ok".to_string()));
        map.insert("drop_me".to_string(), Value::String("nope".to_string()));

        let dropped = retain_schema_columns(&mut map, &allowed);

        assert_eq!(dropped, 1);
        assert!(map.contains_key("keep"));
        assert!(!map.contains_key("drop_me"));
    }

    #[test]
    fn test_contract_calls_block_timestamp_from_timestamp() {
        let mut map = Map::new();
        map.insert(
            "timestamp".to_string(),
            Value::Number(Number::from(1_700_000_000i64)),
        );

        ensure_contract_calls_block_timestamp(&mut map).unwrap();

        assert_eq!(
            map.get("block_timestamp")
                .and_then(|value| value.as_i64())
                .unwrap(),
            1_700_000_000i64
        );
    }

    #[test]
    fn test_contract_calls_block_timestamp_requires_field() {
        let mut map = Map::new();

        let result = ensure_contract_calls_block_timestamp(&mut map);
        assert!(result.is_err());
    }

    #[test]
    fn test_transactions_required_fields_added() {
        let mut map = Map::new();
        map.insert(
            "chain_id".to_string(),
            Value::String("ethereum_mainnet".to_string()),
        );
        map.insert(
            "transaction_hash".to_string(),
            Value::String("0xabc".to_string()),
        );
        map.insert(
            "block_timestamp".to_string(),
            Value::Number(Number::from(1_700_000_000)),
        );

        let allowed: HashSet<String> = [
            "block_date",
            "shard",
            "transaction_index",
            "status",
            "chain_id",
            "transaction_hash",
        ]
        .into_iter()
        .map(|name| name.to_string())
        .collect();

        ensure_transaction_required_fields(&mut map, &Partitioner::new(), &allowed).unwrap();

        assert!(map
            .get("block_date")
            .and_then(|value| value.as_str())
            .is_some());
        assert!(map.get("shard").and_then(|value| value.as_i64()).is_some());
        assert_eq!(
            map.get("transaction_index")
                .and_then(|value| value.as_i64())
                .unwrap(),
            0
        );
        assert_eq!(
            map.get("status").and_then(|value| value.as_str()).unwrap(),
            "SUCCESS"
        );
    }

    #[test]
    fn test_notification_content_requires_user_id() {
        let mut map = Map::new();

        let result = ensure_notification_content_partition_fields(&mut map, &Partitioner::new());
        assert!(result.is_err());
    }

    #[test]
    fn test_select_expr_for_column_casts_timestamp_and_date() {
        assert_eq!(
            select_expr_for_column("started_at"),
            "make_timestamp(\"started_at\"::BIGINT) AS \"started_at\""
        );
        assert_eq!(
            select_expr_for_column("completed_at"),
            "make_timestamp(\"completed_at\"::BIGINT) AS \"completed_at\""
        );
        assert_eq!(
            select_expr_for_column("created_at"),
            "\"created_at\"::TIMESTAMP AS \"created_at\""
        );
        assert_eq!(
            select_expr_for_column("ingested_at"),
            "\"ingested_at\"::TIMESTAMP AS \"ingested_at\""
        );
        assert_eq!(
            select_expr_for_column("notification_date"),
            "\"notification_date\"::DATE AS \"notification_date\""
        );
        assert_eq!(
            select_expr_for_column("delivery_date"),
            "\"delivery_date\"::DATE AS \"delivery_date\""
        );
        assert_eq!(select_expr_for_column("other"), "\"other\"");
    }
}
