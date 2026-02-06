//! DuckLake Write Provider
//!
//! wasmCloud capability provider for writing blockchain data to DuckLake.
//!
//! This provider:
//! - Subscribes to NATS subjects: `ducklake.{table}.{chain}.{subnet}.write`
//! - Parses incoming messages to determine target table
//! - Micro-batches records for efficient writes
//! - Writes to shared DuckLake instance (PostgreSQL metadata + S3/MinIO parquet)
//!
//! Configuration via environment variables:
//! - NATS_URL: NATS server URL
//! - DUCKLAKE_POSTGRES_*: PostgreSQL metadata catalog settings
//! - DUCKLAKE_S3_*: S3/MinIO storage settings

pub mod buffer;
pub mod nats_listener;
pub mod provider;
pub mod writer;

pub use buffer::{FlushTrigger, MicroBatchBuffer, MicroBatchConfig, ReadyBatch};
pub use nats_listener::NatsWriteListener;
pub use provider::DuckLakeWriteProvider;
pub use writer::DuckLakeWriter;

// Re-export common types
pub use ducklake_common::{
    config::DuckLakeConfig,
    connection::create_ducklake_connection,
    error::DuckLakeError,
    partitioner::{PartitionSpec, Partitioner},
    schemas::{get_all_table_names, get_schema_for_table},
    subject_parser::SubjectInfo,
    types::{BatchWriteRequest, JsonRecord, WriteResponse},
    Result,
};
