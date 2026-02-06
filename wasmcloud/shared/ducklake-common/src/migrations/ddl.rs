//! Arrow schema to DuckDB DDL conversion
//!
//! Converts Arrow DataTypes to DuckDB SQL types and generates
//! CREATE TABLE, ALTER TABLE, and other DDL statements.
//!
//! ## Function-Based Partitioning (Schema Redesign)
//!
//! For optimized blockchain tables (transactions, logs, etc.), we use
//! function-based partitioning instead of explicit shard columns:
//! - `chain_id → year(block_timestamp) → month(block_timestamp) → day(block_timestamp)`
//!
//! This allows DuckDB to automatically partition files based on timestamp
//! functions without requiring an explicit shard column in the data.

use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use serde_json::json;

/// Tables that use function-based partitioning (Schema Redesign)
///
/// These tables use `chain_id → year(block_timestamp) → month → day` partitioning
/// instead of explicit `chain_id → block_date → shard` partitioning.
const FUNCTION_PARTITIONED_TABLES: &[&str] = &[
    "transactions",
    "transactions_evm",
    "transactions_svm",
    "transactions_btc",
    "decoded_transactions_evm",
    "logs",
    "contract_calls",
    "token_transfers",
    "address_transactions",
];

/// Convert Arrow DataType to DuckDB SQL type string
pub fn arrow_type_to_duckdb(data_type: &DataType) -> String {
    match data_type {
        // String types
        DataType::Utf8 => "VARCHAR".to_string(),
        DataType::LargeUtf8 => "VARCHAR".to_string(),

        // Integer types
        DataType::Int8 => "TINYINT".to_string(),
        DataType::Int16 => "SMALLINT".to_string(),
        DataType::Int32 => "INTEGER".to_string(),
        DataType::Int64 => "BIGINT".to_string(),
        DataType::UInt8 => "UTINYINT".to_string(),
        DataType::UInt16 => "USMALLINT".to_string(),
        DataType::UInt32 => "UINTEGER".to_string(),
        DataType::UInt64 => "UBIGINT".to_string(),

        // Floating point types
        DataType::Float16 => "FLOAT".to_string(),
        DataType::Float32 => "FLOAT".to_string(),
        DataType::Float64 => "DOUBLE".to_string(),

        // Boolean
        DataType::Boolean => "BOOLEAN".to_string(),

        // Date/Time types
        DataType::Date32 => "DATE".to_string(),
        DataType::Date64 => "DATE".to_string(),
        DataType::Time32(_) => "TIME".to_string(),
        DataType::Time64(_) => "TIME".to_string(),
        DataType::Timestamp(unit, tz) => {
            let base = match unit {
                TimeUnit::Second => "TIMESTAMP_S",
                TimeUnit::Millisecond => "TIMESTAMP_MS",
                TimeUnit::Microsecond => "TIMESTAMP",
                TimeUnit::Nanosecond => "TIMESTAMP_NS",
            };
            if tz.is_some() {
                format!("{} WITH TIME ZONE", base)
            } else {
                base.to_string()
            }
        }

        // Decimal types
        DataType::Decimal128(precision, scale) => {
            format!("DECIMAL({}, {})", precision, scale)
        }
        DataType::Decimal256(precision, scale) => {
            format!("DECIMAL({}, {})", precision, scale)
        }

        // Binary types
        DataType::Binary => "BLOB".to_string(),
        DataType::LargeBinary => "BLOB".to_string(),
        DataType::FixedSizeBinary(_) => "BLOB".to_string(),

        // List types - store as JSON
        DataType::List(_) => "JSON".to_string(),
        DataType::LargeList(_) => "JSON".to_string(),
        DataType::FixedSizeList(_, _) => "JSON".to_string(),

        // Struct/Map types - store as JSON
        DataType::Struct(_) => "JSON".to_string(),
        DataType::Map(_, _) => "JSON".to_string(),

        // Fallback for other types
        _ => "VARCHAR".to_string(),
    }
}

/// Convert Arrow Field to DuckDB column definition
pub fn field_to_column_def(field: &Field) -> String {
    let sql_type = arrow_type_to_duckdb(field.data_type());
    let nullable = if field.is_nullable() { "" } else { " NOT NULL" };
    format!("\"{}\" {}{}", field.name(), sql_type, nullable)
}

/// Check if a table uses function-based partitioning
pub fn uses_function_partitioning(table_name: &str) -> bool {
    FUNCTION_PARTITIONED_TABLES.contains(&table_name)
}

