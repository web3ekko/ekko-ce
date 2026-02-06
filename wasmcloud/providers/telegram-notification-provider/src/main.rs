//! # Telegram Notification wasmCloud Provider Binary
//!
//! Entry point for the Telegram Notification capability provider.
//! This binary is deployed to wasmCloud and handles actor invocations.
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::{Context, Result};
use tracing::{error, info};
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use telegram_notification_provider::{ProviderConfig, TelegramProvider};

/// Main entry point for wasmCloud provider binary
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging with environment filter
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("telegram_notification_provider=info".parse()?),
        )
        .init();

    info!("🌟 Starting Telegram Notification Provider for wasmCloud");

    // Load host data from wasmCloud
    let host_data = load_host_data().context("Failed to load wasmCloud host data")?;

    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);
    info!("Config entries: {}", host_data.config.len());

    // Load configuration from host data or environment
    let config = if !host_data.config.is_empty() {
        info!("Using configuration from wasmCloud HostData");
        ProviderConfig::from_properties(&host_data.config)
            .context("Failed to load Telegram configuration from host data")?
    } else {
        info!("Falling back to environment variables");
        ProviderConfig::from_env().context("Failed to load Telegram configuration")?
    };

    info!("Configuration:");
    info!("  NATS_URL: {}", config.nats_url);
    info!("  REDIS_URL: {}", config.redis_url);
    info!("  WEBHOOK_PORT: {}", config.webhook_port);

    // Create provider
    let provider = TelegramProvider::from_config(config)
        .await
        .context("Failed to create Telegram provider")?;

    info!("🎯 Provider ready - waiting for actor invocations");
    let runtime_provider = provider.clone();
    tokio::spawn(async move {
        if let Err(e) = provider.start().await {
            error!("Provider error: {}", e);
        }
    });

    let handler = run_provider(runtime_provider, "telegram-notification-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("👋 Telegram Notification Provider shutdown complete");
    Ok(())
}
