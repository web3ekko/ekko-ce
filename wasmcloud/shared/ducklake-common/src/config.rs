//! Configuration for DuckLake providers
//!
//! Both ducklake-write and ducklake-read providers use the same configuration
//! to connect to the shared DuckLake instance (PostgreSQL + S3/MinIO).
//!
//! ## Hot/Warm/Cold Data Tier Architecture
//!
//! DuckLake supports a tiered storage strategy for optimal query performance:
//! - **Hot Tier** (0-24 hours): Smaller files, frequent compaction, fast compression
//! - **Warm Tier** (1-7 days): Standard files, moderate compaction
//! - **Cold Tier** (7+ days): Large files, Z-ordered, high compression

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;
use url::Url;

use crate::schemas::{
    ADDRESS_INDEX_TABLE, BLOCKS_TABLE, CONTRACT_CALLS_TABLE, LOGS_TABLE, LP_POSITIONS_TABLE,
    NOTIFICATION_DELIVERIES_TABLE, PROTOCOL_EVENTS_TABLE, TOKEN_HOLDINGS_TABLE, TOKEN_OHLCV_TABLE,
    TOKEN_PRICES_TABLE, TRANSACTIONS_TABLE, WALLET_ACTIVITY_TABLE, YIELD_EVENTS_TABLE,
};

/// DuckLake provider configuration
///
/// Both providers connect to the SAME DuckLake instance:
/// - PostgreSQL: metadata catalog (table schemas, snapshots, file references)
/// - S3/MinIO: data storage (Parquet files)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuckLakeConfig {
    // PostgreSQL configuration (metadata catalog)
    /// PostgreSQL host
    pub postgres_host: String,
    /// PostgreSQL port
    pub postgres_port: u16,
    /// PostgreSQL database name for DuckLake catalog
    pub postgres_database: String,
    /// PostgreSQL user
    pub postgres_user: String,
    /// PostgreSQL password
    pub postgres_password: String,

    // S3/MinIO configuration (data storage)
    /// S3 endpoint URL (e.g., "http://localhost:9000" for MinIO)
    pub s3_endpoint: String,
    /// S3 region
    pub s3_region: String,
    /// S3 bucket name
    pub s3_bucket: String,
    /// S3 access key ID
    pub s3_access_key_id: String,
    /// S3 secret access key
    pub s3_secret_access_key: String,
    /// Whether to use SSL for S3 connections
    pub s3_use_ssl: bool,
    /// Warehouse path for DuckLake tables (e.g., "warehouse")
    pub warehouse_path: String,

    // DuckDB settings
    /// Memory limit in MB per connection
    pub memory_limit_mb: usize,
    /// Number of threads per connection
    pub threads: usize,
    /// Temporary directory for DuckDB operations
    pub temp_directory: String,
    /// Enable automatic table optimization
    pub enable_optimization: bool,
    /// Maximum batch size for writes
    pub max_batch_size: usize,
    /// Enable metrics collection
    pub enable_metrics: bool,
    /// Provider instance ID
    pub instance_id: String,
}

impl DuckLakeConfig {
    /// Load configuration from wasmCloud properties HashMap
    ///
    /// Properties (from wasmCloud link config):
    /// - ducklake_postgres_host, ducklake_postgres_port, ducklake_postgres_database
    /// - ducklake_postgres_user, ducklake_postgres_password
    /// - ducklake_s3_endpoint, ducklake_s3_region, ducklake_s3_bucket
    /// - ducklake_s3_access_key_id, ducklake_s3_secret_access_key
    /// - ducklake_s3_use_ssl, ducklake_warehouse_path
    /// - ducklake_memory_limit_mb, ducklake_threads
    /// - ducklake_temp_dir, ducklake_enable_optimization
    /// - ducklake_max_batch_size, ducklake_enable_metrics
    pub fn from_properties(props: &HashMap<String, String>) -> Result<Self> {
        // PostgreSQL configuration
        let postgres_host = props
            .get("ducklake_postgres_host")
            .cloned()
            .unwrap_or_else(|| "localhost".to_string());
        let postgres_port = props
            .get("ducklake_postgres_port")
            .and_then(|v| v.parse().ok())
            .unwrap_or(5432);
        let postgres_database = props
            .get("ducklake_postgres_database")
            .cloned()
            .unwrap_or_else(|| "ducklake_catalog".to_string());
        let postgres_user = props
            .get("ducklake_postgres_user")
            .cloned()
            .unwrap_or_else(|| "ekko".to_string());
        let postgres_password = props
            .get("ducklake_postgres_password")
            .cloned()
            .context("ducklake_postgres_password property is required")?;

        // S3/MinIO configuration
        let s3_endpoint = props
            .get("ducklake_s3_endpoint")
            .cloned()
            .unwrap_or_else(|| "http://localhost:9000".to_string());
        let s3_region = props
            .get("ducklake_s3_region")
            .cloned()
            .unwrap_or_else(|| "us-east-1".to_string());
        let s3_bucket = props
            .get("ducklake_s3_bucket")
            .cloned()
            .unwrap_or_else(|| "ekko-ducklake".to_string());
        let s3_access_key_id = props
            .get("ducklake_s3_access_key_id")
            .cloned()
            .context("ducklake_s3_access_key_id property is required")?;
        let s3_secret_access_key = props
            .get("ducklake_s3_secret_access_key")
            .cloned()
            .context("ducklake_s3_secret_access_key property is required")?;
        let s3_use_ssl = props
            .get("ducklake_s3_use_ssl")
            .and_then(|v| v.parse().ok())
            .unwrap_or(false);
        let warehouse_path = props
            .get("ducklake_warehouse_path")
            .cloned()
            .unwrap_or_else(|| "warehouse".to_string());

        // DuckDB settings
        let memory_limit_mb = props
            .get("ducklake_memory_limit_mb")
            .and_then(|v| v.parse().ok())
            .unwrap_or(512);
        let threads = props
            .get("ducklake_threads")
            .and_then(|v| v.parse().ok())
            .unwrap_or(4);
        let temp_directory = props
            .get("ducklake_temp_dir")
            .cloned()
            .unwrap_or_else(|| "/tmp/ducklake".to_string());
        let enable_optimization = props
            .get("ducklake_enable_optimization")
            .and_then(|v| v.parse().ok())
            .unwrap_or(true);
        let max_batch_size = props
            .get("ducklake_max_batch_size")
            .and_then(|v| v.parse().ok())
            .unwrap_or(10000);
        let enable_metrics = props
            .get("ducklake_enable_metrics")
            .and_then(|v| v.parse().ok())
            .unwrap_or(false);
        let instance_id = props
            .get("ducklake_provider_instance_id")
            .cloned()
            .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());

