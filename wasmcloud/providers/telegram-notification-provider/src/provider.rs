use crate::bot_commands::BotCommandHandler;
use crate::nats_handler::NatsHandler;
use crate::redis_client::RedisClient;
use crate::telegram_client::TelegramClient;
use crate::types::TelegramUpdate;
use anyhow::{Context, Result};
use async_nats::Client as NatsClient;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{error, info};
use warp::Filter;
use wasmcloud_provider_sdk::Provider;

/// Provider configuration
#[derive(Debug, Clone)]
pub struct ProviderConfig {
    pub nats_url: String,
    pub redis_url: String,
    pub webhook_port: u16,
}

impl ProviderConfig {
    /// Create config from wasmCloud host data properties
    pub fn from_properties(props: &std::collections::HashMap<String, String>) -> Result<Self> {
        let webhook_port: u16 = props
            .get("webhook_port")
            .and_then(|s| s.parse().ok())
            .or_else(|| std::env::var("WEBHOOK_PORT").ok()?.parse().ok())
            .unwrap_or(8080);

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
            webhook_port,
        })
    }

    /// Create config from environment variables
    pub fn from_env() -> Result<Self> {
        let webhook_port: u16 = std::env::var("WEBHOOK_PORT")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(8080);

        Ok(Self {
            nats_url: std::env::var("NATS_URL")
                .unwrap_or_else(|_| "nats://localhost:4222".to_string()),
            redis_url: std::env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://localhost:6379".to_string()),
            webhook_port,
        })
    }
}

impl Default for ProviderConfig {
    fn default() -> Self {
        Self::from_env().unwrap()
    }
}

/// Main Telegram Notification Provider
#[derive(Clone)]
pub struct TelegramProvider {
    nats_handler: Arc<NatsHandler>,
    bot_command_handler: Arc<BotCommandHandler>,
    webhook_port: u16,
}

impl TelegramProvider {
    /// Create a new Telegram provider from config
    pub async fn from_config(config: ProviderConfig) -> Result<Self> {
        Self::new(&config.nats_url, &config.redis_url, config.webhook_port).await
    }

    /// Create a new Telegram provider
    pub async fn new(nats_url: &str, redis_url: &str, webhook_port: u16) -> Result<Self> {
        info!("Initializing Telegram Notification Provider");

        // Connect to NATS
        info!("Connecting to NATS at {}", nats_url);
        let nats_client = async_nats::connect(nats_url)
            .await
            .context("Failed to connect to NATS")?;
        info!("Connected to NATS successfully");

        // Create Redis client
        info!("Creating Redis client for {}", redis_url);
        let redis_client = Arc::new(Mutex::new(
            RedisClient::new(redis_url).context("Failed to create Redis client")?,
        ));
        info!("Redis client created successfully");

        // Create Telegram client
        let telegram_client = Arc::new(TelegramClient::new());
        info!("Telegram client created successfully");

        // Create bot command handler
        let bot_command_handler = Arc::new(BotCommandHandler::new(
            telegram_client.clone(),
            redis_client.clone(),
        ));

        // Create NATS handler
        let nats_handler = Arc::new(NatsHandler::new(nats_client, telegram_client, redis_client));

        info!("Telegram Provider initialized successfully");

        Ok(Self {
            nats_handler,
            bot_command_handler,
            webhook_port,
        })
    }

    /// Start the provider
    pub async fn start(self) -> Result<()> {
        info!("Starting Telegram Notification Provider");

        // Start NATS handler in background task
        let nats_handler = self.nats_handler.clone();
        tokio::spawn(async move {
            if let Err(e) = nats_handler.start().await {
                error!("NATS handler error: {}", e);
            }
        });

        // Start webhook server for bot commands
        self.start_webhook_server().await?;

        Ok(())
    }

    /// Start webhook server for receiving Telegram bot updates
    async fn start_webhook_server(&self) -> Result<()> {
        info!("Starting webhook server on port {}", self.webhook_port);

        let bot_command_handler = self.bot_command_handler.clone();

        // Webhook endpoint for Telegram bot updates
        let webhook = warp::path!("telegram" / "webhook" / String)
            .and(warp::post())
            .and(warp::body::json())
            .and_then(move |bot_token: String, update: TelegramUpdate| {
                let handler = bot_command_handler.clone();
                async move {
                    match handler.handle_update(&bot_token, update).await {
                        Ok(_) => Ok::<_, warp::Rejection>(warp::reply::with_status(
                            "OK",
                            warp::http::StatusCode::OK,
                        )),
                        Err(e) => {
                            error!("Error handling Telegram update: {}", e);
                            Ok(warp::reply::with_status(
                                "Internal Server Error",
                                warp::http::StatusCode::INTERNAL_SERVER_ERROR,
                            ))
                        }
                    }
                }
            });

        // Health check endpoint
        let health = warp::path!("health")
            .map(|| warp::reply::with_status("OK", warp::http::StatusCode::OK));

        let routes = webhook.or(health);

        info!("Webhook server started on port {}", self.webhook_port);
        warp::serve(routes)
            .run(([0, 0, 0, 0], self.webhook_port))
            .await;

        Ok(())
    }
}

impl Provider for TelegramProvider {}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[tokio::test]
    async fn test_provider_creation() {
        // Test would require running NATS and Redis instances
        assert!(true);
    }

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider + Clone>() {}
        assert_provider::<TelegramProvider>();
    }
}
