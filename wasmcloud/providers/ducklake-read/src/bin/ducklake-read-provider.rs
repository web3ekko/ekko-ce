//! DuckLake Read Provider binary entry point
//!
//! This binary runs as a wasmCloud capability provider for executing
//! SQL queries against DuckLake.
//!
//! Uses wasmCloud provider runtime for lifecycle management.

use anyhow::{Context, Result};
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{debug, error, info, warn};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use ducklake_read_provider::DuckLakeReadProvider;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(fmt::layer())
        .with(
            EnvFilter::from_default_env()
                .add_directive("ducklake_read_provider=info".parse()?)
                .add_directive("ducklake_common=info".parse()?),
        )
        .init();

    info!("═══════════════════════════════════════════════════════════════");
    info!("  DuckLake Read Provider - Starting");
    info!("  Ekko Blockchain Data Platform - v1.0.0");
    info!("═══════════════════════════════════════════════════════════════");

    // Load configuration from wasmCloud HostData (fallback to env vars for local runs)
    let config: HashMap<String, String> = match load_host_data() {
        Ok(host_data) => {
            info!("[MAIN] ✅ Successfully received HostData from wasmCloud");
            info!("[MAIN] Host ID: {:?}", host_data.host_id);
            info!("[MAIN] Provider Key: {:?}", host_data.provider_key);
            info!("[MAIN] Config entries: {}", host_data.config.len());
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

    let provider = DuckLakeReadProvider::with_config(config)?;
    let runtime_provider = provider.clone();
    let provider = Arc::new(provider);

    info!("Provider initialized");

    info!("═══════════════════════════════════════════════════════════════");
    info!("  PROVIDER READY - Waiting for shutdown signal");
    info!("═══════════════════════════════════════════════════════════════");
    info!("[MAIN] Provider will run until SIGTERM/SIGINT");

    // Use Unix signals for shutdown - these work reliably in Kubernetes/OrbStack
    // NOTE: Do NOT use stdin monitoring - it fails in container environments
    // where stdin is closed immediately or connected to /dev/null.
    debug!("[TRACE] Setting up shutdown signal handlers...");

    tokio::spawn(async move {
        if let Err(e) = provider.start().await {
            error!("Provider error: {}", e);
        }
    });

    let handler = run_provider(runtime_provider, "ducklake-read-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("═══════════════════════════════════════════════════════════════");
    info!("  SHUTDOWN SEQUENCE INITIATED");
    info!("═══════════════════════════════════════════════════════════════");
    info!("[SHUTDOWN] DuckLake Read Provider shutdown complete");
    Ok(())
}