        // Validate S3 endpoint URL
        Url::parse(&s3_endpoint)
            .with_context(|| format!("Invalid S3 endpoint URL: {}", s3_endpoint))?;

        Ok(Self {
            postgres_host,
            postgres_port,
            postgres_database,
            postgres_user,
            postgres_password,
            s3_endpoint,
            s3_region,
            s3_bucket,
            s3_access_key_id,
            s3_secret_access_key,
            s3_use_ssl,
            warehouse_path,
            memory_limit_mb,
            threads,
            temp_directory,
            enable_optimization,
            max_batch_size,
            enable_metrics,
            instance_id,
        })
    }

    /// Load configuration from environment variables
    ///
    /// Environment variables:
    /// - DUCKLAKE_POSTGRES_HOST, DUCKLAKE_POSTGRES_PORT, DUCKLAKE_POSTGRES_DATABASE
    /// - DUCKLAKE_POSTGRES_USER, DUCKLAKE_POSTGRES_PASSWORD
    /// - DUCKLAKE_S3_ENDPOINT, DUCKLAKE_S3_REGION, DUCKLAKE_S3_BUCKET
    /// - DUCKLAKE_S3_ACCESS_KEY_ID, DUCKLAKE_S3_SECRET_ACCESS_KEY
    /// - DUCKLAKE_S3_USE_SSL, DUCKLAKE_WAREHOUSE_PATH
    /// - DUCKLAKE_MAX_CONNECTIONS, DUCKLAKE_MEMORY_LIMIT_MB, DUCKLAKE_THREADS
    /// - DUCKLAKE_TEMP_DIR, DUCKLAKE_ENABLE_OPTIMIZATION
    /// - DUCKLAKE_MAX_BATCH_SIZE, DUCKLAKE_ENABLE_METRICS
    pub fn from_env() -> Result<Self> {
        // PostgreSQL configuration
        let postgres_host =
            env::var("DUCKLAKE_POSTGRES_HOST").unwrap_or_else(|_| "localhost".to_string());
        let postgres_port = env::var("DUCKLAKE_POSTGRES_PORT")
            .unwrap_or_else(|_| "5432".to_string())
            .parse()
            .unwrap_or(5432);
        let postgres_database = env::var("DUCKLAKE_POSTGRES_DATABASE")
            .unwrap_or_else(|_| "ducklake_catalog".to_string());
        let postgres_user =
            env::var("DUCKLAKE_POSTGRES_USER").unwrap_or_else(|_| "ekko".to_string());
        let postgres_password = env::var("DUCKLAKE_POSTGRES_PASSWORD")
            .context("DUCKLAKE_POSTGRES_PASSWORD environment variable is required")?;

        // S3/MinIO configuration
        let s3_endpoint = env::var("DUCKLAKE_S3_ENDPOINT")
            .unwrap_or_else(|_| "http://localhost:9000".to_string());
        let s3_region = env::var("DUCKLAKE_S3_REGION").unwrap_or_else(|_| "us-east-1".to_string());
        let s3_bucket =
            env::var("DUCKLAKE_S3_BUCKET").unwrap_or_else(|_| "ekko-ducklake".to_string());
        let s3_access_key_id = env::var("DUCKLAKE_S3_ACCESS_KEY_ID")
            .context("DUCKLAKE_S3_ACCESS_KEY_ID environment variable is required")?;
        let s3_secret_access_key = env::var("DUCKLAKE_S3_SECRET_ACCESS_KEY")
            .context("DUCKLAKE_S3_SECRET_ACCESS_KEY environment variable is required")?;
        let s3_use_ssl = env::var("DUCKLAKE_S3_USE_SSL")
            .unwrap_or_else(|_| "false".to_string())
            .parse()
            .unwrap_or(false);
        let warehouse_path =
            env::var("DUCKLAKE_WAREHOUSE_PATH").unwrap_or_else(|_| "warehouse".to_string());

        // DuckDB settings
        let memory_limit_mb = env::var("DUCKLAKE_MEMORY_LIMIT_MB")
            .unwrap_or_else(|_| "512".to_string())
            .parse()
            .unwrap_or(512);
        let threads = env::var("DUCKLAKE_THREADS")
            .unwrap_or_else(|_| "4".to_string())
            .parse()
            .unwrap_or(4);
        let temp_directory =
            env::var("DUCKLAKE_TEMP_DIR").unwrap_or_else(|_| "/tmp/ducklake".to_string());
        let enable_optimization = env::var("DUCKLAKE_ENABLE_OPTIMIZATION")
            .unwrap_or_else(|_| "true".to_string())
            .parse()
            .unwrap_or(true);
        let max_batch_size = env::var("DUCKLAKE_MAX_BATCH_SIZE")
            .unwrap_or_else(|_| "10000".to_string())
            .parse()
            .unwrap_or(10000);
        let enable_metrics = env::var("DUCKLAKE_ENABLE_METRICS")
            .unwrap_or_else(|_| "false".to_string())
            .parse()
            .unwrap_or(false);
        let instance_id = env::var("DUCKLAKE_PROVIDER_INSTANCE_ID")
            .unwrap_or_else(|_| uuid::Uuid::new_v4().to_string());

        // Validate S3 endpoint URL
        Url::parse(&s3_endpoint)
            .with_context(|| format!("Invalid S3 endpoint URL: {}", s3_endpoint))?;

        Ok(Self {
            postgres_host,
            postgres_port,
            postgres_database,
            postgres_user,
            postgres_password,
            s3_endpoint,
            s3_region,
            s3_bucket,
            s3_access_key_id,
            s3_secret_access_key,
            s3_use_ssl,
            warehouse_path,
            memory_limit_mb,
            threads,
            temp_directory,
            enable_optimization,
            max_batch_size,
            enable_metrics,
            instance_id,
        })
    }

    /// Get table path for a given table name
    pub fn table_path(&self, table_name: &str) -> String {
        let warehouse_path = self.warehouse_path.trim_start_matches('/');
        format!("s3://{}/{}/{}", self.s3_bucket, warehouse_path, table_name)
    }

    /// Get S3 data path for DuckLake ATTACH command
    pub fn s3_data_path(&self) -> String {
        let warehouse_path = self.warehouse_path.trim_start_matches('/');
        format!("s3://{}/{}", self.s3_bucket, warehouse_path)
    }

    /// Get S3 endpoint without protocol (for DuckDB S3 config)
    pub fn s3_endpoint_without_protocol(&self) -> String {
        self.s3_endpoint
            .trim_start_matches("http://")
            .trim_start_matches("https://")
            .to_string()
    }

    /// Validate configuration
    pub fn validate(&self) -> Result<()> {
        // Validate S3 endpoint
        Url::parse(&self.s3_endpoint)
            .with_context(|| format!("Invalid S3 endpoint: {}", self.s3_endpoint))?;

        // Validate batch size
        if self.max_batch_size == 0 {
            return Err(anyhow::anyhow!("Max batch size must be greater than 0"));
        }

        // Validate memory limit
        if self.memory_limit_mb == 0 {
            return Err(anyhow::anyhow!("Memory limit must be greater than 0"));
        }

        // Validate PostgreSQL configuration
        if self.postgres_host.is_empty() {
            return Err(anyhow::anyhow!("PostgreSQL host cannot be empty"));
        }
        if self.postgres_port == 0 {
            return Err(anyhow::anyhow!("PostgreSQL port must be greater than 0"));
        }
        if self.postgres_database.is_empty() {
            return Err(anyhow::anyhow!("PostgreSQL database name cannot be empty"));
        }
        if self.postgres_user.is_empty() {
            return Err(anyhow::anyhow!("PostgreSQL user cannot be empty"));
        }
        if self.postgres_password.is_empty() {
            return Err(anyhow::anyhow!("PostgreSQL password cannot be empty"));
        }

        Ok(())
    }
}

