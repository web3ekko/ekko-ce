//! OpenTelemetry integration for provider status tracking.
//!
//! This module provides OTEL initialization and metrics emission that integrates
//! with wasmCloud's built-in observability infrastructure. When wasmCloud
//! observability is enabled (`WASMCLOUD_OBSERVABILITY_ENABLED=true`), providers
//! export metrics and traces to the same OTEL collector as the host.

pub mod init;
pub mod metrics;

pub use init::{init_otel, shutdown_otel, OtelConfig};
pub use metrics::OtelMetrics;
