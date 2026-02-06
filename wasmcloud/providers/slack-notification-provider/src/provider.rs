use crate::nats_handler::NatsHandler;
use crate::redis_client::RedisClient;
use crate::slack_client::SlackClient;
use anyhow::Result;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::info;
use wasmcloud_provider_sdk::Provider;

/// Slack Notification Provider for wasmCloud
#[derive(Clone)]
pub struct SlackNotificationProvider {
    nats_handler: Arc<NatsHandler>,
    redis_client: Arc<Mutex<RedisClient>>,
    slack_client: Arc<SlackClient>,
    config: ProviderConfig,
}

/// Provider configuration
#[derive(Debug, Clone)]
pub struct ProviderConfig {
    pub redis_url: String,
    pub nats_url: String,
}

impl ProviderConfig {
    /// Create config from wasmCloud host data properties
    pub fn from_properties(props: &std::collections::HashMap<String, String>) -> Result<Self> {
        Ok(Self {
            redis_url: props
                .get("redis_url")
                .cloned()
                .or_else(|| std::env::var("REDIS_URL").ok())
                .unwrap_or_else(|| {
                    "redis://:redis123@redis-master.ekko.svc.cluster.local:6379".to_string()
                }),
            nats_url: props
                .get("nats_url")
                .cloned()
                .or_else(|| std::env::var("NATS_URL").ok())
                .unwrap_or_else(|| "nats://127.0.0.1:4222".to_string()),
        })
    }

    /// Create config from environment variables
    pub fn from_env() -> Result<Self> {
        Ok(Self {
            redis_url: std::env::var("REDIS_URL").unwrap_or_else(|_| {
                "redis://:redis123@redis-master.ekko.svc.cluster.local:6379".to_string()
            }),
            nats_url: std::env::var("NATS_URL")
                .unwrap_or_else(|_| "nats://127.0.0.1:4222".to_string()),
        })
    }
}

impl Default for ProviderConfig {
    fn default() -> Self {
        Self::from_env().unwrap()
    }
}

impl SlackNotificationProvider {
    /// Create a new provider instance
    pub async fn new(config: ProviderConfig) -> Result<Self> {
        info!("Initializing Slack Notification Provider");

        // Initialize Redis client
        let mut redis_client = RedisClient::new(&config.redis_url)?;
        redis_client.connect().await?;
        let redis_client = Arc::new(Mutex::new(redis_client));

        // Initialize Slack client
        let slack_client = Arc::new(SlackClient::new());

        // Initialize NATS client
        let nats_client = async_nats::connect(&config.nats_url).await?;

        // Initialize NATS handler
        let nats_handler = Arc::new(NatsHandler::new(
            nats_client,
            slack_client.clone(),
            redis_client.clone(),
        ));

        Ok(Self {
            nats_handler,
            redis_client,
            slack_client,
            config,
        })
    }

    /// Start the provider
    pub async fn start(&self) -> Result<()> {
        info!("Starting Slack Notification Provider");

        // Start NATS subscription
        self.nats_handler.start().await?;

        Ok(())
    }

    /// Get Slack client for testing webhooks
    pub fn slack_client(&self) -> Arc<SlackClient> {
        self.slack_client.clone()
    }
}

impl Provider for SlackNotificationProvider {}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_config_default() {
        let config = ProviderConfig::default();
        assert!(config.redis_url.contains("redis"));
        assert!(config.nats_url.contains("nats"));
    }

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider + Clone>() {}
        assert_provider::<SlackNotificationProvider>();
    }
}