impl Default for DuckLakeConfig {
    fn default() -> Self {
        Self {
            postgres_host: "localhost".to_string(),
            postgres_port: 5432,
            postgres_database: "ducklake_catalog".to_string(),
            postgres_user: "ekko".to_string(),
            postgres_password: "ekko123".to_string(),
            s3_endpoint: "http://localhost:9000".to_string(),
            s3_region: "us-east-1".to_string(),
            s3_bucket: "ekko-ducklake".to_string(),
            s3_access_key_id: "minioadmin".to_string(),
            s3_secret_access_key: "minioadmin".to_string(),
            s3_use_ssl: false,
            warehouse_path: "warehouse".to_string(),
            memory_limit_mb: 512,
            threads: 4,
            temp_directory: "/tmp/ducklake".to_string(),
            enable_optimization: true,
            max_batch_size: 10000,
            enable_metrics: false,
            instance_id: uuid::Uuid::new_v4().to_string(),
        }
    }
}

// ============================================================================
// 4-Tier Storage Configuration (Schema Redesign)
// ============================================================================
//
// ## Tiered Storage Strategy
//
// DuckLake uses a 4-tier storage strategy optimized for blockchain data:
//
// | Tier   | Age     | Target Size | Compression    | Z-Order |
// |--------|---------|-------------|----------------|---------|
// | Hot    | 0-6h    | 16-32 MB    | zstd level 1   | No      |
// | Warm   | 6-24h   | 64 MB       | zstd level 2   | No      |
// | Cold   | 1-7d    | 128 MB      | zstd level 3   | No      |
// | Frozen | 7d+     | 256 MB      | zstd level 3   | Yes     |
//
// This provides optimal query performance across different data ages:
// - Hot: Recent data with frequent updates, fast compression for write throughput
// - Warm: Settling data, moderate compression, larger files for query efficiency
// - Cold: Stable data, high compression, larger files for storage efficiency
// - Frozen: Archival data, maximum compression, Z-ordered for query optimization

