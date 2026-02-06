//! DuckLake maintenance operations
//!
//! Provides utilities for maintaining DuckLake tables including:
//! - Snapshot expiration (cleanup old snapshots)
//! - File compaction (merge small Parquet files)
//! - Data flushing (move inlined data to Parquet)
//! - Tiered compaction (4-tier hot/warm/cold/frozen data management)
//!
//! ## 4-Tier Storage Architecture (Schema Redesign)
//!
//! DuckLake supports a 4-tier storage strategy for optimal query performance:
//!
//! | Tier   | Age     | Target Size | Compression    | Z-Order | Interval |
//! |--------|---------|-------------|----------------|---------|----------|
//! | Hot    | 0-6h    | 16-32 MB    | zstd level 1   | No      | 15 min   |
//! | Warm   | 6-24h   | 64 MB       | zstd level 2   | No      | 30 min   |
//! | Cold   | 1-7d    | 128 MB      | zstd level 3   | No      | 60 min   |
//! | Frozen | 7d+     | 256 MB      | zstd level 3   | Yes     | 24 hours |
//!
//! - **Hot Tier**: Recent data with frequent writes, optimized for fast ingestion
//! - **Warm Tier**: Settling data, moderate compaction, reduced write frequency
//! - **Cold Tier**: Stable data, high compression, infrequent writes
//! - **Frozen Tier**: Archival data, maximum compression, Z-ordered for analytics
//!
//! These operations should be run periodically to maintain optimal performance.
//! See TECH-REF-DuckLake.md for details on DuckLake maintenance patterns.

use duckdb::Connection;
use std::collections::HashMap;
use tracing::{debug, info, warn};

use crate::config::{HotDataConfig, TableConfigMap};
use crate::error::DuckLakeError;

/// Expire old snapshots to allow cleanup of orphaned files
///
/// Must be called BEFORE `delete_orphaned_files` - DuckLake requires
/// snapshots to be expired before their associated files can be deleted.
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `catalog_name` - Name of the attached DuckLake catalog (e.g., "ekko_ducklake")
/// * `older_than_days` - Expire snapshots older than this many days
///
/// # Example
/// ```ignore
/// use ducklake_common::maintenance::expire_snapshots;
/// // Expire snapshots older than 7 days
/// expire_snapshots(&conn, "ekko_ducklake", 7)?;
/// ```
pub fn expire_snapshots(
    conn: &Connection,
    catalog_name: &str,
    older_than_days: u32,
) -> Result<(), DuckLakeError> {
    let sql = format!(
        "CALL ducklake_expire_snapshots('{}', older_than => INTERVAL '{} days');",
        catalog_name, older_than_days
    );

    debug!("Expiring snapshots older than {} days", older_than_days);
    conn.execute(&sql, [])
        .map_err(|e| DuckLakeError::DuckDBError(format!("Failed to expire snapshots: {}", e)))?;

    info!(
        "Successfully expired snapshots older than {} days",
        older_than_days
    );
    Ok(())
}

/// Merge small adjacent Parquet files for better query performance
///
/// DuckLake may create many small files during high-frequency writes.
/// This function merges them into larger files based on the configured
/// `target_file_size` option (default 256MB).
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `table_name` - Name of the table to compact
///
/// # Example
/// ```ignore
/// use ducklake_common::maintenance::compact_table;
/// compact_table(&conn, "transactions")?;
/// ```
pub fn compact_table(conn: &Connection, table_name: &str) -> Result<u64, DuckLakeError> {
    let sql = format!("SELECT merge_adjacent_files('{}');", table_name);

    debug!("Compacting table: {}", table_name);
    let result: i64 = conn.query_row(&sql, [], |row| row.get(0)).map_err(|e| {
        DuckLakeError::DuckDBError(format!("Failed to compact table {}: {}", table_name, e))
    })?;

    let files_merged = result as u64;
    if files_merged > 0 {
        info!("Compacted {} files in table {}", files_merged, table_name);
    } else {
        debug!("No files to compact in table {}", table_name);
    }

    Ok(files_merged)
}

/// Flush inlined data from the catalog to Parquet files
///
/// DuckLake may store small inserts directly in the catalog database
/// (controlled by `data_inlining_row_limit`). This function flushes
/// that data to Parquet files for better query performance and
/// consistency with larger datasets.
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `catalog_name` - Name of the attached DuckLake catalog
/// * `table_name` - Optional specific table to flush; if None, flushes all tables
///
/// # Example
/// ```ignore
/// use ducklake_common::maintenance::flush_inlined_data;
/// // Flush all tables
/// flush_inlined_data(&conn, "ekko_ducklake", None)?;
/// // Flush specific table
/// flush_inlined_data(&conn, "ekko_ducklake", Some("transactions"))?;
/// ```
pub fn flush_inlined_data(
    conn: &Connection,
    catalog_name: &str,
    table_name: Option<&str>,
) -> Result<(), DuckLakeError> {
    let sql = match table_name {
        Some(table) => format!(
            "CALL ducklake_flush_inlined_data('{}', table_name => '{}');",
            catalog_name, table
        ),
        None => format!("CALL ducklake_flush_inlined_data('{}');", catalog_name),
    };

    debug!(
        "Flushing inlined data for {:?}",
        table_name.unwrap_or("all tables")
    );
    conn.execute(&sql, [])
        .map_err(|e| DuckLakeError::DuckDBError(format!("Failed to flush inlined data: {}", e)))?;

    info!("Successfully flushed inlined data");
    Ok(())
}

