//! DuckLake connection management
//!
//! Creates and configures DuckDB connections with DuckLake extension
//! attached to PostgreSQL metadata catalog and S3/MinIO data storage.
//!
//! Uses the official DuckLake secret-based pattern from Context7 docs:
//! 1. Create PostgreSQL secret for metadata catalog
//! 2. Create S3 secret for data storage
//! 3. Create DuckLake secret referencing the postgres secret
//! 4. ATTACH using the ducklake secret

use anyhow::{Context, Result};
use duckdb::Connection;
use tracing::{debug, info, warn};

use crate::config::DuckLakeConfig;
use crate::error::DuckLakeError;

/// Create a new DuckDB connection with DuckLake extension attached
///
/// This connection is configured with:
/// - DuckLake extension for lakehouse capabilities
/// - PostgreSQL connection for metadata catalog
/// - S3/MinIO connection for Parquet data storage
/// - Appropriate memory and thread settings
///
/// Uses the official secret-based pattern from DuckLake documentation.
///
/// # Example
/// ```no_run
/// use ducklake_common::{DuckLakeConfig, create_ducklake_connection};
///
/// let config = DuckLakeConfig::default();
/// let conn = create_ducklake_connection(&config).unwrap();
/// // Now you can execute queries against DuckLake tables
/// ```
pub fn create_ducklake_connection(config: &DuckLakeConfig) -> Result<Connection, DuckLakeError> {
    // Use tracing info! for all logging (eprintln may not appear in K8s logs)
    info!(">>> CONN: Creating DuckLake connection...");
    info!(
        ">>> CONN: PostgreSQL: {}:{}/{}",
        config.postgres_host, config.postgres_port, config.postgres_database
    );
    info!(">>> CONN: S3 Endpoint: {}", config.s3_endpoint);
    info!(">>> CONN: S3 Bucket: {}", config.s3_bucket);

    info!(">>> CONN: Opening DuckDB in-memory connection...");
    let conn = Connection::open_in_memory()
        .context("Failed to create DuckDB connection")
        .map_err(|e| {
            warn!(">>> CONN ERROR: Failed to create DuckDB connection: {}", e);
            DuckLakeError::ConnectionError(e.to_string())
        })?;
    info!(">>> CONN: ✓ DuckDB in-memory connection created");

    // Configure DuckDB settings
    // IMPORTANT: Set extension_directory FIRST to avoid HOME directory issues in containers
    // DuckDB needs a writable directory for extension caching
    info!(">>> CONN: Configuring DuckDB settings...");
    conn.execute_batch(&format!(
        "SET extension_directory = '{}/.duckdb_extensions';
         SET memory_limit = '{}MB';
         SET threads = {};
         SET temp_directory = '{}';
         SET enable_object_cache = true;
         SET enable_http_metadata_cache = true;",
        config.temp_directory, config.memory_limit_mb, config.threads, config.temp_directory
    ))
    .map_err(|e| {
        warn!(">>> CONN ERROR: Failed to configure DuckDB: {}", e);
        DuckLakeError::ConfigError(format!("Failed to configure DuckDB: {}", e))
    })?;
    info!(">>> CONN: ✓ DuckDB settings configured (memory={}MB, threads={}, ext_dir={}/.duckdb_extensions)",
        config.memory_limit_mb, config.threads, config.temp_directory);

    // Install and load httpfs extension for S3 support
    // NOTE: httpfs may not be available for all platforms (e.g., arm64_musl)
    // We continue without it if installation fails - DuckLake may still work via postgres extension
    info!(">>> CONN: Installing httpfs extension... (requires network access to DuckDB repo)");
    match conn.execute("INSTALL httpfs;", []) {
        Ok(_) => {
            info!(">>> CONN: ✓ httpfs installed, loading...");
            match conn.execute("LOAD httpfs;", []) {
                Ok(_) => info!(">>> CONN: ✓ httpfs extension loaded"),
                Err(e) => warn!(">>> CONN: httpfs load failed (continuing): {}", e),
            }
        }
        Err(e) => {
            warn!(
                ">>> CONN: httpfs not available for this platform (continuing): {}",
                e
            );
            warn!(">>> CONN: S3 direct access may be limited, but DuckLake postgres catalog should work");
        }
    }

    // Install DuckLake and PostgreSQL extensions
    info!(">>> CONN: Installing ducklake and postgres extensions... (requires network access)");
    conn.execute_batch(
        "INSTALL ducklake;
         LOAD ducklake;
         INSTALL postgres;
         LOAD postgres;",
    )
    .map_err(|e| {
        warn!(">>> CONN ERROR: Failed to load extensions: {}", e);
        DuckLakeError::DuckDBError(format!("Failed to load extensions: {}", e))
    })?;
    info!(">>> CONN: ✓ ducklake and postgres extensions loaded");

    // Step 1: Create PostgreSQL secret for metadata catalog
    // HOST and PORT must be separate parameters - DuckDB postgres extension expects them separately
    info!(
        ">>> CONN: Creating PostgreSQL secret (host={}, port={}, db={}, user={})...",
        config.postgres_host, config.postgres_port, config.postgres_database, config.postgres_user
    );
    let postgres_secret_sql = format!(
        "CREATE SECRET postgres_secret (TYPE postgres, HOST '{}', PORT {}, DATABASE '{}', USER '{}', PASSWORD '{}');",
        config.postgres_host,
        config.postgres_port,
        config.postgres_database,
        config.postgres_user,
        config.postgres_password
    );
    debug!("[DUCKLAKE] Creating PostgreSQL secret...");
    conn.execute(&postgres_secret_sql, []).map_err(|e| {
        warn!(">>> CONN ERROR: Failed to create PostgreSQL secret: {}", e);
        DuckLakeError::ConfigError(format!("Failed to create PostgreSQL secret: {}", e))
    })?;
    info!(">>> CONN: ✓ PostgreSQL secret created");

    // Step 2: Create S3 secret for data storage
    // ENDPOINT must NOT include http:// or https:// - DuckDB adds the protocol based on USE_SSL
    let endpoint_without_protocol = config.s3_endpoint_without_protocol();
    let use_ssl = if config.s3_use_ssl { "true" } else { "false" };
    info!(
        ">>> CONN: Creating S3 secret (endpoint={}, ssl={})...",
        endpoint_without_protocol, use_ssl
    );

    let s3_secret_sql = format!(
        "CREATE SECRET s3_secret (TYPE S3, KEY_ID '{}', SECRET '{}', REGION '{}', ENDPOINT '{}', URL_STYLE 'path', USE_SSL '{}');",
        config.s3_access_key_id,
        config.s3_secret_access_key,
        config.s3_region,
        endpoint_without_protocol,
        use_ssl
    );
    debug!(
        "[DUCKLAKE] Creating S3 secret with endpoint: {}",
        endpoint_without_protocol
    );
    conn.execute(&s3_secret_sql, []).map_err(|e| {
        warn!(">>> CONN ERROR: Failed to create S3 secret: {}", e);
        DuckLakeError::ConfigError(format!("Failed to create S3 secret: {}", e))
    })?;
    info!(">>> CONN: ✓ S3 secret created");

    // Step 3: Create DuckLake secret that references the postgres secret
    // This follows the official pattern from Context7 docs
    let s3_data_path = config.s3_data_path();
    info!(
        ">>> CONN: Creating DuckLake secret (data_path={})...",
        s3_data_path
    );
    let ducklake_secret_sql = format!(
        "CREATE SECRET ducklake_secret (TYPE ducklake, METADATA_PATH '', DATA_PATH '{}', METADATA_PARAMETERS MAP {{'TYPE': 'postgres', 'SECRET': 'postgres_secret'}});",
        s3_data_path
    );
    debug!(
        "[DUCKLAKE] Creating DuckLake secret with DATA_PATH: {}",
        s3_data_path
    );
    conn.execute(&ducklake_secret_sql, []).map_err(|e| {
        warn!(">>> CONN ERROR: Failed to create DuckLake secret: {}", e);
        DuckLakeError::ConfigError(format!("Failed to create DuckLake secret: {}", e))
    })?;
    info!(">>> CONN: ✓ DuckLake secret created");

    // Step 4: ATTACH using the ducklake secret (official pattern)
    // Use OVERRIDE_DATA_PATH to bypass data path validation in catalog
    info!(">>> CONN: Attaching to DuckLake catalog (connects to PG and S3)...");
    if let Err(e) = conn.execute(
        "ATTACH 'ducklake:ducklake_secret' AS ekko_ducklake (OVERRIDE_DATA_PATH true);",
        [],
    ) {
        warn!(">>> CONN ERROR: DuckDB ATTACH failed with error: {:?}", e);
        warn!(">>> CONN ERROR: Error message: {}", e);
        return Err(DuckLakeError::ConnectionError(format!(
            "Failed to attach DuckLake: {}",
            e
        )));
    }
    info!(">>> CONN: ✓ DuckLake catalog attached");

    // USE the attached DuckLake database
    info!(">>> CONN: Using ekko_ducklake database...");
    conn.execute("USE ekko_ducklake;", [])
        .context("Failed to USE DuckLake database")
        .map_err(|e| {
            warn!(">>> CONN ERROR: Failed to USE DuckLake database: {}", e);
            DuckLakeError::ConnectionError(e.to_string())
        })?;
    info!(">>> CONN: ✓ Using ekko_ducklake database");

    // Configure DuckLake options for optimal performance
    // Use zstd compression for better compression ratio (vs default snappy)
    info!(">>> CONN: Setting parquet compression...");
    match conn.execute(
        "CALL ekko_ducklake.set_option('parquet_compression', 'zstd');",
        [],
    ) {
        Ok(_) => {
            info!(">>> CONN: ✓ Parquet compression set to zstd");
        }
        Err(e) => {
            warn!(
                ">>> CONN: Could not set parquet compression (non-fatal): {}",
                e
            );
        }
    }

    info!(">>> CONN: ✓ DuckLake connection established successfully!");

    Ok(conn)
}

/// Create a read-only DuckDB connection for query operations
///
/// This is identical to the regular connection but signals intent.
/// DuckLake handles transaction isolation automatically.
pub fn create_readonly_connection(config: &DuckLakeConfig) -> Result<Connection, DuckLakeError> {
    // For DuckLake, read and write connections are the same
    // DuckLake handles MVCC and snapshot isolation internally
    create_ducklake_connection(config)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_connection_config_validation() {
        let config = DuckLakeConfig::default();
        // Can't test actual connection without PostgreSQL/S3, but we can validate config
        assert!(config.validate().is_ok());
    }
}
