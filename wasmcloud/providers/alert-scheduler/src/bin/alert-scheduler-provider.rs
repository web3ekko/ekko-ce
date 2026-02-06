//! # Alert Scheduler wasmCloud Provider Binary
//!
//! Entry point for the Alert Scheduler capability provider.
//! This binary is deployed to wasmCloud and handles actor invocations.
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::{Context, Result};
use tracing::info;
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use alert_scheduler_provider::AlertSchedulerProvider;

/// Main entry point for wasmCloud provider binary
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging with environment filter
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("alert_scheduler_provider=info".parse()?),
        )
        .init();

    info!("🌟 Starting Alert Scheduler Provider for wasmCloud");

    // Load host data from wasmCloud
    let host_data = load_host_data().context("Failed to load wasmCloud host data")?;

    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);
    info!("Config entries: {}", host_data.config.len());

    // Create provider instance
    let provider = AlertSchedulerProvider::from_host_data(host_data.clone())
        .await
        .context("Failed to create Alert Scheduler provider")?;

    info!("🎯 Provider ready - waiting for actor invocations");
    let handler = run_provider(provider, "alert-scheduler-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("👋 Alert Scheduler Provider shutdown complete");
    Ok(())
}
