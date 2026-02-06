//! Polars Eval Provider binary entry point
//!
//! Runs as a wasmCloud capability provider, subscribing to `alerts.eval.request.*`
//! and responding with `polars_eval_response_v1` payloads.

use anyhow::{Context, Result};
use std::sync::Arc;
use tracing::{error, info};
use wasmcloud_provider_sdk::{load_host_data, run_provider};

use polars_eval_provider::{NatsEvalListenerConfig, PolarsEvalProvider};

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("polars_eval_provider=info".parse()?),
        )
        .init();

    info!("═══════════════════════════════════════════════════════════════");
    info!("  Polars Eval Provider - Starting");
    info!("═══════════════════════════════════════════════════════════════");

    let host_data = load_host_data().context("Failed to load wasmCloud host data")?;

    info!("Provider ID: {}", host_data.provider_key);
    info!("Lattice RPC URL: {}", host_data.lattice_rpc_url);
    info!("Config entries: {}", host_data.config.len());

    let config = if host_data.config.is_empty() {
        NatsEvalListenerConfig::from_env()
    } else {
        NatsEvalListenerConfig::from_properties(&host_data.config)
    };

    info!("NATS URL: {}", config.nats_url);
    info!("Subscribe subject: {}", config.subscribe_subject);
    info!("Publish prefix: {}", config.publish_prefix);
    info!("Max concurrency: {}", config.max_concurrency);

    let provider = PolarsEvalProvider::with_config(config);
    let runtime_provider = provider.clone();
    let provider = Arc::new(provider);

    tokio::spawn(async move {
        if let Err(e) = provider.start().await {
            error!("provider error: {e:?}");
        }
    });

    let handler = run_provider(runtime_provider, "polars-eval-provider")
        .await
        .context("Provider runtime error")?;
    handler.await;

    info!("Polars Eval Provider shutdown complete");
    Ok(())
}
