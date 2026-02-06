//! PostgreSQL migration registry
//!
//! Tracks applied migrations in PostgreSQL (same database as DuckLake metadata catalog).
//! Uses a dedicated table to record migration versions, checksums, and timing.
//! Implements distributed locking for safe concurrent migrations.

use sha2::{Digest, Sha256};
use tokio_postgres::{Client, NoTls};
use tracing::{debug, info, warn};

use super::definitions::{AppliedMigration, MigrationConfig, MigrationVersion};
use crate::error::DuckLakeError;

/// SQL for creating the migrations tracking table
const CREATE_MIGRATIONS_TABLE: &str = r#"
CREATE TABLE IF NOT EXISTS ekko_migrations (
    id              SERIAL PRIMARY KEY,
    version         INTEGER NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    checksum        VARCHAR(64) NOT NULL,
    applied_at      TIMESTAMPTZ DEFAULT NOW(),
    execution_time_ms BIGINT,
    rolled_back_at  TIMESTAMPTZ,
    up_sql          TEXT NOT NULL,
    down_sql        TEXT NOT NULL,
    schema_json     JSONB
);

CREATE INDEX IF NOT EXISTS idx_ekko_migrations_version ON ekko_migrations(version);
"#;

/// SQL for creating the migration lock table
const CREATE_LOCK_TABLE: &str = r#"
CREATE TABLE IF NOT EXISTS ekko_migration_lock (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    locked_by       VARCHAR(255),
    locked_at       TIMESTAMPTZ,
    CONSTRAINT single_lock CHECK (id = 1)
);

INSERT INTO ekko_migration_lock (id, locked_by, locked_at)
VALUES (1, NULL, NULL)
ON CONFLICT (id) DO NOTHING;
"#;

/// PostgreSQL migration registry
pub struct MigrationRegistry {
    client: Client,
    config: MigrationConfig,
}

impl MigrationRegistry {
    /// Connect to PostgreSQL and ensure migration tables exist
    pub async fn connect(config: MigrationConfig) -> Result<Self, DuckLakeError> {
        info!("Connecting to PostgreSQL for migration registry");

        let (client, connection) = tokio_postgres::connect(&config.postgres_url, NoTls)
            .await
            .map_err(|e| {
                DuckLakeError::ConnectionError(format!("PostgreSQL connection failed: {}", e))
            })?;

        // Spawn connection handler
        tokio::spawn(async move {
            if let Err(e) = connection.await {
                warn!("PostgreSQL connection error: {}", e);
            }
        });

        let registry = Self { client, config };
        registry.ensure_tables_exist().await?;

        Ok(registry)
    }

    /// Ensure migration tracking tables exist
    async fn ensure_tables_exist(&self) -> Result<(), DuckLakeError> {
        debug!("Ensuring migration tracking tables exist");

        self.client
            .batch_execute(CREATE_MIGRATIONS_TABLE)
            .await
            .map_err(|e| {
                DuckLakeError::DuckDBError(format!("Failed to create migrations table: {}", e))
            })?;

        self.client
            .batch_execute(CREATE_LOCK_TABLE)
            .await
            .map_err(|e| {
                DuckLakeError::DuckDBError(format!("Failed to create lock table: {}", e))
            })?;

        debug!("Migration tracking tables ready");
        Ok(())
    }

    /// Get all applied migrations (not rolled back)
    pub async fn get_applied_migrations(&self) -> Result<Vec<AppliedMigration>, DuckLakeError> {
        let rows = self
            .client
            .query(
                r#"
                SELECT id, version, name, checksum, applied_at, execution_time_ms, rolled_back_at
                FROM ekko_migrations
                WHERE rolled_back_at IS NULL
                ORDER BY version ASC
                "#,
                &[],
            )
            .await
            .map_err(|e| DuckLakeError::QueryError(format!("Failed to query migrations: {}", e)))?;

        let migrations = rows
            .iter()
            .map(|row| AppliedMigration {
                id: row.get(0),
                version: row.get::<_, i32>(1) as u32,
                name: row.get(2),
                checksum: row.get(3),
                applied_at: row.get(4),
                execution_time_ms: row.get(5),
                rolled_back_at: row.get(6),
            })
            .collect();

        Ok(migrations)
    }

