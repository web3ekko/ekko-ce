//! Migration runner
//!
//! Executes migrations against DuckLake, tracking state in PostgreSQL.
//! Supports forward migrations (up) and rollbacks (down).

use std::time::Instant;

use duckdb::Connection;
use tracing::{debug, error, info, warn};

use super::definitions::{
    AppliedMigration, Migration, MigrationConfig, MigrationDirection, MigrationResult,
    MigrationVersion,
};
use super::registry::MigrationRegistry;
use crate::error::DuckLakeError;
use crate::DuckLakeConfig;

/// Migration runner that executes migrations and tracks state
pub struct MigrationRunner {
    config: MigrationConfig,
    ducklake_config: DuckLakeConfig,
}

impl MigrationRunner {
    /// Create a new migration runner from DuckLake config
    pub fn new(ducklake_config: DuckLakeConfig) -> Self {
        let config = MigrationConfig::from_ducklake_config(&ducklake_config);
        Self {
            config,
            ducklake_config,
        }
    }

    /// Create a new migration runner with custom config
    pub fn with_config(config: MigrationConfig, ducklake_config: DuckLakeConfig) -> Self {
        Self {
            config,
            ducklake_config,
        }
    }

    /// Run all pending migrations up to the target version
    ///
    /// # Arguments
    /// * `migrations` - Slice of migration implementations to run
    ///
    /// # Returns
    /// * `MigrationResult` - Summary of applied migrations
    pub async fn run_migrations(
        &self,
        migrations: &[Box<dyn Migration>],
    ) -> Result<MigrationResult, DuckLakeError> {
        let start_time = Instant::now();
        let mut result = MigrationResult::default();

        // Connect to registry
        let registry = MigrationRegistry::connect(self.config.clone()).await?;

        // Acquire lock
        let instance_id = &self.ducklake_config.instance_id;
        if !registry.acquire_lock(instance_id).await? {
            return Err(DuckLakeError::InternalError(
                "Could not acquire migration lock - another instance is running migrations"
                    .to_string(),
            ));
        }

        // Execute migrations with lock held
        let run_result = self
            .execute_migrations(&registry, migrations, &mut result)
            .await;

        // Always release lock
        if let Err(e) = registry.release_lock(instance_id).await {
            error!("Failed to release migration lock: {}", e);
        }

        // Propagate any execution error
        run_result?;

        result.total_time_ms = start_time.elapsed().as_millis() as u64;
        result.current_version = registry.get_current_version().await?;

        Ok(result)
    }

    /// Execute pending migrations
    async fn execute_migrations(
        &self,
        registry: &MigrationRegistry,
        migrations: &[Box<dyn Migration>],
        result: &mut MigrationResult,
    ) -> Result<(), DuckLakeError> {
        // Sort migrations by version
        let mut sorted_migrations: Vec<_> = migrations.iter().collect();
        sorted_migrations.sort_by_key(|m| m.version());

        // Get current version
        let current_version = registry.get_current_version().await?.unwrap_or(0);
        let target_version = registry
            .target_version()
            .unwrap_or_else(|| sorted_migrations.last().map(|m| m.version()).unwrap_or(0));

        info!(
            "Migration status: current={}, target={}",
            current_version, target_version
        );

        // Determine direction
        let direction = if target_version >= current_version {
            MigrationDirection::Up
        } else {
            MigrationDirection::Down
        };

        match direction {
            MigrationDirection::Up => {
                self.apply_migrations(
                    registry,
                    &sorted_migrations,
                    current_version,
                    target_version,
                    result,
                )
                .await?;
            }
            MigrationDirection::Down => {
                self.rollback_migrations(registry, current_version, target_version, result)
                    .await?;
            }
        }

        Ok(())
    }

    /// Apply pending migrations (forward)
    async fn apply_migrations(
        &self,
        registry: &MigrationRegistry,
        migrations: &[&Box<dyn Migration>],
        current_version: MigrationVersion,
        target_version: MigrationVersion,
        result: &mut MigrationResult,
    ) -> Result<(), DuckLakeError> {
        // Filter to pending migrations
        let pending: Vec<_> = migrations
            .iter()
            .filter(|m| m.version() > current_version && m.version() <= target_version)
            .collect();

        if pending.is_empty() {
            info!("No pending migrations to apply");
            return Ok(());
        }

        info!("Applying {} migrations", pending.len());

        // Verify checksums for already-applied migrations
        for migration in migrations.iter().filter(|m| m.version() <= current_version) {
            if !registry
                .verify_checksum(migration.version(), migration.up())
                .await?
            {
                return Err(DuckLakeError::SchemaError(format!(
                    "Checksum mismatch for migration v{} '{}' - schema drift detected",
                    migration.version(),
                    migration.name()
                )));
            }
        }

        // Connect to DuckLake for DDL execution
        let conn = crate::create_ducklake_connection(&self.ducklake_config)?;

        // Apply each pending migration
        for migration in pending {
            let applied = self
                .apply_single_migration(registry, &conn, *migration)
                .await?;
            result.migrations_applied.push(applied);
        }

        Ok(())
    }

