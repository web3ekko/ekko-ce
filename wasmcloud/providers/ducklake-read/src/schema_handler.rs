//! Schema handler for NATS-based schema discovery
//!
//! Converts DuckLake Arrow schemas to JSON format for NLP consumption.
//! Handles `ducklake.schema.list` and `ducklake.schema.get` NATS requests.

use anyhow::Result;
use arrow::datatypes::{DataType, Schema, TimeUnit};
use ducklake_common::schemas::{
    get_all_table_names, get_partition_columns_for_table, get_schema_for_table, get_z_order_columns,
};
use ducklake_common::types::{
    SchemaColumn, SchemaGetRequest, SchemaGetResponse, SchemaListRequest, SchemaListResponse,
    TableSchema,
};
use std::sync::Arc;
use tracing::{debug, info, instrument};

/// Schema handler for converting Arrow schemas to JSON format
pub struct SchemaHandler;

impl SchemaHandler {
    /// Create a new schema handler
    pub fn new() -> Self {
        Self
    }

    /// Handle schema list request
    #[instrument(skip(self))]
    pub fn handle_list(&self, request: &SchemaListRequest) -> SchemaListResponse {
        info!("Handling schema list request");

        let table_names = get_all_table_names();
        let mut tables = Vec::with_capacity(table_names.len());

        for table_name in table_names {
            // Apply filter if specified
            if let Some(filter) = &request.table_filter {
                if !table_name.contains(filter) && !filter.contains('*') {
                    continue;
                }
            }

            match self.build_table_schema(table_name, request.include_columns) {
                Ok(schema) => tables.push(schema),
                Err(e) => {
                    debug!("Failed to build schema for {}: {}", table_name, e);
                }
            }
        }

        info!("Returning {} table schemas", tables.len());
        SchemaListResponse::success(tables)
    }

    /// Handle schema get request for a specific table
    #[instrument(skip(self))]
    pub fn handle_get(&self, request: &SchemaGetRequest) -> SchemaGetResponse {
        info!(
            "Handling schema get request for table: {}",
            request.table_name
        );

        match self.build_table_schema(&request.table_name, true) {
            Ok(schema) => {
                info!(
                    "Returning schema for {} with {} columns",
                    request.table_name, schema.column_count
                );
                SchemaGetResponse::success(schema)
            }
            Err(_) => {
                info!("Table not found: {}", request.table_name);
                SchemaGetResponse::not_found(&request.table_name)
            }
        }
    }

    /// Build a TableSchema from Arrow schema
    fn build_table_schema(&self, table_name: &str, include_columns: bool) -> Result<TableSchema> {
        let arrow_schema = get_schema_for_table(table_name)
            .ok_or_else(|| anyhow::anyhow!("Table not found: {}", table_name))?;

        let partition_columns = get_partition_columns_for_table(table_name);
        let z_order_columns = get_z_order_columns(table_name);

        let columns = if include_columns {
            self.convert_arrow_schema(&arrow_schema, &partition_columns)
        } else {
            Vec::new()
        };

        let column_count = arrow_schema.fields().len();

        Ok(TableSchema {
            table_name: table_name.to_string(),
            columns,
            partition_columns,
            z_order_columns,
            column_count,
        })
    }

    /// Convert Arrow schema fields to SchemaColumn format
    fn convert_arrow_schema(
        &self,
        schema: &Arc<Schema>,
        partition_columns: &[String],
    ) -> Vec<SchemaColumn> {
        schema
            .fields()
            .iter()
            .map(|field| SchemaColumn {
                name: field.name().to_string(),
                data_type: self.arrow_type_to_string(field.data_type()),
                nullable: field.is_nullable(),
                is_partition: partition_columns.contains(&field.name().to_string()),
            })
            .collect()
    }

    /// Convert Arrow DataType to SQL-like string representation
    fn arrow_type_to_string(&self, data_type: &DataType) -> String {
        match data_type {
            DataType::Boolean => "BOOLEAN".to_string(),
            DataType::Int8 => "TINYINT".to_string(),
            DataType::Int16 => "SMALLINT".to_string(),
            DataType::Int32 => "INTEGER".to_string(),
            DataType::Int64 => "BIGINT".to_string(),
            DataType::UInt8 => "UTINYINT".to_string(),
            DataType::UInt16 => "USMALLINT".to_string(),
            DataType::UInt32 => "UINTEGER".to_string(),
            DataType::UInt64 => "UBIGINT".to_string(),
            DataType::Float32 => "REAL".to_string(),
            DataType::Float64 => "DOUBLE".to_string(),
            DataType::Utf8 | DataType::LargeUtf8 => "VARCHAR".to_string(),
            DataType::Binary | DataType::LargeBinary => "BLOB".to_string(),
            DataType::Date32 | DataType::Date64 => "DATE".to_string(),
            DataType::Timestamp(unit, tz) => {
                let precision = match unit {
                    TimeUnit::Second => "",
                    TimeUnit::Millisecond => "(3)",
                    TimeUnit::Microsecond => "(6)",
                    TimeUnit::Nanosecond => "(9)",
                };
                if tz.is_some() {
                    format!("TIMESTAMPTZ{}", precision)
                } else {
                    format!("TIMESTAMP{}", precision)
                }
            }
            DataType::Decimal128(precision, scale) => {
                format!("DECIMAL({}, {})", precision, scale)
            }
            DataType::Decimal256(precision, scale) => {
                format!("DECIMAL({}, {})", precision, scale)
            }
            DataType::List(field) => {
                format!("{}[]", self.arrow_type_to_string(field.data_type()))
            }
            DataType::Struct(fields) => {
                let field_strs: Vec<String> = fields
                    .iter()
                    .map(|f| format!("{} {}", f.name(), self.arrow_type_to_string(f.data_type())))
                    .collect();
                format!("STRUCT({})", field_strs.join(", "))
            }
            DataType::Map(field, _) => {
                format!("MAP({})", self.arrow_type_to_string(field.data_type()))
            }
            _ => format!("{:?}", data_type),
        }
    }