/// Generate partition expression for a table
///
/// For function-partitioned tables, generates:
/// `chain_id, year(block_timestamp), month(block_timestamp), day(block_timestamp)`
///
/// For other tables, uses the partition columns directly.
pub fn generate_partition_expression(table_name: &str, partition_columns: &[String]) -> String {
    if uses_function_partitioning(table_name) {
        // Function-based partitioning: chain_id → year → month → day from block_timestamp
        "chain_id, year(block_timestamp), month(block_timestamp), day(block_timestamp)".to_string()
    } else {
        // Column-based partitioning: use columns directly
        partition_columns.join(", ")
    }
}

/// Generate CREATE TABLE DDL from Arrow schema
///
/// # Arguments
/// * `table_name` - Name of the table to create
/// * `schema` - Arrow schema defining the columns
/// * `partition_columns` - Optional partition columns for DuckLake
///
/// # Returns
/// SQL statement(s) to create the table with partitioning
///
/// ## Function-Based Partitioning
///
/// For tables listed in `FUNCTION_PARTITIONED_TABLES`, the partitioning expression
/// uses DuckDB functions on `block_timestamp`:
/// ```sql
/// ALTER TABLE "transactions" SET PARTITIONED BY (
///     chain_id,
///     year(block_timestamp),
///     month(block_timestamp),
///     day(block_timestamp)
/// );
/// ```
///
/// For other tables, partition columns are used directly:
/// ```sql
/// ALTER TABLE "blocks" SET PARTITIONED BY (chain_id, block_date, shard);
/// ```
pub fn generate_create_table_ddl(
    table_name: &str,
    schema: &Schema,
    partition_columns: &[String],
) -> String {
    let columns: Vec<String> = schema
        .fields()
        .iter()
        .map(|f| field_to_column_def(f.as_ref()))
        .collect();

    let columns_sql = columns.join(",\n    ");

    let create_sql = format!(
        "CREATE TABLE IF NOT EXISTS \"{}\" (\n    {}\n);",
        table_name, columns_sql
    );

    // Add partitioning if specified (DuckLake uses ALTER TABLE for this)
    if !partition_columns.is_empty() {
        let partition_expr = generate_partition_expression(table_name, partition_columns);
        format!(
            "{}\nALTER TABLE \"{}\" SET PARTITIONED BY ({});",
            create_sql, table_name, partition_expr
        )
    } else {
        create_sql
    }
}

/// Generate DROP TABLE DDL
pub fn generate_drop_table_ddl(table_name: &str) -> String {
    format!("DROP TABLE IF EXISTS \"{}\";", table_name)
}

/// Generate ADD COLUMN DDL
pub fn generate_add_column_ddl(table_name: &str, field: &Field) -> String {
    let column_def = field_to_column_def(field);
    format!("ALTER TABLE \"{}\" ADD COLUMN {};", table_name, column_def)
}

/// Generate DROP COLUMN DDL
pub fn generate_drop_column_ddl(table_name: &str, column_name: &str) -> String {
    format!(
        "ALTER TABLE \"{}\" DROP COLUMN \"{}\";",
        table_name, column_name
    )
}

/// Serialize schema to JSON for preservation
///
/// Stores complete schema information including column names, types,
/// nullability, and DuckDB type mappings.
pub fn schema_to_json(table_name: &str, schema: &Schema) -> serde_json::Value {
    let columns: Vec<serde_json::Value> = schema
        .fields()
        .iter()
        .map(|f| {
            let field = f.as_ref();
            json!({
                "name": field.name(),
                "arrow_type": format!("{:?}", field.data_type()),
                "duckdb_type": arrow_type_to_duckdb(field.data_type()),
                "nullable": field.is_nullable()
            })
        })
        .collect();

    json!({
        "table_name": table_name,
        "column_count": columns.len(),
        "columns": columns
    })
}

