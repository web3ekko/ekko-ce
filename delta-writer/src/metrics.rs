use anyhow::Result;
use metrics::{counter, gauge, histogram, register_counter, register_gauge, register_histogram};
use metrics_exporter_prometheus::PrometheusBuilder;
use std::net::SocketAddr;
use tokio::task::JoinHandle;
use tracing::info;

/// Initialize metrics collection and Prometheus exporter
pub async fn init_metrics(port: u16) -> Result<JoinHandle<()>> {
    info!("📊 Initializing metrics on port {}", port);

    // Register metrics
    register_counter!("events_received_total", "Total number of events received");
    register_counter!("events_processed_total", "Total number of events processed successfully");
    register_counter!("events_failed_total", "Total number of events that failed processing");
    register_counter!("delta_writes_total", "Total number of Delta table writes");
    register_counter!("delta_write_errors_total", "Total number of Delta write errors");
    
    register_gauge!("events_buffer_size", "Current number of events in buffer");
    register_gauge!("delta_table_size_bytes", "Size of Delta table in bytes");
    register_gauge!("active_connections", "Number of active NATS connections");
    
    register_histogram!("event_processing_duration_seconds", "Time taken to process an event");
    register_histogram!("delta_write_duration_seconds", "Time taken to write to Delta table");
    register_histogram!("batch_size", "Number of events in each batch write");

    // Start Prometheus exporter
    let addr: SocketAddr = format!("0.0.0.0:{}", port).parse()?;
    
    let handle = tokio::spawn(async move {
        let builder = PrometheusBuilder::new();
        if let Err(e) = builder.with_http_listener(addr).install() {
            eprintln!("Failed to start metrics server: {}", e);
        }
    });

    info!("✅ Metrics server started on http://0.0.0.0:{}/metrics", port);
    Ok(handle)
}

/// Metrics helper functions
pub struct Metrics;

impl Metrics {
    /// Record an event received
    pub fn event_received() {
        counter!("events_received_total").increment(1);
    }

    /// Record an event processed successfully
    pub fn event_processed() {
        counter!("events_processed_total").increment(1);
    }

    /// Record an event processing failure
    pub fn event_failed() {
        counter!("events_failed_total").increment(1);
    }

    /// Record a Delta table write
    pub fn delta_write() {
        counter!("delta_writes_total").increment(1);
    }

    /// Record a Delta write error
    pub fn delta_write_error() {
        counter!("delta_write_errors_total").increment(1);
    }

    /// Update buffer size
    pub fn update_buffer_size(size: usize) {
        gauge!("events_buffer_size").set(size as f64);
    }

    /// Update Delta table size
    pub fn update_delta_table_size(size_bytes: u64) {
        gauge!("delta_table_size_bytes").set(size_bytes as f64);
    }

    /// Update active connections count
    pub fn update_active_connections(count: usize) {
        gauge!("active_connections").set(count as f64);
    }

    /// Record event processing duration
    pub fn record_event_processing_duration(duration_seconds: f64) {
        histogram!("event_processing_duration_seconds").record(duration_seconds);
    }

    /// Record Delta write duration
    pub fn record_delta_write_duration(duration_seconds: f64) {
        histogram!("delta_write_duration_seconds").record(duration_seconds);
    }

    /// Record batch size
    pub fn record_batch_size(size: usize) {
        histogram!("batch_size").record(size as f64);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_recording() {
        // Test that metrics can be recorded without panicking
        Metrics::event_received();
        Metrics::event_processed();
        Metrics::event_failed();
        Metrics::delta_write();
        Metrics::delta_write_error();
        Metrics::update_buffer_size(100);
        Metrics::update_delta_table_size(1024);
        Metrics::update_active_connections(5);
        Metrics::record_event_processing_duration(0.001);
        Metrics::record_delta_write_duration(0.1);
        Metrics::record_batch_size(50);
    }
}