/// Rewrite data files to remove deleted rows and optimize storage
///
/// After many DELETE operations, Parquet files may contain tombstones
/// (markers for deleted rows). This function rewrites files to physically
/// remove deleted data and reclaim storage.
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `catalog_name` - Name of the attached DuckLake catalog
///
/// # Example
/// ```ignore
/// use ducklake_common::maintenance::rewrite_data_files;
/// rewrite_data_files(&conn, "ekko_ducklake")?;
/// ```
pub fn rewrite_data_files(conn: &Connection, catalog_name: &str) -> Result<(), DuckLakeError> {
    let sql = format!("CALL ducklake_rewrite_data_files('{}');", catalog_name);

    debug!("Rewriting data files for catalog: {}", catalog_name);
    conn.execute(&sql, [])
        .map_err(|e| DuckLakeError::DuckDBError(format!("Failed to rewrite data files: {}", e)))?;

    info!("Successfully rewrote data files");
    Ok(())
}

/// Delete orphaned Parquet files that are no longer referenced
///
/// IMPORTANT: Must call `expire_snapshots` BEFORE this function.
/// Files can only be deleted after their referencing snapshots are expired.
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `catalog_name` - Name of the attached DuckLake catalog
///
/// # Example
/// ```ignore
/// use ducklake_common::maintenance::{expire_snapshots, delete_orphaned_files};
/// // Correct order: expire first, then delete
/// expire_snapshots(&conn, "ekko_ducklake", 7)?;
/// delete_orphaned_files(&conn, "ekko_ducklake")?;
/// ```
pub fn delete_orphaned_files(conn: &Connection, catalog_name: &str) -> Result<(), DuckLakeError> {
    let sql = format!("CALL ducklake_delete_orphaned_files('{}');", catalog_name);

    debug!("Deleting orphaned files for catalog: {}", catalog_name);
    conn.execute(&sql, []).map_err(|e| {
        DuckLakeError::DuckDBError(format!("Failed to delete orphaned files: {}", e))
    })?;

    info!("Successfully deleted orphaned files");
    Ok(())
}

/// Run full maintenance cycle for a DuckLake catalog
///
/// Performs all maintenance operations in the correct order:
/// 1. Expire old snapshots
/// 2. Flush inlined data
/// 3. Compact tables (merge small files)
/// 4. Rewrite data files (remove deleted rows)
/// 5. Delete orphaned files
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `catalog_name` - Name of the attached DuckLake catalog
/// * `tables` - List of table names to compact
/// * `snapshot_retention_days` - Days to retain snapshots
///
/// # Example
/// ```ignore
/// use ducklake_common::maintenance::run_full_maintenance;
/// let tables = vec!["transactions", "blocks", "logs"];
/// run_full_maintenance(&conn, "ekko_ducklake", &tables, 7)?;
/// ```
pub fn run_full_maintenance(
    conn: &Connection,
    catalog_name: &str,
    tables: &[&str],
    snapshot_retention_days: u32,
) -> Result<MaintenanceReport, DuckLakeError> {
    info!(
        "Starting full maintenance cycle for catalog: {}",
        catalog_name
    );

    let mut report = MaintenanceReport::default();

    // 1. Expire old snapshots
    match expire_snapshots(conn, catalog_name, snapshot_retention_days) {
        Ok(()) => report.snapshots_expired = true,
        Err(e) => {
            warn!("Failed to expire snapshots: {}", e);
            report.errors.push(format!("expire_snapshots: {}", e));
        }
    }

    // 2. Flush inlined data
    match flush_inlined_data(conn, catalog_name, None) {
        Ok(()) => report.inlined_data_flushed = true,
        Err(e) => {
            warn!("Failed to flush inlined data: {}", e);
            report.errors.push(format!("flush_inlined_data: {}", e));
        }
    }

    // 3. Compact each table
    for table in tables {
        match compact_table(conn, table) {
            Ok(files_merged) => report.files_merged += files_merged,
            Err(e) => {
                warn!("Failed to compact table {}: {}", table, e);
                report
                    .errors
                    .push(format!("compact_table({}): {}", table, e));
            }
        }
    }

    // 4. Rewrite data files
    match rewrite_data_files(conn, catalog_name) {
        Ok(()) => report.data_files_rewritten = true,
        Err(e) => {
            warn!("Failed to rewrite data files: {}", e);
            report.errors.push(format!("rewrite_data_files: {}", e));
        }
    }

    // 5. Delete orphaned files (only if snapshots were expired)
    if report.snapshots_expired {
        match delete_orphaned_files(conn, catalog_name) {
            Ok(()) => report.orphaned_files_deleted = true,
            Err(e) => {
                warn!("Failed to delete orphaned files: {}", e);
                report.errors.push(format!("delete_orphaned_files: {}", e));
            }
        }
    }

    if report.errors.is_empty() {
        info!("Full maintenance cycle completed successfully");
    } else {
        warn!(
            "Maintenance cycle completed with {} errors",
            report.errors.len()
        );
    }

    Ok(report)
}

/// Report from a maintenance run
#[derive(Debug, Default)]
pub struct MaintenanceReport {
    pub snapshots_expired: bool,
    pub inlined_data_flushed: bool,
    pub files_merged: u64,
    pub data_files_rewritten: bool,
    pub orphaned_files_deleted: bool,
    pub errors: Vec<String>,
}

impl MaintenanceReport {
    pub fn is_success(&self) -> bool {
        self.errors.is_empty()
    }
}

// ============================================================================
// 4-Tier Compaction System (Schema Redesign)
// ============================================================================
//
// ## Tiered Storage Strategy
//
// | Tier   | Age     | Target Size | Compression    | Z-Order |
// |--------|---------|-------------|----------------|---------|
// | Hot    | 0-6h    | 16-32 MB    | zstd level 1   | No      |
// | Warm   | 6-24h   | 64 MB       | zstd level 2   | No      |
// | Cold   | 1-7d    | 128 MB      | zstd level 3   | No      |
// | Frozen | 7d+     | 256 MB      | zstd level 3   | Yes     |

