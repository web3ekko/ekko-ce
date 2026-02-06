//! Configuration for Alert Scheduler Provider

use serde::{Deserialize, Serialize};

/// Configuration for Alert Scheduler Provider
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct AlertSchedulerConfig {
    /// Redis connection URL (alert cache + deduplication)
    pub redis_url: String,

    /// NATS connection URL
    #[serde(default = "default_nats_url")]
    pub nats_url: String,

    /// NATS JetStream stream name for alert jobs
    #[serde(default = "default_stream_name")]
    pub nats_stream_name: String,

    /// Maximum number of concurrent alerts
    #[serde(default = "default_max_alerts")]
    pub max_concurrent_alerts: usize,

    /// Job deduplication window in seconds
    #[serde(default = "default_dedup_window")]
    pub deduplication_window_seconds: u32,

    /// Batch size for cleanup operations
    #[serde(default = "default_cleanup_batch_size")]
    pub cleanup_batch_size: u32,

    /// Maximum age for instances before cleanup (seconds)
    #[serde(default = "default_max_instance_age")]
    pub max_instance_age_seconds: u32,

    /// Redis connection pool size
    #[serde(default = "default_pool_size")]
    pub redis_pool_size: usize,

    /// Maximum connections (alias for redis_pool_size for compatibility)
    #[serde(default = "default_pool_size")]
    pub max_connections: usize,

    /// Connection timeout in milliseconds
    #[serde(default = "default_connection_timeout")]
    pub connection_timeout_ms: u64,

    /// Number of retry attempts
    #[serde(default = "default_retry_attempts")]
    pub retry_attempts: u32,

    /// Delay between retries in milliseconds
    #[serde(default = "default_retry_delay")]
    pub retry_delay_ms: u64,

    /// Instance scan batch size for seeding schedule indices
    #[serde(default = "default_instance_scan_batch_size")]
    pub instance_scan_batch_size: u32,

    /// Max due scheduled instances processed per scan tick
    #[serde(default = "default_schedule_due_batch_size")]
    pub schedule_due_batch_size: u32,

    /// Max targets per evaluation job (scheduled microbatch)
    #[serde(default = "default_microbatch_max_targets")]
    pub microbatch_max_targets: u32,

    /// Max targets per event-driven job (bundling cap)
    #[serde(default = "default_event_job_targets_cap")]
    pub event_job_targets_cap: u32,

    /// TTL for schedule request dedupe keys (seconds)
    #[serde(default = "default_schedule_request_dedupe_ttl_secs")]
    pub schedule_request_dedupe_ttl_secs: usize,
}

impl AlertSchedulerConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Result<Self, envy::Error> {
        envy::from_env()
    }

    /// Load configuration from wasmCloud properties HashMap
    ///
    /// This is the preferred method when running as a wasmCloud provider,
    /// as the configuration is passed via HostData.config from the WADM manifest.
    pub fn from_properties(
        props: &std::collections::HashMap<String, String>,
    ) -> Result<Self, String> {
        // Required field: redis_url
        let redis_url = props
            .get("redis_url")
            .cloned()
            .ok_or_else(|| "redis_url is required".to_string())?;

        // Optional fields with defaults
        let nats_url = props
            .get("nats_url")
            .cloned()
            .unwrap_or_else(default_nats_url);

        let nats_stream_name = props
            .get("nats_stream_name")
            .cloned()
            .unwrap_or_else(default_stream_name);

        let max_concurrent_alerts = props
            .get("max_concurrent_alerts")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_max_alerts);

        let deduplication_window_seconds = props
            .get("deduplication_window_seconds")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_dedup_window);

        let cleanup_batch_size = props
            .get("cleanup_batch_size")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_cleanup_batch_size);

        let max_instance_age_seconds = props
            .get("max_instance_age_seconds")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_max_instance_age);

        let redis_pool_size = props
            .get("redis_pool_size")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_pool_size);

        let max_connections = props
            .get("max_connections")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_pool_size);

        let connection_timeout_ms = props
            .get("connection_timeout_ms")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_connection_timeout);

        let retry_attempts = props
            .get("retry_attempts")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_retry_attempts);

        let retry_delay_ms = props
            .get("retry_delay_ms")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_retry_delay);

        let instance_scan_batch_size = props
            .get("instance_scan_batch_size")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_instance_scan_batch_size);

        let schedule_due_batch_size = props
            .get("schedule_due_batch_size")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_schedule_due_batch_size);

        let microbatch_max_targets = props
            .get("microbatch_max_targets")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_microbatch_max_targets);

        let event_job_targets_cap = props
            .get("event_job_targets_cap")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_event_job_targets_cap);

        let schedule_request_dedupe_ttl_secs = props
            .get("schedule_request_dedupe_ttl_secs")
            .and_then(|v| v.parse().ok())
            .unwrap_or_else(default_schedule_request_dedupe_ttl_secs);

        Ok(Self {
            redis_url,
            nats_url,
            nats_stream_name,
            max_concurrent_alerts,
            deduplication_window_seconds,
            cleanup_batch_size,
            max_instance_age_seconds,
            redis_pool_size,
            max_connections,
            connection_timeout_ms,
            retry_attempts,
            retry_delay_ms,
            instance_scan_batch_size,
            schedule_due_batch_size,
            microbatch_max_targets,
            event_job_targets_cap,
            schedule_request_dedupe_ttl_secs,
        })
    }
}

impl Default for AlertSchedulerConfig {
    fn default() -> Self {
        Self {
            redis_url: "redis://localhost:6379".to_string(),
            nats_url: "nats://localhost:4222".to_string(),
            nats_stream_name: "ALERT_JOBS".to_string(),
            max_concurrent_alerts: 50_000,
            deduplication_window_seconds: 300, // 5 minutes
            cleanup_batch_size: 100,
            max_instance_age_seconds: 2_592_000, // 30 days
            redis_pool_size: 10,
            max_connections: 10,
            connection_timeout_ms: 5000,
            retry_attempts: 3,
            retry_delay_ms: 100,
            instance_scan_batch_size: 500,
            schedule_due_batch_size: 200,
            microbatch_max_targets: 5000,
            event_job_targets_cap: 8,
            schedule_request_dedupe_ttl_secs: 60 * 60 * 24,
        }
    }
}

fn default_nats_url() -> String {
    "nats://localhost:4222".to_string()
}

fn default_stream_name() -> String {
    "ALERT_JOBS".to_string()
}

fn default_max_alerts() -> usize {
    50_000
}

fn default_dedup_window() -> u32 {
    300
}

fn default_cleanup_batch_size() -> u32 {
    100
}

fn default_max_instance_age() -> u32 {
    2_592_000
}

fn default_pool_size() -> usize {
    10
}

fn default_connection_timeout() -> u64 {
    5000
}

fn default_retry_attempts() -> u32 {
    3
}

fn default_retry_delay() -> u64 {
    100
}

fn default_instance_scan_batch_size() -> u32 {
    500
}

fn default_schedule_due_batch_size() -> u32 {
    200
}

fn default_microbatch_max_targets() -> u32 {
    5000
}

fn default_event_job_targets_cap() -> u32 {
    8
}

fn default_schedule_request_dedupe_ttl_secs() -> usize {
    60 * 60 * 24
}
