//! DuckLake Subject Patterns
//!
//! Subject hierarchy for data lake operations:
//! ```text
//! ducklake.{table}.write                    # Write operations to tables
//! ducklake.{table}.query                    # Query operations
//! ducklake.schema.list                      # Schema list requests
//! ducklake.schema.get                       # Schema get requests
//! ```

/// DuckLake write subject - for persistence
///
/// Example: `ducklake.transactions.write`
pub fn write(table: &str) -> String {
    format!("ducklake.{}.write", table)
}

/// DuckLake query subject - for querying
///
/// Example: `ducklake.transactions.query`
pub fn query(table: &str) -> String {
    format!("ducklake.{}.query", table)
}

/// Schema list request subject
pub fn schema_list() -> &'static str {
    "ducklake.schema.list"
}

/// Schema get request subject
pub fn schema_get() -> &'static str {
    "ducklake.schema.get"
}

/// Subscription patterns

/// Pattern for all write operations
pub fn pattern_write_all() -> &'static str {
    "ducklake.*.write"
}

/// Pattern for all query operations
pub fn pattern_query_all() -> &'static str {
    "ducklake.*.query"
}

/// Pattern for all DuckLake operations (use with caution)
pub fn pattern_ducklake_all() -> &'static str {
    "ducklake.>"
}

/// Common table names
pub mod tables {
    pub const TRANSACTIONS: &str = "transactions";
    pub const LOGS: &str = "logs";
    pub const BLOCKS: &str = "blocks";
    pub const TOKENS: &str = "tokens";
    pub const ALERTS: &str = "alerts";
    pub const NOTIFICATIONS: &str = "notifications";
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_write() {
        assert_eq!(write("transactions"), "ducklake.transactions.write");
    }

    #[test]
    fn test_query() {
        assert_eq!(query("transactions"), "ducklake.transactions.query");
    }
}
