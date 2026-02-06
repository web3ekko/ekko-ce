//! DuckLake reader for SQL query execution
//!
//! Executes parameterized SQL queries against DuckLake (DuckDB) and returns results as
//! Arrow IPC stream bytes (record batch stream).

use std::time::Duration;

use anyhow::{Context, Result};
use arrow::ipc::writer::StreamWriter;
use ducklake_common::{
    config::DuckLakeConfig,
    connection::create_readonly_connection,
    types::{QueryRequest, SqlParam},
};
use tracing::{debug, info, instrument};

/// DuckLake reader for query execution
pub struct DuckLakeReader {
    config: DuckLakeConfig,
}

impl DuckLakeReader {
    /// Create a new DuckLake reader
    pub fn new(config: DuckLakeConfig) -> Self {
        Self { config }
    }

    /// Execute a parameterized SQL query and return Arrow IPC stream bytes.
    #[instrument(skip(self, request), fields(query_len = request.query.len()))]
    pub async fn execute_query_ipc(&self, request: &QueryRequest) -> Result<Vec<u8>> {
        let timeout = request.timeout_seconds.unwrap_or(300) as u64;
        let config = self.config.clone();
        let request = request.clone();

        let task =
            tokio::task::spawn_blocking(move || Self::execute_query_ipc_sync(&config, &request));

        tokio::time::timeout(Duration::from_secs(timeout), task)
            .await
            .context("query timed out")?
            .context("query task panicked")?
    }

    fn execute_query_ipc_sync(config: &DuckLakeConfig, request: &QueryRequest) -> Result<Vec<u8>> {
        let start = std::time::Instant::now();
        debug!("Executing query (ipc): {}", request.query);

        let conn = create_readonly_connection(config)
            .context("Failed to create DuckLake read-only connection")?;

        let mut stmt = conn
            .prepare(&request.query)
            .context("Failed to prepare query")?;

        let params = request.parameters.clone().unwrap_or_default();
        let values = params
            .iter()
            .map(sql_param_to_value)
            .collect::<Result<Vec<_>>>()?;

        let batches: Vec<arrow::record_batch::RecordBatch> = if values.is_empty() {
            stmt.query_arrow([])
                .context("query_arrow failed")?
                .collect()
        } else {
            stmt.query_arrow(duckdb::params_from_iter(values))
                .context("query_arrow failed")?
                .collect()
        };

        let schema = if let Some(first) = batches.first() {
            first.schema()
        } else {
            std::sync::Arc::new(arrow::datatypes::Schema::empty())
        };

        let mut out = Vec::new();
        {
            let mut writer = StreamWriter::try_new(&mut out, &schema)
                .context("failed to create arrow ipc writer")?;
            for batch in batches.iter() {
                writer
                    .write(batch)
                    .context("failed to write record batch")?;
            }
            writer.finish().context("failed to finish ipc stream")?;
        }

        info!(
            "Query executed: {} bytes in {}ms",
            out.len(),
            start.elapsed().as_millis()
        );

        Ok(out)
    }

    /// Check if reader is healthy (creates a test connection)
    pub fn is_healthy(&self) -> bool {
        match create_readonly_connection(&self.config) {
            Ok(conn) => conn.execute("SELECT 1", []).is_ok(),
            Err(_) => false,
        }
    }
}

fn sql_param_to_value(param: &SqlParam) -> Result<duckdb::types::Value> {
    use duckdb::types::{TimeUnit, Value};

    Ok(match param {
        SqlParam::Null => Value::Null,
        SqlParam::Bool(v) => Value::Boolean(*v),
        SqlParam::Int32(v) => Value::Int(*v),
        SqlParam::Int64(v) => Value::BigInt(*v),
        SqlParam::Float64(v) => Value::Double(*v),
        SqlParam::String(v) => Value::Text(v.clone()),
        SqlParam::Timestamp(ms) => Value::Timestamp(TimeUnit::Millisecond, *ms as i64),
        SqlParam::Decimal(v) => Value::Text(v.clone()),
        // The duckdb Rust crate panics when binding Value::List (ValueRef is unimplemented).
        // Keep this as a hard error so the provider never crashes on malformed/unsupported params.
        SqlParam::List(_) => {
            return Err(anyhow::anyhow!(
                "list parameters are not supported by duckdb bindings; encode lists as strings and split in SQL"
            ));
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reader_creation() {
        let config = DuckLakeConfig::default();
        let _reader = DuckLakeReader::new(config);
    }

    #[test]
    fn test_sql_param_to_value_list() {
        let err = sql_param_to_value(&SqlParam::List(vec![
            SqlParam::String("a".to_string()),
            SqlParam::String("b".to_string()),
        ]))
        .unwrap_err();
        assert!(err
            .to_string()
            .to_lowercase()
            .contains("list parameters are not supported"));
    }
}