    /// Get the current (latest) migration version
    pub async fn get_current_version(&self) -> Result<Option<MigrationVersion>, DuckLakeError> {
        let row = self
            .client
            .query_opt(
                r#"
                SELECT MAX(version) as max_version
                FROM ekko_migrations
                WHERE rolled_back_at IS NULL
                "#,
                &[],
            )
            .await
            .map_err(|e| {
                DuckLakeError::QueryError(format!("Failed to query current version: {}", e))
            })?;

        Ok(row.and_then(|r| r.get::<_, Option<i32>>(0).map(|v| v as u32)))
    }

    /// Record a successfully applied migration
    pub async fn record_migration(
        &self,
        version: MigrationVersion,
        name: &str,
        up_sql: &str,
        down_sql: &str,
        execution_time_ms: i64,
        schema_json: Option<&str>,
    ) -> Result<AppliedMigration, DuckLakeError> {
        let checksum = compute_checksum(up_sql);

        let row = self
            .client
            .query_one(
                r#"
                INSERT INTO ekko_migrations (version, name, checksum, execution_time_ms, up_sql, down_sql, schema_json)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                RETURNING id, version, name, checksum, applied_at, execution_time_ms, rolled_back_at
                "#,
                &[
                    &(version as i32),
                    &name,
                    &checksum,
                    &execution_time_ms,
                    &up_sql,
                    &down_sql,
                    &schema_json,
                ],
            )
            .await
            .map_err(|e| DuckLakeError::QueryError(format!("Failed to record migration: {}", e)))?;

        info!(
            "Recorded migration {} (v{}) in {} ms",
            name, version, execution_time_ms
        );

        Ok(AppliedMigration {
            id: row.get(0),
            version: row.get::<_, i32>(1) as u32,
            name: row.get(2),
            checksum: row.get(3),
            applied_at: row.get(4),
            execution_time_ms: row.get(5),
            rolled_back_at: row.get(6),
        })
    }

    /// Mark a migration as rolled back
    pub async fn record_rollback(&self, version: MigrationVersion) -> Result<(), DuckLakeError> {
        let rows_affected = self
            .client
            .execute(
                r#"
                UPDATE ekko_migrations
                SET rolled_back_at = NOW()
                WHERE version = $1 AND rolled_back_at IS NULL
                "#,
                &[&(version as i32)],
            )
            .await
            .map_err(|e| DuckLakeError::QueryError(format!("Failed to record rollback: {}", e)))?;

        if rows_affected == 0 {
            return Err(DuckLakeError::QueryError(format!(
                "Migration version {} not found or already rolled back",
                version
            )));
        }

        info!("Recorded rollback for migration v{}", version);
        Ok(())
    }

    /// Get the down SQL for a specific version (for rollback)
    pub async fn get_down_sql(&self, version: MigrationVersion) -> Result<String, DuckLakeError> {
        let row = self
            .client
            .query_opt(
                r#"
                SELECT down_sql
                FROM ekko_migrations
                WHERE version = $1 AND rolled_back_at IS NULL
                "#,
                &[&(version as i32)],
            )
            .await
            .map_err(|e| DuckLakeError::QueryError(format!("Failed to query down SQL: {}", e)))?;

        row.map(|r| r.get(0))
            .ok_or_else(|| DuckLakeError::QueryError(format!("Migration v{} not found", version)))
    }