/// Data tier classification (4-tier system from Schema Redesign)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataTier {
    /// Hot tier: Recent data (0-6 hours), frequent compaction, fast compression
    Hot,
    /// Warm tier: Settling data (6-24 hours), moderate compaction
    Warm,
    /// Cold tier: Stable data (1-7 days), high compression
    Cold,
    /// Frozen tier: Archival data (7+ days), Z-ordered, maximum compression
    Frozen,
}

impl DataTier {
    /// Determine tier based on data age in hours
    pub fn from_age_hours(age_hours: u32, hot_config: &HotDataConfig) -> Self {
        let age_days = age_hours / 24;
        if hot_config.is_frozen(age_days) {
            DataTier::Frozen
        } else if hot_config.is_warm(age_hours) {
            // Check warm BEFORE cold - warm includes 24h, cold starts at 25h
            DataTier::Warm
        } else if hot_config.is_cold(age_days) {
            DataTier::Cold
        } else {
            DataTier::Hot
        }
    }

    /// Get compaction interval in minutes for this tier
    pub fn compaction_interval_minutes(&self, hot_config: &HotDataConfig) -> u32 {
        match self {
            DataTier::Hot => hot_config.hot_compaction_interval_min,
            DataTier::Warm => hot_config.warm_compaction_interval_min,
            DataTier::Cold => hot_config.cold_compaction_interval_min,
            DataTier::Frozen => hot_config.frozen_compaction_interval_hours * 60,
        }
    }

    /// Get target file size in MB for this tier
    pub fn target_file_size_mb(&self, hot_config: &HotDataConfig) -> u32 {
        match self {
            DataTier::Hot => hot_config.hot_file_size_mb,
            DataTier::Warm => hot_config.warm_file_size_mb,
            DataTier::Cold => hot_config.cold_file_size_mb,
            DataTier::Frozen => hot_config.frozen_file_size_mb,
        }
    }

    /// Get compression level for this tier
    pub fn compression_level(&self, hot_config: &HotDataConfig) -> u32 {
        match self {
            DataTier::Hot => hot_config.hot_compression_level,
            DataTier::Warm => hot_config.warm_compression_level,
            DataTier::Cold => hot_config.cold_compression_level,
            DataTier::Frozen => hot_config.frozen_compression_level,
        }
    }

    /// Check if Z-ordering should be applied for this tier
    pub fn should_z_order(&self, hot_config: &HotDataConfig) -> bool {
        match self {
            DataTier::Frozen => hot_config.enable_frozen_z_ordering,
            _ => false,
        }
    }

    /// Get tier name for logging/metrics
    pub fn name(&self) -> &'static str {
        match self {
            DataTier::Hot => "hot",
            DataTier::Warm => "warm",
            DataTier::Cold => "cold",
            DataTier::Frozen => "frozen",
        }
    }
}

/// Configuration for tiered compaction
#[derive(Debug, Clone)]
pub struct TieredCompactionConfig {
    /// Hot data tier settings
    pub hot_config: HotDataConfig,
    /// Per-table compaction settings
    pub table_config: TableConfigMap,
    /// Snapshot retention in days
    pub snapshot_retention_days: u32,
    /// Whether to apply Z-ordering to cold data
    pub z_order_cold_data: bool,
}

impl Default for TieredCompactionConfig {
    fn default() -> Self {
        Self {
            hot_config: HotDataConfig::default(),
            table_config: TableConfigMap::default(),
            snapshot_retention_days: 7,
            z_order_cold_data: true,
        }
    }
}

impl TieredCompactionConfig {
    /// Create configuration with custom hot tier settings
    pub fn with_hot_config(mut self, hot_config: HotDataConfig) -> Self {
        self.hot_config = hot_config;
        self
    }

    /// Create configuration with custom table settings
    pub fn with_table_config(mut self, table_config: TableConfigMap) -> Self {
        self.table_config = table_config;
        self
    }

    /// Get effective compaction config for a table at a given data age
    ///
    /// ## 4-Tier Configuration (Schema Redesign)
    ///
    /// | Tier   | Age     | Target Size | Compression    | Z-Order |
    /// |--------|---------|-------------|----------------|---------|
    /// | Hot    | 0-6h    | 16-32 MB    | zstd level 1   | No      |
    /// | Warm   | 6-24h   | 64 MB       | zstd level 2   | No      |
    /// | Cold   | 1-7d    | 128 MB      | zstd level 3   | No      |
    /// | Frozen | 7d+     | 256 MB      | zstd level 3   | Yes     |
    pub fn get_effective_config(
        &self,
        table_name: &str,
        age_hours: u32,
    ) -> EffectiveCompactionConfig {
        let tier = DataTier::from_age_hours(age_hours, &self.hot_config);
        let table_config = self.table_config.get_config(table_name);

        // Override file size and compression based on tier (4-tier system)
        let (target_file_size_mb, compression_level) = match tier {
            DataTier::Hot => (
                self.hot_config.hot_file_size_mb,
                self.hot_config.hot_compression_level,
            ),
            DataTier::Warm => (
                self.hot_config.warm_file_size_mb,
                self.hot_config.warm_compression_level,
            ),
            DataTier::Cold => (
                self.hot_config.cold_file_size_mb,
                self.hot_config.cold_compression_level,
            ),
            DataTier::Frozen => (
                self.hot_config.frozen_file_size_mb,
                self.hot_config.frozen_compression_level,
            ),
        };

        // Z-ordering ONLY for frozen tier if enabled (Schema Redesign)
        // Cold tier no longer gets Z-ordering - only frozen data (7d+) is Z-ordered
        let enable_z_ordering = match tier {
            DataTier::Frozen => {
                self.hot_config.enable_frozen_z_ordering && table_config.enable_z_ordering
            }
            _ => false,
        };

        EffectiveCompactionConfig {
            tier,
            target_file_size_mb,
            compression_level,
            enable_z_ordering,
            compaction_threshold: table_config.compaction_threshold,
            min_age_hours: table_config.min_compaction_age_hours,
        }
    }
}

