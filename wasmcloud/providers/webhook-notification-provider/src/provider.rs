use anyhow::{Context, Result};
use async_nats::Client as NatsClient;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info};
use wasmcloud_provider_sdk::Provider;

use crate::nats_handler::NatsHandler;
use crate::redis_client::RedisClient;
use crate::webhook_client::WebhookClient;

/// Provider configuration
#[derive(Debug, Clone)]
pub struct ProviderConfig {
    pub nats_url: String,
    pub redis_url: String,
}

impl ProviderConfig {
    /// Create config from wasmCloud host data properties
    pub fn from_properties(props: &std::collections::HashMap<String, String>) -> Result<Self> {
        Ok(Self {
            nats_url: props
                .get("nats_url")
                .cloned()
                .or_else(|| std::env::var("NATS_URL").ok())
                .unwrap_or_else(|| "nats://localhost:4222".to_string()),
            redis_url: props
                .get("redis_url")
                .cloned()
                .or_else(|| std::env::var("REDIS_URL").ok())
                .unwrap_or_else(|| "redis://localhost:6379".to_string()),
        })
    }

    /// Create config from environment variables
    pub fn from_env() -> Result<Self> {
        Ok(Self {
            nats_url: std::env::var("NATS_URL")
                .unwrap_or_else(|_| "nats://localhost:4222".to_string()),
            redis_url: std::env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://localhost:6379".to_string()),
        })
    }
}

impl Default for ProviderConfig {
    fn default() -> Self {
        Self::from_env().unwrap()
    }
}

/// Webhook notification provider
#[derive(Clone)]
pub struct WebhookProvider {
    nats_client: NatsClient,
    redis_client: Arc<RwLock<RedisClient>>,
    webhook_client: Arc<WebhookClient>,
}

impl WebhookProvider {
    /// Create new webhook provider from config
    pub async fn from_config(config: ProviderConfig) -> Result<Self> {
        Self::new(&config.nats_url, &config.redis_url).await
    }

    /// Create new webhook provider
    pub async fn new(nats_url: &str, redis_url: &str) -> Result<Self> {
        info!("Initializing WebhookProvider");

        // Connect to NATS
        let nats_client = async_nats::connect(nats_url)
            .await
            .context("Failed to connect to NATS")?;

        info!("Connected to NATS at {}", nats_url);

        // Connect to Redis
        let redis_client = RedisClient::new(redis_url).await?;
        let redis_client = Arc::new(RwLock::new(redis_client));

        // Create webhook HTTP client
        let webhook_client = Arc::new(WebhookClient::new()?);

        info!("WebhookProvider initialized successfully");

        Ok(Self {
            nats_client,
            redis_client,
            webhook_client,
        })
    }

    /// Start the provider
    pub async fn run(self) -> Result<()> {
        info!("Starting WebhookProvider");

        // Create NATS handler
        let handler = NatsHandler::new(
            self.nats_client.clone(),
            self.redis_client.clone(),
            self.webhook_client.clone(),
        );

        // Start listening for webhook notifications
        let subject = "notifications.send.immediate.webhook";

        // Run handler (this will block until error or shutdown)
        if let Err(e) = handler.start(subject).await {
            error!("NATS handler error: {}", e);
            return Err(e);
        }

        Ok(())
    }
}

impl Provider for WebhookProvider {}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider + Clone>() {}
        assert_provider::<WebhookProvider>();
    }
}