/// Generate full schema JSON for all tables
pub fn schemas_to_json(tables: &[(&str, &Schema)]) -> String {
    let table_schemas: Vec<serde_json::Value> = tables
        .iter()
        .map(|(name, schema)| schema_to_json(name, schema))
        .collect();

    json!({
        "version": 1,
        "tables": table_schemas
    })
    .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use arrow::datatypes::Field;

    #[test]
    fn test_arrow_type_to_duckdb_basic() {
        assert_eq!(arrow_type_to_duckdb(&DataType::Utf8), "VARCHAR");
        assert_eq!(arrow_type_to_duckdb(&DataType::Int64), "BIGINT");
        assert_eq!(arrow_type_to_duckdb(&DataType::Int32), "INTEGER");
        assert_eq!(arrow_type_to_duckdb(&DataType::Boolean), "BOOLEAN");
        assert_eq!(arrow_type_to_duckdb(&DataType::Date32), "DATE");
        assert_eq!(arrow_type_to_duckdb(&DataType::Float64), "DOUBLE");
    }

    #[test]
    fn test_arrow_type_to_duckdb_decimal() {
        assert_eq!(
            arrow_type_to_duckdb(&DataType::Decimal128(38, 18)),
            "DECIMAL(38, 18)"
        );
        assert_eq!(
            arrow_type_to_duckdb(&DataType::Decimal128(18, 8)),
            "DECIMAL(18, 8)"
        );
    }

    #[test]
    fn test_arrow_type_to_duckdb_timestamp() {
        assert_eq!(
            arrow_type_to_duckdb(&DataType::Timestamp(TimeUnit::Microsecond, None)),
            "TIMESTAMP"
        );
        assert_eq!(
            arrow_type_to_duckdb(&DataType::Timestamp(TimeUnit::Millisecond, None)),
            "TIMESTAMP_MS"
        );
        assert_eq!(
            arrow_type_to_duckdb(&DataType::Timestamp(
                TimeUnit::Microsecond,
                Some("UTC".into())
            )),
            "TIMESTAMP WITH TIME ZONE"
        );
    }

    #[test]
    fn test_field_to_column_def() {
        let field_not_null = Field::new("id", DataType::Int64, false);
        assert_eq!(
            field_to_column_def(&field_not_null),
            "\"id\" BIGINT NOT NULL"
        );

        let field_nullable = Field::new("name", DataType::Utf8, true);
        assert_eq!(field_to_column_def(&field_nullable), "\"name\" VARCHAR");
    }

    #[test]
    fn test_generate_create_table_ddl() {
        let schema = Schema::new(vec![
            Field::new("id", DataType::Int64, false),
            Field::new("name", DataType::Utf8, true),
            Field::new(
                "created_at",
                DataType::Timestamp(TimeUnit::Microsecond, None),
                false,
            ),
        ]);

        let ddl = generate_create_table_ddl("test_table", &schema, &[]);
        assert!(ddl.contains("CREATE TABLE IF NOT EXISTS \"test_table\""));
        assert!(ddl.contains("\"id\" BIGINT NOT NULL"));
        assert!(ddl.contains("\"name\" VARCHAR"));
        assert!(ddl.contains("\"created_at\" TIMESTAMP NOT NULL"));
    }

    #[test]
    fn test_generate_create_table_ddl_with_partitions() {
        let schema = Schema::new(vec![
            Field::new("chain_id", DataType::Utf8, false),
            Field::new("block_date", DataType::Date32, false),
            Field::new("data", DataType::Utf8, true),
        ]);

        let partitions = vec!["chain_id".to_string(), "block_date".to_string()];
        let ddl = generate_create_table_ddl("partitioned_table", &schema, &partitions);

        assert!(ddl.contains("CREATE TABLE IF NOT EXISTS \"partitioned_table\""));
        assert!(ddl.contains(
            "ALTER TABLE \"partitioned_table\" SET PARTITIONED BY (chain_id, block_date)"
        ));
    }

    #[test]
    fn test_generate_drop_table_ddl() {
        let ddl = generate_drop_table_ddl("test_table");
        assert_eq!(ddl, "DROP TABLE IF EXISTS \"test_table\";");
    }

    #[test]
    fn test_generate_add_column_ddl() {
        let field = Field::new("new_column", DataType::Int32, true);
        let ddl = generate_add_column_ddl("test_table", &field);
        assert_eq!(
            ddl,
            "ALTER TABLE \"test_table\" ADD COLUMN \"new_column\" INTEGER;"
        );
    }

    #[test]
    fn test_generate_drop_column_ddl() {
        let ddl = generate_drop_column_ddl("test_table", "old_column");
        assert_eq!(
            ddl,
            "ALTER TABLE \"test_table\" DROP COLUMN \"old_column\";"
        );
    }

    #[test]
    fn test_schema_to_json() {
        let schema = Schema::new(vec![
            Field::new("id", DataType::Int64, false),
            Field::new("name", DataType::Utf8, true),
        ]);

        let json = schema_to_json("test_table", &schema);
        assert_eq!(json["table_name"], "test_table");
        assert_eq!(json["column_count"], 2);
        assert_eq!(json["columns"][0]["name"], "id");
        assert_eq!(json["columns"][0]["duckdb_type"], "BIGINT");
        assert_eq!(json["columns"][0]["nullable"], false);
    }

    // ==========================================================================
    // Function-Based Partitioning Tests (Schema Redesign)
    // ==========================================================================

    #[test]
    fn test_uses_function_partitioning() {
        // Tables that should use function-based partitioning
        assert!(uses_function_partitioning("transactions"));
        assert!(uses_function_partitioning("transactions_evm"));
        assert!(uses_function_partitioning("transactions_svm"));
        assert!(uses_function_partitioning("transactions_btc"));
        assert!(uses_function_partitioning("decoded_transactions_evm"));
        assert!(uses_function_partitioning("logs"));
        assert!(uses_function_partitioning("token_transfers"));
        assert!(uses_function_partitioning("address_transactions"));

        // Tables that should NOT use function-based partitioning
        assert!(!uses_function_partitioning("blocks"));
        assert!(!uses_function_partitioning("token_prices"));
        assert!(!uses_function_partitioning("notification_deliveries"));
        assert!(!uses_function_partitioning("unknown_table"));
    }

    #[test]
    fn test_generate_partition_expression_function_based() {
        // Function-partitioned tables should use timestamp functions
        let expr = generate_partition_expression(
            "transactions",
            &["chain_id".to_string(), "block_date".to_string()],
        );
        assert_eq!(
            expr,
            "chain_id, year(block_timestamp), month(block_timestamp), day(block_timestamp)"
        );

        // Same for all function-partitioned tables
        let expr_logs = generate_partition_expression(
            "logs",
            &["chain_id".to_string(), "block_date".to_string()],
        );
        assert_eq!(
            expr_logs,
            "chain_id, year(block_timestamp), month(block_timestamp), day(block_timestamp)"
        );
    }

    #[test]
    fn test_generate_partition_expression_column_based() {
        // Non-function-partitioned tables should use columns directly
        let expr = generate_partition_expression(
            "blocks",
            &[
                "chain_id".to_string(),
                "block_date".to_string(),
                "shard".to_string(),
            ],
        );
        assert_eq!(expr, "chain_id, block_date, shard");

        let expr_notification = generate_partition_expression(
            "notification_deliveries",
            &[
                "delivery_date".to_string(),
                "channel_type".to_string(),
                "shard".to_string(),
            ],
        );
        assert_eq!(expr_notification, "delivery_date, channel_type, shard");
    }

    #[test]
    fn test_generate_create_table_ddl_with_function_partitioning() {
        let schema = Schema::new(vec![
            Field::new("chain_id", DataType::Utf8, false),
            Field::new("block_date", DataType::Date32, false),
            Field::new(
                "block_timestamp",
                DataType::Timestamp(TimeUnit::Microsecond, None),
                false,
            ),
            Field::new("transaction_hash", DataType::Utf8, false),
        ]);

        // Test transactions table (function-partitioned)
        let partitions = vec!["chain_id".to_string(), "block_date".to_string()];
        let ddl = generate_create_table_ddl("transactions", &schema, &partitions);

        assert!(ddl.contains("CREATE TABLE IF NOT EXISTS \"transactions\""));
        // Should use function-based partitioning
        assert!(ddl.contains("year(block_timestamp)"));
        assert!(ddl.contains("month(block_timestamp)"));
        assert!(ddl.contains("day(block_timestamp)"));
        // Should NOT use block_date directly in partition expression
        assert!(!ddl.contains("PARTITIONED BY (chain_id, block_date)"));
    }

    #[test]
    fn test_generate_create_table_ddl_with_column_partitioning() {
        let schema = Schema::new(vec![
            Field::new("chain_id", DataType::Utf8, false),
            Field::new("block_date", DataType::Date32, false),
            Field::new("shard", DataType::Int32, false),
            Field::new("block_number", DataType::Int64, false),
        ]);

        // Test blocks table (column-partitioned)
        let partitions = vec![
            "chain_id".to_string(),
            "block_date".to_string(),
            "shard".to_string(),
        ];
        let ddl = generate_create_table_ddl("blocks", &schema, &partitions);

        assert!(ddl.contains("CREATE TABLE IF NOT EXISTS \"blocks\""));
        // Should use column-based partitioning
        assert!(ddl.contains("PARTITIONED BY (chain_id, block_date, shard)"));
        // Should NOT use timestamp functions
        assert!(!ddl.contains("year(block_timestamp)"));
    }
}
