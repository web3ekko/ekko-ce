//! NATS listener for DuckLake query and schema operations
//!
//! Listens to:
//! - `ducklake.*.*.*.query` - SQL query execution
//! - `ducklake.schema.list` - List all table schemas
//! - `ducklake.schema.get` - Get specific table schema

use anyhow::{Context, Result};
use ducklake_common::subject_parser::SubjectInfo;
use ducklake_common::types::{QueryRequest, SchemaGetRequest, SchemaListRequest};
use futures::StreamExt;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{debug, error, info, instrument, warn};

use crate::reader::DuckLakeReader;
use crate::schema_handler::SchemaHandler;

/// NATS listener configuration
#[derive(Debug, Clone)]
pub struct NatsQueryListenerConfig {
    /// NATS server URL
    pub nats_url: String,
    /// Subject pattern for SQL queries
    pub query_subject_pattern: String,
    /// Subject for schema list requests
    pub schema_list_subject: String,
    /// Subject for schema get requests
    pub schema_get_subject: String,
}

impl NatsQueryListenerConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        let nats_url =
            std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());

        // Subscribe to all query operations by default
        let query_subject_pattern = std::env::var("DUCKLAKE_QUERY_SUBJECT")
            .unwrap_or_else(|_| "ducklake.*.*.*.query".to_string());

        // Schema discovery subjects
        let schema_list_subject = std::env::var("DUCKLAKE_SCHEMA_LIST_SUBJECT")
            .unwrap_or_else(|_| "ducklake.schema.list".to_string());

        let schema_get_subject = std::env::var("DUCKLAKE_SCHEMA_GET_SUBJECT")
            .unwrap_or_else(|_| "ducklake.schema.get".to_string());

        Self {
            nats_url,
            query_subject_pattern,
            schema_list_subject,
            schema_get_subject,
        }
    }

    /// Load configuration from wasmCloud HostData properties.
    ///
    /// Keys are expected in the same format used by `apps/wasmcloud/setup-configs.sh`.
    pub fn from_properties(props: &HashMap<String, String>) -> Self {
        let nats_url = props
            .get("nats_url")
            .or_else(|| props.get("NATS_URL"))
            .cloned()
            .unwrap_or_else(|| "nats://localhost:4222".to_string());

        let query_subject_pattern = props
            .get("ducklake_query_subject")
            .or_else(|| props.get("ducklake_query_subject_pattern"))
            .or_else(|| props.get("DUCKLAKE_QUERY_SUBJECT"))
            .cloned()
            .unwrap_or_else(|| "ducklake.*.*.*.query".to_string());

        let schema_list_subject = props
            .get("ducklake_schema_list_subject")
            .or_else(|| props.get("DUCKLAKE_SCHEMA_LIST_SUBJECT"))
            .cloned()
            .unwrap_or_else(|| "ducklake.schema.list".to_string());

        let schema_get_subject = props
            .get("ducklake_schema_get_subject")
            .or_else(|| props.get("DUCKLAKE_SCHEMA_GET_SUBJECT"))
            .cloned()
            .unwrap_or_else(|| "ducklake.schema.get".to_string());

        Self {
            nats_url,
            query_subject_pattern,
            schema_list_subject,
            schema_get_subject,
        }
    }
}

/// NATS listener for DuckLake query and schema operations
pub struct NatsQueryListener {
    config: NatsQueryListenerConfig,
    reader: Arc<DuckLakeReader>,
    schema_handler: SchemaHandler,
}

impl NatsQueryListener {
    /// Create a new NATS query listener
    pub fn new(config: NatsQueryListenerConfig, reader: Arc<DuckLakeReader>) -> Self {
        Self {
            config,
            reader,
            schema_handler: SchemaHandler::new(),
        }
    }

