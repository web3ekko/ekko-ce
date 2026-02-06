//! Micro-batch buffer system for DuckLake ingestion
//!
//! Implements configurable triggers (time, count, size) for efficient batching
//! with per-table isolation and overflow protection.

use chrono::{DateTime, Utc};
use dashmap::DashMap;
use ducklake_common::error::DuckLakeError;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::mpsc;
use tokio::time::interval;
use tracing::{debug, info, instrument, warn};
use uuid::Uuid;

/// Buffer key combining table and chain_id
pub type BufferKey = String;

/// Micro-batch configuration with configurable triggers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MicroBatchConfig {
    /// Time threshold - flush after this many seconds
    pub time_threshold_seconds: u64,
    /// Count threshold - flush after this many records
    pub count_threshold: u32,
    /// Size threshold - flush after this many MB
    pub size_threshold_mb: u32,
    /// Maximum buffer memory per partition (MB)
    pub max_buffer_memory_mb: u32,
    /// Buffer overflow strategy
    pub buffer_overflow_strategy: OverflowStrategy,
}

impl Default for MicroBatchConfig {
    fn default() -> Self {
        Self {
            time_threshold_seconds: 30,
            count_threshold: 1000,
            size_threshold_mb: 64,
            max_buffer_memory_mb: 256,
            buffer_overflow_strategy: OverflowStrategy::Compress,
        }
    }
}

impl MicroBatchConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        Self {
            time_threshold_seconds: std::env::var("DUCKLAKE_BUFFER_TIME_THRESHOLD_SECONDS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(30),
            count_threshold: std::env::var("DUCKLAKE_BUFFER_COUNT_THRESHOLD")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(1000),
            size_threshold_mb: std::env::var("DUCKLAKE_BUFFER_SIZE_THRESHOLD_MB")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(64),
            max_buffer_memory_mb: std::env::var("DUCKLAKE_BUFFER_MAX_MEMORY_MB")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(256),
            buffer_overflow_strategy: OverflowStrategy::Compress,
        }
    }

    /// Load configuration from wasmCloud HostData properties.
    ///
    /// This lets K8s/WADM tune write buffering without code deploys.
    pub fn from_properties(props: &HashMap<String, String>) -> Self {
        // Helper to parse numeric values from the common key variants.
        fn parse_u64(props: &HashMap<String, String>, keys: &[&str]) -> Option<u64> {
            keys.iter()
                .find_map(|k| props.get(*k))
                .and_then(|v| v.parse::<u64>().ok())
        }
        fn parse_u32(props: &HashMap<String, String>, keys: &[&str]) -> Option<u32> {
            keys.iter()
                .find_map(|k| props.get(*k))
                .and_then(|v| v.parse::<u32>().ok())
        }

        let defaults = Self::from_env();

        Self {
            time_threshold_seconds: parse_u64(
                props,
                &[
                    "ducklake_buffer_time_threshold_seconds",
                    "DUCKLAKE_BUFFER_TIME_THRESHOLD_SECONDS",
                ],
            )
            .unwrap_or(defaults.time_threshold_seconds),
            count_threshold: parse_u32(
                props,
                &[
                    "ducklake_buffer_count_threshold",
                    "DUCKLAKE_BUFFER_COUNT_THRESHOLD",
                ],
            )
            .unwrap_or(defaults.count_threshold),
            size_threshold_mb: parse_u32(
                props,
                &[
                    "ducklake_buffer_size_threshold_mb",
                    "DUCKLAKE_BUFFER_SIZE_THRESHOLD_MB",
                ],
            )
            .unwrap_or(defaults.size_threshold_mb),
            max_buffer_memory_mb: parse_u32(
                props,
                &[
                    "ducklake_buffer_max_memory_mb",
                    "DUCKLAKE_BUFFER_MAX_MEMORY_MB",
                ],
            )
            .unwrap_or(defaults.max_buffer_memory_mb),
            buffer_overflow_strategy: defaults.buffer_overflow_strategy,
        }
    }
}

/// Buffer overflow handling strategies
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum OverflowStrategy {
    /// Drop oldest records when buffer is full
    DropOldest,
    /// Block new writes until buffer has space
    Block,
    /// Compress buffer contents to save memory
    Compress,
}

/// Flush trigger reasons
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum FlushTrigger {
    TimeThreshold,
    CountThreshold,
    SizeThreshold,
    Manual,
    Shutdown,
}

