//! Provider status tracker implementation.
//!
//! This module contains the main `ProviderStatusTracker` that implements
//! the `StatusTracker` trait with Redis persistence and OTEL metrics.

use crate::redis_storage::RedisStorage;
use crate::traits::{StatusTracker, StatusTrackerConfig};
use crate::types::{BlockInfo, ErrorRecord, ProviderStatus, SubscriptionState, SubscriptionStatus};
use async_trait::async_trait;
use chrono::Utc;
use parking_lot::RwLock;
use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::{debug, error, info, instrument, warn};

#[cfg(feature = "otel")]
use crate::otel::metrics::OtelMetrics;

/// Message types for the background flush task
enum FlushMessage {
    Flush,
    Shutdown,
}

/// Provider status tracker with Redis persistence and OTEL metrics.
///
/// This is the main implementation of `StatusTracker` that:
/// - Maintains in-memory state for fast reads
/// - Batches high-frequency updates (block receipts) for Redis
/// - Immediately persists critical state changes (connections, errors)
/// - Exports metrics via OpenTelemetry when enabled
pub struct ProviderStatusTracker {
    /// Configuration
    config: StatusTrackerConfig,
    /// Current provider status (in-memory)
    status: Arc<RwLock<ProviderStatus>>,
    /// Redis storage layer
    redis: Arc<RedisStorage>,
    /// Channel to trigger flushes
    flush_tx: mpsc::Sender<FlushMessage>,
    /// OTEL metrics (when enabled)
    #[cfg(feature = "otel")]
    metrics: Option<Arc<OtelMetrics>>,
}

impl ProviderStatusTracker {
    /// Create a new provider status tracker.
    ///
    /// # Arguments
    /// * `config` - Tracker configuration
    ///
    /// # Returns
    /// A new tracker instance or an error if initialization fails
    pub async fn new(config: StatusTrackerConfig) -> anyhow::Result<Arc<Self>> {
        info!(
            provider_id = %config.provider_id,
            provider_type = %config.provider_type,
            "Initializing provider status tracker"
        );

        // Initialize Redis storage
        let redis = Arc::new(RedisStorage::new(&config.redis_url).await?);

        // Initialize provider status
        let status =
            ProviderStatus::new(&config.provider_id, config.provider_type, &config.version);

        // Set lattice ID if provided
        let mut status = status;
        status.lattice_id = config.lattice_id.clone();

        let status = Arc::new(RwLock::new(status));

        // Initialize OTEL metrics if enabled
        #[cfg(feature = "otel")]
        let metrics = if config.enable_otel {
            match OtelMetrics::new(&config.provider_id, config.provider_type) {
                Ok(m) => {
                    info!("OTEL metrics enabled for provider");
                    Some(Arc::new(m))
                }
                Err(e) => {
                    warn!("Failed to initialize OTEL metrics: {}", e);
                    None
                }
            }
        } else {
            None
        };

        // Create flush channel
        let (flush_tx, flush_rx) = mpsc::channel::<FlushMessage>(16);

        let tracker = Arc::new(Self {
            config: config.clone(),
            status: status.clone(),
            redis: redis.clone(),
            flush_tx,
            #[cfg(feature = "otel")]
            metrics,
        });

        // Register provider in Redis
        tracker.register_provider().await?;

        // Start background flush task
        let tracker_clone = tracker.clone();
        tokio::spawn(async move {
            tracker_clone.flush_loop(flush_rx).await;
        });

        Ok(tracker)
    }

    /// Register provider in Redis registry
    async fn register_provider(&self) -> anyhow::Result<()> {
        self.redis
            .register_provider(&self.config.provider_id, self.config.provider_type)
            .await
    }

    /// Background loop for periodic flushing
    async fn flush_loop(self: Arc<Self>, mut rx: mpsc::Receiver<FlushMessage>) {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(
            self.config.flush_interval_secs,
        ));

