use crate::{
    AlertSchedulerConfig, AlertSchedulerError, NatsClient, RedisManager, Result, RuntimeStore,
    ScheduleRequestHandler, ScheduleScanner,
};
use async_trait::async_trait;
use futures::StreamExt;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tokio::task::JoinHandle;
use tracing::{info, warn};
use wasmcloud_provider_sdk::Provider;

/// Alert Scheduler Provider (wasmCloud capability provider)
pub struct AlertSchedulerProvider {
    _config: AlertSchedulerConfig,
    _redis: Arc<RedisManager>,
    nats: Arc<NatsClient>,
    store: Arc<RuntimeStore>,
    scanner_task: Arc<RwLock<Option<JoinHandle<()>>>>,
    schedule_request_task: Arc<RwLock<Option<JoinHandle<()>>>>,
}

impl AlertSchedulerProvider {
    pub async fn from_host_data(host_data: wasmcloud_provider_sdk::HostData) -> Result<Self> {
        let config = if !host_data.config.is_empty() {
            AlertSchedulerConfig::from_properties(&host_data.config)
                .map_err(|e| AlertSchedulerError::Configuration(format!("Config error: {}", e)))?
        } else {
            AlertSchedulerConfig::from_env().unwrap_or_default()
        };

        Self::new(config).await
    }

    pub async fn new(config: AlertSchedulerConfig) -> Result<Self> {
        info!("Initializing Alert Scheduler Provider (alert runtime)");

        let redis = Arc::new(RedisManager::new(config.clone()).await?);
        let nats =
            Arc::new(NatsClient::new(&config.nats_url, config.nats_stream_name.clone()).await?);
        let store = Arc::new(RuntimeStore::new(redis.clone()));

        let provider = Self {
            _config: config.clone(),
            _redis: redis,
            nats: nats.clone(),
            store: store.clone(),
            scanner_task: Arc::new(RwLock::new(None)),
            schedule_request_task: Arc::new(RwLock::new(None)),
        };

        provider
            .start_schedule_request_consumer(config.clone(), store.clone(), nats.clone())
            .await?;
        provider
            .start_schedule_scanner(config.clone(), store.clone(), nats.clone())
            .await?;

        Ok(provider)
    }

    async fn start_schedule_scanner(
        &self,
        config: AlertSchedulerConfig,
        store: Arc<RuntimeStore>,
        nats: Arc<NatsClient>,
    ) -> Result<()> {
        let scanner = ScheduleScanner::new(config, store, nats);
        let interval = Duration::from_secs(60);
        let handle = tokio::spawn(async move {
            scanner.run_loop(interval).await;
        });
        *self.scanner_task.write().await = Some(handle);
        Ok(())
    }

    async fn start_schedule_request_consumer(
        &self,
        config: AlertSchedulerConfig,
        store: Arc<RuntimeStore>,
        nats: Arc<NatsClient>,
    ) -> Result<()> {
        let handler = Arc::new(ScheduleRequestHandler::new(config, store, nats.clone()));

        let mut subscriber = self.nats.subscribe_to_schedule_requests().await?;

        let handle = tokio::spawn(async move {
            while let Some(msg_result) = subscriber.next().await {
                let msg = match msg_result {
                    Ok(m) => m,
                    Err(e) => {
                        warn!("Failed to receive schedule message: {}", e);
                        continue;
                    }
                };

                let subject = msg.subject.as_str().to_string();
                let payload = msg.payload.clone();

                let result = if subject == "alerts.schedule.periodic" {
                    match serde_json::from_slice::<alert_runtime_common::AlertSchedulePeriodicV1>(
                        &payload,
                    ) {
                        Ok(req) => handler.handle_periodic(req).await.map(|_| ()),
                        Err(e) => Err(AlertSchedulerError::Serialization(e)),
                    }
                } else if subject == "alerts.schedule.one_time" {
                    match serde_json::from_slice::<alert_runtime_common::AlertScheduleOneTimeV1>(
                        &payload,
                    ) {
                        Ok(req) => handler.handle_one_time(req).await.map(|_| ()),
                        Err(e) => Err(AlertSchedulerError::Serialization(e)),
                    }
                } else if subject == "alerts.schedule.event_driven" {
                    match serde_json::from_slice::<alert_runtime_common::AlertScheduleEventDrivenV1>(
                        &payload,
                    ) {
                        Ok(req) => handler.handle_event_driven(req).await.map(|_| ()),
                        Err(e) => Err(AlertSchedulerError::Serialization(e)),
                    }
                } else {
                    Ok(())
                };

                match result {
                    Ok(_) => {
                        if let Err(e) = msg.ack().await {
                            warn!("Failed to ack schedule message: {}", e);
                        }
                    }
                    Err(e) => {
                        warn!("Failed to handle schedule message {}: {}", subject, e);
                        if let Err(nak) = msg
                            .ack_with(async_nats::jetstream::AckKind::Nak(None))
                            .await
                        {
                            warn!("Failed to NAK schedule message: {}", nak);
                        }
                    }
                }
            }
        });

        *self.schedule_request_task.write().await = Some(handle);
        Ok(())
    }
}

// Provider trait implementation for wasmCloud SDK v0.16 (default impls)
#[async_trait]
impl Provider for AlertSchedulerProvider {}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider>() {}
        assert_provider::<AlertSchedulerProvider>();
    }
}
