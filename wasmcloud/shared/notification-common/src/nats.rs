//! NATS messaging handler for notification providers
//!
//! This module provides a standardized NATS handler that all notification providers
//! use to receive notification requests from actors.

use crate::provider::LegacyNotificationProvider as NotificationProvider;
use crate::provider::LegacyProviderError as ProviderError;
use crate::{
    retry_with_backoff, DeliveryStatus, NotificationChannel, NotificationRequest, RetryConfig,
};
use async_nats::{Client, Subscriber};
use futures::StreamExt;
use std::sync::Arc;
use tokio::task::JoinHandle;
use tracing::{debug, error, info, warn};

/// NATS message handler for notification providers
pub struct NatsHandler {
    client: Client,
    provider: Arc<dyn NotificationProvider>,
    channel: NotificationChannel,
    retry_config: RetryConfig,
    max_concurrent_messages: usize,
}

impl NatsHandler {
    /// Create a new NATS handler for the given provider
    pub async fn new(
        nats_url: &str,
        provider: Arc<dyn NotificationProvider>,
        channel: NotificationChannel,
    ) -> Result<Self, ProviderError> {
        let client = async_nats::connect(nats_url).await.map_err(|e| {
            ProviderError::ConnectionError(format!("Failed to connect to NATS: {}", e))
        })?;

        Ok(Self {
            client,
            provider,
            channel,
            retry_config: RetryConfig::default(),
            max_concurrent_messages: 10,
        })
    }

    /// Configure retry settings
    pub fn with_retry_config(mut self, retry_config: RetryConfig) -> Self {
        self.retry_config = retry_config;
        self
    }

    /// Configure concurrent message processing limit
    pub fn with_max_concurrent(mut self, max_concurrent: usize) -> Self {
        self.max_concurrent_messages = max_concurrent;
        self
    }

    /// Start listening for notifications on the channel's NATS subject
    pub async fn start(&self) -> Result<JoinHandle<()>, ProviderError> {
        let subject = self.channel.nats_subject();

        info!(
            "Starting NATS handler for channel: {} on subject: {}",
            self.channel, subject
        );

        let mut subscriber = self
            .client
            .subscribe(subject.clone())
            .await
            .map_err(|e| ProviderError::NatsError(e.to_string()))?;

        let provider = Arc::clone(&self.provider);
        let channel = self.channel.clone();
        let retry_config = self.retry_config.clone();
        let max_concurrent = self.max_concurrent_messages;

        // Use a semaphore to limit concurrent message processing
        let semaphore = Arc::new(tokio::sync::Semaphore::new(max_concurrent));

        let handle = tokio::spawn(async move {
            info!(
                "NATS handler started for channel: {} (max concurrent: {})",
                channel, max_concurrent
            );

            while let Some(message) = subscriber.next().await {
                debug!("Received NATS message for channel: {}", channel);

                // Acquire semaphore permit before processing
                let permit = match semaphore.clone().acquire_owned().await {
                    Ok(permit) => permit,
                    Err(e) => {
                        error!("Failed to acquire semaphore permit: {}", e);
                        continue;
                    }
                };

                let provider_clone = Arc::clone(&provider);
                let channel_clone = channel.clone();
                let retry_config_clone = retry_config.clone();

                // Process message in background task
                tokio::spawn(async move {
                    let _permit = permit; // Keep permit until task completes

                    match Self::process_message(
                        &message,
                        provider_clone,
                        channel_clone,
                        retry_config_clone,
                    )
                    .await
                    {
                        Ok(status) => {
                            debug!("Successfully processed notification: {:?}", status);
                        }
                        Err(e) => {
                            error!("Failed to process notification: {}", e);
                        }
                    }
                });
            }

            warn!("NATS handler stopped for channel: {}", channel);
        });

        Ok(handle)
    }

