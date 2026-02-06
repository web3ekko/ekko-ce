//! DuckLake table migration system
//!
//! Provides a schema migration framework for DuckLake tables that:
//! - Runs on ducklake-write provider startup
//! - Tracks migrations in PostgreSQL (same database as DuckLake metadata catalog)
//! - Supports bidirectional migrations (up/down for rollbacks)
//! - Preserves schemas as JSON snapshots with each migration
//!
//! ## Usage
//!
//! ```ignore
//! use ducklake_common::migrations::{MigrationRunner, get_all_migrations};
//! use ducklake_common::DuckLakeConfig;
//!
//! async fn run_migrations() {
//!     let config = DuckLakeConfig::from_env().unwrap();
//!     let runner = MigrationRunner::new(config);
//!     let migrations = get_all_migrations();
//!
//!     let result = runner.run_migrations(&migrations).await.unwrap();
//!     println!("Current version: {:?}", result.current_version);
//! }
//! ```
//!
//! ## Adding New Migrations
//!
//! 1. Create a new file (e.g., `v002_add_column.rs`)
//! 2. Implement the `Migration` trait:
//!
//! ```ignore
//! pub struct V002AddTokenDecimals;
//!
//! impl Migration for V002AddTokenDecimals {
//!     fn version(&self) -> u32 { 2 }
//!     fn name(&self) -> &'static str { "add_token_decimals_to_logs" }
//!     fn up(&self) -> &'static str {
//!         "ALTER TABLE logs ADD COLUMN token_decimals INTEGER;"
//!     }
//!     fn down(&self) -> &'static str {
//!         "ALTER TABLE logs DROP COLUMN token_decimals;"
//!     }
//! }
//! ```
//!
//! 3. Add to `get_all_migrations()` in this file

pub mod ddl;
pub mod definitions;
pub mod initial_tables;
pub mod registry;
pub mod runner;
pub mod v002_add_defi_tables;
pub mod v003_wallet_balances;

// Re-export commonly used types
pub use ddl::{
    arrow_type_to_duckdb, field_to_column_def, generate_add_column_ddl, generate_create_table_ddl,
    generate_drop_column_ddl, generate_drop_table_ddl, schema_to_json, schemas_to_json,
};
pub use definitions::{
    AppliedMigration, Migration, MigrationConfig, MigrationDirection, MigrationResult,
    MigrationVersion,
};
pub use initial_tables::V001InitialTables;
pub use registry::{compute_checksum, MigrationRegistry};
pub use runner::{MigrationRunner, MigrationStatus};
pub use v002_add_defi_tables::V002AddDefiTables;
pub use v003_wallet_balances::V003AddWalletBalances;

/// Get all defined migrations in order
///
/// Add new migrations here as they are created.
/// Migrations must be returned in order by version number.
///
/// ## Adding New Migrations
///
/// 1. Create a new file (e.g., `v002_add_column.rs`)
/// 2. Implement the `Migration` trait:
///
/// ```ignore
/// pub struct V002AddTokenDecimals;
///
/// impl Migration for V002AddTokenDecimals {
///     fn version(&self) -> u32 { 2 }
///     fn name(&self) -> &'static str { "add_token_decimals_to_logs" }
///     fn up(&self) -> &'static str {
///         "ALTER TABLE logs ADD COLUMN token_decimals INTEGER;"
///     }
///     fn down(&self) -> &'static str {
///         "ALTER TABLE logs DROP COLUMN token_decimals;"
///     }
/// }
/// ```
///
/// 3. Add `pub mod v002_add_column;` to this file's module declarations
/// 4. Add `Box::new(V002AddTokenDecimals)` to the vector below
pub fn get_all_migrations() -> Vec<Box<dyn Migration>> {
    vec![
        Box::new(V001InitialTables),
        Box::new(V002AddDefiTables),
        Box::new(V003AddWalletBalances),
        // Add future migrations here:
        // Box::new(V004SomeMigration),
    ]
}

/// Convenience function to run all migrations on startup
///
/// This is the recommended way to run migrations from the provider.
///
/// # Example
///
/// ```ignore
/// use ducklake_common::migrations::run_all_migrations;
/// use ducklake_common::DuckLakeConfig;
///
/// async fn startup() {
///     let config = DuckLakeConfig::from_env().unwrap();
///     run_all_migrations(&config).await.unwrap();
/// }
/// ```
pub async fn run_all_migrations(
    ducklake_config: &crate::DuckLakeConfig,
) -> Result<MigrationResult, crate::error::DuckLakeError> {
    let runner = MigrationRunner::new(ducklake_config.clone());
    let migrations = get_all_migrations();
    runner.run_migrations(&migrations).await
}

/// Run migrations with custom configuration
///
/// Allows setting options like dry_run mode and target version.
pub async fn run_migrations_with_config(
    migration_config: MigrationConfig,
    ducklake_config: &crate::DuckLakeConfig,
) -> Result<MigrationResult, crate::error::DuckLakeError> {
    let runner = MigrationRunner::with_config(migration_config, ducklake_config.clone());
    let migrations = get_all_migrations();
    runner.run_migrations(&migrations).await
}

/// Get current migration status without running migrations
pub async fn get_migration_status(
    ducklake_config: &crate::DuckLakeConfig,
) -> Result<MigrationStatus, crate::error::DuckLakeError> {
    let runner = MigrationRunner::new(ducklake_config.clone());
    runner.get_status().await
}

/// Verify all migration checksums match what's recorded in the database
///
/// Returns a list of (version, is_valid) pairs.
/// Use this to detect if migration files have been modified after being applied.
pub async fn verify_migration_checksums(
    ducklake_config: &crate::DuckLakeConfig,
) -> Result<Vec<(MigrationVersion, bool)>, crate::error::DuckLakeError> {
    let runner = MigrationRunner::new(ducklake_config.clone());
    let migrations = get_all_migrations();
    runner.verify_checksums(&migrations).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_all_migrations_ordered() {
        let migrations = get_all_migrations();

        // Should have at least V001
        assert!(!migrations.is_empty());

        // Verify migrations are in order
        let mut last_version = 0;
        for migration in &migrations {
            assert!(
                migration.version() > last_version,
                "Migrations must be in ascending order"
            );
            last_version = migration.version();
        }
    }

    #[test]
    fn test_get_all_migrations_have_up_down() {
        let migrations = get_all_migrations();

        for migration in &migrations {
            assert!(
                !migration.up().is_empty(),
                "Migration {} must have up SQL",
                migration.name()
            );
            assert!(
                !migration.down().is_empty(),
                "Migration {} must have down SQL",
                migration.name()
            );
        }
    }

    #[test]
    fn test_migration_names_unique() {
        let migrations = get_all_migrations();
        let names: Vec<_> = migrations.iter().map(|m| m.name()).collect();
        let unique_names: std::collections::HashSet<_> = names.iter().collect();

        assert_eq!(
            names.len(),
            unique_names.len(),
            "Migration names must be unique"
        );
    }
}