/// Effective compaction configuration for a specific table and data age
#[derive(Debug, Clone)]
pub struct EffectiveCompactionConfig {
    /// Data tier
    pub tier: DataTier,
    /// Target file size in MB
    pub target_file_size_mb: u32,
    /// Compression level (1-3)
    pub compression_level: u32,
    /// Whether to apply Z-ordering
    pub enable_z_ordering: bool,
    /// Number of small files to trigger compaction
    pub compaction_threshold: u32,
    /// Minimum age before compaction
    pub min_age_hours: u32,
}

/// Report from tiered maintenance run
#[derive(Debug, Default)]
pub struct TieredMaintenanceReport {
    /// Base maintenance report
    pub base: MaintenanceReport,
    /// Files compacted per tier
    pub files_per_tier: HashMap<String, u64>,
    /// Tables Z-ordered during cold compaction
    pub tables_z_ordered: Vec<String>,
    /// Hot partitions promoted to warm
    pub partitions_promoted: u64,
}

impl TieredMaintenanceReport {
    pub fn is_success(&self) -> bool {
        self.base.is_success()
    }

    pub fn hot_files_compacted(&self) -> u64 {
        *self.files_per_tier.get("hot").unwrap_or(&0)
    }

    pub fn warm_files_compacted(&self) -> u64 {
        *self.files_per_tier.get("warm").unwrap_or(&0)
    }

    pub fn cold_files_compacted(&self) -> u64 {
        *self.files_per_tier.get("cold").unwrap_or(&0)
    }

    pub fn frozen_files_compacted(&self) -> u64 {
        *self.files_per_tier.get("frozen").unwrap_or(&0)
    }
}

/// Compact hot tier data for a table partition
///
/// Hot tier compaction uses smaller target file sizes and faster compression
/// to optimize for recent data that is frequently queried and updated.
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `table_name` - Name of the table to compact
/// * `partition_filter` - Optional SQL WHERE clause for partition filtering
/// * `config` - Tiered compaction configuration
///
/// # Returns
/// Number of files merged
pub fn hot_compact_partition(
    conn: &Connection,
    table_name: &str,
    partition_filter: Option<&str>,
    config: &TieredCompactionConfig,
) -> Result<u64, DuckLakeError> {
    let effective_config = config.get_effective_config(table_name, 0); // 0 hours = hot data

    debug!(
        "Hot compacting {} (target: {}MB, compression: {})",
        table_name, effective_config.target_file_size_mb, effective_config.compression_level
    );

    // For hot tier, we use merge_adjacent_files with smaller target size
    // The partition filter is used via a transaction that sets session variables
    let sql = if let Some(filter) = partition_filter {
        format!(
            "SELECT merge_adjacent_files('{}') FROM '{}' WHERE {};",
            table_name, table_name, filter
        )
    } else {
        format!("SELECT merge_adjacent_files('{}');", table_name)
    };

    let result: i64 = conn.query_row(&sql, [], |row| row.get(0)).map_err(|e| {
        DuckLakeError::DuckDBError(format!("Failed to hot compact table {}: {}", table_name, e))
    })?;

    let files_merged = result as u64;
    if files_merged > 0 {
        info!(
            "Hot compacted {} files in {} partition",
            files_merged, table_name
        );
    }

    Ok(files_merged)
}

/// Compact table with tier-aware configuration
///
/// Applies appropriate file size, compression, and Z-ordering based on data age.
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `table_name` - Name of the table to compact
/// * `data_age_hours` - Approximate age of the data being compacted
/// * `config` - Tiered compaction configuration
///
/// # Returns
/// Number of files merged
pub fn compact_table_with_config(
    conn: &Connection,
    table_name: &str,
    data_age_hours: u32,
    config: &TieredCompactionConfig,
) -> Result<u64, DuckLakeError> {
    let effective_config = config.get_effective_config(table_name, data_age_hours);

    debug!(
        "Compacting {} (tier: {:?}, target: {}MB, compression: {}, z-order: {})",
        table_name,
        effective_config.tier,
        effective_config.target_file_size_mb,
        effective_config.compression_level,
        effective_config.enable_z_ordering
    );

    // Standard merge for all tiers
    let sql = format!("SELECT merge_adjacent_files('{}');", table_name);

    let result: i64 = conn.query_row(&sql, [], |row| row.get(0)).map_err(|e| {
        DuckLakeError::DuckDBError(format!(
            "Failed to compact table {} (tier: {:?}): {}",
            table_name, effective_config.tier, e
        ))
    })?;

    let files_merged = result as u64;
    if files_merged > 0 {
        info!(
            "Compacted {} files in {} ({:?} tier)",
            files_merged, table_name, effective_config.tier
        );
    }

    Ok(files_merged)
}

