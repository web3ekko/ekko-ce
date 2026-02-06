//! Type definitions for DuckLake providers
//!
//! Shared types for both ducklake-write and ducklake-read providers.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Table identifier
pub type TableName = String;

/// S3/MinIO path for table location
pub type TablePath = String;

/// JSON-encoded record
pub type JsonRecord = String;

/// SQL query string
pub type SqlQuery = String;

/// Batch write request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchWriteRequest {
    /// Target table name
    pub table: TableName,
    /// JSON records to write
    pub records: Vec<JsonRecord>,
    /// Optional partition values for this batch
    pub partition_values: Option<Vec<(String, String)>>,
}

impl BatchWriteRequest {
    /// Create a new batch write request
    pub fn new(table: impl Into<String>, records: Vec<JsonRecord>) -> Self {
        Self {
            table: table.into(),
            records,
            partition_values: None,
        }
    }

    /// Add partition values to the request
    pub fn with_partition_values(mut self, values: Vec<(String, String)>) -> Self {
        self.partition_values = Some(values);
        self
    }

    /// Get the number of records in this batch
    pub fn record_count(&self) -> usize {
        self.records.len()
    }

    /// Validate the batch request
    pub fn validate(&self) -> Result<(), String> {
        if self.table.is_empty() {
            return Err("Table name cannot be empty".to_string());
        }

        if self.records.is_empty() {
            return Err("Records cannot be empty".to_string());
        }

        // Validate JSON records
        for (i, record) in self.records.iter().enumerate() {
            if let Err(e) = serde_json::from_str::<serde_json::Value>(record) {
                return Err(format!("Invalid JSON in record {}: {}", i, e));
            }
        }

        Ok(())
    }
}

/// Write response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WriteResponse {
    /// Number of records written
    pub records_written: u64,
    /// Write time in milliseconds
    pub write_time_ms: u64,
    /// DuckLake snapshot version after write
    pub version: i64,
}

/// Query request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryRequest {
    /// SQL query to execute
    pub query: SqlQuery,
    /// Maximum rows to return
    pub limit: Option<u64>,
    /// Query timeout in seconds
    pub timeout_seconds: Option<u32>,
    /// Optional parameters for parameterized queries
    pub parameters: Option<Vec<SqlParam>>,
}

impl QueryRequest {
    /// Create a new query request
    pub fn new(query: impl Into<String>) -> Self {
        Self {
            query: query.into(),
            limit: None,
            timeout_seconds: None,
            parameters: None,
        }
    }

    /// Set the limit
    pub fn with_limit(mut self, limit: u64) -> Self {
        self.limit = Some(limit);
        self
    }

    /// Set the timeout
    pub fn with_timeout(mut self, timeout_seconds: u32) -> Self {
        self.timeout_seconds = Some(timeout_seconds);
        self
    }

    /// Set parameters
    pub fn with_parameters(mut self, parameters: Vec<SqlParam>) -> Self {
        self.parameters = Some(parameters);
        self
    }
}

/// Query result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryResult {
    /// Result rows as JSON strings
    pub rows: Vec<JsonRecord>,
    /// Column metadata
    pub columns: Vec<ColumnInfo>,
    /// Number of rows returned
    pub row_count: u64,
    /// Query execution time in milliseconds
    pub execution_time_ms: u64,
}

/// SQL parameter types for parameterized queries
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SqlParam {
    Null,
    Bool(bool),
    Int32(i32),
    Int64(i64),
    Float64(f64),
    String(String),
    Timestamp(u64),
    Decimal(String),
    /// Typed list/array parameter.
    ///
    /// Note: the current DuckDB Rust bindings used by `ducklake-read` do not support binding list
    /// parameters (ValueRef for lists is unimplemented and can panic). Prefer encoding lists as
    /// strings and splitting in SQL (e.g. `string_split(?, ',')`) until list binding is supported.
    List(Vec<SqlParam>),
}