/// A buffered record ready for writing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BufferedRecord {
    /// JSON data to write
    pub data: String,
    /// Chain ID (e.g., "ethereum_mainnet")
    pub chain_id: String,
    /// Target table name
    pub table: String,
    /// Block timestamp for partitioning
    pub block_timestamp: i64,
    /// Record size in bytes
    pub size_bytes: usize,
    /// When record was buffered
    pub buffered_at: DateTime<Utc>,
}

/// Batch ready for writing to DuckLake
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReadyBatch {
    pub batch_id: Uuid,
    pub table: String,
    pub chain_id: String,
    pub records: Vec<BufferedRecord>,
    pub flush_reason: FlushTrigger,
    pub total_size_bytes: usize,
    pub created_at: DateTime<Utc>,
}

/// Per-partition buffer with trigger tracking
#[derive(Debug)]
struct PartitionBuffer {
    table: String,
    chain_id: String,
    records: Vec<BufferedRecord>,
    buffer_size_bytes: usize,
    last_flush: Instant,
}

impl PartitionBuffer {
    fn new(table: String, chain_id: String) -> Self {
        Self {
            table,
            chain_id,
            records: Vec::new(),
            buffer_size_bytes: 0,
            last_flush: Instant::now(),
        }
    }

    fn add_record(&mut self, record: BufferedRecord) {
        self.buffer_size_bytes += record.size_bytes;
        self.records.push(record);
    }

    fn should_flush(&self, config: &MicroBatchConfig) -> Option<FlushTrigger> {
        let elapsed = self.last_flush.elapsed();

        // Time threshold check
        if elapsed.as_secs() >= config.time_threshold_seconds {
            return Some(FlushTrigger::TimeThreshold);
        }

        // Count threshold check
        if self.records.len() >= config.count_threshold as usize {
            return Some(FlushTrigger::CountThreshold);
        }

        // Size threshold check
        if self.buffer_size_bytes >= (config.size_threshold_mb as usize * 1024 * 1024) {
            return Some(FlushTrigger::SizeThreshold);
        }

        None
    }

    fn take_batch(&mut self, flush_reason: FlushTrigger) -> ReadyBatch {
        let records = std::mem::take(&mut self.records);
        let total_size_bytes = self.buffer_size_bytes;
        self.buffer_size_bytes = 0;
        self.last_flush = Instant::now();

        ReadyBatch {
            batch_id: Uuid::new_v4(),
            table: self.table.clone(),
            chain_id: self.chain_id.clone(),
            records,
            flush_reason,
            total_size_bytes,
            created_at: Utc::now(),
        }
    }
}

/// Micro-batch buffer manager
pub struct MicroBatchBuffer {
    config: MicroBatchConfig,
    buffers: DashMap<BufferKey, PartitionBuffer>,
    batch_sender: mpsc::Sender<ReadyBatch>,
}

impl MicroBatchBuffer {
    /// Create a new micro-batch buffer
    pub fn new(config: MicroBatchConfig, batch_sender: mpsc::Sender<ReadyBatch>) -> Self {
        Self {
            config,
            buffers: DashMap::new(),
            batch_sender,
        }
    }

    /// Create buffer key from table and chain_id
    fn buffer_key(table: &str, chain_id: &str) -> BufferKey {
        format!("{}:{}", table, chain_id)
    }

    /// Add a record to the buffer
    #[instrument(skip(self, record), fields(table = %record.table, chain_id = %record.chain_id))]
    pub async fn add_record(&self, record: BufferedRecord) -> Result<(), DuckLakeError> {
        let key = Self::buffer_key(&record.table, &record.chain_id);
        let table = record.table.clone();
        let chain_id = record.chain_id.clone();

        // Get or create buffer for this partition
        let mut buffer = self.buffers.entry(key.clone()).or_insert_with(|| {
            debug!("Creating new buffer for {}:{}", table, chain_id);
            PartitionBuffer::new(table.clone(), chain_id.clone())
        });

        // Add record to buffer
        buffer.add_record(record);

        // Check if we should flush
        if let Some(flush_reason) = buffer.should_flush(&self.config) {
            let batch = buffer.take_batch(flush_reason.clone());
            drop(buffer); // Release lock before sending

            info!(
                "Flushing batch {} for {}:{} ({} records, {} bytes, reason: {:?})",
                batch.batch_id,
                table,
                chain_id,
                batch.records.len(),
                batch.total_size_bytes,
                flush_reason
            );

            self.batch_sender
                .send(batch)
                .await
                .map_err(|e| DuckLakeError::BufferError(format!("Failed to send batch: {}", e)))?;
        }

        Ok(())
    }