    /// Apply a single migration
    async fn apply_single_migration(
        &self,
        registry: &MigrationRegistry,
        conn: &Connection,
        migration: &Box<dyn Migration>,
    ) -> Result<AppliedMigration, DuckLakeError> {
        let version = migration.version();
        let name = migration.name();
        let up_sql = migration.up();
        let down_sql = migration.down();
        let schema_json = migration.schema_json();

        info!("Applying migration v{}: {}", version, name);
        debug!("Migration SQL:\n{}", up_sql);

        if registry.is_dry_run() {
            info!("[DRY RUN] Would apply migration v{}: {}", version, name);
            // Return a mock result for dry run
            return Ok(AppliedMigration {
                id: 0,
                version,
                name: name.to_string(),
                checksum: super::registry::compute_checksum(up_sql),
                applied_at: chrono::Utc::now(),
                execution_time_ms: 0,
                rolled_back_at: None,
            });
        }

        let start_time = Instant::now();

        // Execute the migration SQL
        // Split by semicolons and execute each statement
        for statement in up_sql.split(';').filter(|s| !s.trim().is_empty()) {
            let trimmed = statement.trim();
            debug!("Executing: {}...", &trimmed[..trimmed.len().min(100)]);

            conn.execute(trimmed, []).map_err(|e| {
                DuckLakeError::DuckDBError(format!(
                    "Migration v{} '{}' failed: {} (SQL: {})",
                    version,
                    name,
                    e,
                    &trimmed[..trimmed.len().min(200)]
                ))
            })?;
        }

        let execution_time_ms = start_time.elapsed().as_millis() as i64;

        // Record in registry
        let applied = registry
            .record_migration(
                version,
                name,
                up_sql,
                down_sql,
                execution_time_ms,
                schema_json.as_deref(),
            )
            .await?;

        info!(
            "Applied migration v{}: {} in {} ms",
            version, name, execution_time_ms
        );

        Ok(applied)
    }

    /// Rollback migrations to target version
    async fn rollback_migrations(
        &self,
        registry: &MigrationRegistry,
        current_version: MigrationVersion,
        target_version: MigrationVersion,
        result: &mut MigrationResult,
    ) -> Result<(), DuckLakeError> {
        info!(
            "Rolling back from v{} to v{}",
            current_version, target_version
        );

        // Get applied migrations in reverse order
        let applied = registry.get_applied_migrations().await?;
        let to_rollback: Vec<_> = applied
            .iter()
            .filter(|m| m.version > target_version)
            .rev()
            .collect();

        if to_rollback.is_empty() {
            info!("No migrations to rollback");
            return Ok(());
        }

        info!("Rolling back {} migrations", to_rollback.len());

        // Connect to DuckLake for DDL execution
        let conn = crate::create_ducklake_connection(&self.ducklake_config)?;

        for migration in to_rollback {
            self.rollback_single_migration(registry, &conn, migration, result)
                .await?;
        }

        Ok(())
    }

    /// Rollback a single migration
    async fn rollback_single_migration(
        &self,
        registry: &MigrationRegistry,
        conn: &Connection,
        migration: &AppliedMigration,
        result: &mut MigrationResult,
    ) -> Result<(), DuckLakeError> {
        let version = migration.version;
        let name = &migration.name;

        info!("Rolling back migration v{}: {}", version, name);

        if registry.is_dry_run() {
            info!("[DRY RUN] Would rollback migration v{}: {}", version, name);
            return Ok(());
        }

        // Get stored down SQL
        let down_sql = registry.get_down_sql(version).await?;

        debug!("Rollback SQL:\n{}", down_sql);

        // Execute the rollback SQL
        for statement in down_sql.split(';').filter(|s| !s.trim().is_empty()) {
            let trimmed = statement.trim();
            debug!("Executing: {}...", &trimmed[..trimmed.len().min(100)]);

            conn.execute(trimmed, []).map_err(|e| {
                DuckLakeError::DuckDBError(format!(
                    "Rollback v{} '{}' failed: {} (SQL: {})",
                    version,
                    name,
                    e,
                    &trimmed[..trimmed.len().min(200)]
                ))
            })?;
        }

        // Record rollback
        registry.record_rollback(version).await?;

        info!("Rolled back migration v{}: {}", version, name);

        // Add to result
        let mut rolled_back = migration.clone();
        rolled_back.rolled_back_at = Some(chrono::Utc::now());
        result.migrations_rolled_back.push(rolled_back);

        Ok(())
    }

    /// Verify all migration checksums match
    pub async fn verify_checksums(
        &self,
        migrations: &[Box<dyn Migration>],
    ) -> Result<Vec<(MigrationVersion, bool)>, DuckLakeError> {
        let registry = MigrationRegistry::connect(self.config.clone()).await?;

        let mut results = Vec::new();

        for migration in migrations {
            let is_valid = registry
                .verify_checksum(migration.version(), migration.up())
                .await?;
            results.push((migration.version(), is_valid));

            if !is_valid {
                warn!(
                    "Checksum mismatch for migration v{}: {}",
                    migration.version(),
                    migration.name()
                );
            }
        }

        Ok(results)
    }

    /// Get current migration status
    pub async fn get_status(&self) -> Result<MigrationStatus, DuckLakeError> {
        let registry = MigrationRegistry::connect(self.config.clone()).await?;

        let current_version = registry.get_current_version().await?;
        let applied = registry.get_applied_migrations().await?;

        Ok(MigrationStatus {
            current_version,
            applied_migrations: applied,
        })
    }
}

/// Status of migrations
#[derive(Debug)]
pub struct MigrationStatus {
    pub current_version: Option<MigrationVersion>,
    pub applied_migrations: Vec<AppliedMigration>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_migration_result_empty() {
        let result = MigrationResult::empty();
        assert!(result.is_empty());
    }

    #[test]
    fn test_migration_result_with_data() {
        let mut result = MigrationResult::default();
        result.migrations_applied.push(AppliedMigration {
            id: 1,
            version: 1,
            name: "test".to_string(),
            checksum: "abc123".to_string(),
            applied_at: chrono::Utc::now(),
            execution_time_ms: 100,
            rolled_back_at: None,
        });

        assert!(!result.is_empty());
    }
}
