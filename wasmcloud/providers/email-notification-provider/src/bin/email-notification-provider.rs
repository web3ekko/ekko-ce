//! # Email Notification wasmCloud Provider Binary
//!
//! Entry point for the Email Notification capability provider.
//! This binary is deployed to wasmCloud and handles actor invocations.
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::{Context, Result};
use tracing::info;
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use email_notification_provider::{EmailConfig, EmailProvider};
use redis::aio::ConnectionManager;
use std::env;

/// Main entry point for wasmCloud provider binary
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging with environment filter
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("email_notification_provider=info".parse()?),
        )
        .init();

    info!("🌟 Starting Email Notification Provider for wasmCloud");

    // Load host data from wasmCloud
    let host_data = load_host_data().context("Failed to load wasmCloud host data")?;

    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);
    info!("Config entries: {}", host_data.config.len());

    // Load configuration from host data config or environment
    let config = if !host_data.config.is_empty() {
        info!("Using configuration from wasmCloud HostData");
        EmailConfig::from_properties(&host_data.config)
            .context("Failed to load email configuration from host data")?
    } else {
        info!("Falling back to environment variables");
        EmailConfig::from_env().context("Failed to load email configuration")?
    };

    // Connect to Redis
    let redis_url = host_data
        .config
        .get("redis_url")
        .cloned()
        .unwrap_or_else(|| {
            env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://redis.ekko.svc.cluster.local:6379".to_string())
        });
    let redis_client = redis::Client::open(redis_url).context("Failed to create Redis client")?;
    let redis_conn = ConnectionManager::new(redis_client)
        .await
        .context("Failed to connect to Redis")?;

    // Create provider instance
    let provider = EmailProvider::new(config, redis_conn)
        .await
        .context("Failed to create Email Notification provider")?;

    info!("🎯 Provider ready - waiting for actor invocations");
    let handler = run_provider(provider, "email-notification-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("👋 Email Notification Provider shutdown complete");
    Ok(())
}
