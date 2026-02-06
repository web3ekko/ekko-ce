//! wasmCloud provider implementation for DuckLake Read
//!
//! Implements the wasmCloud provider lifecycle.

use anyhow::Result;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{info, instrument};
use wasmcloud_provider_sdk::Provider;

use ducklake_common::config::DuckLakeConfig;

use crate::nats_listener::{NatsQueryListener, NatsQueryListenerConfig};
use crate::reader::DuckLakeReader;

/// DuckLake Read Provider
#[derive(Clone)]
pub struct DuckLakeReadProvider {
    reader: Arc<DuckLakeReader>,
    nats_config: NatsQueryListenerConfig,
}

impl DuckLakeReadProvider {
    /// Create a new DuckLake Read Provider with configuration from wasmCloud HostData.
    #[instrument(skip(config))]
    pub fn with_config(config: HashMap<String, String>) -> Result<Self> {
        info!("Creating DuckLake Read Provider with config from HostData");

        let ducklake_config = if !config.is_empty() {
            DuckLakeConfig::from_properties(&config)?
        } else {
            DuckLakeConfig::from_env()?
        };

        let nats_config = if !config.is_empty() {
            NatsQueryListenerConfig::from_properties(&config)
        } else {
            NatsQueryListenerConfig::from_env()
        };

        let reader = Arc::new(DuckLakeReader::new(ducklake_config));

        Ok(Self {
            reader,
            nats_config,
        })
    }

    /// Create a new DuckLake Read Provider
    #[instrument]
    pub fn new() -> Result<Self> {
        Self::with_config(HashMap::new())
    }

    /// Start the provider
    #[instrument(skip(self))]
    pub async fn start(self: Arc<Self>) -> Result<()> {
        info!("Starting DuckLake Read Provider");

        // Verify reader can connect (health check)
        if !self.reader.is_healthy() {
            return Err(anyhow::anyhow!("Failed to verify DuckLake connection"));
        }
        info!("DuckLake connection verified");

        // Start NATS listener
        let listener = NatsQueryListener::new(self.nats_config.clone(), Arc::clone(&self.reader));

        // This blocks until NATS connection is lost
        listener.start().await?;

        info!("DuckLake Read Provider stopped");
        Ok(())
    }

    /// Check provider health
    pub fn is_healthy(&self) -> bool {
        self.reader.is_healthy()
    }
}

impl Default for DuckLakeReadProvider {
    fn default() -> Self {
        Self::new().expect("Failed to create default DuckLakeReadProvider")
    }
}

impl Provider for DuckLakeReadProvider {}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider + Clone>() {}
        assert_provider::<DuckLakeReadProvider>();
    }
}
