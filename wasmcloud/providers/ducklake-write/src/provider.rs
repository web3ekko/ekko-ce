//! wasmCloud provider implementation for DuckLake Write
//!
//! Implements the wasmCloud provider lifecycle.

use anyhow::Result;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::{error, info, instrument, warn};
use wasmcloud_provider_sdk::Provider;

use ducklake_common::config::DuckLakeConfig;

use crate::buffer::{MicroBatchBuffer, MicroBatchConfig};
use crate::nats_listener::{NatsListenerConfig, NatsWriteListener};
use crate::writer::DuckLakeWriter;

/// DuckLake Write Provider
#[derive(Clone)]
pub struct DuckLakeWriteProvider {
    writer: Arc<DuckLakeWriter>,
    buffer: Arc<MicroBatchBuffer>,
    nats_config: NatsListenerConfig,
}

impl DuckLakeWriteProvider {
    /// Create a new DuckLake Write Provider with configuration from wasmCloud HostData
    #[instrument(skip(config))]
    pub fn with_config(config: HashMap<String, String>) -> Result<Self> {
        info!("Creating DuckLake Write Provider with config from HostData");
        info!("Config keys: {:?}", config.keys().collect::<Vec<_>>());

        // Load DuckLake config - try properties first, fall back to env vars
        let ducklake_config = if !config.is_empty() {
            info!("Using configuration from wasmCloud HostData");
            DuckLakeConfig::from_properties(&config)?
        } else {
            warn!("No config from HostData, falling back to environment variables");
            DuckLakeConfig::from_env()?
        };

        let buffer_config = if !config.is_empty() {
            MicroBatchConfig::from_properties(&config)
        } else {
            MicroBatchConfig::from_env()
        };

        let nats_config = if !config.is_empty() {
            NatsListenerConfig::from_properties(&config)
        } else {
            NatsListenerConfig::from_env()
        };

        // Create batch channel
        let (batch_tx, batch_rx) = mpsc::channel(100);

        // Create writer
        let writer = Arc::new(DuckLakeWriter::new(ducklake_config));

        // Create buffer
        let buffer = Arc::new(MicroBatchBuffer::new(buffer_config, batch_tx));

        // Spawn batch consumer
        let writer_clone = Arc::clone(&writer);
        tokio::spawn(async move {
            writer_clone.start(batch_rx).await;
        });

        Ok(Self {
            writer,
            buffer,
            nats_config,
        })
    }

    /// Create a new DuckLake Write Provider (uses environment variables)
    #[instrument]
    pub fn new() -> Result<Self> {
        info!("Creating DuckLake Write Provider (env-only)");
        Self::with_config(HashMap::new())
    }

    /// Start the provider
    #[instrument(skip(self))]
    pub async fn start(self: Arc<Self>) -> Result<()> {
        info!("Starting DuckLake Write Provider");
        info!(">>> BUILD v1.0.11 - 2025-12-23T11:45Z <<<");

        // Use tracing for debugging (eprintln may not appear in K8s logs)
        info!(">>> HEALTH-CHECK: About to verify DuckLake connection...");

        // Verify writer can connect (health check)
        info!(">>> HEALTH-CHECK: Calling is_healthy()...");
        let is_healthy = self.writer.is_healthy();
        info!(">>> HEALTH-CHECK: is_healthy() returned: {}", is_healthy);

        if !is_healthy {
            error!(">>> HEALTH-CHECK: FAILED - connection could not be established");
            return Err(anyhow::anyhow!("Failed to verify DuckLake connection"));
        }
        info!(">>> HEALTH-CHECK: PASSED");
        info!("DuckLake connection verified");

        // Start buffer timer
        let buffer_clone = Arc::clone(&self.buffer);
        buffer_clone.start_timer();

        // Start NATS listener
        let listener = NatsWriteListener::new(self.nats_config.clone(), Arc::clone(&self.buffer));

        // This blocks until NATS connection is lost
        listener.start().await?;

        // Flush remaining buffers on shutdown
        if let Err(e) = self.buffer.flush_all().await {
            error!("Error flushing buffers on shutdown: {}", e);
        }

        info!("DuckLake Write Provider stopped");
        Ok(())
    }

    /// Get buffer statistics
    pub fn get_stats(&self) -> crate::buffer::BufferStats {
        self.buffer.get_stats()
    }

    /// Check provider health
    pub fn is_healthy(&self) -> bool {
        self.writer.is_healthy()
    }
}

impl Default for DuckLakeWriteProvider {
    fn default() -> Self {
        Self::new().expect("Failed to create default DuckLakeWriteProvider")
    }
}

impl Provider for DuckLakeWriteProvider {}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider + Clone>() {}
        assert_provider::<DuckLakeWriteProvider>();
    }
}
