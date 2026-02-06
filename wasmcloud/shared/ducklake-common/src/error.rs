//! Error types for DuckLake providers

use thiserror::Error;

/// DuckLake operation errors
#[derive(Error, Debug)]
pub enum DuckLakeError {
    /// Table not found
    #[error("Table not found: {0}")]
    TableNotFound(String),

    /// Schema mismatch
    #[error("Schema mismatch: {0}")]
    SchemaError(String),

    /// Storage error (S3, filesystem)
    #[error("Storage error: {0}")]
    StorageError(String),

    /// Query parsing error
    #[error("Query error: {0}")]
    QueryError(String),

    /// Serialization error
    #[error("Serialization error: {0}")]
    SerializationError(String),

    /// Configuration error
    #[error("Configuration error: {0}")]
    ConfigError(String),

    /// Buffer error
    #[error("Buffer error: {0}")]
    BufferError(String),

    /// Compaction error
    #[error("Compaction error: {0}")]
    CompactionError(String),

    /// Connection error
    #[error("Connection error: {0}")]
    ConnectionError(String),

    /// Internal DuckDB error
    #[error("Internal error: {0}")]
    InternalError(String),

    /// DuckDB database error
    #[error("DuckDB error: {0}")]
    DuckDBError(String),

    /// Subject parsing error
    #[error("Subject parse error: {0}")]
    SubjectParseError(String),
}

// Error conversions for DuckDB and Arrow operations

#[cfg(not(target_family = "wasm"))]
impl From<duckdb::Error> for DuckLakeError {
    fn from(err: duckdb::Error) -> Self {
        DuckLakeError::DuckDBError(err.to_string())
    }
}

impl From<serde_json::Error> for DuckLakeError {
    fn from(err: serde_json::Error) -> Self {
        DuckLakeError::SerializationError(err.to_string())
    }
}

impl From<arrow::error::ArrowError> for DuckLakeError {
    fn from(err: arrow::error::ArrowError) -> Self {
        DuckLakeError::SerializationError(err.to_string())
    }
}

impl From<anyhow::Error> for DuckLakeError {
    fn from(err: anyhow::Error) -> Self {
        DuckLakeError::InternalError(err.to_string())
    }
}

impl From<std::env::VarError> for DuckLakeError {
    fn from(err: std::env::VarError) -> Self {
        DuckLakeError::ConfigError(err.to_string())
    }
}