/// 4-tier storage configuration for tiered compaction
///
/// Implements the tiered storage strategy from the Schema Redesign plan:
/// - Hot (0-6h): Small files, fast compression, frequent compaction
/// - Warm (6-24h): Medium files, balanced compression
/// - Cold (1-7d): Large files, high compression
/// - Frozen (7d+): Very large files, high compression, Z-ordered
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HotDataConfig {
    /// Redis TTL for hot data cache in seconds (default: 600 = 10 minutes)
    pub redis_ttl_seconds: u32,

    // =========================================================================
    // Tier Boundaries (Schema Redesign)
    // =========================================================================
    /// Hot tier window in hours (default: 6, 0-6h is hot)
    pub hot_window_hours: u32,
    /// Warm tier window in hours (default: 24, 6-24h is warm)
    pub warm_window_hours: u32,
    /// Cold threshold in days (default: 7, 1-7d is cold)
    pub cold_threshold_days: u32,
    /// Frozen threshold in days (default: 7, 7d+ is frozen)
    pub frozen_threshold_days: u32,

    // =========================================================================
    // Hot Tier Configuration (0-6h)
    // =========================================================================
    /// Target file size for hot tier in MB (default: 32, range 16-32)
    pub hot_file_size_mb: u32,
    /// Compression level for hot tier (default: 1, zstd level 1)
    pub hot_compression_level: u32,
    /// Hot tier compaction interval in minutes (default: 15)
    pub hot_compaction_interval_min: u32,

    // =========================================================================
    // Warm Tier Configuration (6-24h)
    // =========================================================================
    /// Target file size for warm tier in MB (default: 64)
    pub warm_file_size_mb: u32,
    /// Compression level for warm tier (default: 2, zstd level 2)
    pub warm_compression_level: u32,
    /// Warm tier compaction interval in minutes (default: 30)
    pub warm_compaction_interval_min: u32,

    // =========================================================================
    // Cold Tier Configuration (1-7d)
    // =========================================================================
    /// Target file size for cold tier in MB (default: 128)
    pub cold_file_size_mb: u32,
    /// Compression level for cold tier (default: 3, zstd level 3)
    pub cold_compression_level: u32,
    /// Cold tier compaction interval in minutes (default: 60)
    pub cold_compaction_interval_min: u32,

    // =========================================================================
    // Frozen Tier Configuration (7d+)
    // =========================================================================
    /// Target file size for frozen tier in MB (default: 256)
    pub frozen_file_size_mb: u32,
    /// Compression level for frozen tier (default: 3, zstd level 3)
    pub frozen_compression_level: u32,
    /// Enable Z-ordering for frozen data (default: true)
    pub enable_frozen_z_ordering: bool,
    /// Frozen tier compaction interval in hours (default: 24)
    pub frozen_compaction_interval_hours: u32,
}

impl Default for HotDataConfig {
    fn default() -> Self {
        Self {
            redis_ttl_seconds: 600, // 10 minutes

            // Tier boundaries (Schema Redesign)
            hot_window_hours: 6,      // 0-6h is hot
            warm_window_hours: 24,    // 6-24h is warm
            cold_threshold_days: 1,   // 1-7d is cold
            frozen_threshold_days: 7, // 7d+ is frozen

            // Hot tier (0-6h): 16-32 MB, zstd level 1, no Z-order
            hot_file_size_mb: 32,
            hot_compression_level: 1,
            hot_compaction_interval_min: 15,

            // Warm tier (6-24h): 64 MB, zstd level 2, no Z-order
            warm_file_size_mb: 64,
            warm_compression_level: 2,
            warm_compaction_interval_min: 30,

            // Cold tier (1-7d): 128 MB, zstd level 3, no Z-order
            cold_file_size_mb: 128,
            cold_compression_level: 3,
            cold_compaction_interval_min: 60,

            // Frozen tier (7d+): 256 MB, zstd level 3, Z-ordered
            frozen_file_size_mb: 256,
            frozen_compression_level: 3,
            enable_frozen_z_ordering: true,
            frozen_compaction_interval_hours: 24,
        }
    }
}

