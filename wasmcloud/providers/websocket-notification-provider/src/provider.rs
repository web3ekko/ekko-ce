use crate::auth::AuthService;
use crate::connections::ConnectionManager;
use crate::nats_handler::NatsHandler;
use crate::redis_client::RedisClient;
use crate::websocket_server::{WebSocketMessageSenderImpl, WebSocketServer};
use anyhow::{Context, Result};
use std::sync::Arc;
use tracing::{error, info, warn};

/// WebSocket Notification Provider for wasmCloud
pub struct WebSocketNotificationProvider {
    auth_service: Arc<AuthService>,
    connection_manager: Arc<ConnectionManager>,
    nats_handler: Arc<NatsHandler>,
    redis_client: Arc<RedisClient>,
    config: ProviderConfig,
    message_sender: Arc<WebSocketMessageSenderImpl>,
}

/// Provider configuration
#[derive(Debug, Clone)]
pub struct ProviderConfig {
    pub websocket_port: u16,
    pub max_connections: usize,
    pub max_connections_per_user: usize,
    pub redis_url: String,
    pub nats_url: String,
    pub heartbeat_interval_secs: u64,
    pub connection_timeout_secs: u64,
}

fn mask_url(url: &str) -> String {
    let Some((scheme, rest)) = url.split_once("://") else {
        return url.to_string();
    };
    let Some((creds, host)) = rest.split_once('@') else {
        return url.to_string();
    };
    if creds.is_empty() {
        return url.to_string();
    }
    format!("{scheme}://***@{host}")
}

impl Default for ProviderConfig {
    fn default() -> Self {
        Self {
            websocket_port: std::env::var("WEBSOCKET_PORT")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(8080),
            max_connections: std::env::var("MAX_CONNECTIONS")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(10000),
            max_connections_per_user: std::env::var("MAX_CONNECTIONS_PER_USER")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(10),
            redis_url: std::env::var("REDIS_URL").unwrap_or_else(|_| {
                "redis://:redis123@redis-master.ekko.svc.cluster.local:6379".to_string()
            }),
            nats_url: std::env::var("NATS_URL")
                .unwrap_or_else(|_| "nats://127.0.0.1:4222".to_string()),
            heartbeat_interval_secs: std::env::var("HEARTBEAT_INTERVAL_SECS")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(30),
            connection_timeout_secs: std::env::var("CONNECTION_TIMEOUT_SECS")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(300),
        }
    }
}

impl WebSocketNotificationProvider {
    /// Create a new provider instance
    pub async fn new(config: ProviderConfig) -> Result<Self> {
        info!("Initializing WebSocket Notification Provider");
        info!(
            "Config: websocket_port={}, max_connections={}, max_connections_per_user={}, heartbeat_interval_secs={}, connection_timeout_secs={}",
            config.websocket_port,
            config.max_connections,
            config.max_connections_per_user,
            config.heartbeat_interval_secs,
            config.connection_timeout_secs
        );
        info!("Config: redis_url={}", mask_url(&config.redis_url));
        info!("Config: nats_url={}", config.nats_url);

        // Initialize Redis client
        info!("Connecting to Redis...");
        let mut redis_client =
            RedisClient::new(&config.redis_url).context("Failed to create Redis client")?;
        redis_client
            .connect()
            .await
            .context("Failed to connect to Redis")?;
        match redis_client.ping().await {
            Ok(true) => info!("Redis ping OK"),
            Ok(false) => warn!("Redis ping returned non-PONG response"),
            Err(e) => warn!("Redis ping failed: {}", e),
        }
        let redis_client = Arc::new(redis_client);

        // Initialize connection manager
        let connection_manager = Arc::new(ConnectionManager::new());

        // Initialize auth service
        let auth_service = Arc::new(AuthService::new(
            redis_client.clone() as Arc<dyn crate::auth::RedisClientTrait>,
            config.max_connections_per_user,
        ));

        // Initialize WebSocket message sender - SINGLE instance shared between NatsHandler and WebSocketServer
        let message_sender = Arc::new(WebSocketMessageSenderImpl::new(connection_manager.clone()));

        // Initialize NATS client and handler
        info!("Connecting to NATS...");
        let nats_client = async_nats::connect(&config.nats_url)
            .await
            .context("Failed to connect to NATS")?;
        info!("Connected to NATS");
        let nats_handler = Arc::new(NatsHandler::new(
            nats_client,
            connection_manager.clone(),
            message_sender.clone() as Arc<dyn crate::nats_handler::MessageSender>,
            redis_client.clone(),
        ));

        Ok(Self {
            auth_service,
            connection_manager,
            nats_handler,
            redis_client,
            config,
            message_sender, // Store for use in WebSocket server
        })
    }

    /// Start the provider
    pub async fn start(&self) -> Result<()> {
        info!(
            "Starting WebSocket server on port {}",
            self.config.websocket_port
        );

        // Start NATS subscription
        tokio::spawn({
            let nats_handler = self.nats_handler.clone();
            async move {
                if let Err(e) = nats_handler.start().await {
                    error!("NATS handler error: {}", e);
                } else {
                    warn!("NATS handler exited unexpectedly without error");
                }
            }
        });

        // Start WebSocket server
        if let Err(e) = self.start_websocket_server().await {
            error!("WebSocket server failed to start: {}", e);
            return Err(e);
        }

        Ok(())
    }

    /// Start the WebSocket server
    async fn start_websocket_server(&self) -> Result<()> {
        // Use the shared message_sender so NatsHandler and WebSocketServer use the same tx_map
        let ws_server = WebSocketServer::new(
            self.config.clone(),
            self.auth_service.clone(),
            self.connection_manager.clone(),
            self.message_sender.clone(),
        );

        ws_server.start().await
    }
}

// WebSocket message sender is now implemented in websocket_server.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_provider_config_default() {
        let config = ProviderConfig::default();
        assert_eq!(config.websocket_port, 8080);
        assert_eq!(config.max_connections, 10000);
        assert_eq!(config.max_connections_per_user, 10);
        assert_eq!(config.heartbeat_interval_secs, 30);
        assert_eq!(config.connection_timeout_secs, 300);
    }

    #[test]
    fn test_provider_config_custom() {
        let config = ProviderConfig {
            websocket_port: 9090,
            max_connections: 5000,
            max_connections_per_user: 5,
            redis_url: "redis://redis:6379".to_string(),
            nats_url: "nats://nats:4222".to_string(),
            heartbeat_interval_secs: 60,
            connection_timeout_secs: 600,
        };

        assert_eq!(config.websocket_port, 9090);
        assert_eq!(config.max_connections, 5000);
        assert_eq!(config.max_connections_per_user, 5);
    }
}