        loop {
            tokio::select! {
                _ = interval.tick() => {
                    if let Err(e) = self.do_flush().await {
                        error!("Failed to flush status to Redis: {}", e);
                    }
                }
                msg = rx.recv() => {
                    match msg {
                        Some(FlushMessage::Flush) => {
                            if let Err(e) = self.do_flush().await {
                                error!("Failed to flush status to Redis: {}", e);
                            }
                        }
                        Some(FlushMessage::Shutdown) | None => {
                            info!("Status tracker flush loop shutting down");
                            // Final flush
                            let _ = self.do_flush().await;
                            break;
                        }
                    }
                }
            }
        }
    }

    /// Perform the actual flush to Redis
    async fn do_flush(&self) -> anyhow::Result<()> {
        let status = self.status.read().clone();

        // Update heartbeat
        {
            let mut status_write = self.status.write();
            status_write.last_heartbeat = Utc::now();
        }

        // Write to Redis
        self.redis
            .write_provider_status(&status, self.config.status_ttl_secs)
            .await?;

        debug!(provider_id = %status.provider_id, "Flushed status to Redis");
        Ok(())
    }

    /// Update subscription state and persist immediately if critical
    fn update_subscription_state(&self, chain_id: &str, new_state: SubscriptionState) {
        let mut status = self.status.write();
        if let Some(sub) = status.subscriptions.get_mut(chain_id) {
            if sub.state != new_state {
                sub.state = new_state;
                sub.state_changed_at = Utc::now();
            }
        }
        status.update_health();
    }
}

#[async_trait]
impl StatusTracker for ProviderStatusTracker {
    #[instrument(skip(self), fields(chain_id = %chain_id, block = %block_number, latency = %latency_ms))]
    async fn record_block_received(&self, chain_id: &str, block_number: u64, latency_ms: u32) {
        let now = Utc::now();

        // Update in-memory state
        {
            let mut status = self.status.write();
            if let Some(sub) = status.subscriptions.get_mut(chain_id) {
                // Update last block
                sub.last_block = Some(BlockInfo {
                    number: block_number,
                    hash: String::new(), // Will be set by caller if needed
                    timestamp: now,
                    received_at: now,
                    latency_ms,
                });

                // Update metrics
                sub.metrics.blocks_received += 1;
                sub.metrics.blocks_last_minute += 1;

                // Update average latency (simple moving average)
                let n = sub.metrics.blocks_received as f64;
                sub.metrics.avg_latency_ms =
                    (sub.metrics.avg_latency_ms * (n - 1.0) + latency_ms as f64) / n;

                // Update p99 (simplified - in production use reservoir sampling)
                if latency_ms as f64 > sub.metrics.p99_latency_ms {
                    sub.metrics.p99_latency_ms = latency_ms as f64;
                }

                sub.metrics.updated_at = now;

                // Ensure state is Active if receiving blocks
                if sub.state != SubscriptionState::Active {
                    sub.state = SubscriptionState::Active;
                    sub.state_changed_at = now;
                }
            }
            status.update_health();
        }

        // Update OTEL metrics
        #[cfg(feature = "otel")]
        if let Some(ref metrics) = self.metrics {
            metrics.record_block_received(chain_id, latency_ms);
        }

        debug!(
            "Recorded block {} from {} (latency: {}ms)",
            block_number, chain_id, latency_ms
        );
    }

    #[instrument(skip(self), fields(chain_id = %chain_id, connected = %connected))]
    async fn record_connection_change(&self, chain_id: &str, connected: bool) {
        let now = Utc::now();

        // Update in-memory state
        let new_state = if connected {
            SubscriptionState::Active
        } else {
            SubscriptionState::Reconnecting
        };

        {
            let mut status = self.status.write();
            if let Some(sub) = status.subscriptions.get_mut(chain_id) {
                sub.connection.connected = connected;
                if connected {
                    sub.connection.connected_at = Some(now);
                    sub.connection.reconnect_attempts = 0;
                } else {
                    sub.connection.disconnected_at = Some(now);
                }
                sub.state = new_state;
                sub.state_changed_at = now;
            }
            status.update_health();
        }

        // Update OTEL metrics
        #[cfg(feature = "otel")]
        if let Some(ref metrics) = self.metrics {
            metrics.record_connection_state(chain_id, connected);
        }

        // Immediately flush for connection changes
        let _ = self.flush_tx.try_send(FlushMessage::Flush);

        if connected {
            info!("Chain {} connected", chain_id);
        } else {
            warn!("Chain {} disconnected", chain_id);
        }
    }