    /// Acquire distributed lock for migrations
    ///
    /// Uses advisory locking with a timeout to prevent deadlocks.
    pub async fn acquire_lock(&self, instance_id: &str) -> Result<bool, DuckLakeError> {
        let timeout_secs = self.config.lock_timeout_secs;

        // Set statement timeout
        self.client
            .execute(&format!("SET statement_timeout = '{}s'", timeout_secs), &[])
            .await
            .map_err(|e| DuckLakeError::QueryError(format!("Failed to set timeout: {}", e)))?;

        // Try to acquire lock
        let rows_affected = self
            .client
            .execute(
                r#"
                UPDATE ekko_migration_lock
                SET locked_by = $1, locked_at = NOW()
                WHERE id = 1 AND (locked_by IS NULL OR locked_at < NOW() - INTERVAL '5 minutes')
                "#,
                &[&instance_id],
            )
            .await
            .map_err(|e| DuckLakeError::QueryError(format!("Failed to acquire lock: {}", e)))?;

        if rows_affected > 0 {
            info!("Acquired migration lock for instance {}", instance_id);
            Ok(true)
        } else {
            debug!("Migration lock already held by another instance");
            Ok(false)
        }
    }

    /// Release distributed lock
    pub async fn release_lock(&self, instance_id: &str) -> Result<(), DuckLakeError> {
        let rows_affected = self
            .client
            .execute(
                r#"
                UPDATE ekko_migration_lock
                SET locked_by = NULL, locked_at = NULL
                WHERE id = 1 AND locked_by = $1
                "#,
                &[&instance_id],
            )
            .await
            .map_err(|e| DuckLakeError::QueryError(format!("Failed to release lock: {}", e)))?;

        if rows_affected > 0 {
            info!("Released migration lock for instance {}", instance_id);
        } else {
            warn!(
                "Lock was not held by instance {} when releasing",
                instance_id
            );
        }

        Ok(())
    }

    /// Verify checksum for a migration
    pub async fn verify_checksum(
        &self,
        version: MigrationVersion,
        up_sql: &str,
    ) -> Result<bool, DuckLakeError> {
        let expected_checksum = compute_checksum(up_sql);

        let row = self
            .client
            .query_opt(
                r#"
                SELECT checksum
                FROM ekko_migrations
                WHERE version = $1 AND rolled_back_at IS NULL
                "#,
                &[&(version as i32)],
            )
            .await
            .map_err(|e| DuckLakeError::QueryError(format!("Failed to verify checksum: {}", e)))?;

        match row {
            Some(r) => {
                let stored_checksum: String = r.get(0);
                Ok(stored_checksum == expected_checksum)
            }
            None => Ok(true), // Not applied yet, so checksum is valid
        }
    }

    /// Check if dry-run mode is enabled
    pub fn is_dry_run(&self) -> bool {
        self.config.dry_run
    }

    /// Get target version from config
    pub fn target_version(&self) -> Option<MigrationVersion> {
        self.config.target_version
    }
}

/// Compute SHA256 checksum of SQL content
pub fn compute_checksum(sql: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(sql.as_bytes());
    let result = hasher.finalize();
    format!("{:x}", result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_checksum() {
        let sql = "CREATE TABLE test (id INT);";
        let checksum = compute_checksum(sql);

        // Should be 64 hex characters (SHA256)
        assert_eq!(checksum.len(), 64);

        // Same input should produce same output
        assert_eq!(checksum, compute_checksum(sql));

        // Different input should produce different output
        assert_ne!(checksum, compute_checksum("CREATE TABLE other (id INT);"));
    }

    #[test]
    fn test_checksum_consistency() {
        // Verify checksum is deterministic
        let sql = r#"
            CREATE TABLE IF NOT EXISTS "blocks" (
                "chain_id" VARCHAR NOT NULL,
                "block_number" BIGINT NOT NULL
            );
        "#;

        let checksum1 = compute_checksum(sql);
        let checksum2 = compute_checksum(sql);

        assert_eq!(checksum1, checksum2);
    }
}