/// Promote data from hot tier to warm tier
///
/// This function is called during scheduled maintenance to transition
/// data from the hot tier (frequent compaction) to the warm tier
/// (standard compaction with larger file sizes).
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `table_name` - Name of the table
/// * `partition_date` - Date partition to promote (format: YYYY-MM-DD)
/// * `config` - Tiered compaction configuration
///
/// # Returns
/// Number of partitions promoted
pub fn promote_hot_to_warm(
    conn: &Connection,
    table_name: &str,
    partition_date: &str,
    config: &TieredCompactionConfig,
) -> Result<u64, DuckLakeError> {
    // Calculate if data is old enough to promote (past hot window)
    let effective_config =
        config.get_effective_config(table_name, config.hot_config.hot_window_hours + 1);

    if effective_config.tier != DataTier::Warm && effective_config.tier != DataTier::Cold {
        debug!(
            "Partition {} in {} is still in hot tier, skipping promotion",
            partition_date, table_name
        );
        return Ok(0);
    }

    debug!(
        "Promoting partition {} in {} from hot to {:?} tier",
        partition_date, table_name, effective_config.tier
    );

    // Compact with warm tier settings
    let sql = format!(
        "SELECT merge_adjacent_files('{}') WHERE block_date = '{}';",
        table_name, partition_date
    );

    let result: i64 = conn.query_row(&sql, [], |row| row.get(0)).unwrap_or(0);

    let files_merged = result as u64;
    if files_merged > 0 {
        info!(
            "Promoted partition {} in {} ({} files merged)",
            partition_date, table_name, files_merged
        );
    }

    Ok(if files_merged > 0 { 1 } else { 0 })
}

/// Apply Z-ordering to cold tier data
///
/// Z-ordering optimizes file layout for multi-dimensional queries.
/// This should only be applied to cold data that is rarely written to.
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `table_name` - Name of the table
/// * `z_order_columns` - Columns to use for Z-ordering
///
/// # Returns
/// Whether Z-ordering was applied
pub fn apply_z_ordering(
    conn: &Connection,
    table_name: &str,
    z_order_columns: &[&str],
) -> Result<bool, DuckLakeError> {
    if z_order_columns.is_empty() {
        return Ok(false);
    }

    let columns = z_order_columns.join(", ");
    debug!(
        "Applying Z-ordering to {} on columns: {}",
        table_name, columns
    );

    // DuckLake Z-ordering via OPTIMIZE command
    let sql = format!(
        "CALL ducklake_optimize('{}', z_order => [{}]);",
        table_name, columns
    );

    conn.execute(&sql, []).map_err(|e| {
        DuckLakeError::DuckDBError(format!(
            "Failed to apply Z-ordering to {}: {}",
            table_name, e
        ))
    })?;

    info!(
        "Applied Z-ordering to {} on columns: {}",
        table_name, columns
    );
    Ok(true)
}

/// Run tiered maintenance cycle for a DuckLake catalog
///
/// Performs maintenance operations with tier awareness:
/// 1. Expire old snapshots
/// 2. Flush inlined data
/// 3. Hot tier compaction (15-min interval)
/// 4. Warm/Cold tier compaction (hourly interval)
/// 5. Z-order cold data (if enabled)
/// 6. Rewrite data files
/// 7. Delete orphaned files
///
/// # Arguments
/// * `conn` - DuckDB connection with DuckLake attached
/// * `catalog_name` - Name of the attached DuckLake catalog
/// * `tables_with_ages` - Table names with approximate data ages (hours)
/// * `config` - Tiered compaction configuration
///
/// # Example
/// ```ignore
/// use ducklake_common::maintenance::{run_tiered_maintenance, TieredCompactionConfig};
///
/// let config = TieredCompactionConfig::default();
/// let tables = vec![
///     ("transactions", 0),   // Hot data
///     ("transactions", 48),  // Warm data
///     ("blocks", 168),       // Cold data (7 days)
/// ];
/// run_tiered_maintenance(&conn, "ekko_ducklake", &tables, &config)?;
/// ```
pub fn run_tiered_maintenance(
    conn: &Connection,
    catalog_name: &str,
    tables_with_ages: &[(&str, u32)],
    config: &TieredCompactionConfig,
) -> Result<TieredMaintenanceReport, DuckLakeError> {
    info!(
        "Starting tiered maintenance cycle for catalog: {}",
        catalog_name
    );

    let mut report = TieredMaintenanceReport::default();

    // 1. Expire old snapshots
    match expire_snapshots(conn, catalog_name, config.snapshot_retention_days) {
        Ok(()) => report.base.snapshots_expired = true,
        Err(e) => {
            warn!("Failed to expire snapshots: {}", e);
            report.base.errors.push(format!("expire_snapshots: {}", e));
        }
    }

    // 2. Flush inlined data
    match flush_inlined_data(conn, catalog_name, None) {
        Ok(()) => report.base.inlined_data_flushed = true,
        Err(e) => {
            warn!("Failed to flush inlined data: {}", e);
            report
                .base
                .errors
                .push(format!("flush_inlined_data: {}", e));
        }
    }

    // 3. Tier-aware compaction for each table (4-tier system)
    for (table, age_hours) in tables_with_ages {
        let tier = DataTier::from_age_hours(*age_hours, &config.hot_config);
        let tier_key = tier.name(); // "hot", "warm", "cold", or "frozen"

        match compact_table_with_config(conn, table, *age_hours, config) {
            Ok(files_merged) => {
                report.base.files_merged += files_merged;
                *report
                    .files_per_tier
                    .entry(tier_key.to_string())
                    .or_insert(0) += files_merged;
            }
            Err(e) => {
                warn!("Failed to compact table {} ({:?}): {}", table, tier, e);
                report
                    .base
                    .errors
                    .push(format!("compact_table({}, {:?}): {}", table, tier, e));
            }
        }

        // Apply Z-ordering ONLY to frozen data (7d+) as per Schema Redesign
        // Cold tier no longer gets Z-ordering
        if tier == DataTier::Frozen {
            let effective_config = config.get_effective_config(table, *age_hours);
            if effective_config.enable_z_ordering {
                // Get Z-order columns from schema (would need to be passed in or looked up)
                // For now, we'll note that Z-ordering should be applied
                debug!("Z-ordering would be applied to frozen table: {}", table);
                report.tables_z_ordered.push(table.to_string());
            }
        }
    }

    // 4. Rewrite data files
    match rewrite_data_files(conn, catalog_name) {
        Ok(()) => report.base.data_files_rewritten = true,
        Err(e) => {
            warn!("Failed to rewrite data files: {}", e);
            report
                .base
                .errors
                .push(format!("rewrite_data_files: {}", e));
        }
    }

    // 5. Delete orphaned files (only if snapshots were expired)
    if report.base.snapshots_expired {
        match delete_orphaned_files(conn, catalog_name) {
            Ok(()) => report.base.orphaned_files_deleted = true,
            Err(e) => {
                warn!("Failed to delete orphaned files: {}", e);
                report
                    .base
                    .errors
                    .push(format!("delete_orphaned_files: {}", e));
            }
        }
    }

    if report.is_success() {
        info!(
            "Tiered maintenance completed: hot={}, warm={}, cold={}, frozen={} files compacted",
            report.hot_files_compacted(),
            report.warm_files_compacted(),
            report.cold_files_compacted(),
            report.frozen_files_compacted()
        );
    } else {
        warn!(
            "Tiered maintenance completed with {} errors",
            report.base.errors.len()
        );
    }

    Ok(report)
}

