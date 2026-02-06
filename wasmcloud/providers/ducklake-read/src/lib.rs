//! DuckLake Read Provider
//!
//! wasmCloud capability provider for reading blockchain data from DuckLake.
//!
//! This provider:
//! - Listens on NATS subjects: `ducklake.{table}.{chain}.{subnet}.query`
//! - Executes SQL queries against shared DuckLake instance
//! - Returns query results as JSON
//! - Provides schema discovery via `ducklake.schema.list` and `ducklake.schema.get`
//!
//! Configuration via environment variables:
//! - NATS_URL: NATS server URL
//! - DUCKLAKE_POSTGRES_*: PostgreSQL metadata catalog settings
//! - DUCKLAKE_S3_*: S3/MinIO storage settings

pub mod nats_listener;
pub mod provider;
pub mod reader;
pub mod schema_handler;

pub use nats_listener::NatsQueryListener;
pub use provider::DuckLakeReadProvider;
pub use reader::DuckLakeReader;
pub use schema_handler::SchemaHandler;

// Re-export common types
pub use ducklake_common::{
    config::DuckLakeConfig,
    connection::create_readonly_connection,
    error::DuckLakeError,
    schemas::{get_all_table_names, get_schema_for_table},
    subject_parser::SubjectInfo,
    types::{
        QueryOptions, QueryRequest, QueryResult, SchemaColumn, SchemaGetRequest, SchemaGetResponse,
        SchemaListRequest, SchemaListResponse, SchemaMetadata, TableSchema,
    },
    Result,
};
