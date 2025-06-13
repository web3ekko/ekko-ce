use anyhow::Result;
use tracing::{info, error};
use std::sync::Arc;

mod config;
mod event_schema;
mod simple_consumer;

// Re-export commonly used types
pub use event_schema::{BlockchainEvent, EventType, EntityType};

use config::Config;
use simple_consumer::SimpleNatsConsumer;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    info!("🚀 Starting Ekko Transactions Writer Service");

    // Load configuration
    let config = Config::from_env()?;
    info!("📋 Configuration loaded: {}", config.service_name);

    // Initialize simple metrics server
    let metrics_port = config.metrics_port;
    tokio::spawn(async move {
        if let Err(e) = start_metrics_server(metrics_port).await {
            error!("Metrics server error: {}", e);
        }
    });
    info!("📊 Metrics server started on port {}", config.metrics_port);

    // Initialize NATS Consumer
    let consumer = Arc::new(
        SimpleNatsConsumer::new(config.clone()).await?
    );
    info!("📡 NATS Consumer initialized");

    // Start the consumer
    let service_handle = tokio::spawn({
        let consumer = consumer.clone();
        async move {
            if let Err(e) = consumer.start().await {
                error!("NATS Consumer error: {}", e);
            }
        }
    });

    info!("✅ Service started successfully");

    // Wait for shutdown signal
    tokio::select! {
        _ = tokio::signal::ctrl_c() => {
            info!("🛑 Received shutdown signal");
        }
        result = service_handle => {
            if let Err(e) = result {
                error!("Delta Writer service panicked: {}", e);
            }
        }
    }

    info!("🔄 Shutting down gracefully...");

    // Show stored events
    let stored_events = consumer.get_stored_events().await;
    for (key, events) in stored_events.iter() {
        info!("📊 Stored {} events for {}", events.len(), key);
    }

    info!("👋 Transactions Writer Service stopped");
    Ok(())
}

async fn start_metrics_server(port: u16) -> Result<()> {
    use hyper::Server;
    use hyper::service::{make_service_fn, service_fn};
    use std::convert::Infallible;
    use std::net::SocketAddr;

    let make_svc = make_service_fn(|_conn| async {
        Ok::<_, Infallible>(service_fn(handle_metrics))
    });

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    let server = Server::bind(&addr).serve(make_svc);

    info!("📊 Metrics server listening on http://{}", addr);

    if let Err(e) = server.await {
        error!("Metrics server error: {}", e);
    }

    Ok(())
}

async fn handle_metrics(_req: hyper::Request<hyper::Body>) -> Result<hyper::Response<hyper::Body>, std::convert::Infallible> {
    let metrics = r#"# HELP transactions_writer_status Service status
# TYPE transactions_writer_status gauge
transactions_writer_status 1

# HELP events_received_total Total events received
# TYPE events_received_total counter
events_received_total 0

# HELP events_processed_total Total events processed
# TYPE events_processed_total counter
events_processed_total 0
"#;

    Ok(hyper::Response::new(hyper::Body::from(metrics)))
}
