//! DuckLake Write Provider binary entry point
//!
//! This binary runs as a wasmCloud capability provider for writing
//! blockchain data to DuckLake via NATS subjects.
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::{Context, Result};
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{debug, error, info, warn};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use ducklake_write_provider::DuckLakeWriteProvider;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing - include ducklake_common for connection debugging
    tracing_subscriber::registry()
        .with(fmt::layer())
        .with(
            EnvFilter::from_default_env()
                .add_directive("ducklake_write_provider=info".parse()?)
                .add_directive("ducklake_common=info".parse()?)
                .add_directive("duckdb=warn".parse()?),
        )
        .init();

    info!("═══════════════════════════════════════════════════════════════");
    info!("  DuckLake Write Provider - Starting");
    info!("  Ekko Blockchain Data Platform - v1.0.0");
    info!("═══════════════════════════════════════════════════════════════");

    // Load configuration from wasmCloud HostData
    info!("[MAIN] Loading configuration from wasmCloud HostData...");
    let config: HashMap<String, String> = match load_host_data() {
        Ok(host_data) => {
            info!("[MAIN] ✅ Successfully received HostData from wasmCloud");
            info!("[MAIN] Host ID: {:?}", host_data.host_id);
            info!("[MAIN] Lattice RPC URL: {:?}", host_data.lattice_rpc_url);
            info!("[MAIN] Provider Key: {:?}", host_data.provider_key);
            info!("[MAIN] Config entries: {}", host_data.config.len());
            info!(
                "[MAIN] Config keys: {:?}",
                host_data.config.keys().collect::<Vec<_>>()
            );

            // Log each config value for debugging
            for (key, value) in &host_data.config {
                // Mask sensitive values
                let masked_value = if key.to_lowercase().contains("password")
                    || key.to_lowercase().contains("secret")
                    || key.to_lowercase().contains("key")
                {
                    "***MASKED***".to_string()
                } else {
                    value.clone()
                };
                info!("[MAIN] Config: {} = {}", key, masked_value);
            }

            host_data.config.clone()
        }
        Err(e) => {
            warn!(
                "[MAIN] ❌ Failed to load HostData: {}. Falling back to env vars.",
                e
            );
            HashMap::new()
        }
    };

    // Create provider with config
    let provider = DuckLakeWriteProvider::with_config(config)?;
    let runtime_provider = provider.clone();
    let provider = Arc::new(provider);

    info!("Provider initialized");

    info!("═══════════════════════════════════════════════════════════════");
    info!("  PROVIDER READY - Waiting for shutdown signal");
    info!("═══════════════════════════════════════════════════════════════");
    info!("[MAIN] Provider will run until SIGTERM/SIGINT");

    // Use Unix signals for shutdown - these work reliably in Kubernetes/OrbStack
    debug!("[TRACE] Setting up shutdown signal handlers...");

    tokio::spawn(async move {
        if let Err(e) = provider.start().await {
            error!("Provider error: {}", e);
        }
    });

    let handler = run_provider(runtime_provider, "ducklake-write-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("═══════════════════════════════════════════════════════════════");
    info!("  SHUTDOWN SEQUENCE INITIATED");
    info!("═══════════════════════════════════════════════════════════════");
    info!("[SHUTDOWN] DuckLake Write Provider shutdown complete");
    Ok(())
}