impl HotDataConfig {
    /// Load hot data configuration from environment variables
    pub fn from_env() -> Self {
        Self {
            redis_ttl_seconds: env::var("DUCKLAKE_REDIS_TTL_SECONDS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(600),

            // Tier boundaries
            hot_window_hours: env::var("DUCKLAKE_HOT_WINDOW_HOURS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(6),
            warm_window_hours: env::var("DUCKLAKE_WARM_WINDOW_HOURS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(24),
            cold_threshold_days: env::var("DUCKLAKE_COLD_THRESHOLD_DAYS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(1),
            frozen_threshold_days: env::var("DUCKLAKE_FROZEN_THRESHOLD_DAYS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(7),

            // Hot tier
            hot_file_size_mb: env::var("DUCKLAKE_HOT_FILE_SIZE_MB")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(32),
            hot_compression_level: env::var("DUCKLAKE_HOT_COMPRESSION_LEVEL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(1),
            hot_compaction_interval_min: env::var("DUCKLAKE_HOT_COMPACTION_INTERVAL_MIN")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(15),

            // Warm tier
            warm_file_size_mb: env::var("DUCKLAKE_WARM_FILE_SIZE_MB")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(64),
            warm_compression_level: env::var("DUCKLAKE_WARM_COMPRESSION_LEVEL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(2),
            warm_compaction_interval_min: env::var("DUCKLAKE_WARM_COMPACTION_INTERVAL_MIN")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(30),

            // Cold tier
            cold_file_size_mb: env::var("DUCKLAKE_COLD_FILE_SIZE_MB")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(128),
            cold_compression_level: env::var("DUCKLAKE_COLD_COMPRESSION_LEVEL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(3),
            cold_compaction_interval_min: env::var("DUCKLAKE_COLD_COMPACTION_INTERVAL_MIN")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(60),

            // Frozen tier
            frozen_file_size_mb: env::var("DUCKLAKE_FROZEN_FILE_SIZE_MB")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(256),
            frozen_compression_level: env::var("DUCKLAKE_FROZEN_COMPRESSION_LEVEL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(3),
            enable_frozen_z_ordering: env::var("DUCKLAKE_ENABLE_FROZEN_Z_ORDERING")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(true),
            frozen_compaction_interval_hours: env::var("DUCKLAKE_FROZEN_COMPACTION_INTERVAL_HOURS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(24),
        }
    }

    /// Check if data at given age is in hot tier (0-6h)
    pub fn is_hot(&self, age_hours: u32) -> bool {
        age_hours <= self.hot_window_hours
    }

    /// Check if data at given age is in warm tier (6-24h)
    pub fn is_warm(&self, age_hours: u32) -> bool {
        age_hours > self.hot_window_hours && age_hours <= self.warm_window_hours
    }

    /// Check if data at given age is in cold tier (1-7d)
    pub fn is_cold(&self, age_days: u32) -> bool {
        age_days >= self.cold_threshold_days && age_days < self.frozen_threshold_days
    }

    /// Check if data at given age is in frozen tier (7d+)
    pub fn is_frozen(&self, age_days: u32) -> bool {
        age_days >= self.frozen_threshold_days
    }

    /// Get target file size for data tier based on age in hours
    pub fn target_file_size_mb(&self, age_hours: u32) -> u32 {
        let age_days = age_hours / 24;
        if self.is_frozen(age_days) {
            self.frozen_file_size_mb
        } else if self.is_warm(age_hours) {
            // Check warm BEFORE cold - warm includes 24h, cold starts at 25h
            self.warm_file_size_mb
        } else if self.is_cold(age_days) {
            self.cold_file_size_mb
        } else {
            self.hot_file_size_mb
        }
    }

    /// Get compression level for data tier based on age in hours
    pub fn compression_level(&self, age_hours: u32) -> u32 {
        let age_days = age_hours / 24;
        if self.is_frozen(age_days) {
            self.frozen_compression_level
        } else if self.is_warm(age_hours) {
            // Check warm BEFORE cold - warm includes 24h, cold starts at 25h
            self.warm_compression_level
        } else if self.is_cold(age_days) {
            self.cold_compression_level
        } else {
            self.hot_compression_level
        }
    }

    /// Check if Z-ordering should be enabled for data at given age
    pub fn should_z_order(&self, age_hours: u32) -> bool {
        let age_days = age_hours / 24;
        self.is_frozen(age_days) && self.enable_frozen_z_ordering
    }

    /// Get compaction interval in minutes for data at given age
    pub fn compaction_interval_minutes(&self, age_hours: u32) -> u32 {
        let age_days = age_hours / 24;
        if self.is_frozen(age_days) {
            self.frozen_compaction_interval_hours * 60
        } else if self.is_warm(age_hours) {
            // Check warm BEFORE cold - warm includes 24h, cold starts at 25h
            self.warm_compaction_interval_min
        } else if self.is_cold(age_days) {
            self.cold_compaction_interval_min
        } else {
            self.hot_compaction_interval_min
        }
    }
}

// ============================================================================
// Per-Table Compaction Configuration
// ============================================================================

/// Compression strategy for a table
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CompressionStrategy {
    /// High compression, smaller files (zstd level 3)
    High,
    /// Balanced compression (zstd level 2)
    Balanced,
    /// Fast compression, faster writes (zstd level 1)
    Fast,
}

impl Default for CompressionStrategy {
    fn default() -> Self {
        Self::Balanced
    }
}

impl CompressionStrategy {
    /// Get zstd compression level
    pub fn zstd_level(&self) -> u32 {
        match self {
            CompressionStrategy::High => 3,
            CompressionStrategy::Balanced => 2,
            CompressionStrategy::Fast => 1,
        }
    }
}

/// Per-table compaction configuration
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TableCompactionConfig {
    /// Target file size in MB
    pub target_file_size_mb: u32,
    /// Compression strategy
    pub compression: CompressionStrategy,
    /// Enable Z-ordering during compaction
    pub enable_z_ordering: bool,
    /// Compaction threshold (number of small files to trigger compaction)
    pub compaction_threshold: u32,
    /// Minimum age in hours before compaction (avoid compacting hot data)
    pub min_compaction_age_hours: u32,
}

impl Default for TableCompactionConfig {
    fn default() -> Self {
        Self {
            target_file_size_mb: 128,
            compression: CompressionStrategy::Balanced,
            enable_z_ordering: true,
            compaction_threshold: 10,
            min_compaction_age_hours: 1,
        }
    }
}

/// Per-table configuration map
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableConfigMap {
    /// Configuration for each table
    pub tables: HashMap<String, TableCompactionConfig>,
}

impl Default for TableConfigMap {
    fn default() -> Self {
        let mut tables = HashMap::new();

        // Core blockchain tables (high cardinality, balanced compression)
        let core_config = TableCompactionConfig {
            target_file_size_mb: 128,
            compression: CompressionStrategy::High,
            enable_z_ordering: true,
            compaction_threshold: 10,
            min_compaction_age_hours: 1,
        };
        tables.insert(BLOCKS_TABLE.to_string(), core_config.clone());
        tables.insert(TRANSACTIONS_TABLE.to_string(), core_config.clone());
        tables.insert(LOGS_TABLE.to_string(), core_config.clone());
        tables.insert(CONTRACT_CALLS_TABLE.to_string(), core_config.clone());
        tables.insert(PROTOCOL_EVENTS_TABLE.to_string(), core_config.clone());

        // Time-series tables (fast compression for writes)
        let time_series_config = TableCompactionConfig {
            target_file_size_mb: 64,
            compression: CompressionStrategy::Fast,
            enable_z_ordering: true,
            compaction_threshold: 15,
            min_compaction_age_hours: 1,
        };
        tables.insert(TOKEN_PRICES_TABLE.to_string(), time_series_config.clone());
        tables.insert(TOKEN_OHLCV_TABLE.to_string(), time_series_config.clone());

        // Address-centric tables (balanced for wallet queries)
        let address_config = TableCompactionConfig {
            target_file_size_mb: 96,
            compression: CompressionStrategy::Balanced,
            enable_z_ordering: true,
            compaction_threshold: 12,
            min_compaction_age_hours: 2,
        };
        tables.insert(WALLET_ACTIVITY_TABLE.to_string(), address_config.clone());
        tables.insert(ADDRESS_INDEX_TABLE.to_string(), address_config.clone());

        // DeFi analytics tables (balanced compression)
        let defi_config = TableCompactionConfig {
            target_file_size_mb: 64,
            compression: CompressionStrategy::Balanced,
            enable_z_ordering: true,
            compaction_threshold: 10,
            min_compaction_age_hours: 1,
        };
        tables.insert(LP_POSITIONS_TABLE.to_string(), defi_config.clone());
        tables.insert(YIELD_EVENTS_TABLE.to_string(), defi_config.clone());

        // Snapshot tables (high compression, less frequent updates)
        let snapshot_config = TableCompactionConfig {
            target_file_size_mb: 128,
            compression: CompressionStrategy::High,
            enable_z_ordering: true,
            compaction_threshold: 8,
            min_compaction_age_hours: 6, // Daily snapshots, less frequent compaction
        };
        tables.insert(TOKEN_HOLDINGS_TABLE.to_string(), snapshot_config);

        // Notification deliveries (smaller files, balanced)
        let notification_config = TableCompactionConfig {
            target_file_size_mb: 32,
            compression: CompressionStrategy::Balanced,
            enable_z_ordering: false, // No Z-ordering for notifications
            compaction_threshold: 20,
            min_compaction_age_hours: 1,
        };
        tables.insert(
            NOTIFICATION_DELIVERIES_TABLE.to_string(),
            notification_config,
        );

        Self { tables }
    }
}

impl TableConfigMap {
    /// Get configuration for a specific table
    pub fn get_config(&self, table_name: &str) -> TableCompactionConfig {
        self.tables.get(table_name).cloned().unwrap_or_default()
    }

    /// Set custom configuration for a table
    pub fn set_config(&mut self, table_name: &str, config: TableCompactionConfig) {
        self.tables.insert(table_name.to_string(), config);
    }

    /// Get all table names with custom configuration
    pub fn configured_tables(&self) -> Vec<&str> {
        self.tables.keys().map(|s| s.as_str()).collect()
    }

    /// Check if table has Z-ordering enabled
    pub fn is_z_ordering_enabled(&self, table_name: &str) -> bool {
        self.get_config(table_name).enable_z_ordering
    }

    /// Get compression level for a table
    pub fn compression_level(&self, table_name: &str) -> u32 {
        self.get_config(table_name).compression.zstd_level()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ============================================================================
    // DuckLakeConfig Tests
    // ============================================================================

    #[test]
    fn test_config_validation() {
        let config = DuckLakeConfig::default();
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_invalid_memory_limit() {
        let mut config = DuckLakeConfig::default();
        config.memory_limit_mb = 0;
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_table_path() {
        let config = DuckLakeConfig::default();
        let path = config.table_path("transactions");
        assert_eq!(path, "s3://ekko-ducklake/warehouse/transactions");
    }

    #[test]
    fn test_s3_data_path() {
        let config = DuckLakeConfig::default();
        let path = config.s3_data_path();
        assert_eq!(path, "s3://ekko-ducklake/warehouse");
    }

    #[test]
    fn test_s3_endpoint_without_protocol() {
        let mut config = DuckLakeConfig::default();
        config.s3_endpoint = "http://minio.ekko.svc:9000".to_string();
        assert_eq!(config.s3_endpoint_without_protocol(), "minio.ekko.svc:9000");

        config.s3_endpoint = "https://s3.amazonaws.com".to_string();
        assert_eq!(config.s3_endpoint_without_protocol(), "s3.amazonaws.com");
    }

    // ============================================================================
    // HotDataConfig Tests (4-Tier System)
    // ============================================================================

    #[test]
    fn test_hot_data_config_defaults() {
        let config = HotDataConfig::default();

        // Redis TTL
        assert_eq!(config.redis_ttl_seconds, 600);

        // Tier boundaries (Schema Redesign)
        assert_eq!(config.hot_window_hours, 6); // 0-6h is hot
        assert_eq!(config.warm_window_hours, 24); // 6-24h is warm
        assert_eq!(config.cold_threshold_days, 1); // 1-7d is cold
        assert_eq!(config.frozen_threshold_days, 7); // 7d+ is frozen

        // Hot tier config (0-6h)
        assert_eq!(config.hot_file_size_mb, 32);
        assert_eq!(config.hot_compression_level, 1);
        assert_eq!(config.hot_compaction_interval_min, 15);

        // Warm tier config (6-24h)
        assert_eq!(config.warm_file_size_mb, 64);
        assert_eq!(config.warm_compression_level, 2);
        assert_eq!(config.warm_compaction_interval_min, 30);

        // Cold tier config (1-7d)
        assert_eq!(config.cold_file_size_mb, 128);
        assert_eq!(config.cold_compression_level, 3);
        assert_eq!(config.cold_compaction_interval_min, 60);

        // Frozen tier config (7d+)
        assert_eq!(config.frozen_file_size_mb, 256);
        assert_eq!(config.frozen_compression_level, 3);
        assert!(config.enable_frozen_z_ordering);
        assert_eq!(config.frozen_compaction_interval_hours, 24);
    }

    #[test]
    fn test_hot_data_config_is_hot() {
        let config = HotDataConfig::default();

        // Within hot window (0-6 hours)
        assert!(config.is_hot(0));
        assert!(config.is_hot(3));
        assert!(config.is_hot(6));

        // Beyond hot window
        assert!(!config.is_hot(7));
        assert!(!config.is_hot(24));
    }

    #[test]
    fn test_hot_data_config_is_warm() {
        let config = HotDataConfig::default();

        // Not warm (in hot tier)
        assert!(!config.is_warm(0));
        assert!(!config.is_warm(6));

        // In warm tier (6-24 hours)
        assert!(config.is_warm(7));
        assert!(config.is_warm(12));
        assert!(config.is_warm(24));

        // Beyond warm window
        assert!(!config.is_warm(25));
    }

    #[test]
    fn test_hot_data_config_is_cold() {
        let config = HotDataConfig::default();

        // Not cold (< 1 day)
        assert!(!config.is_cold(0));

        // Cold (1-7 days)
        assert!(config.is_cold(1));
        assert!(config.is_cold(3));
        assert!(config.is_cold(6));

        // Not cold (>= 7 days is frozen)
        assert!(!config.is_cold(7));
        assert!(!config.is_cold(14));
    }

    #[test]
    fn test_hot_data_config_is_frozen() {
        let config = HotDataConfig::default();

        // Not frozen (< 7 days)
        assert!(!config.is_frozen(0));
        assert!(!config.is_frozen(6));

        // Frozen (>= 7 days)
        assert!(config.is_frozen(7));
        assert!(config.is_frozen(14));
        assert!(config.is_frozen(30));
    }

    #[test]
    fn test_hot_data_config_target_file_size() {
        let config = HotDataConfig::default();

        // Hot tier (0-6h): 32 MB
        assert_eq!(config.target_file_size_mb(0), 32);
        assert_eq!(config.target_file_size_mb(6), 32);

        // Warm tier (6-24h): 64 MB
        assert_eq!(config.target_file_size_mb(12), 64);
        assert_eq!(config.target_file_size_mb(24), 64);

        // Cold tier (1-7d): 128 MB
        assert_eq!(config.target_file_size_mb(48), 128); // 2 days
        assert_eq!(config.target_file_size_mb(144), 128); // 6 days

        // Frozen tier (7d+): 256 MB
        assert_eq!(config.target_file_size_mb(168), 256); // 7 days
        assert_eq!(config.target_file_size_mb(336), 256); // 14 days
    }

    #[test]
    fn test_hot_data_config_compression_level() {
        let config = HotDataConfig::default();

        // Hot tier: level 1
        assert_eq!(config.compression_level(0), 1);
        assert_eq!(config.compression_level(6), 1);

        // Warm tier: level 2
        assert_eq!(config.compression_level(12), 2);
        assert_eq!(config.compression_level(24), 2);

        // Cold tier: level 3
        assert_eq!(config.compression_level(48), 3);

        // Frozen tier: level 3
        assert_eq!(config.compression_level(168), 3);
    }

    #[test]
    fn test_hot_data_config_should_z_order() {
        let config = HotDataConfig::default();

        // Only frozen tier gets Z-ordering
        assert!(!config.should_z_order(0)); // hot
        assert!(!config.should_z_order(12)); // warm
        assert!(!config.should_z_order(48)); // cold
        assert!(config.should_z_order(168)); // frozen - Z-ordered!
    }

    #[test]
    fn test_hot_data_config_compaction_interval() {
        let config = HotDataConfig::default();

        // Hot tier: 15 min
        assert_eq!(config.compaction_interval_minutes(0), 15);

        // Warm tier: 30 min
        assert_eq!(config.compaction_interval_minutes(12), 30);

        // Cold tier: 60 min
        assert_eq!(config.compaction_interval_minutes(48), 60);

        // Frozen tier: 24 hours (1440 min)
        assert_eq!(config.compaction_interval_minutes(168), 24 * 60);
    }

    #[test]
    fn test_hot_data_config_custom_values() {
        let config = HotDataConfig {
            redis_ttl_seconds: 300,
            hot_window_hours: 12,
            warm_window_hours: 48,
            cold_threshold_days: 3,
            frozen_threshold_days: 14,
            hot_file_size_mb: 16,
            hot_compression_level: 1,
            hot_compaction_interval_min: 10,
            warm_file_size_mb: 48,
            warm_compression_level: 2,
            warm_compaction_interval_min: 20,
            cold_file_size_mb: 96,
            cold_compression_level: 3,
            cold_compaction_interval_min: 45,
            frozen_file_size_mb: 192,
            frozen_compression_level: 3,
            enable_frozen_z_ordering: false,
            frozen_compaction_interval_hours: 12,
        };

        // Custom hot window (12 hours)
        assert!(config.is_hot(12));
        assert!(!config.is_hot(13));

        // Custom warm window (12-48 hours)
        assert!(config.is_warm(13));
        assert!(config.is_warm(48));
        assert!(!config.is_warm(49));

        // Custom cold threshold (3-14 days)
        assert!(config.is_cold(3));
        assert!(config.is_cold(13));
        assert!(!config.is_cold(14)); // now frozen

        // Custom frozen threshold (14+ days)
        assert!(config.is_frozen(14));
        assert!(config.is_frozen(30));

        // Custom file sizes
        assert_eq!(config.target_file_size_mb(10), 16); // hot
        assert_eq!(config.target_file_size_mb(24), 48); // warm
        assert_eq!(config.target_file_size_mb(96), 96); // cold (4 days)
        assert_eq!(config.target_file_size_mb(336), 192); // frozen (14 days)

        // Frozen Z-ordering disabled
        assert!(!config.should_z_order(336));
    }

    // ============================================================================
    // CompressionStrategy Tests
    // ============================================================================

    #[test]
    fn test_compression_strategy_default() {
        let strategy = CompressionStrategy::default();
        assert_eq!(strategy, CompressionStrategy::Balanced);
    }

    #[test]
    fn test_compression_strategy_zstd_levels() {
        assert_eq!(CompressionStrategy::High.zstd_level(), 3);
        assert_eq!(CompressionStrategy::Balanced.zstd_level(), 2);
        assert_eq!(CompressionStrategy::Fast.zstd_level(), 1);
    }

    // ============================================================================
    // TableCompactionConfig Tests
    // ============================================================================

    #[test]
    fn test_table_compaction_config_default() {
        let config = TableCompactionConfig::default();

        assert_eq!(config.target_file_size_mb, 128);
        assert_eq!(config.compression, CompressionStrategy::Balanced);
        assert!(config.enable_z_ordering);
        assert_eq!(config.compaction_threshold, 10);
        assert_eq!(config.min_compaction_age_hours, 1);
    }

    // ============================================================================
    // TableConfigMap Tests
    // ============================================================================

    #[test]
    fn test_table_config_map_default_contains_all_tables() {
        let config_map = TableConfigMap::default();

        // Core blockchain tables
        assert!(config_map.tables.contains_key(BLOCKS_TABLE));
        assert!(config_map.tables.contains_key(TRANSACTIONS_TABLE));
        assert!(config_map.tables.contains_key(LOGS_TABLE));
        assert!(config_map.tables.contains_key(CONTRACT_CALLS_TABLE));
        assert!(config_map.tables.contains_key(PROTOCOL_EVENTS_TABLE));

        // Time-series tables
        assert!(config_map.tables.contains_key(TOKEN_PRICES_TABLE));
        assert!(config_map.tables.contains_key(TOKEN_OHLCV_TABLE));

        // Address-centric tables
        assert!(config_map.tables.contains_key(WALLET_ACTIVITY_TABLE));
        assert!(config_map.tables.contains_key(ADDRESS_INDEX_TABLE));

        // DeFi analytics tables
        assert!(config_map.tables.contains_key(LP_POSITIONS_TABLE));
        assert!(config_map.tables.contains_key(YIELD_EVENTS_TABLE));

        // Snapshot tables
        assert!(config_map.tables.contains_key(TOKEN_HOLDINGS_TABLE));

        // Notification tables
        assert!(config_map
            .tables
            .contains_key(NOTIFICATION_DELIVERIES_TABLE));
    }

    #[test]
    fn test_table_config_map_get_config() {
        let config_map = TableConfigMap::default();

        // Known table
        let tx_config = config_map.get_config(TRANSACTIONS_TABLE);
        assert_eq!(tx_config.compression, CompressionStrategy::High);
        assert!(tx_config.enable_z_ordering);

        // Unknown table returns default
        let unknown_config = config_map.get_config("unknown_table");
        assert_eq!(unknown_config, TableCompactionConfig::default());
    }

    #[test]
    fn test_table_config_map_set_config() {
        let mut config_map = TableConfigMap::default();

        let custom_config = TableCompactionConfig {
            target_file_size_mb: 256,
            compression: CompressionStrategy::High,
            enable_z_ordering: false,
            compaction_threshold: 5,
            min_compaction_age_hours: 4,
        };

        config_map.set_config("custom_table", custom_config.clone());

        let retrieved = config_map.get_config("custom_table");
        assert_eq!(retrieved.target_file_size_mb, 256);
        assert_eq!(retrieved.compression, CompressionStrategy::High);
        assert!(!retrieved.enable_z_ordering);
        assert_eq!(retrieved.compaction_threshold, 5);
    }

    #[test]
    fn test_table_config_map_configured_tables() {
        let config_map = TableConfigMap::default();
        let tables = config_map.configured_tables();

        // Should have all 13 tables configured
        assert_eq!(tables.len(), 13);
        assert!(tables.contains(&TRANSACTIONS_TABLE));
        assert!(tables.contains(&WALLET_ACTIVITY_TABLE));
    }

    #[test]
    fn test_table_config_map_is_z_ordering_enabled() {
        let config_map = TableConfigMap::default();

        // Most tables have Z-ordering enabled
        assert!(config_map.is_z_ordering_enabled(TRANSACTIONS_TABLE));
        assert!(config_map.is_z_ordering_enabled(WALLET_ACTIVITY_TABLE));

        // Notification deliveries has Z-ordering disabled
        assert!(!config_map.is_z_ordering_enabled(NOTIFICATION_DELIVERIES_TABLE));
    }

    #[test]
    fn test_table_config_map_compression_level() {
        let config_map = TableConfigMap::default();

        // Core tables use high compression (level 3)
        assert_eq!(config_map.compression_level(TRANSACTIONS_TABLE), 3);
        assert_eq!(config_map.compression_level(LOGS_TABLE), 3);

        // Time-series tables use fast compression (level 1)
        assert_eq!(config_map.compression_level(TOKEN_PRICES_TABLE), 1);
        assert_eq!(config_map.compression_level(TOKEN_OHLCV_TABLE), 1);

        // Address-centric tables use balanced compression (level 2)
        assert_eq!(config_map.compression_level(WALLET_ACTIVITY_TABLE), 2);
        assert_eq!(config_map.compression_level(ADDRESS_INDEX_TABLE), 2);
    }

    #[test]
    fn test_table_config_map_core_tables_config() {
        let config_map = TableConfigMap::default();

        let tx_config = config_map.get_config(TRANSACTIONS_TABLE);
        assert_eq!(tx_config.target_file_size_mb, 128);
        assert_eq!(tx_config.compression, CompressionStrategy::High);
        assert!(tx_config.enable_z_ordering);
        assert_eq!(tx_config.compaction_threshold, 10);
        assert_eq!(tx_config.min_compaction_age_hours, 1);
    }

    #[test]
    fn test_table_config_map_time_series_config() {
        let config_map = TableConfigMap::default();

        let price_config = config_map.get_config(TOKEN_PRICES_TABLE);
        assert_eq!(price_config.target_file_size_mb, 64);
        assert_eq!(price_config.compression, CompressionStrategy::Fast);
        assert!(price_config.enable_z_ordering);
        assert_eq!(price_config.compaction_threshold, 15);
    }

    #[test]
    fn test_table_config_map_address_config() {
        let config_map = TableConfigMap::default();

        let wallet_config = config_map.get_config(WALLET_ACTIVITY_TABLE);
        assert_eq!(wallet_config.target_file_size_mb, 96);
        assert_eq!(wallet_config.compression, CompressionStrategy::Balanced);
        assert!(wallet_config.enable_z_ordering);
        assert_eq!(wallet_config.compaction_threshold, 12);
        assert_eq!(wallet_config.min_compaction_age_hours, 2);
    }

    #[test]
    fn test_table_config_map_snapshot_config() {
        let config_map = TableConfigMap::default();

        let holdings_config = config_map.get_config(TOKEN_HOLDINGS_TABLE);
        assert_eq!(holdings_config.target_file_size_mb, 128);
        assert_eq!(holdings_config.compression, CompressionStrategy::High);
        assert!(holdings_config.enable_z_ordering);
        assert_eq!(holdings_config.compaction_threshold, 8);
        assert_eq!(holdings_config.min_compaction_age_hours, 6);
    }
}