    /// Start background timer for time-based flushes
    pub fn start_timer(self: Arc<Self>) -> tokio::task::JoinHandle<()> {
        let check_interval = Duration::from_secs(5);

        tokio::spawn(async move {
            let mut interval = interval(check_interval);

            loop {
                interval.tick().await;

                // Check all buffers for time-based flushes
                let keys_to_check: Vec<_> = self.buffers.iter().map(|r| r.key().clone()).collect();

                for key in keys_to_check {
                    if let Some(mut buffer) = self.buffers.get_mut(&key) {
                        if let Some(FlushTrigger::TimeThreshold) = buffer.should_flush(&self.config)
                        {
                            if !buffer.records.is_empty() {
                                let batch = buffer.take_batch(FlushTrigger::TimeThreshold);
                                drop(buffer);

                                info!(
                                    "Time-based flush for {}:{} ({} records)",
                                    batch.table,
                                    batch.chain_id,
                                    batch.records.len()
                                );

                                if let Err(e) = self.batch_sender.send(batch).await {
                                    warn!("Failed to send time-based batch: {}", e);
                                }
                            }
                        }
                    }
                }
            }
        })
    }

    /// Flush all buffers (for shutdown)
    pub async fn flush_all(&self) -> Result<(), DuckLakeError> {
        info!("Flushing all buffers for shutdown");

        let keys: Vec<_> = self.buffers.iter().map(|r| r.key().clone()).collect();

        for key in keys {
            if let Some(mut buffer) = self.buffers.get_mut(&key) {
                if !buffer.records.is_empty() {
                    let batch = buffer.take_batch(FlushTrigger::Shutdown);
                    drop(buffer);

                    info!(
                        "Shutdown flush for {}:{} ({} records)",
                        batch.table,
                        batch.chain_id,
                        batch.records.len()
                    );

                    self.batch_sender.send(batch).await.map_err(|e| {
                        DuckLakeError::BufferError(format!("Failed to send shutdown batch: {}", e))
                    })?;
                }
            }
        }

        Ok(())
    }

    /// Get current buffer statistics
    pub fn get_stats(&self) -> BufferStats {
        let mut total_records = 0;
        let mut total_size_bytes = 0;
        let mut partition_count = 0;

        for buffer in self.buffers.iter() {
            total_records += buffer.records.len();
            total_size_bytes += buffer.buffer_size_bytes;
            partition_count += 1;
        }

        BufferStats {
            total_records,
            total_size_bytes,
            partition_count,
        }
    }
}

/// Buffer statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BufferStats {
    pub total_records: usize,
    pub total_size_bytes: usize,
    pub partition_count: usize,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_defaults() {
        let config = MicroBatchConfig::default();
        assert_eq!(config.time_threshold_seconds, 30);
        assert_eq!(config.count_threshold, 1000);
        assert_eq!(config.size_threshold_mb, 64);
    }

    #[tokio::test]
    async fn test_buffer_add_record() {
        let (tx, mut rx) = mpsc::channel(100);
        let config = MicroBatchConfig {
            count_threshold: 2, // Low threshold for testing
            ..Default::default()
        };
        let buffer = MicroBatchBuffer::new(config, tx);

        // Add first record - should not trigger flush
        let record1 = BufferedRecord {
            data: r#"{"test": 1}"#.to_string(),
            chain_id: "ethereum_mainnet".to_string(),
            table: "transactions".to_string(),
            block_timestamp: 1640995200,
            size_bytes: 20,
            buffered_at: Utc::now(),
        };
        buffer.add_record(record1).await.unwrap();

        // No batch should be ready yet
        assert!(rx.try_recv().is_err());

        // Add second record - should trigger flush due to count threshold
        let record2 = BufferedRecord {
            data: r#"{"test": 2}"#.to_string(),
            chain_id: "ethereum_mainnet".to_string(),
            table: "transactions".to_string(),
            block_timestamp: 1640995200,
            size_bytes: 20,
            buffered_at: Utc::now(),
        };
        buffer.add_record(record2).await.unwrap();

        // Batch should be ready
        let batch = rx.recv().await.unwrap();
        assert_eq!(batch.table, "transactions");
        assert_eq!(batch.chain_id, "ethereum_mainnet");
        assert_eq!(batch.records.len(), 2);
        assert_eq!(batch.flush_reason, FlushTrigger::CountThreshold);
    }
}
