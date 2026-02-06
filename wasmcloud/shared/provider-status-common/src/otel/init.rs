//! OpenTelemetry initialization for wasmCloud providers.
//!
//! This module initializes OTEL tracing and metrics to integrate with
//! wasmCloud's built-in observability infrastructure.

use anyhow::{Context, Result};
use opentelemetry::global;
use opentelemetry::KeyValue;
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::{
    runtime::Tokio,
    trace::{self, Sampler},
    Resource,
};
use opentelemetry_semantic_conventions as semconv;
use tracing::info;
use tracing_opentelemetry::OpenTelemetryLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

/// Configuration for OTEL initialization
#[derive(Debug, Clone)]
pub struct OtelConfig {
    /// Service name for traces/metrics
    pub service_name: String,
    /// Service version
    pub service_version: String,
    /// OTLP endpoint (default: http://localhost:4318)
    pub endpoint: String,
    /// Enable tracing
    pub enable_tracing: bool,
    /// Enable metrics
    pub enable_metrics: bool,
    /// Sample ratio (0.0 - 1.0)
    pub sample_ratio: f64,
}

impl OtelConfig {
    /// Create config from environment variables (wasmCloud native pattern)
    pub fn from_env(service_name: &str, service_version: &str) -> Self {
        let endpoint = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT")
            .unwrap_or_else(|_| "http://localhost:4318".to_string());

        let enabled = std::env::var("WASMCLOUD_OBSERVABILITY_ENABLED")
            .map(|v| v == "true")
            .unwrap_or(false);

        let sample_ratio: f64 = std::env::var("OTEL_TRACES_SAMPLER_ARG")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(1.0);

        Self {
            service_name: std::env::var("OTEL_SERVICE_NAME")
                .unwrap_or_else(|_| service_name.to_string()),
            service_version: service_version.to_string(),
            endpoint,
            enable_tracing: enabled,
            enable_metrics: enabled,
            sample_ratio,
        }
    }
}

impl Default for OtelConfig {
    fn default() -> Self {
        Self {
            service_name: "provider".to_string(),
            service_version: "0.0.0".to_string(),
            endpoint: "http://localhost:4318".to_string(),
            enable_tracing: false,
            enable_metrics: false,
            sample_ratio: 1.0,
        }
    }
}

/// Initialize OpenTelemetry with wasmCloud-compatible configuration.
///
/// This function sets up:
/// - OTLP exporter pointing to wasmCloud's OTEL collector
/// - Tracing with span propagation
/// - Integration with the `tracing` crate for automatic instrumentation
///
/// # Arguments
/// * `config` - OTEL configuration
///
/// # Returns
/// Result indicating success or failure
///
/// # Example
/// ```ignore
/// use provider_status_common::otel::{init_otel, OtelConfig};
///
/// let config = OtelConfig::from_env("newheads-evm", "1.0.0");
/// init_otel(&config)?;
/// ```
pub fn init_otel(config: &OtelConfig) -> Result<()> {
    info!(
        service = %config.service_name,
        endpoint = %config.endpoint,
        "Initializing OpenTelemetry"
    );

    // Build resource with service info
    let resource = Resource::new(vec![
        KeyValue::new(semconv::resource::SERVICE_NAME, config.service_name.clone()),
        KeyValue::new(
            semconv::resource::SERVICE_VERSION,
            config.service_version.clone(),
        ),
        KeyValue::new("deployment.environment", "wasmcloud"),
    ]);

    // Initialize tracer if enabled
    if config.enable_tracing {
        let exporter = opentelemetry_otlp::new_exporter()
            .http()
            .with_endpoint(&config.endpoint);

        let sampler = if config.sample_ratio >= 1.0 {
            Sampler::AlwaysOn
        } else if config.sample_ratio <= 0.0 {
            Sampler::AlwaysOff
        } else {
            Sampler::TraceIdRatioBased(config.sample_ratio)
        };

        // Build the tracer using the pipeline - install_batch returns a Tracer directly
        let tracer = opentelemetry_otlp::new_pipeline()
            .tracing()
            .with_exporter(exporter)
            .with_trace_config(
                trace::Config::default()
                    .with_resource(resource)
                    .with_sampler(sampler),
            )
            .install_batch(Tokio)
            .context("Failed to install OTLP tracer")?;

        // Build tracing subscriber with OTEL layer
        let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| {
            EnvFilter::new("info").add_directive(
                format!("{}=debug", config.service_name.replace('-', "_"))
                    .parse()
                    .unwrap(),
            )
        });

        let fmt_layer = tracing_subscriber::fmt::layer()
            .with_target(true)
            .with_thread_ids(false)
            .with_thread_names(false);

        let otel_layer = OpenTelemetryLayer::new(tracer);

        tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer)
            .with(otel_layer)
            .try_init()
            .map_err(|e| anyhow::anyhow!("Failed to initialize tracing subscriber: {}", e))?;

        info!("OpenTelemetry tracing enabled with OTLP export");
    } else {
        // Build tracing subscriber without OTEL
        let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| {
            EnvFilter::new("info").add_directive(
                format!("{}=debug", config.service_name.replace('-', "_"))
                    .parse()
                    .unwrap(),
            )
        });

        let fmt_layer = tracing_subscriber::fmt::layer()
            .with_target(true)
            .with_thread_ids(false)
            .with_thread_names(false);

        tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer)
            .try_init()
            .map_err(|e| anyhow::anyhow!("Failed to initialize tracing subscriber: {}", e))?;

        info!("Tracing initialized (OTEL disabled)");
    }

    Ok(())
}

/// Shutdown OpenTelemetry gracefully.
///
/// This should be called before provider shutdown to ensure all
/// pending traces and metrics are flushed.
pub fn shutdown_otel() {
    info!("Shutting down OpenTelemetry");
    global::shutdown_tracer_provider();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_otel_config_from_env() {
        // Test default behavior
        std::env::remove_var("WASMCLOUD_OBSERVABILITY_ENABLED");
        std::env::remove_var("OTEL_EXPORTER_OTLP_ENDPOINT");

        let config = OtelConfig::from_env("test-service", "1.0.0");
        assert_eq!(config.service_name, "test-service");
        assert_eq!(config.endpoint, "http://localhost:4318");
        assert!(!config.enable_tracing);
    }
}