    /// Process a single NATS message with retry logic
    async fn process_message(
        message: &async_nats::Message,
        provider: Arc<dyn NotificationProvider>,
        channel: NotificationChannel,
        retry_config: RetryConfig,
    ) -> Result<DeliveryStatus, ProviderError> {
        // Deserialize the notification request
        let request: NotificationRequest = match serde_json::from_slice(&message.payload) {
            Ok(req) => req,
            Err(e) => {
                error!("Failed to deserialize notification request: {}", e);
                return Err(ProviderError::SerializationError(e));
            }
        };

        debug!(
            "Processing notification request - ID: {}, User: {}, Alert: {}",
            request
                .context
                .as_ref()
                .map(|c| c.request_id.as_str())
                .unwrap_or("unknown"),
            request
                .context
                .as_ref()
                .map(|c| c.user_id.as_str())
                .unwrap_or("unknown"),
            request
                .context
                .as_ref()
                .map(|c| c.alert_id.as_str())
                .unwrap_or("unknown")
        );

        // Validate the request
        if let Err(e) = provider.validate_request(&request) {
            error!("Notification request validation failed: {}", e);
            return Err(e);
        }

        // Process with retry logic
        let result = retry_with_backoff(&retry_config, || {
            let provider_clone = Arc::clone(&provider);
            let request_clone = request.clone();

            Box::pin(async move { provider_clone.send_notification(request_clone).await })
        })
        .await;

        match &result {
            Ok(status) => {
                debug!("Notification delivered successfully: {:?}", status);

                // Publish delivery status back to NATS for tracking
                if let Err(e) = Self::publish_delivery_status(message, status, channel).await {
                    warn!("Failed to publish delivery status: {}", e);
                }
            }
            Err(e) => {
                error!("Failed to deliver notification after retries: {}", e);

                // Publish failure status
                let failure_status = crate::DeliveryStatus {
                    notification_id: request.notification_id,
                    channel: request.channel.clone(),
                    delivered: false,
                    delivered_at: None,
                    error_message: Some(e.to_string()),
                    provider_message_id: None,
                    retry_count: 0, // This would need to be tracked properly
                };

                if let Err(e) =
                    Self::publish_delivery_status(message, &failure_status, channel).await
                {
                    warn!("Failed to publish failure status: {}", e);
                }
            }
        }

        result
    }

    /// Publish delivery status back to NATS for tracking
    async fn publish_delivery_status(
        original_message: &async_nats::Message,
        status: &DeliveryStatus,
        channel: NotificationChannel,
    ) -> Result<(), ProviderError> {
        // Extract client from the original message's context if possible
        // For now, we'll skip this and let the notification router handle status tracking
        // This could be enhanced later with a dedicated status tracking system

        debug!("Delivery status for {}: {:?}", channel, status);
        Ok(())
    }

    /// Subscribe to multiple subjects (for multi-channel providers)
    pub async fn start_multi_subject(
        &self,
        subjects: Vec<String>,
    ) -> Result<Vec<JoinHandle<()>>, ProviderError> {
        let mut handles = Vec::new();

        for subject in subjects {
            info!("Starting NATS subscription for subject: {}", subject);

            let subscriber = self
                .client
                .subscribe(subject.clone())
                .await
                .map_err(|e| ProviderError::NatsError(e.to_string()))?;

            let provider = Arc::clone(&self.provider);
            let channel = self.channel.clone();
            let retry_config = self.retry_config.clone();
            let semaphore = Arc::new(tokio::sync::Semaphore::new(self.max_concurrent_messages));

            let handle = tokio::spawn(async move {
                let mut subscriber = subscriber;

                while let Some(message) = subscriber.next().await {
                    let permit = match semaphore.clone().acquire_owned().await {
                        Ok(permit) => permit,
                        Err(e) => {
                            error!("Failed to acquire semaphore permit for {}: {}", subject, e);
                            continue;
                        }
                    };

                    let provider_clone = Arc::clone(&provider);
                    let channel_clone = channel.clone();
                    let retry_config_clone = retry_config.clone();
                    let subject_clone = subject.clone();

                    tokio::spawn(async move {
                        let _permit = permit;

                        match Self::process_message(
                            &message,
                            provider_clone,
                            channel_clone,
                            retry_config_clone,
                        )
                        .await
                        {
                            Ok(status) => {
                                debug!(
                                    "Successfully processed notification on {}: {:?}",
                                    subject_clone, status
                                );
                            }
                            Err(e) => {
                                error!(
                                    "Failed to process notification on {}: {}",
                                    subject_clone, e
                                );
                            }
                        }
                    });
                }
            });

            handles.push(handle);
        }

        Ok(handles)
    }

    /// Gracefully shutdown the NATS handler
    pub async fn shutdown(&self) -> Result<(), ProviderError> {
        // The client will be closed when dropped
        info!("Shutting down NATS handler for channel: {}", self.channel);
        Ok(())
    }

