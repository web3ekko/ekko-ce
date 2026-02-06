//! Migration definitions and traits

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Version number for migrations (monotonically increasing)
pub type MigrationVersion = u32;

/// A single migration operation
pub trait Migration: Send + Sync {
    /// Unique version number (e.g., 1, 2, 3...)
    fn version(&self) -> MigrationVersion;

    /// Human-readable name (e.g., "create_initial_tables")
    fn name(&self) -> &'static str;

    /// SQL to apply this migration (CREATE TABLE, ALTER TABLE, etc.)
    fn up(&self) -> &'static str;

    /// SQL to reverse this migration (DROP TABLE, ALTER TABLE DROP COLUMN, etc.)
    fn down(&self) -> &'static str;

    /// Optional: Full schema definition as JSON for preservation
    fn schema_json(&self) -> Option<String> {
        None
    }
}

/// Record of an applied migration stored in PostgreSQL
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppliedMigration {
    pub id: i32,
    pub version: MigrationVersion,
    pub name: String,
    pub checksum: String,
    pub applied_at: DateTime<Utc>,
    pub execution_time_ms: i64,
    pub rolled_back_at: Option<DateTime<Utc>>,
}

/// Direction of migration execution
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MigrationDirection {
    Up,
    Down,
}

/// Result of running migrations
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MigrationResult {
    pub migrations_applied: Vec<AppliedMigration>,
    pub migrations_rolled_back: Vec<AppliedMigration>,
    pub current_version: Option<MigrationVersion>,
    pub total_time_ms: u64,
}

impl MigrationResult {
    pub fn empty() -> Self {
        Self::default()
    }

    pub fn is_empty(&self) -> bool {
        self.migrations_applied.is_empty() && self.migrations_rolled_back.is_empty()
    }
}

/// Configuration for migration runner
#[derive(Debug, Clone)]
pub struct MigrationConfig {
    /// PostgreSQL connection URL
    pub postgres_url: String,
    /// Whether to run in dry-run mode (log but don't apply)
    pub dry_run: bool,
    /// Target version (None = latest)
    pub target_version: Option<MigrationVersion>,
    /// Lock timeout in seconds
    pub lock_timeout_secs: u32,
}

impl MigrationConfig {
    /// Create config from DuckLakeConfig
    pub fn from_ducklake_config(config: &crate::DuckLakeConfig) -> Self {
        Self {
            postgres_url: format!(
                "postgres://{}:{}@{}:{}/{}",
                config.postgres_user,
                config.postgres_password,
                config.postgres_host,
                config.postgres_port,
                config.postgres_database
            ),
            dry_run: false,
            target_version: None,
            lock_timeout_secs: 30,
        }
    }

    /// Enable dry-run mode
    pub fn with_dry_run(mut self, dry_run: bool) -> Self {
        self.dry_run = dry_run;
        self
    }

    /// Set target version
    pub fn with_target_version(mut self, version: MigrationVersion) -> Self {
        self.target_version = Some(version);
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_migration_result_empty() {
        let result = MigrationResult::empty();
        assert!(result.is_empty());
        assert!(result.migrations_applied.is_empty());
        assert!(result.migrations_rolled_back.is_empty());
        assert!(result.current_version.is_none());
    }
}
