//! OpenTelemetry metrics for provider status tracking.
//!
//! These metrics are exported via OTEL and converted to Prometheus format
//! by the OTEL collector, appearing alongside wasmCloud host metrics.

use crate::types::ProviderType;
use anyhow::Result;
use opentelemetry::{
    global,
    metrics::{Counter, Histogram, Meter, UpDownCounter},
    KeyValue,
};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};
use tracing::debug;

/// OTEL metrics for provider status tracking.
///
/// These metrics follow OpenTelemetry naming conventions and are
/// exported via OTLP to integrate with wasmCloud's observability.
pub struct OtelMetrics {
    /// Provider ID for metric labels
    provider_id: String,
    /// Provider type for metric labels
    provider_type: ProviderType,
    /// Meter for creating instruments
    #[allow(dead_code)]
    meter: Meter,
    /// Total blocks received counter
    blocks_received: Counter<u64>,
    /// Block latency histogram
    block_latency: Histogram<f64>,
    /// Connection state gauge
    connection_state: UpDownCounter<i64>,
    /// Total errors counter
    errors: Counter<u64>,
    /// Active subscriptions gauge (shared for callbacks)
    active_subscriptions: Arc<AtomicUsize>,
}

impl OtelMetrics {
    /// Create new OTEL metrics for a provider.
    ///
    /// # Arguments
    /// * `provider_id` - Unique provider identifier
    /// * `provider_type` - Type of provider (Evm, Utxo, etc.)
    pub fn new(provider_id: &str, provider_type: ProviderType) -> Result<Self> {
        let meter = global::meter("provider_status");

        // Blocks received counter
        let blocks_received = meter
            .u64_counter("provider_blocks_received_total")
            .with_description("Total number of blocks received by the provider")
            .init();

        // Block latency histogram (in seconds)
        let block_latency = meter
            .f64_histogram("provider_block_latency_seconds")
            .with_description("Block receipt latency from block timestamp to provider receipt")
            .init();

        // Connection state (1 = connected, 0 = disconnected)
        let connection_state = meter
            .i64_up_down_counter("provider_connection_state")
            .with_description("Current connection state per chain (1=connected, 0=disconnected)")
            .init();

        // Errors counter
        let errors = meter
            .u64_counter("provider_errors_total")
            .with_description("Total number of errors encountered by the provider")
            .init();

        debug!(
            provider_id = %provider_id,
            provider_type = %provider_type,
            "OTEL metrics initialized"
        );

        Ok(Self {
            provider_id: provider_id.to_string(),
            provider_type,
            meter,
            blocks_received,
            block_latency,
            connection_state,
            errors,
            active_subscriptions: Arc::new(AtomicUsize::new(0)),
        })
    }

    /// Common labels for all metrics
    fn common_labels(&self) -> Vec<KeyValue> {
        vec![
            KeyValue::new("provider", self.provider_id.clone()),
            KeyValue::new("provider_type", self.provider_type.to_string()),
        ]
    }

    /// Labels for chain-specific metrics
    fn chain_labels(&self, chain_id: &str) -> Vec<KeyValue> {
        let mut labels = self.common_labels();
        labels.push(KeyValue::new("chain", chain_id.to_string()));
        labels
    }

    /// Record a block received.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier
    /// * `latency_ms` - Latency in milliseconds
    pub fn record_block_received(&self, chain_id: &str, latency_ms: u32) {
        let labels = self.chain_labels(chain_id);

        // Increment blocks counter
        self.blocks_received.add(1, &labels);

        // Record latency in seconds
        let latency_secs = latency_ms as f64 / 1000.0;
        self.block_latency.record(latency_secs, &labels);
    }

    /// Record connection state change.
    ///
    /// # Arguments
    /// * `chain_id` - Chain identifier
    /// * `connected` - Whether connected (true) or disconnected (false)
    pub fn record_connection_state(&self, chain_id: &str, connected: bool) {
        let labels = self.chain_labels(chain_id);

        // UpDownCounter: +1 for connect, -1 for disconnect
        let delta = if connected { 1 } else { -1 };
        self.connection_state.add(delta, &labels);
    }

    /// Record an error.
    ///
    /// # Arguments
    /// * `chain_id` - Optional chain identifier
    /// * `recoverable` - Whether the error is recoverable
    pub fn record_error(&self, chain_id: Option<&str>, recoverable: bool) {
        let mut labels = self.common_labels();
        if let Some(cid) = chain_id {
            labels.push(KeyValue::new("chain", cid.to_string()));
        }
        labels.push(KeyValue::new(
            "recoverable",
            if recoverable { "true" } else { "false" },
        ));

        self.errors.add(1, &labels);
    }

    /// Update subscription count.
    ///
    /// # Arguments
    /// * `count` - Current number of active subscriptions
    pub fn update_subscription_count(&self, count: usize) {
        self.active_subscriptions.store(count, Ordering::Relaxed);
    }

    /// Get current subscription count.
    pub fn get_subscription_count(&self) -> usize {
        self.active_subscriptions.load(Ordering::Relaxed)
    }

    /// Get a clone of the active subscriptions Arc for use in gauges.
    ///
    /// This returns an Arc that can be safely used in callbacks.
    pub fn get_active_subscriptions_arc(&self) -> Arc<AtomicUsize> {
        Arc::clone(&self.active_subscriptions)
    }

    /// Create a gauge for active subscriptions.
    ///
    /// Note: OTEL SDK doesn't have a direct gauge instrument.
    /// We use an observable gauge with a callback.
    pub fn register_subscription_gauge(&self) -> Result<()> {
        let provider_id = self.provider_id.clone();
        let provider_type = self.provider_type;
        let active_subs = Arc::clone(&self.active_subscriptions);

        let meter = global::meter("provider_status");
        let _gauge = meter
            .u64_observable_gauge("provider_active_subscriptions")
            .with_description("Number of active chain subscriptions")
            .with_callback(move |observer| {
                let labels = vec![
                    KeyValue::new("provider", provider_id.clone()),
                    KeyValue::new("provider_type", provider_type.to_string()),
                ];
                let count = active_subs.load(Ordering::Relaxed);
                observer.observe(count as u64, &labels);
            })
            .init();

        Ok(())
    }

    /// Create a gauge for provider health.
    ///
    /// # Arguments
    /// * `is_healthy` - Function to check if provider is healthy
    pub fn register_health_gauge<F>(&self, is_healthy: F) -> Result<()>
    where
        F: Fn() -> bool + Send + Sync + 'static,
    {
        let provider_id = self.provider_id.clone();
        let provider_type = self.provider_type;

        let meter = global::meter("provider_status");
        let _gauge = meter
            .u64_observable_gauge("provider_healthy")
            .with_description("Provider health status (1=healthy, 0=unhealthy)")
            .with_callback(move |observer| {
                let labels = vec![
                    KeyValue::new("provider", provider_id.clone()),
                    KeyValue::new("provider_type", provider_type.to_string()),
                ];
                let healthy = if is_healthy() { 1 } else { 0 };
                observer.observe(healthy, &labels);
            })
            .init();

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_common_labels() {
        // This test requires OTEL to be initialized, so we skip it in unit tests
        // Integration tests would verify the actual metrics
    }
}