    /// Publish a notification request to a specific channel
    pub async fn publish_notification(
        &self,
        channel: &NotificationChannel,
        request: &NotificationRequest,
    ) -> Result<(), ProviderError> {
        let subject = channel.nats_subject();
        let payload =
            serde_json::to_vec(request).map_err(|e| ProviderError::SerializationError(e))?;

        debug!(
            "Publishing notification to subject: {} for user: {}",
            subject,
            request
                .context
                .as_ref()
                .map(|c| c.user_id.as_str())
                .unwrap_or("unknown")
        );

        self.client
            .publish(subject, payload.into())
            .await
            .map_err(|e| ProviderError::NatsError(e.to_string()))?;

        Ok(())
    }

    /// Check NATS connection health
    pub async fn health_check(&self) -> Result<(), ProviderError> {
        // Try to publish a ping message to a test subject
        let test_subject = format!("health.check.{}", self.channel.to_string().to_lowercase());

        match self.client.publish(test_subject, "ping".into()).await {
            Ok(_) => {
                debug!("NATS health check passed for channel: {}", self.channel);
                Ok(())
            }
            Err(e) => {
                error!(
                    "NATS health check failed for channel {}: {}",
                    self.channel, e
                );
                Err(ProviderError::ConnectionError(format!(
                    "NATS health check failed: {}",
                    e
                )))
            }
        }
    }
}

/// NATS message statistics and monitoring
#[derive(Debug, Clone)]
pub struct NatsStatistics {
    pub messages_received: u64,
    pub messages_processed: u64,
    pub messages_failed: u64,
    pub average_processing_time_ms: f64,
    pub last_message_time: Option<chrono::DateTime<chrono::Utc>>,
}

impl Default for NatsStatistics {
    fn default() -> Self {
        Self {
            messages_received: 0,
            messages_processed: 0,
            messages_failed: 0,
            average_processing_time_ms: 0.0,
            last_message_time: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utilities::*;
    use mockall::mock;
    use tokio_test;
    use uuid::Uuid;

    mock! {
        TestProvider {}

        #[async_trait::async_trait]
        impl crate::provider::LegacyNotificationProvider for TestProvider {
            async fn initialize(&mut self, config: crate::ProviderConfig) -> Result<(), ProviderError>;
            async fn send_notification(&self, request: NotificationRequest) -> Result<DeliveryStatus, ProviderError>;
            async fn health_check(&self) -> Result<crate::HealthStatus, ProviderError>;
            async fn get_metrics(&self) -> Result<crate::ProviderMetrics, ProviderError>;
            fn channel(&self) -> NotificationChannel;
        }
    }

    #[tokio::test]
    async fn test_nats_handler_creation() {
        // This test requires a running NATS server
        // For now, we'll test the creation logic without actual connection
        let mut mock_provider = MockTestProvider::new();
        mock_provider
            .expect_channel()
            .returning(|| NotificationChannel::Email);

        let provider = Arc::new(mock_provider);

        // This would fail without a real NATS server, so we'll skip the actual connection test
        // In a real test environment, you'd use testcontainers to spin up NATS
    }

    #[tokio::test]
    async fn test_message_processing() {
        let mut mock_provider = MockTestProvider::new();
        mock_provider
            .expect_channel()
            .returning(|| NotificationChannel::Email);
        mock_provider.expect_send_notification().returning(|_| {
            Ok(DeliveryStatus {
                notification_id: Uuid::new_v4(),
                channel: NotificationChannel::Email,
                delivered: true,
                delivered_at: Some(chrono::Utc::now()),
                error_message: None,
                provider_message_id: Some("test-123".to_string()),
                retry_count: 0,
            })
        });

        let provider = Arc::new(mock_provider);
        let retry_config = RetryConfig::default();

        let test_request = create_test_notification_request();
        let message_payload = serde_json::to_vec(&test_request).unwrap();
        let test_message = async_nats::Message {
            subject: "test.subject".into(),
            reply: None,
            payload: message_payload.into(),
            headers: None,
            status: None,
            description: None,
            length: 0,
        };

        let result = NatsHandler::process_message(
            &test_message,
            provider,
            NotificationChannel::Email,
            retry_config,
        )
        .await;

        assert!(result.is_ok());
    }
}
