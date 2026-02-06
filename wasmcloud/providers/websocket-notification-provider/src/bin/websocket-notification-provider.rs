use anyhow::Result;
use websocket_notification_provider::provider::{ProviderConfig, WebSocketNotificationProvider};

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing/logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    tracing::info!("Starting WebSocket Notification Provider");

    // Load configuration from environment or use defaults
    let config = ProviderConfig::default();

    // Initialize and start the provider
    let provider = WebSocketNotificationProvider::new(config).await?;
    provider.start().await?;

    Ok(())
}