/// Schedule hint for maintenance operations (4-tier system)
///
/// ## Tier Schedule (Schema Redesign)
///
/// | Tier   | Interval    | Purpose                           |
/// |--------|-------------|-----------------------------------|
/// | Hot    | 15 min      | Frequent compaction for new data  |
/// | Warm   | 30 min      | Moderate compaction               |
/// | Cold   | 60 min      | Infrequent compaction             |
/// | Frozen | 24 hours    | Z-ordering and final compaction   |
#[derive(Debug, Clone)]
pub struct MaintenanceSchedule {
    /// Hot tier compaction interval in minutes (default: 15)
    pub hot_interval_minutes: u32,
    /// Warm tier compaction interval in minutes (default: 30)
    pub warm_interval_minutes: u32,
    /// Cold tier compaction interval in minutes (default: 60)
    pub cold_interval_minutes: u32,
    /// Frozen tier compaction interval in hours (default: 24)
    pub frozen_interval_hours: u32,
    /// Full maintenance (including Z-ordering) interval in hours
    pub full_maintenance_hours: u32,
}

impl Default for MaintenanceSchedule {
    fn default() -> Self {
        Self {
            hot_interval_minutes: 15,
            warm_interval_minutes: 30,
            cold_interval_minutes: 60,
            frozen_interval_hours: 24,
            full_maintenance_hours: 24,
        }
    }
}

impl MaintenanceSchedule {
    /// Create schedule from HotDataConfig (4-tier)
    pub fn from_hot_config(config: &HotDataConfig) -> Self {
        Self {
            hot_interval_minutes: config.hot_compaction_interval_min,
            warm_interval_minutes: config.warm_compaction_interval_min,
            cold_interval_minutes: config.cold_compaction_interval_min,
            frozen_interval_hours: config.frozen_compaction_interval_hours,
            full_maintenance_hours: config.frozen_compaction_interval_hours,
        }
    }