    /// Get all schemas as a list (convenience method)
    pub fn get_all_schemas(&self) -> Vec<TableSchema> {
        let request = SchemaListRequest {
            table_filter: None,
            include_columns: true,
        };
        self.handle_list(&request).tables
    }

    /// Get schema for a specific table (convenience method)
    pub fn get_schema(&self, table_name: &str) -> Option<TableSchema> {
        let request = SchemaGetRequest {
            table_name: table_name.to_string(),
        };
        let response = self.handle_get(&request);
        response.table
    }
}

impl Default for SchemaHandler {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_handle_list_all_tables() {
        let handler = SchemaHandler::new();
        let request = SchemaListRequest {
            table_filter: None,
            include_columns: true,
        };

        let response = handler.handle_list(&request);

        assert!(response.success);
        assert_eq!(response.tables.len(), get_all_table_names().len());
        assert!(response.error.is_none());

        // Verify table names
        let table_names: Vec<&str> = response
            .tables
            .iter()
            .map(|t| t.table_name.as_str())
            .collect();
        assert!(table_names.contains(&"blocks"));
        assert!(table_names.contains(&"transactions"));
        assert!(table_names.contains(&"logs"));
        assert!(table_names.contains(&"token_prices"));
        assert!(table_names.contains(&"protocol_events"));
        assert!(table_names.contains(&"contract_calls"));
        assert!(table_names.contains(&"notification_deliveries"));
    }

    #[test]
    fn test_handle_list_without_columns() {
        let handler = SchemaHandler::new();
        let request = SchemaListRequest {
            table_filter: None,
            include_columns: false,
        };

        let response = handler.handle_list(&request);

        assert!(response.success);
        for table in &response.tables {
            assert!(table.columns.is_empty());
            assert!(table.column_count > 0); // column_count still populated
        }
    }

    #[test]
    fn test_handle_list_with_filter() {
        let handler = SchemaHandler::new();
        let request = SchemaListRequest {
            table_filter: Some("trans".to_string()),
            include_columns: true,
        };

        let response = handler.handle_list(&request);

        assert!(response.success);
        assert!(!response.tables.is_empty());
        assert!(response
            .tables
            .iter()
            .any(|t| t.table_name == "transactions"));
        assert!(response
            .tables
            .iter()
            .all(|t| t.table_name.contains("trans")));
    }

    #[test]
    fn test_handle_get_existing_table() {
        let handler = SchemaHandler::new();
        let request = SchemaGetRequest {
            table_name: "transactions".to_string(),
        };

        let response = handler.handle_get(&request);

        assert!(response.success);
        assert!(response.table.is_some());

        let table = response.table.unwrap();
        assert_eq!(table.table_name, "transactions");
        assert!(!table.columns.is_empty());
        assert!(table.partition_columns.contains(&"chain_id".to_string()));
        assert!(table.z_order_columns.contains(&"block_number".to_string()));
    }

    #[test]
    fn test_handle_get_nonexistent_table() {
        let handler = SchemaHandler::new();
        let request = SchemaGetRequest {
            table_name: "nonexistent".to_string(),
        };

        let response = handler.handle_get(&request);

        assert!(!response.success);
        assert!(response.table.is_none());
        assert!(response.error.is_some());
        assert!(response.error.unwrap().contains("nonexistent"));
    }

    #[test]
    fn test_arrow_type_conversion() {
        let handler = SchemaHandler::new();

        // Test basic types
        assert_eq!(handler.arrow_type_to_string(&DataType::Boolean), "BOOLEAN");
        assert_eq!(handler.arrow_type_to_string(&DataType::Int64), "BIGINT");
        assert_eq!(handler.arrow_type_to_string(&DataType::Utf8), "VARCHAR");
        assert_eq!(handler.arrow_type_to_string(&DataType::Date32), "DATE");

        // Test timestamp
        assert_eq!(
            handler.arrow_type_to_string(&DataType::Timestamp(TimeUnit::Microsecond, None)),
            "TIMESTAMP(6)"
        );

        // Test decimal
        assert_eq!(
            handler.arrow_type_to_string(&DataType::Decimal128(38, 18)),
            "DECIMAL(38, 18)"
        );
    }

    #[test]
    fn test_partition_columns_marked() {
        let handler = SchemaHandler::new();
        let schema = handler.get_schema("transactions").unwrap();
        let expected_partition_columns = get_partition_columns_for_table("transactions");

        // Find partition columns
        let partition_cols: Vec<&SchemaColumn> =
            schema.columns.iter().filter(|c| c.is_partition).collect();

        assert_eq!(partition_cols.len(), expected_partition_columns.len());
        let partition_names: Vec<&str> = partition_cols.iter().map(|c| c.name.as_str()).collect();
        for col in expected_partition_columns {
            assert!(partition_names.contains(&col.as_str()));
        }
    }

    #[test]
    fn test_convenience_methods() {
        let handler = SchemaHandler::new();

        // Test get_all_schemas
        let all_schemas = handler.get_all_schemas();
        assert_eq!(all_schemas.len(), get_all_table_names().len());

        // Test get_schema
        let schema = handler.get_schema("blocks");
        assert!(schema.is_some());
        assert_eq!(schema.unwrap().table_name, "blocks");

        // Test get_schema for nonexistent
        let schema = handler.get_schema("nonexistent");
        assert!(schema.is_none());
    }
}
