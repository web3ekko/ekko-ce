//! # HTTP RPC wasmCloud Provider Binary
//!
//! Entry point for the HTTP RPC capability provider.
//! This binary is deployed to wasmCloud and handles actor invocations.
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::{Context, Result};
use tracing::info;
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use http_rpc_provider::HttpRpcProvider;

/// Main entry point for wasmCloud provider binary
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging with environment filter
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("http_rpc_provider=info".parse()?),
        )
        .init();

    info!("🌟 Starting HTTP RPC Provider for wasmCloud");

    // Load host data from wasmCloud
    let host_data = load_host_data().context("Failed to load wasmCloud host data")?;

    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);

    // Create provider instance
    let provider = HttpRpcProvider::from_host_data(host_data.clone())
        .context("Failed to create HTTP RPC provider")?;

    info!("🎯 Provider ready - waiting for actor invocations");
    let handler = run_provider(provider, "http-rpc-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("👋 HTTP RPC Provider shutdown complete");
    Ok(())
}