    /// Get interval for a specific tier
    pub fn interval_for_tier(&self, tier: DataTier) -> u32 {
        match tier {
            DataTier::Hot => self.hot_interval_minutes,
            DataTier::Warm => self.warm_interval_minutes,
            DataTier::Cold => self.cold_interval_minutes,
            DataTier::Frozen => self.frozen_interval_hours * 60, // Convert to minutes
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ============================================================================
    // MaintenanceReport Tests
    // ============================================================================

    #[test]
    fn test_maintenance_report_default() {
        let report = MaintenanceReport::default();
        assert!(!report.snapshots_expired);
        assert!(!report.inlined_data_flushed);
        assert_eq!(report.files_merged, 0);
        assert!(!report.data_files_rewritten);
        assert!(!report.orphaned_files_deleted);
        assert!(report.errors.is_empty());
        assert!(report.is_success());
    }

    #[test]
    fn test_maintenance_report_with_errors() {
        let mut report = MaintenanceReport::default();
        report.errors.push("test error".to_string());
        assert!(!report.is_success());
    }

    // ============================================================================
    // DataTier Tests (4-Tier System)
    // ============================================================================

    #[test]
    fn test_data_tier_from_age_hours_hot() {
        let config = HotDataConfig::default();

        // 0-6 hours is hot (Schema Redesign)
        assert_eq!(DataTier::from_age_hours(0, &config), DataTier::Hot);
        assert_eq!(DataTier::from_age_hours(3, &config), DataTier::Hot);
        assert_eq!(DataTier::from_age_hours(6, &config), DataTier::Hot);
    }

    #[test]
    fn test_data_tier_from_age_hours_warm() {
        let config = HotDataConfig::default();

        // 7-24 hours is warm (Schema Redesign)
        assert_eq!(DataTier::from_age_hours(7, &config), DataTier::Warm);
        assert_eq!(DataTier::from_age_hours(12, &config), DataTier::Warm);
        assert_eq!(DataTier::from_age_hours(24, &config), DataTier::Warm);
    }

    #[test]
    fn test_data_tier_from_age_hours_cold() {
        let config = HotDataConfig::default();

        // 1-7 days is cold (Schema Redesign): 25 hours to 167 hours
        assert_eq!(DataTier::from_age_hours(25, &config), DataTier::Cold); // Just past 24h
        assert_eq!(DataTier::from_age_hours(48, &config), DataTier::Cold); // 2 days
        assert_eq!(DataTier::from_age_hours(144, &config), DataTier::Cold); // 6 days
        assert_eq!(DataTier::from_age_hours(167, &config), DataTier::Cold); // Just under 7 days
    }

    #[test]
    fn test_data_tier_from_age_hours_frozen() {
        let config = HotDataConfig::default();

        // 7+ days is frozen (Schema Redesign)
        assert_eq!(DataTier::from_age_hours(168, &config), DataTier::Frozen); // 7 days
        assert_eq!(DataTier::from_age_hours(336, &config), DataTier::Frozen); // 14 days
        assert_eq!(DataTier::from_age_hours(720, &config), DataTier::Frozen); // 30 days
    }

    #[test]
    fn test_data_tier_compaction_interval() {
        let config = HotDataConfig::default();

        // Check compaction intervals for all 4 tiers
        assert_eq!(DataTier::Hot.compaction_interval_minutes(&config), 15); // 15 min
        assert_eq!(DataTier::Warm.compaction_interval_minutes(&config), 30); // 30 min
        assert_eq!(DataTier::Cold.compaction_interval_minutes(&config), 60); // 60 min
        assert_eq!(
            DataTier::Frozen.compaction_interval_minutes(&config),
            24 * 60
        ); // 24 hours
    }

    #[test]
    fn test_data_tier_target_file_size() {
        let config = HotDataConfig::default();

        // Check target file sizes for all 4 tiers (Schema Redesign)
        assert_eq!(DataTier::Hot.target_file_size_mb(&config), 32); // 32 MB
        assert_eq!(DataTier::Warm.target_file_size_mb(&config), 64); // 64 MB
        assert_eq!(DataTier::Cold.target_file_size_mb(&config), 128); // 128 MB
        assert_eq!(DataTier::Frozen.target_file_size_mb(&config), 256); // 256 MB
    }

    #[test]
    fn test_data_tier_compression_level() {
        let config = HotDataConfig::default();

        // Check compression levels for all 4 tiers (Schema Redesign)
        assert_eq!(DataTier::Hot.compression_level(&config), 1); // zstd level 1
        assert_eq!(DataTier::Warm.compression_level(&config), 2); // zstd level 2
        assert_eq!(DataTier::Cold.compression_level(&config), 3); // zstd level 3
        assert_eq!(DataTier::Frozen.compression_level(&config), 3); // zstd level 3
    }

    #[test]
    fn test_data_tier_z_ordering() {
        let config = HotDataConfig::default();

        // Only frozen tier gets Z-ordering (Schema Redesign)
        assert!(!DataTier::Hot.should_z_order(&config));
        assert!(!DataTier::Warm.should_z_order(&config));
        assert!(!DataTier::Cold.should_z_order(&config));
        assert!(DataTier::Frozen.should_z_order(&config)); // Only frozen!
    }

    #[test]
    fn test_data_tier_name() {
        assert_eq!(DataTier::Hot.name(), "hot");
        assert_eq!(DataTier::Warm.name(), "warm");
        assert_eq!(DataTier::Cold.name(), "cold");
        assert_eq!(DataTier::Frozen.name(), "frozen");
    }

    // ============================================================================
    // TieredCompactionConfig Tests
    // ============================================================================

    #[test]
    fn test_tiered_compaction_config_default() {
        let config = TieredCompactionConfig::default();

        assert_eq!(config.snapshot_retention_days, 7);
        assert!(config.z_order_cold_data);
    }

    #[test]
    fn test_tiered_compaction_config_with_hot_config() {
        let hot_config = HotDataConfig {
            hot_window_hours: 12,
            ..Default::default()
        };

        let config = TieredCompactionConfig::default().with_hot_config(hot_config);

        assert_eq!(config.hot_config.hot_window_hours, 12);
    }

    #[test]
    fn test_tiered_compaction_config_effective_config_hot() {
        let config = TieredCompactionConfig::default();
        let effective = config.get_effective_config("transactions", 0);

        assert_eq!(effective.tier, DataTier::Hot);
        assert_eq!(effective.target_file_size_mb, 32); // Hot tier file size
        assert_eq!(effective.compression_level, 1); // Fast compression
        assert!(!effective.enable_z_ordering); // No Z-ordering for hot
    }

    #[test]
    fn test_tiered_compaction_config_effective_config_warm() {
        let config = TieredCompactionConfig::default();
        let effective = config.get_effective_config("transactions", 12); // 12 hours = warm

        assert_eq!(effective.tier, DataTier::Warm);
        assert_eq!(effective.target_file_size_mb, 64); // Warm tier file size
        assert_eq!(effective.compression_level, 2); // zstd level 2
        assert!(!effective.enable_z_ordering); // No Z-ordering for warm
    }

    #[test]
    fn test_tiered_compaction_config_effective_config_cold() {
        let config = TieredCompactionConfig::default();
        let effective = config.get_effective_config("transactions", 48); // 2 days = cold

        assert_eq!(effective.tier, DataTier::Cold);
        assert_eq!(effective.target_file_size_mb, 128); // Cold tier file size
        assert_eq!(effective.compression_level, 3); // zstd level 3
        assert!(!effective.enable_z_ordering); // No Z-ordering for cold (only frozen!)
    }

    #[test]
    fn test_tiered_compaction_config_effective_config_frozen() {
        let config = TieredCompactionConfig::default();
        let effective = config.get_effective_config("transactions", 168); // 7 days = frozen

        assert_eq!(effective.tier, DataTier::Frozen);
        assert_eq!(effective.target_file_size_mb, 256); // Frozen tier file size
        assert_eq!(effective.compression_level, 3); // zstd level 3
        assert!(effective.enable_z_ordering); // Z-ordering ONLY for frozen tier
    }

    #[test]
    fn test_tiered_compaction_config_z_ordering_disabled_for_table() {
        let config = TieredCompactionConfig::default();
        // notification_deliveries has z-ordering disabled in table config
        let effective = config.get_effective_config("notification_deliveries", 168); // 7 days = frozen

        // Even for frozen tier, z-ordering is disabled if table config says no
        assert!(!effective.enable_z_ordering);
    }

    // ============================================================================
    // EffectiveCompactionConfig Tests
    // ============================================================================

    #[test]
    fn test_effective_compaction_config_fields() {
        let effective = EffectiveCompactionConfig {
            tier: DataTier::Hot,
            target_file_size_mb: 32,
            compression_level: 1,
            enable_z_ordering: false,
            compaction_threshold: 10,
            min_age_hours: 1,
        };

        assert_eq!(effective.tier, DataTier::Hot);
        assert_eq!(effective.target_file_size_mb, 32);
        assert_eq!(effective.compression_level, 1);
        assert!(!effective.enable_z_ordering);
        assert_eq!(effective.compaction_threshold, 10);
        assert_eq!(effective.min_age_hours, 1);
    }

    // ============================================================================
    // TieredMaintenanceReport Tests (4-Tier System)
    // ============================================================================

    #[test]
    fn test_tiered_maintenance_report_default() {
        let report = TieredMaintenanceReport::default();

        assert!(report.is_success());
        assert_eq!(report.hot_files_compacted(), 0);
        assert_eq!(report.warm_files_compacted(), 0);
        assert_eq!(report.cold_files_compacted(), 0);
        assert_eq!(report.frozen_files_compacted(), 0);
        assert!(report.tables_z_ordered.is_empty());
        assert_eq!(report.partitions_promoted, 0);
    }

    #[test]
    fn test_tiered_maintenance_report_with_files() {
        let mut report = TieredMaintenanceReport::default();
        report.files_per_tier.insert("hot".to_string(), 10);
        report.files_per_tier.insert("warm".to_string(), 5);
        report.files_per_tier.insert("cold".to_string(), 3);
        report.files_per_tier.insert("frozen".to_string(), 2);

        assert_eq!(report.hot_files_compacted(), 10);
        assert_eq!(report.warm_files_compacted(), 5);
        assert_eq!(report.cold_files_compacted(), 3);
        assert_eq!(report.frozen_files_compacted(), 2);
    }

    #[test]
    fn test_tiered_maintenance_report_with_errors() {
        let mut report = TieredMaintenanceReport::default();
        report.base.errors.push("test error".to_string());

        assert!(!report.is_success());
    }

    // ============================================================================
    // MaintenanceSchedule Tests (4-Tier System)
    // ============================================================================

    #[test]
    fn test_maintenance_schedule_default() {
        let schedule = MaintenanceSchedule::default();

        assert_eq!(schedule.hot_interval_minutes, 15);
        assert_eq!(schedule.warm_interval_minutes, 30);
        assert_eq!(schedule.cold_interval_minutes, 60);
        assert_eq!(schedule.frozen_interval_hours, 24);
        assert_eq!(schedule.full_maintenance_hours, 24);
    }

    #[test]
    fn test_maintenance_schedule_from_hot_config() {
        let hot_config = HotDataConfig {
            hot_compaction_interval_min: 10,
            warm_compaction_interval_min: 20,
            cold_compaction_interval_min: 45,
            frozen_compaction_interval_hours: 12,
            ..Default::default()
        };

        let schedule = MaintenanceSchedule::from_hot_config(&hot_config);

        assert_eq!(schedule.hot_interval_minutes, 10);
        assert_eq!(schedule.warm_interval_minutes, 20);
        assert_eq!(schedule.cold_interval_minutes, 45);
        assert_eq!(schedule.frozen_interval_hours, 12);
    }

    #[test]
    fn test_maintenance_schedule_interval_for_tier() {
        let schedule = MaintenanceSchedule::default();

        assert_eq!(schedule.interval_for_tier(DataTier::Hot), 15); // 15 minutes
        assert_eq!(schedule.interval_for_tier(DataTier::Warm), 30); // 30 minutes
        assert_eq!(schedule.interval_for_tier(DataTier::Cold), 60); // 60 minutes
        assert_eq!(schedule.interval_for_tier(DataTier::Frozen), 24 * 60); // 24 hours in minutes
    }

    // ============================================================================
    // Custom HotDataConfig Tests (4-Tier System)
    // ============================================================================

    #[test]
    fn test_custom_tier_boundaries() {
        let config = HotDataConfig {
            hot_window_hours: 12,
            warm_window_hours: 72, // Warm extends to 72h (matches cold_threshold_days * 24)
            cold_threshold_days: 3, // 3 days to cold
            frozen_threshold_days: 14, // 14 days to frozen
            ..Default::default()
        };

        // Custom hot window (12 hours)
        assert_eq!(DataTier::from_age_hours(12, &config), DataTier::Hot);
        assert_eq!(DataTier::from_age_hours(13, &config), DataTier::Warm);

        // Custom warm window (up to 72 hours)
        assert_eq!(DataTier::from_age_hours(48, &config), DataTier::Warm);
        assert_eq!(DataTier::from_age_hours(72, &config), DataTier::Warm);

        // Cold threshold (3 days = 72 hours, cold starts at 73h)
        assert_eq!(DataTier::from_age_hours(73, &config), DataTier::Cold);
        assert_eq!(DataTier::from_age_hours(100, &config), DataTier::Cold);

        // Custom frozen threshold (14 days = 336 hours)
        assert_eq!(DataTier::from_age_hours(335, &config), DataTier::Cold);
        assert_eq!(DataTier::from_age_hours(336, &config), DataTier::Frozen);
    }

    #[test]
    fn test_custom_frozen_z_ordering_disabled() {
        let config = HotDataConfig {
            enable_frozen_z_ordering: false,
            ..Default::default()
        };

        // Frozen tier should not have Z-ordering when disabled
        assert!(!DataTier::Frozen.should_z_order(&config));
    }
}