/// SQL value types in result rows
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SqlValue {
    Null,
    Bool(bool),
    Int64(i64),
    Float64(f64),
    String(String),
    Timestamp(u64),
    Decimal(String),
}

/// Column metadata in SQL results
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ColumnInfo {
    pub name: String,
    pub data_type: String,
}

/// Query options
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryOptions {
    /// Query timeout in seconds (default: 300s)
    pub timeout_seconds: Option<u32>,
    /// Maximum rows to return (default: 100K)
    pub max_rows: Option<u32>,
    /// Flush buffers before query for strong consistency (default: false)
    pub flush_before_query: bool,
}

impl Default for QueryOptions {
    fn default() -> Self {
        Self {
            timeout_seconds: Some(300),
            max_rows: Some(100_000),
            flush_before_query: false,
        }
    }
}

/// Table statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableStats {
    /// Total number of files
    pub file_count: u64,
    /// Total size in bytes
    pub size_bytes: u64,
    /// Number of records
    pub record_count: u64,
    /// Last modified timestamp
    pub last_modified: u64,
    /// Number of partitions
    pub partition_count: u64,
    /// Current snapshot version
    pub snapshot_version: i64,
}

/// Compaction request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompactionRequest {
    /// Target table name
    pub table: TableName,
    /// Target file size in MB
    pub target_file_size_mb: Option<u32>,
    /// Whether to run Z-order optimization
    pub z_order: bool,
}

/// Compaction response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompactionResponse {
    /// Files before compaction
    pub files_before: u64,
    /// Files after compaction
    pub files_after: u64,
    /// Size reduction in bytes
    pub size_reduction_bytes: u64,
    /// Compaction time in milliseconds
    pub compaction_time_ms: u64,
}

/// Provider status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderStatus {
    /// Whether provider is healthy
    pub healthy: bool,
    /// Active tables
    pub active_tables: Vec<TableName>,
    /// Buffer usage metrics (write provider only)
    pub buffer_usage: Option<BufferMetrics>,
    /// Connection pool metrics
    pub connection_pool: Option<ConnectionPoolMetrics>,
}

/// Buffer metrics for write provider
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BufferMetrics {
    /// Total records in buffer
    pub total_records: u64,
    /// Total buffer size in bytes
    pub total_size_bytes: u64,
    /// Number of active chains
    pub active_chains: u32,
    /// Pending flushes
    pub pending_flushes: u32,
}

/// Connection pool metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionPoolMetrics {
    /// Active connections
    pub active_connections: u32,
    /// Idle connections
    pub idle_connections: u32,
    /// Total connections created
    pub total_connections_created: u64,
}

/// Record data wrapper for NATS messages
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecordData {
    /// Raw JSON data
    pub data: JsonRecord,
    /// Chain ID (e.g., "ethereum_mainnet")
    pub chain_id: String,
    /// Block number (if applicable)
    pub block_number: Option<u64>,
    /// Timestamp
    pub timestamp: u64,
    /// Optional metadata
    pub metadata: Option<HashMap<String, String>>,
}

/// Filter operator for queries
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FilterOperator {
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
    In,
    NotIn,
    Like,
    NotLike,
}

/// Filter condition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FilterCondition {
    /// Column name
    pub column: String,
    /// Operator
    pub operator: FilterOperator,
    /// Value to compare
    pub value: serde_json::Value,
}

/// Time travel query options (DuckLake feature)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeTravelOptions {
    /// Query at specific snapshot version
    pub version: Option<i64>,
    /// Query at specific timestamp
    pub timestamp: Option<u64>,
}

// ============================================================================
// Schema Discovery Types (for NATS schema sync with NLP)
// ============================================================================

/// Column metadata for schema discovery
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaColumn {
    /// Column name
    pub name: String,
    /// Data type (e.g., "VARCHAR", "BIGINT", "TIMESTAMP")
    pub data_type: String,
    /// Whether the column allows NULL values
    pub nullable: bool,
    /// Whether this column is a partition column
    pub is_partition: bool,
}

