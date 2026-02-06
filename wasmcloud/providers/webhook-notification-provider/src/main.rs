//! # Webhook Notification wasmCloud Provider Binary
//!
//! Entry point for the Webhook Notification capability provider.
//! This binary is deployed to wasmCloud and handles actor invocations.
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::{Context, Result};
use tracing::{error, info};
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use webhook_notification_provider::{ProviderConfig, WebhookProvider};

/// Main entry point for wasmCloud provider binary
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging with environment filter
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("webhook_notification_provider=info".parse()?),
        )
        .init();

    info!("🌟 Starting Webhook Notification Provider for wasmCloud");

    // Load host data from wasmCloud
    let host_data = load_host_data().context("Failed to load wasmCloud host data")?;

    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);
    info!("Config entries: {}", host_data.config.len());

    // Load configuration from host data or environment
    let config = if !host_data.config.is_empty() {
        info!("Using configuration from wasmCloud HostData");
        ProviderConfig::from_properties(&host_data.config)
            .context("Failed to load Webhook configuration from host data")?
    } else {
        info!("Falling back to environment variables");
        ProviderConfig::from_env().context("Failed to load Webhook configuration")?
    };

    info!("Configuration:");
    info!("  NATS URL: {}", config.nats_url);
    info!("  Redis URL: {}", config.redis_url);

    // Create provider
    let provider = WebhookProvider::from_config(config)
        .await
        .context("Failed to create Webhook provider")?;

    info!("🎯 Provider ready - waiting for actor invocations");
    let runtime_provider = provider.clone();
    tokio::spawn(async move {
        if let Err(e) = provider.run().await {
            error!("Provider error: {}", e);
        }
    });

    let handler = run_provider(runtime_provider, "webhook-notification-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("👋 Webhook Notification Provider shutdown complete");
    Ok(())
}
