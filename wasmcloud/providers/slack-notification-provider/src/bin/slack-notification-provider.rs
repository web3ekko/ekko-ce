//! # Slack Notification wasmCloud Provider Binary
//!
//! Entry point for the Slack Notification capability provider.
//! This binary is deployed to wasmCloud and handles actor invocations.
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::{Context, Result};
use tracing::info;
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use slack_notification_provider::{ProviderConfig, SlackNotificationProvider};

/// Main entry point for wasmCloud provider binary
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging with environment filter
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("slack_notification_provider=info".parse()?),
        )
        .init();

    info!("🌟 Starting Slack Notification Provider for wasmCloud");

    // Load host data from wasmCloud
    let host_data = load_host_data().context("Failed to load wasmCloud host data")?;

    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);
    info!("Config entries: {}", host_data.config.len());

    // Load configuration from host data or environment
    let config = if !host_data.config.is_empty() {
        info!("Using configuration from wasmCloud HostData");
        ProviderConfig::from_properties(&host_data.config)
            .context("Failed to load Slack configuration from host data")?
    } else {
        info!("Falling back to environment variables");
        ProviderConfig::from_env().context("Failed to load Slack configuration")?
    };

    // Create and start provider
    let provider = SlackNotificationProvider::new(config)
        .await
        .context("Failed to create Slack Notification provider")?;

    info!("🎯 Provider ready - waiting for actor invocations");
    let runtime_provider = provider.clone();
    tokio::spawn(async move {
        if let Err(e) = provider.start().await {
            tracing::error!("Failed to start Slack Notification provider: {}", e);
        }
    });

    let handler = run_provider(runtime_provider, "slack-notification-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("👋 Slack Notification Provider shutdown complete");
    Ok(())
}
