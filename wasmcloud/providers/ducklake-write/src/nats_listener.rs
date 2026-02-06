//! NATS listener for DuckLake write operations
//!
//! Subscribes to `ducklake.*.*.*.write` and forwards records to the buffer.

use anyhow::{Context, Result};
use chrono::Utc;
use ducklake_common::subject_parser::SubjectInfo;
use futures::StreamExt;
use serde_json::Value;
use std::sync::Arc;
use tracing::{debug, error, info, instrument, warn};

use crate::buffer::{BufferedRecord, MicroBatchBuffer};

/// NATS listener configuration
#[derive(Debug, Clone)]
pub struct NatsListenerConfig {
    /// NATS server URL
    pub nats_url: String,
    /// Subject pattern to subscribe to
    pub subject_pattern: String,
}

impl NatsListenerConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        let nats_url =
            std::env::var("NATS_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());

        // Subscribe to all write operations by default
        let subject_pattern = std::env::var("DUCKLAKE_WRITE_SUBJECT")
            .unwrap_or_else(|_| "ducklake.*.*.*.write".to_string());

        Self {
            nats_url,
            subject_pattern,
        }
    }

    /// Load configuration from wasmCloud HostData properties.
    ///
    /// Keys are expected in the same format used by `apps/wasmcloud/setup-configs.sh`.
    pub fn from_properties(props: &std::collections::HashMap<String, String>) -> Self {
        let nats_url = props
            .get("nats_url")
            .or_else(|| props.get("NATS_URL"))
            .cloned()
            .unwrap_or_else(|| "nats://localhost:4222".to_string());

        let subject_pattern = props
            .get("ducklake_write_subject")
            .or_else(|| props.get("ducklake_write_subject_pattern"))
            .or_else(|| props.get("DUCKLAKE_WRITE_SUBJECT"))
            .cloned()
            .unwrap_or_else(|| "ducklake.*.*.*.write".to_string());

        Self {
            nats_url,
            subject_pattern,
        }
    }
}

/// NATS listener for DuckLake write operations
pub struct NatsWriteListener {
    config: NatsListenerConfig,
    buffer: Arc<MicroBatchBuffer>,
}

impl NatsWriteListener {
    /// Create a new NATS write listener
    pub fn new(config: NatsListenerConfig, buffer: Arc<MicroBatchBuffer>) -> Self {
        Self { config, buffer }
    }

    /// Start listening for write requests
    #[instrument(skip(self))]
    pub async fn start(self) -> Result<()> {
        info!("Connecting to NATS at {}", self.config.nats_url);

        let client = async_nats::connect(&self.config.nats_url)
            .await
            .context("Failed to connect to NATS")?;

        info!("Connected to NATS successfully");
        info!("Subscribing to pattern: {}", self.config.subject_pattern);

        let mut subscriber = client
            .subscribe(self.config.subject_pattern.clone())
            .await
            .context("Failed to subscribe to write subject pattern")?;

        info!("Successfully subscribed to {}", self.config.subject_pattern);
        info!("DuckLake Write Listener is ready");

        // Process messages
        while let Some(message) = subscriber.next().await {
            let subject = message.subject.as_str();

            if let Err(e) = self.process_message(subject, &message.payload).await {
                error!("Failed to process message on {}: {}", subject, e);
            }
        }

        warn!("NATS subscription ended");
        Ok(())
    }

    /// Process a single message
    #[instrument(skip(self, payload), fields(subject = %subject))]
    async fn process_message(&self, subject: &str, payload: &[u8]) -> Result<()> {
        // Parse the subject to get table, chain, subnet info
        // Important: this provider should only handle `...write` subjects. If misconfigured
        // to subscribe broadly (e.g. `ducklake.>`), ignore any non-write messages to avoid
        // corrupting the lake or swallowing request/reply query traffic.
        let subject_info = match SubjectInfo::parse(subject) {
            Ok(info) => info,
            Err(e) => {
                // ducklake.schema.* subjects intentionally don't match the 5-token format.
                if subject.starts_with("ducklake.schema.") {
                    debug!("Ignoring non-write DuckLake schema subject: {}", subject);
                    return Ok(());
                }
                return Err(anyhow::anyhow!(e)).context("Failed to parse NATS subject");
            }
        };

        if subject_info.action != "write" {
            debug!(
                "Ignoring DuckLake message with non-write action (action={}): {}",
                subject_info.action, subject
            );
            return Ok(());
        }

        debug!(
            "Processing write for table={} chain_id={}",
            subject_info.table, subject_info.chain_id
        );

        // Deserialize JSON record(s)
        let payload_str = std::str::from_utf8(payload).context("Payload is not valid UTF-8")?;

        // Try to parse as array first, then as single object
        let records: Vec<Value> = if payload_str.trim().starts_with('[') {
            serde_json::from_str(payload_str).context("Failed to parse JSON array")?
        } else {
            let single: Value =
                serde_json::from_str(payload_str).context("Failed to parse JSON object")?;
            vec![single]
        };

        info!(
            "Received {} record(s) for {}:{}",
            records.len(),
            subject_info.table,
            subject_info.chain_id
        );

        // Process each record
        for record_value in records {
            // Extract block_timestamp for partitioning
            let block_timestamp = record_value
                .get("block_timestamp")
                .and_then(|v| v.as_i64())
                .or_else(|| record_value.get("timestamp").and_then(|v| v.as_i64()))
                .unwrap_or_else(|| Utc::now().timestamp());

            let data =
                serde_json::to_string(&record_value).context("Failed to serialize record")?;
            let size_bytes = data.len();

            let buffered_record = BufferedRecord {
                data,
                chain_id: subject_info.chain_id.clone(),
                table: subject_info.table.clone(),
                block_timestamp,
                size_bytes,
                buffered_at: Utc::now(),
            };

            self.buffer
                .add_record(buffered_record)
                .await
                .context("Failed to add record to buffer")?;
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn test_config_from_env() {
        let _guard = ENV_LOCK.lock().unwrap();
        std::env::set_var("NATS_URL", "nats://test:4222");
        std::env::set_var("DUCKLAKE_WRITE_SUBJECT", "ducklake.transactions.*.*.write");

        let config = NatsListenerConfig::from_env();
        assert_eq!(config.nats_url, "nats://test:4222");
        assert_eq!(config.subject_pattern, "ducklake.transactions.*.*.write");

        std::env::remove_var("NATS_URL");
        std::env::remove_var("DUCKLAKE_WRITE_SUBJECT");
    }

    #[test]
    fn test_config_defaults() {
        let _guard = ENV_LOCK.lock().unwrap();
        std::env::remove_var("NATS_URL");
        std::env::remove_var("DUCKLAKE_WRITE_SUBJECT");

        let config = NatsListenerConfig::from_env();
        assert_eq!(config.nats_url, "nats://localhost:4222");
        assert_eq!(config.subject_pattern, "ducklake.*.*.*.write");
    }

    #[test]
    fn test_config_from_properties() {
        let mut props = HashMap::new();
        props.insert("nats_url".to_string(), "nats://cluster:4222".to_string());
        props.insert(
            "ducklake_write_subject".to_string(),
            "ducklake.address_transactions.*.*.write".to_string(),
        );

        let config = NatsListenerConfig::from_properties(&props);
        assert_eq!(config.nats_url, "nats://cluster:4222");
        assert_eq!(
            config.subject_pattern,
            "ducklake.address_transactions.*.*.write"
        );
    }
}
