//! # ABI Decoder wasmCloud Provider Binary
//!
//! Entry point for the ABI Decoder capability provider.
//! This binary is deployed to wasmCloud and handles actor invocations.

use anyhow::{Context, Result};
use tracing::info;
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use abi_decoder_provider::AbiDecoderProvider;

/// Main entry point for wasmCloud provider binary
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging with environment filter
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("abi_decoder_provider=info".parse()?),
        )
        .init();

    info!("🌟 Starting ABI Decoder Provider for wasmCloud");

    // Load host data from wasmCloud
    let host_data = load_host_data().context("Failed to load wasmCloud host data")?;

    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);

    // Create provider instance
    let provider = AbiDecoderProvider::from_host_data(host_data.clone())
        .await
        .context("Failed to create ABI Decoder provider")?;

    info!("🎯 Provider ready - waiting for actor invocations");

    // Run provider (blocks until shutdown signal)
    run_provider(provider, "abi-decoder-provider")
        .await
        .context("Provider runtime error")?;

    info!("👋 ABI Decoder Provider shutdown complete");
    Ok(())
}
