//! wasmCloud Provider implementation for WebSocket Notification Provider
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::Context;
use async_trait::async_trait;
use std::collections::HashMap;
use tracing::{info, warn};
use wasmcloud_provider_sdk::{load_host_data, run_provider, Provider};
use websocket_notification_provider::{
    ProviderConfig, WebSocketNotificationProvider as CoreProvider,
};

/// wasmCloud Provider wrapper for WebSocket Notification Provider
pub struct WebSocketProvider {
    core_provider: Option<CoreProvider>,
}

impl WebSocketProvider {
    /// Create a new provider instance with wasmCloud config
    pub async fn new(wasmcloud_config: HashMap<String, String>) -> anyhow::Result<Self> {
        info!("Initializing WebSocket Provider for wasmCloud");

        // Log available config keys for debugging
        for (key, value) in &wasmcloud_config {
            let display_value = if key.contains("password") || key.contains("secret") {
                "***".to_string()
            } else {
                value.clone()
            };
            info!("Config: {} = {}", key, display_value);
        }

        // Build config from wasmCloud config properties, with env var fallbacks
        let config = ProviderConfig {
            websocket_port: wasmcloud_config
                .get("websocket_port")
                .and_then(|s| s.parse().ok())
                .or_else(|| {
                    std::env::var("WEBSOCKET_PORT")
                        .ok()
                        .and_then(|s| s.parse().ok())
                })
                .unwrap_or(8080),
            max_connections: wasmcloud_config
                .get("max_connections")
                .and_then(|s| s.parse().ok())
                .or_else(|| {
                    std::env::var("MAX_CONNECTIONS")
                        .ok()
                        .and_then(|s| s.parse().ok())
                })
                .unwrap_or(10000),
            max_connections_per_user: wasmcloud_config
                .get("max_connections_per_user")
                .and_then(|s| s.parse().ok())
                .or_else(|| {
                    std::env::var("MAX_CONNECTIONS_PER_USER")
                        .ok()
                        .and_then(|s| s.parse().ok())
                })
                .unwrap_or(10),
            redis_url: wasmcloud_config
                .get("redis_url")
                .cloned()
                .or_else(|| std::env::var("REDIS_URL").ok())
                .unwrap_or_else(|| {
                    warn!("No redis_url in config, using default");
                    "redis://:redis123@redis-master.ekko-dev.svc.cluster.local:6379".to_string()
                }),
            nats_url: wasmcloud_config
                .get("nats_url")
                .cloned()
                .or_else(|| std::env::var("NATS_URL").ok())
                .unwrap_or_else(|| {
                    warn!("No nats_url in config, using default");
                    "nats://nats.ekko-dev.svc.cluster.local:4222".to_string()
                }),
            heartbeat_interval_secs: wasmcloud_config
                .get("heartbeat_interval_secs")
                .and_then(|s| s.parse().ok())
                .or_else(|| {
                    std::env::var("HEARTBEAT_INTERVAL_SECS")
                        .ok()
                        .and_then(|s| s.parse().ok())
                })
                .unwrap_or(30),
            connection_timeout_secs: wasmcloud_config
                .get("connection_timeout_secs")
                .and_then(|s| s.parse().ok())
                .or_else(|| {
                    std::env::var("CONNECTION_TIMEOUT_SECS")
                        .ok()
                        .and_then(|s| s.parse().ok())
                })
                .unwrap_or(300),
        };

        info!(
            "Using redis_url: {}",
            config
                .redis_url
                .replace(|c: char| c.is_alphanumeric() && c != '@' && c != ':', "*")
        );
        info!("Using nats_url: {}", config.nats_url);
        info!("Using websocket_port: {}", config.websocket_port);

        // Initialize the core provider
        let core_provider = CoreProvider::new(config).await?;

        Ok(Self {
            core_provider: Some(core_provider),
        })
    }
}

// Provider trait implementation for wasmCloud SDK v0.16
#[async_trait]
impl Provider for WebSocketProvider {
    // The Provider trait in SDK 0.16 has default implementations
    // We only need to implement methods we specifically need to override
}

/// Main entry point for the wasmCloud provider
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("websocket_notification_provider=info".parse().unwrap()),
        )
        .init();

    // Load host data from wasmCloud
    let host_data = load_host_data()?;

    info!("🌟 Starting WebSocket Notification Provider for wasmCloud");
    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);
    info!("Config entries: {}", host_data.config.len());

    // Create provider instance with wasmCloud config
    let mut provider = WebSocketProvider::new(host_data.config.clone()).await?;

    let core_provider = provider
        .core_provider
        .take()
        .context("WebSocket core provider missing")?;

    tokio::spawn(async move {
        if let Err(e) = core_provider.start().await {
            tracing::error!("WebSocket core provider failed: {}", e);
        }
    });

    info!("🎯 Provider ready - waiting for actor invocations");
    let handler = run_provider(provider, "websocket-notification-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("👋 WebSocket Notification Provider shutdown complete");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider>() {}
        assert_provider::<WebSocketProvider>();
    }
}