    /// Start listening for query and schema requests
    #[instrument(skip(self))]
    pub async fn start(self) -> Result<()> {
        info!("Connecting to NATS at {}", self.config.nats_url);

        let client = async_nats::connect(&self.config.nats_url)
            .await
            .context("Failed to connect to NATS")?;

        info!("Connected to NATS successfully");

        // Subscribe to query pattern
        info!(
            "Subscribing to query pattern: {}",
            self.config.query_subject_pattern
        );
        let mut query_subscriber = client
            .subscribe(self.config.query_subject_pattern.clone())
            .await
            .context("Failed to subscribe to query subject pattern")?;

        // Subscribe to schema list subject
        info!(
            "Subscribing to schema list: {}",
            self.config.schema_list_subject
        );
        let mut schema_list_subscriber = client
            .subscribe(self.config.schema_list_subject.clone())
            .await
            .context("Failed to subscribe to schema list subject")?;

        // Subscribe to schema get subject
        info!(
            "Subscribing to schema get: {}",
            self.config.schema_get_subject
        );
        let mut schema_get_subscriber = client
            .subscribe(self.config.schema_get_subject.clone())
            .await
            .context("Failed to subscribe to schema get subject")?;

        info!("DuckLake Query & Schema Listener is ready");
        info!("  Query: {}", self.config.query_subject_pattern);
        info!("  Schema List: {}", self.config.schema_list_subject);
        info!("  Schema Get: {}", self.config.schema_get_subject);

        // Process messages from all subscriptions using tokio::select!
        loop {
            tokio::select! {
                Some(message) = query_subscriber.next() => {
                    let subject = message.subject.to_string();
                    let reply_to = message.reply.clone();
                    let payload = message.payload.to_vec();

                    match self.process_query(&subject, &payload).await {
                        Ok(result_bytes) => {
                            if let Some(reply_subject) = reply_to {
                                if let Err(e) = client.publish(reply_subject, result_bytes.into()).await {
                                    error!("Failed to send query response: {}", e);
                                }
                            }
                        }
                        Err(e) => {
                            error!("Failed to process query on {}: {}", subject, e);
                            if let Some(reply_subject) = reply_to {
                                let error_response = format!(r#"{{"error": "{}"}}"#, e.to_string().replace('"', "'"));
                                if let Err(e) = client.publish(reply_subject, error_response.into()).await {
                                    error!("Failed to send error response: {}", e);
                                }
                            }
                        }
                    }
                }

                Some(message) = schema_list_subscriber.next() => {
                    let reply_to = message.reply.clone();
                    let payload = message.payload.to_vec();

                    let response = self.process_schema_list(&payload);
                    if let Some(reply_subject) = reply_to {
                        let response_bytes = serde_json::to_vec(&response)
                            .unwrap_or_else(|e| format!(r#"{{"error": "{}"}}"#, e).into_bytes());
                        if let Err(e) = client.publish(reply_subject, response_bytes.into()).await {
                            error!("Failed to send schema list response: {}", e);
                        }
                    }
                }

                Some(message) = schema_get_subscriber.next() => {
                    let reply_to = message.reply.clone();
                    let payload = message.payload.to_vec();

                    let response = self.process_schema_get(&payload);
                    if let Some(reply_subject) = reply_to {
                        let response_bytes = serde_json::to_vec(&response)
                            .unwrap_or_else(|e| format!(r#"{{"error": "{}"}}"#, e).into_bytes());
                        if let Err(e) = client.publish(reply_subject, response_bytes.into()).await {
                            error!("Failed to send schema get response: {}", e);
                        }
                    }
                }

                else => {
                    warn!("All NATS subscriptions ended");
                    break;
                }
            }
        }

        Ok(())
    }

    /// Process schema list request
    #[instrument(skip(self, payload))]
    fn process_schema_list(&self, payload: &[u8]) -> ducklake_common::types::SchemaListResponse {
        info!("Processing schema list request");

        // Parse request (empty payload = default request)
        let request: SchemaListRequest = if payload.is_empty() {
            SchemaListRequest::default()
        } else {
            match serde_json::from_slice(payload) {
                Ok(req) => req,
                Err(e) => {
                    error!("Failed to parse schema list request: {}", e);
                    return ducklake_common::types::SchemaListResponse::error(format!(
                        "Invalid request: {}",
                        e
                    ));
                }
            }
        };

        self.schema_handler.handle_list(&request)
    }

    /// Process schema get request
    #[instrument(skip(self, payload))]
    fn process_schema_get(&self, payload: &[u8]) -> ducklake_common::types::SchemaGetResponse {
        info!("Processing schema get request");

        // Parse request
        let request: SchemaGetRequest = match serde_json::from_slice(payload) {
            Ok(req) => req,
            Err(e) => {
                error!("Failed to parse schema get request: {}", e);
                return ducklake_common::types::SchemaGetResponse::error(format!(
                    "Invalid request: {}",
                    e
                ));
            }
        };

        self.schema_handler.handle_get(&request)
    }

    /// Process a query request
    #[instrument(skip(self, payload), fields(subject = %subject))]
    async fn process_query(&self, subject: &str, payload: &[u8]) -> Result<Vec<u8>> {
        // Parse the subject to get table, chain, subnet info
        let subject_info = SubjectInfo::parse(subject).context("Failed to parse NATS subject")?;

        debug!(
            "Processing query for table={} chain_id={}",
            subject_info.table, subject_info.chain_id
        );

        // Deserialize query request
        let request: QueryRequest =
            serde_json::from_slice(payload).context("Failed to parse query request")?;

        info!(
            "Executing query for {}:{} (limit: {:?})",
            subject_info.table, subject_info.chain_id, request.limit
        );

        // Execute the query and return Arrow IPC bytes
        let bytes = self.reader.execute_query_ipc(&request).await?;
        Ok(bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ducklake_common::types::{SchemaGetResponse, SchemaListResponse};

    #[test]
    fn test_config_structure() {
        let config = NatsQueryListenerConfig {
            nats_url: "nats://test:4222".to_string(),
            query_subject_pattern: "ducklake.transactions.*.*.query".to_string(),
            schema_list_subject: "ducklake.schema.list".to_string(),
            schema_get_subject: "ducklake.schema.get".to_string(),
        };
        assert_eq!(config.nats_url, "nats://test:4222");
        assert_eq!(
            config.query_subject_pattern,
            "ducklake.transactions.*.*.query"
        );
        assert_eq!(config.schema_list_subject, "ducklake.schema.list");
        assert_eq!(config.schema_get_subject, "ducklake.schema.get");
    }

    #[test]
    fn test_schema_list_response_json_serialization() {
        // Test that SchemaListResponse serializes to JSON in the format expected by Python
        let handler = SchemaHandler::new();
        let request = SchemaListRequest {
            table_filter: None,
            include_columns: true, // Must be true to get column details
        };
        let response = handler.handle_list(&request);

        // Serialize to JSON
        let json = serde_json::to_string(&response).expect("Failed to serialize response");
        let parsed: serde_json::Value = serde_json::from_str(&json).expect("Failed to parse JSON");

        // Verify wire format matches Python expectations
        assert!(parsed["success"].as_bool().unwrap());
        assert!(parsed["tables"].is_array());
        assert_eq!(
            parsed["tables"].as_array().unwrap().len(),
            ducklake_common::schemas::get_all_table_names().len()
        );

        // Verify first table structure
        let first_table = &parsed["tables"][0];
        assert!(first_table["table_name"].is_string());
        assert!(first_table["columns"].is_array());
        assert!(first_table["partition_columns"].is_array());
        assert!(first_table["z_order_columns"].is_array());
        assert!(first_table["column_count"].is_number());

        // Verify column structure
        let first_column = &first_table["columns"][0];
        assert!(first_column["name"].is_string());
        assert!(first_column["data_type"].is_string());
        assert!(first_column["nullable"].is_boolean());
        assert!(first_column["is_partition"].is_boolean());
    }

    #[test]
    fn test_schema_get_response_json_serialization() {
        // Test that SchemaGetResponse serializes to JSON correctly
        let handler = SchemaHandler::new();
        let request = SchemaGetRequest {
            table_name: "transactions".to_string(),
        };
        let response = handler.handle_get(&request);

        // Serialize to JSON
        let json = serde_json::to_string(&response).expect("Failed to serialize response");
        let parsed: serde_json::Value = serde_json::from_str(&json).expect("Failed to parse JSON");

        // Verify wire format
        assert!(parsed["success"].as_bool().unwrap());
        assert!(parsed["table"].is_object());

        let table = &parsed["table"];
        assert_eq!(table["table_name"].as_str().unwrap(), "transactions");
        assert!(table["columns"].as_array().unwrap().len() > 20); // transactions has 27 columns
        assert!(table["partition_columns"]
            .as_array()
            .unwrap()
            .contains(&serde_json::json!("chain_id")));
    }

    #[test]
    fn test_schema_list_response_json_roundtrip() {
        // Test JSON roundtrip (serialize → deserialize)
        let handler = SchemaHandler::new();
        let request = SchemaListRequest::default();
        let original = handler.handle_list(&request);

        let json = serde_json::to_string(&original).expect("Failed to serialize");
        let deserialized: SchemaListResponse =
            serde_json::from_str(&json).expect("Failed to deserialize");

        assert_eq!(deserialized.success, original.success);
        assert_eq!(deserialized.tables.len(), original.tables.len());
        assert_eq!(
            deserialized.tables[0].table_name,
            original.tables[0].table_name
        );
    }

    #[test]
    fn test_schema_get_response_json_roundtrip() {
        // Test JSON roundtrip for schema get
        let handler = SchemaHandler::new();
        let request = SchemaGetRequest {
            table_name: "blocks".to_string(),
        };
        let original = handler.handle_get(&request);

        let json = serde_json::to_string(&original).expect("Failed to serialize");
        let deserialized: SchemaGetResponse =
            serde_json::from_str(&json).expect("Failed to deserialize");

        assert_eq!(deserialized.success, original.success);
        assert!(deserialized.table.is_some());
        let table = deserialized.table.unwrap();
        assert_eq!(table.table_name, "blocks");
    }

    #[test]
    fn test_schema_error_response_format() {
        // Test that error responses have correct JSON structure
        let handler = SchemaHandler::new();
        let request = SchemaGetRequest {
            table_name: "nonexistent_table".to_string(),
        };
        let response = handler.handle_get(&request);

        let json = serde_json::to_string(&response).expect("Failed to serialize");
        let parsed: serde_json::Value = serde_json::from_str(&json).expect("Failed to parse JSON");

        assert!(!parsed["success"].as_bool().unwrap());
        assert!(parsed["error"].is_string());
        assert!(parsed["table"].is_null());
    }

    #[test]
    fn test_schema_list_request_json_parsing() {
        // Test parsing of incoming JSON requests
        let json = r#"{"include_columns": true}"#;
        let request: SchemaListRequest =
            serde_json::from_str(json).expect("Failed to parse request");
        assert!(request.include_columns);
        assert!(request.table_filter.is_none());

        // Test with include_columns = false
        let json_false = r#"{"include_columns": false}"#;
        let request_no_cols: SchemaListRequest =
            serde_json::from_str(json_false).expect("Failed to parse request");
        assert!(!request_no_cols.include_columns);

        // Test with filter
        let json_filter = r#"{"include_columns": true, "table_filter": "trans"}"#;
        let request_filter: SchemaListRequest =
            serde_json::from_str(json_filter).expect("Failed to parse request");
        assert!(request_filter.include_columns);
        assert_eq!(request_filter.table_filter, Some("trans".to_string()));
    }

    #[test]
    fn test_schema_get_request_json_parsing() {
        // Test parsing of schema get request
        let json = r#"{"table_name": "logs"}"#;
        let request: SchemaGetRequest =
            serde_json::from_str(json).expect("Failed to parse request");
        assert_eq!(request.table_name, "logs");
    }
}