/// Full table schema with columns and metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableSchema {
    /// Table name
    pub table_name: String,
    /// All columns in the table
    pub columns: Vec<SchemaColumn>,
    /// Partition columns (for query optimization)
    pub partition_columns: Vec<String>,
    /// Z-order columns (for read optimization)
    pub z_order_columns: Vec<String>,
    /// Number of columns
    pub column_count: usize,
}

impl TableSchema {
    /// Create a new table schema
    pub fn new(table_name: impl Into<String>) -> Self {
        Self {
            table_name: table_name.into(),
            columns: Vec::new(),
            partition_columns: Vec::new(),
            z_order_columns: Vec::new(),
            column_count: 0,
        }
    }

    /// Add a column to the schema
    pub fn with_column(mut self, column: SchemaColumn) -> Self {
        self.columns.push(column);
        self.column_count = self.columns.len();
        self
    }

    /// Set partition columns
    pub fn with_partition_columns(mut self, columns: Vec<String>) -> Self {
        self.partition_columns = columns;
        self
    }

    /// Set z-order columns
    pub fn with_z_order_columns(mut self, columns: Vec<String>) -> Self {
        self.z_order_columns = columns;
        self
    }

    /// Get column names as a list
    pub fn column_names(&self) -> Vec<&str> {
        self.columns.iter().map(|c| c.name.as_str()).collect()
    }
}

/// Schema list request (for ducklake.schema.list)
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SchemaListRequest {
    /// Optional filter by table name pattern (supports wildcards)
    pub table_filter: Option<String>,
    /// Whether to include full column details
    pub include_columns: bool,
}

/// Schema list response (for ducklake.schema.list)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaListResponse {
    /// Whether the request was successful
    pub success: bool,
    /// List of table schemas
    pub tables: Vec<TableSchema>,
    /// Response metadata
    pub metadata: SchemaMetadata,
    /// Error message if success is false
    pub error: Option<String>,
}

impl SchemaListResponse {
    /// Create a successful response
    pub fn success(tables: Vec<TableSchema>) -> Self {
        Self {
            success: true,
            tables,
            metadata: SchemaMetadata::now(),
            error: None,
        }
    }

    /// Create an error response
    pub fn error(message: impl Into<String>) -> Self {
        Self {
            success: false,
            tables: Vec::new(),
            metadata: SchemaMetadata::now(),
            error: Some(message.into()),
        }
    }
}

/// Schema get request (for ducklake.schema.get)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaGetRequest {
    /// Table name to get schema for
    pub table_name: String,
}

/// Schema get response (for ducklake.schema.get)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaGetResponse {
    /// Whether the request was successful
    pub success: bool,
    /// Table schema (if found)
    pub table: Option<TableSchema>,
    /// Response metadata
    pub metadata: SchemaMetadata,
    /// Error message if success is false
    pub error: Option<String>,
}

impl SchemaGetResponse {
    /// Create a successful response
    pub fn success(table: TableSchema) -> Self {
        Self {
            success: true,
            table: Some(table),
            metadata: SchemaMetadata::now(),
            error: None,
        }
    }

    /// Create a not found response
    pub fn not_found(table_name: &str) -> Self {
        Self {
            success: false,
            table: None,
            metadata: SchemaMetadata::now(),
            error: Some(format!("Table '{}' not found", table_name)),
        }
    }

    /// Create an error response
    pub fn error(message: impl Into<String>) -> Self {
        Self {
            success: false,
            table: None,
            metadata: SchemaMetadata::now(),
            error: Some(message.into()),
        }
    }
}

/// Metadata for schema responses
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaMetadata {
    /// Schema version
    pub version: String,
    /// Response timestamp (ISO 8601)
    pub timestamp: String,
    /// Source of schema (e.g., "catalog", "cache", "fallback")
    pub source: String,
}

impl SchemaMetadata {
    /// Create metadata with current timestamp
    pub fn now() -> Self {
        Self {
            version: "1.0.0".to_string(),
            timestamp: chrono::Utc::now().to_rfc3339(),
            source: "catalog".to_string(),
        }
    }