    #[instrument(skip(self), fields(chain_id = ?chain_id, recoverable = %recoverable))]
    async fn record_error(&self, chain_id: Option<&str>, error: &str, recoverable: bool) {
        let now = Utc::now();

        let error_record = ErrorRecord {
            message: error.to_string(),
            recoverable,
            occurred_at: now,
            code: None,
            chain_id: chain_id.map(String::from),
        };

        // Update in-memory state
        {
            let mut status = self.status.write();

            if let Some(cid) = chain_id {
                if let Some(sub) = status.subscriptions.get_mut(cid) {
                    sub.error_history.add_error(error_record.clone());

                    if recoverable {
                        sub.metrics.processing_errors += 1;
                    } else {
                        sub.metrics.connection_errors += 1;
                        sub.state = SubscriptionState::Error;
                        sub.state_changed_at = now;
                    }
                }
            }

            status.update_health();
        }

        // Update OTEL metrics
        #[cfg(feature = "otel")]
        if let Some(ref metrics) = self.metrics {
            metrics.record_error(chain_id, recoverable);
        }

        // Store error in Redis (separate from status for longer retention)
        if let Err(e) = self
            .redis
            .push_error(
                &self.config.provider_id,
                &error_record,
                self.config.error_ttl_secs,
            )
            .await
        {
            error!("Failed to push error to Redis: {}", e);
        }

        // Immediately flush for errors
        let _ = self.flush_tx.try_send(FlushMessage::Flush);

        if recoverable {
            warn!("Recoverable error: {}", error);
        } else {
            error!("Fatal error: {}", error);
        }
    }

    #[instrument(skip(self), fields(chain_id = %chain_id, attempt = %attempt))]
    async fn record_reconnect_attempt(&self, chain_id: &str, attempt: u32) {
        {
            let mut status = self.status.write();
            if let Some(sub) = status.subscriptions.get_mut(chain_id) {
                sub.connection.reconnect_attempts = attempt;
                sub.state = SubscriptionState::Reconnecting;
                sub.state_changed_at = Utc::now();
            }
        }

        info!("Reconnect attempt {} for {}", attempt, chain_id);
    }

    #[instrument(skip(self), fields(chain_id = %chain_id, chain_name = %chain_name))]
    async fn register_subscription(&self, chain_id: &str, chain_name: &str) {
        let sub = SubscriptionStatus::new(chain_id, chain_name);

        {
            let mut status = self.status.write();
            status.subscriptions.insert(chain_id.to_string(), sub);
            status.update_health();
        }

        // Update OTEL metrics
        #[cfg(feature = "otel")]
        if let Some(ref metrics) = self.metrics {
            metrics.update_subscription_count(self.status.read().subscriptions.len());
        }

        // Persist immediately
        let _ = self.flush_tx.try_send(FlushMessage::Flush);

        info!("Registered subscription for {} ({})", chain_name, chain_id);
    }

    async fn unregister_subscription(&self, chain_id: &str) {
        {
            let mut status = self.status.write();
            status.subscriptions.remove(chain_id);
            status.update_health();
        }

        // Update OTEL metrics
        #[cfg(feature = "otel")]
        if let Some(ref metrics) = self.metrics {
            metrics.update_subscription_count(self.status.read().subscriptions.len());
        }

        // Persist immediately
        let _ = self.flush_tx.try_send(FlushMessage::Flush);

        info!("Unregistered subscription for {}", chain_id);
    }

    fn get_status(&self) -> ProviderStatus {
        self.status.read().clone()
    }

    fn get_subscription_status(&self, chain_id: &str) -> Option<SubscriptionStatus> {
        self.status.read().subscriptions.get(chain_id).cloned()
    }

    fn is_healthy(&self) -> bool {
        self.status.read().is_healthy()
    }

    fn is_chain_connected(&self, chain_id: &str) -> bool {
        self.status
            .read()
            .subscriptions
            .get(chain_id)
            .map(|s| s.connection.connected)
            .unwrap_or(false)
    }

    async fn flush(&self) -> anyhow::Result<()> {
        self.do_flush().await
    }

    async fn shutdown(&self) -> anyhow::Result<()> {
        info!("Shutting down provider status tracker");
        let _ = self.flush_tx.send(FlushMessage::Shutdown).await;
        Ok(())
    }
}

impl Drop for ProviderStatusTracker {
    fn drop(&mut self) {
        // Try to send shutdown signal
        let _ = self.flush_tx.try_send(FlushMessage::Shutdown);
    }
}