    /// Create metadata with specific source
    pub fn with_source(source: impl Into<String>) -> Self {
        Self {
            version: "1.0.0".to_string(),
            timestamp: chrono::Utc::now().to_rfc3339(),
            source: source.into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_batch_request_validation() {
        let valid_request = BatchWriteRequest::new(
            "test_table",
            vec![r#"{"id": 1, "value": "test"}"#.to_string()],
        );
        assert!(valid_request.validate().is_ok());

        let invalid_request =
            BatchWriteRequest::new("test_table", vec!["invalid json".to_string()]);
        assert!(invalid_request.validate().is_err());
    }

    #[test]
    fn test_query_request_builder() {
        let query = QueryRequest::new("SELECT * FROM transactions")
            .with_limit(100)
            .with_timeout(60);

        assert_eq!(query.limit, Some(100));
        assert_eq!(query.timeout_seconds, Some(60));
    }

    #[test]
    fn test_partition_values() {
        let request = BatchWriteRequest::new("test", vec![]).with_partition_values(vec![
            ("chain_id".to_string(), "ethereum_mainnet".to_string()),
            ("block_date".to_string(), "2024-01-25".to_string()),
        ]);

        assert!(request.partition_values.is_some());
        assert_eq!(request.partition_values.unwrap().len(), 2);
    }

    #[test]
    fn test_table_schema_builder() {
        let schema = TableSchema::new("transactions")
            .with_column(SchemaColumn {
                name: "chain_id".to_string(),
                data_type: "VARCHAR".to_string(),
                nullable: false,
                is_partition: true,
            })
            .with_column(SchemaColumn {
                name: "block_number".to_string(),
                data_type: "BIGINT".to_string(),
                nullable: false,
                is_partition: false,
            })
            .with_partition_columns(vec!["chain_id".to_string()])
            .with_z_order_columns(vec!["block_number".to_string()]);

        assert_eq!(schema.table_name, "transactions");
        assert_eq!(schema.column_count, 2);
        assert_eq!(schema.columns.len(), 2);
        assert_eq!(schema.partition_columns, vec!["chain_id"]);
        assert_eq!(schema.z_order_columns, vec!["block_number"]);
        assert_eq!(schema.column_names(), vec!["chain_id", "block_number"]);
    }

    #[test]
    fn test_schema_list_response_success() {
        let tables = vec![TableSchema::new("transactions"), TableSchema::new("blocks")];
        let response = SchemaListResponse::success(tables);

        assert!(response.success);
        assert_eq!(response.tables.len(), 2);
        assert!(response.error.is_none());
        assert_eq!(response.metadata.source, "catalog");
    }

    #[test]
    fn test_schema_list_response_error() {
        let response = SchemaListResponse::error("Connection failed");

        assert!(!response.success);
        assert!(response.tables.is_empty());
        assert_eq!(response.error, Some("Connection failed".to_string()));
    }

    #[test]
    fn test_schema_get_response_success() {
        let table = TableSchema::new("transactions");
        let response = SchemaGetResponse::success(table);

        assert!(response.success);
        assert!(response.table.is_some());
        assert_eq!(response.table.unwrap().table_name, "transactions");
        assert!(response.error.is_none());
    }

    #[test]
    fn test_schema_get_response_not_found() {
        let response = SchemaGetResponse::not_found("unknown_table");

        assert!(!response.success);
        assert!(response.table.is_none());
        assert!(response.error.unwrap().contains("unknown_table"));
    }

    #[test]
    fn test_schema_metadata() {
        let metadata = SchemaMetadata::now();
        assert_eq!(metadata.version, "1.0.0");
        assert_eq!(metadata.source, "catalog");
        assert!(!metadata.timestamp.is_empty());

        let custom_metadata = SchemaMetadata::with_source("fallback");
        assert_eq!(custom_metadata.source, "fallback");
    }
}
